from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PageIntent = Literal["single_resource", "article", "list", "home", "unknown"]
CompatibilityStatus = Literal["compatible", "incompatible", "unknown"]


class PageIntentAssessment(BaseModel):
    intent: PageIntent
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    gate_passed: bool = True
    signals: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    repeated_item_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    visible_text_chars: int = Field(default=0, ge=0)


class BodyQualityMetrics(BaseModel):
    visible_text_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    block_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    continuity_score: float | None = Field(default=None, ge=0.0, le=1.0)
    noise_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    candidate_count: int = Field(default=0, ge=0)
    merged_candidate_count: int = Field(default=0, ge=0)


class BodyCandidate(BaseModel):
    selector: str | None = None
    xpath: str | None = None
    text: str = ""
    score: float = Field(default=0.0, ge=0.0)
    block_count: int = Field(default=0, ge=0)
    document_order: int = Field(default=0, ge=0)


class BodySelection(BaseModel):
    accepted: bool = False
    text: str = ""
    candidates: list[BodyCandidate] = Field(default_factory=list)
    metrics: BodyQualityMetrics = Field(default_factory=BodyQualityMetrics)
    rejected_reasons: list[str] = Field(default_factory=list)


class PageStructureSignature(BaseModel):
    signature_version: str = "1"
    page_intent: PageIntent
    title_shape: list[str] = Field(default_factory=list)
    content_shape: list[str] = Field(default_factory=list)
    heading_count: int = Field(default=0, ge=0)
    text_block_count: int = Field(default=0, ge=0)
    repeated_item_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    selector_match_counts: dict[str, int] = Field(default_factory=dict)
    body_visible_text_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    body_continuity_score: float | None = Field(default=None, ge=0.0, le=1.0)
    body_noise_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class StructureCompatibility(BaseModel):
    status: CompatibilityStatus
    reasons: list[str] = Field(default_factory=list)
