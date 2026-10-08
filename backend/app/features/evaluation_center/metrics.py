from typing import Any

from app.contracts import BenchmarkMethodResult


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
        if confidence is not None:
            confidences.append(float(confidence))
        for name, expected in gold.items():
            actual = predicted.get(name)
            if actual in (None, "") and name in required:
                missing_required += 1
            if actual == expected:
                correct_fields += 1
                if confidence is not None and float(confidence) >= 0.8:
                    accepted_correct += 1
            if confidence is not None and float(confidence) >= 0.8 and actual not in (None, ""):
                accepted_fields += 1
        evidence_total += int(record.get("evidenced_fields") or 0)
        annotations = record.get("evidence_annotations")
        if annotations is not None:
            independently_annotated = True
            evidence_correct += sum(1 for value in annotations.values() if value is True)
            evidence_total = max(evidence_total, len(annotations))
        repair_successes += int(bool(record.get("repair_success")))
        schema = record.get("schema_spec") or {}
        declared = {field["name"] for field in schema.get("fields", [])}
        schema_checks += 2
        schema_passed += int(set(predicted).issubset(declared))
        schema_passed += int(set(required).issubset(set(predicted)))
    accuracy = correct_fields / total_fields if total_fields else None
    missing_rate = missing_required / required_total if required_total else None
    schema_adherence = schema_passed / schema_checks if schema_checks else None
    evidence_precision = evidence_correct / evidence_total if independently_annotated and evidence_total else None
    average_confidence = sum(confidences) / len(confidences) if confidences else None
    selective_accuracy = accepted_correct / accepted_fields if accepted_fields else None
    reuse_rate = reuse_hits / len(records) if records else None
    repair_rate = repair_successes / len(records) if method == "Ours Full" and records else None
    sources = {
        "field_accuracy": "measured", "required_field_missing_rate": "measured",
        "schema_adherence": "measured",
        "evidence_precision": "measured" if independently_annotated else "unavailable",
        "average_confidence": "measured" if confidences else "unavailable",
        "estimated_token_cost": "estimated", "runtime_ms": "measured",
        "program_reuse_rate": "measured",
        "selective_accuracy": "measured" if accepted_fields else "unavailable",
        "repair_success_rate": "measured" if repair_rate is not None else "unavailable",
    }
    reasons: dict[str, str] = {}
    if not independently_annotated:
        reasons["evidence_precision"] = "independent evidence annotations are absent"
    if not accepted_fields:
        reasons["selective_accuracy"] = "no accepted fields at the configured confidence threshold"
    if method != "Ours Full":
        reasons["repair_success_rate"] = "method does not attempt verifier-directed repair"
    return BenchmarkMethodResult(
        method=method,
        field_accuracy=_round(accuracy),
        required_field_missing_rate=_round(missing_rate),
        schema_adherence=_round(schema_adherence),
        evidence_precision=_round(evidence_precision),
        average_confidence=_round(average_confidence),
        estimated_token_cost=token_cost,
        runtime_ms=runtime_ms,
        program_reuse_rate=_round(reuse_rate),
        selective_accuracy=_round(selective_accuracy),
        repair_success_rate=_round(repair_rate),
        metric_sources=sources,
        unavailable_reasons=reasons,
    )


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None
