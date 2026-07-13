from typing import Any

import qtawesome

def icon(name: str, *args: object, **kwargs: object) -> Any:
    if name.startswith("fa."):
        name = name.replace("fa.", "fa5s.", 1)
    return qtawesome.icon(name, *args, **kwargs)
