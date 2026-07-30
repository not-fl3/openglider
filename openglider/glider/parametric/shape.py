from __future__ import annotations

import logging
import math
from typing import Any, Literal

import openglider.rs

from openglider.glider.parametric.config import ParametricGliderConfig
from openglider.glider.parametric.leparagliding import LeparaglidingShapeParams
from openglider.glider.shape import Shape
from openglider.utils import linspace
from openglider.utils.dataclass import dataclass
from openglider.utils.types import CurveType, SymmetricCurveType
from openglider.vector.unit import Angle, Percentage

logger = logging.getLogger(__name__)


@dataclass
class ParametricShape:
    front_curve: SymmetricCurveType
    back_curve: SymmetricCurveType
    rib_distribution: CurveType
    cell_num: int
    config: ParametricGliderConfig
    # When set, the shape was last generated from leparagliding pre-processor
    # parameters. The curves + rib_distribution above stay authoritative (they
    # are the result of fitting the parametric curves); this dict is only
    # restoration metadata for the shape wizard's parametric mode.
    parametric_params: dict[str, Any] | None = None

    num_shape_interpolation = 50
    num_distribution_interpolation = 50
    num_depth_integral = 50

    # cm (leparagliding) -> m (openglider internal)
    LEPARAGLIDING_UNIT_SCALE = 0.01

    class Config:
        arbitrary_types_allowed = True


    def __post_init__(self) -> None:
        self.rescale_curves()

    def __repr__(self) -> str:
        return "{}\n\tcells: {}\n\tarea: {:.2f}\n\taspect_ratio: {:.2f}".format(
            super().__repr__(),
            self.cell_num,
            self.area,
            self.aspect_ratio
        )
    
    def copy(self) -> ParametricShape:
        return self.__class__(
            self.front_curve.copy(),
            self.back_curve.copy(),
            self.rib_distribution.copy(),
            self.cell_num,
            config=self.config,
            parametric_params=(
                None if self.parametric_params is None else dict(self.parametric_params)
            ),
        )

    def apply_leparagliding_params(
        self, params: LeparaglidingShapeParams, num_curve_samples: int = 200
    ) -> None:
        """Rebuild front/back curves and rib distribution from leparagliding params.

        The front/back BSplines are *fit* through the analytical LE/TE curves.
        Unit convention: leparagliding values are in cm, openglider stores metres,
        so sampled curves are scaled by ``LEPARAGLIDING_UNIT_SCALE`` (1/100).
        Coordinate note: leparagliding measures chord with y=0 at the leading
        edge and y increasing towards the trailing edge; openglider's planview
        points the other way, so sampled y values are negated before fitting.
        """
        scale = self.LEPARAGLIDING_UNIT_SCALE
        le_pts = params.sample_le(num_curve_samples)
        te_pts = params.sample_te(num_curve_samples)

        front_polyline = openglider.rs.vector.PolyLine2D(
            [[x * scale, -y * scale] for x, y in le_pts]
        )
        back_polyline = openglider.rs.vector.PolyLine2D(
            [[x * scale, -y * scale] for x, y in te_pts]
        )

        front_cls = type(self.front_curve)
        back_cls = type(self.back_curve)
        num_cp_front = max(len(self.front_curve.controlpoints), 5)
        num_cp_back = max(len(self.back_curve.controlpoints), 5)

        self.front_curve = front_cls.fit(front_polyline, num_cp_front)  # type: ignore
        self.back_curve = back_cls.fit(back_polyline, num_cp_back)  # type: ignore

        self.cell_num = params.cells.cell_num
        self.rib_distribution = self._rib_distribution_from_cell_widths(
            params.compute_cell_widths()
        )
        self.parametric_params = params.to_dict()
        self.rescale_curves()

    def _rib_distribution_from_cell_widths(self, coeffs: list[float]) -> CurveType:
        """Build a rib-distribution curve (span-fraction -> cumulative rib
        fraction) from per-half-cell width coefficients.

        Mirrors the construction in ``import_ods.get_geometry_explicit`` but
        derives rib positions from width coefficients instead of explicit
        geometry. For an odd cell count the first coefficient is a *full* centre
        cell of which only half sits in the half-wing, so it is halved.
        """
        has_center = self.has_center_cell
        if not coeffs:
            coeffs = [1.0]

        if has_center:
            half_widths = [coeffs[0] * 0.5] + list(coeffs[1:])
        else:
            half_widths = list(coeffs)

        total = sum(half_widths) or 1.0
        widths = [w / total for w in half_widths]

        # Cumulative right-half rib span-fractions (last == 1.0).
        if has_center:
            span_fracs = [widths[0]]
            for w in widths[1:]:
                span_fracs.append(span_fracs[-1] + w)
        else:
            span_fracs = [0.0]
            for w in widths:
                span_fracs.append(span_fracs[-1] + w)

        num_ribs = len(span_fracs)
        start = (1.0 / self.cell_num) if has_center else 0.0
        cum_fracs = list(linspace(start, 1.0, num_ribs))

        # Anchor the wing centre (span 0 -> cumulative 0) so the fit passes
        # through the origin; for a centre rib this point already exists.
        points = list(zip(span_fracs, cum_fracs))
        if has_center:
            points = [(0.0, 0.0)] + points

        dist_int = openglider.rs.vector.Interpolation([[sf, cf] for sf, cf in points])
        samples = openglider.rs.vector.PolyLine2D(
            [[x, dist_int.get_value(x)] for x in linspace(0.0, 1.0, 30)]
        )
        # 7 control points keeps the fitted distribution within ~0.2% of span of
        # the exact cell-width positions; fewer over-smooths, more barely helps.
        num_cp = min(7, len(samples.nodes))
        return openglider.rs.spline.BSplineCurve.fit(samples, num_cp)  # type: ignore

    def get_leparagliding_params(self) -> LeparaglidingShapeParams | None:
        """Return the last-saved leparagliding params, or None if not in that mode."""
        if not self.parametric_params:
            return None
        if self.parametric_params.get("mode") != "leparagliding":
            return None
        return LeparaglidingShapeParams.from_dict(self.parametric_params)

    def clear_parametric_params(self) -> None:
        self.parametric_params = None

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
        """
        Interpolate Cell-distribution
        """
        data = self.rib_distribution.get_sequence(self.num_distribution_interpolation)
        interpolation = openglider.rs.vector.Interpolation([[p[1], p[0]] for p in data])
        start = self.has_center_cell / self.cell_num
        num = self.cell_num // 2 + 1
        return [(interpolation.get_value(i), i) for i in linspace(start, 1, num)]

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

        base_shape = Shape(
            front=openglider.rs.vector.PolyLine2D(front),
            back=openglider.rs.vector.PolyLine2D(back)
        )

        if zrot is None:
            return base_shape
        
        baseline = base_shape.get_baseline(self.config.baseline_pct or Percentage(0.)).nodes
        front_new: list[openglider.rs.vector.Vector2D] = []
        back_new: list[openglider.rs.vector.Vector2D] = []

        for rib_no, angle in enumerate(zrot):
            if angle is None:
                front_new.append(openglider.rs.vector.Vector2D(front[rib_no]))
                back_new.append(openglider.rs.vector.Vector2D(back[rib_no]))
            else:
                rotation = openglider.rs.vector.Rotation2D(angle.si)
                front_new.append(
                    baseline[rib_no] + rotation.apply(base_shape.front.nodes[rib_no]-baseline[rib_no])
                )
                back_new.append(
                    baseline[rib_no] + rotation.apply(base_shape.back.nodes[rib_no]-baseline[rib_no])
                )
        
        return Shape(
            front=openglider.rs.vector.PolyLine2D(front_new),
            back=openglider.rs.vector.PolyLine2D(back_new)
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
