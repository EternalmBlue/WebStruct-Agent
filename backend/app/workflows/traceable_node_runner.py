from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.domain import AgentRunTrace, GraphRunState

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
    try:
        update = body(state)
        trace = AgentRunTrace(
            name=name,
            role=role,
            status="success",
            runtime_ms=_elapsed_ms(started_at),
            input_summary=input_summary if input_summary is not None else summarize_state(state),
            output_summary=", ".join(sorted(update.keys())),
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
