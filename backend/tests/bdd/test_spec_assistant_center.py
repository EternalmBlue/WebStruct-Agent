"""行为测试：绑定 specs/features/spec-assistant-center.feature"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from app.contracts import (
    ExtractionRequest,
    FieldProgramSpec,
    ProgramSpec,
    SchemaSpec,
    SpecAssistantRequest,
    ViewBundle,
)
from app.features.extraction_center.workflow import run_extraction_workflow
from app.platform.llm.unconfigured import UnconfiguredModelAdapter
from pytest_bdd import given, scenarios, then, when

from tests.bdd.feature_paths import feature_path
from tests.support.samples import NOTICE_HTML

scenarios(feature_path("spec-assistant-center.feature"))

pytestmark = pytest.mark.db


@dataclass
class FakeModelAdapter:
    """返回一段受控的修订结果，避免测试依赖真实模型。"""

    unsafe_program: bool = False

    def revise_schema_and_program_spec(
        self,
        *,
        user_message: str,
        current_schema_spec: SchemaSpec,
        current_program_spec: ProgramSpec | None,
        fallback_program_spec: ProgramSpec,
        view_bundle: ViewBundle,
    ) -> tuple[str, SchemaSpec, ProgramSpec, list[str], list[str]]:
        fields = list(current_schema_spec.fields)
        self.last_message = user_message
        schema = current_schema_spec.model_copy(update={"fields": fields})
        program_spec = current_program_spec or fallback_program_spec
        if self.unsafe_program:
            # model_construct 绕开字面量校验，用于模拟模型返回不受支持的策略
            program_spec = ProgramSpec.model_construct(
                field_programs=[
                    FieldProgramSpec(
                        field_name=fields[0].name,
                        strategy="css",
                        selector="h1",
                        enabled=True,
                    ),
                    FieldProgramSpec.model_construct(
                        field_name=fields[0].name,
                        strategy="javascript",  # 不安全策略，必须被净化并上报
                        enabled=True,
                    ),
                ]
            )
        issues = [f"rejected unsafe strategy 'javascript' for field '{fields[0].name}'"]
        return "已按你的描述调整契约", schema, program_spec, ["新增了字段"], issues if self.unsafe_program else []


@given("一个已持久化的高校通知抽取任务")
def persisted_extraction(context, builtin_schema):
    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/001",
            html=NOTICE_HTML,
            schema_name="高校通知",
            schema_spec=builtin_schema("高校通知"),
            persist_result=True,
        )
    )
    context["task_id"] = state["task_id"]
    context["schema_spec"] = state["schema_spec"]


@given("一个没有视图数据的任务")
def task_without_views(context):
    context["task_id"] = "extract-not-exist"
    context["schema_spec"] = SchemaSpec(name="高校通知", fields=[])


@given("模型返回一个含不支持策略的 ProgramSpec")
def fake_adapter_with_unsafe_program(context):
    context["adapter"] = FakeModelAdapter(unsafe_program=True)


@given("运行环境没有配置模型凭据")
def without_llm_credentials(context):
    context["adapter"] = UnconfiguredModelAdapter()


def _install_adapter(context, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.features.spec_assistant_center.router.create_model_adapter",
        lambda **_kwargs: context.get("adapter") or FakeModelAdapter(),
    )


@when("我以自然语言提出增加一个新字段的请求")
def request_revision(context, api_client, monkeypatch):
    _install_adapter(context, monkeypatch)
    context["response"] = api_client.post(
        "/api/spec-assistant/revise",
        json=SpecAssistantRequest(
            task_id=context["task_id"],
            message="请增加一个新字段：申报方式",
            schema_spec=context["schema_spec"],
        ).model_dump(mode="json"),
    )
    context["data"] = context["response"].json()


@when("我以自然语言提出修订请求")
def request_plain_revision(context, api_client, monkeypatch):
    _install_adapter(context, monkeypatch)
    context["response"] = api_client.post(
        "/api/spec-assistant/revise",
        json=SpecAssistantRequest(
            task_id=context["task_id"],
            message="请把发布日期改名为发布时间",
            schema_spec=context["schema_spec"],
        ).model_dump(mode="json"),
    )
    context["data"] = context["response"].json()


@then("修订结果包含助手回复与变更摘要")
def expect_message_and_summary(context):
    assert context["response"].status_code == 200
    assert context["data"]["assistant_message"]
    assert context["data"]["change_summary"]


@then("修订结果返回更新后的 Schema 与 ProgramSpec")
def expect_specs_returned(context):
    assert context["data"]["schema_spec"]["fields"]
    assert context["data"]["program_spec"]["field_programs"]


@then("修订结果的问题列表中包含该不安全策略")
def expect_unsafe_issue_reported(context):
    issues = context["data"]["validation_issues"]
    assert any("javascript" in issue for issue in issues), issues


@then("返回的 ProgramSpec 不包含不支持的策略")
def expect_safe_program(context):
    strategies = {
        program["strategy"] for program in context["data"]["program_spec"]["field_programs"]
    }
    assert "javascript" not in strategies


@then("接口返回客户端错误")
def expect_client_error(context):
    assert 400 <= context["response"].status_code < 500


@then("错误信息说明需要 view_bundle")
def expect_view_bundle_required(context):
    detail = context["data"]["detail"]
    assert "view_bundle" in detail or "not found" in detail


@then("接口返回错误")
def expect_error_response(context):
    assert context["response"].status_code >= 400


@then("错误信息包含缺失模型凭据的提示")
def expect_credentials_message(context):
    assert "API_KEY" in context["data"]["detail"].upper()
