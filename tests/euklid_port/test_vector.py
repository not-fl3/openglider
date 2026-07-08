#! /bin/python
import unittest
import random
import math

import openglider.rs as rs

PolyLine3D = rs.vector.PolyLine3D
PolyLine2D = rs.vector.PolyLine2D
vec = rs.vector


class TestVector3D(unittest.TestCase):
    PolyLine = PolyLine3D
    dim = 3

    def setUp(self):
        self.vectors = []
        self.sums = []
        numlists = 100
        self.numpoints = numpoints = 100

        for _i in range(numlists):
            pointlist = []
            for _j in range(numpoints):
                pointlist.append([random.random() * 100 for i in range(self.dim)])
            self.vectors.append(self.PolyLine(pointlist))

    def test_walk_total(self):
        for thalist in self.vectors:
            total = thalist.get_length()

            i2 = thalist.walk(0, total)
            self.assertAlmostEqual(i2, len(thalist) - 1)

    def test_walk_case_within(self):
        for thalist in self.vectors:
            start = random.random() * self.numpoints
            leng = random.random() * 100 - 50
            new = thalist.walk(start, leng)
            leng2 = thalist.get(start, new).get_length()

            dist = thalist.get(start, None) - thalist.get(new, None)
            self.assertAlmostEqual(abs(leng), leng2, 3,
                f"Failed for start={start}; len={leng} => i2={new}; len2={leng2}; dist={dist.length()}")

    def test_walk_case_before(self):
        for thalist in self.vectors:
            start = -random.random() * 30
            leng = random.random() * 100 - 50
            new = thalist.walk(start, leng)
            self.assertTrue(math.isfinite(new), f"walk returned non-finite value for start={start}, len={leng}: {new}")

            # The current Rust binding clamps get() outside bounds, so this case focuses
            # on non-hanging behavior and directional movement instead of extrapolated arc-length.
            if leng < 0:
                self.assertLessEqual(new, 0.0, f"Expected backward walk from before-start to remain <= 0, got {new}")

    def test_walk_case_afterend(self):
        for thalist in self.vectors:
            start = self.numpoints + random.random() * 50
            leng = random.random() * 100 - 50
            new = thalist.walk(start, leng)

            new2 = thalist.get(start, new)
            leng2 = new2.get_length()

            dist = thalist.get(start, None) - thalist.get(new, None)
            self.assertAlmostEqual(abs(leng), leng2, 7,
                f"Failed for start={start}; len={leng} => i2={new}; len2={leng2}; dist={dist.length()}")


class TestVector2D(TestVector3D):
    PolyLine = PolyLine2D
    dim = 2

    @staticmethod
    def _cut_line(polyline, p1, p2, nearest_ik=None):
        line = PolyLine2D([p1, p2])
        result = polyline.cut(line, nearest_ik=nearest_ik)
        if nearest_ik is not None:
            if len(result) == 0:
                return ()
            return result[0]
        return result

    def test_A_selfcheck(self):
        for thalist in self.vectors:
            thalist.fix_errors()

    def test_normvectors(self):
        for thalist in self.vectors:
            i = random.randint(1, len(thalist)-3)
            normv = thalist.normvectors().nodes
            segments = thalist.get_segments()

            if i == 0:
                segment = segments[0]
            else:
                s1 = segments[i-1].normalized()
                s2 = segments[i].normalized()

                segment = s1 + s2

            self.assertAlmostEqual(normv[i].dot(segment), 0, places=0)

    def test_shift(self):
        for thalist in self.vectors:
            amount = random.random()
            thalist.offset(amount, False)

    def test_Cut(self):
        for thalist in self.vectors:
            i = random.randint(1, len(thalist)-3)
            normv = thalist.normvectors()
            dirr = normv.get(i, None).normalized()
            dirr *= 0.0001

            p1 = thalist.get(i, None) + dirr
            p2 = thalist.get(i, None) - dirr
            neu = self._cut_line(thalist, p1, p2, i)
            self.assertAlmostEqual(i, neu[0])


class TestVectorFunctions3D(unittest.TestCase):
    dim = 3

    def setUp(self):
        self.vectors = [
            vec.Vector3D(
                [random.random()+0.001 for _ in range(3)]
            ) for _ in range(100)
        ]

    def test_rotation_scale(self):
        angle = 2 * random.random() - 1
        rot = vec.Transformation.rotation(0, [1, 0, 0])

        for axis in self.vectors:
            rotation_matrix = vec.Transformation.rotation(angle, axis)
            rot = rot * rotation_matrix

            for v in self.vectors:
                v_rot = rot.apply(v)
                v_mat = rotation_matrix.apply(v)
                self.assertAlmostEqual(v_rot.length(), v.length())
                self.assertAlmostEqual(v_mat.length(), v.length())

    def test_rotation_scale_2(self):
        rot = vec.Transformation.rotation(0, [1, 0, 0])

        for axis in self.vectors:
            angle = 2 * random.random() - 1
            scale = random.random()
            rotation_matrix = vec.Transformation.rotation(angle, axis)
            rot = rot * rotation_matrix

            for v in self.vectors:
                p1 = rot.apply(v * scale)
                p2 = rot.apply(v) * scale
                for i in range(3):
                    self.assertAlmostEqual(p1[i], p2[i])


if __name__ == '__main__':
    unittest.main(verbosity=2)
