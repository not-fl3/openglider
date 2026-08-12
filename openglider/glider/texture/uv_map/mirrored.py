from __future__ import annotations

from typing import TYPE_CHECKING

from openglider.glider.shape import Shape
import openglider.rs
from openglider.glider.rib.rib import Rib
from openglider.glider.texture.uv_map.base import _UVMapBase
from openglider.vector.unit import Percentage


if TYPE_CHECKING:
    from openglider.glider.glider import Glider


class UVMapMirrored(_UVMapBase):
    """UV map using chordwise profile length as Y and cell index as X."""

    def __init__(self, shape: Shape, glider: Glider) -> None:
        super().__init__(shape, glider)
        self._rib_profile_to_y: list[openglider.rs.vector.Interpolation] = self._build_rib_profile_to_y()
        self._y_pair_cache: dict[tuple[int, float], tuple[float, float]] = {}

    def _get_length(self, x: Percentage, rib: Rib) -> float:
        ik_front = rib.profile_2d.get_ik(0)
        ik = rib.profile_2d.get_ik(x)

        length = rib.profile_2d.curve.get(ik_front, ik).get_length()

        if x.si < 0:
            length *= -1

        return length * rib.chord

    def _build_rib_profile_to_y(self) -> list[openglider.rs.vector.Interpolation]:
        interpolations: list[openglider.rs.vector.Interpolation] = []
        for rib in self.glider3d.ribs:
            x_values = [float(v) for v in rib.profile_2d.x_values]
            if len(x_values) < 2:
                x_values = [-1.0, 1.0]
            nodes = [[xv, self._get_length(Percentage(xv), rib)] for xv in x_values]
            interpolations.append(openglider.rs.vector.Interpolation(nodes))
        return interpolations

    def _texture_point_from_panel_local(
        self,
        cell_no: int,
        is_upper: bool,
        x: float,
        y: float,
        mirrored: bool,
    ) -> tuple[float, float]:
        u = self._shape.get_point(cell_no + x, 0)[0]
        if mirrored and self._can_mirror(cell_no):
            u = -u

        x_local = self._clamp01(x)
        y_local = self._clamp11(y)
        key = (cell_no, y_local)
        cached = self._y_pair_cache.get(key)
        if cached is None:
            cached = (
                float(self._rib_profile_to_y[cell_no].get_value(y_local)),
                float(self._rib_profile_to_y[cell_no + 1].get_value(y_local)),
            )
            self._y_pair_cache[key] = cached

        left, right = cached
        v = self._lerp(left, right, x_local)

        return u, v