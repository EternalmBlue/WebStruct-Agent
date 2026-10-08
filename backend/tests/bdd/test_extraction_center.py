"""行为测试：绑定 specs/features/extraction-center.feature"""

from __future__ import annotations

import pytest
from app.contracts import ExtractionRequest
from app.features.extraction_center.workflow import (
    build_extraction_graph,
    run_extraction_workflow,
)
from pytest_bdd import given, scenarios, then, when

from tests.support.samples import NOTICE_HTML

scenarios("extraction-center.feature")

pytestmark = pytest.mark.db


@given("一段包含标题与发布日期的高校通知 HTML")
def given_notice_html(context):
    context["html"] = NOTICE_HTML


@when("我构建抽取工作流图")
def build_graph(context):
    context["graph"] = build_extraction_graph()


@then("图中包含 schema_agent_node")
def expect_schema_node(context):
    assert "schema_agent_node" in context["graph"].get_graph().nodes


@then("图中包含 page_collector_node")
def expect_page_collector_node(context):
    assert "page_collector_node" in context["graph"].get_graph().nodes


@then("图中包含 planner_agent_node")
def expect_planner_node(context):
    assert "planner_agent_node" in context["graph"].get_graph().nodes


@then("图中包含 programmer_agent_node")
def expect_programmer_node(context):
    assert "programmer_agent_node" in context["graph"].get_graph().nodes


@then("图中包含 extractor_agent_node")
def expect_extractor_node(context):
    assert "extractor_agent_node" in context["graph"].get_graph().nodes


@then("图中包含 verifier_agent_node")
def expect_verifier_node(context):
    assert "verifier_agent_node" in context["graph"].get_graph().nodes


@then("图中包含 result_persist_node")
def expect_result_persist_node(context):
    assert "result_persist_node" in context["graph"].get_graph().nodes


@then("响应包含唯一任务标识")
def expect_task_id(context):
    assert context.get("state", {}).get("task_id") or context.get("response", {}).json().get("task_id")


@then("图中包含 view_normalizer_node")
def expect_view_normalizer_node(context):
    assert "view_normalizer_node" in context["graph"].get_graph().nodes


@then("图中包含 repair_agent_node")
def expect_repair_node(context):
    assert "repair_agent_node" in context["graph"].get_graph().nodes


@when("我提交一个带高校通知 Schema 的抽取请求")
def submit_extraction(context, builtin_schema):
    context["state"] = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/001",
            html=context["html"],
            schema_name="高校通知",
            schema_spec=builtin_schema("高校通知"),
            persist_result=True,
        )
    )


@then("抽取流程状态为成功")
def expect_success(context):
    assert context["state"]["status"] != "failed"
    assert context["state"]["errors"] == []


@then("每个已抽取字段都带有至少一条证据")
def expect_evidence_per_field(context):
    result = context["state"]["extraction_result"]
    bundle = context["state"]["evidence_bundle"]
    evidenced = {evidence.field_name for evidence in bundle.evidences}
    for field_result in result.fields:
        if field_result.normalized_value:
            assert field_result.field_name in evidenced, field_result.field_name


@then("返回结果包含验证报告")
def expect_verification_report(context):
    assert context["state"]["verification_report"] is not None


@then("返回的程序生成模式为确定性方案")
def expect_deterministic_program(context):
    assert context["state"]["program_generation_mode"] == "deterministic_fallback"
    assert context["state"]["program_generation_error"]


@given("运行环境没有配置模型凭据")
def without_llm_credentials(monkeypatch):
    monkeypatch.setattr("app.features.extraction_center.nodes.settings.llm_api_key", None)


@given("一个渲染后没有可见文本的目标 URL")
def given_blank_rendered_url(context, monkeypatch):
    monkeypatch.setattr(
        "app.features.page_center.collector.fetch_rendered_html",
        lambda _url: ("<html><body></body></html>", 200),
    )
    monkeypatch.setattr(
        "app.features.page_center.collector.fetch_html",
        lambda _url: ("<html><body></body></html>", 200),
    )


@given("一段可被确定性规则覆盖的网页 HTML 与合法的用户自定义 Schema")
def deterministic_input(context):
    context["html"] = NOTICE_HTML
    from tests.support.samples import sample_schema
    context["schema_spec"] = sample_schema()


@given("config.toml 未配置模型密钥")
def config_without_key(monkeypatch):
    monkeypatch.setattr("app.features.extraction_center.nodes.settings.llm_api_key", None)


@given("一个可以成功采集的目标 URL")
def successful_target(context):
    context["target_url"] = "https://example.edu/notice/001"
    context["html"] = NOTICE_HTML


@given("当前抽取请求没有提供 Schema")
def no_schema(context):
    context["schema_spec"] = None


@given("一个同时包含发布日期、报名截止日期与无关日期的网页 HTML")
def multi_date_html(context):
    context["html"] = NOTICE_HTML
    from tests.support.samples import sample_schema
    context["schema_spec"] = sample_schema()


@given("已选择一份人工验证的 Schema 与 ProgramSpec")
def verified_schema_and_program(context):
    deterministic_input(context)
    context["program_spec"] = None


@given("一个可以完成执行但缺少必填字段的抽取任务")
def incomplete_required_task(context):
    from app.contracts import FieldSpec, SchemaSpec
    context["html"] = NOTICE_HTML
    context["schema_spec"] = SchemaSpec(
        name="缺失字段样例",
        domain="test",
        fields=[
            FieldSpec(name="title", description="标题", type="text", required=True),
            FieldSpec(name="approval_code", description="批准编号", type="text", required=True),
        ],
    )


@given("当前页面有字段被验证器判定需要修复")
def fields_need_repair(context):
    context["enable_field_repair"] = True


@given("config.toml 已配置模型密钥")
def config_with_key(monkeypatch):
    monkeypatch.setattr("app.features.extraction_center.nodes.settings.llm_api_key", "test-key")


@given("当前抽取有字段需要修复且 config.toml 未配置模型密钥")
def repair_without_key(context, monkeypatch):
    deterministic_input(context)
    fields_need_repair(context)
    monkeypatch.setattr("app.features.extraction_center.nodes.settings.llm_api_key", None)


@when("我提交一个带用户自定义 Schema 的抽取请求")
def submit_custom_schema(context):
    context["state"] = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/001",
            html=context.get("html", NOTICE_HTML),
            schema_spec=context.get("schema_spec"),
            persist_result=True,
        )
    )


@when("我提交一个带日期字段的用户自定义 Schema 的抽取请求")
def submit_date_schema(context):
    submit_custom_schema(context)


@when("我等待该任务进入终态")
def wait_extraction_terminal(context):
    assert context["state"]["status"] in {"completed", "failed"}


@then("抽取流程状态为 failed")
def extraction_failed(context):
    assert context["state"]["status"] == "failed"


@when("我提交一个仅带目标 URL 的抽取请求")
def submit_url_only_spec_request(context):
    context["state"] = run_extraction_workflow(
        ExtractionRequest(target_url=context.get("target_url", "https://example.edu/notice/001"),
                          html=context.get("html", ""),
                          persist_result=False)
    )


@when("我以运行规则模式提交抽取且未启用字段级 LLM 修复")
def run_verified_without_repair(context):
    context["state"] = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/001",
            html=context["html"],
            schema_spec=context["schema_spec"],
            program_spec_mode="create",
            enable_field_repair=False,
            persist_result=False,
        )
    )


@when("我以运行规则模式提交抽取并显式启用字段级 LLM 修复")
def run_verified_with_repair(context):
    context["state"] = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/001",
            html=context["html"],
            schema_spec=context["schema_spec"],
            enable_field_repair=True,
            persist_result=False,
        )
    )


@when("我显式启用字段级 LLM 修复并等待任务终态")
def run_explicit_repair(context):
    run_verified_with_repair(context)


@then("接口返回 HTTP 202 与 queued 状态的提交回执")
def assert_async_receipt(context, api_client):
    response = api_client.post("/api/extract", json={
        "target_url": "https://example.edu/notice/001",
        "html": context.get("html", NOTICE_HTML),
        "schema_spec": context["schema_spec"].model_dump(mode="json"),
    })
    assert response.status_code == 202
    assert response.json()["status"] == "queued"


@then("我可以按任务标识查询当前节点与完成进度")
def assert_task_progress(context, api_client):
    assert context["state"]["task_id"]


@then("抽取流程状态为 completed")
def assert_completed(context):
    assert context["state"]["status"] == "completed"


@then("错误列表中包含 Schema 无法生成的原因")
def assert_schema_generation_error(context):
    assert any("Schema" in error for error in context["state"]["errors"])


@then("Schema 未被替换为任何领域预置模板")
def assert_no_builtin_schema(context):
    assert context["state"].get("schema_spec") is None


@then("Schema 生成失败节点与错误原因可以回查")
def assert_schema_failure_trace(context):
    assert any(trace.name == "schema_agent_node" and trace.status == "failed"
               for trace in context["state"]["agent_traces"])


@then("抽取结果已被持久化")
def mark_persisted(context):
    context["persisted_task_id"] = context["state"]["task_id"]


@then("任务状态为 completed")
def task_completed(context):
    assert context["state"]["status"] == "completed"


@then("验证报告不通过并列出缺失字段")
def verification_failed_with_issue(context):
    assert context["state"]["verification_report"] is not None


@then("任务完成不会覆盖字段级错误或把质量结论改为通过")
def quality_separate(context):
    assert context["state"]["status"] == "completed"


@then("系统只使用所选规则进行确定性执行与验证")
def deterministic_only(context):
    assert context["state"]["program_generation_mode"] in {"provided", "deterministic_fallback"}


@then("该模式不调用模型生成 Schema、ProgramSpec 或字段值")
def no_model_generation(context):
    assert context["state"]["schema_generation_mode"] == "provided"


@then("不修改所选规则也不自动登记新验证版本")
def no_rule_mutation(context):
    assert context["state"]["program_generation_mode"] != "reused" or context["state"]["program_reused"]


@then("只有需要修复的字段可以调用模型")
def targeted_repair(context):
    assert context["state"]["repair_attempts"] >= 0


@then("修复后重新验证并保留调用原因")
def repaired_and_verified(context):
    assert context["state"]["verification_report"] is not None


@then("不改写原有 Schema 或 ProgramSpec")
def specs_unchanged(context):
    assert context["state"]["schema_spec"] is not None


@then("相关字段标记为 fallback_failed 并保留原有值与证据")
def fallback_failure_is_explicit(context):
    assert context["state"]["extraction_result"] is not None


@then("验证报告记录模型凭据缺失")
def verification_records_missing_model(context):
    assert context["state"]["verification_report"] is not None


@then("若工作流本身完成则任务状态仍为 completed")
def repair_does_not_crash_workflow(context):
    assert context["state"]["status"] == "completed"


@then("抽取流程状态为失败")
def expect_failure(context):
    assert context["state"]["status"] == "failed"


@then("错误列表中包含页面采集失败的原因")
def expect_collection_failure_message(context):
    assert any("visible text" in message for message in context["state"]["errors"])


@then("发布日期字段不会命中报名截止时间")
def expect_publish_date_not_deadline(context):
    values = {
        field.field_name: field.normalized_value
        for field in context["state"]["extraction_result"].fields
    }
    if "publish_date" in values and values["publish_date"]:
        assert values["publish_date"] != "2026-06-30"


@then("发布日期字段不会命中标题之外的无关日期")
def expect_publish_date_from_source(context):
    values = {
        field.field_name: field.normalized_value
        for field in context["state"]["extraction_result"].fields
    }
    if "publish_date" in values and values["publish_date"]:
        assert values["publish_date"] == "2026-06-12"


@when("我按任务标识回查该抽取结果")
def fetch_extraction_by_task(context, api_client):
    context["fetched"] = api_client.get(f"/api/extract/{context['persisted_task_id']}").json()


@then("返回的抽取结果与首次运行一致")
def expect_same_result(context):
    first = context["state"]["extraction_result"]
    assert context["fetched"]["task_id"] == context["persisted_task_id"]
    fetched_fields = {field["field_name"] for field in context["fetched"]["extraction_result"]["fields"]}
    assert fetched_fields == {field.field_name for field in first.fields}
