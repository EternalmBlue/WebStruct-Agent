from __future__ import annotations

import json
from typing import Any

from app.storage.database import SessionLocal, init_storage
from app.storage.json_payloads import jsonable_state
from app.storage.orm_models import ExtractionRunRecord


def persist_extraction_state(state: dict[str, Any]) -> None:
    init_storage()
    payload = jsonable_state(state)
    with SessionLocal() as session:
        existing = (
            session.query(ExtractionRunRecord)
            .filter(ExtractionRunRecord.task_id == state.get("task_id", ""))
            .one_or_none()
        )
        if existing:
            existing.status = state.get("status", "completed")
            existing.target_url = state.get("target_url", "")
            existing.payload_json = json.dumps(payload, ensure_ascii=False)
        else:
            session.add(
                ExtractionRunRecord(
                    task_id=state.get("task_id", ""),
                    target_url=state.get("target_url", ""),
                    status=state.get("status", "completed"),
                    payload_json=json.dumps(payload, ensure_ascii=False),
                )
            )
        session.commit()


def get_extraction_payload(task_id: str) -> dict[str, Any] | None:
    init_storage()
    with SessionLocal() as session:
        record = (
            session.query(ExtractionRunRecord)
            .filter(ExtractionRunRecord.task_id == task_id)
            .one_or_none()
        )
        if not record:
            return None
        return json.loads(record.payload_json)
