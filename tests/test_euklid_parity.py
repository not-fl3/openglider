from __future__ import annotations

from collections.abc import Iterable

import euklid
import openglider.rs as rs


def _public_names(obj: object) -> set[str]:
    return {name for name in dir(obj) if not name.startswith("_")}


def _missing_names(reference: object, candidate: object) -> set[str]:
    return _public_names(reference) - _public_names(candidate)


def _missing_map() -> dict[str, set[str]]:
    missing: dict[str, set[str]] = {}

    top_missing = _missing_names(euklid, rs)
    if top_missing:
        missing["top"] = top_missing

    for module_name in ("vector", "spline", "plane", "mesh"):
        emod = getattr(euklid, module_name, None)
        rmod = getattr(rs, module_name, None)
        if emod is None or rmod is None:
            continue

        module_missing = _missing_names(emod, rmod)
        if module_missing:
            missing[f"module:{module_name}"] = module_missing

    class_pairs: Iterable[tuple[str, str]] = (
        ("vector", "Vector2D"),
        ("vector", "Vector3D"),
        ("vector", "PolyLine2D"),
        ("vector", "PolyLine3D"),
        ("vector", "Transformation"),
        ("vector", "Rotation2D"),
        ("vector", "Interpolation"),
        ("spline", "BezierCurve"),
        ("spline", "BSplineCurve"),
        ("spline", "LinSplineCurve"),
        ("spline", "CubicBSplineCurve"),
        ("spline", "QuadBSplineCurve"),
        ("spline", "SymmetricBezierCurve"),
        ("spline", "SymmetricBSplineCurve"),
        ("spline", "SymmetricCubicBSplineCurve"),
        ("spline", "SymmetricQuadBSplineCurve"),
        ("plane", "Plane"),
    )

    for module_name, class_name in class_pairs:
        eclass = getattr(getattr(euklid, module_name), class_name)
        rclass = getattr(getattr(rs, module_name), class_name)
        class_missing = _missing_names(eclass, rclass)
        if class_missing:
            missing[f"class:{module_name}.{class_name}"] = class_missing

    return missing


# Full parity snapshot as of 2026-07-08.
KNOWN_MISSING: dict[str, set[str]] = {}


def test_euklid_parity_has_no_new_missing_members() -> None:
    missing = _missing_map()

    unexpected: dict[str, set[str]] = {}
    for key, names in missing.items():
        known = KNOWN_MISSING.get(key, set())
        delta = names - known
        if delta:
            unexpected[key] = delta

    assert not unexpected, (
        "Found new missing API members compared to euklid: "
        f"{ {k: sorted(v) for k, v in unexpected.items()} }"
    )


def test_rs_core_smoke() -> None:
    v2 = rs.vector.Vector2D([1.0, 2.0])
    v3 = rs.vector.Vector3D([1.0, 2.0, 3.0])
    assert v2.length() > 0.0
    assert v3.length() > 0.0

    poly = rs.vector.PolyLine2D([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])
    assert len(poly) == 3
    assert poly.get_length() > 0.0

    poly3 = rs.vector.PolyLine3D(
        [
            rs.vector.Vector3D([0.0, 0.0, 0.0]),
            rs.vector.Vector3D([1.0, 0.0, 0.0]),
            rs.vector.Vector3D([1.0, 1.0, 0.0]),
        ]
    )
    assert poly3.get_positions(0.0, 2.0) == [0.0, 1.0, 2.0]
    assert len(poly3.get_segments()) == 2
    assert len(poly3.get_segment_lengthes()) == 2
    assert len(poly3.get_tangents()) == 3
    assert len(poly3.tolist()) == 3
    assert isinstance(poly3.mix(poly3, 0.5), rs.vector.PolyLine3D)
    assert isinstance(poly3.walk(0.0, 0.2), float)

    assert hasattr(rs, "mesh")
    assert hasattr(rs.vector, "cut")
    cut_result = rs.vector.cut([0.0, 0.0], [1.0, 0.0], [0.5, -1.0], [0.5, 1.0])
    assert cut_result.success is True

    curve = rs.spline.BezierCurve(
        [
            rs.vector.Vector2D([0.0, 0.0]),
            rs.vector.Vector2D([0.5, 1.0]),
            rs.vector.Vector2D([1.0, 0.0]),
        ]
    )
    seq = curve.get_sequence(8)
    assert len(seq) == 9
    assert hasattr(curve, "numpoints")

    bcurve = rs.spline.BSplineCurve(
        [
            rs.vector.Vector2D([0.0, 0.0]),
            rs.vector.Vector2D([0.3, 0.7]),
            rs.vector.Vector2D([0.6, 0.5]),
            rs.vector.Vector2D([1.0, 0.0]),
        ]
    )
    assert hasattr(bcurve, "get_derivate")

    p1 = rs.vector.Vector3D([1.0, 0.0, 0.0])
    p2 = rs.vector.Vector3D([0.0, 1.0, 0.0])
    p0 = rs.vector.Vector3D([0.0, 0.0, 0.0])
    plane = rs.plane.Plane(p1, p2, p0)
    projected = plane.project(rs.vector.Vector3D([1.0, 2.0, 3.0]))
    assert isinstance(projected, rs.vector.Vector2D)
