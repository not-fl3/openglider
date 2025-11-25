from __future__ import annotations

import abc
import types
import typing
from typing import Any, ClassVar, Generic, Self, TypeVar

from openglider.utils.dataclass import BaseModel
import pydantic


ReturnType = TypeVar("ReturnType")
TupleType = TypeVar("TupleType")

class CellTuple(BaseModel, Generic[TupleType]):
    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid"
        )
    index_offset: ClassVar[tuple[int, int]] = (0, 1)
    first: TupleType
    second: TupleType

    def __getitem__(self, index: int) -> TupleType:
        if index == 0:
            return self.first
        elif index == 1:
            return self.second
        
        raise ValueError(f"invalid index: {index}")

    
    @classmethod
    def from_value(cls, value: TupleType) -> Self:
        return cls(first=value, second=value)

    @pydantic.model_validator(mode="before")
    @classmethod
    def _validate(cls, v: Any) -> dict[str, Any] | Self:
        if isinstance(v, tuple):
            v_tuple = typing.cast(tuple[Any, Any], v)
            if len(v_tuple) == 2:
                return {
                    "first": v_tuple[0],
                    "second": v_tuple[1]
                }
        return {
            "first": v,
            "second": v
        }
class SingleCellTuple(CellTuple[TupleType], Generic[TupleType]):
    index_offset: ClassVar[tuple[int, int]] = (0, 0)


_type_cache: dict[type[DTO[Any]], list[tuple[str, str]]] = {}

class DTO(BaseModel, Generic[ReturnType], abc.ABC):
    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid"
        )
    _types: list[tuple[str, str]] | None = None

    def get_object(self) -> ReturnType:

        raise NotImplementedError
    
    @staticmethod
    def _get_type_string(type_: type | types.UnionType | None) -> str:
        assert type_ is not None

        if isinstance(type_, types.UnionType):
            names: list[str] = []
            for subtype in typing.get_args(type_):
                names.append(subtype.__name__)
            
            return " | ".join(names)
        elif typing.get_origin(type_) == typing.Literal:
            args = [
                f"'{x}'" if isinstance(x, str) else x
                for x in
                typing.get_args(type_)
            ]
            
            return " | ".join(args)
        else:
            return type_.__name__
    
    @staticmethod
    def check_is_cell_tuple(type_: Any) -> type[CellTuple[Any]] | None:
        try:
            if isinstance(type_, type) and issubclass(type_, CellTuple):
                return typing.cast(type[CellTuple[Any]], type_)
        except TypeError:
            pass

        return None

    @classmethod
    def describe(cls) -> list[tuple[str, str]]:
        if cls not in _type_cache:
            result: list[tuple[str, str]] = []
            for field_name, field in cls.model_fields.items():
                is_cell_tuple = cls.check_is_cell_tuple(field.annotation)

                if is_cell_tuple:
                    inner_type = is_cell_tuple.model_fields["first"].annotation
                    inner_type_str = cls._get_type_string(inner_type)

                    if sum(is_cell_tuple.index_offset) > 0:
                        for side in is_cell_tuple.index_offset:
                            result.append((f"{field_name} ({side+1})", inner_type_str))
                    else:
                        result.append((f"{field_name}", inner_type_str))
                
                else:
                    result.append((field_name, cls._get_type_string(field.annotation)))

            _type_cache[cls] = result

        return _type_cache[cls]
    
    @classmethod
    def describe_text(cls) -> str:
        result = ""
        for index, (field_name, field_type) in enumerate(cls.describe()):
            result += f" {index+1: 2d}: {field_name}  ({field_type})\n"

        return result

        
    @classmethod
    def column_length(cls) -> int:
        return len(cls.describe())
