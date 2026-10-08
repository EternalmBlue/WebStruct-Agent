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
from app.platform.observability import runtime
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
    for result in extraction_result.fields:
        if result.field_name not in fallback_by_field:
            fields.append(result)
            continue
        field_spec = next(field for field in schema_spec.fields if field.name == result.field_name)
        try:
            value, evidence = model_adapter.extract_field(field_spec, view_bundle)
        except (MissingModelConfigurationError, ModelProviderError) as exc:
            runtime.decision(
                "field_repair",
                field=result.field_name,
                result="failed",
                reason=str(exc),
            )
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
            runtime.decision("field_repair", field=result.field_name, result="repaired")
            normalized = normalize_date(value) if field_spec.type == "date" else value
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
            runtime.decision("field_repair", field=result.field_name, result="abstained")
            fields.append(
                result.model_copy(
                    update={
                        "status": "fallback_failed",
                        "error_message": f"LLM fallback abstained: {fallback_by_field[result.field_name].reason}",
                    }
                )
            )

    repaired_result = extraction_result.model_copy(update={"fields": fields})
    repaired_report = verify_extraction(
        task_id=task_id,
        schema_spec=schema_spec,
        extraction_result=repaired_result,
    )
    evidences = [evidence for field in repaired_result.fields for evidence in field.evidence]
    return {
        "extraction_result": repaired_result,
        "evidence_bundle": EvidenceBundle(task_id=task_id, evidences=evidences),
        "verification_report": repaired_report,
        "repair_attempts": repair_attempts + 1,
        "status": "repaired",
    }
