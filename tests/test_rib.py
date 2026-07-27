import unittest
import random
import math

import openglider.rs

import openglider
import openglider.airfoil
from openglider.glider.rib.rib import Rib, rib_rotation, rib_transformation
from openglider.glider.rib.crossports import RibHole
from openglider.materials import cloth
from openglider.vector.unit import Length, Percentage

class TestRib(unittest.TestCase):

    def setUp(self) -> None:
        naca = random.randint(1, 99) * 100 + random.randint(1, 99) # camber / thickness (thickness > 0)
        numpoints = random.randint(10,11)
        self.prof = openglider.airfoil.Profile2D.compute_naca(naca, numpoints)
        self.rib = Rib(profile_2d=self.prof,
                       pos=openglider.rs.vector.Vector3D([random.random(), random.random(), random.random()]),
                       chord=random.random(),
                       arcang=random.random(),
                       aoa_absolute=random.random(),
                       glide=random.random()*10,
                       material=cloth.get("default"),
                       seam_allowance=Length("10mm"),
                       trailing_edge_extra=None
                       )

    #def test_normvectors(self) -> None:

    def test_align(self) -> None:
        first = self.rib.pos
        second = self.rib.align(openglider.rs.vector.Vector2D([0, 0]))
        for i in range(3):
            self.assertAlmostEqual(first[i], second[i])

    def test_align_scale(self) -> None:
        prof1 = [self.rib.align(p) for p in self.rib.profile_2d.curve]
        _prof2 = self.rib.profile_2d.curve.scale(self.rib.chord)
        prof2 = [self.rib.align(p, scale=False) for p in _prof2]


        for p1, p2 in zip(prof1, prof2):
            self.assertAlmostEqual(p1[0], p2[0])
            self.assertAlmostEqual(p1[1], p2[1])
            self.assertAlmostEqual(p1[2], p2[2])

    def test_mesh(self) -> None:
        self.rib.holes.append(RibHole(pos=Percentage(0.2)))
        self.rib.get_mesh()

    def test_rib_rotation_application_order(self) -> None:
        aoa = 0.23
        arc = -0.41

        rot = rib_rotation(aoa=aoa, arc=arc, zrot=None, xrot=None)

        rot0 = openglider.rs.vector.Transformation.rotation(math.pi / 2, [1, 0, 0])
        rot1 = openglider.rs.vector.Transformation.rotation(aoa, [0, 1, 0])
        rot2 = openglider.rs.vector.Transformation.rotation(-arc, [1, 0, 0])

        point = openglider.rs.vector.Vector2D([0.37, -0.19])
        expected = rot2.apply(rot1.apply(rot0.apply(point)))
        actual = rot.apply(point)

        for i in range(3):
            self.assertAlmostEqual(actual[i], expected[i])

    def test_rib_transformation_application_order(self) -> None:
        aoa = 0.31
        arc = 0.52
        scale = 0.77
        pos = openglider.rs.vector.Vector3D([0.31, -0.27, 0.43])
        offset = openglider.rs.vector.Vector3D([0.11, -0.07, 0.05])

        trans = rib_transformation(
            aoa=aoa,
            arc=arc,
            zrot=None,
            xrot=None,
            scale=scale,
            pos=pos,
            offset=offset,
        )

        rot = rib_rotation(aoa=aoa, arc=arc, zrot=None, xrot=None)
        scale_trans = openglider.rs.vector.Transformation.scale(scale)
        move = openglider.rs.vector.Transformation.translation(pos + rot.apply(offset))

        point = openglider.rs.vector.Vector2D([-0.22, 0.18])
        expected = move.apply(rot.apply(scale_trans.apply(point)))
        actual = trans.apply(point)

        for i in range(3):
            self.assertAlmostEqual(actual[i], expected[i])




if __name__ == '__main__':
    unittest.main(verbosity=2)
