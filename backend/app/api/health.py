from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    model_mode: str
    llm_configured: bool
    llm_model: str
    database_driver: str


@router.get("", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        model_mode=settings.model_mode,
        llm_configured=settings.llm_configured,
        llm_model=settings.llm_model,
        database_driver=settings.database_driver,
    )
