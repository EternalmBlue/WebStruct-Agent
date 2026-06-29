from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.domain import SchemaSpec
from app.extraction.schema_catalog import get_builtin_schemas
from app.storage.schema_repository import get_schema_versions, persist_schema_version

router = APIRouter(prefix="/schemas", tags=["schemas"])


class SchemaValidationResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    schema_spec: SchemaSpec | None = None
    schema_version: dict[str, object] | None = None


@router.get("", response_model=list[SchemaSpec])
def list_schemas() -> list[SchemaSpec]:
    return list(get_builtin_schemas().values())


@router.get("/versions")
def list_schema_versions(schema_name: str | None = None) -> list[dict[str, object]]:
    return get_schema_versions(schema_name=schema_name)


@router.post("/validate", response_model=SchemaValidationResponse)
def validate_schema(schema_spec: SchemaSpec) -> SchemaValidationResponse:
    errors: list[str] = []
    if not schema_spec.fields:
        errors.append("schema must contain at least one field")
    for field in schema_spec.fields:
        if not field.name.strip():
            errors.append("field name must not be empty")
        if field.required and not field.description.strip():
            errors.append(f"required field '{field.name}' should include a description")
        if field.type == "date" and not any(
            keyword in (field.description + " ".join(field.aliases))
            for keyword in ("日期", "时间", "date")
        ):
            errors.append(f"date field '{field.name}' should include date/time semantics")
    return SchemaValidationResponse(
        valid=not errors,
        errors=errors,
        schema_spec=schema_spec,
        schema_version=persist_schema_version(schema_spec=schema_spec, source="validation")
        if not errors
        else None,
    )
