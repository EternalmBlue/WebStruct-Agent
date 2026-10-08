from app.contracts import SchemaSpec

DEFAULT_SCHEMA_NAME = ""


def get_builtin_schemas() -> dict[str, SchemaSpec]:
    return {}


def get_builtin_schema(name: str) -> SchemaSpec:
    raise LookupError("系统内置领域 Schema 已移除，请提供明确的 SchemaSpec")
