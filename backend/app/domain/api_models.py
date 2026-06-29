from typing import Literal

from pydantic import BaseModel, Field

from app.domain.benchmark import BenchmarkDataset, BenchmarkReport
from app.domain.evidence import EvidenceBundle, VerificationReport
from app.domain.extraction import ExtractionPlan, ExtractionResult
from app.domain.page import PageObservation, ViewBundle
from app.domain.program import ProgramSpec
from app.domain.schema import SchemaSpec
from app.domain.trace import AgentRunTrace


class ExtractionRequest(BaseModel):
    target_url: str = ""
    html: str | None = None
    schema_name: str = "高校通知"
    schema_spec: SchemaSpec | None = None
    program_spec: ProgramSpec | None = None
    force_builtin_schema: bool = False
    program_spec_mode: Literal["create", "run_verified"] = "create"
    persist_result: bool = True
    reuse_verified_program: bool = False


class ExtractionResponse(BaseModel):
    task_id: str
    status: str
    schema_spec: SchemaSpec
    schema_version: dict[str, object] | None = None
    schema_generation_mode: str = "unknown"
    schema_generation_error: str | None = None
    page_observation: PageObservation | None = None
    view_bundle: ViewBundle | None = None
    extraction_plan: ExtractionPlan | None = None
    program_spec: ProgramSpec | None = None
    program_reused: bool = False
    program_generation_mode: str = "unknown"
    program_generation_error: str | None = None
    extraction_result: ExtractionResult | None = None
    evidence_bundle: EvidenceBundle | None = None
    verification_report: VerificationReport | None = None
    repair_attempts: int = 0
    agent_traces: list[AgentRunTrace] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class BenchmarkRequest(BaseModel):
    schema_name: str = "高校通知"
    dataset: BenchmarkDataset | None = None


class BenchmarkResponse(BaseModel):
    task_id: str
    status: str
    benchmark_report: BenchmarkReport | None = None
    agent_traces: list[AgentRunTrace] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ManualReviewField(BaseModel):
    field_name: str
    value: str = ""
    accepted: bool = True
    note: str = ""


class ManualReviewRequest(BaseModel):
    task_id: str
    schema_spec: SchemaSpec
    program_spec: ProgramSpec | None = None
    fields: list[ManualReviewField] = Field(default_factory=list)
    mark_program_verified: bool = False
    rule_name: str = ""


class ManualReviewResponse(BaseModel):
    task_id: str
    status: str = "reviewed"
    program_verified: bool = False
    field_count: int = 0


class SpecAssistantRequest(BaseModel):
    task_id: str
    message: str
    schema_spec: SchemaSpec
    program_spec: ProgramSpec | None = None


class SpecAssistantResponse(BaseModel):
    task_id: str
    assistant_message: str
    schema_spec: SchemaSpec
    program_spec: ProgramSpec
    change_summary: list[str] = Field(default_factory=list)
    validation_issues: list[str] = Field(default_factory=list)
