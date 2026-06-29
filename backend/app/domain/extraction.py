from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.evidence import FieldEvidence
from app.domain.types import FieldType, ProgramStrategy


class FieldExtractionPlan(BaseModel):
    field_name: str
    field_type: FieldType = "string"
    labels: list[str] = Field(default_factory=list)
    strategies: list[ProgramStrategy] = Field(default_factory=list)
    required: bool = True


class ExtractionPlan(BaseModel):
    schema_name: str
    field_plans: list[FieldExtractionPlan]


class FieldExtractionResult(BaseModel):
    field_name: str
    value: Any = None
    normalized_value: Any = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[FieldEvidence] = Field(default_factory=list)
    strategy: ProgramStrategy | Literal["none"] = "none"
    status: Literal["extracted", "missing", "repaired", "fallback_failed"] = "missing"
    error_message: str | None = None


class ExtractionResult(BaseModel):
    task_id: str
    schema_name: str
    fields: list[FieldExtractionResult]
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    def get_field(self, field_name: str) -> FieldExtractionResult | None:
        return next(
            (field for field in self.fields if field.field_name == field_name),
            None,
        )
