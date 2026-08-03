from __future__ import annotations

import logging
import math
from typing import Any, Literal

import openglider.rs

from openglider.glider.parametric.config import ParametricGliderConfig
from openglider.glider.parametric.leparagliding import LeparaglidingShapeParams
from openglider.glider.shape import Shape, ShapeBase
from openglider.utils import linspace
from openglider.utils.dataclass import dataclass
from openglider.utils.types import CurveType, SymmetricCurveType
from openglider.vector.unit import Angle, Percentage

logger = logging.getLogger(__name__)


@dataclass
class ParametricShape(ShapeBase):
    front_curve: SymmetricCurveType
    back_curve: SymmetricCurveType
    rib_distribution: CurveType
    cell_num: int
    config: ParametricGliderConfig
    # Optional cell-width coefficients (cell-distribution "sliders" mode).
    # These values are used directly for rib positions; ``rib_distribution`` is
    # only authoritative when this is ``None`` (spline mode).
    cell_widths: list[float] | None = None

    num_shape_interpolation = 50
    num_distribution_interpolation = 50
    num_depth_integral = 50

    # cm (leparagliding) -> m (openglider internal)
    LEPARAGLIDING_UNIT_SCALE = 0.01

    class Config:
        arbitrary_types_allowed = True


    def __post_init__(self) -> None:
        self.rescale_curves()

    @classmethod
    def __from_json__(cls, front_curve: Any, back_curve: Any, rib_distribution: Any,
                      cell_num: int, config: Any, cell_widths: list[float] | None = None,
                      **_legacy: Any) -> ParametricShape:
        # ``**_legacy`` tolerates fields from older saves (e.g. parametric_params),
        # which now load as a plain spline shape.
        return cls(front_curve, back_curve, rib_distribution, cell_num,
                   config=config, cell_widths=cell_widths)

    def __repr__(self) -> str:
        return "{}\n\tcells: {}\n\tarea: {:.2f}\n\taspect_ratio: {:.2f}".format(
            super().__repr__(),
            self.cell_num,
            self.area,
            self.aspect_ratio
        )

    def copy(self) -> ParametricShape:
        return ParametricShape(
            self.front_curve.copy(),
            self.back_curve.copy(),
            self.rib_distribution.copy(),
            self.cell_num,
            config=self.config,
            cell_widths=None if self.cell_widths is None else list(self.cell_widths),
        )

    @property
    def _num_cell_widths(self) -> int:
        """Number of cell-width coefficients for the half-wing (no stabi cell)."""
        return self.cell_num // 2 + self.has_center_cell

    def _get_cell_widths(self) -> list[float]:
        """Current cell-width coefficients, padded/trimmed to the cell count.

        Falls back to the coefficients implied by the current rib distribution
        (so switching to cell-width "sliders" mode preserves the shape), then to
        uniform. Ported from openglider_lines' ``ParametricShape._get_cell_widths``.
        """
        needed = self._num_cell_widths
        coeffs = (
            list(self.cell_widths)
            if self.cell_widths is not None
            else self._current_cell_widths()
        )
        if len(coeffs) < needed:
            coeffs.extend([1.0] * (needed - len(coeffs)))
        elif len(coeffs) > needed:
            coeffs = coeffs[:needed]
        return coeffs

    def _current_cell_widths(self) -> list[float]:
        """Cell-width coefficients (mean ~1) implied by the current rib
        distribution."""
        x_abs = [abs(x) for x in self.rib_x_values]
        positions = ([0.0] + x_abs[1:]) if self.has_center_cell else list(x_abs)
        widths = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
        if self.has_center_cell and widths:
            widths[0] *= 2.0  # centre coefficient is a full cell
        mean = (sum(widths) / len(widths)) if widths else 1.0
        return [w / (mean or 1.0) for w in widths]

    def apply_cell_widths(self, widths: list[float]) -> None:
        """Set cell-width coefficients (sliders mode) and rederive the rib
        distribution from them."""
        self.cell_widths = list(widths)

    def _cell_width_positions(self) -> list[float]:
        """Exact right-half rib positions, normalized to the half-span.

        For an odd cell count the first slider represents the full centre cell,
        so only half of that width lies on the right half-wing.
        """
        coeffs = self._get_cell_widths()
        if self.has_center_cell:
            half_widths = [coeffs[0] * 0.5] + coeffs[1:]
            positions = [half_widths[0]]
            for width in half_widths[1:]:
                positions.append(positions[-1] + width)
        else:
            half_widths = coeffs
            positions = [0.0]
            for width in half_widths:
                positions.append(positions[-1] + width)

        total = sum(half_widths)
        return [position / total for position in positions]

    @property
    def baseline(self) -> openglider.rs.vector.PolyLine2D:
        return self.get_baseline(self.config.baseline_pct or Percentage(0.))

    def get_baseline(self, pct: Percentage) -> openglider.rs.vector.PolyLine2D:
        shape = self.get_half_shape()
        return shape.get_baseline(pct)

    @property
    def has_center_cell(self) -> bool:
        return self.cell_num % 2 > 0

    @property
    def half_cell_num(self) -> int:
        return self.cell_num // 2 + self.has_center_cell + self.config.has_stabicell

    @property
    def half_rib_num(self) -> int:
        return self.half_cell_num + 1 - self.has_center_cell + self.config.has_stabicell

    def rescale_curves(self) -> None:
        span = self.span

        dist_scale = 1 / self.rib_distribution.controlpoints.nodes[-1][0]
        self.rib_distribution.controlpoints = self.rib_distribution.controlpoints.scale(
            openglider.rs.vector.Vector2D([dist_scale, 1])
        )

        back_scale = span / self.back_curve.controlpoints.nodes[-1][0]
        self.back_curve.controlpoints = self.back_curve.controlpoints.scale(
            openglider.rs.vector.Vector2D([back_scale, 1])
        )

    @property
    def rib_dist_interpolation(self) -> list[tuple[float, float]]:
        """Return normalized rib positions and their distribution coordinates."""
        start = self.has_center_cell / self.cell_num
        num = self.cell_num // 2 + 1
        distribution_values = list(linspace(start, 1, num))
        if self.cell_widths is not None:
            return list(zip(self._cell_width_positions(), distribution_values))

        data = self.rib_distribution.get_sequence(self.num_distribution_interpolation)
        interpolation = openglider.rs.vector.Interpolation([[p[1], p[0]] for p in data])
        return [(interpolation.get_value(i), i) for i in distribution_values]

    # besser mit spezieller bezier?
    @property
    def rib_dist_controlpoints(self) -> openglider.rs.vector.PolyLine2D:
        return openglider.rs.vector.PolyLine2D(self.rib_distribution.controlpoints.nodes[1:-1])

    @rib_dist_controlpoints.setter
    def rib_dist_controlpoints(self, arr: list[list[float]] | list[openglider.rs.vector.Vector2D]) -> None:

        self.rib_distribution.controlpoints = openglider.rs.vector.PolyLine2D([[0., 0.]] + arr + [[1., 1.]])

    @property
    def rib_x_values(self) -> list[float]:
        xvalues = [p[0]*self.span for p in self.rib_dist_interpolation]

        if self.config.has_stabicell:
            width = self.config.stabi_cell_width * (xvalues[-1] - xvalues[-2])
            xvalues.append(xvalues[-1] + width)
            xvalues = [p*self.span/xvalues[-1] for p in xvalues]
        
        if self.has_center_cell:
            xvalues.insert(0, -xvalues[0])

        return xvalues


    @property
    def cell_x_values(self) -> list[float]:
        ribs = self.rib_x_values

        cells = []
        for x1, x2 in zip(ribs[:-1], ribs[1:]):
            cells.append((x1+x2)/2)

        return cells

    def get_half_shape(self, zrot: list[Angle | None] | None = None) -> Shape:
        """
        Return shape of the glider:
        [ribs, front, back]
        """
        self.rescale_curves()
        num = self.num_shape_interpolation
        front_int = openglider.rs.vector.Interpolation(self.front_curve.get_sequence(num).nodes)
        back_int = openglider.rs.vector.Interpolation(self.back_curve.get_sequence(num).nodes)
        
        distribution = self.rib_x_values
        if self.has_center_cell:
            distribution = distribution[1:]

        front = [[x, front_int.get_value(x)] for x in distribution]
        back = [[x, back_int.get_value(x)] for x in distribution]

        if self.config.has_stabicell:
            y1 = front[-2][1]
            y2 = back[-2][1]
            delta = (y2 - y1) * (1-self.config.stabi_cell_length)

            front[-1][1] = y1 + delta * self.config.stabi_cell_position
            back[-1][1] = y2 - delta * (1-self.config.stabi_cell_position)
        
        if self.has_center_cell:
            p1 = front[0][:]
            p1[0] = - p1[0]
            front.insert(0, p1)

            p2 = back[0][:]
            p2[0] = - p2[0]
            back.insert(0, p2)

        return Shape(
            front=openglider.rs.vector.PolyLine2D(front),
            back=openglider.rs.vector.PolyLine2D(back)
        )

    def get_shape(self) -> Shape:
        """
        Return shape of the glider:
        [ribs, front, back]
        """
        return self.get_half_shape().copy_complete()

    def __getitem__(self, pos: tuple[int, float]) -> openglider.rs.vector.Vector2D:
        """if first argument is negative the point is returned mirrored"""
        rib_nr, rib_pos = pos
        ribs = self.ribs
        neg = (rib_nr < 0)
        sign = -neg * 2 + 1
        if rib_nr > len(ribs):
            raise ValueError(f"invalid rib_nr: {rib_nr}")

        fr, ba = ribs[abs(rib_nr + neg * self.has_center_cell)]
        chord = ba[1] - fr[1]
        x = fr[0]
        y = fr[1] + rib_pos * chord
        return openglider.rs.vector.Vector2D([sign * x, y])

    @property
    def ribs(self) -> list[tuple[openglider.rs.vector.Vector2D, openglider.rs.vector.Vector2D]]:
        return self.get_half_shape().ribs
    
    @property
    def chords(self) -> list[float]:
        return [(p1-p2).length() for p1, p2 in self.ribs]

    def get_rib_point(self, rib_no: int, x: float) -> openglider.rs.vector.Vector2D:
        ribs = list(self.ribs)
        rib = ribs[rib_no]

        try:
            return rib[0] + (rib[1] - rib[0]) * x
        except TypeError:
            return rib[0]

    def get_shape_point(self, x: float, y: float) -> openglider.rs.vector.Vector2D:
        k = x%1
        rib1 = int(x)
        p1 = self.get_rib_point(rib1, y)

        if k > 0:
            p2 = self.get_rib_point(rib1+1, y)
            return p1 + (p2-p1) * k
        else:
            return p1

    @property
    def depth_integrated(self) -> list[tuple[float, float]]:
        """
        Return A(x)
        """
        num = self.num_depth_integral
        x_values = linspace(0, self.span, num)
        front_int = openglider.rs.vector.Interpolation(self.front_curve.get_sequence(num).nodes)
        back_int = openglider.rs.vector.Interpolation(self.back_curve.get_sequence(num).nodes)
        integrated_depth = [0.]
        for x in x_values[1:]:
            depth = front_int.get_value(x) - back_int.get_value(x)
            integrated_depth.append(integrated_depth[-1] + 1. / depth)
        y_values = [i / integrated_depth[-1] for i in integrated_depth]

        x_values_normalized = [x/self.span for x in x_values]
        return list(zip(x_values_normalized, y_values))

    def set_const_cell_dist(self) -> None:
        const_dist = openglider.rs.vector.PolyLine2D(list(self.depth_integrated))
        num_pts = len(self.rib_distribution.controlpoints)
        self.rib_distribution = self.rib_distribution.fit(const_dist, numpoints=num_pts)  # type: ignore

    ############################################################################
    # scaling stuff
    def scale(self, x: float=1., y: float=None) -> None:
        if y is None:
            y = x

        print("scale factor: ", x, y)
        self.front_curve.controlpoints = self.front_curve.controlpoints.scale(openglider.rs.vector.Vector2D([x, y]))

        # scale back to fit with front
        factor = self.front_curve.controlpoints.nodes[-1][0] / self.back_curve.controlpoints.nodes[-1][0]
        self.back_curve.controlpoints = self.back_curve.controlpoints.scale(openglider.rs.vector.Vector2D([factor, y]))

        # scale rib_dist
        #factor = 1 / self.rib_distribution.controlpoints.nodes[-1][0]
        #self.rib_distribution.controlpoints = self.rib_distribution.controlpoints.scale([factor, 1])

    @property
    def area(self) -> float:
        return self.get_shape().area

    def set_area(self, area: float, fixed: Literal["aspect_ratio"] | Literal["span"] | Literal["depth"]="aspect_ratio") -> float:
        if fixed == "aspect_ratio":
            # scale proportional
            factor = math.sqrt(area/self.area)
            self.scale(factor, factor)
        elif fixed == "span":
            # scale y
            factor = area/self.area
            self.scale(1, factor)
        elif fixed == "depth":
            # scale span
            factor = area/self.area
            self.scale(factor, 1)
        else:
            raise ValueError(f"Invalid Value: {fixed} for 'constant' (aspect_ratio, span, depth)")

        return self.area

    def get_sweep(self) -> float:
        ribs = self.ribs

        center_f = ribs[0][0]
        center_b = ribs[0][1]

        if self.config.has_stabicell:
            tip_rib = ribs[-2]
        else:
            tip_rib = ribs[-1]

        tip_f = tip_rib[0]
        tip_b = tip_rib[1]

        dy = ((tip_f + tip_b) * 0.5)[1] - center_f[1]

        return dy / (center_f + center_b)[1]
    
    def _clean(self) -> None:
        p0 = self.front_curve.get(0) * openglider.rs.vector.Vector2D([0, -1])
        self.front_curve.controlpoints = self.front_curve.controlpoints.move(p0)
        self.back_curve.controlpoints = self.back_curve.controlpoints.move(p0)
    
    def set_sweep(self, sweep: float) -> float:
        current_sweep = self.get_sweep()
        self.rescale_curves()

        ribs = self.ribs
        if self.config.has_stabicell:
            ribs.pop(-1)

        center_chord = (ribs[0][0] - ribs[0][1]).length()
        diff = (current_sweep - sweep) * center_chord

        x0 = ribs[0][0][0]
        span = ribs[-1][0][0] - x0

        front = openglider.rs.vector.PolyLine2D([p + openglider.rs.vector.Vector2D([0, (p[0]-x0)*diff/span]) for p, _ in ribs])
        back = openglider.rs.vector.PolyLine2D([p + openglider.rs.vector.Vector2D([0, (p[0]-x0)*diff/span]) for _, p in ribs])

        # .fit expects a control-point count (<= number of input points); the
        # curve's `numpoints` is its interpolation resolution (~100), not that.
        num_cp_front = min(len(self.front_curve.controlpoints), len(front.nodes))
        num_cp_back = min(len(self.back_curve.controlpoints), len(back.nodes))
        self.front_curve = self.front_curve.fit(front, num_cp_front)  # type: ignore
        self.back_curve = self.back_curve.fit(back, num_cp_back)  # type: ignore

        y0 = self.ribs[0][0][1]

        self.front_curve.controlpoints = self.front_curve.controlpoints.move(openglider.rs.vector.Vector2D([0, -y0]))
        self.back_curve.controlpoints = self.back_curve.controlpoints.move(openglider.rs.vector.Vector2D([0, -y0]))
        
        return self.get_sweep()

    @property
    def aspect_ratio(self) -> float:
        # todo: span -> half span, area -> full area???
        return (2*self.span) ** 2 / self.area

    def set_aspect_ratio(self, ar: float, fixed: Literal["span"] | Literal["area"]="span") -> None:
        ar0 = self.aspect_ratio
        if fixed == "span":
            self.scale(y=ar0 / ar)
        elif fixed == "area":
            self.scale(x=math.sqrt(ar / ar0), y=math.sqrt(ar0 / ar))

    @property
    def span(self) -> float:
        span = self.front_curve.controlpoints.nodes[-1][0]
        return span

    @span.setter
    def span(self, span: float) -> None:
        factor = span/self.span
        self.scale(factor, 1)

    def set_span(self, span: float, fixed: Literal["area"] | Literal["aspect_ratio"] | None="area") -> None:
        span_0 = self.span
        if fixed == "area":
            self.scale(x=span / span_0, y=span_0 / span)
        elif fixed == "aspect_ratio":
            self.scale(x=span/span_0, y=span/span_0)
        else:
            self.scale(x=span/span_0, y=1)


class LeparaglidingShape(ParametricShape):
    """Planform whose leading and trailing edges use Leparagliding parameters.

    Cell distribution is independent: it can still be an editable spline or a
    list of explicit cell-width coefficients, just like on a spline planform.
    """

    _NUM_CURVE_SAMPLES = 200
    _NUM_CP = 7

    def __init__(
        self,
        params: LeparaglidingShapeParams,
        config: ParametricGliderConfig,
        cell_num: int,
        rib_distribution: CurveType | None = None,
        cell_widths: list[float] | None = None,
    ) -> None:
        front, back = self._compile_planform(params)

        if rib_distribution is None:
            if cell_widths is None:
                raise ValueError(
                    "LeparaglidingShape requires a rib distribution or cell widths"
                )
            # Slider mode uses cell_widths directly. This linear curve is only a
            # dormant placeholder required by the common ParametricShape API.
            rib_distribution = openglider.rs.spline.BSplineCurve(
                [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
            )

        super().__init__(
            front, back, rib_distribution, cell_num,
            config=config,
            cell_widths=None if cell_widths is None else list(cell_widths),
        )
        self.params = params

    def __json__(self) -> dict[str, Any]:
        return {
            "params": self.params.to_dict(),
            "config": self.config,
            "rib_distribution": self.rib_distribution,
            "cell_num": self.cell_num,
            "cell_widths": self.cell_widths,
        }

    @classmethod
    def __from_json__(  # type: ignore[override]
        cls,
        params: dict[str, Any],
        config: Any,
        cell_num: int,
        rib_distribution: CurveType | None = None,
        cell_widths: list[float] | None = None,
    ) -> LeparaglidingShape:
        return cls(
            LeparaglidingShapeParams.from_dict(params), config,
            rib_distribution=rib_distribution,
            cell_num=cell_num,
            cell_widths=cell_widths,
        )

    def copy(self) -> LeparaglidingShape:
        return LeparaglidingShape(
            LeparaglidingShapeParams.from_dict(self.params.to_dict()),
            self.config,
            rib_distribution=self.rib_distribution.copy(),
            cell_num=self.cell_num,
            cell_widths=None if self.cell_widths is None else list(self.cell_widths),
        )

    @classmethod
    def _compile_planform(cls, params: LeparaglidingShapeParams) -> tuple[Any, Any]:
        """Fit front/back curves from the analytic LE/TE.

        Unit convention: leparagliding values are in cm, openglider stores metres,
        so sampled curves are scaled by ``LEPARAGLIDING_UNIT_SCALE`` (1/100).
        leparagliding measures chord with y=0 at the LE and y increasing towards
        the TE; openglider's planview points the other way, so y is negated.
        """
        scale = ParametricShape.LEPARAGLIDING_UNIT_SCALE
        le_pts = params.sample_le(cls._NUM_CURVE_SAMPLES)
        te_pts = params.sample_te(cls._NUM_CURVE_SAMPLES)
        front_pl = openglider.rs.vector.PolyLine2D([[x * scale, -y * scale] for x, y in le_pts])
        back_pl = openglider.rs.vector.PolyLine2D([[x * scale, -y * scale] for x, y in te_pts])
        front = openglider.rs.spline.SymmetricBSplineCurve.fit(front_pl, cls._NUM_CP)  # type: ignore
        back = openglider.rs.spline.SymmetricBSplineCurve.fit(back_pl, cls._NUM_CP)  # type: ignore
        return front, back


class ExplicitShape(ParametricShape):
    """Planform defined by explicit per-rib front/back points (half-wing).

    ``front_points`` / ``back_points`` are [x, y] per rib (LE / TE positions).
    Front/back curves are fit through them and the rib distribution is built from
    the rib span positions — no separate cell-width data (spacing is implicit).
    """

    _NUM_CP = 3

    def __init__(self, front_points: list[list[float]], back_points: list[list[float]],
                 cell_num: int, config: ParametricGliderConfig) -> None:
        front, back, rib_dist = self._compile(front_points, back_points)
        super().__init__(front, back, rib_dist, cell_num, config=config, cell_widths=None)
        self.front_points = [list(p) for p in front_points]
        self.back_points = [list(p) for p in back_points]

    def __json__(self) -> dict[str, Any]:
        return {"front_points": self.front_points, "back_points": self.back_points,
                "cell_num": self.cell_num, "config": self.config}

    @classmethod
    def __from_json__(  # type: ignore[override]
        cls, front_points: list[list[float]], back_points: list[list[float]],
        cell_num: int, config: Any
    ) -> ExplicitShape:
        return cls(front_points, back_points, cell_num, config)

    def copy(self) -> ExplicitShape:
        return ExplicitShape([list(p) for p in self.front_points],
                             [list(p) for p in self.back_points], self.cell_num, self.config)

    @classmethod
    def _compile(cls, front_points: list[list[float]], back_points: list[list[float]]) -> tuple[Any, Any, Any]:
        front_pl = openglider.rs.vector.PolyLine2D([list(p) for p in front_points])
        back_pl = openglider.rs.vector.PolyLine2D([list(p) for p in back_points])
        front = openglider.rs.spline.SymmetricBSplineCurve.fit(front_pl, cls._NUM_CP)  # type: ignore
        back = openglider.rs.spline.SymmetricBSplineCurve.fit(back_pl, cls._NUM_CP)  # type: ignore
        rib_dist = cls._rib_distribution_from_points(front_points)
        return front, back, rib_dist

    @staticmethod
    def _rib_distribution_from_points(front_points: list[list[float]]) -> CurveType:
        """Build the rib-distribution curve from per-rib span positions
        (mirrors ``import_ods.get_geometry_explicit``)."""
        has_center = not (front_points[0][0] == 0)
        cell_no = (len(front_points) - 1) * 2 + has_center
        start = (2 - has_center) / cell_no
        const_arr = [0.0] + list(linspace(start, 1, len(front_points) - (not has_center)))
        rib_pos = [0.0] + [p[0] for p in front_points[(not has_center):]]
        rib_pos_int = openglider.rs.vector.Interpolation(list(zip(rib_pos, const_arr)))
        samples = openglider.rs.vector.PolyLine2D(
            [[i, rib_pos_int.get_value(i)] for i in linspace(0, rib_pos[-1], 30)]
        )
        return openglider.rs.spline.BSplineCurve.fit(samples, 3)  # type: ignore
