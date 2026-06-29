from typing import Any

from pydantic import BaseModel, Field


class BenchmarkItem(BaseModel):
    item_id: str
    url: str = ""
    html: str
    schema_name: str = "高校通知"
    gold_record: dict[str, Any] = Field(default_factory=dict)


class BenchmarkDataset(BaseModel):
    name: str = "内置演示数据集"
    items: list[BenchmarkItem]


class BenchmarkMethodResult(BaseModel):
    method: str
    field_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    required_field_missing_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    schema_adherence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_precision: float = Field(default=0.0, ge=0.0, le=1.0)
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_token_cost: int = Field(default=0, ge=0)
    runtime_ms: int = Field(default=0, ge=0)
    program_reuse_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    selective_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    repair_success_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class BenchmarkReport(BaseModel):
    task_id: str
    dataset_name: str
    methods: list[BenchmarkMethodResult]
    summary: str
