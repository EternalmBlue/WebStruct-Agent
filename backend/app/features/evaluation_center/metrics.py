from typing import Any

from app.contracts import BenchmarkMethodResult
from app.features.extraction_center.verifier import _matches_type
from app.platform.configuration import settings


def score_method(method: str, records: list[dict[str, Any]]) -> BenchmarkMethodResult:
    total_fields = correct_fields = missing_required = required_total = 0
    confidences: list[float] = []
    runtime_ms = token_cost = reuse_hits = repair_successes = 0
    independently_annotated = False
    evidence_correct = evidence_total = 0
    schema_checks = schema_passed = accepted_fields = accepted_correct = 0
    for record in records:
        predicted = record.get("predicted", {})
        gold = record.get("gold", {})
        required = set(record.get("required_fields", gold.keys()))
        total_fields += len(gold)
        required_total += len(required)
        runtime_ms += int(record.get("runtime_ms") or 0)
        token_cost += int(record.get("token_cost") or 0)
        reuse_hits += int(bool(record.get("program_reused")))
        confidence = record.get("confidence")
        field_confidences = record.get("field_confidences") or {}
        if field_confidences:
            confidences.extend(float(value) for value in field_confidences.values())
        elif confidence is not None:
            confidences.append(float(confidence))
        for name, expected in gold.items():
            actual = predicted.get(name)
            if actual in (None, "") and name in required:
                missing_required += 1
            if actual == expected:
                correct_fields += 1
                field_confidence = field_confidences.get(name, confidence)
                if field_confidence is not None and float(field_confidence) >= settings.confidence_threshold:
                    accepted_correct += 1
            field_confidence = field_confidences.get(name, confidence)
            if field_confidence is not None and float(field_confidence) >= settings.confidence_threshold and actual not in (None, ""):
                accepted_fields += 1
        missing_required += sum(
            1 for name in required
            if name not in gold and predicted.get(name) in (None, "")
        )
        evidence_total += int(record.get("evidenced_fields") or 0)
        annotations = record.get("evidence_annotations")
        if annotations is not None:
            independently_annotated = True
            evidence_correct += sum(1 for value in annotations.values() if value is True)
            evidence_total = max(evidence_total, len(annotations))
        repair_successes += int(record.get("repair_success_fields") or 0)
        schema = record.get("schema_spec") or {}
        declared = {field["name"] for field in schema.get("fields", [])}
        schema_checks += 2 + len(schema.get("fields", []))
        schema_passed += int(set(predicted).issubset(declared))
        schema_passed += int(all(predicted.get(name) not in (None, "", []) for name in required))
        schema_passed += sum(
            _matches_type(predicted.get(field["name"]), field["type"])
            for field in schema.get("fields", [])
        )
    accuracy = correct_fields / total_fields if total_fields else None
    missing_rate = missing_required / required_total if required_total else None
    schema_adherence = schema_passed / schema_checks if schema_checks else None
    evidence_precision = evidence_correct / evidence_total if independently_annotated and evidence_total else None
    average_confidence = sum(confidences) / len(confidences) if confidences else None
    selective_accuracy = accepted_correct / accepted_fields if accepted_fields else None
    reuse_rate = reuse_hits / len(records) if records else None
    repair_attempts = sum(int(record.get("repair_attempt_fields") or 0) for record in records)
    repair_rate = repair_successes / repair_attempts if method == "Ours Full" and repair_attempts else None
    model_calls = sum(int(record.get("model_call_count") or 0) for record in records)
    actual_input = sum(int(record.get("actual_input_tokens") or 0) for record in records)
    actual_output = sum(int(record.get("actual_output_tokens") or 0) for record in records)
    missing_usage = sum(int(record.get("token_usage_missing_calls") or 0) for record in records)
    total_fields = sum(int(record.get("nonempty_field_count", record.get("field_count")) or 0) for record in records)
    evidence_coverage = sum(int(record.get("evidenced_fields") or 0) for record in records) / total_fields if total_fields else None
    sources = {
        "field_accuracy": "measured", "required_field_missing_rate": "measured",
        "schema_adherence": "measured",
        "evidence_precision": "measured" if independently_annotated else "unavailable",
        "average_confidence": "measured" if confidences else "unavailable",
        "estimated_token_cost": "measured" if model_calls == 0 else "estimated", "runtime_ms": "measured",
        "program_reuse_rate": "measured" if method in {"Program Only", "Hybrid without Verifier", "Ours Full"} else "unavailable",
        "evidence_coverage": "measured" if evidence_coverage is not None else "unavailable",
        "actual_input_tokens": "measured" if model_calls and missing_usage == 0 else "unavailable",
        "actual_output_tokens": "measured" if model_calls and missing_usage == 0 else "unavailable",
        "selective_accuracy": "measured" if accepted_fields else "unavailable",
        "repair_success_rate": "measured" if repair_rate is not None else "unavailable",
    }
    reasons: dict[str, str] = {}
    if not confidences:
        reasons["average_confidence"] = "no extracted fields with confidence"
    if not independently_annotated:
        reasons["evidence_precision"] = "independent evidence annotations are absent"
    if not accepted_fields:
        reasons["selective_accuracy"] = "no accepted fields at the configured confidence threshold"
    if evidence_coverage is None:
        reasons["evidence_coverage"] = "no non-empty prediction fields"
    if method != "Ours Full":
        reasons["repair_success_rate"] = "method does not attempt verifier-directed repair"
    elif repair_rate is None:
        reasons["repair_success_rate"] = "no verifier-directed repair fields were attempted"
    if method not in {"Program Only", "Hybrid without Verifier", "Ours Full"}:
        reasons["program_reuse_rate"] = "method is not a program method"
    if not model_calls:
        reasons["actual_input_tokens"] = "no model calls"
        reasons["actual_output_tokens"] = "no model calls"
    elif missing_usage:
        reasons["actual_input_tokens"] = "provider usage missing for one or more calls"
        reasons["actual_output_tokens"] = "provider usage missing for one or more calls"
    for name, value in [("field_accuracy", accuracy), ("required_field_missing_rate", missing_rate),
                        ("schema_adherence", schema_adherence)]:
        if value is None:
            sources[name] = "unavailable"
            reasons[name] = "no eligible annotated fields or schema checks"
    return BenchmarkMethodResult(
        method=method,
        field_accuracy=_round(accuracy),
        required_field_missing_rate=_round(missing_rate),
        schema_adherence=_round(schema_adherence),
        evidence_precision=_round(evidence_precision),
        average_confidence=_round(average_confidence),
        estimated_token_cost=token_cost,
        runtime_ms=runtime_ms,
        program_reuse_rate=_round(reuse_rate) if method in {"Program Only", "Hybrid without Verifier", "Ours Full"} else None,
        selective_accuracy=_round(selective_accuracy),
        repair_success_rate=_round(repair_rate),
        actual_input_tokens=actual_input if model_calls and missing_usage == 0 else None,
        actual_output_tokens=actual_output if model_calls and missing_usage == 0 else None,
        partial_actual_input_tokens=sum(int(record.get("partial_actual_input_tokens") or 0) for record in records),
        partial_actual_output_tokens=sum(int(record.get("partial_actual_output_tokens") or 0) for record in records),
        token_usage_missing_calls=missing_usage,
        evidence_coverage=_round(evidence_coverage),
        sample_count=len(records),
        success_count=sum(record.get("status") == "completed" for record in records),
        failure_count=sum(record.get("status") == "failed" for record in records),
        accepted_field_count=accepted_fields,
        model_call_count=model_calls,
        sample_errors={record["item_id"]: record["errors"] for record in records if record.get("errors")},
        metric_sources=sources,
        unavailable_reasons=reasons,
    )


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None
