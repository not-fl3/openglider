from __future__ import annotations

from openglider.mesh import Mesh


class MeshView:
    """Backend-independent 3D actor that stores mesh data for rendering."""

    def __init__(self) -> None:
        self.mesh = Mesh()

    def draw_mesh(self, mesh: Mesh, colors: bool=True) -> None:
        _ = colors
        self.mesh = mesh
