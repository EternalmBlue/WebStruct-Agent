from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.types import PostprocessFunction, ProgramStrategy


class FieldProgramSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: str = Field(min_length=1, max_length=128)
    strategy: ProgramStrategy
    enabled: bool = True
    selector: str | None = Field(default=None, max_length=500)
    attribute: str | None = Field(default=None, max_length=128)
    pattern: str | None = Field(default=None, max_length=500)
    label: str | None = Field(default=None, max_length=200)
    labels: list[str] = Field(default_factory=list, max_length=8)
    postprocess: list[PostprocessFunction] = Field(default_factory=list)

    @field_validator("selector", "attribute", "pattern", "label", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None or not isinstance(value, str):
            return value
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_strategy_shape(self):
        strategy = self.strategy
        selector = self.selector
        pattern = self.pattern
        label = self.label
        labels = [item.strip() for item in self.labels if item.strip()]

        if strategy in {"css", "xpath"}:
            if not selector:
                raise ValueError(f"{self.field_name}: {strategy} requires selector")
            if pattern or label or labels:
                raise ValueError(
                    f"{self.field_name}: {strategy} cannot include regex or label parameters"
                )
        elif strategy == "regex_on_text":
            if not pattern:
                raise ValueError(f"{self.field_name}: regex_on_text requires pattern")
            if selector or self.attribute or label or labels:
                raise ValueError(
                    f"{self.field_name}: regex_on_text cannot include DOM or label parameters"
                )
        elif strategy == "text_near_label":
            if not label and not labels:
                raise ValueError(f"{self.field_name}: text_near_label requires label or labels")
            if selector or self.attribute or pattern:
                raise ValueError(
                    f"{self.field_name}: text_near_label cannot include selector or pattern"
                )
        elif strategy == "llm_fallback":
            if selector or self.attribute or pattern or label or labels:
                raise ValueError(
                    f"{self.field_name}: llm_fallback cannot include locator parameters"
                )
        return self


class ProgramSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(default="0.1", min_length=1, max_length=32)
    safety_mode: Literal["dsl"] = "dsl"
    field_programs: list[FieldProgramSpec]
