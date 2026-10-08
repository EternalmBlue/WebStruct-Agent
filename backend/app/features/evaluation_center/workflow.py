from __future__ import annotations

from functools import lru_cache
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.contracts import BenchmarkRequest, GraphRunState
from app.features.evaluation_center.nodes import (
    baseline_runner_node,
    dataset_loader_node,
    metric_agent_node,
    ours_runner_node,
    report_agent_node,
)

BENCHMARK_NODE_NAMES = [
    "dataset_loader_node",
    "baseline_runner_node",
    "ours_runner_node",
    "metric_agent_node",
    "report_agent_node",
]


@lru_cache(maxsize=1)
def build_benchmark_graph():
    graph = StateGraph(GraphRunState)
    graph.add_node("dataset_loader_node", dataset_loader_node)
    graph.add_node("baseline_runner_node", baseline_runner_node)
    graph.add_node("ours_runner_node", ours_runner_node)
    graph.add_node("metric_agent_node", metric_agent_node)
    graph.add_node("report_agent_node", report_agent_node)

    graph.set_entry_point("dataset_loader_node")
    graph.add_edge("dataset_loader_node", "baseline_runner_node")
    graph.add_edge("baseline_runner_node", "ours_runner_node")
    graph.add_edge("ours_runner_node", "metric_agent_node")
    graph.add_edge("metric_agent_node", "report_agent_node")
    graph.add_edge("report_agent_node", END)
    return graph.compile()


def initial_benchmark_state(request: BenchmarkRequest, task_id: str | None = None) -> GraphRunState:
    state: GraphRunState = {
        "task_id": task_id or f"bench-{uuid4().hex[:12]}",
        "benchmark_config": {},
        "agent_traces": [],
        "errors": [],
        "status": "created",
    }
    if request.dataset:
        state["benchmark_dataset"] = request.dataset
    return state


def run_benchmark_workflow(request: BenchmarkRequest) -> GraphRunState:
    return build_benchmark_graph().invoke(initial_benchmark_state(request))


def run_benchmark_workflow_for_task(request: BenchmarkRequest, task_id: str) -> GraphRunState:
    return build_benchmark_graph().invoke(initial_benchmark_state(request, task_id))
