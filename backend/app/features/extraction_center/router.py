from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.contracts import ExtractionRequest, ExtractionResponse
from app.features.extraction_center.repository import get_extraction_payload
from app.features.extraction_center.workflow import (
    EXTRACTION_NODE_NAMES,
    run_extraction_workflow_for_task,
)
from app.platform.observability import runtime

router = APIRouter(prefix="/extract", tags=["extraction"])


@router.post("", status_code=202)
def extract(request: ExtractionRequest):
    if not request.target_url.strip() and not (request.html or "").strip():
        raise HTTPException(status_code=422, detail="target_url or html is required")
    if request.force_builtin_schema:
        raise HTTPException(status_code=422, detail="system builtin schemas are disabled")
    if request.program_spec_mode == "run_verified" and request.schema_spec is None:
        raise HTTPException(status_code=422, detail="run_verified requires schema_spec")
    payload = request.model_dump(mode="json")
    receipt = runtime.create("extraction", EXTRACTION_NODE_NAMES + ["result_persist_node"], payload)
    runtime.submit(
        receipt,
        lambda task_id: run_extraction_workflow_for_task(request, task_id),
    )
    return receipt


@router.get("/{task_id}")
def get_extraction_run(task_id: str):
    snapshot = runtime.snapshot(task_id)
    if snapshot is None:
        payload = get_extraction_payload(task_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="extraction run not found")
        return ExtractionResponse.model_validate(payload)
    payload = runtime.result(task_id)
    if snapshot["status"] not in {"completed", "failed"} or payload is None:
        return JSONResponse(status_code=202, content=snapshot)
    return ExtractionResponse.model_validate(payload)
