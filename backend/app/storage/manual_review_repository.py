from __future__ import annotations

import json
from typing import Any

from app.storage.database import SessionLocal, init_storage
from app.storage.orm_models import ManualReviewRecord


def persist_manual_review(review_payload: dict[str, Any]) -> None:
    init_storage()
    with SessionLocal() as session:
        session.add(
            ManualReviewRecord(
                task_id=review_payload.get("task_id", ""),
                schema_name=review_payload.get("schema_name", ""),
                status="reviewed",
                payload_json=json.dumps(review_payload, ensure_ascii=False),
            )
        )
        session.commit()
