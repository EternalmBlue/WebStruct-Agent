from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.platform.browser import browser_status
from app.platform.config import settings
from app.platform.observability import runtime

router = APIRouter(tags=["ops"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    model_mode: str
    llm_configured: bool
    llm_model: str
    database_driver: str
    config_source: str
    config_loaded: bool
    browser: dict[str, object]
    observability: dict[str, object]
    deterministic_extraction_available: bool = True
    model_reachability: str = "unknown"


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        model_mode=settings.model_mode,
        llm_configured=settings.llm_configured,
        llm_model=settings.llm_model,
        database_driver=settings.database_driver,
        config_source="config.toml",
        config_loaded=True,
        browser=browser_status(),
        observability={"available": True, "summary": "/api/observability/summary"},
        deterministic_extraction_available=True,
        model_reachability="configured" if settings.llm_configured else "not_configured",
    )


@router.get("/config")
def public_config():
    return settings.public_config()


@router.get("/runs/{task_id}")
def run_status(task_id: str):
    snapshot = runtime.snapshot(task_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")
    return snapshot


@router.get("/runs/{task_id}/events")
def run_events(task_id: str, after_cursor: int = Query(default=0, ge=0)):
    if runtime.snapshot(task_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    return runtime.events(task_id, after_cursor)


@router.get("/runs/{task_id}/metrics")
def run_metrics(task_id: str):
    snapshot = runtime.snapshot(task_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {key: snapshot.get(key, {}) for key in
            ("task_id", "status", "config_version", "metrics_version", "metrics", "fingerprint")}


@router.get("/observability/summary")
def observability_summary(hours: int = 24):
    return runtime.summary(hours=max(1, min(hours, 24 * 30)))


@router.post("/runs/{task_id}/retry", status_code=202)
def retry_run(task_id: str):
    try:
        receipt = runtime.retry(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    request = runtime.request(task_id)
    if receipt["workflow_type"] == "extraction":
        from app.contracts import ExtractionRequest
        from app.features.extraction_center.workflow import run_extraction_workflow_for_task

        parsed = ExtractionRequest.model_validate(request)
        runtime.submit(
            receipt,
            lambda new_task_id: run_extraction_workflow_for_task(parsed, new_task_id),
        )
    else:
        from app.contracts import BenchmarkRequest
        from app.features.evaluation_center.workflow import run_benchmark_workflow_for_task

        parsed = BenchmarkRequest.model_validate(request)
        runtime.submit(
            receipt,
            lambda new_task_id: run_benchmark_workflow_for_task(parsed, new_task_id),
        )
    receipt.pop("workflow_type", None)
    return receipt
