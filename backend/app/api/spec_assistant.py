from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.domain import (
    SpecAssistantRequest,
    SpecAssistantResponse,
    ViewBundle,
)
from app.extraction.model_adapters import (
    MissingModelConfigurationError,
    ModelProviderError,
    create_model_adapter,
)
from app.extraction.planner import build_extraction_plan, build_program_spec
from app.storage.extraction_repository import get_extraction_payload

router = APIRouter(prefix="/spec-assistant", tags=["spec-assistant"])


@router.post("/revise", response_model=SpecAssistantResponse)
def revise_spec(request: SpecAssistantRequest) -> SpecAssistantResponse:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    payload = get_extraction_payload(request.task_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="extraction run not found")

    view_bundle_payload = payload.get("view_bundle")
    if not view_bundle_payload:
        raise HTTPException(status_code=400, detail="view_bundle is required for spec collaboration")
    view_bundle = ViewBundle.model_validate(view_bundle_payload)

    fallback_program_spec = request.program_spec
    if fallback_program_spec is None:
        fallback_program_spec = build_program_spec(build_extraction_plan(request.schema_spec))

    adapter = create_model_adapter(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    try:
        (
            assistant_message,
            schema_spec,
            program_spec,
            change_summary,
            validation_issues,
        ) = adapter.revise_schema_and_program_spec(
            user_message=request.message,
            current_schema_spec=request.schema_spec,
            current_program_spec=request.program_spec,
            fallback_program_spec=fallback_program_spec,
            view_bundle=view_bundle,
        )
    except MissingModelConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ModelProviderError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return SpecAssistantResponse(
        task_id=request.task_id,
        assistant_message=assistant_message,
        schema_spec=schema_spec,
        program_spec=program_spec,
        change_summary=change_summary,
        validation_issues=validation_issues,
    )
