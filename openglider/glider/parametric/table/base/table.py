import enum
import logging
import typing
from typing import Any, Generic, TypeVar


from openglider.glider.curve import GliderCurveType
from openglider.glider.parametric.table.base.dto import DTO
from openglider.glider.parametric.table.base.parser import Parser
from openglider.utils.table import Table
from openglider.vector.unit import Quantity

from .keyword import Keyword

logger = logging.getLogger(__name__)

ElementType = TypeVar("ElementType")

class TableType(enum.Enum):
    rib = "Rib Table"
    cell = "Cell Table"
    general = "General Table"

class ElementTable(Generic[ElementType]):
    table_type: TableType = TableType.general
    keywords: dict[str, Keyword[Any]] = {}
    dtos: dict[str, type[DTO[Any]]] = {}
    _dto_field_plan_cache: dict[type[DTO[Any]], list[tuple[str, tuple[int, int] | None, bool]]] = {}

    def __init__(self, table: Table | None=None, migrate_header: bool=False):
        self.table = Table()
        if table is not None:
            if migrate_header:
                _table = table.get_rows(0, 1)
                _table.append_bottom(table.get_rows(1, table.num_rows), space=1)
            else:
                _table = table

            def add_data(keyword: str, data_length: int) -> None:
                for column in self.get_columns(_table, keyword, data_length):
                    self.table.append_right(column)

            for keyword in self.keywords:
                data_length = self.keywords[keyword].attribute_length
                add_data(keyword, data_length)

            for dto in self.dtos:
                data_length = self.dtos[dto].column_length()
                add_data(dto, data_length)
    
    def __json__(self) -> dict[str, Any]:
        return {
            "table": self.table
        }
    
    @classmethod
    def get_columns(cls, table: Table, keyword: str, data_length: int) -> list[Table]:
        columns: list[Table] = []
        cache_key = (cls.__name__, keyword, data_length, table._version)
        cached_columns = table._element_table_cache.get(cache_key)

        if keyword in cls.keywords:
            keyword_instance = cls.keywords[keyword]
            header = keyword_instance.get_header(keyword)
        elif keyword in cls.dtos:
            dto = cls.dtos[keyword]
            types = dto.describe()
            header = Table()
            header[0, 0] = keyword
            for i, (field_name, field_type) in enumerate(types):
                header[1, i] = f"{field_name}: {field_type}"
        else:
            raise ValueError(f"unknown keyword {keyword}")

        if cached_columns is None:
            header_starts = [column for key, (column, row) in table.coords.items() if row == 0 and table.dct.get(key) == keyword]
            header_starts.sort()

            cached_columns = []
            for column in header_starts:
                cells: list[tuple[int, int, Any]] = []

                for key, value in table.dct.items():
                    source_column, source_row = table.coords[key]
                    if source_row >= 2 and column <= source_column < column + data_length and value is not None:
                        cells.append((source_column - column, source_row - 2, value))

                cached_columns.append((column, tuple(cells)))

            table._element_table_cache[cache_key] = tuple(cached_columns)

        for column, cells in cached_columns:
            columns_part_header = header.copy()
            columns_part = Table()

            for source_column, source_row, value in cells:
                columns_part.set_value(source_column, source_row, value)

            columns_part_header.append_bottom(columns_part)
            columns.append(columns_part_header)

        return columns

    def get(self, row_no: int, keywords: list[str] | None=None, **kwargs: Any) -> list[ElementType]:
        row_no += 2  # skip header line
        elements: list[ElementType] = []
        
        for keyword in list(self.keywords.keys()) + list(self.dtos.keys()):
            if keyword in self.keywords:
                data_length = self.keywords[keyword].attribute_length
            else:
                data_length = self.dtos[keyword].column_length()

            if keywords is not None and keyword not in keywords:
                logger.debug(f"skipping keyword {keyword}")
                continue

            for column in self.get_columns(self.table, keyword, data_length):
                if column[row_no, 0] is not None:
                    data = [column[row_no, i] for i in range(data_length)]
                    try:
                        element = self.get_element(row_no-2, keyword, data, **kwargs)
                    except Exception as e:
                        logger.error(f"failed to get element ({keyword}: {row_no-2}, ({data})")
                        raise e

                    elements.append(element)
        return elements
    
    @staticmethod
    def get_curve_value(curves: dict[str, GliderCurveType] | None, curve_name: str | float, rib_no: int) -> float | Quantity:
        if curves is None:
            raise ValueError("No curves specified")

        if isinstance(curve_name, str):
            factor = 1.
            if curve_name.startswith("-"):
                curve_name = curve_name[1:]
                factor = -1
            
            return curves[curve_name].get(rib_no) * factor
        
        return curve_name
    
    def get_one(self, row_no: int, keywords: list[str] | None=None, **kwargs: Any) -> ElementType | None:
        elements = self.get(row_no, keywords=keywords, **kwargs)

        if len(elements) > 1:
            logger.error(f"received too many elements for {keywords} (expected to get only one) in row {row_no}! {elements}")

        if len(elements) > 0:
            return elements[0]
        
        return None

    @classmethod
    def _get_dto_field_plan(cls, dto: type[DTO[Any]]) -> list[tuple[str, tuple[int, int] | None, bool]]:
        if dto not in cls._dto_field_plan_cache:
            plan: list[tuple[str, tuple[int, int] | None, bool]] = []

            for field_name, field in dto.model_fields.items():
                tuple_type = dto.check_is_cell_tuple(field.annotation)
                if tuple_type is not None:
                    plan.append((field_name, tuple_type.index_offset, False))
                else:
                    plan.append((field_name, None, field.annotation is str or typing.get_origin(field.annotation) == typing.Literal))

            cls._dto_field_plan_cache[dto] = plan

        return cls._dto_field_plan_cache[dto]

    def _prepare_dto_data(self, row: int, dto: type[DTO[Any]], data: list[Any], resolvers: list[Parser]) -> dict[str, Any]:
        dct: dict[str, Any] = {}
        index = 0

        for field_name, tuple_offset, is_raw in self._get_dto_field_plan(dto):
            if tuple_offset is not None:
                offset1, offset2 = tuple_offset
                dct[field_name] = (
                    resolvers[row].parse(data[index+offset1]),
                    resolvers[row+1].parse(data[index+offset2])
                )
                index = index + 1 + max(tuple_offset)
            else:
                if is_raw:
                    dct[field_name] = data[index]
                else:
                    dct[field_name] = resolvers[row].parse(data[index])
                index += 1
        
        return dct

    
    def get_element(self, row: int, keyword: str, data: list[typing.Any], **kwargs: Any) -> ElementType:
        if keyword in self.keywords:
            keyword_mapper = self.keywords[keyword]

            return keyword_mapper.get(keyword, data)
        
        elif keyword in self.dtos:
            dto = self.dtos[keyword]
            dct = self._prepare_dto_data(row, dto, data, kwargs["resolvers"])
                
            return dto(**dct).get_object()

        else:
            raise ValueError()

    def _repr_html_(self) -> str:
        return self.table._repr_html_() # type: ignore


class CellTable(ElementTable[Any]):
    table_type = TableType.cell

class RibTable(ElementTable[Any]):
    table_type = TableType.rib
