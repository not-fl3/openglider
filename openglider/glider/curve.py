from typing import Any

import openglider.rs
import enum

from openglider.glider.shape import Shape
from openglider.utils.cache import cached_property
from openglider.utils.dataclass import BaseModel
from openglider.vector.unit import Angle, Length, Percentage, Quantity

class CurveBase(BaseModel):
    unit: str | None = None
    interpolation: openglider.rs.vector.Interpolation
    shape: Shape

    def to_unit(self, value: float) -> Quantity | float:
        if self.unit is None:
            return value
        
        if self.unit in Angle.unit_variants or self.unit == Angle.unit:
            return Angle(value, unit=self.unit)
        if self.unit in Length.unit_variants or self.unit == Length.unit:
            return Length(value, unit=self.unit)
        if self.unit in Percentage.unit_variants:
            return Percentage(value, self.unit)

        raise ValueError()

class FreeCurve(CurveBase):
    def __init__(self, points: list[openglider.rs.vector.Vector2D], shape: Shape):
        super().__init__(
            shape = shape,
            interpolation = openglider.rs.vector.Interpolation(points)
        )
    
    @property
    def controlpoints(self) -> list[openglider.rs.vector.Vector2D]:
        return self.interpolation.nodes
    
    @controlpoints.setter
    def controlpoints(self, points: list[openglider.rs.vector.Vector2D]) -> None:
        self.interpolation = openglider.rs.vector.Interpolation(points)

    @property
    def controlpoints_2d(self) -> list[openglider.rs.vector.Vector2D]:
        return self.to_2d(self.controlpoints)
    
    def set_controlpoints_2d(self, points: list[openglider.rs.vector.Vector2D]) -> None:
        controlpoints = self.to_controlpoints(points)
        self.controlpoints = controlpoints
    
    def to_2d(self, points: list[openglider.rs.vector.Vector2D]) -> list[openglider.rs.vector.Vector2D]:
        nodes: list[openglider.rs.vector.Vector2D] = []
        for p in points:
            x_shape = p[0]
            y = p[1]

            x = self.shape.get_point(x_shape, 0)[0]

            nodes.append(openglider.rs.vector.Vector2D([x,y]))
        
        return nodes

    
    def to_controlpoints(self, points: list[openglider.rs.vector.Vector2D]) -> list[openglider.rs.vector.Vector2D]:
        controlpoints: list[openglider.rs.vector.Vector2D] = []

        x_values = [p[0] for p in self.shape.front]

        for point in points:
            distance = abs(x_values[0] - point[0])
            index = 0

            for i, x in enumerate(x_values):
                _distance = abs(x - point[0])

                if _distance < distance:
                    distance = _distance
                    index = i

            if index == 0 and self.shape.has_center_cell:
                index = 1
            
            controlpoints.append(openglider.rs.vector.Vector2D([index, point[1]]))
        
        return controlpoints
    
    @property
    def points_2d(self) -> list[openglider.rs.vector.Vector2D]:
        return self.to_2d(self.interpolation.nodes)
    
    def get(self, rib_no: int) -> float | Quantity:
        if rib_no == 0 and self.shape.has_center_cell:
            rib_no = 1

        value = self.interpolation.get_value(rib_no)
        return self.to_unit(value)

    def draw(self) -> openglider.rs.vector.PolyLine2D:
        x_values = [p[0] for p in self.controlpoints]

        start = min(x_values)
        end = max(x_values)

        start_int = int(start) + (start % 1) > 1e-10

        x_values_lst = [float(x) for x in range(start_int, int(end)+1)]

        if start % 1:
            x_values_lst.insert(0, start)
        
        if end % 1:
            x_values_lst.append(end)
        
        return openglider.rs.vector.PolyLine2D(self.to_2d([openglider.rs.vector.Vector2D([x, self.interpolation.get_value(x)]) for x in x_values_lst]))


class Curve(CurveBase):
    def __init__(self, points: list[openglider.rs.vector.Vector2D], shape: Shape):
        super().__init__(
            interpolation = openglider.rs.vector.Interpolation(points),
            shape=shape
        )

    @property
    def controlpoints(self) -> list[openglider.rs.vector.Vector2D]:
        return self.interpolation.nodes
    
    @controlpoints.setter
    def controlpoints(self, points: list[openglider.rs.vector.Vector2D]) -> None:
        self.interpolation = openglider.rs.vector.Interpolation(points)

    @property
    def controlpoints_2d(self) -> list[openglider.rs.vector.Vector2D]:
        return [
            openglider.rs.vector.Vector2D(self.shape.get_point(*p)) for p in self.controlpoints
        ]
    
    def set_controlpoints_2d(self, points: list[openglider.rs.vector.Vector2D]) -> None:
        controlpoints = self.to_controlpoints(points)
        self.controlpoints = controlpoints
    
    def to_controlpoints(self, points: list[openglider.rs.vector.Vector2D]) -> list[openglider.rs.vector.Vector2D]:
        controlpoints = []

        x_values = [p[0] for p in self.shape.front]
        ribs = self.shape.ribs

        for point in points:
            distance = abs(x_values[0] - point[0])
            index = 0

            for i, x in enumerate(x_values):
                _distance = abs(x - point[0])

                if _distance < distance:
                    distance = _distance
                    index = i

            if index == 0 and self.shape.has_center_cell:
                index = 1

            y1 = ribs[index][0][1]
            y2 = ribs[index][1][1]

            y = (point[1]-y1) / (y2-y1)

            y = max(0, y)
            y = min(1, y)
            
            controlpoints.append(openglider.rs.vector.Vector2D([index, y]))
        
        return controlpoints
    
    @cached_property('shape', 'interpolation')
    def points_2d(self) -> openglider.rs.vector.PolyLine2D:
        return openglider.rs.vector.PolyLine2D([
            self.shape.get_point(*p) for p in self.interpolation.nodes
        ])
    
    def get(self, rib_no: int) -> float | Quantity:
        if rib_no == 0 and self.shape.has_center_cell:
            rib_no = 1

        y = self.interpolation.get_value(rib_no)

        return self.to_unit(y)
        
    def draw(self) -> openglider.rs.vector.PolyLine2D:
        x_values = [p[0] for p in self.controlpoints]

        start = int(min(x_values))
        end = int(max(x_values))

        start_int = int(start) + ((start % 1) > 1e-10)

        x_values_lst = list(range(start_int, int(end)+1))

        if start % 1:
            x_values_lst.insert(0, start)
        
        if end % 1:
            x_values_lst.append(end)

        percentage_lst: list[Percentage | float] = []
        for x in x_values_lst:
            y = self.get(x)
            if not isinstance(y, (Percentage, float)):
                raise ValueError()

            percentage_lst.append(y)

        for p in percentage_lst:
            if not isinstance(p, (Percentage, float)):
                raise ValueError()

        points = [self.shape.get_point(x, y) for x, y in zip(x_values_lst, percentage_lst)]

        if start == 1 and self.shape.has_center_cell:
            points.insert(0, points[0] * openglider.rs.vector.Vector2D([-1,1]))
        
        return openglider.rs.vector.PolyLine2D(points)



class ShapeCurve(Curve):
    def get(self, rib_no: int) -> float | Quantity:
        if rib_no == 0 and self.shape.has_center_cell:
            rib_no = 1

        front, back = self.shape.front.get(rib_no), self.shape.back.get(rib_no)

        results = self.points_2d.cut(front, back)

        if len(results) != 1:
            raise Exception(f"wrong number of cut results: {len(results)}")

        return self.to_unit(results[0][1])


class ShapeBSplineCurve(ShapeCurve):
    curve_cls: ClassVar[type] = openglider.rs.spline.BSplineCurve
    
    @cached_property('shape', 'interpolation')
    def points_2d(self) -> openglider.rs.vector.PolyLine2D:
        return openglider.rs.spline.BSplineCurve([
            openglider.rs.vector.Vector2D(self.shape.get_point(*p)) for p in self.controlpoints
        ]).get_sequence(100)


GliderCurveType = FreeCurve | Curve | ShapeCurve | ShapeBSplineCurve

class CurveEnum(enum.Enum):
    FreeCurve = FreeCurve
    Curve = Curve
    ShapeCurve = ShapeCurve
    ShapeBSplineCurve = ShapeBSplineCurve