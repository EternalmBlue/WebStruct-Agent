"""ProgramSpec 复用前的页面结构兼容性判断。"""

from __future__ import annotations

from app.contracts import (
    BodySelection,
    PageIntentAssessment,
    PageStructureSignature,
    StructureCompatibility,
    ViewBundle,
)
from app.platform.dom import parse_html


def build_page_structure_signature(
    view_bundle: ViewBundle,
    *,
    intent: PageIntentAssessment | None = None,
    body_selection: BodySelection | None = None,
    selector_match_counts: dict[str, int] | None = None,
) -> PageStructureSignature:
    """Build a compact structure fingerprint without persisting page contents."""

    from app.features.page_center.single_page import assess_page_intent, select_body_content

    source = view_bundle.raw_html
    root = parse_html(source)
    intent = intent or assess_page_intent(source)
    body_selection = body_selection or select_body_content(source)
    title_shape = [node.tag for node in root.xpath("//h1|//h2|//h3") if node.text_content().strip()]
    content_nodes = root.xpath("//main|//article|//*[@role='main']")
    content_shape = list(dict.fromkeys(node.tag for node in content_nodes))
    blocks = [
        node for node in root.xpath("//p|//li|//td|//th|//h1|//h2|//h3")
        if node.text_content().strip()
    ]
    return PageStructureSignature(
        page_intent=intent.intent,
        title_shape=title_shape[:8],
        content_shape=content_shape[:8],
        heading_count=len(title_shape),
        text_block_count=len(blocks),
        repeated_item_ratio=intent.repeated_item_ratio,
        selector_match_counts=selector_match_counts or {},
        body_visible_text_coverage=body_selection.metrics.visible_text_coverage,
        body_continuity_score=body_selection.metrics.continuity_score,
        body_noise_ratio=body_selection.metrics.noise_ratio,
    )


def compare_structure_signatures(
    expected: PageStructureSignature,
    actual: PageStructureSignature,
) -> StructureCompatibility:
    reasons: list[str] = []
    unknown = False

    if expected.signature_version != actual.signature_version:
        reasons.append("signature_version_mismatch")
    if expected.page_intent != actual.page_intent:
        reasons.append("page_intent_mismatch")
    if expected.title_shape != actual.title_shape:
        reasons.append("title_shape_mismatch")
    if expected.content_shape != actual.content_shape:
        reasons.append("content_shape_mismatch")

    if expected.repeated_item_ratio is None or actual.repeated_item_ratio is None:
        unknown = True
    elif abs(expected.repeated_item_ratio - actual.repeated_item_ratio) > 0.35:
        reasons.append("repeated_item_ratio_out_of_range")

    if expected.body_visible_text_coverage is None or actual.body_visible_text_coverage is None:
        reasons.append("missing_body_coverage")
        unknown = True
    elif abs(expected.body_visible_text_coverage - actual.body_visible_text_coverage) > 0.45:
        reasons.append("body_coverage_out_of_range")

    if expected.body_continuity_score is None or actual.body_continuity_score is None:
        unknown = True
    elif abs(expected.body_continuity_score - actual.body_continuity_score) > 0.45:
        reasons.append("body_continuity_out_of_range")

    if expected.body_noise_ratio is None or actual.body_noise_ratio is None:
        unknown = True
    elif abs(expected.body_noise_ratio - actual.body_noise_ratio) > 0.35:
        reasons.append("body_noise_ratio_out_of_range")

    for field_name, expected_count in expected.selector_match_counts.items():
        actual_count = actual.selector_match_counts.get(field_name)
        if actual_count is None:
            reasons.append(f"missing_selector_match:{field_name}")
        elif expected_count == 1 and actual_count != 1:
            reasons.append(f"selector_match_mismatch:{field_name}")

    if any(reason for reason in reasons if not reason.startswith("missing_")):
        return StructureCompatibility(status="incompatible", reasons=list(dict.fromkeys(reasons)))
    if unknown:
        return StructureCompatibility(status="unknown", reasons=list(dict.fromkeys(reasons)))
    return StructureCompatibility(status="compatible", reasons=[])


__all__ = ["compare_structure_signatures"]
