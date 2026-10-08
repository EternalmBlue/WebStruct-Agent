from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.contracts import BenchmarkRequest, BenchmarkResponse
from app.features.evaluation_center.repository import get_benchmark_payload
from app.features.evaluation_center.workflow import (
    BENCHMARK_NODE_NAMES,
    run_benchmark_workflow_for_task,
)
from app.platform.observability import runtime

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.post("/run", status_code=202)
def run_benchmark(request: BenchmarkRequest):
    if request.dataset is None or not request.dataset.items:
        raise HTTPException(status_code=422, detail="benchmark requires explicit dataset with Schema per item")
    if any(item.schema_spec is None for item in request.dataset.items):
        raise HTTPException(status_code=422, detail="each benchmark item requires explicit Schema")
    payload = request.model_dump(mode="json")
    receipt = runtime.create("benchmark", BENCHMARK_NODE_NAMES, payload)
    runtime.submit(receipt, lambda task_id: run_benchmark_workflow_for_task(request, task_id))
    return receipt


@router.get("/reports/{task_id}")
def get_benchmark_report(task_id: str):
    snapshot = runtime.snapshot(task_id)
    if snapshot is None:
        payload = get_benchmark_payload(task_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="benchmark report not found")
        return BenchmarkResponse.model_validate(payload)
    payload = runtime.result(task_id)
    if snapshot["status"] not in {"completed", "failed"} or payload is None:
        return JSONResponse(status_code=202, content=snapshot)
    return BenchmarkResponse.model_validate(payload)
