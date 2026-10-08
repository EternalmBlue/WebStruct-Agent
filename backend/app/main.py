from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.features import feature_centers, register_feature_routers
from app.platform.config import settings
from app.platform.persistence import init_storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_storage()
    from app.platform.observability import runtime

    runtime.recover_interrupted()
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

    # 全部对外能力由功能中心提供，路由登记见 specs/feature-centers.md
    register_feature_routers(app, prefix="/api")

    @app.get("/")
    def root() -> dict[str, object]:
        return {
            "name": settings.app_name,
            "status": "running",
            "feature_centers": [center.key for center in feature_centers()],
        }

    return app


app = create_app()
