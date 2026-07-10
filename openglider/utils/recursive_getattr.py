from typing import Any

def recursive_getattr(obj: Any, attr: str) -> Any:
    """
    Recursive Attribute-getter
    """
    if attr == "self":
        return obj
    current = obj
    for part in attr.split('.'):
        current = getattr(current, part)

    return current