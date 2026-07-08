from typing import Union
import openglider.rs

AsymmetricCurveType = Union[
    openglider.rs.spline.BSplineCurve,
    openglider.rs.spline.BezierCurve,
    openglider.rs.spline.CubicBSplineCurve,
    openglider.rs.spline.QuadBSplineCurve
    ]

SymmetricCurveType = Union[
    openglider.rs.spline.SymmetricBSplineCurve,
    openglider.rs.spline.SymmetricBezierCurve,
    openglider.rs.spline.SymmetricCubicBSplineCurve,
    openglider.rs.spline.SymmetricQuadBSplineCurve
    ]
    
CurveType = Union[AsymmetricCurveType, SymmetricCurveType]