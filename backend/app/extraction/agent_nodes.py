from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.domain import EvidenceBundle, GraphRunState
from app.extraction.schema_catalog import DEFAULT_SCHEMA_NAME, get_builtin_schema
from app.extraction.collector import collect_page, normalize_page_view
from app.extraction.model_adapters import (
    MissingModelConfigurationError,
    ModelProviderError,
    create_model_adapter,
)
from app.extraction.planner import build_extraction_plan, build_program_spec
from app.extraction.program_executor import execute_program_spec
from app.extraction.repair import repair_missing_required_fields
from app.extraction.verifier import verify_extraction
from app.storage.extraction_repository import persist_extraction_state
from app.storage.program_repository import get_user_verified_program_spec
from app.storage.schema_repository import (
    persist_schema_version,
)
from app.workflows.traceable_node_runner import run_traced_node


def schema_agent_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="schema_agent_node",
        role="SchemaAgent",
        body=_schema_agent_body,
    )


def page_collector_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="page_collector_node",
        role="PageCollectorAgent",
        body=_page_collector_body,
    )


def view_normalizer_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="view_normalizer_node",
        role="ViewNormalizerAgent",
        body=_view_normalizer_body,
    )


def planner_agent_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="planner_agent_node",
        role="PlannerAgent",
        body=_planner_body,
    )


def programmer_agent_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="programmer_agent_node",
        role="ProgrammerAgent",
        body=_programmer_body,
    )


def extractor_agent_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="extractor_agent_node",
        role="ExtractorAgent",
        body=_extractor_body,
    )


def verifier_agent_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="verifier_agent_node",
        role="VerifierAgent",
        body=_verifier_body,
    )


def repair_agent_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="repair_agent_node",
        role="RepairAgent",
        body=_repair_body,
    )


def result_persist_node(state: GraphRunState) -> dict[str, Any]:
    return run_traced_node(
        state,
        name="result_persist_node",
        role="ResultPersistAgent",
        body=_persist_body,
    )


def _schema_agent_body(state: GraphRunState) -> dict[str, Any]:
    schema_generation_mode = "provided"
    schema_generation_error = None
    schema_spec = state.get("schema_spec")
    if schema_spec is None and state.get("force_builtin_schema", False):
        schema_spec = get_builtin_schema(state.get("schema_name", DEFAULT_SCHEMA_NAME))
        schema_generation_mode = "builtin"
    if schema_spec is None:
        view_bundle = state.get("view_bundle")
        if view_bundle is None:
            raise ValueError("view_bundle is required when schema_spec is not provided")
        adapter = create_model_adapter(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
        try:
            schema_spec = adapter.generate_schema_spec(view_bundle=view_bundle)
            schema_generation_mode = "llm"
        except (MissingModelConfigurationError, ModelProviderError, ValueError) as exc:
            schema_spec = get_builtin_schema(DEFAULT_SCHEMA_NAME)
            schema_generation_mode = "builtin_fallback"
            schema_generation_error = str(exc)

    schema_version = None
    if state.get("persist_result", True):
        schema_version = persist_schema_version(schema_spec=schema_spec, source="extraction")
    return {
        "schema_spec": schema_spec,
        "schema_name": schema_spec.name,
        "schema_version": schema_version,
        "schema_generation_mode": schema_generation_mode,
        "schema_generation_error": schema_generation_error,
        "status": "schema_ready",
    }


def _page_collector_body(state: GraphRunState) -> dict[str, Any]:
    observation = collect_page(
        target_url=state.get("target_url", ""),
        schema_name=state.get("schema_name", DEFAULT_SCHEMA_NAME),
        input_html=state.get("input_html") or "",
    )
    return {"page_observation": observation, "target_url": observation.url, "status": "page_collected"}


def _view_normalizer_body(state: GraphRunState) -> dict[str, Any]:
    view_bundle = normalize_page_view(state["page_observation"])
    return {"view_bundle": view_bundle, "status": "view_normalized"}


def _planner_body(state: GraphRunState) -> dict[str, Any]:
    schema_spec = state["schema_spec"]
    if schema_spec is None:
        raise ValueError("schema_spec is required before planning")
    return {"extraction_plan": build_extraction_plan(schema_spec), "status": "plan_ready"}


def _programmer_body(state: GraphRunState) -> dict[str, Any]:
    schema_spec = state["schema_spec"]
    if schema_spec is None:
        raise ValueError("schema_spec is required before programming")
    extraction_plan = state.get("extraction_plan")
    if extraction_plan is None:
        raise ValueError("extraction_plan is required before programming")
    view_bundle = state.get("view_bundle")
    if view_bundle is None:
        raise ValueError("view_bundle is required before programming")

    fallback_program_spec = build_program_spec(extraction_plan)
    provided_program_spec = state.get("provided_program_spec")
    if provided_program_spec is not None:
        return {
            "program_spec": provided_program_spec,
            "program_reused": False,
            "program_generation_mode": "provided",
            "program_generation_error": None,
            "status": "program_provided",
        }

    must_run_verified = state.get("program_spec_mode") == "run_verified"
    allow_verified_reuse = must_run_verified or state.get("reuse_verified_program", False)
    reused_program = get_user_verified_program_spec(schema_spec) if allow_verified_reuse else None
    if must_run_verified and reused_program is None:
        raise ValueError(
            "运行 ProgramSpec 需要先在人工复核中标记一个已验证 ProgramSpec"
        )
    if reused_program:
        return {
            "program_spec": reused_program,
            "program_reused": True,
            "program_generation_mode": "reused",
            "program_generation_error": None,
            "status": "program_reused",
        }

    adapter = create_model_adapter(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    try:
        program_spec = adapter.generate_program_spec(
            schema_spec=schema_spec,
            extraction_plan=extraction_plan,
            view_bundle=view_bundle,
            fallback_program_spec=fallback_program_spec,
        )
        generation_mode = "llm"
        generation_error = None
    except (MissingModelConfigurationError, ModelProviderError, ValueError) as exc:
        program_spec = fallback_program_spec
        generation_mode = "deterministic_fallback"
        generation_error = str(exc)

    return {
        "program_spec": program_spec,
        "program_reused": False,
        "program_generation_mode": generation_mode,
        "program_generation_error": generation_error,
        "status": "program_ready",
    }


def _extractor_body(state: GraphRunState) -> dict[str, Any]:
    schema_spec = state["schema_spec"]
    if schema_spec is None:
        raise ValueError("schema_spec is required before extraction")
    adapter = create_model_adapter(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    extraction_result = execute_program_spec(
        task_id=state["task_id"],
        schema_spec=schema_spec,
        view_bundle=state["view_bundle"],
        program_spec=state["program_spec"],
        model_adapter=adapter,
    )
    evidences = [
        evidence
        for field in extraction_result.fields
        for evidence in field.evidence
    ]
    return {
        "extraction_result": extraction_result,
        "evidence_bundle": EvidenceBundle(
            task_id=state["task_id"],
            evidences=evidences,
        ),
        "status": "extracted",
    }


def _verifier_body(state: GraphRunState) -> dict[str, Any]:
    schema_spec = state["schema_spec"]
    if schema_spec is None:
        raise ValueError("schema_spec is required before verification")
    report = verify_extraction(
        task_id=state["task_id"],
        schema_spec=schema_spec,
        extraction_result=state["extraction_result"],
    )
    return {"verification_report": report, "status": "verified"}


def _repair_body(state: GraphRunState) -> dict[str, Any]:
    report = state.get("verification_report")
    extraction_result = state.get("extraction_result")
    schema_spec = state.get("schema_spec")
    if not report or not extraction_result or not schema_spec:
        return {"status": "repair_skipped"}
    return repair_missing_required_fields(
        task_id=state["task_id"],
        schema_spec=schema_spec,
        view_bundle=state["view_bundle"],
        extraction_result=extraction_result,
        verification_report=report,
        repair_attempts=state.get("repair_attempts", 0),
        model_adapter=create_model_adapter(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        ),
    )


def _persist_body(state: GraphRunState) -> dict[str, Any]:
    if state.get("persist_result", True):
        final_state = {**state, "status": "completed"}
        persist_extraction_state(final_state)
    return {"status": "completed"}
