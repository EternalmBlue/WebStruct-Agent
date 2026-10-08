from __future__ import annotations

import re
from typing import Any

from app.contracts import (
    ExtractionResult,
    FieldExtractionResult,
    SchemaSpec,
    VerificationIssue,
    VerificationReport,
)
from app.platform.text_processing import normalize_date, normalize_whitespace


def verify_extraction(
    *,
    task_id: str,
    schema_spec: SchemaSpec,
    extraction_result: ExtractionResult,
) -> VerificationReport:
    issues: list[VerificationIssue] = []

    for field in schema_spec.fields:
        result = extraction_result.get_field(field.name)
        if result is None:
            issues.append(
                VerificationIssue(
                    field_name=field.name,
                    code="field_not_returned",
                    severity="error" if field.required else "warning",
                    message="字段没有出现在抽取结果中。",
                )
            )
            continue

        value = _effective_value(result)
        if result.status == "fallback_failed":
            issues.append(
                VerificationIssue(
                    field_name=field.name,
                    code="llm_fallback_failed",
                    severity="error" if field.required else "warning",
                    message=result.error_message or "LLM fallback failed explicitly.",
                )
            )
        if field.required and not value:
            issues.append(
                VerificationIssue(
                    field_name=field.name,
                    code="required_field_missing",
                    severity="error",
                    message="必填字段缺失。",
                )
            )
        if value and not _matches_type(value, field.type):
            issues.append(
                VerificationIssue(
                    field_name=field.name,
                    code="field_type_mismatch",
                    severity="error" if field.required else "warning",
                    message=f"字段值不符合 {field.type} 类型。",
                )
            )
        if field.type == "date" and value and normalize_date(str(value)) != str(value):
            issues.append(
                VerificationIssue(
                    field_name=field.name,
                    code="date_normalization_failure",
                    severity="warning",
                    message="日期没有归一化为 YYYY-MM-DD。",
                )
            )
        if value and not _evidence_supports_value(result):
            issues.append(
                VerificationIssue(
                    field_name=field.name,
                    code="evidence_not_supporting_value",
                    severity="warning",
                    message="证据文本不能直接支持字段值。",
                )
            )
        if not result.evidence or all(len(item.text.strip()) < 4 for item in result.evidence):
            issues.append(
                VerificationIssue(
                    field_name=field.name,
                    code="empty_or_low_quality_evidence",
                    severity="warning" if value else "error",
                    message="证据为空或质量过低。",
                )
            )
        if value and result.confidence < _expected_confidence_floor(result):
            issues.append(
                VerificationIssue(
                    field_name=field.name,
                    code="low_confidence",
                    severity="warning",
                    message="置信度低于当前策略的建议阈值。",
                )
            )

    _check_publish_deadline_confusion(extraction_result, issues)

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    score = max(0.0, 1.0 - error_count * 0.25 - warning_count * 0.08)
    return VerificationReport(
        task_id=task_id,
        passed=error_count == 0,
        issues=issues,
        score=round(score, 4),
    )


def _effective_value(result: FieldExtractionResult) -> Any:
    return result.normalized_value if result.normalized_value is not None else result.value


def _matches_type(value: Any, field_type: str) -> bool:
    if field_type in {"string", "text"}:
        return isinstance(value, str) and bool(normalize_whitespace(value))
    if field_type == "date":
        return isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
    if field_type == "number":
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False
    if field_type == "url":
        return isinstance(value, str) and value.startswith(("http://", "https://"))
    if field_type == "list":
        return isinstance(value, list)
    return True


def _evidence_supports_value(result: FieldExtractionResult) -> bool:
    value = normalize_whitespace(str(_effective_value(result) or ""))
    if not value:
        return False
    relaxed_value = value.replace("-", "")
    for evidence in result.evidence:
        evidence_text = normalize_whitespace(evidence.text)
        relaxed_evidence = evidence_text.replace("-", "")
        evidence_date = normalize_date(evidence_text)
        if value in evidence_text or relaxed_value in relaxed_evidence or evidence_date == value:
            return True
    return False


def _expected_confidence_floor(result: FieldExtractionResult) -> float:
    if result.strategy in {"css", "xpath", "regex_on_text", "text_near_label"}:
        return 0.55
    if result.strategy == "llm_fallback":
        return 0.35
    return 0.0


def _check_publish_deadline_confusion(
    extraction_result: ExtractionResult,
    issues: list[VerificationIssue],
) -> None:
    publish = extraction_result.get_field("publish_date")
    deadline = extraction_result.get_field("deadline")
    if not publish or not deadline:
        return
    publish_value = _effective_value(publish)
    deadline_value = _effective_value(deadline)
    if not publish_value or not deadline_value or publish_value != deadline_value:
        return
    publish_evidence = " ".join(item.text for item in publish.evidence)
    deadline_evidence = " ".join(item.text for item in deadline.evidence)
    if "截止" in publish_evidence or "发布" in deadline_evidence:
        issues.append(
            VerificationIssue(
                field_name="publish_date",
                code="publish_date_deadline_confusion",
                severity="warning",
                message="发布日期和截止日期可能被混淆。",
            )
        )
