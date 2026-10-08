from types import SimpleNamespace

from app.contracts import (
    ExtractionRequest,
    ExtractionResult,
    FieldEvidence,
    FieldExtractionResult,
    FieldProgramSpec,
    FieldSpec,
    ProgramSpec,
    SchemaSpec,
)
from app.features.extraction_center.verifier import verify_extraction
from app.features.extraction_center.workflow import run_extraction_workflow
from app.platform.observability import runtime
from pytest_bdd import given, scenarios, then, when

from tests.bdd.feature_paths import feature_path
from tests.bdd.test_rsi_observability import make_run
from tests.support.browser_pages import CONTENT_HTML, BrowserPage

scenarios(feature_path("resource-validation.feature"))


@given("a normal browser page and a configured navigation delay")
def normal_page(context, monkeypatch):
    from app.platform.browser import CloakBrowserAdapter
    from app.platform.configuration import settings
    page = BrowserPage(monkeypatch, status=200)
    page.html = CONTENT_HTML
    adapter = CloakBrowserAdapter()
    monkeypatch.setattr(settings, "browser_post_navigation_wait_ms", 10000)
    monkeypatch.setattr(adapter, "readiness", lambda: {"available": True})
    monkeypatch.setattr("app.platform.browser.importlib.import_module",
                        lambda *_: SimpleNamespace(launch=page.launch))
    context.update(page=page, adapter=adapter)


@when("the browser-backed collector reads the URL")
def fetch(context):
    context["page_result"] = context["adapter"].fetch(context["page"].url)


@then("it waits the full delay once and retains the final document response")
def waited(context):
    assert context["page"].waits == [10000]
    assert context["page_result"].metadata["post_navigation_wait_ms"] == 10000
    assert context["page_result"].status_code == 200
    assert context["page"].closed


@given("a valid required title and an empty optional description")
def optional(context):
    context["schema"] = SchemaSpec(name="Test", fields=[
        FieldSpec(name="title"), FieldSpec(name="description", required=False)])
    context["result"] = ExtractionResult(task_id="test", schema_name="Test", fields=[
        FieldExtractionResult(field_name="title", value="Resource title", confidence=.9,
                              strategy="css", status="extracted", evidence=[
                                  FieldEvidence(field_name="title", source="css", text="Resource title", score=.9)]),
        FieldExtractionResult(field_name="description"),
    ])


@given("a required numeric field with the value zero and supporting evidence")
def zero(context):
    context["schema"] = SchemaSpec(name="Test", fields=[FieldSpec(name="count", type="number")])
    context["result"] = ExtractionResult(task_id="test", schema_name="Test", fields=[
        FieldExtractionResult(field_name="count", value=0, confidence=.9, strategy="css",
                              status="extracted", evidence=[
                                  FieldEvidence(field_name="count", source="css", text="Count: 0", score=.9)])])


@when("I verify the extraction")
def verify(context):
    context["verification"] = verify_extraction(task_id="test", schema_spec=context["schema"],
                                              extraction_result=context["result"])


@then("verification passes without penalizing the absent optional field")
def optional_pass(context):
    assert context["verification"].passed
    assert context["verification"].score == 1
    assert not context["verification"].issues


@then("verification does not report a required field missing")
def zero_pass(context):
    assert context["verification"].passed
    assert not any(i.code == "required_field_missing" for i in context["verification"].issues)


@given("nested resource markup with images and a sidebar")
def nested(context):
    context["html"] = """<h1>Resource</h1><main><div class="bbWrapper">
    <p>Body <strong>only</strong><img src="demo.png"><br>Second line</p></div>
    <aside>Sidebar noise</aside></main><span class="version">1.2.3</span>"""
    context["schema"] = SchemaSpec(name="Test", fields=[
        FieldSpec(name="description"), FieldSpec(name="version")])
    context["program"] = ProgramSpec(field_programs=[
        FieldProgramSpec(field_name="description", strategy="css", selector="main .bbWrapper"),
        FieldProgramSpec(field_name="version", strategy="xpath", selector="//span[@class='version']/text()")])


@when("I execute a scoped CSS and XPath program")
def execute(context):
    context["state"] = run_extraction_workflow(ExtractionRequest(
        html=context["html"], schema_spec=context["schema"], program_spec=context["program"],
        persist_result=False))


@then("the body excludes the sidebar and XPath selects the version")
def dom_result(context):
    result = context["state"]["extraction_result"]
    assert result.get_field("description").normalized_value == "Body only Second line"
    assert result.get_field("version").normalized_value == "1.2.3"


@given("generated document title and ambiguous body selectors")
def broad(context):
    context["html"] = "<title>Site</title><h1>Resource</h1><div class='body'>A</div><div class='body'>B</div>"
    context["program"] = ProgramSpec(field_programs=[
        FieldProgramSpec(field_name="title", strategy="xpath", selector="//title"),
        FieldProgramSpec(field_name="description", strategy="css", selector=".body")])


@when("I validate those generated rules against the current page")
def validate_rules(context):
    from app.features.program_center.quality import validate_page_program
    context["validated"], context["diagnostics"] = validate_page_program(
        context["program"], context["html"])


@then("those rules are rejected with diagnostics")
def rejected_rules(context):
    assert not context["validated"].field_programs
    assert {d["reason"] for d in context["diagnostics"]} == {"document_scope", "ambiguous_matches"}


@given("comparable runs with a higher score but fewer extracted fields")
def regression(context, monkeypatch):
    base = runtime.snapshot(make_run(score=.5))
    candidate = runtime.snapshot(make_run(score=1))
    for snap, value in [(base, 1), (candidate, .5)]:
        snap["metrics"]["field_completion_rate"] = {
            "value": value, "source": "measured", "sample_count": 1,
        }
    context.update(baseline=base, candidate=candidate)
    monkeypatch.setattr(runtime, "snapshot", lambda tid: base if tid == base["task_id"] else candidate)


@given("otherwise comparable runs with different evaluator versions")
def evaluator_versions(context, monkeypatch):
    regression(context, monkeypatch)
    context["candidate"]["fingerprint"]["evaluator_version"] = "other"


@given("comparable runs with a missing evidence coverage measurement")
def missing_guardrail(context, monkeypatch):
    regression(context, monkeypatch)
    for snapshot in (context["baseline"], context["candidate"]):
        snapshot["metrics"]["evidence_coverage"] = {
            "value": None, "source": "unavailable", "sample_count": 0,
        }


@given("comparable runs with equal verifier scores and better candidate completion")
def completion_improvement(context, monkeypatch):
    regression(context, monkeypatch)
    for snapshot in (context["baseline"], context["candidate"]):
        snapshot["metrics"]["verification_score"] = {
            "value": .5, "source": "measured", "sample_count": 1,
        }
        snapshot["metrics"]["evidence_coverage"] = {
            "value": .5, "source": "measured", "sample_count": 1,
        }
    context["baseline"]["metrics"]["field_completion_rate"] = {
        "value": .5, "source": "measured", "sample_count": 1,
    }
    context["candidate"]["metrics"]["field_completion_rate"] = {
        "value": 1, "source": "measured", "sample_count": 1,
    }
    context["baseline"]["metrics"]["required_field_missing_rate"] = {
        "value": .5, "source": "measured", "sample_count": 1,
    }
    context["candidate"]["metrics"]["required_field_missing_rate"] = {
        "value": 0, "source": "measured", "sample_count": 1,
    }


@given("generated qualified root and document title selectors")
def qualified_broad(context):
    context["html"] = "<html><head><title>Site</title></head><body><h1>Resource</h1></body></html>"
    context["program"] = ProgramSpec(field_programs=[
        FieldProgramSpec(field_name="title", strategy="css", selector="html > body"),
        FieldProgramSpec(field_name="description", strategy="xpath", selector="//head/title/text()"),
    ])

@when("I evaluate their RSI iteration")
def evaluate(context):
    from app.contracts import RSIIterationRequest
    from app.features.rsi_center.service import evaluate_iteration
    context["iteration"] = evaluate_iteration(RSIIterationRequest(
        experiment_id="test", baseline_run_id=context["baseline"]["task_id"],
        candidate_run_id=context["candidate"]["task_id"], hypothesis_id="h",
        hypothesis="Specific selectors", intervention="selector", change_set_id="test"))


@then("the iteration is rejected for a completeness regression")
def completeness_rejected(context):
    assert context["iteration"]["status"] == "rejected"
    assert "field_completion_rate" in context["iteration"]["decision_reason"]


@then("the iteration is blocked for evaluator incompatibility")
def incompatible(context):
    assert context["iteration"]["status"] == "blocked"
    assert "evaluator" in context["iteration"]["decision_reason"]


@then("the iteration is blocked for unavailable guardrail measurements")
def guardrail_blocked(context):
    assert context["iteration"]["status"] == "blocked"
    assert "guardrail" in context["iteration"]["decision_reason"]


@then("the iteration is accepted using a completion-aware quality proxy")
def completion_accepted(context):
    assert context["iteration"]["status"] == "accepted"
    assert context["iteration"]["quality_basis"] == "verifier_completion_evidence_proxy_not_gold_accuracy"
    assert context["iteration"]["metric_deltas"]["quality_proxy"] > 0


@then("those rules are rejected as document scope")
def qualified_rejected(context):
    assert not context["validated"].field_programs
    assert {issue["reason"] for issue in context["diagnostics"]} == {"document_scope"}
