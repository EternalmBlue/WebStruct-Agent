from __future__ import annotations

import time
from typing import Any

from app.benchmark.datasets import load_builtin_dataset
from app.benchmark.metrics import score_method
from app.domain import (
    BenchmarkItem,
    BenchmarkReport,
    FieldExtractionResult,
    ExtractionRequest,
    GraphRunState,
)
from app.extraction.schema_catalog import get_builtin_schema
from app.extraction.collector import collect_page, normalize_page_view
from app.extraction.model_adapters import create_model_adapter
from app.extraction.planner import build_extraction_plan, build_program_spec
from app.extraction.program_executor import execute_program_spec
from app.extraction.verifier import verify_extraction
from app.extraction.workflow import run_extraction_workflow
from app.core.config import settings
from app.storage.benchmark_repository import persist_benchmark_state
from app.workflows.traceable_node_runner import run_traced_node

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
    dataset = load_builtin_dataset(state.get("schema_name", "高校通知"))
    return {"benchmark_dataset": dataset, "status": "dataset_loaded"}


def _baseline_runner_body(state: GraphRunState) -> dict[str, Any]:
    dataset = state["benchmark_dataset"]
    runs = {
        method: [
            _run_method(method, item)
            for item in dataset.items
        ]
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
        score_method(method, records)
        for method, records in state.get("benchmark_runs", {}).items()
    ]
    report = BenchmarkReport(
        task_id=state["task_id"],
        dataset_name=state["benchmark_dataset"].name,
        methods=method_results,
        summary="内置中文网页评测集 benchmark 已完成，可用于论文实验章节的接口和指标展示。",
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
                    schema_name=item.schema_name,
                    schema_spec=get_builtin_schema(item.schema_name),
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
            repaired_fields = sum(1 for field in extraction_result.fields if field.status == "repaired")
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
        "program_reused": program_reused
        or method in {"Program Only", "Hybrid without Verifier"},
        "evidenced_fields": evidenced_fields,
        "field_count": field_count,
        "repair_success": method == "Ours Full" and repaired_fields > 0,
    }


def _run_baseline_extraction(method: str, item: BenchmarkItem):
    schema_spec = get_builtin_schema(item.schema_name)
    observation = collect_page(
        target_url=item.url,
        schema_name=item.schema_name,
        input_html=item.html,
    )
    view_bundle = normalize_page_view(observation)
    adapter = create_model_adapter(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
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
    elif method in {"Direct LLM", "LLM + Schema"}:
        keep_labels = method == "LLM + Schema"
        program_spec = program_spec.model_copy(
            update={
                "field_programs": [
                    program.model_copy(
                        update={
                            "enabled": program.strategy == "llm_fallback"
                            or (keep_labels and program.strategy == "text_near_label")
                        }
                    )
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
    if method in {"Direct LLM", "LLM + Schema"}:
        return extraction_result
    report = verify_extraction(
        task_id=f"benchmark-{item.item_id}-{method}",
        schema_spec=schema_spec,
        extraction_result=extraction_result,
    )
    _ = report
    return extraction_result


def _predicted_record(fields: list[FieldExtractionResult]) -> dict[str, Any]:
    return {
        field.field_name: field.normalized_value
        if field.normalized_value is not None
        else field.value
        for field in fields
    }


def _estimate_token_cost(item: BenchmarkItem, method: str, predicted: dict[str, Any]) -> int:
    base = len(item.html) // 4
    if method in {"Direct LLM", "LLM + Schema"}:
        base = int(base * 1.15)
    elif method == "Program Only":
        base = int(base * 0.35)
    elif method == "Hybrid without Verifier":
        base = int(base * 0.7)
    elif method == "Ours Full":
        base = int(base * 0.85)
    return max(base + len(predicted) * 12, 0)
