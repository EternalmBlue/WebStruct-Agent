from __future__ import annotations

import json

from app.domain import ProgramSpec, SchemaSpec
from app.storage.database import SessionLocal, init_storage
from app.storage.orm_models import ProgramSpecRecord
from app.storage.schema_repository import persist_schema_version, schema_signature


def persist_program_spec(
    *,
    schema_spec: SchemaSpec,
    program_spec: ProgramSpec,
    user_verified: bool,
    rule_name: str = "",
) -> None:
    init_storage()
    persist_schema_version(schema_spec=schema_spec, source="program_spec")
    signature = schema_signature(schema_spec)
    display_name = rule_name.strip() or schema_spec.name
    payload = {
        "schema_spec": schema_spec.model_dump(mode="json"),
        "program_spec": program_spec.model_dump(mode="json"),
        "user_verified": user_verified,
        "rule_name": display_name,
    }
    with SessionLocal() as session:
        existing = (
            session.query(ProgramSpecRecord)
            .filter(ProgramSpecRecord.schema_signature == signature)
            .one_or_none()
        )
        if existing:
            existing.schema_name = schema_spec.name
            existing.user_verified = 1 if user_verified else 0
            existing.payload_json = json.dumps(payload, ensure_ascii=False)
        else:
            session.add(
                ProgramSpecRecord(
                    schema_signature=signature,
                    schema_name=schema_spec.name,
                    user_verified=1 if user_verified else 0,
                    payload_json=json.dumps(payload, ensure_ascii=False),
                )
            )
        session.commit()


def get_user_verified_program_spec(schema_spec: SchemaSpec) -> ProgramSpec | None:
    init_storage()
    signature = schema_signature(schema_spec)
    with SessionLocal() as session:
        record = (
            session.query(ProgramSpecRecord)
            .filter(
                ProgramSpecRecord.schema_signature == signature,
                ProgramSpecRecord.user_verified == 1,
            )
            .one_or_none()
        )
        if not record:
            return None
        payload = json.loads(record.payload_json)
        return ProgramSpec.model_validate(payload["program_spec"])


def list_user_verified_program_specs() -> list[dict[str, object]]:
    init_storage()
    with SessionLocal() as session:
        records = (
            session.query(ProgramSpecRecord)
            .filter(ProgramSpecRecord.user_verified == 1)
            .order_by(ProgramSpecRecord.id.desc())
            .all()
        )
        items: list[dict[str, object]] = []
        for record in records:
            payload = json.loads(record.payload_json)
            program_payload = payload.get("program_spec") or {}
            field_programs = program_payload.get("field_programs") or []
            schema_payload = payload.get("schema_spec") or {}
            items.append(
                {
                    "schema_signature": record.schema_signature,
                    "schema_name": record.schema_name,
                    "rule_name": payload.get("rule_name") or record.schema_name,
                    "schema_spec": schema_payload,
                    "program_count": len(field_programs),
                    "created_at": record.created_at.isoformat(),
                }
            )
        return items
