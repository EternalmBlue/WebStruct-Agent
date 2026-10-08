"""模式中心对外 HTTP 接口：用户/模型 Schema 列表、版本查询与 Schema 校验。

行为契约：specs/features/schema-center.feature
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.contracts import SchemaSpec
from app.features.schema_center.repository import get_schema_versions, persist_schema_version
from app.features.schema_center.validation import validate_schema_spec

router = APIRouter(prefix="/schemas", tags=["schemas"])


class SchemaValidationResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    schema_spec: SchemaSpec | None = None
    schema_version: dict[str, object] | None = None


@router.get("")
def list_schemas() -> list[dict[str, object]]:
    persisted = get_schema_versions()
    return [
        {
            **SchemaSpec.model_validate(item["schema_spec"]).model_dump(mode="json"),
            "source": item["source"],
            "version": item["version"],
            "schema_signature": item["schema_signature"],
        }
        for item in persisted
        if item.get("source") not in {"builtin", "system"}
    ]


@router.get("/versions")
def list_schema_versions(schema_name: str | None = None) -> list[dict[str, object]]:
    return get_schema_versions(schema_name=schema_name)


@router.post("/validate", response_model=SchemaValidationResponse)
def validate_schema(schema_spec: SchemaSpec) -> SchemaValidationResponse:
    errors = validate_schema_spec(schema_spec)
    return SchemaValidationResponse(
        valid=not errors,
        errors=errors,
        schema_spec=schema_spec,
        schema_version=persist_schema_version(schema_spec=schema_spec, source="user")
        if not errors
        else None,
    )
