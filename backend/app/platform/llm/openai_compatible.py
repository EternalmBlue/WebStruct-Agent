"""OpenAI 兼容 Chat Completions 适配器，默认对接 DeepSeek。"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.contracts import (
    ExtractionPlan,
    FieldEvidence,
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
from app.platform.text_processing import bounded_snippet, normalize_date, normalize_whitespace


@dataclass
class OpenAICompatibleModelAdapter:
    """OpenAI-compatible chat-completions adapter, configured for DeepSeek by default."""

    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    timeout_seconds: float = 30.0

    def generate_schema_spec(
        self,
        *,
        view_bundle: ViewBundle,
    ) -> SchemaSpec:
        payload = self._build_schema_spec_payload(view_bundle=view_bundle)
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
    ) -> tuple[str | None, FieldEvidence | None]:
        payload = self._build_payload(field, view_bundle)
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

    def _build_payload(self, field: FieldSpec, view_bundle: ViewBundle) -> dict[str, object]:
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
        user_prompt = (
            "Extract one field from this page.\n\n"
            f"FieldSpec JSON:\n{json.dumps(field_payload, ensure_ascii=False)}\n\n"
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
            "html_excerpt": view_bundle.raw_html[:MAX_PROGRAMMER_HTML_CHARS],
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
        )
        user_prompt = (
            "Create ProgramSpec for this page.\n\n"
            f"SchemaSpec JSON:\n{json.dumps(schema_payload, ensure_ascii=False)}\n\n"
            f"ExtractionPlan JSON:\n{json.dumps(plan_payload, ensure_ascii=False)}\n\n"
            f"Current page view JSON:\n{json.dumps(page_payload, ensure_ascii=False)}\n\n"
            "Return one JSON object with exactly this top-level key: field_programs. "
            "field_programs must be an array. Each item must contain: field_name, "
            "strategy, enabled, selector, pattern, label, labels, postprocess. "
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
            "html_excerpt": view_bundle.raw_html[:MAX_PROGRAMMER_HTML_CHARS],
        }
        system_prompt = (
            "You are SpecCollaborationAgent for a schema-first web information "
            "extraction workbench. Revise SchemaSpec and ProgramSpec together from "
            "the user's natural-language instruction and the current page view. "
            "You may use the provided HTML/text to align fields with page evidence. "
            "Do not invent page facts. Do not create arbitrary code. ProgramSpec "
            "must use only strategies css, xpath, regex_on_text, text_near_label, "
            "llm_fallback and postprocess strip, normalize_whitespace, normalize_date. "
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
            "strategy, enabled, selector, pattern, label, labels, postprocess. "
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

    def _post_chat_completion(self, payload: dict[str, object]) -> dict[str, object]:
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ModelProviderError(
                f"LLM provider returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelProviderError(
                f"LLM provider request failed: {exc.__class__.__name__}"
            ) from exc

        data = response.json()
        if not isinstance(data, dict):
            raise ModelProviderError("LLM provider response was not a JSON object")
        return data
