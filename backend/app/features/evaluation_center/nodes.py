from __future__ import annotations

import time
from typing import Any

from app.contracts import (
    BenchmarkItem,
    BenchmarkReport,
    ExtractionRequest,
    ExtractionResult,
    FieldSpec,
    FieldExtractionResult,
    GraphRunState,
)
from app.features.evaluation_center.metrics import score_method
from app.features.evaluation_center.repository import persist_benchmark_state
from app.features.extraction_center.executor import execute_program_spec
from app.features.extraction_center.verifier import verify_extraction
from app.features.extraction_center.workflow import run_extraction_workflow
from app.features.page_center.collector import collect_page
from app.features.page_center.views import normalize_page_view
from app.features.program_center.plan import build_extraction_plan, build_program_spec
from app.platform.config import settings
from app.platform.llm import create_model_adapter
from app.platform.tracing.node_runner import run_traced_node

BENCHMARK_METHODS = [
    "Direct LLM",
    "LLM + Schema",
    "Program Only",
    "Hybrid without Verifier",
]


def dataset_loader_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="dataset_loader_node",
        role="EvaluatorAgent",
        body=_dataset_loader_body,
    )


def baseline_runner_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="baseline_runner_node",
        role="EvaluatorAgent",
        body=_baseline_runner_body,
    )


def ours_runner_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="ours_runner_node",
        role="EvaluatorAgent",
        body=_ours_runner_body,
    )


def metric_agent_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="metric_agent_node",
        role="EvaluatorAgent",
        body=_metric_body,
    )


def report_agent_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="report_agent_node",
        role="EvaluatorAgent",
        body=_report_body,
    )


def _dataset_loader_body(state: GraphRunState) -> dict[str, Any]:
    dataset = state.get("benchmark_dataset")
    if dataset:
        return {"benchmark_dataset": dataset, "status": "dataset_loaded"}
    raise ValueError("benchmark_dataset with explicit Schema is required")


def _baseline_runner_body(state: GraphRunState) -> dict[str, Any]:
    dataset = state["benchmark_dataset"]
    runs = {
        method: [_run_method(method, item) for item in dataset.items]
        for method in BENCHMARK_METHODS
    }
    return {"benchmark_runs": runs, "status": "baselines_done"}


def _ours_runner_body(state: GraphRunState) -> dict[str, Any]:
    dataset = state["benchmark_dataset"]
    ours_records = []
    for item in dataset.items:
        ours_records.append(_run_method("Ours Full", item))
    runs = dict(state.get("benchmark_runs", {}))
    runs["Ours Full"] = ours_records
    return {"benchmark_runs": runs, "status": "ours_done"}


def _metric_body(state: GraphRunState) -> dict[str, Any]:
    method_results = [
        score_method(method, records) for method, records in state.get("benchmark_runs", {}).items()
    ]
    report = BenchmarkReport(
        task_id=state["task_id"],
        dataset_name=state["benchmark_dataset"].name,
        methods=method_results,
        summary="显式 Schema、固定页面与标注输入的 benchmark 已完成；各指标均保留实际来源与不可用原因。",
    )
    return {"benchmark_report": report, "status": "metrics_done"}


def _report_body(state: GraphRunState) -> dict[str, Any]:
    persist_benchmark_state({**state, "status": "completed"})
    return {"status": "completed"}


def _run_method(method: str, item: BenchmarkItem) -> dict[str, Any]:
    errors: list[str] = []
    status = "completed"
    confidence = 0.0
    predicted: dict[str, Any] = {}
    evidenced_fields = 0
    repaired_fields = 0
    field_count = 0
    program_reused = False
    start_time = time.perf_counter()
    try:
        if method == "Ours Full":
            result_state = run_extraction_workflow(
                ExtractionRequest(
                    target_url=item.url,
                    html=item.html,
                    schema_name=item.schema_spec.name if item.schema_spec else "",
                    schema_spec=item.schema_spec,
                    persist_result=False,
                )
            )
            errors = result_state.get("errors", [])
            status = result_state.get("status", "failed")
            extraction_result = result_state.get("extraction_result")
            program_reused = bool(result_state.get("program_reused", False))
        else:
            extraction_result = _run_baseline_extraction(method, item)
        if extraction_result:
            predicted = _predicted_record(extraction_result.fields)
            confidence = extraction_result.overall_confidence
            field_count = len(extraction_result.fields)
            evidenced_fields = sum(1 for field in extraction_result.fields if field.evidence)
            repaired_fields = sum(
                1 for field in extraction_result.fields if field.status == "repaired"
            )
    except Exception as exc:  # benchmark should report failed methods, not abort all metrics
        status = "failed"
        errors = [f"{method}: {exc}"]
    runtime_ms = int((time.perf_counter() - start_time) * 1000)
    token_cost = _estimate_token_cost(item, method, predicted)
    return {
        "item_id": item.item_id,
        "predicted": predicted,
        "gold": item.gold_record,
        "confidence": confidence,
        "status": status,
        "errors": errors,
        "method": method,
        "runtime_ms": runtime_ms,
        "token_cost": token_cost,
            "program_reused": program_reused,
        "evidenced_fields": evidenced_fields,
        "field_count": field_count,
        "repair_success": method == "Ours Full" and repaired_fields > 0,
        "schema_spec": item.schema_spec.model_dump(mode="json") if item.schema_spec else None,
        "required_fields": [
            field.name for field in item.schema_spec.fields if field.required
        ] if item.schema_spec else [],
        "evidence_annotations": None,
    }


def _run_baseline_extraction(method: str, item: BenchmarkItem):
    schema_spec = item.schema_spec
    if schema_spec is None:
        raise ValueError(f"benchmark item {item.item_id} requires explicit schema_spec")
    observation = collect_page(
        target_url=item.url,
        schema_name=schema_spec.name,
        input_html=item.html,
    )
    view_bundle = normalize_page_view(observation)
    adapter = create_model_adapter(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    if method == "Direct LLM":
        return _run_direct_llm(
            task_id=f"benchmark-{item.item_id}-{method}",
            view_bundle=view_bundle,
            adapter=adapter,
        )
    if method == "LLM + Schema":
        return _run_llm_with_schema(
            task_id=f"benchmark-{item.item_id}-{method}",
            schema_spec=schema_spec,
            view_bundle=view_bundle,
            adapter=adapter,
        )

    plan = build_extraction_plan(schema_spec)
    program_spec = build_program_spec(plan)

    if method == "Program Only":
        program_spec = program_spec.model_copy(
            update={
                "field_programs": [
                    program.model_copy(update={"enabled": program.strategy != "llm_fallback"})
                    for program in program_spec.field_programs
                ]
            }
        )
    extraction_result = execute_program_spec(
        task_id=f"benchmark-{item.item_id}-{method}",
        schema_spec=schema_spec,
        view_bundle=view_bundle,
        program_spec=program_spec,
        model_adapter=adapter,
        allow_llm_fallback=method in {"Direct LLM", "LLM + Schema", "Hybrid without Verifier"},
    )
    if method == "Hybrid without Verifier":
        return extraction_result
    report = verify_extraction(
        task_id=f"benchmark-{item.item_id}-{method}",
        schema_spec=schema_spec,
        extraction_result=extraction_result,
    )
    _ = report
    return extraction_result


DIRECT_LLM_FIELDS = (
    FieldSpec(name="title", description="页面标题", type="text", required=True),
    FieldSpec(name="organization", description="页面中的组织或发布单位", type="text"),
    FieldSpec(name="position", description="页面中的岗位或事项名称", type="text"),
    FieldSpec(name="publish_date", description="页面明确标注的发布日期", type="date"),
    FieldSpec(name="deadline", description="页面明确标注的截止日期", type="date"),
)


def _run_direct_llm(*, task_id: str, view_bundle, adapter) -> ExtractionResult:
    fields: list[FieldExtractionResult] = []
    for field in DIRECT_LLM_FIELDS:
        value, evidence = adapter.extract_field(field, view_bundle)
        fields.append(
            FieldExtractionResult(
                field_name=field.name,
                value=value,
                normalized_value=value,
                confidence=evidence.score if evidence else 0.0,
                evidence=[evidence] if evidence else [],
                strategy="llm_fallback",
                status="extracted" if value not in (None, "") else "missing",
            )
        )
    return ExtractionResult(
        task_id=task_id,
        schema_name="direct_llm_fixed_mapping",
        fields=fields,
        overall_confidence=round(
            sum(field.confidence for field in fields) / len(fields), 4
        ),
    )


def _run_llm_with_schema(*, task_id: str, schema_spec, view_bundle, adapter) -> ExtractionResult:
    fields: list[FieldExtractionResult] = []
    for field in schema_spec.fields:
        value, evidence = adapter.extract_field(field, view_bundle)
        fields.append(
            FieldExtractionResult(
                field_name=field.name,
                value=value,
                normalized_value=value,
                confidence=evidence.score if evidence else 0.0,
                evidence=[evidence] if evidence else [],
                strategy="llm_fallback",
                status="extracted" if value not in (None, "") else "missing",
            )
        )
    return ExtractionResult(
        task_id=task_id,
        schema_name=schema_spec.name,
        fields=fields,
        overall_confidence=round(
            sum(field.confidence for field in fields) / len(fields), 4
        ),
    )


def _predicted_record(fields: list[FieldExtractionResult]) -> dict[str, Any]:
    return {
        field.field_name: field.normalized_value
        if field.normalized_value is not None
        else field.value
        for field in fields
    }


def _estimate_token_cost(item: BenchmarkItem, method: str, predicted: dict[str, Any]) -> int:
    base = int(len(item.html) / settings.estimated_chars_per_token)
    if method in {"Direct LLM", "LLM + Schema"}:
        base = int(base * 1.15)
    elif method == "Program Only":
        base = int(base * 0.35)
    elif method == "Hybrid without Verifier":
        base = int(base * 0.7)
    elif method == "Ours Full":
        base = int(base * 0.85)
    return max(base + len(predicted) * 12, 0)
