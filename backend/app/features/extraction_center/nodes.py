from __future__ import annotations

from typing import Any

from app.contracts import EvidenceBundle, GraphRunState
from app.features.extraction_center.executor import execute_program_spec
from app.features.extraction_center.repair import repair_missing_required_fields
from app.features.extraction_center.repository import persist_extraction_state
from app.features.extraction_center.verifier import verify_extraction
from app.features.page_center.collector import collect_page
from app.features.page_center.single_page import assess_page_intent, select_body_content
from app.features.page_center.views import normalize_page_view
from app.features.program_center.compatibility import build_page_structure_signature
from app.features.program_center.plan import build_extraction_plan, build_program_spec
from app.features.program_center.quality import (
    add_body_fallback_programs,
    validate_page_program,
)
from app.features.program_center.repository import resolve_user_verified_program_spec
from app.features.schema_center.catalog import DEFAULT_SCHEMA_NAME
from app.features.schema_center.repository import (
    persist_schema_version,
)
from app.platform.config import settings
from app.platform.llm import (
    MissingModelConfigurationError,
    ModelProviderError,
    create_model_adapter,
)
from app.platform.observability import runtime
from app.platform.tracing.node_runner import run_traced_node


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
        raise ValueError("内置 Schema 已移除，请提供明确的 schema_spec")
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
            runtime.decision("model_decision", purpose="schema_generation", result="failed",
                             reason=str(exc))
            raise ValueError(f"Schema 无法生成: {exc}") from exc

    schema_version = None
    if state.get("persist_result", True) and state.get("program_spec_mode") != "run_verified":
        schema_version = persist_schema_version(
            schema_spec=schema_spec,
            source="model" if schema_generation_mode == "llm" else "user",
        )
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
        requested_intent=state.get("target_page_intent", "single_resource"),
    )
    assessment = assess_page_intent(
        observation.html,
        requested_intent=(
            None
            if state.get("target_page_intent") == "auto"
            else state.get("target_page_intent", "single_resource")
        ),
    )
    if not assessment.gate_passed:
        runtime.decision(
            "page_intent_gate",
            result="rejected",
            intent=assessment.intent,
            reasons=assessment.reasons,
        )
        raise ValueError(
            f"page intent mismatch: requested={state.get('target_page_intent')}, "
            f"actual={assessment.intent}"
        )
    body_selection = select_body_content(observation.html)
    return {
        "page_observation": observation,
        "target_url": observation.url,
        "page_intent_assessment": assessment,
        "body_selection": body_selection,
        "status": "page_collected",
    }


def _view_normalizer_body(state: GraphRunState) -> dict[str, Any]:
    view_bundle = normalize_page_view(state["page_observation"])
    signature = build_page_structure_signature(
        view_bundle,
        intent=state.get("page_intent_assessment"),
        body_selection=state.get("body_selection"),
    )
    return {
        "view_bundle": view_bundle,
        "page_structure_signature": signature,
        "status": "view_normalized",
    }


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
    if state.get("program_spec_mode") == "run_verified":
        provided_program_spec = None
    if provided_program_spec is not None:
        runtime.decision("program_generation", mode="provided")
        return {
            "program_spec": provided_program_spec,
            "program_reused": False,
            "program_generation_mode": "provided",
            "program_generation_error": None,
            "program_reuse_decision": "not_requested",
            "program_reuse_reasons": [],
            "status": "program_provided",
        }

    must_run_verified = state.get("program_spec_mode") == "run_verified"
    allow_verified_reuse = must_run_verified or state.get("reuse_verified_program", False)
    reused_program = None
    reuse_decision = "not_requested"
    reuse_reasons: list[str] = []
    if allow_verified_reuse:
        reused_program, compatibility = resolve_user_verified_program_spec(
            schema_spec,
            page_structure_signature=state.get("page_structure_signature"),
        )
        reuse_decision = "accepted" if reused_program is not None else compatibility.status
        reuse_reasons = compatibility.reasons
        runtime.decision(
            "program_reuse",
            result=reuse_decision,
            reasons=reuse_reasons,
        )
    if must_run_verified and reused_program is None:
        reason = ", ".join(reuse_reasons) or "no_verified_program"
        raise ValueError(f"运行 ProgramSpec 无兼容的已验证程序: {reason}")
    if reused_program:
        from app.features.schema_center.repository import schema_signature

        runtime.decision(
            "program_reuse",
            result="hit",
            schema_signature=schema_signature(schema_spec),
        )
        return {
            "program_spec": reused_program,
            "program_reused": True,
            "program_generation_mode": "reused",
            "program_generation_error": None,
            "program_reuse_decision": "accepted",
            "program_reuse_reasons": [],
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
        runtime.decision("model_decision", purpose="program_generation", result="fallback",
                         reason=str(exc))

    program_spec, diagnostics = validate_page_program(
        program_spec,
        view_bundle.raw_html,
        body_selection=state.get("body_selection"),
    )
    program_spec = add_body_fallback_programs(
        program_spec,
        schema_spec=schema_spec,
        body_selection=state.get("body_selection"),
    )
    for diagnostic in diagnostics:
        runtime.decision("program_rule_rejected", **diagnostic)
    return {
        "program_spec": program_spec,
        "program_reused": False,
        "program_generation_mode": generation_mode,
        "program_generation_error": generation_error,
        "program_validation_issues": diagnostics,
        "program_reuse_decision": reuse_decision,
        "program_reuse_reasons": reuse_reasons,
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
        allow_llm_fallback=state.get("allow_execution_fallback", False),
    )
    evidences = [evidence for field in extraction_result.fields for evidence in field.evidence]
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
    if not state.get("enable_field_repair", False):
        return {"status": "repair_skipped", "repair_attempts": state.get("repair_attempts", 0)}
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
    """留存最终结果，但不能把「节点失败」的运行状态抹平成成功。

    旧实现无条件写入 completed，导致采集/执行环节的失败在落库后被伪装成成功；
    这里保留 failed 状态，让 /api/extract/{task_id} 回放与运维面板都能看到真实结果。
    """
    final_status = "failed" if state.get("status") == "failed" else "completed"
    if state.get("persist_result", True):
        persist_extraction_state({**state, "status": final_status})
    return {"status": final_status}
