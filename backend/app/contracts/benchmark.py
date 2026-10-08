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
    metric_sources: dict[str, str] = Field(default_factory=dict)
    unavailable_reasons: dict[str, str] = Field(default_factory=dict)


class BenchmarkReport(BaseModel):
    task_id: str
    dataset_name: str
    methods: list[BenchmarkMethodResult]
    summary: str
