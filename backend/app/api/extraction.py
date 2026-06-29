from fastapi import APIRouter, HTTPException

from app.domain import ExtractionRequest, ExtractionResponse
from app.extraction.workflow import run_extraction_workflow
from app.storage.extraction_repository import get_extraction_payload

router = APIRouter(prefix="/extract", tags=["extraction"])


@router.post("", response_model=ExtractionResponse)
def extract(request: ExtractionRequest) -> ExtractionResponse:
    state = run_extraction_workflow(request)
    if state.get("errors") or state.get("schema_spec") is None:
        raise HTTPException(
            status_code=400,
            detail="；".join(state.get("errors", [])) or "extraction workflow failed",
        )
    return ExtractionResponse(
        task_id=state["task_id"],
        status=state.get("status", "completed"),
        schema_spec=state["schema_spec"],
        schema_version=state.get("schema_version"),
        schema_generation_mode=state.get("schema_generation_mode", "unknown"),
        schema_generation_error=state.get("schema_generation_error"),
        page_observation=state.get("page_observation"),
        view_bundle=state.get("view_bundle"),
        extraction_plan=state.get("extraction_plan"),
        program_spec=state.get("program_spec"),
        program_reused=state.get("program_reused", False),
        program_generation_mode=state.get("program_generation_mode", "unknown"),
        program_generation_error=state.get("program_generation_error"),
        extraction_result=state.get("extraction_result"),
        evidence_bundle=state.get("evidence_bundle"),
        verification_report=state.get("verification_report"),
        repair_attempts=state.get("repair_attempts", 0),
        agent_traces=state.get("agent_traces", []),
        errors=state.get("errors", []),
    )


@router.get("/{task_id}", response_model=ExtractionResponse)
def get_extraction_run(task_id: str) -> ExtractionResponse:
    payload = get_extraction_payload(task_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="extraction run not found")
    return ExtractionResponse.model_validate(payload)
