from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from langgraph.graph import END, StateGraph

from app.contracts import (
    EvidenceBundle, ExtractionResponse, FieldSpec, ProgramSpec, SchemaSpec,
    VerificationIssue, ViewBundle,
)
from app.contracts.builder import (
    BuilderCheckRequest, BuilderCheckResponse, SchemaCollaborationRequest,
    SchemaCollaborationResponse, ValueCollaborationRequest, ValueCollaborationResponse,
)
from app.features.extraction_center.executor import execute_program_spec
from app.features.extraction_center.repository import (
    get_extraction_payload, persist_extraction_state,
)
from app.features.extraction_center.verifier import verify_extraction
from app.features.page_center.collector import collect_page
from app.features.page_center.views import normalize_page_view
from app.features.program_center.plan import (
    build_extraction_plan, build_program_spec, sanitize_candidate_field_programs,
)
from app.platform.config import settings
from app.platform.llm import create_model_adapter
from app.platform.text_processing import normalize_whitespace
from app.platform.tracing.node_runner import run_traced_node

router = APIRouter()


class CollaborationState(TypedDict, total=False):
    task_id: str
    view_bundle: ViewBundle
    schema_spec: SchemaSpec
    field: FieldSpec
    message: str
    guidance_value: str
    evidence_text: str
    result: Any
    program_spec: ProgramSpec
    agent_traces: Annotated[list, operator.add]
    errors: Annotated[list[str], operator.add]
    status: str


def _adapter():
    return create_model_adapter(
        api_key=settings.llm_api_key, base_url=settings.llm_base_url,
        model=settings.llm_model, timeout_seconds=settings.llm_timeout_seconds,
    )


def _snapshot(task_id: str) -> ViewBundle:
    payload = get_extraction_payload(task_id)
    if payload is None:
        raise HTTPException(404, "extraction run not found")
    if not payload.get("view_bundle"):
        raise HTTPException(400, "view_bundle is required for collaboration")
    return ViewBundle.model_validate(payload["view_bundle"])


def _schema_body(state):
    schema = _adapter().revise_field_schema(
        view_bundle=state["view_bundle"],
        current_schema_spec=state["schema_spec"],
        user_message=state["message"],
    )
    if not schema.fields or any(not field.name.strip() for field in schema.fields):
        raise ValueError("schema proposal must contain named fields")
    return {"schema_spec": schema, "status": "completed"}


def _value_body(state):
    view = state["view_bundle"]
    evidence_text = state.get("evidence_text", "").strip()
    if evidence_text and normalize_whitespace(evidence_text) not in normalize_whitespace(view.text):
        raise ValueError("selected evidence is absent from the saved snapshot")
    result, program = _adapter().revise_field_value(
        field=state["field"], view_bundle=view,
        guidance_value=state.get("guidance_value", ""),
        evidence_text=evidence_text,
    )
    safe, issues = sanitize_candidate_field_programs(
        program, schema_spec=SchemaSpec(name="field", fields=[state["field"]]),
    )
    if issues or not any(item.enabled for item in safe):
        raise ValueError("field agent did not produce executable safe rules")
    if result.field_name != state["field"].name:
        raise ValueError("field agent changed field identity")
    for evidence in result.evidence:
        if not evidence.text.strip() or normalize_whitespace(evidence.text) not in normalize_whitespace(view.text):
            raise ValueError("field evidence is absent from the saved snapshot")
        evidence.field_name = state["field"].name
        start = view.text.find(evidence.text)
        evidence.start_char = start if start >= 0 else None
        evidence.end_char = start + len(evidence.text) if start >= 0 else None
    if result.value not in (None, "") and not result.evidence:
        raise ValueError("nonempty field value requires page evidence")
    return {"result": result, "program_spec": ProgramSpec(field_programs=safe), "status": "completed"}


def build_collaboration_graph(kind: str):
    """Separate typed, traced graphs prevent schema and value responsibilities mixing."""
    graph = StateGraph(CollaborationState)
    name = "field_schema_agent_node" if kind == "schema" else "field_value_agent_node"
    body = _schema_body if kind == "schema" else _value_body
    role = "FieldSchemaAgent" if kind == "schema" else "FieldValueAgent"
    graph.add_node(name, lambda state: run_traced_node(state, name=name, role=role, body=body))
    graph.set_entry_point(name)
    graph.add_edge(name, END)
    return graph.compile()


def _invoke(kind: str, state: CollaborationState):
    output = build_collaboration_graph(kind).invoke(state)
    if output.get("status") == "failed":
        detail = "; ".join(output.get("errors", []))
        status = 502 if "provider" in detail.lower() or "http" in detail.lower() else 400
        raise HTTPException(status, detail)
    return output


@router.post("/fields/schema", response_model=SchemaCollaborationResponse)
def collaborate_schema(request: SchemaCollaborationRequest):
    if not request.message.strip():
        raise HTTPException(422, "message is required")
    output = _invoke("schema", {
        "task_id": request.task_id, "view_bundle": _snapshot(request.task_id),
        "schema_spec": request.schema_spec, "message": request.message,
    })
    return SchemaCollaborationResponse(
        task_id=request.task_id, schema_spec=output["schema_spec"],
        agent_traces=output["agent_traces"],
    )


@router.post("/fields/value", response_model=ValueCollaborationResponse)
def collaborate_value(request: ValueCollaborationRequest):
    output = _invoke("value", {
        "task_id": request.task_id, "view_bundle": _snapshot(request.task_id),
        "field": request.field, "guidance_value": request.guidance_value,
        "evidence_text": request.evidence_text,
    })
    return ValueCollaborationResponse(
        task_id=request.task_id, result=output["result"],
        program_spec=output["program_spec"], agent_traces=output["agent_traces"],
        assistant_message="字段值和对应证据已根据当前页面快照更新。",
    )


def _check_page(request: BuilderCheckRequest, view: ViewBundle, *, second: bool = False):
    safe, issues = sanitize_candidate_field_programs(
        request.program_spec, schema_spec=request.schema_spec,
    )
    if issues:
        raise HTTPException(422, "; ".join(issues))
    program = ProgramSpec(field_programs=safe)
    task_id = f"builder-check-{uuid4().hex[:12]}"
    result = execute_program_spec(
        task_id=task_id, schema_spec=request.schema_spec, view_bundle=view,
        program_spec=program, model_adapter=_adapter(), allow_llm_fallback=False,
    )
    report = verify_extraction(
        task_id=task_id, schema_spec=request.schema_spec, extraction_result=result,
    )
    if not second:
        for name, expected in request.expected_values.items():
            field = result.get_field(name)
            value = field.normalized_value if field and field.normalized_value is not None else (field.value if field else None)
            if normalize_whitespace(str(value or "")) != normalize_whitespace(expected):
                report.issues.append(VerificationIssue(
                    field_name=name, code="guidance_mismatch", severity="error",
                    message="当前规则不能重现已确认的字段值，请重新协作此字段。",
                ))
    if any(issue.severity == "error" for issue in report.issues):
        report.passed = False
        report.score = min(report.score, 0.5)
    state = {
        "task_id": task_id, "target_url": view.url, "source_task_id": request.task_id,
        "builder_check": True, "status": "completed",
        "schema_spec": request.schema_spec, "view_bundle": view,
        "program_spec": program, "extraction_result": result,
        "evidence_bundle": EvidenceBundle(
            task_id=task_id, evidences=[e for field in result.fields for e in field.evidence],
        ),
        "verification_report": report, "errors": [], "agent_traces": [],
    }
    persist_extraction_state(state)
    return ExtractionResponse.model_validate(state)


@router.post("/fields/check", response_model=BuilderCheckResponse)
def check_builder(request: BuilderCheckRequest):
    view = _snapshot(request.task_id)
    if request.second_url:
        first, second = urlsplit(view.url), urlsplit(request.second_url.strip())
        if second.scheme not in {"http", "https"} or (first.scheme, first.hostname, first.port) != (second.scheme, second.hostname, second.port):
            raise HTTPException(422, "second URL must use the same origin")
        if second.username or second.password or (
            first.scheme,
            first.netloc,
            first.path,
            first.query,
        ) == (
            second.scheme,
            second.netloc,
            second.path,
            second.query,
        ):
            raise HTTPException(422, "second URL must be a different page without credentials")
    extraction = _check_page(request, view)
    second_page = None
    if request.second_url:
        try:
            second_view = normalize_page_view(collect_page(target_url=request.second_url.strip()))
            second_page = _check_page(request, second_view, second=True)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, f"second-page validation failed: {exc}") from exc
        # A selected generalization check is part of the candidate's save gate.
        if not second_page.verification_report.passed:
            extraction.verification_report.passed = False
            extraction.verification_report.issues.append(VerificationIssue(
                field_name="", code="second_page_failed", severity="error",
                message="同结构第二页未通过验证，当前候选规则不可标记为已验证。",
            ))
            payload = get_extraction_payload(extraction.task_id)
            persist_extraction_state({**payload, "verification_report": extraction.verification_report})
    return BuilderCheckResponse(extraction=extraction, second_page=second_page)
