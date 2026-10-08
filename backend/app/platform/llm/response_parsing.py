"""模型返回值的解析与净化：只产出受 Schema / ProgramSpec 约束的契约对象。"""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.contracts import SchemaSpec, ViewBundle
from app.platform.llm.protocol import DEFAULT_SCHEMA_FIELD_LIMIT, ModelProviderError
from app.platform.text_processing import normalize_whitespace


def _parse_json_content(response_data: dict[str, object]) -> dict[str, object]:
    try:
        choices = response_data["choices"]
        if not isinstance(choices, list) or not choices:
            raise KeyError("choices")
        message = choices[0]["message"]
        content = message["content"]
    except (KeyError, TypeError) as exc:
        raise ModelProviderError(
            "LLM provider response missing choices[0].message.content"
        ) from exc

    if not isinstance(content, str):
        raise ModelProviderError("LLM provider message content was not text")
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelProviderError("LLM provider did not return valid JSON content") from exc
    if not isinstance(parsed, dict):
        raise ModelProviderError("LLM provider JSON content was not an object")
    return parsed


def _sanitize_schema_spec(candidate: dict[str, object], *, view_bundle: ViewBundle) -> SchemaSpec:
    fields = candidate.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ModelProviderError("LLM schema response did not contain fields")

    normalized_fields: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for field in fields[:DEFAULT_SCHEMA_FIELD_LIMIT]:
        if not isinstance(field, dict):
            continue
        name = _normalize_field_name(field.get("name"))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        field_type = field.get("type")
        if field_type not in {"string", "text", "number", "date", "url", "list"}:
            field_type = "string"
        description = _safe_text(field.get("description")) or name
        normalized_fields.append(
            {
                "name": name,
                "description": description,
                "type": field_type,
                "required": bool(field.get("required", True)),
                "aliases": _safe_text_list(field.get("aliases")),
                "examples": _safe_text_list(field.get("examples")),
            }
        )

    if not normalized_fields:
        raise ModelProviderError("LLM schema response did not contain usable fields")
    if "title" not in {field["name"] for field in normalized_fields} and view_bundle.title:
        normalized_fields.insert(
            0,
            {
                "name": "title",
                "description": "页面标题",
                "type": "text",
                "required": True,
                "aliases": ["标题", "名称"],
                "examples": [view_bundle.title[:120]],
            },
        )

    payload = {
        "name": _safe_text(candidate.get("name")) or _schema_name_from_page(view_bundle),
        "description": _safe_text(candidate.get("description"))
        or "AI 根据当前 URL 页面内容生成的字段契约",
        "domain": _safe_text(candidate.get("domain")) or "auto_inferred",
        "fields": normalized_fields[:DEFAULT_SCHEMA_FIELD_LIMIT],
    }
    try:
        return SchemaSpec.model_validate(payload)
    except ValidationError as exc:
        raise ModelProviderError("LLM schema response failed SchemaSpec validation") from exc


def _schema_name_from_page(view_bundle: ViewBundle) -> str:
    title = _safe_text(view_bundle.title)
    if title:
        return f"自动字段契约 - {title[:24]}"
    return "自动字段契约"


def _normalize_field_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lower().replace("-", "_").replace(" ", "_")
    chars = []
    for index, char in enumerate(cleaned):
        if char == "_" or char.isascii() and char.isalnum():
            chars.append(char)
        elif char.isalnum() and not char.isascii():
            continue
        else:
            chars.append("_")
    normalized = "".join(chars).strip("_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    if not normalized:
        return None
    if normalized[0].isdigit():
        normalized = f"field_{normalized}"
    return normalized[:64]


def _safe_text(value: object, *, max_length: int = 240) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = normalize_whitespace(value)
    return cleaned[:max_length] if cleaned else None


def _safe_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result = [text for item in value if (text := _safe_text(item, max_length=120)) is not None]
    return list(dict.fromkeys(result))[:8]
