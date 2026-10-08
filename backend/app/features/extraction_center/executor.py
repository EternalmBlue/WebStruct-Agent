from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from app.contracts import (
    ExtractionResult,
    FieldEvidence,
    FieldExtractionResult,
    FieldProgramSpec,
    ProgramSpec,
    SchemaSpec,
    ViewBundle,
)
from app.platform.llm import MissingModelConfigurationError, ModelAdapter
from app.platform.text_processing import bounded_snippet, normalize_date, normalize_whitespace


class _SimpleSelectorParser(HTMLParser):
    def __init__(self, selector: str) -> None:
        super().__init__()
        self.selector = selector
        self.matches: list[str] = []
        self._capture_depth = 0
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if self._matches(tag.lower(), attrs_dict):
            self._capture_depth = 1
            self._buffer = []
        elif self._capture_depth:
            self._capture_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if not self._capture_depth:
            return
        self._capture_depth -= 1
        if self._capture_depth == 0:
            value = normalize_whitespace(" ".join(self._buffer))
            if value:
                self.matches.append(value)

    def handle_data(self, data: str) -> None:
        if self._capture_depth:
            self._buffer.append(data)

    def _matches(self, tag: str, attrs: dict[str, str | None]) -> bool:
        selector = self.selector.strip()
        if not selector:
            return False
        if selector.startswith("#"):
            return attrs.get("id") == selector[1:]
        if selector.startswith("."):
            classes = (attrs.get("class") or "").split()
            return selector[1:] in classes
        if "." in selector:
            tag_name, class_name = selector.split(".", maxsplit=1)
            return tag == tag_name and class_name in (attrs.get("class") or "").split()
        if "#" in selector:
            tag_name, element_id = selector.split("#", maxsplit=1)
            return tag == tag_name and attrs.get("id") == element_id
        return tag == selector.lower()


def execute_program_spec(
    *,
    task_id: str,
    schema_spec: SchemaSpec,
    view_bundle: ViewBundle,
    program_spec: ProgramSpec,
    model_adapter: ModelAdapter | None = None,
    allow_llm_fallback: bool = False,
) -> ExtractionResult:
    if model_adapter is None:
        raise MissingModelConfigurationError(
            "execute_program_spec requires a configured ModelAdapter for llm_fallback"
        )
    adapter = model_adapter
    fields: list[FieldExtractionResult] = []

    for field in schema_spec.fields:
        field_programs = [
            program for program in program_spec.field_programs if program.field_name == field.name
        ]
        result = _execute_field_programs(
            field,
            field_programs,
            view_bundle,
            adapter,
            allow_llm_fallback=allow_llm_fallback,
        )
        fields.append(result)

    extracted = [field for field in fields if field.status != "missing"]
    overall_confidence = (
        round(sum(field.confidence for field in extracted) / len(fields), 4) if fields else 0.0
    )
    return ExtractionResult(
        task_id=task_id,
        schema_name=schema_spec.name,
        fields=fields,
        overall_confidence=overall_confidence,
    )


def _execute_field_programs(
    field: Any,
    field_programs: list[FieldProgramSpec],
    view_bundle: ViewBundle,
    adapter: ModelAdapter,
    *,
    allow_llm_fallback: bool,
) -> FieldExtractionResult:
    for program in field_programs:
        if not program.enabled:
            continue
        if program.strategy == "llm_fallback" and not allow_llm_fallback:
            continue
        value, evidence = _execute_single_program(field, program, view_bundle, adapter)
        if value not in (None, ""):
            normalized = _apply_postprocess(value, program.postprocess)
            confidence = _confidence_for(program, evidence, normalized)
            return FieldExtractionResult(
                field_name=field.name,
                value=value,
                normalized_value=normalized,
                confidence=confidence,
                evidence=[evidence] if evidence else [],
                strategy=program.strategy,
                status="extracted",
            )

    return FieldExtractionResult(
        field_name=field.name,
        value=None,
        normalized_value=None,
        confidence=0.0,
        evidence=[],
        strategy="none",
        status="missing",
    )


def _execute_single_program(
    field: Any,
    program: FieldProgramSpec,
    view_bundle: ViewBundle,
    adapter: ModelAdapter,
) -> tuple[str | None, FieldEvidence | None]:
    if program.strategy == "text_near_label":
        return _extract_text_near_label(field.name, program, view_bundle)
    if program.strategy == "regex_on_text":
        return _extract_regex(field.name, program, view_bundle)
    if program.strategy == "css":
        return _extract_css(field.name, program, view_bundle)
    if program.strategy == "xpath":
        return _extract_xpath(field.name, program, view_bundle)
    if program.strategy == "llm_fallback":
        return adapter.extract_field(field, view_bundle)
    raise ValueError(f"unsupported ProgramSpec strategy: {program.strategy}")


def _extract_text_near_label(
    field_name: str,
    program: FieldProgramSpec,
    view_bundle: ViewBundle,
) -> tuple[str | None, FieldEvidence | None]:
    labels = [program.label, *program.labels]
    labels = sorted({label for label in labels if label}, key=len, reverse=True)
    if not labels:
        return None, None
    for line in view_bundle.lines:
        normalized_line = line.strip()
        for label in labels:
            if not _label_matches_field_line(label, normalized_line):
                continue
            escaped = re.escape(label)
            match = re.search(
                rf"^(?:[【\[\(（\-\*\d一二三四五六七八九十\.、\s]*){escaped}\s*[：:\-：]\s*(?P<value>.+)$",
                normalized_line,
            )
            if match:
                value = normalize_whitespace(match.group("value"))
                if value:
                    start = max(view_bundle.text.find(normalized_line), 0)
                    return value, FieldEvidence(
                        field_name=field_name,
                        source="text_near_label",
                        text=bounded_snippet(view_bundle.text, start, start + len(normalized_line)),
                        start_char=start,
                        end_char=start + len(normalized_line),
                        score=0.85,
                    )
    return None, None


def _label_matches_field_line(label: str, line: str) -> bool:
    if not line or not label:
        return False
    if label not in line:
        return False
    if line.startswith(label):
        return True
    prefix = line.split(label, maxsplit=1)[0].strip()
    if not prefix:
        return True
    allowed_prefixes = {
        "",
        "发布日期",
        "报名截止",
        "申报截止",
        "施行日期",
        "发布单位",
        "发布机关",
        "招聘单位",
        "岗位",
        "联系人",
        "发文字号",
    }
    return prefix in allowed_prefixes


def _extract_regex(
    field_name: str,
    program: FieldProgramSpec,
    view_bundle: ViewBundle,
) -> tuple[str | None, FieldEvidence | None]:
    if not program.pattern:
        return None, None
    match = re.search(program.pattern, view_bundle.text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return None, None
    value = match.group(1) if match.groups() else match.group(0)
    return normalize_whitespace(value), FieldEvidence(
        field_name=field_name,
        source="regex_on_text",
        text=bounded_snippet(view_bundle.text, match.start(), match.end()),
        start_char=match.start(),
        end_char=match.end(),
        score=0.75,
    )


def _extract_css(
    field_name: str,
    program: FieldProgramSpec,
    view_bundle: ViewBundle,
) -> tuple[str | None, FieldEvidence | None]:
    if not program.selector:
        return None, None
    parser = _SimpleSelectorParser(program.selector)
    parser.feed(view_bundle.raw_html)
    if not parser.matches:
        return None, None
    value = parser.matches[0]
    start = max(view_bundle.text.find(value), 0)
    return value, FieldEvidence(
        field_name=field_name,
        source="css",
        text=value,
        start_char=start,
        end_char=start + len(value),
        score=0.8,
    )


def _extract_xpath(
    field_name: str,
    program: FieldProgramSpec,
    view_bundle: ViewBundle,
) -> tuple[str | None, FieldEvidence | None]:
    if not program.selector or not program.selector.startswith("//"):
        return None, None
    tag = program.selector.removeprefix("//").split("[", maxsplit=1)[0].strip()
    if not tag:
        return None, None
    return _extract_css(
        field_name,
        FieldProgramSpec(field_name=field_name, strategy="css", selector=tag),
        view_bundle,
    )


def _apply_postprocess(value: str, postprocess: list[str]) -> str:
    current = value
    for function_name in postprocess:
        if function_name == "strip":
            current = current.strip()
        elif function_name == "normalize_whitespace":
            current = normalize_whitespace(current)
        elif function_name == "normalize_date":
            current = normalize_date(current)
        else:
            raise ValueError(f"unsupported postprocess function: {function_name}")
    return current


def _confidence_for(
    program: FieldProgramSpec,
    evidence: FieldEvidence | None,
    value: str,
) -> float:
    if not evidence or not value:
        return 0.0
    base = {
        "css": 0.82,
        "xpath": 0.8,
        "regex_on_text": 0.76,
        "text_near_label": 0.86,
        "llm_fallback": 0.48,
    }[program.strategy]
    if len(value) < 2:
        base -= 0.15
    return max(0.0, min(1.0, round((base + evidence.score) / 2, 4)))
