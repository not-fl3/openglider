from __future__ import annotations

from typing import TYPE_CHECKING

import openglider.rs
from openglider.glider.shape import Shape
from openglider.glider.texture.uv_map.base import _UVMapBase


if TYPE_CHECKING:
    from openglider.glider.glider import Glider


class UVMapStacked(_UVMapBase):
    """UV map stacking upper surface above lower surface in shape space."""

    def __init__(self, shape: Shape, glider: Glider) -> None:
        super().__init__(shape, glider)
        self._upper_offset = 0.0
        self._shape_point_cache: dict[tuple[int, float], tuple[float, float]] = {}
        self._upper_offset = self._compute_upper_offset()

    def _shape_point_cached(self, rib_no: int, chord_pos: float) -> tuple[float, float]:
        key = (rib_no, chord_pos)
        cached = self._shape_point_cache.get(key)
        if cached is not None:
            return cached

        point = self._shape.get_point(rib_no, chord_pos)
        cached = (float(point[0]), float(point[1]))
        self._shape_point_cache[key] = cached
        return cached

    def _compute_upper_offset(self) -> float:
        """Compute vertical offset required to place upper panels above lower panels."""
        upper_polys: list[openglider.rs.vector.PolyLine2D] = []
        lower_polys: list[openglider.rs.vector.PolyLine2D] = []
        for cell_no, cell in enumerate(self.glider3d.cells):
            for panel in cell.panels:
                poly = self.get_panel_polygon(cell_no, panel)
                (lower_polys if panel.is_lower() else upper_polys).append(poly)

        upper_bbox = self._get_bbox(upper_polys) if upper_polys else (0.0, 0.0, 0.0, 0.0)
        lower_bbox = self._get_bbox(lower_polys) if lower_polys else (0.0, 0.0, 0.0, 0.0)
        upper_height = upper_bbox[3] - upper_bbox[2]
        lower_height = lower_bbox[3] - lower_bbox[2]
        size = max(upper_height, lower_height, 1e-3)
        gap = 0.05 * size
        upper_offset = (lower_bbox[3] + gap) - upper_bbox[2]
        return upper_offset

    def _texture_point_from_panel_local(
        self,
        cell_no: int,
        is_upper: bool,
        x: float,
        y: float,
        mirrored: bool,
    ) -> tuple[float, float]:
        x_local = self._clamp01(x)
        y_local = self._clamp11(y)

        if not is_upper:
            chord_pos = y_local
        else:
            chord_pos = -y_local

        p_lx, p_ly = self._shape_point_cached(cell_no, chord_pos)
        p_rx, p_ry = self._shape_point_cached(cell_no + 1, chord_pos)

        tx = self._lerp(p_lx, p_rx, x_local)
        ty = self._lerp(p_ly, p_ry, x_local)

        if is_upper:
            ty += self._upper_offset

        if mirrored and self._can_mirror(cell_no):
            tx = -tx

        return tx, ty