from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from sqlalchemy import func

from app.domain import SchemaSpec
from app.storage.database import SessionLocal, init_storage
from app.storage.orm_models import SchemaVersionRecord


def schema_signature(schema_spec: SchemaSpec) -> str:
    payload = schema_spec.model_dump(mode="json")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def persist_schema_version(
    *,
    schema_spec: SchemaSpec,
    source: str = "runtime",
) -> dict[str, Any]:
    init_storage()
    signature = schema_signature(schema_spec)
    payload = {
        "schema_spec": schema_spec.model_dump(mode="json"),
        "schema_signature": signature,
        "source": source,
    }
    with SessionLocal() as session:
        existing = (
            session.query(SchemaVersionRecord)
            .filter(SchemaVersionRecord.schema_signature == signature)
            .one_or_none()
        )
        if existing:
            existing.schema_name = schema_spec.name
            existing.source = source
            existing.payload_json = json.dumps(payload, ensure_ascii=False)
            record = existing
        else:
            max_version = (
                session.query(func.max(SchemaVersionRecord.version))
                .filter(SchemaVersionRecord.schema_name == schema_spec.name)
                .scalar()
                or 0
            )
            record = SchemaVersionRecord(
                schema_signature=signature,
                schema_name=schema_spec.name,
                version=max_version + 1,
                source=source,
                payload_json=json.dumps(payload, ensure_ascii=False),
            )
            session.add(record)
        session.commit()
        return {
            "schema_signature": signature,
            "schema_name": schema_spec.name,
            "version": record.version,
            "source": source,
        }


def get_schema_versions(schema_name: str | None = None) -> list[dict[str, Any]]:
    init_storage()
    with SessionLocal() as session:
        query = session.query(SchemaVersionRecord)
        if schema_name:
            query = query.filter(SchemaVersionRecord.schema_name == schema_name)
        records = query.order_by(SchemaVersionRecord.id.asc()).all()
        versions: list[dict[str, Any]] = []
        for record in records:
            payload = json.loads(record.payload_json)
            versions.append(
                {
                    "schema_signature": record.schema_signature,
                    "schema_name": record.schema_name,
                    "version": record.version,
                    "source": record.source,
                    "schema_spec": payload["schema_spec"],
                    "created_at": record.created_at.isoformat(),
                }
            )
        return versions
