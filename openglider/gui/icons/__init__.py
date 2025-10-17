import qtawesome

def icon(name, *args, **kwargs):
    if name.startswith("fa."):
        name = name.replace("fa.", "fa5s.", 1)
    return qtawesome.icon(name, *args, **kwargs)
