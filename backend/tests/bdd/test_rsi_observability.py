"""Exact executable acceptance bindings for the RSI increment."""
import json
from types import SimpleNamespace

import httpx
from app.contracts import FieldSpec, SchemaSpec
from app.platform.observability import runtime
from pytest_bdd import given, scenarios, then, when

from tests.bdd.feature_paths import feature_path
from tests.support.browser_pages import BrowserPage

scenarios(feature_path("rsi-observability.feature"))


def browser_page_context(context, monkeypatch, resolves):
    from app.platform.browser import CloakBrowserAdapter
    from app.platform.config import settings
    page = BrowserPage(monkeypatch, resolves=resolves)
    adapter = CloakBrowserAdapter()
    monkeypatch.setattr(settings, "browser_post_navigation_wait_ms", 500)
    monkeypatch.setattr(adapter, "readiness", lambda: {"available": True})
    monkeypatch.setattr("app.platform.browser.importlib.import_module",
                        lambda *_: SimpleNamespace(launch=page.launch))
    monkeypatch.setattr("app.features.page_center.collector.adapter", adapter)
    context.update(browser_page=page, http_calls=[])
    monkeypatch.setattr("app.features.page_center.collector.fetch_html",
                        context["http_calls"].append)


@given("a CloakBrowser page initially returning 468 that automatically navigates to 200")
def transient_challenge(context, monkeypatch):
    browser_page_context(context, monkeypatch, resolves=True)


@given("a CloakBrowser page that remains access-limited after the configured wait deadline")
def persistent_challenge(context, monkeypatch):
    browser_page_context(context, monkeypatch, resolves=False)


@when("the browser-backed collector reads the URL")
def collect_browser_page(context):
    from app.features.page_center.collector import PageCollectionError, collect_page
    try:
        context["page_observation"] = collect_page(target_url=context["browser_page"].url)
    except PageCollectionError as exc:
        context["collection_error"] = exc


@then("the final document status and content are collected without HTTP fallback")
def final_document(context):
    page = context["page_observation"]
    assert page.status_code == 200
    assert page.title == ""
    assert "Resolved heading" in page.text
    assert not context["http_calls"]
    assert page.metadata["page_classification"] == "usable_content"


@then("the initial status and bounded wait observations remain available")
def bounded_wait(context):
    attempt = context["page_observation"].metadata["collection_attempts"][0]
    assert attempt["initial_http_status"] == 468
    assert attempt["final_http_status"] == 200
    assert attempt["post_navigation_wait_ms"] == 500
    assert attempt["post_navigation_wait_outcome"] == "completed"
    assert context["browser_page"].closed
    assert context["browser_page"].navigate_count == 1


@then("collection fails without HTTP fallback or page-specific recognition")
def challenge_boundary(context):
    assert not context["http_calls"]
    assert context["browser_page"].navigate_count == 1
    assert len(context["collection_error"].attempts) == 1
    assert context["collection_error"].attempts[0]["classification"] == "access_limited"


@then("wait timeout observations and browser cleanup are retained")
def wait_timeout(context):
    attempt = context["collection_error"].attempts[0]
    assert attempt["post_navigation_wait_outcome"] == "completed"
    assert attempt["post_navigation_wait_ms"] == 500
    assert attempt["close_verified"] is True
    assert context["browser_page"].closed

@given("a rendered HTTP 200 page with challenge-like markup")
def challenge(context, monkeypatch):
    context["http_calls"] = []
    monkeypatch.setattr("app.features.page_center.collector.fetch_rendered_html",
                        lambda _: ('<html><body><div id="slg-box">Access Forbidden</div>'
                                   '<script>SafeLineChallenge()</script></body></html>', 200))
    monkeypatch.setattr("app.features.page_center.collector.fetch_html",
                        lambda url: context["http_calls"].append(url))


@when("I submit that URL for extraction")
def extract_challenge(context):
    from app.contracts import ExtractionRequest
    from app.features.extraction_center.workflow import run_extraction_workflow_for_task
    request = ExtractionRequest(target_url="https://example.test/", persist_result=False)
    receipt = runtime.create("extraction", ["page_collector_node", "schema_agent_node"], None)
    runtime.execute(receipt["task_id"], lambda task: run_extraction_workflow_for_task(request, task))
    context["run"] = runtime.snapshot(receipt["task_id"])
    context["events"] = runtime.events(receipt["task_id"])["events"]


@then("the collection attempt is classified from generic content and status")
def classification(context):
    attempts = [e for e in context["events"] if e["event_type"] == "collection_attempt"]
    assert attempts[0]["classification"] == "usable_content"


@then("the page is not rejected by challenge markup")
def no_fallback(context):
    assert not context["http_calls"]
    assert context["run"]["nodes"]["schema_agent_node"]["status"] != "skipped"


@then("the failed run retains structured collection observations")
def retained(context):
    assert context["run"]["status"] == "failed"
    assert context["run"]["metrics"]["collection_attempt_count"]["value"] == 1


def make_run(html="<h1>Same page</h1>", score=.5, elapsed=100):
    from app.contracts import (
        ExtractionResult,
        FieldEvidence,
        FieldExtractionResult,
        PageObservation,
        VerificationReport,
    )
    receipt = runtime.create("extraction", [], None)
    runtime.start(receipt["task_id"])
    state = {"status": "completed", "page_observation": PageObservation(
        url="https://example.test/", html=html, text="Same page"),
        "schema_spec": SchemaSpec(name="Test", domain="test", fields=[
            FieldSpec(name="title", description="Heading", type="text", required=True)]),
        "extraction_result": ExtractionResult(
            task_id=receipt["task_id"],
            schema_name="Test",
            fields=[FieldExtractionResult(
                field_name="title",
                value="Same page",
                normalized_value="Same page",
                confidence=score,
                evidence=[FieldEvidence(
                    field_name="title", source="css", text="Same page", score=score,
                )],
                strategy="css",
                status="extracted",
            )],
        ),
        "verification_report": VerificationReport(task_id=receipt["task_id"], passed=score == 1,
                                                   score=score, issues=[])}
    runtime.finish(receipt["task_id"], state, elapsed)
    return receipt["task_id"]


@given("completed baseline and candidate runs of the same page and schema")
def comparable(context):
    context["baseline"] = make_run(score=.5)
    context["candidate"] = make_run(score=1)
    context["before"] = runtime.snapshot(context["baseline"])


@given("baseline and candidate runs with different page snapshots")
def different(context):
    comparable(context)
    context["candidate"] = make_run(html="<h1>Other page</h1>", score=1)


@when("I evaluate an RSI iteration with a hypothesis and change identifier")
def evaluate(context, api_client):
    response = api_client.post("/api/rsi/iterations", json={
        "experiment_id": "test", "baseline_run_id": context["baseline"],
        "candidate_run_id": context["candidate"], "hypothesis_id": "h1",
        "hypothesis": "A more specific selector improves evidence", "intervention": "selector",
        "change_set_id": "test-change"})
    assert response.status_code == 201, response.text
    context["iteration"] = response.json()
    fetched = api_client.get(f'/api/rsi/iterations/{context["iteration"]["iteration_id"]}')
    assert fetched.json() == context["iteration"]


@then("the stored iteration links both runs and reports metric deltas")
def linked(context):
    result = context["iteration"]
    assert result["baseline_run_id"] == context["baseline"]
    assert result["candidate_run_id"] == context["candidate"]
    assert result["metric_deltas"]["verification_score"] == .5


@then("the decision is accepted when quality improves without excessive latency regression")
def accepted(context):
    assert context["iteration"]["status"] == "accepted"
    assert context["iteration"]["quality_basis"] == "verifier_completion_evidence_proxy_not_gold_accuracy"


@then("evaluation does not alter either extraction run")
def immutable(context):
    assert runtime.snapshot(context["baseline"]) == context["before"]


@then("the iteration is blocked with a comparability reason")
def blocked(context):
    assert context["iteration"]["status"] == "blocked"
    assert "page" in context["iteration"]["decision_reason"]


@given("a model response without provider token usage")
def response_without_usage(context, monkeypatch):
    context["response"] = {"choices": [{"message": {"content": "{}"}}]}
    monkeypatch.setattr("app.platform.llm.openai_compatible.httpx.post", lambda *a, **kw:
                        SimpleNamespace(raise_for_status=lambda: None, json=lambda: context["response"]))


@when("the model call is observed")
def observe_call(context):
    from app.platform.llm.openai_compatible import OpenAICompatibleModelAdapter
    from app.platform.observability.telemetry import capture_observations
    with capture_observations() as events:
        OpenAICompatibleModelAdapter(api_key="test-key")._post_chat_completion(
            {"messages": [{"content": "test"}]})
    context["call"] = events[-1]


@then("actual token usage is unavailable and estimates are labelled estimated")
def token_sources(context):
    assert context["call"]["actual_input_tokens"] is None
    assert context["call"]["token_usage_source"] == "unavailable"
    assert context["call"]["estimated_input_tokens"] > 0
    assert context["call"]["estimate_source"] == "estimated"


@given("a program-only benchmark record with no model calls")
def record(context):
    context["record"] = {"predicted": {"a": "ok", "b": "wrong"},
        "gold": {"a": "ok", "b": "ok"}, "required_fields": ["a", "b", "c"],
        "field_confidences": {"a": .9, "b": .1}, "observations": [],
        "runtime_ms": 1, "schema_spec": {"fields": [
            {"name": n, "type": "text", "required": True} for n in ["a", "b", "c"]]}}


@when("I score that benchmark record")
def score(context):
    from app.features.evaluation_center.metrics import score_method
    context["metrics"] = score_method("Program Only", [context["record"]])


@then("token cost is measured zero and repair success is unavailable")
def no_fake_cost(context):
    assert context["metrics"].estimated_token_cost == 0
    assert context["metrics"].metric_sources["estimated_token_cost"] == "measured"
    assert context["metrics"].repair_success_rate is None


@then("selective accuracy uses field confidence and missing rate uses required fields")
def denominators(context):
    assert context["metrics"].selective_accuracy == 1
    assert context["metrics"].required_field_missing_rate == .3333


@given("an empty monitoring window")
def empty_window(context, monkeypatch):
    from app.platform.observability.metrics import summarize_runs
    monkeypatch.setattr(runtime, "summary", lambda **kw: summarize_runs([]))


@when("I query the monitoring summary")
def summary(context, api_client):
    response = api_client.get("/api/observability/summary")
    assert response.status_code == 200
    context["summary"] = response.json()


@then("latency percentiles and failure rate are unavailable rather than fabricated zero")
def unavailable_summary(context):
    for key in ["p50_runtime_ms", "p95_runtime_ms", "p99_runtime_ms", "failure_rate"]:
        metric = context["summary"]["metrics"][key]
        assert metric["value"] is None
        assert metric["source"] == "unavailable"
        assert metric["reason"]


@given("a model provider returning a generic record with measured usage")
def generic_provider(context, monkeypatch):
    from app.contracts import BenchmarkItem
    context["requests"] = []
    context["item"] = BenchmarkItem(
        item_id="generic",
        html="<h1>Observed heading</h1>",
        schema_spec=SchemaSpec(name="Target schema marker", fields=[
            FieldSpec(name="hidden_contract_key", description="Secret contract marker")]),
        gold_record={"hidden_contract_key": "Gold answer marker"},
    )
    monkeypatch.setattr("app.features.evaluation_center.nodes.settings.llm_api_key", "test-key")

    def post(*args, **kwargs):
        context["requests"].append(kwargs["json"])
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": json.dumps({
                "record": {"page_title": "Observed heading"},
                "evidence": {"page_title": {"text": "Observed heading", "confidence": .9}},
            })}}], "usage": {"prompt_tokens": 20, "completion_tokens": 10}},
        )
    monkeypatch.setattr("app.platform.llm.openai_compatible.httpx.post", post)


@given("a model provider whose HTTP request fails")
def failed_provider(context, monkeypatch):
    generic_provider(context, monkeypatch)
    def post(*args, **kwargs):
        context["requests"].append(kwargs["json"])
        raise httpx.ConnectError("test network failure")
    monkeypatch.setattr("app.platform.llm.openai_compatible.httpx.post", post)


@when("I run the Direct LLM benchmark method")
def direct_method(context):
    from app.features.evaluation_center.nodes import _run_method
    context["record"] = _run_method("Direct LLM", context["item"])


@then("exactly one model HTTP call is recorded with provider usage")
def measured_call(context):
    assert len(context["requests"]) == 1
    assert context["record"]["model_call_count"] == 1
    assert context["record"]["actual_input_tokens"] == 20
    assert context["record"]["actual_output_tokens"] == 10
    assert context["record"]["token_usage_missing_calls"] == 0
    assert context["record"]["predicted"] == {"page_title": "Observed heading"}


@then("neither the target schema nor gold answers appear in its prompt")
def schema_free_prompt(context):
    prompt = json.dumps(context["requests"])
    for marker in ["Target schema marker", "Secret contract marker",
                   "hidden_contract_key", "Gold answer marker"]:
        assert marker not in prompt


@then("the failed sample retains one attempted call and unavailable usage")
def failed_call(context):
    assert context["record"]["status"] == "failed"
    assert context["record"]["model_call_count"] == 1
    assert context["record"]["actual_input_tokens"] is None
    assert context["record"]["token_usage_missing_calls"] == 1
    assert context["record"]["errors"]


@given("a labelled sample with one incorrect field before repair")
def labelled_repair(context, monkeypatch):
    from app.contracts import BenchmarkItem, ExtractionResult, FieldExtractionResult
    context["item"] = BenchmarkItem(
        item_id="repair", html="<h1>correct</h1>",
        schema_spec=SchemaSpec(name="Test", fields=[FieldSpec(name="title", description="Title")]),
        gold_record={"title": "correct"},
    )
    def workflow(request):
        context["full_request"] = request
        return {
            "status": "completed",
            "extraction_result": ExtractionResult(task_id="repair", schema_name="Test", fields=[
                FieldExtractionResult(field_name="title", value="correct", normalized_value="correct",
                                      confidence=.9, status="repaired")]),
            "repair_outcomes": [
                {"field": "title", "before": "wrong", "after": "correct", "result": "repaired"},
                {"field": "unlabelled", "before": None, "after": "unknown", "result": "repaired"},
            ],
        }
    monkeypatch.setattr("app.features.evaluation_center.nodes.run_extraction_workflow", workflow)


@when("I run the full benchmark method with a controlled repair result")
def full_repair(context):
    from app.features.evaluation_center.nodes import _run_method
    context["record"] = _run_method("Ours Full", context["item"])


@then("repair success counts only wrong-to-right gold improvements")
def gold_repair(context):
    assert context["record"]["repair_attempt_fields"] == 1
    assert context["record"]["repair_success_fields"] == 1


@then("the full method receives the shared deterministic program without history reuse")
def shared_program(context):
    from app.features.program_center.plan import build_extraction_plan, build_program_spec
    expected = build_program_spec(build_extraction_plan(context["item"].schema_spec))
    request = context["full_request"]
    assert request.program_spec == expected
    assert request.enable_field_repair is True
    assert request.reuse_verified_program is False


@when("I record a human rollback reason")
def human_rollback(context, api_client):
    identifier = context["iteration"]["iteration_id"]
    url = f"/api/rsi/iterations/{identifier}/rollback"
    first = api_client.post(url, json={"reason": "human review regression"})
    second = api_client.post(url, json={"reason": "human review regression"})
    assert first.status_code == second.status_code == 200
    context["rollback"] = first.json()
    context["rollback_again"] = second.json()


@then("rollback is idempotent and original run metrics are unchanged")
def idempotent_rollback(context):
    assert context["rollback"] == context["rollback_again"]
    assert context["rollback"]["status"] == "rolled_back"
    assert context["rollback"]["rollback_reason"] == "human review regression"
    assert runtime.snapshot(context["baseline"]) == context["before"]
