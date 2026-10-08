"""Versioned measurements, fingerprints and empirical aggregation."""
import json
import math
from hashlib import sha256

from app.contracts import MetricEnvelope


def metric(value, *, unit="", count=1, source="measured", reason="no eligible samples"):
    return MetricEnvelope(value=value, source=source if value is not None else "unavailable",
                          unit=unit, sample_count=count, reason=reason if value is None else None).model_dump()


def ratio(numerator, denominator):
    return metric(numerator / denominator if denominator else None, count=denominator, unit="ratio")


def percentile(values, quantile):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lo, hi = math.floor(index), math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def signature(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest() if value else None


def token_metrics(observations):
    calls = [e for e in observations if e["event_type"] == "model_call" and e.get("http_attempted")]
    missing = sum(e.get("actual_input_tokens") is None or e.get("actual_output_tokens") is None for e in calls)
    return {
        "model_call_count": len(calls),
        "token_usage_missing_calls": missing,
        "actual_input_tokens": None if missing else sum(e["actual_input_tokens"] for e in calls),
        "actual_output_tokens": None if missing else sum(e["actual_output_tokens"] for e in calls),
        "partial_actual_input_tokens": sum(e.get("actual_input_tokens") or 0 for e in calls),
        "partial_actual_output_tokens": sum(e.get("actual_output_tokens") or 0 for e in calls),
        "estimated_input_tokens": sum(e.get("estimated_input_tokens") or 0 for e in calls),
        "estimated_output_tokens": sum(e.get("estimated_output_tokens") or 0 for e in calls),
    }


def _field_value(field):
    value = field.get("normalized_value")
    return field.get("value") if value is None else value


def build_run_metrics(state, elapsed_ms, observations):
    from app.features.extraction_center.verifier import EVALUATOR_VERSION, is_missing
    from app.platform.configuration import settings
    from app.platform.persistence.json_payloads import jsonable_state
    payload = jsonable_state(state)
    attempts = [e for e in observations if e["event_type"] == "collection_attempt"]
    probes = [e for e in observations if e["event_type"] == "browser_probe"]
    repairs = [e for e in observations if e["event_type"] == "field_repair"]
    selectors = [e for e in observations if e["event_type"] == "selector_execution"]
    rejected = [e for e in observations if e["event_type"] == "program_rule_rejected"]
    fields = (payload.get("extraction_result") or {}).get("fields", [])
    schema = payload.get("schema_spec") or {}
    report = payload.get("verification_report") or {}
    nonempty = [f for f in fields if not is_missing(_field_value(f))]
    required = [f["name"] for f in schema.get("fields", []) if f.get("required")]
    optional = [f["name"] for f in schema.get("fields", []) if not f.get("required")]
    predicted = {f["field_name"]: _field_value(f) for f in fields}
    tokens = token_metrics(observations)
    metrics = {
        "workflow_runtime_ms": metric(elapsed_ms, unit="ms"),
        "collection_attempt_count": metric(len(attempts)),
        "browser_launch_success_rate": ratio(sum(bool(p.get("launch_verified")) for p in probes), len(probes)),
        "collection_success_rate": ratio(sum(a["result"] == "success" for a in attempts), len(attempts)),
        "fallback_attempt_count": metric(sum(a.get("fallback_attempted", False) for a in attempts)),
        "access_limited_count": metric(sum(a["classification"] == "access_limited" for a in attempts)),
        "schema_failure_count": metric(sum(
            trace.get("name") == "schema_agent_node" and trace.get("status") == "failed"
            for trace in payload.get("agent_traces", [])
        )),
        "schema_field_count": metric(len(schema.get("fields", [])) if schema else None, count=int(bool(schema))),
        "extracted_field_count": metric(len(nonempty) if fields else None, count=len(fields)),
        "required_field_missing_rate": ratio(sum(is_missing(predicted.get(n)) for n in required), len(required)),
        "optional_field_missing_rate": ratio(sum(is_missing(predicted.get(n)) for n in optional), len(optional)),
        "field_completion_rate": ratio(sum(not is_missing(predicted.get(f["name"]))
                                         for f in schema.get("fields", [])), len(schema.get("fields", []))),
        "selector_attempt_count": metric(len(selectors)),
        "selector_ambiguity_count": metric(sum(e.get("result") == "ambiguous_matches" for e in selectors)),
        "selector_error_count": metric(sum(e.get("result") == "invalid_selector" for e in selectors)),
        "program_rule_rejection_count": metric(len(rejected)),
        "browser_wait_ms": metric(sum(p.get("post_navigation_wait_ms", 0) for p in probes)
                                   if probes else None, unit="ms", count=len(probes)),
        "evidence_coverage": ratio(sum(bool(f.get("evidence")) for f in nonempty), len(nonempty)),
        "average_confidence": metric(sum(f["confidence"] for f in fields) / len(fields) if fields else None, count=len(fields)),
        "verification_score": metric(report.get("score"), count=int(bool(report))),
        "verification_passed": metric(int(report["passed"]) if report else None, count=int(bool(report))),
        "verification_issue_count": metric(len(report.get("issues", [])) if report else None, count=int(bool(report))),
        "repair_attempt_count": metric(len(repairs)),
        "repair_supported_rate": ratio(sum(e.get("verified") is True for e in repairs), len(repairs)),
        "program_reuse": metric(int(bool(payload.get("program_reused"))) if payload.get("program_spec") else None, count=int(bool(payload.get("program_spec")))),
        "page_intent_confidence": metric(
            (payload.get("page_intent_assessment") or {}).get("confidence"),
            count=int(bool(payload.get("page_intent_assessment"))),
        ),
        "body_visible_text_coverage": metric(
            (payload.get("body_selection") or {}).get("metrics", {}).get("visible_text_coverage"),
            count=int(bool(payload.get("body_selection"))),
        ),
        "body_block_coverage": metric(
            (payload.get("body_selection") or {}).get("metrics", {}).get("block_coverage"),
            count=int(bool(payload.get("body_selection"))),
        ),
        "body_continuity_score": metric(
            (payload.get("body_selection") or {}).get("metrics", {}).get("continuity_score"),
            count=int(bool(payload.get("body_selection"))),
        ),
        "body_noise_ratio": metric(
            (payload.get("body_selection") or {}).get("metrics", {}).get("noise_ratio"),
            count=int(bool(payload.get("body_selection"))),
        ),
        "body_candidate_count": metric(
            (payload.get("body_selection") or {}).get("metrics", {}).get("candidate_count"),
            count=int(bool(payload.get("body_selection"))),
        ),
        "body_merged_candidate_count": metric(
            (payload.get("body_selection") or {}).get("metrics", {}).get("merged_candidate_count"),
            count=int(bool(payload.get("body_selection"))),
        ),
        "program_reuse_reason_count": metric(
            len(payload.get("program_reuse_reasons") or []),
            count=int("program_reuse_decision" in payload),
        ),
    }
    for name, value in tokens.items():
        metrics[name] = metric(value, count=tokens["model_call_count"],
                               source="estimated" if name.startswith("estimated_") and tokens["model_call_count"] else "measured",
                               reason="provider usage missing for one or more calls")
    observation = payload.get("page_observation") or {}
    html = observation.get("html", "")
    fingerprint = {
        "page_hash": sha256(html.encode()).hexdigest() if html else None,
        "schema_signature": signature(schema),
        "program_signature": signature(payload.get("program_spec")),
        "model": settings.llm_model,
        "model_endpoint_hash": signature(settings.llm_base_url),
        "enable_field_repair": bool(payload.get("enable_field_repair")),
        "program_spec_mode": payload.get("program_spec_mode", "create"),
        "reuse_verified_program": bool(payload.get("reuse_verified_program")),
        "page_intent": (payload.get("page_intent_assessment") or {}).get("intent"),
        "page_structure_signature": signature(payload.get("page_structure_signature")),
        "program_reuse_decision": payload.get("program_reuse_decision", "not_requested"),
        "program_reuse_reasons": list(payload.get("program_reuse_reasons") or []),
        "workflow_type": "extraction" if schema else "unknown",
        "evaluator_version": EVALUATOR_VERSION,
    }
    return {"metrics_version": "2", "metrics": metrics, "fingerprint": fingerprint}


def summarize_runs(snapshots):
    terminal = [s for s in snapshots if s["status"] in {"completed", "failed"}]
    times = [s["runtime_ms"] for s in terminal if s.get("runtime_ms") is not None]
    metrics = {
        f"p{label}_runtime_ms": metric(percentile(times, p), unit="ms", count=len(times))
        for label, p in [(50, .5), (95, .95), (99, .99)]
    }
    metrics["failure_rate"] = ratio(sum(s["status"] == "failed" for s in terminal), len(terminal))
    queues = [s["queue_wait_ms"] for s in snapshots if s.get("queue_wait_ms") is not None]
    metrics["average_queue_wait_ms"] = metric(sum(queues) / len(queues) if queues else None, unit="ms", count=len(queues))
    for name in [
        "verification_score",
        "verification_passed",
        "evidence_coverage",
        "program_reuse",
        "page_intent_confidence",
        "body_visible_text_coverage",
        "body_block_coverage",
        "body_continuity_score",
        "body_noise_ratio",
    ]:
        values = [s.get("metrics", {}).get(name, {}).get("value") for s in snapshots]
        values = [v for v in values if v is not None]
        metrics[name] = metric(sum(values) / len(values) if values else None, count=len(values), unit="ratio")
    for name in ["browser_launch_success_rate", "collection_success_rate",
                 "required_field_missing_rate", "optional_field_missing_rate",
                 "field_completion_rate", "repair_supported_rate"]:
        eligible = [s["metrics"][name] for s in snapshots if s.get("metrics", {}).get(name, {}).get("value") is not None]
        count = sum(m["sample_count"] for m in eligible)
        metrics[name] = metric(sum(m["value"] * m["sample_count"] for m in eligible) / count if count else None, count=count, unit="ratio")
    for name in ["collection_attempt_count", "fallback_attempt_count", "access_limited_count",
                 "schema_failure_count", "model_call_count", "token_usage_missing_calls",
                 "selector_attempt_count", "selector_ambiguity_count", "selector_error_count",
                 "program_rule_rejection_count", "body_candidate_count",
                 "body_merged_candidate_count", "program_reuse_reason_count"]:
        values = [s.get("metrics", {}).get(name, {}).get("value") for s in snapshots]
        values = [value for value in values if value is not None]
        metrics[name] = metric(sum(values) if values else None, count=len(values))
    waits = [s.get("metrics", {}).get("browser_wait_ms", {}).get("value") for s in snapshots]
    waits = [value for value in waits if value is not None]
    metrics["browser_wait_ms"] = metric(sum(waits) if waits else None, unit="ms", count=len(waits))
    nodes = {}
    for snapshot in snapshots:
        for name, node in snapshot.get("nodes", {}).items():
            if node.get("runtime_ms") is not None and node["status"] != "skipped":
                nodes.setdefault(name, []).append(node["runtime_ms"])
    counts = {state: sum(s["status"] == state for s in snapshots)
              for state in ("queued", "running", "completed", "failed")}
    return {"total": len(snapshots), **counts,
            "average_runtime_ms": sum(times) / len(times) if times else None,
            "metrics": metrics,
            "nodes": {name: {"average_runtime_ms": metric(sum(v) / len(v), unit="ms", count=len(v)),
                             "p95_runtime_ms": metric(percentile(v, .95), unit="ms", count=len(v))}
                      for name, v in nodes.items()},
            "by_workflow": {kind: sum(s["workflow_type"] == kind for s in snapshots)
                            for kind in {s["workflow_type"] for s in snapshots}}}
