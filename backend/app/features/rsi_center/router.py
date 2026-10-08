from fastapi import APIRouter, HTTPException

from app.contracts import RSIIterationRequest, RSIIterationResponse
from app.contracts.rsi import RSIRollbackRequest
from app.features.rsi_center.repository import get_iteration
from app.features.rsi_center.service import evaluate_iteration, rollback_iteration

router = APIRouter(prefix="/rsi", tags=["rsi"])


@router.post("/iterations", status_code=201, response_model=RSIIterationResponse)
def create_iteration(request: RSIIterationRequest):
    try:
        return evaluate_iteration(request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/iterations/{iteration_id}", response_model=RSIIterationResponse)
def read_iteration(iteration_id: str):
    payload = get_iteration(iteration_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="iteration not found")
    return payload


@router.post("/iterations/{iteration_id}/rollback", response_model=RSIIterationResponse)
def rollback(iteration_id: str, request: RSIRollbackRequest):
    try:
        return rollback_iteration(iteration_id, request.reason)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
