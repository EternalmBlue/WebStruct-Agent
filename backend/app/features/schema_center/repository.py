"""Schema 版本仓储：负责 Schema 签名、版本登记与版本查询。

行为契约：specs/features/schema-center.feature
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from sqlalchemy import func

from app.contracts import SchemaSpec
from app.platform.persistence.orm_models import SchemaVersionRecord
from app.platform.persistence.payload_store import dump_payload, load_payload, session_scope


def schema_signature(schema_spec: SchemaSpec) -> str:
    """Schema 的内容指纹：同一个 SchemaSpec 永远得到同一个签名。"""
    canonical = json_canonical(schema_spec.model_dump(mode="json"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def json_canonical(payload: dict[str, Any]) -> str:
    """生成与键顺序无关的规范 JSON，避免字段顺序变化导致签名漂移。"""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def persist_schema_version(
    *,
    schema_spec: SchemaSpec,
    source: str = "runtime",
) -> dict[str, Any]:
    """登记（或刷新）一条 Schema 版本记录，并返回版本摘要。"""
    signature = schema_signature(schema_spec)
    payload = {
        "schema_spec": schema_spec.model_dump(mode="json"),
        "schema_signature": signature,
        "source": source,
    }
    with session_scope() as session:
        existing = (
            session.query(SchemaVersionRecord)
            .filter(SchemaVersionRecord.schema_signature == signature)
            .one_or_none()
        )
        if existing is not None:
            existing.schema_name = schema_spec.name
            existing.source = source
            existing.payload_json = dump_payload(payload)
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
                payload_json=dump_payload(payload),
            )
            session.add(record)
            session.flush()
        return {
            "schema_signature": signature,
            "schema_name": schema_spec.name,
            "version": record.version,
            "source": source,
        }


def get_schema_versions(schema_name: str | None = None) -> list[dict[str, Any]]:
    """列出 Schema 版本记录，可按 Schema 名称过滤。"""
    with session_scope() as session:
        query = session.query(SchemaVersionRecord)
        if schema_name:
            query = query.filter(SchemaVersionRecord.schema_name == schema_name)
        records = query.order_by(SchemaVersionRecord.id.asc()).all()
        versions: list[dict[str, Any]] = []
        for record in records:
            payload = load_payload(record.payload_json)
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


__all__ = ["get_schema_versions", "json_canonical", "persist_schema_version", "schema_signature"]
