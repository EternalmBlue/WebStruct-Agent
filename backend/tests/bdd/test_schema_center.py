"""行为测试：绑定 specs/features/schema-center.feature"""

from __future__ import annotations

import pytest
from app.contracts import FieldSpec, SchemaSpec
from app.features.schema_center.catalog import get_builtin_schemas
from app.features.schema_center.repository import persist_schema_version
from app.features.schema_center.validation import validate_schema_spec
from pytest_bdd import given, scenarios, then, when

from tests.bdd.feature_paths import feature_path

scenarios(feature_path("schema-center.feature"))

pytestmark = pytest.mark.db


@when("我请求内置 Schema 列表")
def request_builtin_schemas(context):
    context["schemas"] = list(get_builtin_schemas().values())


@then("返回至少 3 个 Schema")
def expect_three_domains(context):
    assert len(context["schemas"]) >= 3


@then("每个 Schema 都包含名称与至少一个字段")
def expect_named_fields(context):
    for schema in context["schemas"]:
        assert schema.name.strip()
        assert len(schema.fields) >= 1


@then("列表中包含 高校通知 Schema")
def expect_university_notice(context):
    assert any(schema.name == "高校通知" for schema in context["schemas"])


@given("一个含必填字段但缺少描述的 Schema")
def schema_with_blank_required_description(context):
    context["schema_spec"] = SchemaSpec(
        name="测试Schema",
        fields=[FieldSpec(name="title", type="string", required=True, description="")],
    )


@given("一个缺少日期语义的日期字段 Schema")
def schema_with_weak_date_field(context):
    context["schema_spec"] = SchemaSpec(
        name="测试Schema",
        fields=[
            FieldSpec(
                name="begin_time",
                type="date",
                required=False,
                description="活动开始时刻",
            )
        ],
    )


@given("一个合法的高校通知 Schema")
def valid_university_schema(context, builtin_schema):
    context["schema_spec"] = builtin_schema("高校通知")


@when("我提交该 Schema 进行校验")
def submit_schema_for_validation(context):
    schema_spec = context["schema_spec"]
    context["errors"] = validate_schema_spec(schema_spec)
    context["schema_version"] = (
        persist_schema_version(schema_spec=schema_spec, source="validation")
        if not context["errors"]
        else None
    )


@then("校验结果为不通过")
def expect_invalid(context):
    assert context["errors"]


@then("校验结果为通过")
def expect_valid(context):
    assert context["errors"] == []


@then("错误列表提示该必填字段需要填写描述")
def expect_description_error(context):
    assert any("description" in message for message in context["errors"])


@then("错误列表提示该日期字段需要日期或时间语义")
def expect_date_semantics_error(context):
    assert any("date/time semantics" in message for message in context["errors"])


@then("该 Schema 会生成一条 Schema 版本记录")
def expect_version_persisted(context):
    version = context["schema_version"]
    assert version is not None
    assert version["version"] >= 1
    assert version["schema_name"] == context["schema_spec"].name
    assert version["source"] == "validation"
