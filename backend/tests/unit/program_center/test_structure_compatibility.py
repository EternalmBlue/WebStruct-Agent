from app.contracts import PageStructureSignature
from app.features.program_center.compatibility import compare_structure_signatures


def make_signature(**overrides):
    payload = {
        "signature_version": "1",
        "page_intent": "single_resource",
        "title_shape": ["h1"],
        "content_shape": ["main", "article"],
        "heading_count": 3,
        "text_block_count": 12,
        "repeated_item_ratio": 0.05,
        "selector_match_counts": {"title": 1, "body": 1},
        "body_visible_text_coverage": 0.86,
        "body_continuity_score": 0.9,
        "body_noise_ratio": 0.08,
    }
    payload.update(overrides)
    return PageStructureSignature(**payload)


def test_same_structure_is_compatible_for_program_reuse():
    result = compare_structure_signatures(make_signature(), make_signature())

    assert result.status == "compatible"
    assert result.reasons == []


def test_same_schema_shape_is_not_enough_when_page_structure_differs():
    result = compare_structure_signatures(
        make_signature(),
        make_signature(
            page_intent="list",
            title_shape=["h1", "h2"],
            content_shape=["main", "section"],
            repeated_item_ratio=0.8,
        ),
    )

    assert result.status == "incompatible"
    assert "page_intent_mismatch" in result.reasons
    assert "repeated_item_ratio_out_of_range" in result.reasons


def test_missing_signature_measurement_is_unknown_not_compatible():
    result = compare_structure_signatures(
        make_signature(),
        make_signature(body_visible_text_coverage=None),
    )

    assert result.status == "unknown"
    assert "missing_body_coverage" in result.reasons
