"""抽取运行仓储：保存一次抽取的完整状态，并支持按任务标识回放。

行为契约：specs/features/extraction-center.feature
"""

from __future__ import annotations

from typing import Any

from app.platform.persistence.json_payloads import jsonable_state
from app.platform.persistence.orm_models import ExtractionRunRecord
from app.platform.persistence.payload_store import dump_payload, load_payload, session_scope


def persist_extraction_state(state: dict[str, Any]) -> None:
    """把一次抽取的结果状态按 task_id 落库（同 task_id 覆盖）。"""
    payload = jsonable_state(state)
    with session_scope() as session:
        existing = (
            session.query(ExtractionRunRecord)
            .filter(ExtractionRunRecord.task_id == state.get("task_id", ""))
            .one_or_none()
        )
        if existing is not None:
            existing.status = state.get("status", "completed")
            existing.target_url = state.get("target_url", "")
            existing.payload_json = dump_payload(payload)
        else:
            session.add(
                ExtractionRunRecord(
                    task_id=state.get("task_id", ""),
                    target_url=state.get("target_url", ""),
                    status=state.get("status", "completed"),
                    payload_json=dump_payload(payload),
                )
            )


def get_extraction_payload(task_id: str) -> dict[str, Any] | None:
    """按任务标识读取历史抽取结果。"""
    with session_scope() as session:
        record = (
            session.query(ExtractionRunRecord)
            .filter(ExtractionRunRecord.task_id == task_id)
            .one_or_none()
        )
        if record is None:
            return None
        return load_payload(record.payload_json)


__all__ = ["get_extraction_payload", "persist_extraction_state"]
