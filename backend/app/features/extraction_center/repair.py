import time

from app.contracts import (
    EvidenceBundle,
    ExtractionResult,
    FieldExtractionResult,
    SchemaSpec,
    VerificationReport,
    ViewBundle,
)
from app.features.extraction_center.fallback import decide_fallback_fields
from app.features.extraction_center.verifier import verify_extraction
from app.platform.llm import MissingModelConfigurationError, ModelAdapter, ModelProviderError
from app.platform.observability.telemetry import observe
from app.platform.text_processing import normalize_date


def repair_missing_required_fields(
    *,
    task_id: str,
    schema_spec: SchemaSpec,
    view_bundle: ViewBundle,
    extraction_result: ExtractionResult,
    verification_report: VerificationReport,
    repair_attempts: int,
    model_adapter: ModelAdapter,
) -> dict[str, object]:
    fallback_decisions = decide_fallback_fields(
        schema_spec=schema_spec,
        extraction_result=extraction_result,
        verification_report=verification_report,
    )
    fallback_by_field = {decision.field_name: decision for decision in fallback_decisions}
    if not fallback_by_field or repair_attempts >= 1:
        return {"repair_attempts": repair_attempts, "status": "repair_skipped"}

    fields = []
    outcomes = []
    for result in extraction_result.fields:
        if result.field_name not in fallback_by_field:
            fields.append(result)
            continue
        field_spec = next(field for field in schema_spec.fields if field.name == result.field_name)
        started = time.perf_counter()
        outcome = {"field": result.field_name, "before": result.normalized_value
                   if result.normalized_value is not None else result.value,
                   "reason": fallback_by_field[result.field_name].reason}
        try:
            value, evidence = model_adapter.extract_field(field_spec, view_bundle)
        except (MissingModelConfigurationError, ModelProviderError) as exc:
            outcome.update(result="failed", error_message=str(exc), after=outcome["before"])
            outcome["runtime_ms"] = int((time.perf_counter() - started) * 1000)
            outcomes.append(outcome)
            fields.append(
                result.model_copy(
                    update={
                        "status": "fallback_failed",
                        "error_message": str(exc),
                    }
                )
            )
            continue
        if value and evidence:
            normalized = normalize_date(value) if field_spec.type == "date" else value
            outcome.update(result="repaired", after=normalized)
            fields.append(
                FieldExtractionResult(
                    field_name=result.field_name,
                    value=value,
                    normalized_value=normalized,
                    confidence=0.42,
                    evidence=[evidence],
                    strategy="llm_fallback",
                    status="repaired",
                )
            )
        else:
            outcome.update(result="abstained", after=outcome["before"])
            fields.append(
                result.model_copy(
                    update={
                        "status": "fallback_failed",
                        "error_message": f"LLM fallback abstained: {fallback_by_field[result.field_name].reason}",
                    }
                )
            )
        outcome["runtime_ms"] = int((time.perf_counter() - started) * 1000)
        outcomes.append(outcome)

    repaired_result = extraction_result.model_copy(update={
        "fields": fields,
        "overall_confidence": round(sum(field.confidence for field in fields) / len(fields), 4)
        if fields else 0.0,
    })
    repaired_report = verify_extraction(
        task_id=task_id,
        schema_spec=schema_spec,
        extraction_result=repaired_result,
    )
    issue_fields = {issue.field_name for issue in repaired_report.issues}
    for outcome in outcomes:
        outcome["verified"] = outcome["result"] == "repaired" and outcome["field"] not in issue_fields
        observe("field_repair", **{key: value for key, value in outcome.items()
                                 if key not in {"before", "after"}})
    evidences = [evidence for field in repaired_result.fields for evidence in field.evidence]
    return {
        "extraction_result": repaired_result,
        "evidence_bundle": EvidenceBundle(task_id=task_id, evidences=evidences),
        "verification_report": repaired_report,
        "repair_attempts": repair_attempts + 1,
        "repair_outcomes": outcomes,
        "status": "repaired",
    }
