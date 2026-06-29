from collections.abc import Generator
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
_metadata_init_lock = Lock()
_metadata_initialized = False


def init_storage() -> None:
    global _metadata_initialized

    if _metadata_initialized:
        return
    with _metadata_init_lock:
        if _metadata_initialized:
            return
        from app.storage.migrations import run_auto_migrations

        run_auto_migrations(engine)
        _metadata_initialized = True


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
