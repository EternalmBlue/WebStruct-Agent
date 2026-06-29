from fastapi import APIRouter, HTTPException

from app.benchmark.workflow import run_benchmark_workflow
from app.domain import BenchmarkRequest, BenchmarkResponse
from app.storage.benchmark_repository import get_benchmark_payload

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.post("/run", response_model=BenchmarkResponse)
def run_benchmark(request: BenchmarkRequest) -> BenchmarkResponse:
    state = run_benchmark_workflow(request)
    return BenchmarkResponse(
        task_id=state["task_id"],
        status=state.get("status", "completed"),
        benchmark_report=state.get("benchmark_report"),
        agent_traces=state.get("agent_traces", []),
        errors=state.get("errors", []),
    )


@router.get("/reports/{task_id}", response_model=BenchmarkResponse)
def get_benchmark_report(task_id: str) -> BenchmarkResponse:
    payload = get_benchmark_payload(task_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="benchmark report not found")
    return BenchmarkResponse.model_validate(payload)
