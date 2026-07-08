"""PyO3 Rust module providing high-performance geometric calculations.

This module is automatically generated from Rust code using PyO3.
Type stubs are generated from introspection data.
"""

from typing import Any

from . import vector as vector
from . import spline as spline
from . import plane as plane
from . import mesh as mesh

__all__ = [
    "triangle_area",
    "version",
    "vector",
    "spline",
    "plane",
    "mesh",
]

def find_duplicates(*args: Any, **kwargs: Any) -> Any: ...
def triangle_area(*args: Any, **kwargs: Any) -> Any: ...
def version(*args: Any, **kwargs: Any) -> Any: ...