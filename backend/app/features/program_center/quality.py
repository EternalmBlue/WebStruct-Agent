"""Validate model-generated DOM rules without changing explicit user programs."""

from app.contracts import BodySelection, FieldProgramSpec, ProgramSpec, SchemaSpec
from app.platform.dom import parse_html, select_values

_BODY_FIELD_TOKENS = {
    "body",
    "content",
    "description",
    "details",
    "article",
    "text",
    "body_text",
}


def validate_page_program(
    program: ProgramSpec,
    source: str,
    *,
    body_selection: BodySelection | None = None,
):
    root = parse_html(source)
    accepted, diagnostics = [], []
    for rule in program.field_programs:
        if rule.strategy not in {"css", "xpath"} or not rule.enabled:
            accepted.append(rule)
            continue
        selector = rule.selector or ""
        reason = None
        count = None
        try:
            matches = root.cssselect(selector) if rule.strategy == "css" else root.xpath(selector)
            values = select_values(root, rule.strategy, selector, rule.attribute)
            count = len(values)
            if any(_document_node(match) for match in matches):
                reason = "document_scope"
            else:
                reason = ("no_matches" if not values else "ambiguous_matches" if len(values) > 1
                          else "empty_value" if not values[0] else None)
                if (
                    reason is None
                    and body_selection is not None
                    and body_selection.accepted
                    and _is_body_field(rule.field_name)
                    and len(body_selection.text) > 0
                    and len(values[0]) / len(body_selection.text) < 0.5
                ):
                    reason = "body_incomplete"
        except Exception:
            reason = "invalid_selector"
        if reason:
            diagnostics.append({"field": rule.field_name, "strategy": rule.strategy,
                                "selector": selector, "reason": reason, "match_count": count})
        else:
            accepted.append(rule)
    return program.model_copy(update={"field_programs": accepted}), diagnostics


def _is_body_field(field_name: str) -> bool:
    normalized = field_name.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in _BODY_FIELD_TOKENS or any(
        token in normalized for token in ("body", "content", "description", "detail", "article")
    )


def add_body_fallback_programs(
    program: ProgramSpec,
    *,
    schema_spec: SchemaSpec,
    body_selection: BodySelection | None,
) -> ProgramSpec:
    """Add generic selected body regions after rejecting an incomplete rule."""

    if body_selection is None or not body_selection.accepted or not body_selection.candidates:
        return program
    programs = list(program.field_programs)
    for field in schema_spec.fields:
        if not _is_body_field(field.name):
            continue
        if any(item.field_name == field.name for item in programs):
            continue
        for candidate in body_selection.candidates:
            if not candidate.selector:
                continue
            programs.append(
                FieldProgramSpec(
                    field_name=field.name,
                    strategy="css",
                    selector=candidate.selector,
                    postprocess=["strip", "normalize_whitespace"],
                )
            )
    return program.model_copy(update={"field_programs": programs})


def _document_node(match):
    node = match if hasattr(match, "tag") else match.getparent() if hasattr(match, "getparent") else None
    return node is not None and node.tag in {"html", "body", "head", "title"}
