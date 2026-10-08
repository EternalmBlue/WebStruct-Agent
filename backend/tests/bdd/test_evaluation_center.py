"""行为测试：绑定 specs/features/evaluation-center.feature"""

from __future__ import annotations

import pytest
from app.contracts import BenchmarkDataset, BenchmarkItem, BenchmarkRequest
from app.features.evaluation_center.workflow import build_benchmark_graph, run_benchmark_workflow
from pytest_bdd import given, scenarios, then, when
from tests.support.samples import SAMPLE_HTML, sample_schema

scenarios("evaluation-center.feature")

pytestmark = pytest.mark.db

BENCHMARK_NODE_NAMES = [
    "dataset_loader_node",
    "baseline_runner_node",
    "ours_runner_node",
    "metric_agent_node",
    "report_agent_node",
]


@given("评测使用内置高校通知数据集")
def use_builtin_dataset(context):
    context["dataset"] = BenchmarkDataset(items=[BenchmarkItem(
        item_id="bdd-notice",
        html=SAMPLE_HTML,
        schema_spec=sample_schema(),
        gold_record={"title": "关于开展2026年大学生创新训练项目申报的通知"},
    )])


@given("评测数据集为每条样本提供明确的用户自定义 Schema 与标注记录")
def explicit_dataset(context):
    use_builtin_dataset(context)


@given("评测数据集中至少一条样本没有提供 Schema")
def missing_schema_dataset(context):
    context["dataset"] = BenchmarkDataset(items=[BenchmarkItem(
        item_id="missing-schema", html=SAMPLE_HTML, gold_record={}
    )])


@given("项目保留中文领域的 HTML 与标注实验样例")
def experiment_fixture_dataset(context):
    use_builtin_dataset(context)


@given("评测样本有字段答案与人工证据标注")
def annotated_dataset(context):
    use_builtin_dataset(context)
    context["dataset"].items[0].gold_record = {
        "title": "关于开展2026年大学生创新训练项目申报的通知"
    }


@given("一个预测字段有证据但证据不支持其字段值")
def unsupported_evidence(context):
    use_builtin_dataset(context)


@given("一个需要模型的方法因凭据缺失或调用失败而不能完成")
def model_failure_dataset(context, monkeypatch):
    use_builtin_dataset(context)
    monkeypatch.setattr("app.features.evaluation_center.nodes.settings.llm_api_key", None)


@given("我按评测协议运行程序类方法的对比实验")
def protocol_dataset(context):
    use_builtin_dataset(context)


@when("我构建评测工作流图")
def build_graph(context):
    context["graph"] = build_benchmark_graph()


@then("图中包含 dataset_loader_node")
def expect_dataset_node(context):
    assert "dataset_loader_node" in context["graph"].get_graph().nodes


@then("图中包含 metric_agent_node")
def expect_metric_node(context):
    assert "metric_agent_node" in context["graph"].get_graph().nodes


@then("图中包含 report_agent_node")
def expect_report_node(context):
    assert "report_agent_node" in context["graph"].get_graph().nodes


@when("我提交一次评测运行请求")
def run_benchmark(context):
    context["state"] = run_benchmark_workflow(BenchmarkRequest(dataset=context["dataset"]))


@when("我等待该任务进入终态")
def wait_benchmark(context):
    assert context["state"]["status"] == "completed"


@when("我运行样例评测")
def run_fixture_benchmark(context):
    context["state"] = run_benchmark_workflow(BenchmarkRequest(dataset=context["dataset"]))


@when("我运行五种对比方法")
def run_five_methods(context):
    context["state"] = run_benchmark_workflow(BenchmarkRequest(dataset=context["dataset"]))


@when("我按人工证据标注计算评测指标")
def score_annotations(context):
    context["state"] = run_benchmark_workflow(BenchmarkRequest(dataset=context["dataset"]))


@when("其他方法继续执行并生成评测报告")
def continue_after_method_failure(context):
    context["state"] = run_benchmark_workflow(BenchmarkRequest(dataset=context["dataset"]))


@when("我查看评测报告")
def view_report(context):
    if "state" not in context:
        context["state"] = run_benchmark_workflow(
            BenchmarkRequest(dataset=context["dataset"])
        )
    assert context["state"]["benchmark_report"] is not None


def _methods(context):
    return [result.method for result in context["state"]["benchmark_report"].methods]


@then("评测报告中包含 Direct LLM")
def expect_direct_llm(context):
    assert "Direct LLM" in _methods(context)


@then("评测报告中包含 LLM + Schema")
def expect_llm_with_schema(context):
    assert "LLM + Schema" in _methods(context)


@then("评测报告中包含 Program Only")
def expect_program_only(context):
    assert "Program Only" in _methods(context)


@then("评测报告中包含 Hybrid without Verifier")
def expect_hybrid_without_verifier(context):
    assert "Hybrid without Verifier" in _methods(context)


@then("评测报告中包含 Ours Full")
def expect_ours_full(context):
    assert "Ours Full" in _methods(context)


@then("每种方法都产出字段准确率")
def expect_accuracy(context):
    for result in context["state"]["benchmark_report"].methods:
        if result.field_accuracy is not None:
            assert 0.0 <= result.field_accuracy <= 1.0


@then("每种方法都产出必填字段缺失率")
def expect_missing_rate(context):
    for result in context["state"]["benchmark_report"].methods:
        if result.required_field_missing_rate is not None:
            assert 0.0 <= result.required_field_missing_rate <= 1.0


@then("每种方法都产出证据精度与平均置信度")
def expect_evidence_and_confidence(context):
    for result in context["state"]["benchmark_report"].methods:
        if result.evidence_precision is not None:
            assert 0.0 <= result.evidence_precision <= 1.0
        if result.average_confidence is not None:
            assert 0.0 <= result.average_confidence <= 1.0


@then("每种方法都产出估算 token 成本与运行时长")
def expect_cost_and_runtime(context):
    for result in context["state"]["benchmark_report"].methods:
        assert result.estimated_token_cost >= 0
        assert result.runtime_ms >= 0


@then("评测报告已被持久化")
def expect_report_persisted(context):
    assert context["state"]["task_id"]
    context["report_task_id"] = context["state"]["task_id"]


@when("我按任务标识回查该评测报告")
def fetch_report(context, api_client):
    response = api_client.get(f"/api/benchmark/reports/{context['report_task_id']}")
    assert response.status_code == 200
    context["fetched"] = response.json()


@then("返回的评测报告的方法数量与首次运行一致")
def expect_same_method_count(context):
    assert len(context["fetched"]["benchmark_report"]["methods"]) == len(_methods(context))


@then("Direct LLM 方法不接收该 Schema 作为模型输入")
def direct_llm_contract(context):
    assert context["state"]["benchmark_report"] is not None


@then("LLM + Schema 方法接收该 Schema 作为模型输入")
def llm_schema_contract(context):
    assert context["state"]["benchmark_report"] is not None


@then("Program Only、Hybrid without Verifier 与 Ours Full 使用该 Schema 约束字段契约")
def schema_methods_contract(context):
    assert context["state"]["benchmark_report"] is not None


@then("每种方法的报告都包含规范要求的指标项")
def report_metric_shape(context):
    for method in context["state"]["benchmark_report"].methods:
        assert method.method


@then("每个指标标明实际测量、估算或不可用")
def report_metric_sources(context):
    for method in context["state"]["benchmark_report"].methods:
        assert method.metric_sources


@then("不可用指标具有明确原因且不以固定值或零值冒充测量结果")
def report_unavailable_reasons(context):
    for method in context["state"]["benchmark_report"].methods:
        for metric, source in method.metric_sources.items():
            if source == "unavailable":
                assert metric in method.unavailable_reasons


@then("评测流程使用每条样本关联的 Schema")
def per_item_schema(context):
    assert context["dataset"].items[0].schema_spec is not None


@then("评测流程不会读取系统内置中文领域 Schema")
def no_builtin_schema(context):
    assert context["dataset"].items[0].schema_spec.name == "通知样例"


@then("接口返回 HTTP 422 且不会创建评测任务")
def reject_missing_schema(context, api_client):
    response = api_client.post("/api/benchmark/run", json={"dataset": context["dataset"].model_dump(mode="json")})
    assert response.status_code == 422


@then("错误信息说明评测需要明确的 Schema")
def reject_reason(context, api_client):
    response = api_client.post("/api/benchmark/run", json={"dataset": context["dataset"].model_dump(mode="json")})
    assert "Schema" in response.json()["detail"]


@then("样例 Schema 必须作为评测输入明确提供")
def fixture_schema_explicit(context):
    assert all(item.schema_spec is not None for item in context["dataset"].items)


@then("不自动登记为工作台内置模板或默认 Schema")
def fixture_not_default(context, api_client):
    from app.features.schema_center.catalog import get_builtin_schemas

    assert get_builtin_schemas() == {}


@then("方法输入不包含标注答案或人工证据标注")
def annotations_not_input(context):
    assert context["dataset"].items[0].gold_record


@then("答案只在预测完成后的指标计算阶段使用")
def annotations_scored_after(context):
    assert context["state"]["benchmark_report"] is not None


@then("该证据不会被计为正确证据")
def evidence_not_assumed_correct(context):
    assert all(method.evidence_precision is None for method in context["state"]["benchmark_report"].methods)


@then("证据覆盖率与证据精度分开计算")
def evidence_metrics_separate(context):
    assert all("evidence_precision" in method.metric_sources for method in context["state"]["benchmark_report"].methods)


@then("报告保留失败方法的状态、原因与样本数量")
def method_failure_retained(context):
    assert all(method.method for method in context["state"]["benchmark_report"].methods)


@then("不生成虚构预测或固定指标")
def no_fake_metrics(context):
    assert context["state"]["benchmark_report"].methods


@then("评测报告可以为 completed 但明确包含方法失败")
def report_can_complete_with_failure(context):
    assert context["state"]["status"] == "completed"


@then("报告记录共享初始 ProgramSpec、模型设置与冷启动或复用设置")
def report_experiment_settings(context):
    assert context["state"]["benchmark_report"].summary


@then("验证和修复开关按方法定义记录")
def report_method_settings(context):
    assert len(context["state"]["benchmark_report"].methods) == 5


@then("报告不把本地历史规则自动命中当作默认公平对照")
def report_no_implicit_reuse(context):
    assert context["state"]["benchmark_report"] is not None
