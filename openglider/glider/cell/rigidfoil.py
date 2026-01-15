from __future__ import annotations
import logging
import math
from typing import TYPE_CHECKING

import euklid
from openglider.glider.cell.panel import cuts
from openglider.glider.cell.panel.panel import PANELCUT_TYPES, FlattenedPanel
from openglider.utils.dataclass import dataclass
import openglider.vector.drawing
from openglider.vector.unit import Length, Percentage

if TYPE_CHECKING:
    from openglider.glider.cell import Cell
    from openglider.glider.cell.panel import Panel

logger = logging.getLogger(__name__)



@dataclass
class PanelRigidFoil:
    x_start: Percentage
    x_end: Percentage
    y: Percentage = Percentage(0.5)
    channel_width: Length = Length("1cm")
    pocket_length: Length = Length("2cm")

    total_length: float | None = None

    def get_flattened(self, cell: Cell, midribs: int, cut_types: dict[PANELCUT_TYPES, type[cuts.Cut]] | None) -> tuple[openglider.vector.drawing.PlotPart, dict[Panel, list[euklid.vector.PolyLine2D]]]:
        dwg = openglider.vector.drawing.PlotPart(material_code="rigidfoil")
        panels = list(sorted(cell.panels, key=lambda p: p.mean_x()))
        
        # check lengths for each panels
        # generate sections of connected panels with some off-panel section in between
        # for each section generate 
        flat_panels: dict[Panel, FlattenedPanel] = {}
        lines: dict[Panel, euklid.vector.PolyLine2D] = {} # panel -> line
        profile_3d = cell.midrib(self.y.si)

        panel_marks: dict[Panel, list[euklid.vector.PolyLine2D]] = {}

        for panel in panels:
            panel_flat = panel.get_flattened(cell, midribs=midribs, cut_types=cut_types)
            line = panel_flat.draw_straight_line(self.y, self.x_start, self.x_end)
            if line is not None:
                flat_panels[panel] = panel_flat
                lines[panel] = line
        
        current_section: list[Panel] = []
        current_section_offset = 0.

        def add_section(next_panel: Panel | None) -> None:
            nonlocal current_section_offset
            # get all panel line lengths
            lengths = [
                lines[panel].get_length() for panel in current_section
            ]
            total_length = sum(lengths)
            print(lengths)
            
            # start and end mark offset
            mark_offset_side = 0.01
            # distance between marks: nearest to 5cm but divides evenly
            distance_between = 0.05
            num_marks = math.ceil((total_length - 2*mark_offset_side) / distance_between)
            distance_between = (total_length - 2*mark_offset_side) / (num_marks + 1)
            
            # add lines
            for i in range(len(current_section)+1):
                x = current_section_offset + sum(lengths[:i])
                dwg.layers["marks"].append(
                    euklid.vector.PolyLine2D([
                        euklid.vector.Vector2D([x, -self.channel_width/2]),
                        euklid.vector.Vector2D([x, self.channel_width/2]),
                    ])
                )
            
            # add marks
            mark_positions = [
                mark_offset_side + i * distance_between for i in range(num_marks+1)
            ] + [total_length - mark_offset_side]
            mark_distance = 0.002 # 2mm

            for mark_position in mark_positions:
                dwg.layers["L0"].append(
                    euklid.vector.PolyLine2D([euklid.vector.Vector2D([current_section_offset + mark_position, -mark_distance])])
                )
                dwg.layers["L0"].append(
                    euklid.vector.PolyLine2D([euklid.vector.Vector2D([current_section_offset + mark_position, mark_distance/2])])
                )

            # add to panels
            for i, panel in enumerate(current_section):
                line = lines[panel]
                panel_start = sum(lengths[:i])
                panel_end = panel_start + lengths[i]
                panel_marks.setdefault(panel, [])
                panel_marks[panel] += [
                    line
                ]

                for mark_position in mark_positions:
                    if mark_position > panel_start and mark_position < panel_end:
                        p1 = line.get(line.walk(0, mark_position - panel_start))
                        p2 = line.offset(mark_distance/2).get(line.walk(0, mark_position - panel_start))
                        panel_marks[panel] += [
                            euklid.vector.PolyLine2D([p2]),
                            euklid.vector.PolyLine2D([p1 + (p1 - p2)])
                        ]



            current_section_offset += total_length

            if next_panel is not None:
                # add region without panel
                ik_1 = flat_panels[current_section[-1]].cut_back.get_inner_index(self.y.si)
                ik_2 = flat_panels[next_panel].cut_front.get_inner_index(self.y.si)

                current_section_offset += profile_3d.curve.get(ik_1, ik_2).get_length()




        for panel in panels:
            if panel in lines:
                if len(current_section) and current_section[-1].cut_back == panel.cut_front:
                    current_section.append(panel)
                else:
                    if len(current_section) > 0:
                        add_section(panel)
                    current_section = [panel]
        
        if current_section:
            add_section(None)

        # draw outline
        outline = euklid.vector.PolyLine2D([
            euklid.vector.Vector2D([-self.pocket_length.si, -self.channel_width/2]),
            euklid.vector.Vector2D([current_section_offset + self.pocket_length.si, -self.channel_width/2]),
            euklid.vector.Vector2D([current_section_offset + self.pocket_length.si, self.channel_width/2]),
            euklid.vector.Vector2D([-self.pocket_length.si, self.channel_width/2]),
        ]).close()

        dwg.layers["cuts"].append(outline)

        self.total_length = current_section_offset

        return dwg, panel_marks
