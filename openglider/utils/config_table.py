from __future__ import annotations

from typing import Any, ClassVar, Self

import openglider.rs
import pydantic

from openglider.utils.dataclass import BaseModel
from openglider.utils.table import Table
from openglider.vector import unit


adapters: dict[type, Any] = {}


def get_adapter(cls: type) -> Any:
    if cls not in adapters:
        try:
            adapter: Any = pydantic.TypeAdapter(cls).validate_python
        except pydantic.errors.PydanticSchemaGenerationError:
            adapter = cls

        adapters[cls] = adapter

    return adapters[cls]


class ConfigTable(BaseModel):
    table_name: ClassVar[str] = "Data"

    @classmethod
    def _migrate_table(cls, data: dict[str, list[Any]]) -> dict[str, list[Any]]:
        return data

    @classmethod
    def read_table(cls, table: Table) -> Self:
        raw_data: dict[str, list[Any]] = {}
        for current_row in range(1, table.num_rows):
            key_raw = table[current_row, 0]
            if key_raw is None:
                continue

            key = str(key_raw).strip().lower()
            if not key:
                continue

            raw_data[key] = [table[current_row, i] for i in range(1, table.num_columns)]

        raw_data = cls._migrate_table(raw_data)
        data = {}

        for key, value in raw_data.items():
            if key not in cls.model_fields or not value:
                continue

            target_type = cls.model_fields[key].annotation
            assert target_type is not None

            adapter = get_adapter(target_type)  # type: ignore[arg-type]
            data_length = 3 if target_type == openglider.rs.vector.Vector3D else 1

            try:
                data[key] = adapter(value if data_length > 1 else value[0])
            except pydantic.ValidationError as error:
                if value[0] is None:
                    continue
                raise error

        return cls(**data)

    def _serialize_table_value(self, key: str, value: Any) -> list[Any]:
        if isinstance(value, openglider.rs.vector.Vector3D):
            return list(value)
        if isinstance(value, unit.Quantity):
            return [str(value)]
        return [value]

    def _get_table_headers(self) -> tuple[str, str]:
        return ("Key", "Values")

    def _get_default_excluded_export_fields(self) -> set[str]:
        return set()

    def _get_default_export_extra_rows(self) -> list[tuple[str, list[Any]]]:
        return []

    def get_table(
        self,
        *,
        exclude_fields: set[str] | None = None,
        extra_rows: list[tuple[str, list[Any] | Any]] | None = None,
    ) -> Table:
        table = Table(name=self.table_name)
        header_key, header_value = self._get_table_headers()
        table[0, 0] = header_key
        table[0, 1] = header_value

        excluded = self._get_default_excluded_export_fields()
        if exclude_fields:
            excluded.update(exclude_fields)

        row = 1
        for key, value in self:
            if key in excluded:
                continue

            values = self._serialize_table_value(key, value)

            table[row, 0] = key
            for column, column_value in enumerate(values):
                table[row, column + 1] = column_value
            row += 1

        rows = self._get_default_export_extra_rows()
        if extra_rows:
            for key, value in extra_rows:
                if isinstance(value, list):
                    rows.append((key, value))
                else:
                    rows.append((key, [value]))

        for key, values in rows:
            table[row, 0] = key
            for column, column_value in enumerate(values):
                table[row, column + 1] = column_value
            row += 1

        return table
