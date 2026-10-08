from typing import Any

from pydantic import BaseModel, Field

from app.contracts.schema import SchemaSpec


class BenchmarkItem(BaseModel):
    item_id: str
    url: str = ""
    html: str
    schema_name: str = ""
    schema_spec: SchemaSpec | None = None
    gold_record: dict[str, Any] = Field(default_factory=dict)


class BenchmarkDataset(BaseModel):
    name: str = "显式输入评测数据集"
    items: list[BenchmarkItem]


class BenchmarkMethodResult(BaseModel):
    method: str
    field_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    required_field_missing_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    schema_adherence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_precision: float | None = Field(default=None, ge=0.0, le=1.0)
    average_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    estimated_token_cost: int | None = Field(default=None, ge=0)
    runtime_ms: int | None = Field(default=None, ge=0)
    program_reuse_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    selective_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    repair_success_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    actual_input_tokens: int | None = Field(default=None, ge=0)
    actual_output_tokens: int | None = Field(default=None, ge=0)
    partial_actual_input_tokens: int = Field(default=0, ge=0)
    partial_actual_output_tokens: int = Field(default=0, ge=0)
    token_usage_missing_calls: int = 0
    evidence_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    sample_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    accepted_field_count: int = 0
    model_call_count: int = 0
    sample_errors: dict[str, list[str]] = Field(default_factory=dict)
    metric_sources: dict[str, str] = Field(default_factory=dict)
    unavailable_reasons: dict[str, str] = Field(default_factory=dict)


class BenchmarkReport(BaseModel):
    task_id: str
    dataset_name: str
    methods: list[BenchmarkMethodResult]
    summary: str
    experiment_settings: dict[str, Any] = Field(default_factory=dict)


class MetricEnvelope(BaseModel):
    value: float | int | None = None
    source: str
    unit: str = ""
    sample_count: int = 0
    reason: str | None = None
