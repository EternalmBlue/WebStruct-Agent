import pytest
from app.contracts import FieldProgramSpec, FieldSpec, ProgramSpec, SchemaSpec
from app.features.page_center.single_page import select_body_content
from app.features.program_center.quality import (
    add_body_fallback_programs,
    validate_page_program,
)


@pytest.mark.parametrize("strategy,selector,reason", [
    ("css", "html > body.content", "document_scope"),
    ("xpath", "//head/title/text()", "document_scope"),
    ("xpath", "//body[@class='content']/@class", "document_scope"),
    ("xpath", "count(//h1)", "invalid_selector"),
    ("css", ".absent", "no_matches"),
    ("css", "h2", "empty_value"),
    ("css", "p", "ambiguous_matches"),
])
def test_generated_rule_validation_checks_actual_selected_nodes(strategy, selector, reason):
    source = "<html><head><title>Site</title></head><body class='content'><h1>Title</h1><h2></h2><p>A</p><p>B</p></body></html>"
    program = ProgramSpec(version="custom", field_programs=[
        FieldProgramSpec(field_name="title", strategy=strategy, selector=selector),
    ])
    validated, diagnostics = validate_page_program(program, source)
    assert not validated.field_programs
    assert diagnostics[0]["reason"] == reason
    assert validated.version == "custom"


def test_scoped_attribute_extraction_is_accepted():
    program = ProgramSpec(field_programs=[
        FieldProgramSpec(field_name="date", strategy="css", selector="time", attribute="datetime"),
    ])
    validated, diagnostics = validate_page_program(program, "<time datetime='2026-10-09'>Today</time>")
    assert validated.field_programs == program.field_programs
    assert not diagnostics


def test_body_like_rule_is_rejected_when_it_only_covers_a_summary():
    source = """
    <html><body><main>
      <div class="summary">Short summary only.</div>
      <article class="content">
        <p>Full body paragraph one with installation details.</p>
        <p>Full body paragraph two with configuration details.</p>
      </article>
    </main></body></html>
    """
    program = ProgramSpec(field_programs=[
        FieldProgramSpec(field_name="body", strategy="css", selector=".summary"),
    ])

    validated, diagnostics = validate_page_program(
        program,
        source,
        body_selection=select_body_content(source),
    )

    assert not validated.field_programs
    assert diagnostics[0]["reason"] == "body_incomplete"


def test_body_fallback_uses_selected_generic_regions():
    source = """
    <html><body><main>
      <div class="summary">Short summary only.</div>
      <article class="content"><p>Full body paragraph one.</p><p>Full body paragraph two.</p></article>
    </main></body></html>
    """
    selection = select_body_content(source)
    schema = SchemaSpec(name="Article", fields=[FieldSpec(name="body", required=True)])

    fallback = add_body_fallback_programs(
        ProgramSpec(field_programs=[]),
        schema_spec=schema,
        body_selection=selection,
    )

    assert [item.selector for item in fallback.field_programs] == ["article.content"]
