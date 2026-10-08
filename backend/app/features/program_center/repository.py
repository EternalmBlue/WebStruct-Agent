"""已验证 ProgramSpec 仓储：登记、按 Schema 签名复用、按验证状态列举。

行为契约：specs/features/program-center.feature
"""

from __future__ import annotations

from app.contracts import PageStructureSignature, ProgramSpec, SchemaSpec, StructureCompatibility
from app.features.program_center.compatibility import compare_structure_signatures
from app.features.schema_center.repository import persist_schema_version, schema_signature
from app.platform.persistence.orm_models import ProgramSpecRecord
from app.platform.persistence.payload_store import dump_payload, load_payload, session_scope


def persist_program_spec(
    *,
    schema_spec: SchemaSpec,
    program_spec: ProgramSpec,
    user_verified: bool,
    rule_name: str = "",
    page_structure_signature: PageStructureSignature | None = None,
) -> None:
    """登记（或刷新）一条 ProgramSpec 记录，并同步其 Schema 版本。"""
    persist_schema_version(schema_spec=schema_spec, source="program_spec")
    signature = schema_signature(schema_spec)
    display_name = rule_name.strip() or schema_spec.name
    payload = {
        "schema_spec": schema_spec.model_dump(mode="json"),
        "program_spec": program_spec.model_dump(mode="json"),
        "user_verified": user_verified,
        "rule_name": display_name,
        "page_structure_signature": (
            page_structure_signature.model_dump(mode="json")
            if page_structure_signature is not None
            else None
        ),
    }
    with session_scope() as session:
        existing = (
            session.query(ProgramSpecRecord)
            .filter(ProgramSpecRecord.schema_signature == signature)
            .one_or_none()
        )
        if existing is not None:
            existing.schema_name = schema_spec.name
            existing.user_verified = 1 if user_verified else 0
            if page_structure_signature is None:
                previous_payload = load_payload(existing.payload_json)
                payload["page_structure_signature"] = previous_payload.get(
                    "page_structure_signature"
                )
            existing.payload_json = dump_payload(payload)
        else:
            session.add(
                ProgramSpecRecord(
                    schema_signature=signature,
                    schema_name=schema_spec.name,
                    user_verified=1 if user_verified else 0,
                    payload_json=dump_payload(payload),
                )
            )


def get_user_verified_program_spec(
    schema_spec: SchemaSpec,
    *,
    page_structure_signature: PageStructureSignature | None = None,
) -> ProgramSpec | None:
    """读取该 Schema 对应的、已被人工验证过的 ProgramSpec。"""
    signature = schema_signature(schema_spec)
    with session_scope() as session:
        record = (
            session.query(ProgramSpecRecord)
            .filter(
                ProgramSpecRecord.schema_signature == signature,
                ProgramSpecRecord.user_verified == 1,
            )
            .one_or_none()
        )
        if record is None:
            return None
        payload = load_payload(record.payload_json)
        stored_signature = payload.get("page_structure_signature")
        if page_structure_signature is not None:
            if not stored_signature:
                return None
            compatibility = compare_structure_signatures(
                PageStructureSignature.model_validate(stored_signature),
                page_structure_signature,
            )
            if compatibility.status != "compatible":
                return None
        return ProgramSpec.model_validate(payload["program_spec"])


def resolve_user_verified_program_spec(
    schema_spec: SchemaSpec,
    *,
    page_structure_signature: PageStructureSignature | None,
) -> tuple[ProgramSpec | None, StructureCompatibility]:
    """Return a verified program and an explicit reuse decision."""

    signature = schema_signature(schema_spec)
    with session_scope() as session:
        record = (
            session.query(ProgramSpecRecord)
            .filter(
                ProgramSpecRecord.schema_signature == signature,
                ProgramSpecRecord.user_verified == 1,
            )
            .one_or_none()
        )
        if record is None:
            return None, StructureCompatibility(status="unknown", reasons=["no_verified_program"])
        payload = load_payload(record.payload_json)
        stored_signature = payload.get("page_structure_signature")
        if page_structure_signature is None or not stored_signature:
            return None, StructureCompatibility(status="unknown", reasons=["missing_structure_signature"])
        compatibility = compare_structure_signatures(
            PageStructureSignature.model_validate(stored_signature),
            page_structure_signature,
        )
        if compatibility.status != "compatible":
            return None, compatibility
        return ProgramSpec.model_validate(payload["program_spec"]), compatibility


def list_user_verified_program_specs() -> list[dict[str, object]]:
    """列出所有已验证 ProgramSpec 的摘要（前端复用面板使用）。"""
    with session_scope() as session:
        records = (
            session.query(ProgramSpecRecord)
            .filter(ProgramSpecRecord.user_verified == 1)
            .order_by(ProgramSpecRecord.id.desc())
            .all()
        )
        items: list[dict[str, object]] = []
        for record in records:
            payload = load_payload(record.payload_json)
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
                    "page_structure_signature": payload.get("page_structure_signature"),
                    "created_at": record.created_at.isoformat(),
                }
            )
        return items


__all__ = [
    "get_user_verified_program_spec",
    "list_user_verified_program_specs",
    "persist_program_spec",
    "resolve_user_verified_program_spec",
]
