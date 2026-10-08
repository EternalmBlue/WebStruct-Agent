from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.contracts import AgentRunTrace, GraphRunState
from app.platform.observability import active_task, runtime

NodeBody = Callable[[GraphRunState], dict[str, Any]]


def run_traced_node(
    state: GraphRunState,
    *,
    name: str,
    role: str,
    body: NodeBody,
    input_summary: str | None = None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    task_id = active_task.get()
    if task_id:
        runtime.node(
            task_id,
            name,
            role,
            "running",
            input_summary=input_summary if input_summary is not None else summarize_state(state),
        )
    try:
        update = body(state)
        trace_status = "skipped" if str(update.get("status", "")).endswith("skipped") else "success"
        trace = AgentRunTrace(
            name=name,
            role=role,
            status=trace_status,
            runtime_ms=_elapsed_ms(started_at),
            input_summary=input_summary if input_summary is not None else summarize_state(state),
            output_summary=", ".join(sorted(update.keys())),
        )
        if task_id:
            runtime.node(
                task_id,
                name,
                role,
                trace_status,
                runtime_ms=trace.runtime_ms,
                input_summary=trace.input_summary,
                output_summary=trace.output_summary,
            )
        return {**update, "agent_traces": [trace]}
    except Exception as exc:
        message = f"{name}: {exc}"
        trace = AgentRunTrace(
            name=name,
            role=role,
            status="failed",
            runtime_ms=_elapsed_ms(started_at),
            input_summary=input_summary if input_summary is not None else summarize_state(state),
            output_summary="",
            error_message=str(exc),
        )
        if task_id:
            runtime.node(
                task_id,
                name,
                role,
                "failed",
                runtime_ms=trace.runtime_ms,
                input_summary=trace.input_summary,
                error_message=trace.error_message,
            )
        return {"status": "failed", "errors": [message], "agent_traces": [trace]}


def summarize_state(state: GraphRunState) -> str:
    parts = []
    if "schema_name" in state:
        parts.append(f"schema={state['schema_name']}")
    if "target_url" in state:
        parts.append(f"url={state['target_url']}")
    if "status" in state:
        parts.append(f"status={state['status']}")
    return ", ".join(parts)


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)
