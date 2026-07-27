from typing import ClassVar, overload

from openglider.airfoil.profile_2d import Profile2D
import openglider.rs

from openglider.utils.cache import cached_property
from openglider.utils.dataclass import BaseModel

class Profile3D(BaseModel):
    curve: openglider.rs.vector.PolyLine3D
    x_values: list[float]

    name: str = "unnamed"

    @overload
    def __getitem__(self, ik: float) -> openglider.rs.vector.Vector3D: ...

    @overload
    def __getitem__(self, ik: slice) -> openglider.rs.vector.PolyLine3D: ...

    def __getitem__(self, ik: float | slice) -> openglider.rs.vector.PolyLine3D | openglider.rs.vector.Vector3D:
        if isinstance(ik, slice):
            start = ik.start
            stop = ik.stop
            if ik.step == -1:
                stop, start = start, stop
            elif ik.step not in (None, 1):
                raise Exception(f"invalid step: {ik.step}")
            
            return self.curve.get(start, stop)

        return self.curve.get(ik)
    
    def __len__(self) -> int:
        return len(self.curve)
    
    def get_positions(self, start: float, stop: float) -> list[float]:
        return self.curve.get_positions(start, stop)

    @overload
    def get(self, start: float) -> openglider.rs.vector.Vector3D: ...

    @overload
    def get(self, start: float, stop: float) -> openglider.rs.vector.PolyLine3D: ...


    def get(self, start: float, stop: float | None=None) -> openglider.rs.vector.PolyLine3D | openglider.rs.vector.Vector3D:
        if stop is None:
            return self.curve.get(start)
            
        return self.curve.get(start, stop)

    @cached_property('self')
    def noseindex(self) -> int:
        p0 = self.curve.nodes[0]
        max_dist = 0.
        noseindex = 0
        for i, p1 in enumerate(self.curve.nodes):
            diff = (p1 - p0).length()
            if diff > max_dist:
                noseindex = i
                max_dist = diff
        return noseindex

    @cached_property('self')
    def projection_layer(self) -> openglider.rs.plane.Plane:
        """
        Projection Layer of profile_3d
        """
        p1 = self.curve.nodes[0]
        diff = [p - p1 for p in self.curve.nodes]

        xvect = diff[self.noseindex].normalized() * -1
        yvect = openglider.rs.vector.Vector3D([0, 0, 0])

        for i in range(len(diff)):
            sign = 1 - 2 * (i > self.noseindex)
            yvect = yvect + (diff[i] - xvect * xvect.dot(diff[i])) * sign

        yvect = yvect.normalized()

        return openglider.rs.plane.Plane(self.curve.nodes[self.noseindex], xvect, yvect)

    def flatten(self) -> Profile2D:
        """Flatten the airfoil and return a 2d-Representative"""
        layer = self.projection_layer
        return Profile2D(
            layer.project(self.curve).nodes,
            name=self.name or 'profile' + "_flattened"
        )

    @cached_property('self')
    def normvectors(self) -> list[openglider.rs.vector.Vector3D]:
        layer = self.projection_layer
        profnorm = layer.normvector

        def get_normvector(x: openglider.rs.vector.Vector3D) -> openglider.rs.vector.Vector3D:
            return x.cross(profnorm).normalized()

        vectors = [get_normvector(self.curve.nodes[1] - self.curve.nodes[0])]
        for i in range(1, len(self.curve.nodes) - 1):
            vectors.append(get_normvector(
                (self.curve.nodes[i + 1] - self.curve.nodes[i]).normalized() +
                (self.curve.nodes[i] - self.curve.nodes[i - 1]).normalized()
                ))
        vectors.append(get_normvector(self.curve.nodes[-1] - self.curve.nodes[-2]))

        return vectors

    @property
    def tangents(self) -> list[openglider.rs.vector.Vector3D]:
        return self.curve.get_tangents()