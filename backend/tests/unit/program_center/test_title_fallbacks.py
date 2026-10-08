from app.contracts import (
    BodyCandidate,
    BodyQualityMetrics,
    BodySelection,
    FieldProgramSpec,
    FieldSpec,
    ProgramSpec,
    SchemaSpec,
)
from app.features.program_center.plan import build_extraction_plan, build_program_spec
from app.features.program_center.quality import add_body_fallback_programs


def test_title_fallbacks_cover_heading_levels_without_site_specific_selectors():
    schema = SchemaSpec(name="Resource", fields=[FieldSpec(name="title", required=True)])

    program = build_program_spec(build_extraction_plan(schema))
    selectors = [
        item.selector
        for item in program.field_programs
        if item.field_name == "title" and item.strategy == "css"
    ]

    assert selectors == ["h1", "*[class*='title'] h2", "*[class*='title'] h3"]


def test_body_candidates_are_added_when_existing_rules_are_non_deterministic():
    schema = SchemaSpec(name="Resource", fields=[FieldSpec(name="body")])
    program = ProgramSpec(field_programs=[
        FieldProgramSpec(field_name="body", strategy="text_near_label", label="body"),
        FieldProgramSpec(field_name="body", strategy="llm_fallback"),
    ])
    selection = BodySelection(
        accepted=True,
        candidates=[
            BodyCandidate(selector="article.content", text="正文", block_count=1),
        ],
        metrics=BodyQualityMetrics(visible_text_coverage=1, block_coverage=1),
    )

    supplemented = add_body_fallback_programs(
        program,
        schema_spec=schema,
        body_selection=selection,
    )

    assert any(
        item.field_name == "body"
        and item.strategy == "css"
        and item.selector == "article.content"
        for item in supplemented.field_programs
    )
