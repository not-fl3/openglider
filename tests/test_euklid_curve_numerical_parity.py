from __future__ import annotations

import math
import unittest

import euklid
import openglider.rs as rs
from openglider.glider.parametric.arc import ArcCurve


ABS_TOL = 1e-6
REL_TOL = 1e-6


def _assert_close(left: float, right: float, msg: str = "") -> None:
    assert math.isclose(left, right, rel_tol=REL_TOL, abs_tol=ABS_TOL), (
        msg or f"values differ: {left} vs {right}"
    )


def _assert_vec2_close(left: object, right: object, msg: str = "") -> None:
    _assert_close(float(left[0]), float(right[0]), msg)
    _assert_close(float(left[1]), float(right[1]), msg)


def _assert_polyline_close(left: object, right: object, msg: str = "") -> None:
    left_nodes = list(left.nodes)
    right_nodes = list(right.nodes)
    assert len(left_nodes) == len(right_nodes), (
        msg or f"node-count differs: {len(left_nodes)} vs {len(right_nodes)}"
    )
    for idx, (lvec, rvec) in enumerate(zip(left_nodes, right_nodes)):
        _assert_vec2_close(lvec, rvec, f"{msg} at node {idx}")


def _sorted_cuts(cuts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return sorted(cuts, key=lambda cut: (cut[0], cut[1]))


def _assert_curve_sampling_parity(e_curve: object, r_curve: object) -> None:
    for value in (0.0, 0.2, 0.9, 1.6, 2.4, 3.0):
        _assert_vec2_close(e_curve.get(value), r_curve.get(value), f"curve.get({value})")

    e_seq = e_curve.get_sequence(35)
    r_seq = r_curve.get_sequence(35)
    _assert_polyline_close(e_seq, r_seq, "curve.get_sequence")


class TestEuklidCurveNumericalParity(unittest.TestCase):
    def test_transformation_chain_parity(self) -> None:
        axis = [1.0, 0.0, 0.0]
        angle = 0.3
        scale = 2.0
        translation = [3.0, 4.0, 5.0]

        e_transform = (
            euklid.vector.Transformation.scale(scale)
            * euklid.vector.Transformation.rotation(angle, axis)
            * euklid.vector.Transformation.translation(translation)
        )
        r_transform = (
            rs.vector.Transformation.scale(scale)
            * rs.vector.Transformation.rotation(angle, axis)
            * rs.vector.Transformation.translation(translation)
        )

        points = [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 2.0, 3.0],
        ]

        for idx, point in enumerate(points):
            e_result = e_transform.apply(euklid.vector.Vector3D(point))
            r_result = r_transform.apply(rs.vector.Vector3D(point))
            _assert_close(float(e_result[0]), float(r_result[0]), f"transform[{idx}].x")
            _assert_close(float(e_result[1]), float(r_result[1]), f"transform[{idx}].y")
            _assert_close(float(e_result[2]), float(r_result[2]), f"transform[{idx}].z")

    def test_polyline_get_walk_and_subcurve_parity(self) -> None:
        nodes = [
            [0.0, 0.0],
            [1.0, 0.5],
            [2.0, -0.25],
            [3.0, 0.9],
            [4.0, 1.1],
        ]
        e_line = euklid.vector.PolyLine2D(nodes)
        r_line = rs.vector.PolyLine2D(nodes)

        for ik in (-0.3, 0.0, 0.25, 1.3, 2.7, 4.4):
            _assert_vec2_close(e_line.get(ik), r_line.get(ik), f"get({ik})")

        for start, amount in ((0.1, 0.8), (1.6, -0.9), (3.2, 0.5)):
            _assert_close(
                float(e_line.walk(start, amount)),
                float(r_line.walk(start, amount)),
                f"walk({start}, {amount})",
            )

        for start, end in ((0.2, 3.1), (3.1, 0.2), (-0.2, 2.2), (1.2, 4.4)):
            e_part = e_line.get(start, end)
            r_part = r_line.get(start, end)
            _assert_polyline_close(e_part, r_part, f"get({start}, {end})")

    def test_polyline_cut_parity_for_point_and_polyline_overloads(self) -> None:
        nodes = [
            [0.0, 0.0],
            [1.0, 1.2],
            [2.2, 0.0],
            [3.3, 1.0],
        ]
        other_nodes = [
            [0.1, 0.9],
            [2.8, 0.2],
            [3.4, 1.3],
        ]

        e_line = euklid.vector.PolyLine2D(nodes)
        r_line = rs.vector.PolyLine2D(nodes)
        e_other = euklid.vector.PolyLine2D(other_nodes)
        r_other = rs.vector.PolyLine2D(other_nodes)

        p1 = [-0.5, 0.5]
        p2 = [4.0, 0.5]

        e_cuts = _sorted_cuts(list(e_line.cut(p1, p2)))
        r_cuts = _sorted_cuts(list(r_line.cut(p1, p2)))
        self.assertEqual(len(e_cuts), len(r_cuts), f"cut count differs: {len(e_cuts)} vs {len(r_cuts)}")
        for idx, (ecut, rcut) in enumerate(zip(e_cuts, r_cuts)):
            _assert_close(float(ecut[0]), float(rcut[0]), f"point cut[{idx}].ik_1")
            _assert_close(float(ecut[1]), float(rcut[1]), f"point cut[{idx}].ik_2")

        nearest = 1.6
        e_near = e_line.cut(p1, p2, nearest)
        r_near = r_line.cut(p1, p2, nearest)
        _assert_close(float(e_near[0]), float(r_near[0]), "point cut nearest ik_1")
        _assert_close(float(e_near[1]), float(r_near[1]), "point cut nearest ik_2")

        e_poly_cuts = _sorted_cuts(list(e_line.cut(e_other)))
        r_poly_cuts = _sorted_cuts(list(r_line.cut(r_other)))
        self.assertEqual(
            len(e_poly_cuts),
            len(r_poly_cuts),
            f"polyline cut count differs: {len(e_poly_cuts)} vs {len(r_poly_cuts)}",
        )
        for idx, (ecut, rcut) in enumerate(zip(e_poly_cuts, r_poly_cuts)):
            _assert_close(float(ecut[0]), float(rcut[0]), f"poly cut[{idx}].ik_1")
            _assert_close(float(ecut[1]), float(rcut[1]), f"poly cut[{idx}].ik_2")

        e_poly_near = e_line.cut(e_other, nearest)
        r_poly_near = r_line.cut(r_other, nearest)
        _assert_close(float(e_poly_near[0]), float(r_poly_near[0]), "polyline cut nearest ik_1")
        _assert_close(float(e_poly_near[1]), float(r_poly_near[1]), "polyline cut nearest ik_2")

    def test_polyline_offset_parity_default_and_simple(self) -> None:
        nodes = [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.7, 0.8],
            [2.2, 0.2],
            [2.8, 0.7],
        ]
        e_line = euklid.vector.PolyLine2D(nodes)
        r_line = rs.vector.PolyLine2D(nodes)

        amount = 0.15

        # Default behavior is part of parity and has regressed before.
        _assert_polyline_close(e_line.offset(amount), r_line.offset(amount), "offset(amount)")
        _assert_polyline_close(
            e_line.offset(amount, True),
            r_line.offset(amount, True),
            "offset(amount, True)",
        )
        _assert_polyline_close(
            e_line.offset(amount, False),
            r_line.offset(amount, False),
            "offset(amount, False)",
        )

    def test_spline_curve_sampling_parity(self) -> None:
        control = [
            [0.0, 0.0],
            [0.6, 1.1],
            [1.5, 0.2],
            [2.2, 1.0],
        ]

        _assert_curve_sampling_parity(
            euklid.spline.BezierCurve(control),
            rs.spline.BezierCurve(control),
        )
        _assert_curve_sampling_parity(
            euklid.spline.BSplineCurve(control),
            rs.spline.BSplineCurve(control),
        )
        _assert_curve_sampling_parity(
            euklid.spline.CubicBSplineCurve(control),
            rs.spline.CubicBSplineCurve(control),
        )

    def test_symmetric_bspline_fit_parity_arc_like(self) -> None:
        right_nodes = [
            [0.0, 0.0],
            [0.8, -0.03],
            [1.6, -0.09],
            [2.5, -0.2],
            [3.3, -0.34],
            [4.1, -0.55],
        ]

        e_right = euklid.vector.PolyLine2D(right_nodes)
        r_right = rs.vector.PolyLine2D(right_nodes)
        e_left = e_right.mirror()
        r_left = r_right.mirror()

        e_curve = euklid.vector.PolyLine2D(list(e_left.nodes[:-1]) + list(e_right.nodes))
        r_curve = rs.vector.PolyLine2D(list(r_left.nodes[:-1]) + list(r_right.nodes))

        e_fit = euklid.spline.SymmetricBSplineCurve.fit(e_curve, 8)
        r_fit = rs.spline.SymmetricBSplineCurve.fit(r_curve, 8)

        _assert_polyline_close(e_fit.controlpoints, r_fit.controlpoints, "symmetric.fit.controlpoints")

        e_seq = e_fit.get_sequence(80)
        r_seq = r_fit.get_sequence(80)
        _assert_polyline_close(e_seq, r_seq, "symmetric.fit.get_sequence")

    def test_symmetric_bspline_curvature_parity(self) -> None:
        control = [
            [0.0, 0.0],
            [0.8, -0.1],
            [1.6, -0.35],
            [2.4, -0.8],
        ]

        e_curve = euklid.spline.SymmetricBSplineCurve(control)
        r_curve = rs.spline.SymmetricBSplineCurve(control)

        e_curv = e_curve.get_curvature(100)
        r_curv = r_curve.get_curvature(100)

        self.assertEqual(len(e_curv.nodes), len(r_curv.nodes))

        for idx, (left, right) in enumerate(zip(e_curv.nodes, r_curv.nodes)):
            _assert_close(float(left[0]), float(right[0]), f"curvature.x[{idx}]")

            left_y = float(left[1])
            right_y = float(right[1])
            if math.isnan(left_y) and math.isnan(right_y):
                continue
            self.assertTrue(
                math.isclose(left_y, right_y, rel_tol=1e-4, abs_tol=2e-3),
                f"curvature.y[{idx}] differs: {left_y} vs {right_y}",
            )

    def test_arc_near_zero_xvalue_uses_no_center_cell_mode(self) -> None:
        curve = rs.spline.SymmetricBSplineCurve(
            [
                rs.vector.Vector2D([1.4, 0.0]),
                rs.vector.Vector2D([2.3, -0.8]),
                rs.vector.Vector2D([3.7, -2.1]),
            ]
        )
        arc = ArcCurve(curve)

        x_values_exact = [0.0, 0.25, 0.7, 1.2, 2.0]
        x_values_noisy = [1e-12, 0.25, 0.7, 1.2, 2.0]

        pos_exact = arc.get_arc_positions(x_values_exact)
        pos_noisy = arc.get_arc_positions(x_values_noisy)

        _assert_polyline_close(pos_exact, pos_noisy, "arc near-zero x-value handling")


if __name__ == "__main__":
    unittest.main()
