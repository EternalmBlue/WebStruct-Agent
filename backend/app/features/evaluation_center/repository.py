"""评测报告仓储：保存一次评测运行的结果，并支持按任务标识回放。

行为契约：specs/features/evaluation-center.feature
"""

from __future__ import annotations

from typing import Any

from app.platform.persistence.json_payloads import jsonable_state
from app.platform.persistence.orm_models import BenchmarkReportRecord
from app.platform.persistence.payload_store import dump_payload, load_payload, session_scope


def persist_benchmark_state(state: dict[str, Any]) -> None:
    """把一次评测运行的结果状态按 task_id 落库。"""
    payload = jsonable_state(state)
    report = state.get("benchmark_report")
    dataset_name = getattr(report, "dataset_name", "") if report else ""
    with session_scope() as session:
        existing = (
            session.query(BenchmarkReportRecord)
            .filter(BenchmarkReportRecord.task_id == state.get("task_id", ""))
            .one_or_none()
        )
        if existing is not None:
            existing.status = state.get("status", "completed")
            existing.dataset_name = dataset_name
            existing.payload_json = dump_payload(payload)
        else:
            session.add(
                BenchmarkReportRecord(
                    task_id=state.get("task_id", ""),
                    dataset_name=dataset_name,
                    status=state.get("status", "completed"),
                    payload_json=dump_payload(payload),
                )
            )


def get_benchmark_payload(task_id: str) -> dict[str, Any] | None:
    """按任务标识读取历史评测报告。"""
    with session_scope() as session:
        record = (
            session.query(BenchmarkReportRecord)
            .filter(BenchmarkReportRecord.task_id == task_id)
            .one_or_none()
        )
        if record is None:
            return None
        return load_payload(record.payload_json)


__all__ = ["get_benchmark_payload", "persist_benchmark_state"]
