from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.benchmark import router as benchmark_router
from app.api.extraction import router as extraction_router
from app.api.health import router as health_router
from app.api.program_specs import router as program_specs_router
from app.api.review import router as review_router
from app.api.schemas import router as schemas_router
from app.api.spec_assistant import router as spec_assistant_router
from app.core.config import settings
from app.storage import init_storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_storage()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Research prototype for schema-first web information extraction.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(schemas_router, prefix="/api")
    app.include_router(extraction_router, prefix="/api")
    app.include_router(program_specs_router, prefix="/api")
    app.include_router(benchmark_router, prefix="/api")
    app.include_router(review_router, prefix="/api")
    app.include_router(spec_assistant_router, prefix="/api")

    @app.get("/")
    def root() -> dict[str, str]:
        return {"name": settings.app_name, "status": "running"}

    return app


app = create_app()
