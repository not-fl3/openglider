from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any, Self, TypeAlias

import openglider.rs
from openglider.utils.dataclass import BaseModel
from openglider.vector.drawing import Layout, PlotPart
from openglider.vector.unit import Percentage

if TYPE_CHECKING:
    from openglider.glider.cell.panel import Panel


logger = logging.getLogger(__name__)

V2: TypeAlias = openglider.rs.vector.Vector2D

class Shape(BaseModel):
    front: openglider.rs.vector.PolyLine2D
    back: openglider.rs.vector.PolyLine2D

    @property
    def has_center_cell(self) -> bool:
        return abs(self.front.nodes[0][0]) > 1e-5 and abs(self.back.nodes[0][0]) > 1e-5

    def get_point(self, x: float | int, y: float | Percentage) -> openglider.rs.vector.Vector2D:
        front = self.front.get(x)
        back = self.back.get(x)

        return front + (back-front) *  float(y)
    
    def get_baseline(self, position: Percentage) -> openglider.rs.vector.PolyLine2D:
        points = []
        for front, back in zip(self.front.nodes, self.back.nodes):
            points.append(
                front + (back - front) * position.si
            )

        return openglider.rs.vector.PolyLine2D(points)

    def get_panel(self, cell_no: int, panel: Panel) -> tuple[V2, V2, V2, V2]:
        p1 = self.get_point(cell_no, panel.cut_front.x_left)
        p2 = self.get_point(cell_no, panel.cut_back.x_left)
        p3 = self.get_point(cell_no+1, panel.cut_back.x_right)
        p4 = self.get_point(cell_no+1, panel.cut_front.x_right)

        return p1, p2, p3, p4

    @property
    def cell_no(self) -> int:
        return len(self.front) - 1

    @property
    def rib_no(self) -> int:
        return len(self.front)

    @property
    def ribs(self) -> list[tuple[openglider.rs.vector.Vector2D, openglider.rs.vector.Vector2D]]:
        return [(self.front.get(x), self.back.get(x)) for x in range(len(self.front))]

    @property
    def ribs_front_back(self) -> tuple[
        list[tuple[V2, V2]],
        openglider.rs.vector.PolyLine2D,
        openglider.rs.vector.PolyLine2D    
    ]:
        return (self.ribs, self.front, self.back)

    @property
    def span(self) -> float:
        return self.front.nodes[-1][0]
    
    @span.setter
    def span(self, span: float) -> None:
        span_old = self.span
        self.scale(span/span_old, 1)


    @property
    def chords(self) -> list[float]:
        return [(p1-p2).length() for p1, p2 in zip(self.front, self.back)]

    @property
    def cell_widths(self) -> list[float]:
        return [p2[0]-p1[0] for p1, p2 in zip(self.front.nodes[:-1], self.front.nodes[1:])]

    @property
    def area(self) -> float:
        front, back = self.front, self.back
        area = 0.
        for i in range(len(self.front) - 1):
            l = (front.get(i)[1] - back.get(i)[1]) + (front.get(i+1)[1] - back.get(i+1)[1])
            area += l * (front.get(i+1)[0] - front.get(i)[0]) / 2
        return area
    
    @area.setter
    def area(self, area: float) -> None:
        factor = math.sqrt(area / self.area)

        self.scale(factor, factor)

    def scale(self, x: float=1, y: float =1.) -> Shape:
        self.front = self.front.scale(openglider.rs.vector.Vector2D([x, y]))
        self.back = self.back.scale(openglider.rs.vector.Vector2D([x, y]))

        return self
    
    def copy(self, *args: Any, **kwargs: Any) -> Self:
        return self.__class__(
            front=self.front.copy(),
            back=self.back.copy()
        )

    def copy_complete(self) -> Shape:
        front = self.front.mirror().reverse()
        back = self.back.mirror().reverse()

        if front.nodes[-1][0] != 0:
            start = 2
        else:
            start = 1

        front_nodes = front.nodes + self.front.copy().nodes[start:]
        back_nodes = back.nodes + self.back.copy().nodes[start:]

        return Shape(
            front=openglider.rs.vector.PolyLine2D(front_nodes),
            back=openglider.rs.vector.PolyLine2D(back_nodes)
        )

    @staticmethod
    def _close_polyline(polyline: openglider.rs.vector.PolyLine2D) -> openglider.rs.vector.PolyLine2D:
        nodes = list(polyline.nodes)
        if nodes and nodes[0] != nodes[-1]:
            nodes.append(nodes[0])
        return openglider.rs.vector.PolyLine2D(nodes)

    def _get_symmetric_outline(self) -> openglider.rs.vector.PolyLine2D:
        front_nodes = list(self.front.nodes)
        back_nodes = list(self.back.nodes)

        if front_nodes and abs(float(front_nodes[0][0])) > 1e-12:
            front_nodes[0] = openglider.rs.vector.Vector2D([0.0, float(front_nodes[0][1])])
        if back_nodes and abs(float(back_nodes[0][0])) > 1e-12:
            back_nodes[0] = openglider.rs.vector.Vector2D([0.0, float(back_nodes[0][1])])

        outline_nodes = front_nodes + back_nodes[::-1]
        return self._close_polyline(openglider.rs.vector.PolyLine2D(outline_nodes))

    def get_attachment_point_areas(
        self,
        attachment_points: list[tuple[str, openglider.rs.vector.Vector2D]],
    ) -> dict[str, openglider.rs.vector.PolyLine2D | None]:
        if not attachment_points:
            return {}

        outline = self._get_symmetric_outline()
        names_by_position: dict[tuple[float, float], list[str]] = {}
        unique_points: list[openglider.rs.vector.Vector2D] = []

        for name, point in attachment_points:
            key = (float(point[0]), float(point[1]))
            if key not in names_by_position:
                unique_points.append(openglider.rs.vector.Vector2D([key[0], key[1]]))
                names_by_position[key] = []
            names_by_position[key].append(name)

        voronoi_areas = openglider.rs.voronoi.voronoi_areas(outline, unique_points)

        result: dict[str, openglider.rs.vector.PolyLine2D | None] = {}
        for point, area in zip(unique_points, voronoi_areas):
            key = (float(point[0]), float(point[1]))

            closed_area: openglider.rs.vector.PolyLine2D | None = None
            if area is not None:
                closed_area = self._close_polyline(area)

            for name in names_by_position.get(key, []):
                result[name] = closed_area.copy() if closed_area is not None else None

        return result

    def _repr_svg_(self) -> str:
        da = Layout()
        for cell_no in range(self.cell_no):
            points = [
                self.get_point(cell_no, 0),
                self.get_point(cell_no, 1),
                self.get_point(cell_no+1, 1),
                self.get_point(cell_no+1, 0)
            ]
            points.append(points[0])
            da.parts.append(PlotPart(marks=[openglider.rs.vector.PolyLine2D(points)]))

        return da._repr_svg_()
