from __future__ import annotations

import json
from typing import Any

from app.storage.database import SessionLocal, init_storage
from app.storage.json_payloads import jsonable_state
from app.storage.orm_models import BenchmarkReportRecord


def persist_benchmark_state(state: dict[str, Any]) -> None:
    init_storage()
    payload = jsonable_state(state)
    report = state.get("benchmark_report")
    dataset_name = getattr(report, "dataset_name", "") if report else ""
    with SessionLocal() as session:
        existing = (
            session.query(BenchmarkReportRecord)
            .filter(BenchmarkReportRecord.task_id == state.get("task_id", ""))
            .one_or_none()
        )
        if existing:
            existing.status = state.get("status", "completed")
            existing.dataset_name = dataset_name
            existing.payload_json = json.dumps(payload, ensure_ascii=False)
        else:
            session.add(
                BenchmarkReportRecord(
                    task_id=state.get("task_id", ""),
                    dataset_name=dataset_name,
                    status=state.get("status", "completed"),
                    payload_json=json.dumps(payload, ensure_ascii=False),
                )
            )
        session.commit()


def get_benchmark_payload(task_id: str) -> dict[str, Any] | None:
    init_storage()
    with SessionLocal() as session:
        record = (
            session.query(BenchmarkReportRecord)
            .filter(BenchmarkReportRecord.task_id == task_id)
            .one_or_none()
        )
        if not record:
            return None
        return json.loads(record.payload_json)
