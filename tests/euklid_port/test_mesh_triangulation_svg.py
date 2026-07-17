from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import openglider.rs as rs
from openglider.airfoil import Profile2D


def _ring_area(nodes: list[rs.vector.Vector2D]) -> float:
    if len(nodes) < 3:
        return 0.0
    area = 0.0
    for i, first in enumerate(nodes):
        second = nodes[(i + 1) % len(nodes)]
        area += float(first[0]) * float(second[1]) - float(second[0]) * float(first[1])
    return 0.5 * area


def _polyline_bounds(nodes: list[rs.vector.Vector2D]) -> tuple[float, float, float, float]:
    xs = [float(node[0]) for node in nodes]
    ys = [float(node[1]) for node in nodes]
    return min(xs), min(ys), max(xs), max(ys)


def _write_triangulation_svg(
    filepath: Path,
    nodes: list[rs.vector.Vector2D],
    triangles: list[tuple[int, int, int]],
    outline: rs.vector.PolyLine2D,
    hole: rs.vector.PolyLine2D,
) -> None:
    min_x, min_y, max_x, max_y = _polyline_bounds(nodes)
    width = max(max_x - min_x, 1e-9)
    height = max(max_y - min_y, 1e-9)
    pad = 0.08 * max(width, height)
    view_box = f"{min_x - pad} {-(max_y + pad)} {width + 2 * pad} {height + 2 * pad}"

    parts: list[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" width="1200" height="800">'
    )
    parts.append('<g transform="scale(1,-1)">')

    for ia, ib, ic in triangles:
        a = nodes[ia]
        b = nodes[ib]
        c = nodes[ic]
        parts.append(
            '<polygon '
            f'points="{float(a[0])},{float(a[1])} {float(b[0])},{float(b[1])} {float(c[0])},{float(c[1])}" '
            'fill="#9ecae1" fill-opacity="0.4" stroke="#08519c" stroke-width="0.0008" />'
        )

    def polyline_points(line: rs.vector.PolyLine2D) -> str:
        return " ".join(f"{float(p[0])},{float(p[1])}" for p in line.nodes)

    parts.append(
        f'<polyline points="{polyline_points(outline)}" fill="none" stroke="#0f172a" stroke-width="0.003" />'
    )
    parts.append(
        f'<polyline points="{polyline_points(hole)}" fill="none" stroke="#dc2626" stroke-width="0.003" />'
    )

    parts.append('</g>')
    parts.append('</svg>')

    filepath.write_text("\n".join(parts), encoding="utf-8")


class TestMeshTriangulationSvg(unittest.TestCase):
    def test_naca_1212_offset_triangulation_export_svg(self) -> None:
        profile = Profile2D.compute_naca(naca=1212, numpoints=180)
        inner = profile.curve

        amount = 0.02
        offset_plus = inner.offset(amount, True)
        offset_minus = inner.offset(-amount, True)

        # Choose the offset that encloses a larger area as the outer boundary.
        if abs(_ring_area(list(offset_plus.nodes))) >= abs(_ring_area(list(offset_minus.nodes))):
            outer = offset_plus
        else:
            outer = offset_minus

        triangulation = rs.mesh.triangulate_with_holes(outer, [inner])

        self.assertGreater(len(triangulation.nodes), 0)
        self.assertGreater(len(triangulation.triangles), 0)

        output_dir = Path(tempfile.gettempdir()) / "openglider_test_outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        svg_path = output_dir / "naca_1212_offset_triangulation.svg"

        _write_triangulation_svg(
            svg_path,
            list(triangulation.nodes),
            list(triangulation.triangles),
            outer,
            inner,
        )

        self.assertTrue(svg_path.exists())
        self.assertGreater(os.path.getsize(svg_path), 0)


if __name__ == "__main__":
    unittest.main()
