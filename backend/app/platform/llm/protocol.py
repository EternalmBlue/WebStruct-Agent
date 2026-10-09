"""模型适配协议、错误类型与共享常量。

Adapter 契约来自 AGENTS.md：任何 LLM 能力都必须通过 ModelAdapter 协议接入，
未配置凭据时必须「显式失败」，而不是静默降级。
"""

from typing import Protocol

from app.contracts import (
    ExtractionPlan,
    FieldEvidence,
    FieldExtractionResult,
    FieldSpec,
    ProgramSpec,
    SchemaSpec,
    ViewBundle,
)


class ModelAdapter(Protocol):
    def extract_record(
        self,
        *,
        view_bundle: ViewBundle,
    ) -> dict[str, object]:
        """Return one generic structured record without receiving a target SchemaSpec."""

    def generate_schema_spec(
        self,
        *,
        view_bundle: ViewBundle,
    ) -> SchemaSpec:
        """Return a field contract for the current page view."""

    def generate_program_spec(
        self,
        *,
        schema_spec: SchemaSpec,
        extraction_plan: ExtractionPlan,
        view_bundle: ViewBundle,
        fallback_program_spec: ProgramSpec,
    ) -> ProgramSpec:
        """Return a safe ProgramSpec DSL for the current page view."""

    def extract_field(
        self,
        field: FieldSpec,
        view_bundle: ViewBundle,
        guidance_value: str = "",
    ) -> tuple[str | None, FieldEvidence | None]:
        """Return a structured field value and evidence without free-form chat state."""

    def revise_schema_and_program_spec(
        self,
        *,
        user_message: str,
        current_schema_spec: SchemaSpec,
        current_program_spec: ProgramSpec | None,
        fallback_program_spec: ProgramSpec,
        view_bundle: ViewBundle,
    ) -> tuple[str, SchemaSpec, ProgramSpec, list[str], list[str]]:
        """Return a revised SchemaSpec and safe ProgramSpec for human AI collaboration."""

    def revise_field_schema(
        self,
        *,
        view_bundle: ViewBundle,
        current_schema_spec: SchemaSpec,
        user_message: str,
    ) -> SchemaSpec:
        """Return only a field-set proposal for the current page snapshot."""

    def revise_field_value(
        self,
        *,
        field: FieldSpec,
        view_bundle: ViewBundle,
        guidance_value: str = "",
        evidence_text: str = "",
    ) -> tuple[FieldExtractionResult, ProgramSpec]:
        """Return one field value/evidence and its safe field-local program."""


class MissingModelConfigurationError(RuntimeError):
    """Raised when a workflow reaches LLM fallback without provider credentials."""


class ModelProviderError(RuntimeError):
    """Raised when the external model provider returns an unusable response."""


MAX_LLM_TEXT_CHARS = 12000
MAX_PROGRAMMER_TEXT_CHARS = 8000
MAX_PROGRAMMER_HTML_CHARS = 6000
MAX_SCHEMA_TEXT_CHARS = 10000
MAX_SCHEMA_LINES = 140
DEFAULT_SCHEMA_FIELD_LIMIT = 8
