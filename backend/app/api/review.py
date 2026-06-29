from fastapi import APIRouter, HTTPException

from app.domain import ManualReviewRequest, ManualReviewResponse
from app.storage.manual_review_repository import persist_manual_review
from app.storage.program_repository import persist_program_spec

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/manual", response_model=ManualReviewResponse)
def submit_manual_review(request: ManualReviewRequest) -> ManualReviewResponse:
    if request.mark_program_verified and request.program_spec is None:
        raise HTTPException(
            status_code=400,
            detail="program_spec is required when mark_program_verified is true",
        )

    persist_manual_review(request.model_dump(mode="json"))
    if request.mark_program_verified and request.program_spec is not None:
        persist_program_spec(
            schema_spec=request.schema_spec,
            program_spec=request.program_spec,
            user_verified=True,
            rule_name=request.rule_name,
        )

    return ManualReviewResponse(
        task_id=request.task_id,
        status="reviewed",
        program_verified=request.mark_program_verified,
        field_count=len(request.fields),
    )
