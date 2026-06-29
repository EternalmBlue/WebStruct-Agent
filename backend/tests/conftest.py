import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "postgres: requires a reachable PostgreSQL database from DATABASE_URL",
    )


def pytest_collection_modifyitems(config, items) -> None:
    if _postgres_available():
        return
    skip_postgres = pytest.mark.skip(
        reason="PostgreSQL is not reachable; start docker compose postgres to run persistence tests",
    )
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip_postgres)


def _postgres_available() -> bool:
    database_url = os.environ.get("DATABASE_URL", settings.database_url)
    if not database_url.startswith("postgresql"):
        return False
    try:
        engine = create_engine(
            _with_connect_timeout(database_url),
            pool_pre_ping=True,
        )
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except SQLAlchemyError:
        return False


def _with_connect_timeout(database_url: str) -> str:
    parts = urlsplit(database_url)
    query = dict(parse_qsl(parts.query))
    query.setdefault("connect_timeout", "2")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
