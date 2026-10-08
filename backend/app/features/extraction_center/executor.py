from __future__ import annotations

import re
from typing import Any

from app.contracts import (
    ExtractionResult,
    FieldEvidence,
    FieldExtractionResult,
    FieldProgramSpec,
    ProgramSpec,
    SchemaSpec,
    ViewBundle,
)
from app.platform.dom import parse_html, select_values
from app.platform.llm import MissingModelConfigurationError, ModelAdapter
from app.platform.observability.telemetry import observe
from app.platform.text_processing import bounded_snippet, normalize_date, normalize_whitespace


def execute_program_spec(
    *,
    task_id: str,
    schema_spec: SchemaSpec,
    view_bundle: ViewBundle,
    program_spec: ProgramSpec,
    model_adapter: ModelAdapter | None = None,
    allow_llm_fallback: bool = False,
) -> ExtractionResult:
    if model_adapter is None:
        raise MissingModelConfigurationError(
            "execute_program_spec requires a configured ModelAdapter for llm_fallback"
        )
    adapter = model_adapter
    fields: list[FieldExtractionResult] = []

    for field in schema_spec.fields:
        field_programs = [
            program for program in program_spec.field_programs if program.field_name == field.name
        ]
        result = _execute_field_programs(
            field,
            field_programs,
            view_bundle,
            adapter,
            allow_llm_fallback=allow_llm_fallback,
        )
        fields.append(result)

    extracted = [field for field in fields if field.status != "missing"]
    overall_confidence = (
        round(sum(field.confidence for field in extracted) / len(fields), 4) if fields else 0.0
    )
    return ExtractionResult(
        task_id=task_id,
        schema_name=schema_spec.name,
        fields=fields,
        overall_confidence=overall_confidence,
    )


def _execute_field_programs(
    field: Any,
    field_programs: list[FieldProgramSpec],
    view_bundle: ViewBundle,
    adapter: ModelAdapter,
    *,
    allow_llm_fallback: bool,
) -> FieldExtractionResult:
    errors = []
    for program in field_programs:
        if not program.enabled:
            continue
        if program.strategy == "llm_fallback" and not allow_llm_fallback:
            continue
        try:
            value, evidence = _execute_single_program(field, program, view_bundle, adapter)
        except (ValueError, MissingModelConfigurationError) as exc:
            if isinstance(exc, ValueError) and "unsupported ProgramSpec strategy" in str(exc):
                raise
            errors.append(str(exc))
            continue
        if value not in (None, ""):
            normalized = _apply_postprocess(value, program.postprocess)
            confidence = _confidence_for(program, evidence, normalized)
            return FieldExtractionResult(
                field_name=field.name,
                value=value,
                normalized_value=normalized,
                confidence=confidence,
                evidence=[evidence] if evidence else [],
                strategy=program.strategy,
                status="extracted",
            )

    return FieldExtractionResult(
        field_name=field.name,
        value=None,
        normalized_value=None,
        confidence=0.0,
        evidence=[],
        strategy="none",
        status="missing",
        error_message="; ".join(errors) if errors else None,
    )


def _execute_single_program(
    field: Any,
    program: FieldProgramSpec,
    view_bundle: ViewBundle,
    adapter: ModelAdapter,
) -> tuple[str | None, FieldEvidence | None]:
    if program.strategy == "text_near_label":
        return _extract_text_near_label(field.name, program, view_bundle)
    if program.strategy == "regex_on_text":
        return _extract_regex(field.name, program, view_bundle)
    if program.strategy == "css":
        return _extract_css(field.name, program, view_bundle)
    if program.strategy == "xpath":
        return _extract_xpath(field.name, program, view_bundle)
    if program.strategy == "llm_fallback":
        return adapter.extract_field(field, view_bundle)
    raise ValueError(f"unsupported ProgramSpec strategy: {program.strategy}")


def _extract_text_near_label(
    field_name: str,
    program: FieldProgramSpec,
    view_bundle: ViewBundle,
) -> tuple[str | None, FieldEvidence | None]:
    labels = [program.label, *program.labels]
    labels = sorted({label for label in labels if label}, key=len, reverse=True)
    if not labels:
        return None, None
    for line in view_bundle.lines:
        normalized_line = line.strip()
        for label in labels:
            if not _label_matches_field_line(label, normalized_line):
                continue
            escaped = re.escape(label)
            match = re.search(
                rf"^(?:[【\[\(（\-\*\d一二三四五六七八九十\.、\s]*){escaped}\s*[：:\-：]\s*(?P<value>.+)$",
                normalized_line,
            )
            if match:
                value = normalize_whitespace(match.group("value"))
                if value:
                    start = max(view_bundle.text.find(normalized_line), 0)
                    return value, FieldEvidence(
                        field_name=field_name,
                        source="text_near_label",
                        text=bounded_snippet(view_bundle.text, start, start + len(normalized_line)),
                        start_char=start,
                        end_char=start + len(normalized_line),
                        score=0.85,
                    )
    return None, None


def _label_matches_field_line(label: str, line: str) -> bool:
    if not line or not label:
        return False
    if label not in line:
        return False
    if line.startswith(label):
        return True
    prefix = line.split(label, maxsplit=1)[0].strip()
    if not prefix:
        return True
    allowed_prefixes = {
        "",
        "发布日期",
        "报名截止",
        "申报截止",
        "施行日期",
        "发布单位",
        "发布机关",
        "招聘单位",
        "岗位",
        "联系人",
        "发文字号",
    }
    return prefix in allowed_prefixes


def _extract_regex(
    field_name: str,
    program: FieldProgramSpec,
    view_bundle: ViewBundle,
) -> tuple[str | None, FieldEvidence | None]:
    if not program.pattern:
        return None, None
    match = re.search(program.pattern, view_bundle.text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return None, None
    value = match.group(1) if match.groups() else match.group(0)
    return normalize_whitespace(value), FieldEvidence(
        field_name=field_name,
        source="regex_on_text",
        text=bounded_snippet(view_bundle.text, match.start(), match.end()),
        start_char=match.start(),
        end_char=match.end(),
        score=0.75,
    )


def _extract_css(
    field_name: str,
    program: FieldProgramSpec,
    view_bundle: ViewBundle,
) -> tuple[str | None, FieldEvidence | None]:
    if not program.selector:
        return None, None
    return _extract_dom(field_name, program, view_bundle)


def _extract_xpath(
    field_name: str,
    program: FieldProgramSpec,
    view_bundle: ViewBundle,
) -> tuple[str | None, FieldEvidence | None]:
    if not program.selector:
        return None, None
    return _extract_dom(field_name, program, view_bundle)


def _extract_dom(field_name, program, view_bundle):
    try:
        values = select_values(parse_html(view_bundle.raw_html), program.strategy,
                               program.selector, program.attribute)
    except Exception as exc:
        observe("selector_execution", field=field_name, strategy=program.strategy,
                selector=program.selector, result="invalid_selector", match_count=None)
        raise ValueError(f"invalid {program.strategy} selector: {program.selector}") from exc
    outcome = ("no_matches" if not values else "ambiguous_matches" if len(values) > 1
               else "empty_value" if not values[0] else "success")
    observe("selector_execution", field=field_name, strategy=program.strategy,
            selector=program.selector, result=outcome, match_count=len(values))
    if outcome == "ambiguous_matches":
        raise ValueError(f"ambiguous {program.strategy} selector: {program.selector}")
    if outcome != "success":
        return None, None
    value = values[0]
    start = view_bundle.text.find(value)
    return value, FieldEvidence(field_name=field_name, source=program.strategy, text=value,
                               start_char=start if start >= 0 else None,
                               end_char=start + len(value) if start >= 0 else None, score=.8)


def _apply_postprocess(value: str, postprocess: list[str]) -> str:
    current = value
    for function_name in postprocess:
        if function_name == "strip":
            current = current.strip()
        elif function_name == "normalize_whitespace":
            current = normalize_whitespace(current)
        elif function_name == "normalize_date":
            current = normalize_date(current)
        else:
            raise ValueError(f"unsupported postprocess function: {function_name}")
    return current


def _confidence_for(
    program: FieldProgramSpec,
    evidence: FieldEvidence | None,
    value: str,
) -> float:
    if not evidence or not value:
        return 0.0
    base = {
        "css": 0.82,
        "xpath": 0.8,
        "regex_on_text": 0.76,
        "text_near_label": 0.86,
        "llm_fallback": 0.48,
    }[program.strategy]
    if len(value) < 2:
        base -= 0.15
    return max(0.0, min(1.0, round((base + evidence.score) / 2, 4)))
