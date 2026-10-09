from fastapi import APIRouter, HTTPException

from app.contracts import ManualReviewRequest, ManualReviewResponse
from app.features.extraction_center.repository import get_extraction_payload
from app.features.program_center.repository import persist_program_spec
from app.features.review_center.repository import persist_manual_review

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/manual", response_model=ManualReviewResponse)
def submit_manual_review(request: ManualReviewRequest) -> ManualReviewResponse:
    if request.mark_program_verified and request.program_spec is None:
        raise HTTPException(
            status_code=400,
            detail="program_spec is required when mark_program_verified is true",
        )
    if request.mark_program_verified:
        payload = get_extraction_payload(request.task_id)
        report = payload.get("verification_report") if payload else None
        if payload and payload.get("builder_check") and (
            not report or not report.get("passed", False)
        ):
            raise HTTPException(
                status_code=409,
                detail="quality check must pass before a rule can be verified",
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
