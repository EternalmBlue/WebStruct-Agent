"""人工复核仓储：记录每一次人工复核结论。

行为契约：specs/features/review-center.feature
"""

from __future__ import annotations

from typing import Any

from app.platform.persistence.orm_models import ManualReviewRecord
from app.platform.persistence.payload_store import dump_payload, session_scope


def persist_manual_review(review_payload: dict[str, Any]) -> None:
    """写入一条人工复核记录（追加语义，不做覆盖）。"""
    with session_scope() as session:
        session.add(
            ManualReviewRecord(
                task_id=review_payload.get("task_id", ""),
                schema_name=review_payload.get("schema_name", ""),
                status="reviewed",
                payload_json=dump_payload(review_payload),
            )
        )


__all__ = ["persist_manual_review"]
