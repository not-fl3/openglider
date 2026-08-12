from __future__ import annotations

from openglider.glider.texture.uv_map.mirrored import UVMapMirrored
from openglider.glider.texture.uv_map.stacked import UVMapStacked
import openglider.rs


import svglib.svglib
from PIL import Image
from reportlab.graphics.shapes import Drawing, Group, Line, Path as ReportPath, PolyLine, Polygon


import math
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from openglider.utils.dataclass import BaseModel

class Texture(BaseModel):
    uv_map: UVMapMirrored | UVMapStacked
    texture: SVGTexture


class SVGTexture:
    """SVG-backed texture utility for vector extraction and raster sampling."""

    def __init__(self, svg_data: str, dpi: int = 300):
        self.dpi = dpi
        self._svg_data = svg_data
        self.width, self.height = self._read_svg_size(self._svg_data)
        self._drawing: Drawing | None = None
        self._normalized_vectors: list[openglider.rs.vector.PolyLine2D] | None = None
        self._raster: Image.Image | None = None
        self._raster_by_max_dim: dict[tuple[int, float], Image.Image] = {}

    @classmethod
    def read(cls, file_path: Path, dpi: int = 300) -> SVGTexture:
        svg_bytes = file_path.read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                svg_data = svg_bytes.decode(encoding)
                return cls(svg_data=svg_data, dpi=dpi)
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
            raise ValueError("could not read svg file") from err

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

        raise ValueError("svg file has no usable size information")

    def _normalize_point(self, x: float, y: float) -> tuple[float, float]:
        u = 0.0 if self.width == 0 else x / self.width
        v = 1.0 if self.height == 0 else 1.0 - y / self.height
        return u, v

    def _get_drawing(self) -> Drawing:
        if self._drawing is None:
            drawing = svglib.svglib.svg2rlg(BytesIO(self._svg_data.encode("utf-8")))  # type: ignore
            if drawing is None:
                raise ValueError("could not read svg file")
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