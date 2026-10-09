from fastapi import APIRouter, HTTPException

from app.contracts import (
    FieldExtractionResult,
    FieldValueAssistRequest,
    FieldValueAssistResponse,
    FieldProgramSpec,
    ProgramSpec,
    SchemaSpec,
    SpecAssistantRequest,
    SpecAssistantResponse,
    ViewBundle,
)
from app.features.extraction_center.repository import get_extraction_payload
from app.features.program_center.plan import (
    build_extraction_plan,
    build_program_spec,
    sanitize_candidate_field_programs,
)
from app.features.program_center.quality import validate_page_program
from app.platform.config import settings
from app.platform.llm import (
    MissingModelConfigurationError,
    ModelProviderError,
    create_model_adapter,
)

router = APIRouter(prefix="/spec-assistant", tags=["spec-assistant"])

from app.features.spec_assistant_center.builder import router as builder_router


def _sanitize_program(
    *,
    program_spec: ProgramSpec,
    schema_spec: SchemaSpec,
    fallback_program_spec: ProgramSpec,
) -> tuple[ProgramSpec, list[str]]:
    """把模型给出的 ProgramSpec 收敛到白名单策略内，并补充确定性兜底程序。

    ProgramSpec 的安全边界不能只依赖模型自觉：这里用 Unicode 以内的
    确定性程序做兜底，任何不受支持的策略都会被丢弃并上报。
    """
    safe_programs, issues = sanitize_candidate_field_programs(
        program_spec,
        schema_spec=schema_spec,
    )
    merged: list[FieldProgramSpec] = list(safe_programs)
    covered = {program.field_name for program in safe_programs}
    for program in fallback_program_spec.field_programs:
        if program.field_name not in covered:
            merged.append(program)
    return ProgramSpec(field_programs=merged), issues


@router.post("/revise", response_model=SpecAssistantResponse)
def revise_spec(request: SpecAssistantRequest) -> SpecAssistantResponse:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    payload = get_extraction_payload(request.task_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="extraction run not found")

    view_bundle_payload = payload.get("view_bundle")
    if not view_bundle_payload:
        raise HTTPException(
            status_code=400, detail="view_bundle is required for spec collaboration"
        )
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

    # 安全边界：不论模型返回什么，对外只允许受支持的策略
    program_spec, safety_issues = _sanitize_program(
        program_spec=program_spec,
        schema_spec=schema_spec,
        fallback_program_spec=fallback_program_spec,
    )
    validation_issues = [*validation_issues, *safety_issues]
    program_spec, page_issues = validate_page_program(program_spec, view_bundle.raw_html)
    validation_issues.extend(
        f"{issue['field']}: {issue['reason']} ({issue['selector']})"
        for issue in page_issues
    )

    return SpecAssistantResponse(
        task_id=request.task_id,
        assistant_message=assistant_message,
        schema_spec=schema_spec,
        program_spec=program_spec,
        change_summary=change_summary,
        validation_issues=validation_issues,
    )


@router.post("/field-value", response_model=FieldValueAssistResponse)
def assist_field_value(request: FieldValueAssistRequest) -> FieldValueAssistResponse:
    """Run the value agent for one field against the existing page snapshot.

    The snapshot is immutable for this task. A field retry therefore cannot
    accidentally trigger a new browser read or change the schema agent's work.
    """
    payload = get_extraction_payload(request.task_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="extraction run not found")

    view_bundle_payload = payload.get("view_bundle")
    if not view_bundle_payload:
        raise HTTPException(status_code=400, detail="view_bundle is required")
    view_bundle = ViewBundle.model_validate(view_bundle_payload)

    field = request.field.model_copy(
        update={
            "description": (
                f"{request.field.description}\n"
                f"Reference value from the current page: {request.guidance_value[:1000]}"
            ).strip()
        }
    )
    adapter = create_model_adapter(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    try:
        value, evidence = adapter.extract_field(
            field,
            view_bundle,
            guidance_value=request.guidance_value,
        )
    except MissingModelConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ModelProviderError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    result = FieldExtractionResult(
        field_name=request.field_name,
        value=value,
        normalized_value=value,
        confidence=evidence.score if evidence else 0.0,
        evidence=[evidence] if evidence else [],
        strategy="llm_fallback" if evidence else "none",
        status="extracted" if value not in (None, "") else "missing",
    )
    return FieldValueAssistResponse(
        task_id=request.task_id,
        field_name=request.field_name,
        result=result,
        assistant_message=(
            "已根据当前页面快照和引导值重试该字段。"
            if value not in (None, "")
            else "当前页面快照没有找到足够证据，已保留字段为未命中。"
        ),
    )


router.include_router(builder_router)
