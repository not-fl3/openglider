from openglider.glider.parametric.table.base.dto import DTO
from openglider.glider.rib import MiniRib

from openglider.glider.parametric.table.base import CellTable
from openglider.vector.unit import Percentage, Length

class MiniRibDTO(DTO):
    y_value: Percentage
    front_cut: Percentage
    back_cut: Percentage
    trailing_edge_cut: Length
    material_code: str

    def get_object(self) -> MiniRib:
        return MiniRib(yvalue=self.y_value.si, front_cut=self.front_cut.si, back_cut=self.back_cut.si, trailing_edge_cut=self.trailing_edge_cut, material_code=self.material_code)
    
class MiniRibWithHoles(MiniRibDTO):
    hole_num: int
    def get_object(self) -> MiniRib:
        result = super().get_object()
        result.hole_num = self.hole_num

        return result

class MiniRibTable(CellTable):
    dtos = {
        "MINIRIB": MiniRibDTO,
        "MINIRIB6": MiniRibWithHoles
    }