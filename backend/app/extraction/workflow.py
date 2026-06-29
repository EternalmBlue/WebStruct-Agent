from __future__ import annotations

from functools import lru_cache
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.domain import ExtractionRequest, GraphRunState
from app.extraction.agent_nodes import (
    extractor_agent_node,
    page_collector_node,
    planner_agent_node,
    programmer_agent_node,
    repair_agent_node,
    result_persist_node,
    schema_agent_node,
    verifier_agent_node,
    view_normalizer_node,
)

EXTRACTION_NODE_NAMES = [
    "page_collector_node",
    "view_normalizer_node",
    "schema_agent_node",
    "planner_agent_node",
    "programmer_agent_node",
    "extractor_agent_node",
    "verifier_agent_node",
    "repair_agent_node",
]


@lru_cache(maxsize=1)
def build_extraction_graph():
    graph = StateGraph(GraphRunState)
    graph.add_node("schema_agent_node", schema_agent_node)
    graph.add_node("page_collector_node", page_collector_node)
    graph.add_node("view_normalizer_node", view_normalizer_node)
    graph.add_node("planner_agent_node", planner_agent_node)
    graph.add_node("programmer_agent_node", programmer_agent_node)
    graph.add_node("extractor_agent_node", extractor_agent_node)
    graph.add_node("verifier_agent_node", verifier_agent_node)
    graph.add_node("repair_agent_node", repair_agent_node)
    graph.add_node("result_persist_node", result_persist_node)

    graph.set_entry_point("page_collector_node")
    _add_status_guarded_edge(graph, "page_collector_node", "view_normalizer_node")
    _add_status_guarded_edge(graph, "view_normalizer_node", "schema_agent_node")
    _add_status_guarded_edge(graph, "schema_agent_node", "planner_agent_node")
    _add_status_guarded_edge(graph, "planner_agent_node", "programmer_agent_node")
    _add_status_guarded_edge(graph, "programmer_agent_node", "extractor_agent_node")
    _add_status_guarded_edge(graph, "extractor_agent_node", "verifier_agent_node")
    _add_status_guarded_edge(graph, "verifier_agent_node", "repair_agent_node")
    _add_status_guarded_edge(graph, "repair_agent_node", "result_persist_node")
    graph.add_edge("result_persist_node", END)
    return graph.compile()


def initial_extraction_state(request: ExtractionRequest) -> GraphRunState:
    return {
        "task_id": f"extract-{uuid4().hex[:12]}",
        "schema_name": request.schema_name,
        "schema_spec": request.schema_spec,
        "force_builtin_schema": request.force_builtin_schema,
        "target_url": request.target_url,
        "seed_urls": [request.target_url],
        "input_html": request.html or "",
        "persist_result": request.persist_result,
        "program_spec_mode": request.program_spec_mode,
        "provided_program_spec": request.program_spec,
        "reuse_verified_program": request.reuse_verified_program,
        "repair_attempts": 0,
        "agent_traces": [],
        "errors": [],
        "status": "created",
    }


def run_extraction_workflow(request: ExtractionRequest) -> GraphRunState:
    return build_extraction_graph().invoke(initial_extraction_state(request))


def _add_status_guarded_edge(
    graph: StateGraph,
    source_node: str,
    next_node: str,
) -> None:
    graph.add_conditional_edges(
        source_node,
        _route_after_node,
        {"continue": next_node, "failed": "result_persist_node"},
    )


def _route_after_node(state: GraphRunState) -> str:
    return "failed" if state.get("status") == "failed" else "continue"
