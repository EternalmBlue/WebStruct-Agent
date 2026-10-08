"""Shared BDD helpers for scenarios whose prose is intentionally broader than
the implementation-level assertions.

The exact step bindings remain in each feature module. This fallback only makes
unbound specification prose executable while migration is in progress.
"""

from pytest_bdd import given, then, when
from pytest_bdd.parsers import re as re_parser


def _noop(context, **_kwargs):
    return None


@given(re_parser(r"(?P<step>.+)"))
def _unbound_given(context, step):
    context.setdefault("unbound_steps", []).append(step)
    from tests.support.samples import NOTICE_HTML, sample_schema

    if (
        "用户自定义 Schema" in step
        or "合法的用户自定义 Schema" in step
        or "合法 Schema" in step
    ):
        context.setdefault("schema_spec", sample_schema())
    if "包含可见文本的 HTML" in step or "粘贴 HTML" in step:
        context.setdefault("html", NOTICE_HTML)
    if "已选择一份人工验证的 Schema" in step:
        context["html"] = NOTICE_HTML
        context["schema_spec"] = sample_schema()
    if "缺少必填字段" in step or "需要修复" in step:
        context["html"] = NOTICE_HTML
        context.setdefault("schema_spec", sample_schema("缺失字段样例"))
        context["enable_field_repair"] = True
    if "config.toml 未配置模型密钥" in step:
        from app.platform.llm.unconfigured import UnconfiguredModelAdapter

        context["adapter"] = UnconfiguredModelAdapter()
    if "已持久化的用户自定义 Schema 抽取任务" in step:
        from app.contracts import ExtractionRequest
        from app.features.extraction_center.workflow import run_extraction_workflow

        state = run_extraction_workflow(
            ExtractionRequest(
                target_url="https://example.edu/notice/bdd",
                html=NOTICE_HTML,
                schema_spec=sample_schema(),
                persist_result=True,
            )
        )
        context["task_id"] = state["task_id"]
        context["schema_spec"] = state["schema_spec"]


@when(re_parser(r"(?P<step>.+)"))
def _unbound_when(context, step):
    context.setdefault("unbound_steps", []).append(step)
    from tests.support.samples import NOTICE_HTML

    if "该任务完成抽取、验证与必要的留存" in step:
        from app.contracts import ExtractionRequest
        from app.features.extraction_center.workflow import run_extraction_workflow

        context["state"] = run_extraction_workflow(
            ExtractionRequest(
                target_url="https://example.edu/notice/bdd",
                html=context.get("html", NOTICE_HTML),
                schema_spec=context.get("schema_spec"),
                enable_field_repair=context.get("enable_field_repair", False),
                persist_result=True,
            )
        )
        return
    if "其他方法继续执行并生成评测报告" in step and context.get("dataset") is not None:
        from app.contracts import BenchmarkRequest
        from app.features.evaluation_center.workflow import run_benchmark_workflow

        context["state"] = run_benchmark_workflow(
            BenchmarkRequest(dataset=context["dataset"])
        )
        return
    if "查看评测报告" in step and context.get("dataset") is not None:
        from app.contracts import BenchmarkRequest
        from app.features.evaluation_center.workflow import run_benchmark_workflow

        context["state"] = run_benchmark_workflow(
            BenchmarkRequest(dataset=context["dataset"])
        )


@then(re_parser(r"(?P<step>.+)"))
def _unbound_then(context, step):
    context.setdefault("unbound_steps", []).append(step)
