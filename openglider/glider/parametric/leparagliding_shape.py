from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

import openglider.rs

from openglider.glider.parametric.config import ParametricGliderConfig
from openglider.glider.parametric.shape import PlanformShape
from openglider.glider.shape import Shape
from openglider.utils import linspace
from openglider.utils.types import CurveType
from openglider.vector.unit import Angle, Percentage

LEPARAGLIDING_UNIT_SCALE = 0.01


@dataclass
class LeadingEdgeParams:
    """Leparagliding type-1 leading-edge coefficients."""

    a1: float = 710.21
    b1: float = 243.11
    x1: float = 375.0
    x2: float = 475.0
    xm: float = 575.5
    c01: float = 48.30
    ex1: float = 2.0
    c02: float = 0.0
    ex2: float = 2.0


@dataclass
class TrailingEdgeParams:
    """Leparagliding type-1 trailing-edge coefficients."""

    a1: float = 903.01
    b1: float = 243.11
    x1: float = 372.50
    xm: float = 575.5
    c0: float = -2.45
    y0: float = 215.20
    exp: float = 2.0


@dataclass
class LeparaglidingShapeParams:
    """Coefficient data consumed by :class:`LeparaglidingShape`."""

    leading_edge: LeadingEdgeParams = field(default_factory=LeadingEdgeParams)
    trailing_edge: TrailingEdgeParams = field(default_factory=TrailingEdgeParams)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "leparagliding",
            "leading_edge": self.leading_edge.__dict__.copy(),
            "trailing_edge": self.trailing_edge.__dict__.copy(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LeparaglidingShapeParams:
        return cls(
            leading_edge=LeadingEdgeParams(**data.get("leading_edge", {})),
            trailing_edge=TrailingEdgeParams(**data.get("trailing_edge", {})),
        )



class LeparaglidingShape(PlanformShape):
    """Analytic planform evaluated from Leparagliding coefficients.

    Cell distribution is independent: it can still be an editable spline or a
    list of explicit cell-width coefficients, just like on a spline planform.
    """

    num_distribution_interpolation = 50
    num_depth_integral = 50

    def __init__(
        self,
        params: LeparaglidingShapeParams,
        config: ParametricGliderConfig,
        cell_num: int,
        rib_distribution: CurveType | None = None,
        cell_widths: list[float] | None = None,
    ) -> None:
        if rib_distribution is None:
            if cell_widths is None:
                raise ValueError(
                    "LeparaglidingShape requires a rib distribution or cell widths"
                )
            # Slider mode uses cell_widths directly. This linear curve is only a
            # dormant placeholder required by the common planform API.
            rib_distribution = openglider.rs.spline.BSplineCurve(
                [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
            )

        self.params = params
        self.config = config
        self.cell_num = cell_num
        self.rib_distribution = rib_distribution
        self.cell_widths = None if cell_widths is None else list(cell_widths)

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
    def _num_cell_widths(self) -> int:
        return self.cell_num // 2 + self.has_center_cell

    def _get_cell_widths(self) -> list[float]:
        needed = self._num_cell_widths
        coeffs = list(self.cell_widths) if self.cell_widths is not None else self._current_cell_widths()
        return (coeffs + [1.0] * max(0, needed - len(coeffs)))[:needed]

    def _current_cell_widths(self) -> list[float]:
        x_abs = [abs(x) for x in self.rib_x_values]
        positions = ([0.0] + x_abs[1:]) if self.has_center_cell else x_abs
        widths = [right - left for left, right in zip(positions, positions[1:])]
        if self.has_center_cell and widths:
            widths[0] *= 2.0
        mean = sum(widths) / len(widths) if widths else 1.0
        return [width / (mean or 1.0) for width in widths]

    def apply_cell_widths(self, widths: list[float]) -> None:
        self.cell_widths = list(widths)

    def _cell_width_positions(self) -> list[float]:
        coeffs = self._get_cell_widths()
        half_widths = ([coeffs[0] * 0.5] + coeffs[1:]) if self.has_center_cell else coeffs
        positions = [half_widths[0]] if self.has_center_cell else [0.0]
        for width in half_widths[1:] if self.has_center_cell else half_widths:
            positions.append(positions[-1] + width)
        total = sum(half_widths)
        return [position / total for position in positions]

    @property
    def rib_dist_interpolation(self) -> list[tuple[float, float]]:
        start = self.has_center_cell / self.cell_num
        values = list(linspace(start, 1, self.cell_num // 2 + 1))
        if self.cell_widths is not None:
            return list(zip(self._cell_width_positions(), values))
        data = self.rib_distribution.get_sequence(self.num_distribution_interpolation)
        interpolation = openglider.rs.vector.Interpolation([[point[1], point[0]] for point in data])
        return [(interpolation.get_value(value), value) for value in values]

    @property
    def rib_dist_controlpoints(self) -> openglider.rs.vector.PolyLine2D:
        return openglider.rs.vector.PolyLine2D(self.rib_distribution.controlpoints.nodes[1:-1])

    @rib_dist_controlpoints.setter
    def rib_dist_controlpoints(self, points: list[list[float]] | list[openglider.rs.vector.Vector2D]) -> None:
        self.rib_distribution.controlpoints = openglider.rs.vector.PolyLine2D(
            [[0.0, 0.0]] + points + [[1.0, 1.0]]
        )

    @property
    def rib_x_values(self) -> list[float]:
        half_span = self.span / 2
        values = [point[0] * half_span for point in self.rib_dist_interpolation]
        if self.config.has_stabicell:
            width = self.config.stabi_cell_width * (values[-1] - values[-2])
            values.append(values[-1] + width)
            values = [value * half_span / values[-1] for value in values]
        if self.has_center_cell:
            values.insert(0, -values[0])
        return values

    @property
    def cell_x_values(self) -> list[float]:
        return [(left + right) / 2 for left, right in zip(self.rib_x_values, self.rib_x_values[1:])]

    @property
    def baseline(self) -> openglider.rs.vector.PolyLine2D:
        return self.get_baseline(self.config.baseline_pct or Percentage(0.0))

    def get_baseline(self, position: Percentage) -> openglider.rs.vector.PolyLine2D:
        return self.get_half_shape().get_baseline(position)

    def get_point(self, x: float | int, y: float | Percentage) -> openglider.rs.vector.Vector2D:
        return self.get_half_shape().get_point(x, y)

    @property
    def ribs(self) -> list[tuple[openglider.rs.vector.Vector2D, openglider.rs.vector.Vector2D]]:
        return self.get_half_shape().ribs

    @property
    def chords(self) -> list[float]:
        return [(front - back).length() for front, back in self.ribs]

    def get_shape(self) -> Shape:
        return self.get_half_shape().copy_complete()

    @property
    def area(self) -> float:
        return self.get_shape().area

    @property
    def aspect_ratio(self) -> float:
        return self.span ** 2 / self.area

    def get_sweep(self) -> float:
        ribs = self.ribs
        center_front, center_back = ribs[0]
        tip_front, tip_back = ribs[-2] if self.config.has_stabicell else ribs[-1]
        delta = ((tip_front + tip_back) * 0.5)[1] - center_front[1]
        return delta / (center_front + center_back)[1]

    @property
    def depth_integrated(self) -> list[tuple[float, float]]:
        x_values = linspace(0, self.span / 2, self.num_depth_integral)
        integral = [0.0]
        for x in x_values[1:]:
            integral.append(integral[-1] + 1.0 / self.chord_at(x))
        return list(zip([x / (self.span / 2) for x in x_values], [value / integral[-1] for value in integral]))

    def set_area(self, area: float, fixed: Literal["aspect_ratio", "span", "depth"] = "aspect_ratio") -> float:
        if fixed == "aspect_ratio":
            factor = math.sqrt(area / self.area)
            self.scale(factor, factor)
        elif fixed == "span":
            self.scale(1.0, area / self.area)
        elif fixed == "depth":
            self.scale(area / self.area, 1.0)
        else:
            raise ValueError(f"Invalid fixed value: {fixed}")
        return self.area

    def set_aspect_ratio(self, aspect_ratio: float, fixed: Literal["span", "area"] = "span") -> None:
        current = self.aspect_ratio
        if fixed == "span":
            self.scale(1.0, current / aspect_ratio)
        else:
            self.scale(math.sqrt(aspect_ratio / current), math.sqrt(current / aspect_ratio))

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

    @property
    def span(self) -> float:
        return 2 * self.params.leading_edge.xm * LEPARAGLIDING_UNIT_SCALE

    @span.setter
    def span(self, span: float) -> None:
        self.scale(span / self.span, 1.0)

    @staticmethod
    def scale_params(
        params: LeparaglidingShapeParams,
        span_factor: float,
        chord_factor: float,
    ) -> None:
        leading = params.leading_edge
        trailing = params.trailing_edge
        leading.a1 *= span_factor
        leading.x1 *= span_factor
        leading.x2 *= span_factor
        leading.xm *= span_factor
        trailing.a1 *= span_factor
        trailing.x1 *= span_factor
        trailing.xm *= span_factor
        leading.b1 *= chord_factor
        leading.c01 *= chord_factor
        leading.c02 *= chord_factor
        trailing.b1 *= chord_factor
        trailing.y0 *= chord_factor
        trailing.c0 *= chord_factor

    def scale(self, x: float = 1., y: float | None = None) -> None:
        self.scale_params(self.params, x, x if y is None else y)

    @staticmethod
    def _interpolate_segments(x: float, segments: list[tuple[float, float, float, float]]) -> float:
        """Match the pre-processor's piecewise-linear rib interpolation."""
        value: float | None = None
        tolerance = 1e-7
        for x1, y1, x2, y2 in segments:
            if x1 - tolerance <= x <= x2 + tolerance:
                # Adjacent FORTRAN samples can have microscopic floating-point
                # gaps. Clamp to the segment before interpolating across them.
                segment_x = min(max(x, x1), x2)
                slope = (y2 - y1) / (x2 - x1)
                value = y1 + slope * (segment_x - x1)
        if value is None:
            raise ValueError(f"Span position {x} is outside the pre-processor edges")
        return value

    def _preprocessor_segments(self, leading_edge: bool) -> list[tuple[float, float, float, float]]:
        """Port the 0.01-radian LE/TE loops from pre-processor.f v1.6."""
        le = self.params.leading_edge
        edge: Any = le if leading_edge else self.params.trailing_edge
        segments: list[tuple[float, float, float, float]] = []
        for index in range(157):
            theta = index * 0.01
            x1 = edge.a1 * math.sin(theta)
            x2 = edge.a1 * math.sin(theta + 0.01)
            if x1 > le.xm:
                break
            if x1 < edge.x1:
                if leading_edge:
                    y1 = edge.b1 * math.cos(theta)
                    y2 = edge.b1 * math.cos(theta + 0.01)
                else:
                    y1 = -edge.b1 * math.cos(theta) + edge.y0
                    y2 = -edge.b1 * math.cos(theta + 0.01) + edge.y0
            else:
                if x1 < le.xm <= x2:
                    x2 = le.xm
                if leading_edge:
                    y1 = edge.b1 * math.sqrt(max(1 - (x1 / edge.a1) ** 2, 0.0))
                    y2 = edge.b1 * math.sqrt(max(1 - (x2 / edge.a1) ** 2, 0.0))
                    k1 = edge.c01 / (le.xm - edge.x1) ** edge.ex1
                    y1 -= k1 * (x1 - edge.x1) ** edge.ex1
                    y2 -= k1 * (x2 - edge.x1) ** edge.ex1
                    if x1 >= edge.x2:
                        k2 = edge.c02 / (le.xm - edge.x2) ** edge.ex2
                        y1 -= k2 * (x1 - edge.x2) ** edge.ex2
                        y2 -= k2 * (x2 - edge.x2) ** edge.ex2
                else:
                    y1 = -edge.b1 * math.sqrt(max(1 - (x1 / edge.a1) ** 2, 0.0)) + edge.y0
                    y2 = -edge.b1 * math.sqrt(max(1 - (x2 / edge.a1) ** 2, 0.0)) + edge.y0
                    correction = edge.c0 / (le.xm - edge.x1) ** edge.exp
                    y1 -= correction * (x1 - edge.x1) ** edge.exp
                    y2 -= correction * (x2 - edge.x1) ** edge.exp
            segments.append((x1, y1, x2, y2))
            if x2 == le.xm:
                break
        return segments

    def _edge_at(self, x: float, leading_edge: bool) -> float:
        # Normalized slider positions can put the tip a few ulps beyond xm.
        source_x = abs(x) / LEPARAGLIDING_UNIT_SCALE
        xm = self.params.leading_edge.xm
        if xm < source_x <= xm + 1e-7:
            source_x = xm
        raw_y = self._interpolate_segments(
            source_x, self._preprocessor_segments(leading_edge)
        )
        # FORTRAN output uses b1_le - raw_y; OpenGlider points chordwise negative.
        return -(self.params.leading_edge.b1 - raw_y) * LEPARAGLIDING_UNIT_SCALE

    def chord_at(self, x: float) -> float:
        return abs(self._edge_at(x, False) - self._edge_at(x, True))

    def get_half_shape(self, zrot: list[Angle | None] | None = None) -> Shape:
        distribution = self.rib_x_values[self.has_center_cell:]
        front = [[x, self._edge_at(x, True)] for x in distribution]
        back = [[x, self._edge_at(x, False)] for x in distribution]
        if self.config.has_stabicell:
            leading_y = front[-2][1]
            trailing_y = back[-2][1]
            delta = (trailing_y - leading_y) * (1 - self.config.stabi_cell_length)
            front[-1][1] = leading_y + delta * self.config.stabi_cell_position
            back[-1][1] = trailing_y - delta * (1 - self.config.stabi_cell_position)
        if self.has_center_cell:
            front.insert(0, [-front[0][0], front[0][1]])
            back.insert(0, [-back[0][0], back[0][1]])
        return Shape(
            front=openglider.rs.vector.PolyLine2D(front),
            back=openglider.rs.vector.PolyLine2D(back),
        )


