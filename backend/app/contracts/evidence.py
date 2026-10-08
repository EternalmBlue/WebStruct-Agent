from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.types import ProgramStrategy


class FieldEvidence(BaseModel):
    field_name: str
    source: ProgramStrategy | Literal["verifier", "repair"]
    text: str
    start_char: int | None = None
    end_char: int | None = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)


class EvidenceBundle(BaseModel):
    task_id: str
    evidences: list[FieldEvidence] = Field(default_factory=list)


class VerificationIssue(BaseModel):
    field_name: str
    code: str
    severity: Literal["info", "warning", "error"] = "warning"
    message: str


class VerificationReport(BaseModel):
    task_id: str
    passed: bool
    issues: list[VerificationIssue] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
