from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import openglider.rs
from openglider.mesh import Mesh


def _clip01(value: float) -> float:
	return max(0.0, min(1.0, value))


def _rgb_float_to_hex(color: Sequence[float]) -> str:
	r = int(round(_clip01(float(color[0])) * 255))
	g = int(round(_clip01(float(color[1])) * 255))
	b = int(round(_clip01(float(color[2])) * 255))
	return f"#{r:02X}{g:02X}{b:02X}"


def _named_color_to_rgb(color: str) -> tuple[float, float, float]:
	named = {
		"grey": (0.60, 0.60, 0.60),
		"gray": (0.60, 0.60, 0.60),
		"white": (1.00, 1.00, 1.00),
		"black": (0.00, 0.00, 0.00),
		"red": (1.00, 0.00, 0.00),
		"green": (0.00, 1.00, 0.00),
		"blue": (0.00, 0.00, 1.00),
		"yellow": (1.00, 1.00, 0.00),
		"cyan": (0.00, 1.00, 1.00),
	}
	return named.get(color.lower(), (0.60, 0.60, 0.60))


def _default_color_hex(default_color: str | Sequence[float] | None) -> str:
	if default_color is None:
		return "#999999"
	if isinstance(default_color, str):
		return _rgb_float_to_hex(_named_color_to_rgb(default_color))
	return _rgb_float_to_hex(default_color)


def _sample_colormap(value: float) -> tuple[float, float, float]:
	"""Turbo-like 4-stop ramp: blue -> cyan -> yellow -> red."""
	v = _clip01(value)
	if v < 1.0 / 3.0:
		t = v * 3.0
		return (0.0, t, 1.0)
	if v < 2.0 / 3.0:
		t = (v - 1.0 / 3.0) * 3.0
		return (t, 1.0, 1.0 - t)
	t = (v - 2.0 / 3.0) * 3.0
	return (1.0, 1.0 - t, 0.0)


def _normalize_values(values: Sequence[float]) -> list[float]:
	if not values:
		return []
	vmin = min(values)
	vmax = max(values)
	if vmax <= vmin:
		return [0.5 for _ in values]
	scale = vmax - vmin
	return [(v - vmin) / scale for v in values]


@dataclass
class _MeshActorWrapper:
	actor: openglider.rs.wgpu.MeshActor


class MeshView(_MeshActorWrapper):
	"""Backward-compatible mesh wrapper used by View3D.show_actor()."""

	def __init__(self, mesh: Mesh | None=None, default_color: str | Sequence[float] | None=None):
		self.mesh = mesh or Mesh(name="mesh_view")
		self.default_color = default_color
		actor_mesh = self.mesh if default_color is None else self._apply_single_color(self.mesh, default_color)
		super().__init__(openglider.rs.wgpu.MeshActor(actor_mesh, draw_edges=True, boundary_only=False))

	def _apply_single_color(self, mesh: Mesh, color: str | Sequence[float]) -> Mesh:
		vertices, polygons, boundaries = mesh.get_indexed()
		color_hex = _default_color_hex(color)
		recolored: dict[str, list[tuple[tuple[int, ...], dict[str, object]]]] = {}
		for _, layer in polygons.items():
			recolored.setdefault(f"mesh{color_hex}", []).extend(
				[(tuple(indices), dict(attrs)) for indices, attrs in layer]
			)
		return Mesh.from_indexed(vertices, recolored, boundaries=boundaries, name=mesh.name)

	def draw_mesh(self, mesh: Mesh) -> None:
		self.mesh = mesh
		actor_mesh = self.mesh if self.default_color is None else self._apply_single_color(self.mesh, self.default_color)
		self.actor = openglider.rs.wgpu.MeshActor(actor_mesh, draw_edges=True, boundary_only=False)


class MeshDataView(MeshView):
	"""Create a mesh actor with face colors mapped from scalar panel data."""

	def __init__(self, mesh: Mesh, data: Iterable[float] | None=None, default_color: str | Sequence[float]="Grey"):
		self.data = list(data) if data is not None else []
		colored_mesh = self._build_colored_mesh(mesh, self.data, default_color)
		super().__init__(colored_mesh)

	def _build_colored_mesh(
		self,
		mesh: Mesh,
		data: Sequence[float],
		default_color: str | Sequence[float] | None,
	) -> Mesh:
		vertices, polygons, boundaries = mesh.get_indexed()

		normalized = _normalize_values(data)
		poly_colors = [_rgb_float_to_hex(_sample_colormap(v)) for v in normalized]
		fallback_hex = _default_color_hex(default_color)

		recolored: dict[str, list[tuple[tuple[int, ...], dict[str, object]]]] = {}
		data_index = 0

		for layer_name, layer_polys in polygons.items():
			for indices, attrs in layer_polys:
				# Color only surface polygons using data; keep line colors neutral.
				if len(indices) > 2 and data_index < len(poly_colors):
					color_hex = poly_colors[data_index]
					data_index += 1
				else:
					color_hex = fallback_hex

				key = f"{layer_name}{color_hex}"
				recolored.setdefault(key, []).append((tuple(indices), dict(attrs)))

		return Mesh.from_indexed(vertices, recolored, boundaries=boundaries, name=f"{mesh.name}_colored")


class Arrow(_MeshActorWrapper):
	"""Simple line-arrow replacement for WGPU renderer compatibility."""

	def __init__(
		self,
		p1: openglider.rs.vector.Vector3D,
		p2: openglider.rs.vector.Vector3D,
		shaft: float=0.01,
		tip: float=0.2,
		color: tuple[float, float, float] | None=None,
	):
		_ = shaft
		_ = tip
		color_hex = _default_color_hex(color or (1.0, 0.0, 0.0))
		points = [p1.copy(), p2.copy()]
		polygons = {f"arrow{color_hex}": [((0, 1), {})]}
		mesh = Mesh.from_indexed(points, polygons, name="arrow")
		super().__init__(openglider.rs.wgpu.MeshActor(mesh, draw_edges=True, boundary_only=False))

