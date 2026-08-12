from __future__ import annotations

import copy
from decimal import Decimal
import re
from typing import Any, Union
import numbers

from odfdo import Cell as OdfdoCell
from odfdo import Column as OdfdoColumn
from odfdo import Document as OdfdoDocument
from odfdo import Row as OdfdoRow
from odfdo import Style as OdfdoStyle
from odfdo import Table as OdfdoTable

CellIndex = Union[tuple[int, int], str]


class ODSDocument:
    """Compatibility wrapper for ODS export objects.

    Existing call sites expect `.saveas(path)` and optional `.document`
    access for post-processing.
    """

    def __init__(self, document: OdfdoDocument):
        self.document = document

    def saveas(self, path: str) -> None:
        self.document.save(path)

    def save(self, path: str) -> None:
        self.document.save(path)

class Table:
    rex = re.compile(r"([A-Z]*)([0-9]*)")
    format_float_digits = 4
    name: str=""

    dct: dict[str, Any]
    coords: dict[str, tuple[int, int]]
    _version: int
    _element_table_cache: dict[tuple[str, str, int, int], tuple[tuple[int, tuple[tuple[int, int, Any], ...]], ...]]

    @classmethod
    def str_decrypt(cls, str: str) -> tuple[int, int]:
        result = cls.rex.match(str.upper())
        if result:
            column, row = result.groups()
            column_no = 0
            for i, character in enumerate(column[::-1]):
                column_no += (26**i)*(ord(character)-64)

            row_no = int(row)

            return column_no-1, row_no-1

        raise ValueError

    @classmethod
    def str_encrypt(cls, column: int, row: int) -> str:

        return cls.column_to_char(column + 1) + str(row + 1)

    @classmethod
    def column_to_char(cls, x: int) -> str:
        base = 26
        out = ""
        #x -= 1
        while x:
            out += chr(((x-1) % base)+65)
            x = int((x-1)/base)
        return out[::-1]

    def __init__(self, rows: int=0, columns: int=0, name: str=None):
        self.dct = {}
        self.coords = {}
        self._element_table_cache = {}
        self._version = 0
        self.num_rows = rows
        self.num_columns = columns
        self.name=name or ""
    
    def __json__(self) -> dict[str, Any]:
        return {
            "dct": self.dct
        }
    
    @classmethod
    def __from_json__(cls, dct: dict[str, Any]) -> Table:
        table = cls()
        table.dct = dct
        table.coords = {}

        for key in dct:
            column, row = cls.str_decrypt(key)
            table.coords[key] = (column, row)

            table.num_rows = max(table.num_rows, row+1)
            table.num_columns = max(table.num_columns, column+1)
        
        return table


    def __setitem__(self, key: CellIndex , value: Any) -> None:
        if isinstance(key, tuple):
            row_no, column_no = key
        else:
            column_no, row_no = self.str_decrypt(key)
        self.set_value(column_no, row_no, value)

    def __getitem__(self, item: CellIndex) -> Any:
        if isinstance(item, tuple):
            row_no, column_no = item
            item = self.str_encrypt(column_no, row_no)
        return self.dct.get(item, None)

    def get_columns(self, from_i: int, to_j: int | None) -> Table:
        if to_j is None:
            to_j = self.num_columns
        new_table = self.__class__(self.num_rows, to_j-from_i)

        for key, value in self.dct.items():
            column, row = self.coords[key]
            if from_i <= column < to_j and value is not None:
                new_table.set_value(column-from_i, row, value)
        
        return new_table
    
    def get_rows(self, from_row: int, to_row: int | None) -> Table:
        if to_row is None:
            to_row = self.num_rows
        row_count = to_row - from_row
        new_table = Table(row_count, self.num_columns, name=self.name)

        for key, value in self.dct.items():
            column, row = self.coords[key]
            if from_row <= row < to_row and value is not None:
                new_table.set_value(column, row-from_row, value)
        
        return new_table

    def __isub__(self, other: Table) -> Table:
        import numbers
        for key in other.dct:
            zwei = other[key]

            if key in self.dct:
                eins = self[key]
            else:
                if isinstance(zwei, numbers.Number):
                    eins = 0
                else:
                    eins = ""

            if isinstance(eins, numbers.Number) and isinstance(zwei, numbers.Number):
                self[key] = eins - zwei  # type: ignore
            else:
                self[key] = str(eins) + " - " + str(zwei)

        return self

    def __sub__(self, other: Table) -> Table:
        cpy = copy.deepcopy(self)
        cpy -= other

        return cpy

    def copy(self) -> Table:
        return copy.deepcopy(self)

    def set_value(self, column_no: int, row_no: int, value: Any) -> None:
        self.num_columns = max(column_no+1, self.num_columns)
        self.num_rows = max(row_no+1, self.num_rows)
        key = self.str_encrypt(column_no, row_no)
        self.dct[key] = value
        self.coords[key] = (column_no, row_no)
        self._version += 1
        self._element_table_cache.clear()

    def insert_row(self, row: list[Any], row_no: int | None=None) -> None:
        if row_no is None:
            row_no = self.num_rows
        for i, el in enumerate(row):
            self.set_value(i, row_no, el)

    def get(self, column_no: int, row_no: int) -> Any:
        key = self.str_encrypt(column_no, row_no)
        return self.dct.get(key, None)

    def append_right(self, table: Table, space: int=0) -> None:
        old_column_no = self.num_columns

        for key, value in table.dct.items():
            column_no, row_no = table.coords[key]
            if value is not None:
                self.set_value(old_column_no+column_no+space, row_no, value)

    def append_bottom(self, table: Table, space: int=0) -> None:
        total_rows = self.num_rows
        for key, value in table.dct.items():
            column_no, row_no = table.coords[key]
            if value is not None:
                self.set_value(column_no, total_rows+row_no+space, value)

    @staticmethod
    def _cell_from_value(value: Any) -> OdfdoCell:
        if value is None:
            return OdfdoCell()

        if isinstance(value, bool):
            return OdfdoCell(value=value, cell_type="boolean")

        if isinstance(value, numbers.Integral) and not isinstance(value, bool):
            return OdfdoCell(value=int(value), cell_type="float")

        if isinstance(value, numbers.Real) and not isinstance(value, bool):
            return OdfdoCell(value=float(value), cell_type="float")

        text = str(value)
        return OdfdoCell(value=text, text=text, cell_type="string")

    def get_ods_sheet(self, name: str=None) -> OdfdoTable:
        sheet_name = name or self.name or "table"
        rows = max(1, self.num_rows)
        columns = max(1, self.num_columns)

        sheet = OdfdoTable(name=sheet_name)

        for row_no in range(rows):
            row = OdfdoRow()
            for column_no in range(columns):
                value = self[row_no, column_no]
                row.append(self._cell_from_value(value))
            sheet.append(row)

        return sheet

    @staticmethod
    def _estimate_column_width_cm(char_count: int) -> float:
        # Tuned for LibreOffice Calc default font sizing.
        # Previous calibration was about 1.6x too wide in practice.
        return min(28.0, max(2.0, 0.154 * char_count + 0.55))

    def _column_widths_cm(self, skip_rows_1_based: set[int] | None = None) -> list[float]:
        if self.num_columns <= 0:
            return []

        widths: list[int] = [4] * self.num_columns
        float_str = f"{{:.{self.format_float_digits}f}}"

        for row_no in range(self.num_rows):
            if skip_rows_1_based and (row_no + 1) in skip_rows_1_based:
                continue
            for col_no in range(self.num_columns):
                value = self[row_no, col_no]
                if value is None:
                    continue

                if isinstance(value, float):
                    text = float_str.format(value)
                else:
                    text = str(value)

                longest_line = max(len(line) for line in text.splitlines()) if text else 0
                widths[col_no] = max(widths[col_no], min(longest_line, 120))

        return [self._estimate_column_width_cm(char_count) for char_count in widths]

    @classmethod
    def build_ods_document(
        cls,
        tables: list[Table],
        skip_width_rows: set[int] | None = None,
        skip_width_rows_for_tables: set[str] | None = None,
    ) -> ODSDocument:
        doc = OdfdoDocument("spreadsheet")
        doc.body.clear()
        for table_index, table in enumerate(tables):
            sheet = table.get_ods_sheet()

            apply_skip_rows = skip_width_rows
            if skip_width_rows_for_tables is not None and table.name not in skip_width_rows_for_tables:
                apply_skip_rows = None

            for col_no, width_cm in enumerate(table._column_widths_cm(skip_rows_1_based=apply_skip_rows)):
                style_name = f"co_{table_index}_{col_no}"
                style = OdfdoStyle(family="table-column", name=style_name, width=f"{width_cm:.2f}cm")
                doc.insert_style(style, automatic=True)
                sheet.set_column(col_no, OdfdoColumn(style=style_name))

            doc.body.append(sheet)
        return ODSDocument(doc)

    def save(
        self,
        path: str,
        skip_width_rows: set[int] | None = None,
        skip_width_rows_for_tables: set[str] | None = None,
    ) -> ODSDocument:
        doc = self.__class__.build_ods_document(
            [self],
            skip_width_rows=skip_width_rows,
            skip_width_rows_for_tables=skip_width_rows_for_tables,
        )
        doc.save(path)
        return doc
    
    @classmethod
    def save_tables(
        cls,
        tables: list[Table],
        path: str,
        skip_width_rows: set[int] | None = None,
        skip_width_rows_for_tables: set[str] | None = None,
    ) -> ODSDocument:
        doc = cls.build_ods_document(
            tables,
            skip_width_rows=skip_width_rows,
            skip_width_rows_for_tables=skip_width_rows_for_tables,
        )
        doc.save(path)
        return doc

    @staticmethod
    def _repeat_count(value: Any) -> int:
        if value in (None, ""):
            return 1
        try:
            count = int(value)
            return max(1, count)
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _read_ods_cell_value(cell: Any) -> Any:
        value = getattr(cell, "value", None)

        if isinstance(value, Decimal):
            value = float(value)

        if isinstance(value, float) and value.is_integer():
            return int(value)

        if value not in (None, ""):
            return value

        text_value = getattr(cell, "text", "")
        if isinstance(text_value, str):
            text_value = text_value.strip()
            if text_value:
                return text_value

        return None

    @classmethod
    def load(cls, path: str) -> list[Table]:
        document = OdfdoDocument(path)
        return cls.load_document(document)

    @classmethod
    def load_document(cls, document: OdfdoDocument) -> list[Table]:
        tables: list[Table] = []

        for sheet in document.body.get_sheets():
            table_name = sheet.get_attribute("table:name")
            if isinstance(table_name, str):
                table_name = table_name.strip()
            else:
                table_name = ""
            table = cls(name=table_name)
            row_no = 0

            for node in sheet.get_rows():
                row_repeat = cls._repeat_count(getattr(node, "repeated", None))
                row_values: list[tuple[int, Any]] = []
                col_no = 0

                for cell in node.get_cells():
                    tag = getattr(cell, "tag", None)
                    col_repeat = cls._repeat_count(getattr(cell, "repeated", None))

                    if tag == "table:covered-table-cell":
                        col_no += col_repeat
                        continue

                    value = cls._read_ods_cell_value(cell)
                    if value not in ("", None):
                        for offset in range(col_repeat):
                            row_values.append((col_no + offset, value))

                    col_no += col_repeat

                for row_offset in range(row_repeat):
                    current_row = row_no + row_offset
                    for current_col, value in row_values:
                        table[current_row, current_col] = value

                row_no += row_repeat

            tables.append(table)

        return tables

    @classmethod
    def from_ods_sheet(cls, sheet: Any) -> Table:
        raise NotImplementedError("Use Table.load() for ODS imports")

    @classmethod
    def from_list(cls, lst: list[list[Any]], name: str | None=None) -> Table:
        table = cls(name=name)

        for row_no, row in enumerate(lst):
            for col_no, value in enumerate(row):
                if value not in ("", None):
                    table[row_no, col_no] = value
        
        return table

    @staticmethod
    def _parse_markdown_value(value: str) -> Any:
        value = value.strip()
        if value == "":
            return None
        if value.lower() in {"true", "false"}:
            return value.lower() == "true"
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        if re.fullmatch(r"-?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?", value):
            return float(value)
        return value

    @classmethod
    def loads_markdown(cls, text: str) -> list[Table]:
        tables: list[Table] = []
        current_table: Table | None = None

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("# "):
                continue
            if line.startswith("## "):
                if current_table is not None:
                    tables.append(current_table)
                current_table = cls(name=line[3:].strip())
                continue
            if current_table is None:
                continue
            if not line.startswith("|"):
                continue

            cells = [cls._parse_markdown_value(cell) for cell in line.strip("|").split("|")]
            current_table.insert_row(cells)

        if current_table is not None:
            tables.append(current_table)

        return tables

    @classmethod
    def load_markdown(cls, path: str) -> list[Table]:
        with open(path, encoding="utf-8") as infile:
            return cls.loads_markdown(infile.read())

    def get_markdown_table(self) -> str:
        table = self.copy()
        column_widths = []
        num_columns = table.num_columns
        num_rows = table.num_rows
        float_str = f"{{:.{self.format_float_digits}f}}"

        for column_no in range(num_columns):
            column_width = 0
            for row_no in range(num_rows):
                value = table[row_no, column_no]
                if value is not None:
                    if type(value) is float:
                        str_value = float_str.format(value)
                        table[row_no, column_no] = str_value
                    else:
                        str_value = str(value)
                        table[row_no, column_no] = str_value
                    
                    column_width = max(column_width, len(str_value))
                else:
                    table[row_no, column_no] = ""
            
            column_widths.append(column_width)
        
        text = ""
        for row_no in range(num_rows):
            text += "|"
            for column_no in range(num_columns):
                width = column_widths[column_no]
                value = table[row_no, column_no] or ""

                text += " " * (width - len(value) + 1)
                text += value
                text += " |"
            
            text += "\n"

        return text

    def _repr_html_(self) -> str:
        html = "<table><thead><td></td>"
        for column_no in range(self.num_columns):
            html += f"<td>{self.column_to_char(column_no + 1)}</td>"

        html += "</thead>"
        for row_no in range(self.num_rows):
            html += f"<tr><td>{row_no+1}</td>"
            for column_no in range(self.num_columns):
                ident = self.str_encrypt(column_no, row_no)
                value = self.dct.get(ident, "")
                if isinstance(value, float):
                    value = round(value, self.format_float_digits)
                html += f"<td>{value}</td>"
            html += "</tr>"

        html += "</table>"

        return html

