"""行为测试：绑定 specs/features/program-center.feature"""

from __future__ import annotations

from typing import get_args

import pytest
from app.contracts import FieldProgramSpec, ProgramSpec
from app.contracts.types import ProgramStrategy
from app.features.program_center.plan import (
    build_extraction_plan,
    build_program_spec,
    sanitize_candidate_field_programs,
)
from app.features.program_center.repository import (
    list_user_verified_program_specs,
    persist_program_spec,
)
from pydantic import ValidationError
from pytest_bdd import given, scenarios, then, when

from tests.bdd.feature_paths import feature_path

scenarios(feature_path("program-center.feature"))

pytestmark = pytest.mark.db

ALLOWED_STRATEGIES = set(get_args(ProgramStrategy))


@given("一个合法的高校通知 Schema")
def valid_university_schema(context, builtin_schema):
    context["schema_spec"] = builtin_schema("高校通知")


@given("运行环境没有配置模型凭据")
def without_llm_credentials():
    """测试默认已关闭真实模型调用（见 conftest 的 autouse 夹具）。"""


@when("ProgramSpec 中心为该 Schema 生成抽取程序")
def build_program(context):
    plan = build_extraction_plan(context["schema_spec"])
    context["program_spec"] = build_program_spec(plan)


@then("生成的 ProgramSpec 为每个字段都提供了至少一条抽取程序")
def expect_program_per_field(context):
    program_spec: ProgramSpec = context["program_spec"]
    field_names = {field.name for field in context["schema_spec"].fields}
    covered = {program.field_name for program in program_spec.field_programs}
    assert field_names <= covered


@then("所有抽取程序只允许使用受支持的策略")
def expect_only_supported_strategies(context):
    for program in context["program_spec"].field_programs:
        assert program.strategy in ALLOWED_STRATEGIES


@then("生成的 ProgramSpec 仍然覆盖全部必填字段")
def expect_required_fields_covered(context):
    required = {field.name for field in context["schema_spec"].fields if field.required}
    covered = {program.field_name for program in context["program_spec"].field_programs}
    assert required <= covered


@given("一个含不支持策略的候选 ProgramSpec")
def unsafe_candidate(context):
    context["candidate"] = {
        "field_programs": [
            {
                "field_name": "title",
                "strategy": "javascript",  # 明确不在白名单内的策略
                "enabled": True,
            }
        ]
    }


@when("ProgramSpec 中心净化该候选 ProgramSpec")
def sanitize_candidate(context):
    programs, issues = sanitize_candidate_field_programs(
        context["candidate"],
        schema_spec=context["schema_spec"],
    )
    context["sanitized_programs"] = programs
    context["issues"] = issues


@then("净化后的 ProgramSpec 不包含不支持的策略")
def expect_no_unsafe_strategy(context):
    for program in context["sanitized_programs"]:
        assert program.strategy in ALLOWED_STRATEGIES


@then("净化过程至少上报一条问题")
def expect_reported_issue(context):
    assert context["issues"]


@given("一条被标记为人工验证通过的 ProgramSpec 记录")
def persisted_verified_program(context):
    if "program_spec" not in context:
        context["program_spec"] = build_program_spec(
            build_extraction_plan(context["schema_spec"])
        )
    context["rule_name"] = f"复用规则-{context['schema_spec'].name}"
    persist_program_spec(
        schema_spec=context["schema_spec"],
        program_spec=context["program_spec"],
        user_verified=True,
        rule_name=context["rule_name"],
    )


@when("我请求已验证 ProgramSpec 列表")
def request_verified_programs(context):
    context["verified"] = list_user_verified_program_specs()


@then("列表中至少包含该条记录")
def expect_record_listed(context):
    names = [item["rule_name"] for item in context["verified"]]
    assert context["rule_name"] in names


@then("列表项包含 Schema 名称与抽取程序数量")
def expect_summary_fields(context):
    item = next(
        item for item in context["verified"] if item["rule_name"] == context["rule_name"]
    )
    assert item["schema_name"] == context["schema_spec"].name
    assert item["program_count"] >= 1


@given("一个缺少 selector 的 CSS 规则与一个携带 selector 的 LLM fallback 规则")
def mismatched_program_rules(context):
    context["mismatched_program_rules"] = [
        {"field_name": "title", "strategy": "css"},
        {"field_name": "description", "strategy": "llm_fallback", "selector": "h1"},
    ]


@when("我校验这些 ProgramSpec 规则")
def validate_program_rules(context):
    context["program_rule_errors"] = []
    for payload in context["mismatched_program_rules"]:
        try:
            FieldProgramSpec.model_validate(payload)
        except ValidationError as exc:
            context["program_rule_errors"].extend(
                str(error.get("msg", "")) for error in exc.errors()
            )


@then("ProgramSpec 校验会拒绝参数不匹配的规则")
def reject_mismatched_program_rules(context):
    assert len(context["program_rule_errors"]) == 2


@then("错误信息指出具体字段与策略")
def explain_mismatched_program_rules(context):
    errors = " ".join(context["program_rule_errors"])
    assert "title" in errors and "css" in errors
    assert "description" in errors and "llm_fallback" in errors
