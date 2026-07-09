from __future__ import annotations

from typing import TYPE_CHECKING
import openglider.rs
import logging
import pyfoil

from openglider.airfoil import Profile3D
from openglider.utils.dataclass import dataclass, Field
from openglider.mesh import Mesh, triangulate
from openglider.vector.unit import Length, Percentage
from openglider.glider.rib.crossports import polygon

if TYPE_CHECKING:
    from openglider.glider.cell import Cell

logger = logging.getLogger(__name__)

@dataclass
class MiniRib:
    yvalue: float
    front_cut: float
    back_cut: float | None=None
    chord: float = 0.3
    name: str="unnamed_minirib"
    material_code: str="unnamed_material"
    seam_allowance: Length = Length("6mm")
    trailing_edge_cut: Length = Length("20mm")
    mrib_num: int = 0
    function: openglider.rs.vector.Interpolation = Field(default_factory=lambda: openglider.rs.vector.Interpolation([]))
    hole_num: int = 0
    hole_border_side : Length | Percentage = Length("2cm")
    hole_border_panel: Length | Percentage = Length("2cm")
    hole_curve_factor: float = 0.5


    class Config:
        arbitrary_types_allowed = True

    def __post_init__(self) -> None:

        p1_x = 2/3

        if self.function is None or len(self.function.nodes) == 0:
            if self.front_cut > 0:
                if self.back_cut is None:
                    back_cut = 1.
                else:
                    back_cut = self.back_cut
                points = [[self.front_cut, 1], [self.front_cut + (back_cut - self.front_cut) * (1-p1_x), 0]]  #
            else:
                points = [[0, 0]]

            if self.back_cut is not None and self.back_cut < 1.:
                points = points + [[self.front_cut + (self.back_cut-self.front_cut) * p1_x, 0], [self.back_cut, 1]]
            else:
                points = points + [[1., 0.]]

            curve = openglider.rs.spline.BSplineCurve(points).get_sequence(100)
            self.function = openglider.rs.vector.Interpolation(curve.nodes)

    def get_multiplier(self, x: float) -> float:
        within_back_cut = self.back_cut is None or abs(x) <= self.back_cut
        if self.front_cut <= abs(x) and within_back_cut:
            return min(1, max(0, self.function.get_value(abs(x))))
        else:
            return 1.
        
    def rib_chord(self, cell: Cell) -> float:
        return cell.rib1.chord*(1-self.yvalue) + cell.rib2.chord*self.yvalue
        
    def convert_to_percentage(self, value: Percentage | Length, cell: Cell) -> Percentage:
        if isinstance(value, Percentage):
            return value
        
        return Percentage(value.si/self.rib_chord(cell))
    
    def get_offset_outline(self, cell:Cell, margin: Percentage | Length) -> pyfoil.Airfoil:
        profile_3d = self.get_profile_3d(cell)
        self.profile_2d = profile_3d.flatten()
        if margin == 0.:
            return self.profile_2d
        else:
            if isinstance(margin, Percentage):
                margin = margin/self.chord
            
            envelope = self.profile_2d.curve.offset(-margin.si, simple=False).nodes
            
            return pyfoil.Airfoil(envelope)
        
    def get_flattened(self, cell:Cell) -> openglider.rs.vector.PolyLine2D:
        profile_3d = self.get_profile_3d(cell)
        return profile_3d.flatten().curve
   

    def get_profile_3d(self, cell: Cell) -> Profile3D:

        return cell.rib_profiles_3d[self.mrib_num+1]  
    
    def convert_to_chordlength(self, value: Percentage | Length, cell:Cell) -> Length:
        if isinstance(value, Length):
            return value
        
        return Length(value.si*self.rib_chord(cell))

    def _get_lengths(self, cell: Cell) -> tuple[float, float]:
        flattened_cell = cell.get_flattened_cell()
        left, right = flattened_cell.ballooned
        line = left.mix(right, self.yvalue)

        if self.back_cut is None:
            back_cut = 1.
        else:
            back_cut = self.back_cut

        ik_front_bot = (cell.rib1.profile_2d(self.front_cut) + cell.rib2.profile_2d(self.front_cut))/2
        ik_back_bot = (cell.rib1.profile_2d(back_cut) + cell.rib2.profile_2d(back_cut))/2


        ik_back_top = (cell.rib1.profile_2d(-self.front_cut) + cell.rib2.profile_2d(-self.front_cut))/2
        ik_front_top = (cell.rib1.profile_2d(-back_cut) + cell.rib2.profile_2d(-back_cut))/2

        return line.get(ik_front_top, ik_back_top).get_length(), line.get(ik_front_bot, ik_back_bot).get_length()

    def get_nodes(self, cell: Cell) -> tuple[openglider.rs.vector.PolyLine2D, openglider.rs.vector.PolyLine2D]:
        profile_3d = self.get_profile_3d(cell)
        profile_2d = profile_3d.flatten()
        contour = profile_2d.curve

        cutback = self.convert_to_chordlength(self.trailing_edge_cut, cell).si

        start_bottom = profile_2d.get_ik(self.front_cut*profile_2d.curve.nodes[0][0])
        end_bottom = profile_2d.get_ik(self.back_cut*profile_2d.curve.nodes[0][0]-cutback)
        start_top = profile_2d.get_ik(-self.front_cut*profile_2d.curve.nodes[0][0])
        end_top = profile_2d.get_ik(-self.back_cut*profile_2d.curve.nodes[0][0]+cutback)

        nodes_top = contour.get(end_top, start_top)
        nodes_bottom = contour.get(start_bottom, end_bottom)

        return nodes_top, nodes_bottom

    def rename_parts(self) -> None:
        for hole_no, hole in enumerate(self.holes):
            hole.name = self.hole_naming_scheme.format(hole_no, rib=self)


    def get_hull(self, cell: Cell) -> openglider.rs.vector.PolyLine2D:
        """returns the outer contour of the normalized mesh in form
           of a Polyline"""
        
        nodes_top, nodes_bottom = self.get_nodes(cell)

        return openglider.rs.vector.PolyLine2D(nodes_top.nodes+nodes_bottom.nodes)

    def align_all(self, cell: Cell, data: openglider.rs.vector.PolyLine2D) -> openglider.rs.vector.PolyLine3D:
        """align 2d coordinates to the 3d pos of the minirib"""
        projection_plane: openglider.rs.plane.Plane = self.get_profile_3d(cell).projection_layer

        nodes_3d: list[openglider.rs.vector.Vector3D] = []
        
        for p in data:
            nodes_3d.append(
                projection_plane.p0 + projection_plane.x_vector * p[0] + projection_plane.y_vector * p[1]
            )
        
        return openglider.rs.vector.PolyLine3D(nodes_3d)


    def get_mesh(self, cell:Cell, filled: bool=True, max_area: float=None, hole_res: int = 40) -> Mesh:
        outline = self.get_hull(cell)
        holes, _hole_centers = self.get_holes(cell, hole_res)

        if filled:
            tri = triangulate.Triangulation(
                outline,
                holes,
            )
            if max_area is not None:
                tri.max_area = max_area

            tri.name = self.name
            mesh = tri.triangulate()

            points = self.align_all(cell, openglider.rs.vector.PolyLine2D(mesh.points))
            boundaries = {self.name: list(range(len(points)))}


            minirib_mesh = Mesh.from_indexed(points.nodes, polygons={"miniribs": [(tri, {}) for tri in mesh.elements]} , boundaries=boundaries)

        else:
            vertices = [(p[0], p[1]) for p in outline.nodes[:-1]]
            boundary = [list(range(len(vertices))) + [0]]
            for curve in holes:
                start_index = len(vertices)
                hole_vertices = curve.tolist()[:-1]
                hole_indices = list(range(len(hole_vertices))) + [0]
                vertices+= hole_vertices
                boundary.append([start_index + i for i in hole_indices])

            segments = []
            for lst in boundary:
                segments += triangulate.Triangulation.get_segments(lst)
            return Mesh.from_indexed(
                self.align_all(cell, openglider.rs.vector.PolyLine2D(vertices)).nodes,
                {'minirib': [(segment, {}) for segment in segments]},
                {}
            )

        return minirib_mesh
    

    def get_holes(self, cell: Cell, num_points: int=140) -> tuple[list[openglider.rs.vector.PolyLine2D], list[openglider.rs.vector.Vector2D]]:
        if self.hole_num < 1:
            return [], []
        nodes_top, nodes_bottom = self.get_nodes(cell)

        # add border on top / bottom
        offset = self.convert_to_chordlength(self.hole_border_panel, cell)
        top_curve = nodes_top.reverse().offset(offset)
        bottom_curve = nodes_bottom.offset(-offset)

        # check for intersection between offset lines
        try:
            cut = top_curve.cut(bottom_curve, nearest_ik=len(top_curve.nodes)-1)
            top_curve = top_curve.get(0, cut[0])
            bottom_curve = bottom_curve.get(0, cut[1])
        except RuntimeError:
            pass

        # helper functions to get points on minirib
        len_top=top_curve.get_length()
        len_bot=bottom_curve.get_length()

        def to_percentage(length: Length | Percentage):
            if isinstance(length, Percentage):
                return length

            return Percentage(length.si/len_top)
        
        def get_top(x: float) -> openglider.rs.vector.Vector2D:
            return top_curve.get(top_curve.walk(0, len_top*x))
        
        def get_bottom(x: float) -> openglider.rs.vector.Vector2D:
            return bottom_curve.get(bottom_curve.walk(0, len_bot*x))

        holes = []
        centers = []

        end = self.back_cut if self.back_cut is not None else 1.
        
        if self.trailing_edge_cut is not None:
            end -= to_percentage(self.trailing_edge_cut).si

        border_holes = to_percentage(self.hole_border_side).si

        total_border = (self.hole_num + 1) * border_holes
        hole_width = (1 - total_border) / self.hole_num

        x_left = border_holes

        # draw holes
        for _ in range(self.hole_num):
            x_right = x_left + hole_width
            x_center = (x_left+x_right)/2

            points = [
                get_bottom(x_left),
                get_bottom(x_right),
                get_top(x_right),
                get_top(x_left)
            ]

            holes.append(polygon(points, self.hole_curve_factor, num_points))
            centers.append((get_top(x_center) + get_bottom(x_center))* 0.5)

            x_left = x_right + border_holes

        return holes, centers
