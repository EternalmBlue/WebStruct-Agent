from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.storage.database import Base


def run_auto_migrations(engine: Engine) -> None:
    """Create and lightly migrate storage tables at application startup.

    The thesis prototype keeps migrations intentionally small and deterministic:
    SQLAlchemy metadata creates missing tables, then this module adds columns
    that may be absent in an older local database.
    """

    import app.storage.orm_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _add_missing_columns(engine)


def _add_missing_columns(engine: Engine) -> None:
    dialect = engine.dialect
    preparer = dialect.identifier_preparer
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_columns = {
            column["name"]
            for column in inspector.get_columns(table.name)
        }
        for column in table.columns:
            if column.name in existing_columns:
                continue
            ddl = (
                f"ALTER TABLE {preparer.quote(table.name)} "
                f"ADD COLUMN {_column_ddl(column, dialect)}"
            )
            with engine.begin() as connection:
                connection.execute(text(ddl))


def _column_ddl(column, dialect) -> str:
    preparer = dialect.identifier_preparer
    compiled_type = column.type.compile(dialect=dialect)
    default = ""
    if column.default is not None and column.default.is_scalar:
        default = f" DEFAULT {_literal_default(column.default.arg)}"
    return f"{preparer.quote(column.name)} {compiled_type}{default}"


def _literal_default(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"
