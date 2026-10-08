"""行为测试：绑定 specs/features/ops-center.feature"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.bdd.feature_paths import feature_path

scenarios(feature_path("ops-center.feature"))

pytestmark = pytest.mark.db


@given("后端应用已启动")
def backend_started(api_client):
    return api_client


@given("运行环境没有配置模型凭据")
def without_llm_credentials(monkeypatch):
    monkeypatch.setattr("app.features.ops_center.router.settings.llm_api_key", None)


@when("我请求健康检查接口")
def request_health(context, api_client):
    context["response"] = api_client.get("/api/health")
    context["data"] = context["response"].json()


@then("返回的运行状态为 ok")
def health_status_ok(context):
    assert context["response"].status_code == 200
    assert context["data"]["status"] == "ok"


@then("响应包含模型模式与模型名称")
def health_exposes_model(context):
    assert context["data"]["model_mode"] in {"deepseek", "openai-compatible"}
    assert isinstance(context["data"]["llm_model"], str)


@then("响应包含是否已配置模型凭据")
def health_exposes_credentials_state(context):
    assert isinstance(context["data"]["llm_configured"], bool)


@then("响应中的已配置模型凭据为否")
def health_reports_missing_credentials(context):
    assert context["data"]["llm_configured"] is False
