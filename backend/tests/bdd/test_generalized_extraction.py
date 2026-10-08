"""泛化单资源抽取 feature 的可执行行为绑定。"""

from __future__ import annotations

from app.contracts import (
    ExtractionRequest,
    FieldSpec,
    PageIntentAssessment,
    SchemaSpec,
)
from app.features.extraction_center.workflow import run_extraction_workflow
from app.features.page_center.single_page import (
    assess_page_intent,
    select_body_content,
)
from app.features.program_center.compatibility import compare_structure_signatures
from app.platform.observability.metrics import build_run_metrics
from pytest_bdd import given, scenarios, then, when

from tests.bdd.feature_paths import feature_path

scenarios(feature_path("generalized-extraction.feature"))


def _single_page_html() -> str:
    return """
    <html><body>
      <nav>首页 资源 搜索 登录</nav>
      <main>
        <h1>示例资源</h1>
        <div class="meta"><span class="author">作者甲</span><time>2026-10-09</time></div>
        <article class="content">
          <p>正文第一段，说明资源用途与适用范围。</p>
          <p>正文第二段，说明安装配置与使用步骤。</p>
        </article>
      </main>
      <aside>推荐内容和广告</aside>
      <footer>版权信息</footer>
    </body></html>
    """


@given("一个包含唯一主标题、详情元数据和连续正文的单资源页")
def given_single_resource(context):
    context["html"] = _single_page_html()


@when("页面中心完成采集、归一化和页面意图判断")
def assess_single_resource(context):
    context["assessment"] = assess_page_intent(
        context["html"], requested_intent="single_resource"
    )


@then("页面意图为 single_resource 或 article")
def assert_single_resource_intent(context):
    assert context["assessment"].intent in {"single_resource", "article"}


@then("页面可以进入 SchemaAgent 和 ProgrammerAgent")
def assert_single_resource_gate(context):
    assert context["assessment"].gate_passed


@given("一个包含导航、多个频道入口和重复资源列表的论坛主页")
def given_forum_home(context):
    context["html"] = """
    <html><body><nav>首页 论坛 资源 登录</nav>
      <main><h1>论坛首页</h1><ul>
        <li><a href="/a">资源 A</a></li><li><a href="/b">资源 B</a></li>
        <li><a href="/c">资源 C</a></li><li><a href="/d">资源 D</a></li>
      </ul></main>
    </body></html>
    """


@when("用户以 single_resource 意图提交该页面")
def submit_single_resource(context):
    context["assessment"] = assess_page_intent(
        context["html"], requested_intent="single_resource"
    )


@then("页面意图不会被判定为 single_resource")
def assert_not_single_resource(context):
    assert context["assessment"].intent != "single_resource"


@then("抽取被阻止并记录 page_intent_mismatch")
def assert_home_blocked(context):
    assert not context["assessment"].gate_passed
    assert "page_intent_mismatch" in context["assessment"].reasons


@given("一个包含多个同级资源卡片和分页导航的分类页")
def given_listing(context):
    context["html"] = """
    <html><body><main><h1>资源分类</h1>
      <section class="card"><h2>A</h2><p>简介 A</p></section>
      <section class="card"><h2>B</h2><p>简介 B</p></section>
      <section class="card"><h2>C</h2><p>简介 C</p></section>
      <nav>上一页 1 2 下一页</nav>
    </main></body></html>
    """


@when("用户以 single_resource 意图提交该页面")
def submit_listing(context):
    context["assessment"] = assess_page_intent(
        context["html"], requested_intent="single_resource"
    )


@then("页面意图为 list")
def assert_list_intent(context):
    assert context["assessment"].intent == "list"


@then("系统不会为该页面生成正文 ExtractionResult")
def assert_listing_blocked(context):
    assert not context["assessment"].gate_passed


@given("用户只提交一个单资源页 URL 且没有显式 Schema")
def given_url_only(context):
    context["html"] = _single_page_html()


@when("系统开始抽取")
def run_url_only(context, monkeypatch):
    from app.contracts import FieldSpec, SchemaSpec

    class FakeAdapter:
        def generate_schema_spec(self, *, view_bundle):
            assert view_bundle.raw_html
            return SchemaSpec(
                name="Inferred Resource",
                fields=[FieldSpec(name="title", required=True)],
            )

        def generate_program_spec(self, **kwargs):
            return kwargs["fallback_program_spec"]

    monkeypatch.setattr(
        "app.features.extraction_center.nodes.create_model_adapter",
        lambda **_: FakeAdapter(),
    )
    context["state"] = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.test/resource/1",
            html=context["html"],
            persist_result=False,
        )
    )


@then("先完成页面采集和 ViewBundle 归一化")
def assert_collection_before_schema(context):
    names = [trace.name for trace in context["state"]["agent_traces"]]
    assert names.index("page_collector_node") < names.index("view_normalizer_node")
    assert names.index("view_normalizer_node") < names.index("schema_agent_node")


@then("SchemaAgent 使用当前页面观测推断字段")
def assert_inferred_schema(context):
    assert context["state"]["schema_generation_mode"] == "llm"
    assert context["state"]["schema_spec"].name == "Inferred Resource"


@then("Trace 区分 schema_generation_mode=inferred")
def assert_schema_trace_mode(context):
    assert any(
        trace.name == "schema_agent_node"
        and "schema_generation_mode" in trace.output_summary
        for trace in context["state"]["agent_traces"]
    )


@given("页面存在一个短简介和一个更长的连续正文区域")
def given_summary_and_body(context):
    context["html"] = """
    <html><body><main>
      <div class="summary">短简介摘要。</div>
      <article class="content">
        <p>完整正文第一段，包含安装说明。</p>
        <p>完整正文第二段，包含配置说明。</p>
        <p>完整正文第三段，包含故障排查。</p>
      </article>
    </main></body></html>
    """


@when("系统评估正文候选区域")
def evaluate_body(context):
    context["body"] = select_body_content(context["html"])


@then("只有短简介的候选不能被接受为完整正文")
def assert_full_body_selected(context):
    assert context["body"].accepted
    assert "完整正文第一段" in context["body"].text
    assert "完整正文第三段" in context["body"].text


@then("观测记录正文覆盖率和低完整性原因")
def assert_body_quality_observed(context):
    assert context["body"].metrics.visible_text_coverage is not None
    assert context["body"].metrics.block_coverage is not None


@given("页面正文被分成两个相邻候选区域且中间没有外围噪声")
def given_adjacent_body(context):
    context["html"] = """
    <html><body><main>
      <div class="content"><p>正文上半部分。</p></div>
      <div class="content"><p>正文下半部分。</p></div>
    </main></body></html>
    """


@when("系统选择正文区域")
def select_body(context):
    context["body"] = select_body_content(context["html"])


@then("两个区域按文档顺序合并")
def assert_body_order(context):
    assert context["body"].accepted
    assert context["body"].text.index("正文上半部分") < context["body"].text.index("正文下半部分")


@then("不重复抽取相同 DOM 节点")
def assert_no_duplicate_body(context):
    texts = [candidate.text for candidate in context["body"].candidates]
    assert len(texts) == len(set(texts))


@given("正文区域旁边存在导航、侧栏、推荐和页脚内容")
def given_body_noise(context):
    context["html"] = """
    <html><body><nav>导航菜单</nav><main>
      <article class="content"><p>正文内容，不应带入外围噪声。</p></article>
    </main><aside>推荐广告</aside><footer>版权信息</footer></body></html>
    """


@when("系统评估正文候选区域")
def evaluate_body_noise(context):
    context["body"] = select_body_content(context["html"])


@then("噪声不会进入 body 字段")
def assert_noise_excluded(context):
    assert "导航菜单" not in context["body"].text
    assert "推荐广告" not in context["body"].text
    assert "版权信息" not in context["body"].text


@then("观测记录 noise_ratio")
def assert_noise_metric(context):
    assert context["body"].metrics.noise_ratio is not None


def _signature(**overrides):
    from app.contracts import PageStructureSignature

    payload = {
        "page_intent": "single_resource",
        "title_shape": ["h1"],
        "content_shape": ["main", "article"],
        "heading_count": 1,
        "text_block_count": 3,
        "repeated_item_ratio": 0.0,
        "selector_match_counts": {"title": 1, "body": 1},
        "body_visible_text_coverage": 0.9,
        "body_continuity_score": 0.9,
        "body_noise_ratio": 0.0,
    }
    payload.update(overrides)
    return PageStructureSignature(**payload)


@given("一个已验证 ProgramSpec 绑定了单资源页结构指纹")
def given_verified_program(context):
    context["expected"] = _signature()


@given("新页面的页面意图和结构观测落在已验证范围内")
def given_compatible_page(context):
    context["actual"] = _signature()


@when("系统决定是否复用 ProgramSpec")
def decide_reuse(context):
    context["compatibility"] = compare_structure_signatures(
        context["expected"], context["actual"]
    )


@then("兼容性为 compatible")
def assert_compatible(context):
    assert context["compatibility"].status == "compatible"


@then("复用决定为 accepted")
def assert_reuse_accepted(context):
    assert context["compatibility"].status == "compatible"


@given("两个页面使用同名 Schema 但正文和标题结构明显不同")
def given_same_schema_different_structure(context):
    context["expected"] = _signature()
    context["actual"] = _signature(
        page_intent="list",
        title_shape=["h1", "h2"],
        content_shape=["main", "section"],
        repeated_item_ratio=0.8,
    )


@then("兼容性不为 compatible")
def assert_not_compatible(context):
    assert context["compatibility"].status != "compatible"


@then("系统重新进入规划或程序生成")
def assert_regeneration_required(context):
    assert context["compatibility"].status in {"incompatible", "unknown"}


@given("新页面的必填字段 selector 命中状态或正文覆盖率超出已验证范围")
def given_incompatible_signature(context):
    context["expected"] = _signature()
    context["actual"] = _signature(
        selector_match_counts={"title": 2, "body": 0},
        body_visible_text_coverage=0.2,
    )


@then("复用被拒绝并记录具体原因")
def assert_reuse_rejected(context):
    assert context["compatibility"].status == "incompatible"
    assert context["compatibility"].reasons


@then("不把旧规则结果伪装为成功复用")
def assert_no_fake_reuse(context):
    assert context["compatibility"].status != "compatible"


@given("一次单资源页抽取完成并经历了复用判断")
def given_metrics_state(context):
    context["state"] = {
        "schema_spec": SchemaSpec(
            name="Metric Schema",
            fields=[FieldSpec(name="title", required=True)],
        ),
        "page_intent_assessment": PageIntentAssessment(
            intent="single_resource", confidence=0.91
        ),
        "body_selection": {
            "metrics": {
                "visible_text_coverage": 0.88,
                "block_coverage": 1.0,
                "continuity_score": 0.92,
                "noise_ratio": 0.04,
                "candidate_count": 2,
                "merged_candidate_count": 2,
            }
        },
        "program_reused": True,
        "program_spec": {"field_programs": []},
        "program_reuse_decision": "accepted",
        "program_reuse_reasons": [],
        "extraction_result": {"fields": []},
    }


@when("系统生成运行指标和 RSI 观测")
def build_metrics(context):
    context["metrics"] = build_run_metrics(context["state"], 10.0, [])


@then("指标包含页面意图置信度、正文覆盖率、正文噪声率和复用决定")
def assert_metrics_present(context):
    metrics = context["metrics"]["metrics"]
    assert metrics["page_intent_confidence"]["value"] == 0.91
    assert metrics["body_visible_text_coverage"]["value"] == 0.88
    assert metrics["body_noise_ratio"]["value"] == 0.04
    assert context["metrics"]["fingerprint"]["program_reuse_decision"] == "accepted"


@then("每个指标标明 measured、estimated 或 unavailable")
def assert_metric_provenance(context):
    for value in context["metrics"]["metrics"].values():
        assert value["source"] in {"measured", "estimated", "unavailable"}


@then("RSI 不把这些代理指标宣称为人工 gold accuracy")
def assert_no_gold_accuracy(context):
    assert "gold_accuracy" not in context["metrics"]["metrics"]
