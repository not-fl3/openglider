

from openglider.glider.glider import Glider
from openglider.utils.table import Table


def get_attachment_point_table(glider: Glider) -> Table:
    table = Table(name="Attachment Points")

    table.insert_row(["Rib No.", "Attachment Point", "Type"])
    
    for rib in glider.ribs:
        if rib.attachment_points:
            for attachment_point in rib.attachment_points:
                table.insert_row([rib.name, attachment_point.name, attachment_point.type_name])
            table.insert_row([])
    
    return table