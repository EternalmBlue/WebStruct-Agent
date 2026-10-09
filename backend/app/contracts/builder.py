from pydantic import BaseModel, Field, model_validator

from app.contracts.api_models import ExtractionResponse
from app.contracts.extraction import FieldExtractionResult
from app.contracts.program import ProgramSpec
from app.contracts.schema import FieldSpec, SchemaSpec
from app.contracts.trace import AgentRunTrace


class SchemaCollaborationRequest(BaseModel):
    task_id: str
    schema_spec: SchemaSpec
    message: str = Field(min_length=1, max_length=4000)


class SchemaCollaborationResponse(BaseModel):
    task_id: str
    schema_spec: SchemaSpec
    agent_traces: list[AgentRunTrace] = Field(default_factory=list)


class ValueCollaborationRequest(BaseModel):
    task_id: str
    field: FieldSpec
    guidance_value: str = Field(default="", max_length=4000)
    evidence_text: str = Field(default="", max_length=8000)


class ValueCollaborationResponse(BaseModel):
    task_id: str
    result: FieldExtractionResult
    program_spec: ProgramSpec
    agent_traces: list[AgentRunTrace] = Field(default_factory=list)
    assistant_message: str = ""


class BuilderCheckRequest(BaseModel):
    task_id: str
    schema_spec: SchemaSpec
    program_spec: ProgramSpec
    expected_values: dict[str, str] = Field(default_factory=dict)
    second_url: str = ""

    @model_validator(mode="after")
    def active_fields_only(self):
        names = [field.name.strip() for field in self.schema_spec.fields]
        if not names or any(not name for name in names) or len(names) != len(set(names)):
            raise ValueError("at least one uniquely named active field is required")
        if any(program.field_name not in names for program in self.program_spec.field_programs):
            raise ValueError("rules must belong to active fields")
        if any(name not in names for name in self.expected_values):
            raise ValueError("expected values must belong to active fields")
        return self


class BuilderCheckResponse(BaseModel):
    extraction: ExtractionResponse
    second_page: ExtractionResponse | None = None
