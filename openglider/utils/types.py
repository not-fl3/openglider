from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    import openglider.rs as rs
    BSplineCurve = rs.spline.BSplineCurve
    BezierCurve = rs.spline.BezierCurve
    CubicBSplineCurve = rs.spline.CubicBSplineCurve
    QuadBSplineCurve = rs.spline.QuadBSplineCurve
    SymmetricBSplineCurve = rs.spline.SymmetricBSplineCurve
    SymmetricBezierCurve = rs.spline.SymmetricBezierCurve
    SymmetricCubicBSplineCurve = rs.spline.SymmetricCubicBSplineCurve
    SymmetricQuadBSplineCurve = rs.spline.SymmetricQuadBSplineCurve
    
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