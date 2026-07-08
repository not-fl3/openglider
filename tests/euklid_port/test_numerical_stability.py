#!/usr/bin/env python
"""
Test numerical stability improvements for cut_2d and offset functions.
"""
import math
import unittest

import openglider.rs as rs

PolyLine2D = rs.vector.PolyLine2D
Vector2D = rs.vector.Vector2D


class TestNumericalStability(unittest.TestCase):
    """Test cases for numerical stability improvements."""

    @staticmethod
    def _cut_line(polyline, p1, p2, nearest_ik=None):
        line = PolyLine2D([p1, p2])
        result = polyline.cut(line, nearest_ik=nearest_ik)
        if nearest_ik is not None:
            if len(result) == 0:
                return ()
            return result[0]
        return result

    def test_cut_2d_nearly_parallel_lines(self):
        angle = math.radians(1)

        p1 = PolyLine2D([[0, 0], [10, 0]])
        p2 = PolyLine2D([[0, 0.1], [10, 0.1 + 10 * math.tan(angle)]])

        cuts = p1.cut(p2)
        if len(cuts) > 0:
            self.assertIsInstance(cuts[0][0], float)
            self.assertIsInstance(cuts[0][1], float)

    def test_cut_2d_very_short_segments(self):
        p1 = PolyLine2D([[0, 0], [10, 0]])
        p2 = PolyLine2D([[5, -1], [5, -1 + 1e-9]])

        cuts = p1.cut(p2)
        self.assertEqual(len(cuts), 0)

    def test_cut_2d_exact_parallel_lines(self):
        p1 = PolyLine2D([[0, 0], [10, 0]])
        p2 = PolyLine2D([[0, 1], [10, 1]])

        cuts = p1.cut(p2)
        self.assertEqual(len(cuts), 0)

    def test_cut_2d_perpendicular_lines(self):
        p1 = PolyLine2D([[0, 0], [10, 0]])
        p2 = PolyLine2D([[5, -5], [5, 5]])

        cuts = p1.cut(p2)
        self.assertEqual(len(cuts), 1)

        ik1, ik2 = cuts[0]
        self.assertAlmostEqual(ik1, 0.5, places=6)
        self.assertAlmostEqual(ik2, 0.5, places=6)

    def test_cut_2d_with_nearest_ik(self):
        p1 = PolyLine2D([[0, 0], [10, 0], [20, 0]])
        p2_start = Vector2D([5, -1])
        p2_end = Vector2D([5, 1])

        result = self._cut_line(p1, p2_start, p2_end, 0.5)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

        ik1, _ik2 = result
        self.assertAlmostEqual(ik1, 0.5, places=6)

    def test_offset_simple_square(self):
        square = PolyLine2D([[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]])

        offset_square = square.offset(1.0, True)

        self.assertEqual(len(offset_square), len(square))

        for i in range(len(square) - 1):
            orig_pt = square.get(i, None)
            offset_pt = offset_square.get(i, None)
            dist = (offset_pt - orig_pt).length()
            self.assertGreater(dist, 0.5)
            self.assertLess(dist, 2.0)

    def test_offset_with_sharp_angle(self):
        sharp = PolyLine2D([[0, 0], [10, 0], [10.1, 5]])

        offset_sharp = sharp.offset(1.0, True)

        self.assertEqual(len(offset_sharp), len(sharp))

    def test_offset_with_very_small_segments(self):
        small_seg = PolyLine2D([[0, 0], [10, 0], [10 + 1e-9, 0], [10, 10]])

        offset_small = small_seg.offset(1.0, True)

        self.assertIsInstance(offset_small, PolyLine2D)

    def test_cut_with_mixed_scales(self):
        p1 = PolyLine2D([[0, 0], [1e6, 0]])
        p2 = PolyLine2D([[5e5, -1e-3], [5e5, 1e-3]])

        cuts = p1.cut(p2)

        if len(cuts) > 0:
            ik1, _ik2 = cuts[0]
            self.assertGreater(ik1, 0.4)
            self.assertLess(ik1, 0.6)


class TestProjectionBasedIntersection(unittest.TestCase):
    def test_intersection_symmetry(self):
        p1 = PolyLine2D([[0, 0], [10, 0]])
        p2 = PolyLine2D([[5, -5], [5, 5]])

        cuts1 = p1.cut(p2)
        cuts2 = p2.cut(p1)

        self.assertEqual(len(cuts1), 1)
        self.assertEqual(len(cuts2), 1)

        ik1_1, ik2_1 = cuts1[0]
        ik1_2, ik2_2 = cuts2[0]

        self.assertAlmostEqual(ik1_1, ik2_2, places=6)
        self.assertAlmostEqual(ik2_1, ik1_2, places=6)

    def test_intersection_at_endpoint(self):
        p1 = PolyLine2D([[0, 0], [10, 0]])
        p2 = PolyLine2D([[10, -5], [10, 5]])

        cuts = p1.cut(p2)

        self.assertEqual(len(cuts), 1)
        ik1, _ik2 = cuts[0]

        self.assertAlmostEqual(ik1, 1.0, places=6)

    def test_no_intersection_parallel(self):
        p1 = PolyLine2D([[0, 0], [10, 0]])
        p2 = PolyLine2D([[0, 5], [10, 5]])

        cuts = p1.cut(p2)

        self.assertEqual(len(cuts), 0)

    def test_intersection_diagonal_lines(self):
        p1 = PolyLine2D([[0, 0], [10, 10]])
        p2 = PolyLine2D([[0, 10], [10, 0]])

        cuts = p1.cut(p2)

        self.assertEqual(len(cuts), 1)
        ik1, ik2 = cuts[0]

        self.assertAlmostEqual(ik1, 0.5, places=6)
        self.assertAlmostEqual(ik2, 0.5, places=6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
