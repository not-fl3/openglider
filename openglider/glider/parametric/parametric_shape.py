from __future__ import annotations

import math
from typing import Any, Literal

import openglider.rs

from openglider.glider.parametric.config import ParametricGliderConfig
from openglider.glider.parametric.shape import PlanformShape
from openglider.glider.shape import Shape
from openglider.utils import linspace
from openglider.utils.dataclass import dataclass
from openglider.utils.types import CurveType, SymmetricCurveType
from openglider.vector.unit import Angle, Percentage


@dataclass
class ParametricShape(PlanformShape):
    """Planform represented by editable front/back splines."""

    front_curve: SymmetricCurveType
    back_curve: SymmetricCurveType
    rib_distribution: CurveType
    cell_num: int
    config: ParametricGliderConfig
    cell_widths: list[float] | None = None

    num_shape_interpolation = 50
    num_distribution_interpolation = 50
    num_depth_integral = 50

    def __repr__(self) -> str:
        return "{}\n\tcells: {}\n\tarea: {:.2f}\n\taspect_ratio: {:.2f}".format(
            super().__repr__(),
            self.cell_num,
            self.area,
            self.aspect_ratio
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
    def cell_no(self) -> int:
        return self.cell_num + 2 * self.config.has_stabicell

    @property
    def rib_no(self) -> int:
        return self.cell_no + 1

    @property
    def half_cell_num(self) -> int:
        return self.cell_num // 2 + self.has_center_cell + self.config.has_stabicell

    @property
    def half_rib_num(self) -> int:
        return self.half_cell_num + 1 - self.has_center_cell + self.config.has_stabicell

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
        half_span = self.span / 2
        xvalues = [p[0] * half_span for p in self.rib_dist_interpolation]

        if self.config.has_stabicell:
            width = self.config.stabi_cell_width * (xvalues[-1] - xvalues[-2])
            xvalues.append(xvalues[-1] + width)
            xvalues = [p * half_span / xvalues[-1] for p in xvalues]
        
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

    def _finish_half_shape(
        self, front: list[list[float]], back: list[list[float]]
    ) -> Shape:
        if self.config.has_stabicell:
            y1 = front[-2][1]
            y2 = back[-2][1]
            delta = (y2 - y1) * (1 - self.config.stabi_cell_length)
            front[-1][1] = y1 + delta * self.config.stabi_cell_position
            back[-1][1] = y2 - delta * (1 - self.config.stabi_cell_position)

        if self.has_center_cell:
            front.insert(0, [-front[0][0], front[0][1]])
            back.insert(0, [-back[0][0], back[0][1]])

        return Shape(
            front=openglider.rs.vector.PolyLine2D(front),
            back=openglider.rs.vector.PolyLine2D(back),
        )

    def get_shape(self) -> Shape:
        """Return the complete planform."""
        return self.get_half_shape().copy_complete()

    def get_point(self, x: float | int, y: float | Percentage) -> openglider.rs.vector.Vector2D:
        return self.get_half_shape().get_point(x, y)

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
        """Return normalized integral of inverse chord depth."""
        x_values = linspace(0, self.span / 2, self.num_depth_integral)
        integrated_depth = [0.]
        for x in x_values[1:]:
            integrated_depth.append(integrated_depth[-1] + 1. / self.chord_at(x))
        y_values = [value / integrated_depth[-1] for value in integrated_depth]
        return list(zip([x / (self.span / 2) for x in x_values], y_values))

    def set_const_cell_dist(self) -> None:
        const_dist = openglider.rs.vector.PolyLine2D(list(self.depth_integrated))
        num_pts = len(self.rib_distribution.controlpoints)
        self.rib_distribution = self.rib_distribution.fit(const_dist, numpoints=num_pts)  # type: ignore

    ############################################################################
    # scaling stuff
    @property
    def area(self) -> float:
        return self.get_half_shape().area

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
    
    @property
    def aspect_ratio(self) -> float:
        return self.span ** 2 / self.area

    def set_aspect_ratio(self, ar: float, fixed: Literal["span"] | Literal["area"]="span") -> None:
        ar0 = self.aspect_ratio
        if fixed == "span":
            self.scale(y=ar0 / ar)
        elif fixed == "area":
            self.scale(x=math.sqrt(ar / ar0), y=math.sqrt(ar0 / ar))

    def set_span(self, span: float, fixed: Literal["area"] | Literal["aspect_ratio"] | None="area") -> None:
        span_0 = self.span
        if fixed == "area":
            self.scale(x=span / span_0, y=span_0 / span)
        elif fixed == "aspect_ratio":
            self.scale(x=span/span_0, y=span/span_0)
        else:
            self.scale(x=span/span_0, y=1)


    def __post_init__(self) -> None:
        self.rescale_curves()

    def rescale_curves(self) -> None:
        span = self.span / 2
        dist_scale = 1 / self.rib_distribution.controlpoints.nodes[-1][0]
        self.rib_distribution.controlpoints = self.rib_distribution.controlpoints.scale(
            openglider.rs.vector.Vector2D([dist_scale, 1])
        )
        back_scale = span / self.back_curve.controlpoints.nodes[-1][0]
        self.back_curve.controlpoints = self.back_curve.controlpoints.scale(
            openglider.rs.vector.Vector2D([back_scale, 1])
        )

    def get_half_shape(self, zrot: list[Angle | None] | None = None) -> Shape:
        self.rescale_curves()
        front_int = openglider.rs.vector.Interpolation(
            self.front_curve.get_sequence(self.num_shape_interpolation).nodes
        )
        back_int = openglider.rs.vector.Interpolation(
            self.back_curve.get_sequence(self.num_shape_interpolation).nodes
        )
        distribution = self.rib_x_values[self.has_center_cell:]
        front = [[x, front_int.get_value(x)] for x in distribution]
        back = [[x, back_int.get_value(x)] for x in distribution]
        return self._finish_half_shape(front, back)

    def chord_at(self, x: float) -> float:
        front_int = openglider.rs.vector.Interpolation(
            self.front_curve.get_sequence(self.num_shape_interpolation).nodes
        )
        back_int = openglider.rs.vector.Interpolation(
            self.back_curve.get_sequence(self.num_shape_interpolation).nodes
        )
        return abs(back_int.get_value(x) - front_int.get_value(x))

    def scale(self, x: float = 1., y: float | None = None) -> None:
        if y is None:
            y = x
        self.front_curve.controlpoints = self.front_curve.controlpoints.scale(
            openglider.rs.vector.Vector2D([x, y])
        )
        factor = (
            self.front_curve.controlpoints.nodes[-1][0]
            / self.back_curve.controlpoints.nodes[-1][0]
        )
        self.back_curve.controlpoints = self.back_curve.controlpoints.scale(
            openglider.rs.vector.Vector2D([factor, y])
        )

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
        front = openglider.rs.vector.PolyLine2D([
            p + openglider.rs.vector.Vector2D([0, (p[0] - x0) * diff / span])
            for p, _ in ribs
        ])
        back = openglider.rs.vector.PolyLine2D([
            p + openglider.rs.vector.Vector2D([0, (p[0] - x0) * diff / span])
            for _, p in ribs
        ])
        num_cp_front = min(len(self.front_curve.controlpoints), len(front.nodes))
        num_cp_back = min(len(self.back_curve.controlpoints), len(back.nodes))
        self.front_curve = self.front_curve.fit(front, num_cp_front)  # type: ignore
        self.back_curve = self.back_curve.fit(back, num_cp_back)  # type: ignore
        y0 = self.ribs[0][0][1]
        offset = openglider.rs.vector.Vector2D([0, -y0])
        self.front_curve.controlpoints = self.front_curve.controlpoints.move(offset)
        self.back_curve.controlpoints = self.back_curve.controlpoints.move(offset)
        return self.get_sweep()

    @property
    def span(self) -> float:
        return 2 * self.front_curve.controlpoints.nodes[-1][0]

    @span.setter
    def span(self, span: float) -> None:
        self.scale(span / self.span, 1.0)

    @classmethod
    def __from_json__(cls, front_curve: Any, back_curve: Any, rib_distribution: Any,
                      cell_num: int, config: Any, cell_widths: list[float] | None = None,
                      **_legacy: Any) -> ParametricShape:
        # ``**_legacy`` tolerates fields from older saves (e.g. parametric_params),
        # which now load as a plain spline shape.
        return cls(front_curve, back_curve, rib_distribution, cell_num,
                   config=config, cell_widths=cell_widths)

    def copy(self) -> ParametricShape:
        return ParametricShape(
            self.front_curve.copy(),
            self.back_curve.copy(),
            self.rib_distribution.copy(),
            self.cell_num,
            config=self.config,
            cell_widths=None if self.cell_widths is None else list(self.cell_widths),
        )

    @classmethod
    def from_shape(cls, shape: PlanformShape) -> ParametricShape:
        """Explicitly convert an analytic or point-based shape to splines."""
        from openglider.glider.parametric.leparagliding_shape import LeparaglidingShape
        if isinstance(shape, ParametricShape):
            return shape.copy()
        if isinstance(shape, LeparaglidingShape):
            x_values = linspace(0.0, shape.span / 2, 200)
            front_points = [[x, shape._edge_at(x, True)] for x in x_values]
            back_points = [[x, shape._edge_at(x, False)] for x in x_values]
            num_controlpoints = 7
            cell_widths = None if shape.cell_widths is None else list(shape.cell_widths)
        else:
            raise TypeError(f"Cannot convert {type(shape)} to ParametricShape")

        front = openglider.rs.spline.SymmetricBSplineCurve.fit(
            openglider.rs.vector.PolyLine2D(front_points), num_controlpoints
        )
        back = openglider.rs.spline.SymmetricBSplineCurve.fit(
            openglider.rs.vector.PolyLine2D(back_points), num_controlpoints
        )
        return cls(
            front, back, shape.rib_distribution.copy(), shape.cell_num,
            config=shape.config, cell_widths=cell_widths,
        )


