from pydantic import BaseModel, Field

from app.contracts.types import PostprocessFunction, ProgramStrategy


class FieldProgramSpec(BaseModel):
    field_name: str
    strategy: ProgramStrategy
    enabled: bool = True
    selector: str | None = None
    pattern: str | None = None
    label: str | None = None
    labels: list[str] = Field(default_factory=list)
    postprocess: list[PostprocessFunction] = Field(default_factory=list)


class ProgramSpec(BaseModel):
    version: str = "0.1"
    safety_mode: str = "dsl"
    field_programs: list[FieldProgramSpec]
