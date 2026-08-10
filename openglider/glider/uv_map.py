from __future__ import annotations

import logging
from collections.abc import Iterable
import math
from xml.etree import ElementTree
from pathlib import Path
from io import BytesIO
from typing import TYPE_CHECKING, Literal

import openglider
from openglider.glider.shape import Shape
import openglider.rs
import svglib.svglib
from PIL import Image
from reportlab.graphics.shapes import Drawing, Group, Line, Path as ReportPath, PolyLine, Polygon
from openglider.vector.drawing import Layout, PlotPart
from openglider.vector.unit import Percentage
from openglider.glider.rib.rib import Rib
from openglider.glider.cell.cell import Cell
from openglider import glider

if TYPE_CHECKING:
    from openglider.glider.cell.panel import Panel


logger = logging.getLogger(__name__)


UVMapMode = Literal["mirrored", "stacked"]


class SVGTexture:
    def __init__(self, file_path: str | Path, dpi: int = 300, svg_data: str | None = None):
        self.file_path = Path(file_path)
        self.dpi = dpi
        self._svg_data = svg_data if svg_data is not None else self._read_svg_string(self.file_path)
        source = None if svg_data is not None else self.file_path
        self.width, self.height = self._read_svg_size(self._svg_data, source)
        self._drawing: Drawing | None = None
        self._normalized_vectors: list[openglider.rs.vector.PolyLine2D] | None = None
        self._raster: Image.Image | None = None
        self._raster_by_max_dim: dict[tuple[int, float], Image.Image] = {}

    @classmethod
    def from_svg_string(cls, svg_data: str, source_label: str = "<inline-svg>", dpi: int = 300) -> SVGTexture:
        return cls(Path(source_label), dpi=dpi, svg_data=svg_data)

    @staticmethod
    def _read_svg_string(file_path: Path) -> str:
        svg_bytes = file_path.read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return svg_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"could not decode svg file: {file_path}")

    @staticmethod
    def _parse_svg_length(value: str | None) -> float | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None

        for suffix in ("px", "pt", "pc", "mm", "cm", "in"):
            if text.endswith(suffix):
                text = text[: -len(suffix)]
                break

        try:
            return float(text)
        except ValueError:
            return None

    @classmethod
    def _read_svg_size(cls, svg_data: str, source: Path | None = None) -> tuple[float, float]:
        try:
            root = ElementTree.fromstring(svg_data)
        except ElementTree.ParseError as err:
            source_label = str(source) if source is not None else "<inline-svg>"
            raise ValueError(f"could not read svg file: {source_label}") from err

        width = cls._parse_svg_length(root.get("width"))
        height = cls._parse_svg_length(root.get("height"))

        if width is not None and height is not None:
            return max(width, 1.0), max(height, 1.0)

        view_box = root.get("viewBox") or root.get("viewbox")
        if view_box:
            parts = [part for part in view_box.replace(",", " ").split() if part]
            if len(parts) == 4:
                try:
                    return max(float(parts[2]), 1.0), max(float(parts[3]), 1.0)
                except ValueError:
                    pass

        source_label = str(source) if source is not None else "<inline-svg>"
        raise ValueError(f"svg file has no usable size information: {source_label}")

    def _normalize_point(self, x: float, y: float) -> tuple[float, float]:
        u = 0.0 if self.width == 0 else x / self.width
        v = 1.0 if self.height == 0 else 1.0 - y / self.height
        return u, v

    def _get_drawing(self) -> Drawing:
        if self._drawing is None:
            drawing = svglib.svglib.svg2rlg(BytesIO(self._svg_data.encode("utf-8")))
            if drawing is None:
                raise ValueError(f"could not read svg file: {self.file_path}")
            self._drawing = drawing
        return self._drawing

    def _walk_nodes(self, node: Drawing | Group) -> Iterable[object]:
        if hasattr(node, "contents"):
            for child in node.contents:
                yield child
                if isinstance(child, (Drawing, Group)):
                    yield from self._walk_nodes(child)

    def _extract_path_lines(self, path: ReportPath) -> list[openglider.rs.vector.PolyLine2D]:
        lines: list[openglider.rs.vector.PolyLine2D] = []
        if not path.points:
            return lines

        points = path.points
        operators = path.operators

        cursor = 0
        current_line: list[tuple[float, float]] = []
        first_point: tuple[float, float] | None = None

        for op in operators:
            if op == 0:
                if len(current_line) >= 2:
                    lines.append(openglider.rs.vector.PolyLine2D(current_line))
                x = points[cursor]
                y = points[cursor + 1]
                cursor += 2
                current_line = [self._normalize_point(x, y)]
                first_point = current_line[0]
            elif op == 1:
                x = points[cursor]
                y = points[cursor + 1]
                cursor += 2
                current_line.append(self._normalize_point(x, y))
            elif op == 2:
                if cursor + 5 < len(points):
                    x = points[cursor + 4]
                    y = points[cursor + 5]
                    current_line.append(self._normalize_point(x, y))
                cursor += 6
            elif op == 3:
                if first_point is not None:
                    current_line.append(first_point)
                if len(current_line) >= 2:
                    lines.append(openglider.rs.vector.PolyLine2D(current_line))
                current_line = []
                first_point = None

        if len(current_line) >= 2:
            lines.append(openglider.rs.vector.PolyLine2D(current_line))

        return lines

    def _extract_vectors(self, drawing: Drawing) -> list[openglider.rs.vector.PolyLine2D]:
        vectors: list[openglider.rs.vector.PolyLine2D] = []

        for node in self._walk_nodes(drawing):
            if isinstance(node, Line):
                p1 = self._normalize_point(float(node.x1), float(node.y1))
                p2 = self._normalize_point(float(node.x2), float(node.y2))
                vectors.append(openglider.rs.vector.PolyLine2D([p1, p2]))
            elif isinstance(node, PolyLine):
                points = [self._normalize_point(float(x), float(y)) for x, y in zip(node.points[0::2], node.points[1::2])]
                if len(points) >= 2:
                    vectors.append(openglider.rs.vector.PolyLine2D(points))
            elif isinstance(node, Polygon):
                points = [self._normalize_point(float(x), float(y)) for x, y in zip(node.points[0::2], node.points[1::2])]
                if len(points) >= 2:
                    points.append(points[0])
                    vectors.append(openglider.rs.vector.PolyLine2D(points))
            elif isinstance(node, ReportPath):
                vectors.extend(self._extract_path_lines(node))

        return vectors

    def get_vectors(self, bbox: tuple[float, float, float, float]) -> list[openglider.rs.vector.PolyLine2D]:
        """Return normalized SVG outlines remapped into the requested bbox.

        The ReportLab parse is performed lazily because this path is only needed
        for plotfile-style vector overlays, not for the raster texture pipeline.
        """
        if self._normalized_vectors is None:
            self._normalized_vectors = self._extract_vectors(self._get_drawing())
        return [self._map_to_bbox(polyline, bbox) for polyline in self._normalized_vectors]

    def _map_to_bbox(
        self,
        polyline: openglider.rs.vector.PolyLine2D,
        bbox: tuple[float, float, float, float],
    ) -> openglider.rs.vector.PolyLine2D:
        min_x, max_x, min_y, max_y = bbox
        width = max(max_x - min_x, 1e-9)
        height = max(max_y - min_y, 1e-9)

        mapped = [(min_x + p[0] * width, min_y + p[1] * height) for p in polyline]
        return openglider.rs.vector.PolyLine2D(mapped)

    def _get_raster(self) -> Image.Image:
        if self._raster is None:
            px_w = max(1, int(round(self.width * self.dpi / 72.0)))
            px_h = max(1, int(round(self.height * self.dpi / 72.0)))
            width, height, rgba = openglider.rs.svg_mod.render_svg_rgba_from_string(self._svg_data, px_w, px_h)
            self._raster = Image.frombytes("RGBA", (int(width), int(height)), bytes(rgba))
        return self._raster

    def get_raster_bounded(
        self,
        max_dim: int = 8192,
        precision: float = 1.0,
        cache: bool = True,
    ) -> Image.Image:
        """Return full texture raster capped to max_dim without giant intermediates."""
        max_dim = max(1, int(max_dim))
        precision = max(0.1, min(float(precision), 1.0))
        cache_key = (max_dim, round(precision, 3))
        if cache:
            cached = self._raster_by_max_dim.get(cache_key)
            if cached is not None:
                return cached

        px_w, px_h = self._get_bounded_raster_size(max_dim=max_dim, precision=precision)
        width, height, rgba = openglider.rs.svg_mod.render_svg_rgba_from_string(self._svg_data, px_w, px_h)
        image = Image.frombytes("RGBA", (int(width), int(height)), bytes(rgba))
        if cache:
            self._raster_by_max_dim[cache_key] = image
        return image

    def _get_bounded_raster_size(self, max_dim: int, precision: float) -> tuple[int, int]:
        px_w = max(1, int(round(self.width * self.dpi / 72.0)))
        px_h = max(1, int(round(self.height * self.dpi / 72.0)))
        scale = min(1.0, max_dim / max(px_w, px_h))
        render_scale = min(scale, precision)
        render_dpi = max(10, int(math.floor(self.dpi * render_scale)))
        px_w = max(1, int(round(self.width * render_dpi / 72.0)))
        px_h = max(1, int(round(self.height * render_dpi / 72.0)))
        return px_w, px_h

    def sample_color(self, u: float, v: float) -> tuple[int, int, int]:
        image = self._get_raster()
        width, height = image.size

        u = min(max(u, 0.0), 1.0)
        v = min(max(v, 0.0), 1.0)

        px = min(width - 1, max(0, int(round(u * (width - 1)))))
        py = min(height - 1, max(0, int(round(v * (height - 1)))))
        color = image.getpixel((px, py))
        if isinstance(color, tuple) and len(color) >= 3:
            return (int(color[0]), int(color[1]), int(color[2]))
        elif isinstance(color, int):
            return (int(color), int(color), int(color))
        else:
            raise ValueError(f"unexpected pixel color format: {color}")

class _UVMapBase:
    def __init__(self, glider_obj: glider.ParametricGlider) -> None:
        self.glider = glider_obj
        self.glider3d = self.glider.get_glider_3d()
        self.cell_x_values = self.glider.shape.rib_x_values
        self._has_center_cell = bool(self.glider3d.has_center_cell)
        self._texture_bbox_cache: tuple[float, float, float, float] | None = None
        self._panel_index_by_id: dict[int, tuple[int, int]] = {}
        self._uv_panel_mesh_cache: dict[int, openglider.rs.mesh.Mesh] = {}
        for cell_no, cell in enumerate(self.glider3d.cells):
            for panel_idx, panel in enumerate(cell.panels):
                self._panel_index_by_id[id(panel)] = (cell_no, panel_idx)

    @staticmethod
    def _get_bbox(polylines: Iterable[openglider.rs.vector.PolyLine2D]) -> tuple[float, float, float, float]:
        points = [p for polyline in polylines for p in polyline]
        if not points:
            return (0.0, 1.0, 0.0, 1.0)

        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        return min_x, max_x, min_y, max_y

    def _can_mirror(self, cell_no: int) -> bool:
        return cell_no > 0 or not self._has_center_cell

    @staticmethod
    def _clamp01(value: float) -> float:
        return min(max(float(value), 0.0), 1.0)

    @staticmethod
    def _clamp11(value: float) -> float:
        return min(max(float(value), -1.0), 1.0)

    @staticmethod
    def _lerp(a: float, b: float, t: float) -> float:
        return a + t * (b - a)

    def _iter_panels(self) -> Iterable[tuple[int, int, Cell, Panel]]:
        for cell_no, cell in enumerate(self.glider3d.cells):
            for panel_idx, panel in enumerate(cell.panels):
                yield cell_no, panel_idx, cell, panel

    def _get_texture_bbox(self) -> tuple[float, float, float, float]:
        if self._texture_bbox_cache is None:
            self._texture_bbox_cache = self._compute_texture_bbox()
        return self._texture_bbox_cache

    def _normalize_texture_point(self, x: float, y: float) -> tuple[float, float]:
        min_x, max_x, min_y, max_y = self._get_texture_bbox()
        width = max(max_x - min_x, 1e-9)
        height = max(max_y - min_y, 1e-9)
        u = (x - min_x) / width
        v = 1.0 - ((y - min_y) / height)
        return (u, v)

    def transform_cell_local_coordinates(
        self,
        cell_no: int,
        panel_idx: int,
        x: float,
        y: float,
        mirrored: bool = False,
    ) -> tuple[float, float]:
        cell = self.glider3d.cells[cell_no]
        panel = cell.panels[panel_idx]
        return self.transform_panel_local_coordinates(panel, x=x, y=y, mirrored=mirrored)

    def _resolve_panel_reference(self, panel: Panel) -> tuple[int, int]:
        """Resolve a panel instance to (cell_no, panel_idx)."""
        cached = self._panel_index_by_id.get(id(panel))
        if cached is not None:
            return cached

        candidate_cells: list[int] = []

        if hasattr(panel, "cell_no"):
            try:
                raw_cell_no = int(getattr(panel, "cell_no"))
                if 0 <= raw_cell_no < len(self.glider3d.cells):
                    candidate_cells.append(raw_cell_no)
                elif 1 <= raw_cell_no <= len(self.glider3d.cells):
                    candidate_cells.append(raw_cell_no - 1)
            except (TypeError, ValueError):
                pass

        if candidate_cells:
            for cell_no in candidate_cells:
                for panel_idx, candidate in enumerate(self.glider3d.cells[cell_no].panels):
                    if candidate is panel or candidate == panel:
                        return cell_no, panel_idx

        # Fallback: global search by identity/equality.
        for cell_no, cell in enumerate(self.glider3d.cells):
            for panel_idx, candidate in enumerate(cell.panels):
                if candidate is panel or candidate == panel:
                    return cell_no, panel_idx

        # Last resort: search by side + name when present.
        panel_name = getattr(panel, "name", None)
        if panel_name:
            for cell_no, cell in enumerate(self.glider3d.cells):
                for panel_idx, candidate in enumerate(cell.panels):
                    if getattr(candidate, "name", None) == panel_name and candidate.is_lower() == panel.is_lower():
                        return cell_no, panel_idx

        raise ValueError("could not resolve panel reference to glider cell/panel index")

    def transform_panel_local_coordinates(
        self,
        panel: Panel,
        x: float,
        y: float,
        mirrored: bool = False,
    ) -> tuple[float, float]:
        cell_no, panel_idx = self._resolve_panel_reference(panel)
        panel_obj = self.glider3d.cells[cell_no].panels[panel_idx]
        return self._transform_panel_local_coordinates_resolved(
            cell_no=cell_no,
            panel=panel_obj,
            x=x,
            y=y,
            mirrored=mirrored,
        )

    def _transform_panel_local_coordinates_resolved(
        self,
        cell_no: int,
        panel: Panel,
        x: float,
        y: float,
        mirrored: bool = False,
    ) -> tuple[float, float]:
        x_local = self._clamp01(x)
        y_local = self._clamp11(y)
        tx, ty = self._texture_point_from_panel_local(
            cell_no=cell_no,
            panel=panel,
            x=x_local,
            y=y_local,
            mirrored=mirrored,
        )
        return self._normalize_texture_point(tx, ty)

    def transform_glider_coordinates(
        self,
        panel: Panel,
        x: float,
        y: float,
        mirrored: bool = False,
    ) -> tuple[float, float]:
        """Map glider-local coordinates (x in [0,1], y in [-1,1]) to texture UV."""
        return self.transform_panel_local_coordinates(panel=panel, x=x, y=y, mirrored=mirrored)

    def get_textured_panels_actor(
        self,
        texture: SVGTexture | str | Path,
        numribs: int = 3,
        precision: float = 1.0,
        cache_texture: bool = True,
        draw_edges: bool = False,
        boundary_only: bool = False,
    ) -> openglider.rs.wgpu.MeshActor:
        texture_map = texture if isinstance(texture, SVGTexture) else SVGTexture(texture)
        panel_mesh_cached = self._uv_panel_mesh_cache.get(numribs)
        if panel_mesh_cached is None:
            panel_mesh = self._build_uv_panel_mesh(numribs)
            self._uv_panel_mesh_cache[numribs] = panel_mesh.copy()
        else:
            panel_mesh = panel_mesh_cached.copy()

        image = texture_map.get_raster_bounded(8192, precision=precision, cache=cache_texture)
        # WGPU mandates MAX_TEXTURE_DIMENSION_2D <= 8192 on all conformant devices.
        _MAX_TEX = 8192
        if image.width > _MAX_TEX or image.height > _MAX_TEX:
            scale = min(_MAX_TEX / image.width, _MAX_TEX / image.height)
            image = image.resize(
                (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
        panel_mesh.set_texture_rgba(image.width, image.height, image.tobytes())
        return openglider.rs.wgpu.MeshActor(panel_mesh, draw_edges=draw_edges, boundary_only=boundary_only)

    def _build_uv_panel_mesh(self, numribs: int) -> openglider.rs.mesh.Mesh:
        panel_mesh = openglider.rs.mesh.Mesh(name="textured_panels")
        map_local = self._transform_panel_local_coordinates_resolved

        for cell_no, _panel_idx, cell, panel in self._iter_panels():
            mesh_temp = panel.get_mesh(cell, numribs=numribs)
            uv_original = mesh_temp.get_uv_coords()

            if uv_original is not None:
                uv_mapped = [
                    map_local(cell_no=cell_no, panel=panel, x=u, y=v, mirrored=False)
                    for u, v in uv_original
                ]
                mesh_temp.set_uv_coords(uv_mapped)

            panel_mesh += mesh_temp

            if self._can_mirror(cell_no):
                mesh_mirrored = mesh_temp.copy().mirror("y")
                # Keep panel-local UV inputs stable; mirrored mesh mutates UV y values.
                uv_source_m = uv_original if uv_original is not None else mesh_mirrored.get_uv_coords()
                if uv_source_m is not None:
                    uv_mapped_m = [
                        map_local(cell_no=cell_no, panel=panel, x=u, y=v, mirrored=True)
                        for u, v in uv_source_m
                    ]
                    mesh_mirrored.set_uv_coords(uv_mapped_m)
                panel_mesh += mesh_mirrored

        return panel_mesh

    def get_layout(self) -> Layout:
        points: list[openglider.rs.vector.PolyLine2D] = []
        for cell_no, panel_idx, cell, panel in self._iter_panels():
            del panel_idx, cell
            poly = self._get_overlay_panel_shape(cell_no, panel)
            points.append(poly.close())
            if self._can_mirror(cell_no):
                points.append(poly.mirror().close())

        layout = Layout()
        layout.parts.append(PlotPart(marks=points))
        layout = layout.scale(100)
        return layout

    def get_panels(self) -> tuple[list[tuple[Panel, openglider.rs.vector.PolyLine2D]], list[tuple[Panel, openglider.rs.vector.PolyLine2D]]]:
        upper: list[tuple[Panel, openglider.rs.vector.PolyLine2D]] = []
        lower: list[tuple[Panel, openglider.rs.vector.PolyLine2D]] = []
        for cell_no, panel_idx, cell, panel in self._iter_panels():
            del panel_idx, cell
            panel_polygon = self._get_overlay_panel_shape(cell_no, panel)
            target = lower if panel.is_lower() else upper
            target.append((panel, panel_polygon))
            if self._can_mirror(cell_no):
                target.append((panel, panel_polygon.mirror()))
        return upper, lower

    def _texture_point_from_panel_local(
        self,
        cell_no: int,
        panel: Panel,
        x: float,
        y: float,
        mirrored: bool,
    ) -> tuple[float, float]:
        raise NotImplementedError

    def _compute_texture_bbox(self) -> tuple[float, float, float, float]:
        raise NotImplementedError

    def _get_polygon_from_transform(
        self,
        cell_no: int,
        panel: Panel,
    ) -> openglider.rs.vector.PolyLine2D:
        corners = [
            (0.0, float(panel.cut_back.x_left)),
            (1.0, float(panel.cut_back.x_right)),
            (1.0, float(panel.cut_front.x_right)),
            (0.0, float(panel.cut_front.x_left)),
        ]
        points = [
            self._texture_point_from_panel_local(
                cell_no=cell_no,
                panel=panel,
                x=x_local,
                y=y_local,
                mirrored=False,
            )
            for x_local, y_local in corners
        ]
        return openglider.rs.vector.PolyLine2D(points)

    def _get_panel_shape(
        self,
        cell_no: int,
        panel: Panel,
        shape: Shape | None = None,
    ) -> openglider.rs.vector.PolyLine2D:
        raise NotImplementedError

    def _get_overlay_panel_shape(
        self,
        cell_no: int,
        panel: Panel,
    ) -> openglider.rs.vector.PolyLine2D:
        return self._get_panel_shape(cell_no, panel)

    def get_panel_polygon(
        self,
        cell_no: int,
        _panel_idx: int,
        _cell: Cell,
        panel: Panel,
    ) -> openglider.rs.vector.PolyLine2D:
        return self._get_polygon_from_transform(cell_no, panel)


class UVMapMirrored(_UVMapBase):
    def __init__(self, glider_obj: glider.ParametricGlider) -> None:
        super().__init__(glider_obj)
        self._rib_profile_to_y: list[openglider.rs.vector.Interpolation] = self._build_rib_profile_to_y()
        self._y_pair_cache: dict[tuple[int, float], tuple[float, float]] = {}

    def _get_length(self, x: Percentage, rib: Rib) -> float:
        ik_front = rib.profile_2d.get_ik(0)
        ik = rib.profile_2d.get_ik(x)

        length = rib.profile_2d.curve.get(ik_front, ik).get_length()

        if x.si < 0:
            length *= -1

        return length * rib.chord

    def _length_for_profile(self, value: float, rib: Rib) -> float:
        return self._get_length(Percentage(value), rib)

    def _build_rib_profile_to_y(self) -> list[openglider.rs.vector.Interpolation]:
        interpolations: list[openglider.rs.vector.Interpolation] = []
        for rib in self.glider3d.ribs:
            x_values = [float(v) for v in rib.profile_2d.x_values]
            if len(x_values) < 2:
                x_values = [-1.0, 1.0]
            nodes = [[xv, self._length_for_profile(xv, rib)] for xv in x_values]
            interpolations.append(openglider.rs.vector.Interpolation(nodes))
        return interpolations

    def _texture_x_raw(self, cell_no: int, x: float, mirrored: bool) -> float:
        u = float(cell_no) + self._clamp01(x)
        if mirrored and self._can_mirror(cell_no):
            return -u
        return u

    def _texture_y_raw(self, cell_no: int, x: float, y: float) -> float:
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
        return self._lerp(left, right, x_local)

    def _texture_point_from_panel_local(
        self,
        cell_no: int,
        panel: Panel,
        x: float,
        y: float,
        mirrored: bool,
    ) -> tuple[float, float]:
        return self._texture_x_raw(cell_no, x, mirrored), self._texture_y_raw(cell_no, x, y)

    def _compute_texture_bbox(self) -> tuple[float, float, float, float]:
        xs: list[float] = []
        ys: list[float] = []

        for cell_no, _panel_idx, _cell, _panel in self._iter_panels():
            xs.append(self._texture_x_raw(cell_no, 0.0, mirrored=False))
            xs.append(self._texture_x_raw(cell_no, 1.0, mirrored=False))
            if self._can_mirror(cell_no):
                xs.append(self._texture_x_raw(cell_no, 0.0, mirrored=True))
                xs.append(self._texture_x_raw(cell_no, 1.0, mirrored=True))

        for rib_no, rib in enumerate(self.glider3d.ribs):
            for y in [float(v) for v in rib.profile_2d.x_values]:
                ys.append(float(self._rib_profile_to_y[rib_no].get_value(y)))

        if not xs or not ys:
            return (0.0, 1.0, 0.0, 1.0)

        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        if abs(max_x - min_x) < 1e-9:
            max_x = min_x + 1.0
        if abs(max_y - min_y) < 1e-9:
            max_y = min_y + 1.0

        return (min_x, max_x, min_y, max_y)

    def _get_panel_shape(
        self,
        cell_no: int,
        panel: Panel,
        shape: Shape | None = None,
    ) -> openglider.rs.vector.PolyLine2D:
        del shape
        cell = self.glider3d.cells[cell_no]
        p1 = (self.cell_x_values[cell_no], self._get_length(panel.cut_back.x_left, cell.rib1))
        p2 = (self.cell_x_values[cell_no + 1], self._get_length(panel.cut_back.x_right, cell.rib2))
        p3 = (self.cell_x_values[cell_no + 1], self._get_length(panel.cut_front.x_right, cell.rib2))
        p4 = (self.cell_x_values[cell_no], self._get_length(panel.cut_front.x_left, cell.rib1))
        return openglider.rs.vector.PolyLine2D([p1, p2, p3, p4])

class UVMapStacked(_UVMapBase):
    def __init__(self, glider_obj: glider.ParametricGlider) -> None:
        super().__init__(glider_obj)
        self._shape = self.glider.get_shape()
        self._upper_offset = 0.0
        self._shape_point_cache: dict[tuple[int, float], tuple[float, float]] = {}
        _, _, self._upper_offset, _ = self._stacked_params(self._shape)

    def _shape_point_cached(self, rib_no: int, chord_pos: float) -> tuple[float, float]:
        key = (rib_no, chord_pos)
        cached = self._shape_point_cache.get(key)
        if cached is not None:
            return cached

        point = self._shape.get_point(rib_no, chord_pos)
        cached = (float(point[0]), float(point[1]))
        self._shape_point_cache[key] = cached
        return cached

    def _stacked_params(
        self,
        half_shape: Shape | None = None,
    ) -> tuple[float, float, float, float]:
        """Return (max_upper_y, max_lower_y, upper_offset, y_min) in Shape units."""
        if half_shape is None:
            half_shape = self.glider.get_shape()

        upper_polys: list[openglider.rs.vector.PolyLine2D] = []
        lower_polys: list[openglider.rs.vector.PolyLine2D] = []
        for cell_no, cell in enumerate(self.glider3d.cells):
            for panel in cell.panels:
                poly = self._get_panel_shape(cell_no, panel, half_shape)
                (lower_polys if panel.is_lower() else upper_polys).append(poly)

        upper_bbox = self._get_bbox(upper_polys) if upper_polys else (0.0, 0.0, 0.0, 0.0)
        lower_bbox = self._get_bbox(lower_polys) if lower_polys else (0.0, 0.0, 0.0, 0.0)
        max_upper_y = upper_bbox[3]
        max_lower_y = lower_bbox[3]
        size = max(max_upper_y, max_lower_y, 1e-3)
        gap = 0.05 * size
        upper_offset = (lower_bbox[3] + gap) - upper_bbox[2]
        y_min = min(upper_bbox[2] + upper_offset, lower_bbox[2])
        return max_upper_y, max_lower_y, upper_offset, y_min

    def _get_panel_shape(
        self,
        cell_no: int,
        panel: Panel,
        shape: Shape | None = None,
    ) -> openglider.rs.vector.PolyLine2D:
        """Panel corners using ShapePlot's planform-side projection."""
        if shape is None:
            shape = self.glider.get_shape()

        if panel.is_lower():
            def normalize_x(val: float | Percentage) -> float:
                return max(float(val), 0.0)
        else:
            def normalize_x(val: float | Percentage) -> float:
                return max(float(-val), 0.0)

        p_fl = shape.get_point(cell_no, normalize_x(panel.cut_front.x_left))  # type: ignore[union-attr]
        p_bl = shape.get_point(cell_no, normalize_x(panel.cut_back.x_left))   # type: ignore[union-attr]
        p_br = shape.get_point(cell_no + 1, normalize_x(panel.cut_back.x_right))  # type: ignore[union-attr]
        p_fr = shape.get_point(cell_no + 1, normalize_x(panel.cut_front.x_right))  # type: ignore[union-attr]

        return openglider.rs.vector.PolyLine2D([
            (float(p_bl[0]), float(p_bl[1])),
            (float(p_br[0]), float(p_br[1])),
            (float(p_fr[0]), float(p_fr[1])),
            (float(p_fl[0]), float(p_fl[1])),
        ])

    def _get_overlay_panel_shape(
        self,
        cell_no: int,
        panel: Panel,
    ) -> openglider.rs.vector.PolyLine2D:
        poly = self._get_panel_shape(cell_no, panel, self._shape)
        if panel.is_lower():
            return poly
        diff = openglider.rs.vector.Vector2D([0.0, self._upper_offset])
        return poly.move(diff)

    def _get_stacked_uv_polys(self) -> dict[tuple[int, int], openglider.rs.vector.PolyLine2D]:
        uv_poly_map: dict[tuple[int, int], openglider.rs.vector.PolyLine2D] = {}
        for cell_no, cell in enumerate(self.glider3d.cells):
            for panel_idx, panel in enumerate(cell.panels):
                poly = self.get_panel_polygon(cell_no, panel_idx, cell, panel)
                uv_poly_map[(cell_no, panel_idx)] = poly
        return uv_poly_map

    def _texture_point_from_panel_local(
        self,
        cell_no: int,
        panel: Panel,
        x: float,
        y: float,
        mirrored: bool,
    ) -> tuple[float, float]:
        x_local = self._clamp01(x)
        y_local = self._clamp11(y)
        is_lower = panel.is_lower()

        if is_lower:
            chord_pos = max(y_local, 0.0)
        else:
            chord_pos = max(-y_local, 0.0)

        p_lx, p_ly = self._shape_point_cached(cell_no, chord_pos)
        p_rx, p_ry = self._shape_point_cached(cell_no + 1, chord_pos)

        tx = self._lerp(p_lx, p_rx, x_local)
        ty = self._lerp(p_ly, p_ry, x_local)

        if not is_lower:
            ty += self._upper_offset

        if mirrored and self._can_mirror(cell_no):
            tx = -tx

        return tx, ty

    def _compute_texture_bbox(self) -> tuple[float, float, float, float]:
        uv_poly_map = self._get_stacked_uv_polys()
        all_polys: list[openglider.rs.vector.PolyLine2D] = []
        for (cell_no, _), poly in uv_poly_map.items():
            all_polys.append(poly)
            if self._can_mirror(cell_no):
                all_polys.append(poly.mirror())

        return self._get_bbox(all_polys)

class UVMap:
    """Compatibility facade over UVMapMirrored and UVMapStacked."""

    def __init__(self, glider_obj: glider.ParametricGlider) -> None:
        self.glider = glider_obj
        self.glider3d = self.glider.get_glider_3d()
        self.cell_x_values = self.glider.shape.rib_x_values
        self._mirrored = UVMapMirrored(glider_obj)
        self._stacked = UVMapStacked(glider_obj)

    def _map_for_mode(self, mode: UVMapMode) -> _UVMapBase:
        if mode == "stacked":
            return self._stacked
        return self._mirrored

    def transform_cell_local_coordinates(
        self,
        cell_no: int,
        panel_idx: int,
        x: float,
        y: float,
        mode: UVMapMode = "stacked",
        mirrored: bool = False,
    ) -> tuple[float, float]:
        return self._map_for_mode(mode).transform_cell_local_coordinates(cell_no, panel_idx, x, y, mirrored=mirrored)

    def transform_panel_local_coordinates(
        self,
        panel: Panel,
        x: float,
        y: float,
        mode: UVMapMode = "stacked",
        mirrored: bool = False,
    ) -> tuple[float, float]:
        return self._map_for_mode(mode).transform_panel_local_coordinates(
            panel=panel,
            x=x,
            y=y,
            mirrored=mirrored,
        )

    def transform_glider_coordinates(
        self,
        panel: Panel,
        x: float,
        y: float,
        mode: UVMapMode = "stacked",
        mirrored: bool = False,
    ) -> tuple[float, float]:
        return self._map_for_mode(mode).transform_glider_coordinates(
            panel=panel,
            x=x,
            y=y,
            mirrored=mirrored,
        )

    def get_panels(
        self,
        mode: UVMapMode = "mirrored",
    ) -> tuple[list[tuple[Panel, openglider.rs.vector.PolyLine2D]], list[tuple[Panel, openglider.rs.vector.PolyLine2D]]]:
        return self._map_for_mode(mode).get_panels()

    def get_textured_panels_actor(
        self,
        texture: SVGTexture | str | Path,
        numribs: int = 3,
        mode: UVMapMode = "stacked",
        precision: float = 1.0,
        cache_texture: bool = True,
        draw_edges: bool = False,
        boundary_only: bool = False,
    ) -> openglider.rs.wgpu.MeshActor:
        return self._map_for_mode(mode).get_textured_panels_actor(
            texture=texture,
            numribs=numribs,
            precision=precision,
            cache_texture=cache_texture,
            draw_edges=draw_edges,
            boundary_only=boundary_only,
        )

    def get_layout(self, mode: UVMapMode = "mirrored") -> Layout:
        return self._map_for_mode(mode).get_layout()

    # Backwards-compatible accessors for tests and callers that still use legacy internals.
    def _get_panel_shape(
        self,
        cell_no: int,
        panel: Panel,
        shape: Shape | None = None,
    ) -> openglider.rs.vector.PolyLine2D:
        return self._stacked._get_panel_shape(cell_no, panel, shape)

    def _stacked_params(self, half_shape: Shape | None = None) -> tuple[float, float, float, float]:
        return self._stacked._stacked_params(half_shape)

    def _get_stacked_uv_polys(self) -> dict[tuple[int, int], openglider.rs.vector.PolyLine2D]:
        return self._stacked._get_stacked_uv_polys()

