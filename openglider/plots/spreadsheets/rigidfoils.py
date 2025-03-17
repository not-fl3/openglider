from __future__ import annotations

from typing import TYPE_CHECKING
from openglider.utils.table import Table

if TYPE_CHECKING:
    from openglider.glider import Glider

def get_length_table(glider: Glider) -> Table:
    rib_table = get_rib_length_table(glider)
    rib_table.append_right(get_cell_length_table(glider), space=1)

    return rib_table

def get_rib_length_table(glider: Glider) -> Table:
    table = Table(name="Rigidfoils (rib)")

    current_row = 1

    table[0, 0] = "Name"
    table[0, 1] = "Rib no."
    table[0, 2] = "Start"
    table[0, 3] = "Stop"
    table[0, 4] = "Length"
    table[0, 5] = "Material"
    table[0, 6] = "Diameter"
    table[0, 7] = "Offset"

    for rib_no, rib in enumerate(glider.ribs):
        for rigidfoil in rib.get_rigidfoils():
            table[current_row, 0] = rigidfoil.name
            table[current_row, 1] = rib_no
            table[current_row, 2] = rigidfoil.start
            table[current_row, 3] = rigidfoil.end
            table[current_row, 4] = round(1000*rigidfoil.get_length(rib), 1)
            table[current_row, 5] = rigidfoil.material
            table[current_row, 6] = rigidfoil.diameter
            table[current_row, 7] = rigidfoil.distance

            current_row += 1

    return table

def get_cell_length_table(glider: Glider) -> Table:
    table = Table(name="Rigidfoils (cell)")
    current_row = 1

    table[0, 0] = "Name"
    table[0, 1] = "Cell no."
    table[0, 2] = "Cell position"
    table[0, 3] = "Start"
    table[0, 4] = "Stop"
    table[0, 5] = "Length"

    for cell_no, cell in enumerate(glider.cells):
        for rigidfoil in cell.rigidfoils:
            table[current_row, 0] = f"{cell.name} {rigidfoil.y}"
            table[current_row, 1] = cell_no
            table[current_row, 2] = rigidfoil.y
            table[current_row, 3] = rigidfoil.x_start
            table[current_row, 4] = rigidfoil.x_end
            table[current_row, 5] = round(1000*rigidfoil.get_length(cell), 1)

            current_row += 1

    return table