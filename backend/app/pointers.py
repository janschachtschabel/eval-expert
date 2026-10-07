"""JSON Pointer helpers; mappings never execute user code."""

MISSING = object()


def get_pointer(value, path, default=MISSING):
    if path == "":
        return value
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("Paths must be JSON Pointers starting with /.")
    try:
        for token in path[1:].split("/"):
            key = token.replace("~1", "/").replace("~0", "~")
            value = value[int(key)] if isinstance(value, list) else value[key]
        return value
    except (KeyError, IndexError, TypeError, ValueError):
        return default


def render_mapping(template, source):
    """Only an object containing exactly $input is an input substitution."""
    if isinstance(template, dict):
        if set(template) == {"$input"}:
            value = get_pointer(source, template["$input"])
            if value is MISSING:
                raise ValueError(f"Missing input: {template['$input']}")
            return value
        return {key: render_mapping(value, source) for key, value in template.items()}
    if isinstance(template, list):
        return [render_mapping(value, source) for value in template]
    return template
