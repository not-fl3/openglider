import openglider.rs
from collections.abc import Iterator, Sized

class Triangle(Sized):
    attributes: dict
    nodes: tuple[int, int, int]

    def __init__(self, lst: tuple[int, int, int], name: str=""):
        self.nodes = lst
        self.attributes = {
            "name": name
        }
    
    def __iter__(self) -> Iterator[int]:
        return self.nodes.__iter__()
    
    def __len__(self) -> int:
        return 3


class TriMesh:
    def __init__(self, points: list[openglider.rs.vector.Vector2D], elements: list[tuple[int, int, int]], name: str=""):
        self.points = points
        self.elements = [Triangle(v, name) for v in elements]

class Triangulation:
    # Rust backend settings.
    keep_boundary = True
    planar_straight_line_graph = True
    max_area: float | None = None
    incremental_algorithm = True
    quality_mesh = True
    min_area: float | None = 1e-10

    name: str = ""

    def __init__(
        self,
        outline: openglider.rs.vector.PolyLine2D,
        holes: list[openglider.rs.vector.PolyLine2D] | None=None,
    ):
        self.outline = outline
        self.holes = holes or []

    @staticmethod
    def get_segments(polyline: list[int]) -> list[tuple[int, int]]:
        segments = []
        for i in range(len(polyline)-1):
            segments.append((polyline[i], polyline[i+1]))

        return segments

    def triangulate(self) -> TriMesh:
        triangulation = openglider.rs.mesh.triangulate_with_holes(
            self.outline,
            self.holes,
            min_area=self.min_area,
            max_area=self.max_area,
        )

        points = list(triangulation.nodes)
        elements = list(triangulation.triangles)

        return TriMesh(points, elements, self.name)
