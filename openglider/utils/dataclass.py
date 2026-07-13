from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, TypeVar, dataclass_transform
from collections.abc import Callable
import openglider.rs
import weakref

import pydantic
from pydantic import PrivateAttr, model_validator

#from pydantic import Field as field
from pydantic import ConfigDict, Field  # export Field

from dataclasses import dataclass as dc, replace

from openglider.utils.cache import CachedProperty, hash_list

if TYPE_CHECKING:
    from pydantic.dataclasses import Dataclass

    OGDataclassT = TypeVar("OGDataclassT", bound="OGDataclass")
    class OGDataclass(Dataclass):
        def __json__(self: OGDataclassT) -> dict[str, Any]:
            pass

        def copy(self: OGDataclassT) -> OGDataclassT:
            pass

        def __hash__(self: OGDataclassT) -> int:
            pass


class Config:
    arbitrary_types_allowed = True
    #post_init_call = 'after_validation'

@dataclass_transform(kw_only_default=False)
def dataclass(_cls: type[Any]) -> type[OGDataclassT]:

    if TYPE_CHECKING:
        _cls_new = dc(_cls)
    else:
        _cls_new = pydantic.dataclasses.dataclass(config=Config, kw_only=False)(_cls)
        
    old_json = getattr(_cls, "__json__", None)
    if old_json is None or getattr(old_json, "is_auto", False):
        def __json__(instance: Any) -> dict[str, Any]:
            return {
                key: getattr(instance, key) for key in _cls_new.__dataclass_fields__
            }
        
        setattr(__json__, "is_auto", True)

        _cls.__json__ = __json__

    old_copy = getattr(_cls, "copy", None)
    if old_copy is None or getattr(old_copy, "is_auto", False):
        def copy(instance: Any) -> Any:
            return  replace(instance)
        
        setattr(copy, "is_auto", True)

        _cls.copy = copy
    
    old_hash = getattr(_cls, "__hash__", None)
    if old_hash is None or getattr(old_hash, "is_auto", False):
        # don't shadow hash (internal python name)
        def _hash(instance: Any) -> int:
            try:
                lst = [getattr(instance, key) for key in _cls_new.__dataclass_fields__]
                return hash_list(lst)
            except Exception as e:
                raise ValueError(f"invalid elem: {instance}") from e

        
        setattr(_hash, "is_auto", True)

        _cls.__hash__ = _hash  # type: ignore

        
    return _cls_new


# https://github.com/pydantic/pydantic/issues/501
def get_validator(cls: type) -> Callable[[Any], Any]:
    def validator(v: Any) -> Any:
        if isinstance(v, (list, tuple)):
            return cls(v)
        if isinstance(v, cls):
            return v
        raise ValueError(f"Cannot convert value to Vector3D: {v}")
    
    return validator

#pydantic.validators._VALIDATORS += [
#    (openglider.rs.vector.Vector3D, [get_validator(openglider.rs.vector.Vector3D)]),
#    (openglider.rs.vector.Vector2D, [get_validator(openglider.rs.vector.Vector2D)])
#]

class BaseModel(pydantic.BaseModel):
    cache_versioned: ClassVar[bool] = False
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        ignored_types=(CachedProperty,),
        extra="forbid"
        )

    _cache_version: int = PrivateAttr(default=0)
    _cache_ready: bool = PrivateAttr(default=False)
    _cache_parents: list[weakref.ReferenceType[BaseModel]] = PrivateAttr(default_factory=list)
    _cache_missing = object()
    
    def __eq__(self, other: Any) -> bool:
        return other.__class__ == self.__class__ and self.__dict__ == other.__dict__

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "_cache_ready", True)
        for field_name in self.model_fields:
            self._cache_link_value(getattr(self, field_name))

    def touch(self, propagate: bool=True) -> None:
        if self.cache_versioned:
            object.__setattr__(self, "_cache_version", self._cache_version + 1)

            if propagate:
                for parent_ref in list(self._cache_parents):
                    parent = parent_ref()
                    if parent is None:
                        self._cache_parents.remove(parent_ref)
                    else:
                        parent.touch(propagate=True)

    def _cache_add_parent(self, parent: BaseModel) -> None:
        if not self.cache_versioned:
            return

        for parent_ref in self._cache_parents:
            if parent_ref() is parent:
                return

        self._cache_parents.append(weakref.ref(parent))

    def _cache_remove_parent(self, parent: BaseModel) -> None:
        self._cache_parents = [parent_ref for parent_ref in self._cache_parents if parent_ref() is not None and parent_ref() is not parent]

    def _cache_iter_child_models(self, value: Any):
        if isinstance(value, BaseModel):
            yield value
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from self._cache_iter_child_models(item)

    def _cache_link_value(self, value: Any) -> None:
        if not self.cache_versioned:
            return

        for child in self._cache_iter_child_models(value):
            child._cache_add_parent(self)

    def _cache_unlink_value(self, value: Any) -> None:
        if not self.cache_versioned:
            return

        for child in self._cache_iter_child_models(value):
            child._cache_remove_parent(self)

    def __setattr__(self, name: str, value: Any) -> None:
        old_value = self._cache_missing
        if self._cache_ready and name in self.model_fields:
            old_value = getattr(self, name, self._cache_missing)
        super().__setattr__(name, value)

        if self._cache_ready and self.cache_versioned and name in self.model_fields:
            if old_value is not self._cache_missing:
                self._cache_unlink_value(old_value)
            self._cache_link_value(value)
            self.touch(propagate=True)

    def __json__(self) -> dict[str, Any]:
        return self.model_dump()

    def __hash__(self) -> int:
        if self.cache_versioned:
            return hash((self.__class__, id(self), self._cache_version))

        return hash_list(*self.dict().values())
    
    @model_validator(mode="before")
    @classmethod
    def validate_basemodel(cls, data: dict[str, Any]) -> dict[str, Any]:
        # TODO: this is an ugly hack
        evaluated_types = (
            openglider.rs.vector.Vector3D,
            openglider.rs.vector.Vector2D,
        )

        for field_name, field in cls.model_fields.items():
            if field.annotation in evaluated_types:
                value = data.get(field_name, None)
                if value is not None and type(value) != field.annotation:
                    data[field_name] = field.annotation(value)
        
        return data
