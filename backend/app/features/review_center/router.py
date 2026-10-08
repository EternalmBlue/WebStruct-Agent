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

    persist_manual_review(request.model_dump(mode="json"))
    if request.mark_program_verified and request.program_spec is not None:
        extraction_payload = get_extraction_payload(request.task_id) or {}
        signature_payload = extraction_payload.get("page_structure_signature")
        from app.contracts import PageStructureSignature

        persist_program_spec(
            schema_spec=request.schema_spec,
            program_spec=request.program_spec,
            user_verified=True,
            rule_name=request.rule_name,
            page_structure_signature=(
                PageStructureSignature.model_validate(signature_payload)
                if signature_payload
                else None
            ),
        )

    return ManualReviewResponse(
        task_id=request.task_id,
        status="reviewed",
        program_verified=request.mark_program_verified,
        field_count=len(request.fields),
    )
