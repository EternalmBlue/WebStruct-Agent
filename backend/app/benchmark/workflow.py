from __future__ import annotations

from functools import lru_cache
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.benchmark.benchmark_nodes import (
    baseline_runner_node,
    dataset_loader_node,
    metric_agent_node,
    ours_runner_node,
    report_agent_node,
)
from app.domain import BenchmarkRequest, GraphRunState


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


def initial_benchmark_state(request: BenchmarkRequest) -> GraphRunState:
    state: GraphRunState = {
        "task_id": f"bench-{uuid4().hex[:12]}",
        "schema_name": request.schema_name,
        "benchmark_config": {"schema_name": request.schema_name},
        "agent_traces": [],
        "errors": [],
        "status": "created",
    }
    if request.dataset:
        state["benchmark_dataset"] = request.dataset
    return state


def run_benchmark_workflow(request: BenchmarkRequest) -> GraphRunState:
    return build_benchmark_graph().invoke(initial_benchmark_state(request))
