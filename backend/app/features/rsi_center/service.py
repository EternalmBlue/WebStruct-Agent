import math
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from app.contracts import RSIIterationRequest
from app.features.rsi_center.repository import get_iteration, save_iteration, update_iteration
from app.platform.configuration import settings
from app.platform.observability import runtime
from app.platform.observability.telemetry import redact_tree

EVALUATION_VERSION = "2"
QUALITY_BASIS = "verifier_completion_evidence_proxy_not_gold_accuracy"
QUALITY_WEIGHTS = {"verification_score": .5, "field_completion_rate": .3, "evidence_coverage": .2}


def _now():
    return datetime.now(UTC).isoformat()


def _completed(task_id):
    snapshot = runtime.snapshot(task_id)
    if snapshot is None:
        raise LookupError(f"run not found: {task_id}")
    if snapshot["status"] != "completed":
        raise ValueError(f"run {task_id} is not completed")
    return snapshot


def _value(snapshot, key):
    return ((snapshot.get("metrics") or {}).get(key) or {}).get("value")


def evaluate_iteration(request: RSIIterationRequest):
    started = perf_counter()
    baseline = _completed(request.baseline_run_id)
    candidate = _completed(request.candidate_run_id)
    if request.parent_iteration_id:
        parent = get_iteration(request.parent_iteration_id)
        if parent is None:
            raise LookupError("parent iteration not found")
        if parent["experiment_id"] != request.experiment_id:
            raise ValueError("parent iteration belongs to a different experiment")
    base_fp = baseline.get("fingerprint") or {}
    cand_fp = candidate.get("fingerprint") or {}
    mismatches = [key for key in ("page_hash", "schema_signature", "model", "model_endpoint_hash",
                                  "enable_field_repair", "reuse_verified_program", "program_spec_mode",
                                  "evaluator_version")
                  if base_fp.get(key) != cand_fp.get(key)]
    if baseline["workflow_type"] != "extraction" or candidate["workflow_type"] != "extraction":
        mismatches.append("workflow_type")
    for key in ("page_hash", "schema_signature"):
        if not base_fp.get(key) or not cand_fp.get(key):
            mismatches.append(f"missing_{key}")
    for key in ("evaluator_version",):
        if not base_fp.get(key) or not cand_fp.get(key):
            mismatches.append(f"missing_{key}")
    if request.baseline_run_id == request.candidate_run_id:
        mismatches.append("identical_run_ids")
    if not baseline.get("metrics_version") or not candidate.get("metrics_version"):
        mismatches.append("missing_metrics_version")
    elif baseline.get("metrics_version") != candidate.get("metrics_version"):
        mismatches.append("metrics_version")
    missing_metrics = []
    for name in (*QUALITY_WEIGHTS, "required_field_missing_rate"):
        for label, snap in (("baseline", baseline), ("candidate", candidate)):
            measurement = (snap.get("metrics") or {}).get(name) or {}
            value = measurement.get("value")
            if (
                type(value) not in (int, float) or not math.isfinite(value)
                or not 0 <= value <= 1 or measurement.get("source") != "measured"
            ):
                missing_metrics.append(f"{label}.{name}")
    regressions = []
    for key, direction in (("verification_score", -1), ("field_completion_rate", -1), ("evidence_coverage", -1),
                           ("required_field_missing_rate", 1)):
        before, after = _value(baseline, key), _value(candidate, key)
        if before is not None and after is not None and direction * (after - before) > 1e-9:
            regressions.append(key)
    base_quality = None if missing_metrics else sum(
        _value(baseline, key) * weight for key, weight in QUALITY_WEIGHTS.items())
    candidate_quality = None if missing_metrics else sum(
        _value(candidate, key) * weight for key, weight in QUALITY_WEIGHTS.items())
    base_latency = baseline.get("runtime_ms")
    candidate_latency = candidate.get("runtime_ms")
    deltas = {"quality_proxy": (candidate_quality - base_quality)
              if base_quality is not None and candidate_quality is not None else None,
              "runtime_ms": (candidate_latency - base_latency)
              if base_latency is not None and candidate_latency is not None else None}
    for name, baseline_metric in baseline.get("metrics", {}).items():
        candidate_metric = candidate.get("metrics", {}).get(name, {})
        base_value = baseline_metric.get("value")
        cand_value = candidate_metric.get("value")
        if isinstance(base_value, (int, float)) and isinstance(cand_value, (int, float)):
            deltas[name] = cand_value - base_value
    ratio = ((candidate_latency - base_latency) / base_latency
             if base_latency and candidate_latency is not None else None)
    if mismatches:
        status, reason = "blocked", "incomparable fingerprints: " + ", ".join(mismatches)
    elif missing_metrics:
        status, reason = "blocked", "guardrail measurements unavailable: " + ", ".join(missing_metrics)
    elif base_quality is None or candidate_quality is None or not base_latency or candidate_latency is None:
        status, reason = "blocked", "quality or runtime metric unavailable"
    elif regressions:
        status, reason = "rejected", "quality guardrail regression: " + ", ".join(regressions)
    elif deltas["quality_proxy"] + 1e-9 < settings.rsi_min_quality_delta:
        status, reason = "rejected", "quality improvement is below configured threshold"
    elif ratio is not None and ratio > settings.rsi_max_latency_regression_ratio:
        status, reason = "rejected", "latency regression exceeds configured threshold"
    else:
        status, reason = "accepted", "quality improvement meets threshold within latency guardrail"
    payload = redact_tree({
        **request.model_dump(), "iteration_id": f"rsi-{uuid4().hex}", "status": status,
        "metric_deltas": deltas, "baseline_metrics": baseline.get("metrics", {}),
        "candidate_metrics": candidate.get("metrics", {}),
        "thresholds": {"min_quality_delta": settings.rsi_min_quality_delta,
                       "max_latency_regression_ratio": settings.rsi_max_latency_regression_ratio},
        "decision_reason": reason, "quality_basis": QUALITY_BASIS,
        "evaluation_version": EVALUATION_VERSION,
        "created_at": _now(), "runtime_ms": int((perf_counter() - started) * 1000),
    })
    save_iteration(payload)
    return payload


def rollback_iteration(iteration_id, reason):
    payload = get_iteration(iteration_id)
    if payload is None:
        raise LookupError("iteration not found")
    if payload["status"] == "rolled_back":
        return payload
    if payload["status"] not in {"accepted", "rejected"}:
        raise ValueError("only accepted or rejected iterations can be rolled back")
    payload.update(status="rolled_back", rollback_reason=settings.redact(reason), rollback_at=_now())
    return update_iteration(iteration_id, payload)
