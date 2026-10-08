"""pytest 全局约定与共享夹具。

两条硬约定：
1. 测试默认不发起真实 LLM 请求，需要用假适配器的用例自行注入；
2. 需要真实数据库的用例打 `@pytest.mark.db`，数据库不可达时自动跳过。
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest
from app.main import app
from app.platform.config import settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "db: requires a reachable database configured by DATABASE_URL",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _database_available():
        return
    skip_db = pytest.mark.skip(reason="database is not reachable; check DATABASE_URL")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip_db)


def _database_available() -> bool:
    database_url = settings.database_url
    if database_url.startswith("sqlite"):
        return True
    try:
        engine = create_engine(_with_connect_timeout(database_url), pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except (SQLAlchemyError, OSError):
        return False
    return True


def _with_connect_timeout(database_url: str) -> str:
    parts = urlsplit(database_url)
    query = dict(parse_qsl(parts.query))
    query.setdefault("connect_timeout", "2")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@pytest.fixture(autouse=True)
def no_real_llm_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认断开真实模型调用，避免测试依赖外网或真实凭据。"""
    monkeypatch.setattr("app.features.extraction_center.nodes.settings.llm_api_key", None)


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def context() -> dict[str, object]:
    """行为测试在各步骤之间传递中间结果的共享字典。"""
    return {}


@pytest.fixture
def builtin_schema():
    """Compatibility name for legacy scenarios; returns an explicit test schema."""
    from tests.support.samples import sample_schema

    return sample_schema
