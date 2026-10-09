"""未配置模型凭据时的适配器：所有 LLM 调用都会显式抛出异常。"""

from dataclasses import dataclass

from app.contracts import (
    ExtractionPlan,
    FieldEvidence,
    FieldSpec,
    ProgramSpec,
    SchemaSpec,
    ViewBundle,
)
from app.platform.llm.protocol import MissingModelConfigurationError


@dataclass
class UnconfiguredModelAdapter:
    """Adapter that fails explicitly when real LLM fallback is required."""

    reason: str = "LLM fallback requires model.api_key in config.toml"

    def generate_schema_spec(
        self,
        *,
        view_bundle: ViewBundle,
    ) -> SchemaSpec:
        raise MissingModelConfigurationError(self.reason)

    def generate_program_spec(
        self,
        *,
        schema_spec: SchemaSpec,
        extraction_plan: ExtractionPlan,
        view_bundle: ViewBundle,
        fallback_program_spec: ProgramSpec,
    ) -> ProgramSpec:
        raise MissingModelConfigurationError(self.reason)

    def extract_field(
        self,
        field: FieldSpec,
        view_bundle: ViewBundle,
        guidance_value: str = "",
    ) -> tuple[str | None, FieldEvidence | None]:
        raise MissingModelConfigurationError(self.reason)

    def revise_schema_and_program_spec(
        self,
        *,
        user_message: str,
        current_schema_spec: SchemaSpec,
        current_program_spec: ProgramSpec | None,
        fallback_program_spec: ProgramSpec,
        view_bundle: ViewBundle,
    ) -> tuple[str, SchemaSpec, ProgramSpec, list[str], list[str]]:
        raise MissingModelConfigurationError(self.reason)

    def revise_field_schema(
        self,
        *,
        view_bundle: ViewBundle,
        current_schema_spec: SchemaSpec,
        user_message: str,
    ) -> SchemaSpec:
        raise MissingModelConfigurationError(self.reason)

    def revise_field_value(
        self,
        *,
        field: FieldSpec,
        view_bundle: ViewBundle,
        guidance_value: str = "",
        evidence_text: str = "",
    ):
        raise MissingModelConfigurationError(self.reason)
