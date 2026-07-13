from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from openglider.rs.spline import (
        BSplineCurve,
        BezierCurve,
        CubicBSplineCurve,
        QuadBSplineCurve,
        SymmetricBSplineCurve,
        SymmetricBezierCurve,
        SymmetricCubicBSplineCurve,
        SymmetricQuadBSplineCurve,
    )
else:
    BSplineCurve = Any
    BezierCurve = Any
    CubicBSplineCurve = Any
    QuadBSplineCurve = Any
    SymmetricBSplineCurve = Any
    SymmetricBezierCurve = Any
    SymmetricCubicBSplineCurve = Any
    SymmetricQuadBSplineCurve = Any

AsymmetricCurveType: TypeAlias = (
    BSplineCurve
    | BezierCurve
    | CubicBSplineCurve
    | QuadBSplineCurve
)

SymmetricCurveType: TypeAlias = (
    SymmetricBSplineCurve
    | SymmetricBezierCurve
    | SymmetricCubicBSplineCurve
    | SymmetricQuadBSplineCurve
)

CurveType: TypeAlias = AsymmetricCurveType | SymmetricCurveType