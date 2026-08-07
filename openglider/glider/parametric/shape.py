from __future__ import annotations

import math
from abc import abstractmethod
from typing import Any, Literal, Self

import openglider.rs

from openglider.glider.parametric.config import ParametricGliderConfig
from openglider.glider.shape import Shape, ShapeBase
from openglider.utils import linspace
from openglider.utils.types import CurveType
from openglider.vector.unit import Angle, Percentage


class PlanformShape(ShapeBase):
    """Pure behavior interface for independent planform representations."""

    @abstractmethod
    def copy(self) -> Self: ...

    @abstractmethod
    def get_half_shape(self, zrot: list[Angle | None] | None = None) -> Shape: ...

    @abstractmethod
    def get_shape(self) -> Shape: ...

    @abstractmethod
    def get_point(self, x: float | int, y: float | Percentage) -> openglider.rs.vector.Vector2D: ...

    @abstractmethod
    def get_baseline(self, position: Percentage) -> openglider.rs.vector.PolyLine2D: ...

    @abstractmethod
    def chord_at(self, x: float) -> float: ...

    @abstractmethod
    def scale(self, x: float = 1., y: float | None = None) -> None: ...

    @property
    @abstractmethod
    def has_center_cell(self) -> bool: ...

    @property
    @abstractmethod
    def cell_no(self) -> int: ...

    @property
    @abstractmethod
    def rib_no(self) -> int: ...

    @property
    @abstractmethod
    def half_cell_num(self) -> int: ...

    @property
    @abstractmethod
    def ribs(self) -> list[tuple[openglider.rs.vector.Vector2D, openglider.rs.vector.Vector2D]]: ...

    @property
    @abstractmethod
    def rib_x_values(self) -> list[float]: ...

    @property
    @abstractmethod
    def span(self) -> float: ...

    @property
    @abstractmethod
    def chords(self) -> list[float]: ...

    @property
    @abstractmethod
    def area(self) -> float: ...

    @property
    @abstractmethod
    def aspect_ratio(self) -> float: ...

    @abstractmethod
    def get_sweep(self) -> float: ...
