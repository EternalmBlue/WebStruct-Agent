"""行为测试：绑定 specs/features/review-center.feature"""

from __future__ import annotations

import pytest
from app.contracts import ExtractionRequest, ManualReviewField, ManualReviewRequest
from app.features.extraction_center.workflow import run_extraction_workflow
from app.features.program_center.plan import build_extraction_plan, build_program_spec
from app.features.program_center.repository import (
    get_user_verified_program_spec,
    list_user_verified_program_specs,
)
from pytest_bdd import given, scenarios, then, when

from tests.support.samples import NOTICE_HTML

scenarios("review-center.feature")

pytestmark = pytest.mark.db


@given("一条待复核的抽取任务")
def a_completed_extraction(context, builtin_schema):
    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/001",
            html=NOTICE_HTML,
            schema_name="高校通知",
            schema_spec=builtin_schema("高校通知"),
            persist_result=False,
        )
    )
    context["schema_spec"] = state["schema_spec"]
    context["task_id"] = state["task_id"]
    context["program_spec"] = build_program_spec(build_extraction_plan(state["schema_spec"]))
    context["fields"] = [
        ManualReviewField(field_name=field.name, value="", accepted=True)
        for field in state["schema_spec"].fields
    ]


@when("我提交一次人工复核")
def submit_review(context, api_client):
    context["response"] = api_client.post(
        "/api/reviews/manual",
        json=ManualReviewRequest(
            task_id=context["task_id"],
            schema_spec=context["schema_spec"],
            fields=context["fields"],
        ).model_dump(mode="json"),
    )
    context["data"] = context["response"].json()


@when("我提交一次人工复核并标记程序可用")
def submit_review_marking_program(context, api_client):
    context["response"] = api_client.post(
        "/api/reviews/manual",
        json=ManualReviewRequest(
            task_id=context["task_id"],
            schema_spec=context["schema_spec"],
            program_spec=context["program_spec"],
            fields=context["fields"],
            mark_program_verified=True,
            rule_name="复核通过的高校通知规则",
        ).model_dump(mode="json"),
    )
    context["data"] = context["response"].json()


@when("我提交一次未附带 ProgramSpec 却要求标记程序可用的复核")
def submit_review_without_program(context, api_client):
    context["response"] = api_client.post(
        "/api/reviews/manual",
        json=ManualReviewRequest(
            task_id=context["task_id"],
            schema_spec=context["schema_spec"],
            fields=context["fields"],
            mark_program_verified=True,
        ).model_dump(mode="json"),
    )
    context["data"] = context["response"].json()


@then("返回状态为复核完成")
def expect_reviewed(context):
    assert context["response"].status_code == 200
    assert context["data"]["status"] == "reviewed"


@then("返回的字段数量等于我提交的字段数")
def expect_field_count(context):
    assert context["data"]["field_count"] == len(context["fields"])


@then("该 ProgramSpec 会被登记为已验证程序")
def expect_program_verified(context):
    assert get_user_verified_program_spec(context["schema_spec"]) is not None


@then("已验证 ProgramSpec 列表中包含该 Schema")
def expect_listed_schema(context):
    names = {item["rule_name"] for item in list_user_verified_program_specs()}
    assert "复核通过的高校通知规则" in names


@then("接口返回客户端错误")
def expect_client_error(context):
    assert 400 <= context["response"].status_code < 500


@then("错误信息说明需要提供 ProgramSpec")
def expect_program_required_message(context):
    assert "program_spec" in context["data"]["detail"]
