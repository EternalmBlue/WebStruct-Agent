from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, get_args

from app.contracts import (
    ExtractionPlan,
    FieldExtractionPlan,
    FieldProgramSpec,
    ProgramSpec,
    SchemaSpec,
)
from app.contracts.types import PostprocessFunction, ProgramStrategy

ALLOWED_PROGRAM_STRATEGIES = set(get_args(ProgramStrategy))
ALLOWED_POSTPROCESS_FUNCTIONS = set(get_args(PostprocessFunction))


def build_extraction_plan(schema_spec: SchemaSpec) -> ExtractionPlan:
    field_plans = []
    for field in schema_spec.fields:
        labels = [field.name, field.description, *field.aliases]
        strategies = ["text_near_label", "regex_on_text", "llm_fallback"]
        if field.name == "title":
            strategies = ["css", "xpath", "text_near_label", "llm_fallback"]
        field_plans.append(
            FieldExtractionPlan(
                field_name=field.name,
                field_type=field.type,
                labels=[label for label in labels if label],
                strategies=strategies,
                required=field.required,
            )
        )
    return ExtractionPlan(schema_name=schema_spec.name, field_plans=field_plans)


def build_program_spec(plan: ExtractionPlan) -> ProgramSpec:
    programs: list[FieldProgramSpec] = []
    for field_plan in plan.field_plans:
        if field_plan.field_name == "title":
            programs.extend(_title_programs(field_plan.field_name))
        programs.extend(_label_programs(field_plan))
        if field_plan.field_type == "date":
            programs.append(_date_regex_program(field_plan))
        programs.append(
            FieldProgramSpec(
                field_name=field_plan.field_name,
                strategy="llm_fallback",
                enabled=True,
                postprocess=_postprocess_for(field_plan.field_type),
            )
        )
    return ProgramSpec(field_programs=programs)


def build_safe_program_spec_from_candidate(
    candidate: ProgramSpec | Mapping[str, Any],
    *,
    fallback_program_spec: ProgramSpec,
    schema_spec: SchemaSpec,
) -> ProgramSpec:
    """Sanitize model-produced DSL and merge it with deterministic fallbacks."""

    sanitized_programs, _ = sanitize_candidate_field_programs(
        candidate,
        schema_spec=schema_spec,
    )

    return merge_program_specs(
        preferred_program_spec=ProgramSpec(field_programs=sanitized_programs),
        fallback_program_spec=fallback_program_spec,
        schema_spec=schema_spec,
    )


def sanitize_candidate_field_programs(
    candidate: ProgramSpec | Mapping[str, Any],
    *,
    schema_spec: SchemaSpec,
) -> tuple[list[FieldProgramSpec], list[str]]:
    """Return safe generated programs plus validation issues for rejected items."""

    field_names = {field.name for field in schema_spec.fields}
    field_types = {field.name: field.type for field in schema_spec.fields}
    sanitized_programs: list[FieldProgramSpec] = []
    validation_issues: list[str] = []

    for item in _candidate_field_programs(candidate):
        program = _sanitize_field_program(item, field_names, field_types)
        if program is not None:
            sanitized_programs.append(program)
        else:
            issue = _unsafe_program_issue(item, field_names)
            if issue not in validation_issues:
                validation_issues.append(issue)

    return sanitized_programs, validation_issues


def merge_program_specs(
    *,
    preferred_program_spec: ProgramSpec,
    fallback_program_spec: ProgramSpec,
    schema_spec: SchemaSpec,
) -> ProgramSpec:
    """Prefer generated programs, then append deterministic programs per field."""

    field_names = [field.name for field in schema_spec.fields]
    merged: list[FieldProgramSpec] = []
    seen: set[tuple[Any, ...]] = set()

    for field_name in field_names:
        for source in (preferred_program_spec, fallback_program_spec):
            for program in source.field_programs:
                if program.field_name != field_name:
                    continue
                key = _program_identity(program)
                if key in seen:
                    continue
                merged.append(program)
                seen.add(key)

    return ProgramSpec(field_programs=merged)


def _title_programs(field_name: str) -> list[FieldProgramSpec]:
    return [
        FieldProgramSpec(
            field_name=field_name,
            strategy="css",
            enabled=True,
            selector="h1",
            postprocess=["strip", "normalize_whitespace"],
        ),
        FieldProgramSpec(
            field_name=field_name,
            strategy="xpath",
            enabled=True,
            selector="//title",
            postprocess=["strip", "normalize_whitespace"],
        ),
    ]


def _label_programs(field_plan: FieldExtractionPlan) -> list[FieldProgramSpec]:
    labels = _refine_labels(field_plan)
    return [
        FieldProgramSpec(
            field_name=field_plan.field_name,
            strategy="text_near_label",
            enabled=True,
            label=label,
            labels=labels,
            postprocess=_postprocess_for(field_plan.field_type),
        )
        for label in labels
    ]


def _date_regex_program(field_plan: FieldExtractionPlan) -> FieldProgramSpec:
    labels = "|".join(re.escape(label) for label in field_plan.labels)
    return FieldProgramSpec(
        field_name=field_plan.field_name,
        strategy="regex_on_text",
        enabled=True,
        pattern=rf"(?:{labels})\s*[：:\-]\s*(\d{{4}}\s*[年\-/\.]\s*\d{{1,2}}\s*[月\-/\.]\s*\d{{1,2}}\s*日?)",
        postprocess=["strip", "normalize_whitespace", "normalize_date"],
    )


def _postprocess_for(field_type: str) -> list[str]:
    steps = ["strip", "normalize_whitespace"]
    if field_type == "date":
        steps.append("normalize_date")
    return steps


def _refine_labels(field_plan: FieldExtractionPlan) -> list[str]:
    labels = [label for label in field_plan.labels if label]
    if field_plan.field_name in {"publish_date", "deadline", "effective_date"}:
        labels = [label for label in labels if label not in {"日期"}]
    return list(dict.fromkeys(labels))


def _candidate_field_programs(candidate: ProgramSpec | Mapping[str, Any]) -> list[Any]:
    if isinstance(candidate, ProgramSpec):
        return list(candidate.field_programs)
    field_programs = candidate.get("field_programs", [])
    return list(field_programs) if isinstance(field_programs, list) else []


def _sanitize_field_program(
    item: Any,
    field_names: set[str],
    field_types: dict[str, str],
) -> FieldProgramSpec | None:
    if isinstance(item, FieldProgramSpec):
        payload = item.model_dump(mode="json")
    elif isinstance(item, Mapping):
        payload = dict(item)
    else:
        return None

    field_name = payload.get("field_name")
    strategy = payload.get("strategy")
    if field_name not in field_names or strategy not in ALLOWED_PROGRAM_STRATEGIES:
        return None

    normalized_payload: dict[str, Any] = {
        "field_name": field_name,
        "strategy": strategy,
        "enabled": bool(payload.get("enabled", True)),
        "postprocess": _sanitize_postprocess(
            payload.get("postprocess"),
            field_types.get(str(field_name), "string"),
        ),
    }

    selector = _clean_optional_text(payload.get("selector"))
    pattern = _clean_optional_text(payload.get("pattern"))
    label = _clean_optional_text(payload.get("label"))
    labels = _sanitize_labels(payload.get("labels"))

    if strategy == "css":
        if not selector or any(token in selector for token in ["<", ">", "{", "}"]):
            return None
        normalized_payload["selector"] = selector
    elif strategy == "xpath":
        if not selector or not selector.startswith("//"):
            return None
        normalized_payload["selector"] = selector
    elif strategy == "regex_on_text":
        if not pattern:
            return None
        try:
            re.compile(pattern)
        except re.error:
            return None
        normalized_payload["pattern"] = pattern
    elif strategy == "text_near_label":
        if not label and not labels:
            return None
        normalized_payload["label"] = label
        normalized_payload["labels"] = labels or ([label] if label else [])
    elif strategy == "llm_fallback":
        pass
    else:
        return None

    return FieldProgramSpec.model_validate(normalized_payload)


def _unsafe_program_issue(item: Any, field_names: set[str]) -> str:
    if isinstance(item, FieldProgramSpec):
        payload: Mapping[str, Any] = item.model_dump(mode="json")
    elif isinstance(item, Mapping):
        payload = item
    else:
        return "已忽略非对象 ProgramSpec 规则"

    field_name = payload.get("field_name")
    strategy = payload.get("strategy")
    if field_name not in field_names:
        return f"已忽略未知字段的 ProgramSpec 规则：{field_name or '未命名字段'}"
    if strategy not in ALLOWED_PROGRAM_STRATEGIES:
        return f"已忽略字段 {field_name} 的非白名单策略：{strategy or '未指定策略'}"
    return f"已忽略字段 {field_name} 的不完整或不安全 ProgramSpec 规则"


def _sanitize_postprocess(value: Any, field_type: str) -> list[str]:
    if not isinstance(value, list):
        return _postprocess_for(field_type)
    steps = [
        str(step)
        for step in value
        if isinstance(step, str) and step in ALLOWED_POSTPROCESS_FUNCTIONS
    ]
    if "strip" not in steps:
        steps.insert(0, "strip")
    if "normalize_whitespace" not in steps:
        insert_at = 1 if steps and steps[0] == "strip" else 0
        steps.insert(insert_at, "normalize_whitespace")
    if field_type == "date" and "normalize_date" not in steps:
        steps.append("normalize_date")
    return list(dict.fromkeys(steps))


def _sanitize_labels(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    labels = [label.strip() for label in value if isinstance(label, str) and label.strip()]
    return list(dict.fromkeys(labels))[:8]


def _clean_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 500:
        return None
    return cleaned


def _program_identity(program: FieldProgramSpec) -> tuple[Any, ...]:
    return (
        program.field_name,
        program.strategy,
        program.selector,
        program.pattern,
        program.label,
        tuple(program.labels),
        tuple(program.postprocess),
    )
