from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.database import Base


class ExtractionRunRecord(Base):
    __tablename__ = "extraction_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    target_url: Mapped[str] = mapped_column(String(2048), default="")
    status: Mapped[str] = mapped_column(String(32), default="completed")
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BenchmarkReportRecord(Base):
    __tablename__ = "benchmark_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    dataset_name: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="completed")
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SchemaVersionRecord(Base):
    __tablename__ = "schema_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    schema_signature: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    schema_name: Mapped[str] = mapped_column(String(256), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(64), default="runtime")
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProgramSpecRecord(Base):
    __tablename__ = "program_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    schema_signature: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    schema_name: Mapped[str] = mapped_column(String(256), default="")
    user_verified: Mapped[int] = mapped_column(Integer, default=0)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ManualReviewRecord(Base):
    __tablename__ = "manual_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    schema_name: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="reviewed")
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
