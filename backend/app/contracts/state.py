from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from app.contracts.benchmark import BenchmarkDataset, BenchmarkReport
from app.contracts.evidence import EvidenceBundle, VerificationReport
from app.contracts.extraction import ExtractionPlan, ExtractionResult
from app.contracts.page import PageObservation, ViewBundle
from app.contracts.program import ProgramSpec
from app.contracts.schema import SchemaSpec
from app.contracts.trace import AgentRunTrace


class GraphRunState(TypedDict, total=False):
    task_id: str
    schema_name: str
    schema_spec: SchemaSpec | None
    force_builtin_schema: bool
    schema_version: dict[str, Any]
    schema_generation_mode: str
    schema_generation_error: str | None
    target_url: str
    seed_urls: list[str]
    input_html: str
    persist_result: bool
    program_spec_mode: str
    provided_program_spec: ProgramSpec | None
    reuse_verified_program: bool
    enable_field_repair: bool
    allow_execution_fallback: bool
    page_observation: PageObservation
    view_bundle: ViewBundle
    extraction_plan: ExtractionPlan
    program_spec: ProgramSpec
    program_reused: bool
    program_generation_mode: str
    program_generation_error: str | None
    extraction_result: ExtractionResult
    evidence_bundle: EvidenceBundle
    verification_report: VerificationReport
    repair_attempts: int
    benchmark_config: dict[str, Any]
    benchmark_dataset: BenchmarkDataset
    benchmark_runs: dict[str, Any]
    benchmark_report: BenchmarkReport
    agent_traces: Annotated[list[AgentRunTrace], operator.add]
    errors: Annotated[list[str], operator.add]
    status: str
