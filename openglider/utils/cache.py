from __future__ import annotations
import collections

import copy
import functools
import logging
from typing import Generic, TypeVar, Any, overload
from collections.abc import Callable, Iterator, Sequence

from typing import TYPE_CHECKING

from openglider.utils.recursive_getattr import recursive_getattr
from openglider.config import config


logger = logging.getLogger(__name__)

cache_instances: list[Any] = []

def clear() -> None:
    for instance in cache_instances:
        instance.cache.cache.clear()

def stats() -> list[tuple[str, int, int]]:
    return [
        (instance.__qualname__, instance.cache.hits, instance.cache.misses) for instance in cache_instances
    ]


class CachedObject:
    """
    An object to provide cached properties and functions.
    Provide a list of attributes to hash down for tracking changes
    """
    name: str = "unnamed"
    hashlist: list[str] = []

    def __hash__(self) -> int:
        return hash_attributes(self, self.hashlist)

    def __repr__(self) -> str:
        rep = super().__repr__()
        if hasattr(self, "name"):
            rep = rep[:-1] + f': "{self.name}">'
        return rep



CLS = TypeVar("CLS")
SelfT = TypeVar("SelfT")
ResultT = TypeVar("ResultT")

class LruCache(Generic[ResultT]):
    NotFound = object()
    
    def __init__(self, maxsize: int=128) -> None:
        self.maxsize = maxsize
        self.cache: collections.OrderedDict[int, ResultT] = collections.OrderedDict()

        self.hits = 0
        self.misses = 0
    
    @property
    def cache_full(self) -> bool:
        return len(self.cache) > self.maxsize
    
    def get(self, key: int) -> ResultT | None:
        try:
            value = self.cache.pop(key)
            self.cache[key] = value
            self.hits += 1
            return value
        except KeyError:
            self.misses += 1
            return None
    
    def set(self, key: int, value: ResultT) -> None:
        try:
            self.cache.pop(key)
        except KeyError:
            pass

        for _ in range(len(self.cache) - self.maxsize):
            self.cache.popitem(last=False)

        self.cache[key] = value
            

class CachedProperty(Generic[SelfT, ResultT]):
    hashlist: list[str]

    def __init__(self, fget: Callable[[SelfT], ResultT], hashlist: Sequence[str], maxsize: int):
        super().__init__()
        self.function = fget
        self.__doc__ = fget.__doc__
        self.__module__ = fget.__module__
        self.__name__ = fget.__name__
        self.__qualname__ = fget.__qualname__

        self.hashlist = list(hashlist)
        self.cache: LruCache[ResultT] = LruCache(maxsize)

        global cache_instances
        cache_instances.append(self)
    
    def __repr__(self) -> str:
        return f"<CachedProperty {self.function.__qualname__}>"

    @overload
    def __get__(self, parentclass: None, type: type[SelfT] | None=None) -> CachedProperty[SelfT, ResultT]:
        pass

    @overload
    def __get__(self, parentclass: SelfT, type: type[SelfT] | None=None) -> ResultT:
        pass

    def __get__(self, parentclass: SelfT | None, type: type[SelfT] | None=None) -> ResultT | CachedProperty[SelfT, ResultT]:
        if parentclass is None:
            return self

        if not config["caching"]:
            return self.function(parentclass)
        
        hash_value = hash_attributes(parentclass, self.hashlist)
        value = self.cache.get(hash_value)

        if value is None:
            value = self.function(parentclass)
            self.cache.set(hash_value, value)            
        
        return value


def cached_property(*hashlist: str, max_size: int=1024) -> Callable[[Callable[[SelfT], ResultT]], CachedProperty[SelfT, ResultT]]:
    def property_decorator(fget: Callable[[SelfT], ResultT]) -> CachedProperty[SelfT, ResultT]:
        return CachedProperty(fget, hashlist, max_size)
    
    return property_decorator


F = TypeVar("F")

def cached_function(*hashlist: str, exclude: list[str | None]=None, generator: Callable[[Any], Sequence[Any]]=None, max_size: int=1024) -> Callable[[F], F]:
    if TYPE_CHECKING:
        @functools.wraps
        def wrapper(f: F) -> F:
            return f
        
        return wrapper  # type: ignore
    
    else:
        def wrapper(getter):
            cache = LruCache(max_size)

            @functools.wraps(getter)
            def new_function(self, *args, **kwargs):
                cls_hash = hash_attributes(self, hashlist, exclude, generator)
                hashvalue = hash_list(cls_hash, *args, *kwargs.values())

                value = cache.get(hashvalue)
                if value is None or not config.caching:
                    value = getter(self, *args, **kwargs)
                    cache.set(hashvalue, value)
                
                return value
            
            new_function.cache = cache
            global cache_instances
            cache_instances.append(new_function)

            return new_function
                

        return wrapper

def c_mul(a: float, b: int) -> int:
    """
    C type multiplication
    http://stackoverflow.com/questions/6008026/how-hash-is-implemented-in-python-3-2
    """
    return eval(hex((int(a) * b) & 0xFFFFFFFF)[:-1])

def hash_value(value: Any) -> int:
    try:
        return hash(value)
    except TypeError:  # Lists p.e.
        logger.debug(f"bad hash value: {value}")
        #logger.debug(f"bad cache: {type(class_instance)} -> {attribute}, {type(value)} {type(value)}")
        try:
            return hash(frozenset(value))
        except TypeError:
            return hash(str(value))


def hash_attributes(class_instance: CLS, hashlist: list[str], exclude: list[str] | None=None, generator: Callable[[CLS], Iterator[Any]]=None) -> int:
    """
    http://effbot.org/zone/python-hash.htm
    """
    value_lst: tuple[int,...] = (id(class_instance), )

    if len(hashlist) == 1 and hashlist[0] in ("self", "*") and exclude is not None:
        for key, value in class_instance.__dict__.items():
            if key not in exclude:
                value_lst += (hash_value(value), )
    else:
        for attribute in hashlist:
            el = recursive_getattr(class_instance, attribute)
            value_lst += (hash_value(el), )

    if generator is not None:
        for el in generator(class_instance):
            value_lst += (hash_value(el), )

    return hash(value_lst)


def hash_list(*lst: Any) -> int:
    value_lst: list[int] = []
    for el in lst:

        try:
            value_lst.append(hash(el))
        except TypeError:  # Lists p.e.
            #logging.warning(f"bad cache: {el}")
            try:
                value_lst.append(hash(frozenset(el)))
            except TypeError:
                value_lst.append(hash(str(el)))

    return hash(tuple(value_lst))



T = TypeVar('T')

class HashedList(Generic[T]):
    """
    Hashed List to use cached properties
    """
    _hash: int | None
    name = "unnamed"
    def __init__(self, data: list[T], name: str="unnamed"):
        self._data: list[T] = []
        self._hash = None
        self.data = data
        self.name = name

    def __json__(self) -> dict[str, Any]:
        # attrs = self.__init__.func_code.co_varnames
        # return {key: getattr(self, key) for key in attrs if key != 'self'}
        return {"data": self.data, "name": self.name}

    def __getitem__(self, item: int) -> T:
        return self.data[item]

    def __setitem__(self, key: int, value: T) -> None:
        self.data[key] = value
        self._hash = None

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(str(self.data))
            #self._hash = hash("{}/{}".format(id(self), time.time()))
        return self._hash

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self) -> Iterator[T]:
        yield from self.data

    def __str__(self) -> str:
        return str(self.data)

    def __repr__(self) -> str:
        return f"<class '{self.__class__}' name: {self.name}"

    @property
    def data(self) -> list[T]:
        return self._data

    @data.setter
    def data(self, data: list[T]) -> None:
        if data is not None:
            self._data = data
            self._hash = None
        else:
            self._data = []

    def copy(self) -> HashedList[T]:
        return copy.deepcopy(self)