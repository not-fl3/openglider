from __future__ import annotations
import math
import openglider.rs
from typing import ClassVar

from openglider.airfoil import Profile3D
from openglider.utils.cache import cached_property
from openglider.utils.dataclass import BaseModel


class BasicCell(BaseModel):
    """
    A very simple cell without any extras like midribs, diagonals,..
    """
    cache_versioned: ClassVar[bool] = True
    prof1: Profile3D
    prof2: Profile3D
    ballooning_phi: list[float]
    name: str = "unnamed_cell"

    def point_basic_cell(self, y: int=0, ik: float=0) -> openglider.rs.vector.Vector3D:
        ##round ballooning
        return self.midrib(y).get(ik)

    def midrib(self, y_value: float, ballooning: bool=True, arc_argument: bool=True, close_trailing_edge: bool=False) -> Profile3D:
        # return early for left and right side
        if y_value <= 0:
            return self.prof1
        elif y_value >= 1:
            return self.prof2
        else:
            curve, x_values = openglider.rs.basic_cell_midrib(
                self.prof1.curve,
                self.prof2.curve,
                self.prof1.x_values,
                self.prof2.x_values,
                self.normvectors,
                self.ballooning_phi,
                self.ballooning_radius,
                y_value,
                ballooning=ballooning,
                arc_argument=arc_argument,
                close_trailing_edge=close_trailing_edge,
            )
            return Profile3D(curve=curve, x_values=x_values)

    @cached_property('prof1', 'prof2')
    def normvectors(self) -> openglider.rs.vector.PolyLine3D:
        prof1 = self.prof1.curve
        prof2 = self.prof2.curve
        
        t_1 = self.prof1.tangents
        t_2 = self.prof2.tangents
        # cross (differenzvektor, tangentialvektor)

        normals: list[openglider.rs.vector.Vector3D] = []

        for p1, p2, t1, t2 in zip(prof1, prof2, t_1, t_2):
            normal = (t1 + t2).cross(p1 - p2).normalized()
            normals.append(normal)
        
        return openglider.rs.vector.PolyLine3D(normals)

    @cached_property('ballooning_phi', 'prof1', 'prof2')
    def ballooning_radius(self) -> list[float | None]:
        prof1 = self.prof1.curve.nodes
        prof2 = self.prof2.curve.nodes

        radius: list[float | None] = []

        for p1, p2, phi in zip(prof1, prof2, self.ballooning_phi):
            if phi < 1e-10:
                radius.append(None)
            else:
                r = (p1-p2).length() / (2 * math.sin(phi) + (phi==0))
                radius.append(r)

        return radius
    
    @cached_property('ballooning_phi', 'prof1', 'prof2')
    def ballooning_tension_factors(self) -> list[float]:
        prof1 = self.prof1.curve.nodes
        prof2 = self.prof2.curve.nodes
        tension: list[float] = []
        for p1, p2, phi in zip(prof1, prof2, self.ballooning_phi):
            value =  2. * math.tan(phi)
            if value > 1e-10:
                value = 1/value
            
            tension.append(value * (p1-p2).length())
        
        return tension
