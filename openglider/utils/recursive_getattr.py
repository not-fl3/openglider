from typing import Any

def recursive_getattr(obj: Any, attr: str) -> Any:
    """
    Recursive Attribute-getter
    """
    if attr == "self":
        return obj
    elif '.' not in attr:
        return getattr(obj, attr)
    else:
        l = attr.split('.')
        return recursive_getattr(getattr(obj, l[0]), '.'.join(l[1:]))