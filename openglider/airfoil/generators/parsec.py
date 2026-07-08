
from dataclasses import dataclass
import math

import openglider.rs
from pyfoil.airfoil import Airfoil

@dataclass
class BezierParsecAirfoil:
    # https://pubs.sciepub.com/ajme/2/4/1/
    thickness_x: float
    thickness_y: float
    nose_radius: float
    big_radius: float
    trailing_edge_angle: float

    camber_angle_front: float
    camber_angle_back: float
    camber_radius: float
    camber_big_radius: float
    camber_max_x: float
    camber_max_y: float

    trailing_edge_offset: float = 0

    def b9(self) -> float:
        def y(x: float):
            return (
                27 * self.big_radius**2 * x ** 4 / 4 -
                27 * self.big_radius**2*self.thickness_x*x**3 +
                (9*self.big_radius*self.thickness_y + 81 * self.big_radius**2 * self.big_radius**2 / 2) * x +
                (2 * self.nose_radius - 18 * self.big_radius**2 * self.thickness_x**3) * x +
                (3 * self.thickness_y**2 + 9*self.big_radius*self.thickness_x**2*self.thickness_y + 27 * self.big_radius**2*self.thickness_x**4 / 4)
            )
        
        

    def build(self, x_values: list[float]) -> Airfoil:
        y1 = 3*self.big_radius * (self.thickness_x - self.nose_radius)**2 / 2 + self.thickness_y
        leading_edge_thickness = openglider.rs.spline.BezierCurve([
            [0, 0],
            [0, y1],
            [self.nose_radius, self.thickness_y],
            [self.thickness_x, self.thickness_y]
        ])

        trailing_edge_thickness = openglider.rs.spline.BezierCurve([
            [self.thickness_x, self.thickness_y],
            [2*self.thickness_x - self.nose_radius, self.thickness_y],
            [1+ (self.trailing_edge_offset-y1)*math.tan(self.trailing_edge_angle), y1],
            [1, self.trailing_edge_offset]
        ])

        thickness_interpolation = openglider.rs.vector.Interpolation(
            leading_edge_thickness.get_sequence(200).nodes +
            trailing_edge_thickness.get_sequence(200).nodes[1:]
        )

        camber_dist_x = math.sqrt(2*(self.camber_radius-self.camber_max_y)/(3*self.camber_big_radius))

        leading_edge_camber = openglider.rs.spline.BezierCurve([
            [0, 0],
            [self.camber_radius * math.tan(self.camber_angle_front), self.camber_radius],
            [self.camber_max_x - camber_dist_x, self.camber_max_y],
            [self.camber_max_x, self.camber_max_y]
        ])

        trailing_edge_camber = openglider.rs.spline.BezierCurve([
            [self.camber_max_x, self.camber_max_y],
            [self.camber_max_x + camber_dist_x, self.camber_max_y],
            [1 + (self.trailing_edge_offset-self.camber_radius)*math.tan(self.camber_angle_back), self.camber_radius],
            [1, self.trailing_edge_offset]
        ])

        camber_interpolation = openglider.rs.vector.Interpolation(
            leading_edge_camber.get_sequence(200).nodes +
            trailing_edge_camber.get_sequence(200).nodes[1:]
        )

        if False:
            return (
                leading_edge_thickness,
                trailing_edge_thickness,
                leading_edge_camber,
                trailing_edge_camber,
            )

        result = []

        for x in x_values:
            x_abs = abs(x)
            thickness = thickness_interpolation.get_value(x_abs)/2
            camber = camber_interpolation.get_value(x_abs)
            if x < 0:
                result.append([x_abs, camber + thickness])
            else:
                result.append([x_abs, camber - thickness])

        return Airfoil(result)