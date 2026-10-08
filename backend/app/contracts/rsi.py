from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RSIIterationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    experiment_id: str = Field(min_length=1, max_length=128)
    parent_iteration_id: str | None = Field(default=None, max_length=64)
    baseline_run_id: str = Field(min_length=1, max_length=64)
    candidate_run_id: str = Field(min_length=1, max_length=64)
    hypothesis_id: str = Field(min_length=1, max_length=128)
    hypothesis: str = Field(min_length=1, max_length=1000)
    intervention: str = Field(min_length=1, max_length=1000)
    change_set_id: str = Field(min_length=1, max_length=128)


class RSIIterationResponse(RSIIterationRequest):
    iteration_id: str
    status: Literal["accepted", "rejected", "blocked", "rolled_back"]
    metric_deltas: dict[str, float | None] = Field(default_factory=dict)
    baseline_metrics: dict = Field(default_factory=dict)
    candidate_metrics: dict = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)
    decision_reason: str
    quality_basis: str = "verifier_completion_evidence_proxy_not_gold_accuracy"
    evaluation_version: str = "1"
    created_at: str
    runtime_ms: int
    rollback_reason: str | None = None
    rollback_at: str | None = None


class RSIRollbackRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)
