from jsonschema.validators import validator_for


def check_schema(schema):
    """Only local JSON Schema references are supported in configured response schemas."""

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("$ref", "$dynamicRef") and (
                    not isinstance(item, str) or not item.startswith("#")
                ):
                    raise ValueError("Response schema references must be local (#...).")
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(schema)
    validator_for(schema).check_schema(schema)
    return schema
