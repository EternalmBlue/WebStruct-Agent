from __future__ import annotations

from dataclasses import dataclass

from app.contracts import ExtractionResult, SchemaSpec, VerificationReport


@dataclass(frozen=True)
class FallbackDecision:
    field_name: str
    reason: str


def decide_fallback_fields(
    *,
    schema_spec: SchemaSpec,
    extraction_result: ExtractionResult,
    verification_report: VerificationReport,
) -> list[FallbackDecision]:
    decisions: dict[str, FallbackDecision] = {}
    fallback_issue_codes = {
        "required_field_missing",
        "field_not_returned",
        "field_type_mismatch",
        "date_normalization_failure",
        "evidence_not_supporting_value",
        "empty_or_low_quality_evidence",
        "low_confidence",
        "publish_date_deadline_confusion",
    }
    required_fields = {field.name for field in schema_spec.fields if field.required}

    for issue in verification_report.issues:
        if issue.code not in fallback_issue_codes:
            continue
        if issue.severity == "warning" and issue.field_name not in required_fields:
            result = extraction_result.get_field(issue.field_name)
            if result and result.confidence >= 0.45 and result.evidence:
                continue
        decisions[issue.field_name] = FallbackDecision(
            field_name=issue.field_name,
            reason=issue.code,
        )

    for field in schema_spec.fields:
        result = extraction_result.get_field(field.name)
        if not result:
            decisions[field.name] = FallbackDecision(field.name, "field_not_returned")
            continue
        if field.required and result.status == "missing":
            decisions[field.name] = FallbackDecision(field.name, "required_field_missing")
        elif result.confidence < 0.35 and not result.evidence:
            decisions[field.name] = FallbackDecision(field.name, "low_confidence")

    return list(decisions.values())
