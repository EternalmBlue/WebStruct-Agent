"""OpenAI 兼容 Chat Completions 适配器，默认对接 DeepSeek。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx

from app.contracts import (
    ExtractionPlan,
    FieldEvidence,
    FieldExtractionResult,
    FieldSpec,
    ProgramSpec,
    SchemaSpec,
    ViewBundle,
)
from app.features.program_center.plan import (
    build_extraction_plan,
    build_program_spec,
    build_safe_program_spec_from_candidate,
    merge_program_specs,
    sanitize_candidate_field_programs,
)
from app.platform.configuration import settings
from app.platform.dom import page_context
from app.platform.llm.protocol import (
    MAX_LLM_TEXT_CHARS,
    MAX_PROGRAMMER_HTML_CHARS,
    MAX_PROGRAMMER_TEXT_CHARS,
    MAX_SCHEMA_LINES,
    MAX_SCHEMA_TEXT_CHARS,
    ModelProviderError,
)
from app.platform.llm.response_parsing import (
    _parse_json_content,
    _safe_text,
    _safe_text_list,
    _sanitize_schema_spec,
)
from app.platform.observability.telemetry import model_context, model_operation, observe
from app.platform.text_processing import bounded_snippet, normalize_date, normalize_whitespace


@dataclass
class OpenAICompatibleModelAdapter:
    """OpenAI-compatible chat-completions adapter, configured for DeepSeek by default."""

    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    timeout_seconds: float = 30.0

    def extract_record(self, *, view_bundle: ViewBundle) -> dict[str, object]:
        """Direct-LLM baseline: one generic record call, with no target schema."""
        payload = self._build_record_payload(view_bundle=view_bundle)
        with model_operation("record_extraction"):
            response_data = self._post_chat_completion(payload)
        parsed = _parse_json_content(response_data)
        record = parsed.get("record", parsed)
        if not isinstance(record, dict):
            raise ModelProviderError("direct LLM record was not a JSON object")
        evidence = parsed.get("evidence", {})
        return {
            "record": {
                str(key): value
                for key, value in record.items()
                if isinstance(key, str) and key and key != "evidence"
            },
            "evidence": evidence if isinstance(evidence, dict) else {},
        }

    def generate_schema_spec(
        self,
        *,
        view_bundle: ViewBundle,
    ) -> SchemaSpec:
        payload = self._build_schema_spec_payload(view_bundle=view_bundle)
        with model_operation("schema_generation"):
            response_data = self._post_chat_completion(payload)
        parsed = _parse_json_content(response_data)
        return _sanitize_schema_spec(parsed, view_bundle=view_bundle)

    def generate_program_spec(
        self,
        *,
        schema_spec: SchemaSpec,
        extraction_plan: ExtractionPlan,
        view_bundle: ViewBundle,
        fallback_program_spec: ProgramSpec,
    ) -> ProgramSpec:
        payload = self._build_program_spec_payload(
            schema_spec=schema_spec,
            extraction_plan=extraction_plan,
            view_bundle=view_bundle,
        )
        with model_operation("program_generation"):
            response_data = self._post_chat_completion(payload)
        parsed = _parse_json_content(response_data)
        return build_safe_program_spec_from_candidate(
            parsed,
            fallback_program_spec=fallback_program_spec,
            schema_spec=schema_spec,
        )

    def extract_field(
        self,
        field: FieldSpec,
        view_bundle: ViewBundle,
        guidance_value: str = "",
    ) -> tuple[str | None, FieldEvidence | None]:
        payload = self._build_payload(field, view_bundle, guidance_value=guidance_value)
        with model_operation("field_extraction", field.name):
            response_data = self._post_chat_completion(payload)
        parsed = _parse_json_content(response_data)
        if parsed.get("abstain") is True:
            return None, None

        value = parsed.get("value")
        if value in (None, ""):
            return None, None
        value = normalize_whitespace(str(value))
        if field.type == "date":
            value = normalize_date(value)

        evidence_text = normalize_whitespace(str(parsed.get("evidence_text") or value))
        text = view_bundle.text
        start = text.find(evidence_text)
        if start < 0:
            start = text.find(value)
            if start >= 0:
                evidence_text = bounded_snippet(text, start, start + len(value))
        if start < 0:
            start_char = None
            end_char = None
        else:
            start_char = start
            end_char = start + len(evidence_text)

        confidence = parsed.get("confidence", 0.55)
        try:
            score = float(confidence)
        except (TypeError, ValueError):
            score = 0.55
        return value, FieldEvidence(
            field_name=field.name,
            source="llm_fallback",
            text=evidence_text,
            start_char=start_char,
            end_char=end_char,
            score=max(0.0, min(1.0, score)),
        )

    def revise_schema_and_program_spec(
        self,
        *,
        user_message: str,
        current_schema_spec: SchemaSpec,
        current_program_spec: ProgramSpec | None,
        fallback_program_spec: ProgramSpec,
        view_bundle: ViewBundle,
    ) -> tuple[str, SchemaSpec, ProgramSpec, list[str], list[str]]:
        payload = self._build_spec_revision_payload(
            user_message=user_message,
            current_schema_spec=current_schema_spec,
            current_program_spec=current_program_spec,
            view_bundle=view_bundle,
        )
        with model_operation("spec_revision"):
            response_data = self._post_chat_completion(payload)
        parsed = _parse_json_content(response_data)
        revised_schema = _sanitize_schema_spec(
            parsed.get("schema_spec", {}), view_bundle=view_bundle
        )
        revised_plan = build_extraction_plan(revised_schema)
        schema_fallback = build_program_spec(revised_plan)
        candidate_program = parsed.get("program_spec")
        preferred_program = candidate_program if isinstance(candidate_program, dict) else {}
        sanitized_programs, program_validation_issues = sanitize_candidate_field_programs(
            preferred_program,
            schema_spec=revised_schema,
        )
        revised_program = merge_program_specs(
            preferred_program_spec=ProgramSpec(field_programs=sanitized_programs),
            fallback_program_spec=schema_fallback,
            schema_spec=revised_schema,
        )
        assistant_message = _safe_text(parsed.get("assistant_message"), max_length=1200)
        if not assistant_message:
            assistant_message = "已根据当前页面和你的说明生成新的字段契约与 ProgramSpec 草稿。"
        change_summary = _safe_text_list(parsed.get("change_summary"))
        validation_issues = _safe_text_list(parsed.get("validation_issues"))
        if not isinstance(candidate_program, dict):
            validation_issues.append("AI 未返回可用 ProgramSpec，已使用确定性兜底规则。")
        for issue in program_validation_issues:
            if issue not in validation_issues:
                validation_issues.append(issue)
        return (
            assistant_message,
            revised_schema,
            revised_program,
            change_summary,
            validation_issues,
        )

    def _build_payload(
        self,
        field: FieldSpec,
        view_bundle: ViewBundle,
        *,
        guidance_value: str = "",
    ) -> dict[str, object]:
        page_text = view_bundle.text[:MAX_LLM_TEXT_CHARS]
        field_payload = {
            "name": field.name,
            "description": field.description,
            "type": field.type,
            "required": field.required,
            "aliases": field.aliases,
            "examples": field.examples,
        }
        system_prompt = (
            "You are a strict field-level web information extraction component. "
            "Return only valid JSON. Extract only from the provided page text. "
            "Do not infer facts that are not supported by evidence. The evidence_text "
            "must be an exact substring from the page text whenever possible."
        )
        guidance = (
            f"User reference value for this field (use it only to locate the matching "
            f"page evidence, never copy it when absent): {guidance_value[:1000]}\n\n"
            if guidance_value.strip()
            else ""
        )

    def revise_field_schema(
        self,
        *,
        view_bundle: ViewBundle,
        current_schema_spec: SchemaSpec,
        user_message: str,
    ) -> SchemaSpec:
        payload = self._build_field_schema_payload(
            view_bundle=view_bundle,
            current_schema_spec=current_schema_spec,
            user_message=user_message,
        )
        parsed = _parse_json_content(self._post_chat_completion(payload))
        return _sanitize_schema_spec(parsed.get("schema_spec", parsed), view_bundle=view_bundle)

    def revise_field_value(
        self,
        *,
        field: FieldSpec,
        view_bundle: ViewBundle,
        guidance_value: str = "",
        evidence_text: str = "",
    ) -> tuple[FieldExtractionResult, ProgramSpec]:
        payload = self._build_field_value_payload(
            field=field,
            view_bundle=view_bundle,
            guidance_value=guidance_value,
            evidence_text=evidence_text,
        )
        parsed = _parse_json_content(self._post_chat_completion(payload))
        value = parsed.get("value")
        if value in (None, "") or parsed.get("abstain") is True:
            value = None
        else:
            value = normalize_whitespace(str(value))
            if field.type == "date":
                value = normalize_date(value)
        evidence_value = normalize_whitespace(str(parsed.get("evidence_text") or value or ""))
        start = view_bundle.text.find(evidence_value) if evidence_value else -1
        evidence = (
            FieldEvidence(
                field_name=field.name,
                source="llm_fallback",
                text=evidence_value,
                start_char=start if start >= 0 else None,
                end_char=start + len(evidence_value) if start >= 0 else None,
                score=max(0.0, min(1.0, float(parsed.get("confidence", 0.55)))),
            )
            if value is not None and evidence_value and start >= 0
            else None
        )
        result = FieldExtractionResult(
            field_name=field.name,
            value=value,
            normalized_value=value,
            confidence=evidence.score if evidence else 0.0,
            evidence=[evidence] if evidence else [],
            strategy="llm_fallback" if evidence else "none",
            status="extracted" if value is not None and evidence else "missing",
        )
        fallback = build_program_spec(
            build_extraction_plan(SchemaSpec(name="field", fields=[field]))
        )
        candidate = parsed.get("program_spec")
        safe, _ = sanitize_candidate_field_programs(
            candidate if isinstance(candidate, dict) else {},
            schema_spec=SchemaSpec(name="field", fields=[field]),
        )
        return result, merge_program_specs(
            preferred_program_spec=ProgramSpec(field_programs=safe),
            fallback_program_spec=fallback,
            schema_spec=SchemaSpec(name="field", fields=[field]),
        )
        user_prompt = (
            "Extract one field from this page.\n\n"
            f"FieldSpec JSON:\n{json.dumps(field_payload, ensure_ascii=False)}\n\n"
            f"{guidance}"
            f"Page title: {view_bundle.title}\n"
            f"Page URL: {view_bundle.url}\n\n"
            f"Page text:\n{page_text}\n\n"
            "Return JSON with exactly these keys: "
            "value, evidence_text, confidence, abstain, reason. "
            "If the field is missing or evidence is insufficient, set abstain=true, "
            "value=null, evidence_text=null."
        )
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
        }

    def _build_record_payload(self, *, view_bundle: ViewBundle) -> dict[str, object]:
        page_payload = {
            "url": view_bundle.url,
            "title": view_bundle.title,
            "headings": view_bundle.headings[:20],
            "metadata": view_bundle.metadata,
            "lines": view_bundle.lines[:160],
            "text_excerpt": view_bundle.text[:MAX_LLM_TEXT_CHARS],
        }
        system_prompt = (
            "You are a generic web information extraction baseline. Return one JSON object "
            "for the current page without receiving or inferring a target SchemaSpec. "
            "Extract only salient facts explicitly supported by the page. Use stable snake_case "
            "keys, scalar or list values, and do not invent facts. Include an evidence object "
            "mapping each key to exact supporting text and confidence when possible."
        )
        user_prompt = (
            "Extract a generic structured record from this page. Do not use a predefined field "
            "list and do not mention a schema. Return JSON with keys record and evidence. "
            "record must be an object. evidence must map field names to objects with text and "
            "confidence.\n\n"
            f"Current page view JSON:\n{json.dumps(page_payload, ensure_ascii=False)}"
        )
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
        }

    def _build_schema_spec_payload(self, *, view_bundle: ViewBundle) -> dict[str, object]:
        page_payload = {
            "url": view_bundle.url,
            "title": view_bundle.title,
            "headings": view_bundle.headings[:20],
            "metadata": view_bundle.metadata,
            "lines": view_bundle.lines[:MAX_SCHEMA_LINES],
            "text_excerpt": view_bundle.text[:MAX_SCHEMA_TEXT_CHARS],
        }
        system_prompt = (
            "You are SchemaAgent in a schema-first web information extraction workflow. "
            "Infer a compact SchemaSpec field contract for the current web page. "
            "Do not copy a built-in template unless the page actually matches it. "
            "Create fields that a user would naturally want from this page. "
            "Return only JSON and do not include selectors, xpath, regex, or extraction programs."
        )
        user_prompt = (
            "Infer SchemaSpec for this page.\n\n"
            f"Current page view JSON:\n{json.dumps(page_payload, ensure_ascii=False)}\n\n"
            "Return a JSON object with exactly these keys: name, description, domain, fields. "
            "fields must contain 3 to 8 objects. Each field must contain: name, description, "
            "type, required, aliases, examples. Field names must be stable snake_case English "
            "identifiers. Type must be one of string, text, number, date, url, list. "
            "Use Chinese descriptions and aliases when the page is Chinese. "
            "Always include a title field when the page has a discernible title. "
            "Mark required=true only for core fields strongly supported by the page."
        )
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
        }

    def _build_program_spec_payload(
        self,
        *,
        schema_spec: SchemaSpec,
        extraction_plan: ExtractionPlan,
        view_bundle: ViewBundle,
    ) -> dict[str, object]:
        schema_payload = schema_spec.model_dump(mode="json")
        plan_payload = extraction_plan.model_dump(mode="json")
        page_payload = {
            "url": view_bundle.url,
            "title": view_bundle.title,
            "headings": view_bundle.headings[:20],
            "metadata": view_bundle.metadata,
            "lines": view_bundle.lines[:120],
            "text_excerpt": view_bundle.text[:MAX_PROGRAMMER_TEXT_CHARS],
            **page_context(view_bundle.raw_html, limit=MAX_PROGRAMMER_HTML_CHARS),
        }
        system_prompt = (
            "You are ProgrammerAgent in a schema-first web information extraction "
            "workflow. Generate a safe ProgramSpec JSON DSL for the current URL. "
            "Do not write code. Do not invent fields. Use only these strategies: "
            "css, xpath, regex_on_text, text_near_label, llm_fallback. Use only "
            "these postprocess functions: strip, normalize_whitespace, normalize_date. "
            "Prefer page-specific selectors, labels, or regex rules that can be "
            "executed locally against the provided HTML/text. Add llm_fallback only "
            "as a final fallback for a field when local evidence may be insufficient."
            " Use selector_candidates and content HTML, not site navigation. "
            "DOM selectors must match exactly one nonempty field-specific node. "
            "Never use html/body/head/title or //title for a resource/article title. "
            "Separate title from version and badges; do not include related resources. "
            "CSS supports combinators/attributes/pseudo-classes; XPath is a real XPath evaluator. "
            "Use optional attribute for element attributes (e.g. datetime, href); "
            "XPath may also select /text() or /@datetime. Do not invent selectors."
        )
        user_prompt = (
            "Create ProgramSpec for this page.\n\n"
            f"SchemaSpec JSON:\n{json.dumps(schema_payload, ensure_ascii=False)}\n\n"
            f"ExtractionPlan JSON:\n{json.dumps(plan_payload, ensure_ascii=False)}\n\n"
            f"Current page view JSON:\n{json.dumps(page_payload, ensure_ascii=False)}\n\n"
            "Return one JSON object with exactly this top-level key: field_programs. "
            "field_programs must be an array. Each item must contain: field_name, "
            "strategy, enabled, selector, attribute, pattern, label, labels, postprocess. "
            "Use null when selector, pattern, or label is not applicable. "
            "Keep regex patterns valid for Python re. Do not include markdown."
        )
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
        }

    def _build_spec_revision_payload(
        self,
        *,
        user_message: str,
        current_schema_spec: SchemaSpec,
        current_program_spec: ProgramSpec | None,
        view_bundle: ViewBundle,
    ) -> dict[str, object]:
        current_program_payload = (
            current_program_spec.model_dump(mode="json")
            if current_program_spec is not None
            else {"field_programs": []}
        )
        page_payload = {
            "url": view_bundle.url,
            "title": view_bundle.title,
            "headings": view_bundle.headings[:20],
            "metadata": view_bundle.metadata,
            "lines": view_bundle.lines[:160],
            "text_excerpt": view_bundle.text[:MAX_SCHEMA_TEXT_CHARS],
            **page_context(view_bundle.raw_html, limit=MAX_PROGRAMMER_HTML_CHARS),
        }
        system_prompt = (
            "You are SpecCollaborationAgent for a schema-first web information "
            "extraction workbench. Revise SchemaSpec and ProgramSpec together from "
            "the user's natural-language instruction and the current page view. "
            "You may use the provided HTML/text to align fields with page evidence. "
            "Do not invent page facts. Do not create arbitrary code. ProgramSpec "
            "must use only strategies css, xpath, regex_on_text, text_near_label, "
            "llm_fallback and postprocess strip, normalize_whitespace, normalize_date. "
            "DOM rules must match exactly one nonempty field-specific node. "
            "Do not select html, body, head, document title, navigation or related resources. "
            "Separate article title, version and badges; use XPath /text() when appropriate. "
            "Return JSON only."
        )
        user_prompt = (
            "Revise the extraction spec for the current page.\n\n"
            f"User instruction:\n{user_message[:3000]}\n\n"
            "Current SchemaSpec JSON:\n"
            f"{json.dumps(current_schema_spec.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            "Current ProgramSpec JSON:\n"
            f"{json.dumps(current_program_payload, ensure_ascii=False)}\n\n"
            "Current page view JSON:\n"
            f"{json.dumps(page_payload, ensure_ascii=False)}\n\n"
            "Return one JSON object with exactly these top-level keys: "
            "assistant_message, schema_spec, program_spec, change_summary, validation_issues. "
            "schema_spec must contain name, description, domain, fields. "
            "Each field must contain name, description, type, required, aliases, examples. "
            "program_spec must contain field_programs. Each program must contain field_name, "
            "strategy, enabled, selector, attribute, pattern, label, labels, postprocess. "
            "Keep field names stable snake_case English identifiers. Use Chinese descriptions. "
            "Put uncertainty or missing evidence in validation_issues instead of inventing values."
        )
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
        }

    def _build_field_schema_payload(
        self,
        *,
        view_bundle: ViewBundle,
        current_schema_spec: SchemaSpec,
        user_message: str,
    ) -> dict[str, object]:
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are FieldSchemaAgent. Change only the field set for the "
                        "current page. Return JSON with one schema_spec key. Never "
                        "return extracted values, selectors, regex or programs."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"User request:\n{user_message[:4000]}\n\n"
                        f"Current schema:\n{json.dumps(current_schema_spec.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                        f"Page view:\n{json.dumps({'url': view_bundle.url, 'title': view_bundle.title, 'text': view_bundle.text[:MAX_SCHEMA_TEXT_CHARS]}, ensure_ascii=False)}\n\n"
                        "Return schema_spec with name, description, domain and fields. "
                        "Fields use name, description, type, required, aliases, examples."
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
        }

    def _build_field_value_payload(
        self,
        *,
        field: FieldSpec,
        view_bundle: ViewBundle,
        guidance_value: str,
        evidence_text: str,
    ) -> dict[str, object]:
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are FieldValueAgent. Extract exactly one field from the "
                        "provided page. Return JSON only. Evidence must be an exact "
                        "substring of page text. Do not invent values. Include a safe "
                        "field-local ProgramSpec using only css, xpath, regex_on_text, "
                        "text_near_label, llm_fallback."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Field:\n{json.dumps(field.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                        f"Guidance value:\n{guidance_value[:4000]}\n\n"
                        f"Selected evidence:\n{evidence_text[:8000]}\n\n"
                        f"Page text:\n{view_bundle.text[:MAX_LLM_TEXT_CHARS]}\n\n"
                        "Return value, evidence_text, confidence, abstain, reason and "
                        "program_spec.field_programs."
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
        }

    def _post_chat_completion(self, payload: dict[str, object]) -> dict[str, object]:
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.perf_counter()
        details = {"http_attempted": True, **model_context.get(), "provider": "openai-compatible",
                   "model": self.model, "actual_input_tokens": None, "actual_output_tokens": None,
                   "estimated_input_tokens": max(1, int(sum(len(str(m.get("content", "")))
                       for m in payload.get("messages", [])) / settings.estimated_chars_per_token)),
                   "estimated_output_tokens": None, "token_usage_source": "unavailable",
                   "estimate_source": "estimated", "estimated_chars_per_token": settings.estimated_chars_per_token}
        try:
            try:
                response = httpx.post(endpoint, headers=headers, json=payload,
                                      timeout=self.timeout_seconds)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ModelProviderError(f"LLM provider returned HTTP {exc.response.status_code}") from exc
            except httpx.HTTPError as exc:
                raise ModelProviderError(f"LLM provider request failed: {exc.__class__.__name__}") from exc
            data = response.json()
            if not isinstance(data, dict):
                raise ModelProviderError("LLM provider response was not a JSON object")
            usage = data.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            for metric_name, provider_name in [("actual_input_tokens", "prompt_tokens"),
                                               ("actual_output_tokens", "completion_tokens")]:
                value = usage.get(provider_name)
                details[metric_name] = value if type(value) is int and value >= 0 else None
            details.update(result="success",
                           estimated_output_tokens=int(len(json.dumps(data.get("choices", []),
                               ensure_ascii=False)) / settings.estimated_chars_per_token))
            if details["actual_input_tokens"] is not None and details["actual_output_tokens"] is not None:
                details["token_usage_source"] = "measured"
            return data
        except Exception as exc:
            details.update(result="failed", error_code=exc.__class__.__name__,
                           error_message=f"model request failed: {exc.__class__.__name__}")
            raise
        finally:
            observe("model_call", runtime_ms=round((time.perf_counter() - started) * 1000, 3), **details)
