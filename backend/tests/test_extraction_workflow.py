import json

import pytest
from fastapi.testclient import TestClient

from app.benchmark.workflow import build_benchmark_graph
from app.extraction.workflow import build_extraction_graph, run_extraction_workflow
from app.main import app
from app.domain import (
    ExtractionRequest,
    FieldProgramSpec,
    FieldSpec,
    ProgramSpec,
    SchemaSpec,
    ViewBundle,
)
from app.extraction.model_adapters import (
    MissingModelConfigurationError,
    ModelProviderError,
    OpenAICompatibleModelAdapter,
)
from app.extraction.program_executor import execute_program_spec
from app.extraction.schema_catalog import get_builtin_schema
from app.storage.extraction_repository import persist_extraction_state


client = TestClient(app)


SAMPLE_HTML = """
<html>
  <head><title>关于开展2026年大学生创新训练项目申报的通知</title></head>
  <body>
    <h1>关于开展2026年大学生创新训练项目申报的通知</h1>
    <p>发布单位：教务处</p>
    <p>发布日期：2026年06月12日</p>
    <p>申报截止：2026年06月30日</p>
    <p>联系人：张老师，联系电话：010-12345678</p>
  </body>
</html>
"""


def builtin_request_schema(name: str = "高校通知") -> SchemaSpec:
    return get_builtin_schema(name)


@pytest.fixture(autouse=True)
def disable_real_programmer_llm_calls(monkeypatch) -> None:
    monkeypatch.setattr("app.extraction.agent_nodes.settings.llm_api_key", None)


def test_extraction_graph_compiles() -> None:
    assert build_extraction_graph() is not None


def test_benchmark_graph_compiles() -> None:
    assert build_benchmark_graph() is not None


def test_extraction_workflow_returns_evidence_and_verification() -> None:
    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/001",
            html=SAMPLE_HTML,
            schema_name="高校通知",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    result = state["extraction_result"]
    fields = {field.field_name: field for field in result.fields}

    assert state["status"] == "completed"
    assert fields["title"].normalized_value == "关于开展2026年大学生创新训练项目申报的通知"
    assert fields["publish_date"].normalized_value == "2026-06-12"
    assert fields["deadline"].normalized_value == "2026-06-30"
    assert fields["publish_date"].evidence
    assert state["view_bundle"].metadata["text_block_count"] >= 4
    assert state["verification_report"].passed
    assert len(state["agent_traces"]) >= 9


def test_programmer_agent_generates_url_specific_program_spec_with_llm(monkeypatch) -> None:
    class FakeProgramSpecAdapter:
        def generate_program_spec(
            self,
            *,
            schema_spec,
            extraction_plan,
            view_bundle,
            fallback_program_spec,
        ):
            assert view_bundle.url == "https://example.edu/notice/ai-program"
            return ProgramSpec(
                field_programs=[
                    FieldProgramSpec(
                        field_name="title",
                        strategy="css",
                        selector="h1.notice-title",
                        postprocess=["strip", "normalize_whitespace"],
                    ),
                    *fallback_program_spec.field_programs,
                ]
            )

        def extract_field(self, field, view_bundle):
            return None, None

    monkeypatch.setattr(
        "app.extraction.agent_nodes.create_model_adapter",
        lambda **kwargs: FakeProgramSpecAdapter(),
    )

    html = """
    <html>
      <body>
        <h1 class="notice-title">AI ProgrammerAgent 娴嬭瘯閫氱煡</h1>
        <p>鍙戝竷鏃ユ湡锛?026骞?6鏈?2鏃?/p>
        <p>鐢虫姤鎴锛?026骞?6鏈?0鏃?/p>
      </body>
    </html>
    """

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/ai-program",
            html=html,
            schema_name="楂樻牎閫氱煡",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    title_programs = [
        program
        for program in state["program_spec"].field_programs
        if program.field_name == "title"
    ]
    assert state["program_reused"] is False
    assert state["program_generation_mode"] == "llm"
    assert title_programs[0].selector == "h1.notice-title"
    assert state["extraction_result"].get_field("title").normalized_value == "AI ProgrammerAgent 娴嬭瘯閫氱煡"


def test_schema_agent_infers_schema_for_url_when_no_schema_is_provided(monkeypatch) -> None:
    class FakeSchemaAndProgramAdapter:
        def generate_schema_spec(self, *, view_bundle):
            assert "阿道夫·希特勒" in view_bundle.text
            return SchemaSpec(
                name="自动字段契约 - 百科人物",
                domain="encyclopedia_person",
                description="AI 根据百科页面生成的人物字段契约",
                fields=[
                    FieldSpec(
                        name="title",
                        description="页面人物名称",
                        type="text",
                        required=True,
                        aliases=["标题", "人物名称"],
                    ),
                    FieldSpec(
                        name="birth_date",
                        description="出生日期",
                        type="date",
                        required=False,
                        aliases=["出生", "出生日期"],
                    ),
                    FieldSpec(
                        name="nationality",
                        description="国籍",
                        type="string",
                        required=False,
                        aliases=["国籍"],
                    ),
                ],
            )

        def generate_program_spec(
            self,
            *,
            schema_spec,
            extraction_plan,
            view_bundle,
            fallback_program_spec,
        ):
            return fallback_program_spec

        def extract_field(self, field, view_bundle):
            return None, None

    monkeypatch.setattr(
        "app.extraction.agent_nodes.create_model_adapter",
        lambda **kwargs: FakeSchemaAndProgramAdapter(),
    )

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://zh.wikipedia.org/wiki/adolf-hitler",
            html="""
            <html>
              <body>
                <h1>阿道夫·希特勒</h1>
                <p>阿道夫·希特勒是德国政治人物。</p>
                <p>出生日期：1889年4月20日</p>
                <p>国籍：德国</p>
              </body>
            </html>
            """,
            persist_result=False,
        )
    )

    field_names = {field.name for field in state["schema_spec"].fields}
    assert state["schema_generation_mode"] == "llm"
    assert state["schema_spec"].name == "自动字段契约 - 百科人物"
    assert "birth_date" in field_names
    assert "deadline" not in field_names
    assert state["extraction_result"].schema_name == "自动字段契约 - 百科人物"


def test_programmer_agent_falls_back_to_deterministic_program_spec_without_key(monkeypatch) -> None:
    monkeypatch.setattr("app.extraction.agent_nodes.settings.llm_api_key", None)

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/no-program-key",
            html=SAMPLE_HTML,
            schema_name="楂樻牎閫氱煡",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    assert state["status"] == "completed"
    assert state["program_reused"] is False
    assert state["program_generation_mode"] == "deterministic_fallback"
    assert "DEEPSEEK_API_KEY" in state["program_generation_error"]


def test_programmer_agent_falls_back_when_llm_program_spec_generation_fails(monkeypatch) -> None:
    class BrokenProgramSpecAdapter:
        def generate_program_spec(
            self,
            *,
            schema_spec,
            extraction_plan,
            view_bundle,
            fallback_program_spec,
        ):
            raise ModelProviderError("bad ProgramSpec JSON")

        def extract_field(self, field, view_bundle):
            return None, None

    monkeypatch.setattr(
        "app.extraction.agent_nodes.create_model_adapter",
        lambda **kwargs: BrokenProgramSpecAdapter(),
    )

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/broken-program",
            html=SAMPLE_HTML,
            schema_name="楂樻牎閫氱煡",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    assert state["status"] == "completed"
    assert state["program_generation_mode"] == "deterministic_fallback"
    assert state["program_generation_error"] == "bad ProgramSpec JSON"
    assert state["program_spec"].field_programs


def test_missing_required_field_records_explicit_fallback_failure_without_key(monkeypatch) -> None:
    monkeypatch.setattr("app.extraction.agent_nodes.settings.llm_api_key", None)

    schema = SchemaSpec(
        name="Fallback Required",
        domain="test",
        fields=[
            FieldSpec(
                name="title",
                description="标题",
                type="text",
                required=True,
                aliases=["标题"],
            ),
            FieldSpec(
                name="approval_code",
                description="批准编号",
                type="string",
                required=True,
                aliases=["批准编号"],
            ),
        ],
    )

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/fallback-required",
            html="<html><body><h1>测试通知</h1><p>发布日期：2026年06月12日</p></body></html>",
            schema_name=schema.name,
            schema_spec=schema,
            persist_result=False,
        )
    )

    fields = {field.field_name: field for field in state["extraction_result"].fields}
    issues = {issue.code for issue in state["verification_report"].issues}

    assert state["status"] == "completed"
    assert fields["title"].normalized_value == "测试通知"
    assert fields["approval_code"].status == "fallback_failed"
    assert "llm_fallback_failed" in issues
    assert "DEEPSEEK_API_KEY" in fields["approval_code"].error_message


@pytest.mark.postgres
def test_spec_assistant_revises_schema_and_program_from_saved_view_bundle(monkeypatch) -> None:
    class FakeSpecAssistantAdapter:
        def revise_schema_and_program_spec(
            self,
            *,
            user_message,
            current_schema_spec,
            current_program_spec,
            fallback_program_spec,
            view_bundle,
        ):
            assert "作者字段" in user_message
            assert "发布单位：教务处" in view_bundle.text
            schema = SchemaSpec(
                name="协作字段契约",
                domain="notice",
                description="人工和 AI 协作修订",
                fields=[
                    FieldSpec(
                        name="title",
                        description="标题",
                        type="text",
                        required=True,
                        aliases=["标题"],
                    ),
                    FieldSpec(
                        name="author",
                        description="作者或发布单位",
                        type="string",
                        required=False,
                        aliases=["作者", "发布单位"],
                    ),
                ],
            )
            return (
                "已加入作者字段。",
                schema,
                ProgramSpec(
                    field_programs=[
                        FieldProgramSpec(
                            field_name="author",
                            strategy="text_near_label",
                            label="发布单位",
                            labels=["发布单位"],
                            postprocess=["strip", "normalize_whitespace"],
                        )
                    ]
                ),
                ["新增 author 字段"],
                [],
            )

    monkeypatch.setattr(
        "app.api.spec_assistant.create_model_adapter",
        lambda **kwargs: FakeSpecAssistantAdapter(),
    )
    schema = builtin_request_schema().model_dump(mode="json")
    extraction_response = client.post(
        "/api/extract",
        json={
            "target_url": "https://example.edu/notice/spec-assistant",
            "html": SAMPLE_HTML,
            "schema_name": "高校通知",
            "schema_spec": schema,
        },
    )
    assert extraction_response.status_code == 200
    extraction = extraction_response.json()

    response = client.post(
        "/api/spec-assistant/revise",
        json={
            "task_id": extraction["task_id"],
            "message": "把作者字段对应到发布单位。",
            "schema_spec": extraction["schema_spec"],
            "program_spec": extraction["program_spec"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["assistant_message"] == "已加入作者字段。"
    assert data["schema_spec"]["name"] == "协作字段契约"
    assert {field["name"] for field in data["schema_spec"]["fields"]} == {"title", "author"}
    assert data["program_spec"]["field_programs"][0]["field_name"] == "author"
    assert data["change_summary"] == ["新增 author 字段"]


@pytest.mark.postgres
def test_spec_assistant_requires_existing_view_bundle() -> None:
    response = client.post(
        "/api/spec-assistant/revise",
        json={
            "task_id": "missing-task",
            "message": "新增作者字段",
            "schema_spec": builtin_request_schema().model_dump(mode="json"),
        },
    )

    assert response.status_code == 404


@pytest.mark.postgres
def test_spec_assistant_requires_saved_view_bundle_payload() -> None:
    schema = builtin_request_schema()
    persist_extraction_state(
        {
            "task_id": "spec-assistant-no-view-bundle",
            "target_url": "https://example.edu/no-view",
            "status": "completed",
            "schema_spec": schema,
            "program_spec": ProgramSpec(field_programs=[]),
            "agent_traces": [],
            "errors": [],
        }
    )

    response = client.post(
        "/api/spec-assistant/revise",
        json={
            "task_id": "spec-assistant-no-view-bundle",
            "message": "新增作者字段",
            "schema_spec": schema.model_dump(mode="json"),
        },
    )

    assert response.status_code == 400
    assert "view_bundle" in response.json()["detail"]


def test_spec_assistant_sanitizes_unsafe_program_spec_and_reports_issue() -> None:
    class FakeRevisionAdapter(OpenAICompatibleModelAdapter):
        def _post_chat_completion(self, payload):
            content = {
                "assistant_message": "已生成草稿。",
                "schema_spec": {
                    "name": "协作字段契约",
                    "description": "人工和 AI 协作修订",
                    "domain": "notice",
                    "fields": [
                        {
                            "name": "title",
                            "description": "标题",
                            "type": "text",
                            "required": True,
                            "aliases": ["标题"],
                            "examples": [],
                        },
                        {
                            "name": "author",
                            "description": "作者或发布单位",
                            "type": "string",
                            "required": False,
                            "aliases": ["发布单位"],
                            "examples": [],
                        },
                    ],
                },
                "program_spec": {
                    "field_programs": [
                        {
                            "field_name": "author",
                            "strategy": "eval",
                            "selector": "exec('bad')",
                            "enabled": True,
                            "postprocess": ["strip"],
                        },
                        {
                            "field_name": "author",
                            "strategy": "text_near_label",
                            "label": "发布单位",
                            "labels": ["发布单位"],
                            "enabled": True,
                            "postprocess": ["strip", "normalize_whitespace"],
                        },
                    ]
                },
                "change_summary": ["新增 author 字段"],
                "validation_issues": [],
            }
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(content, ensure_ascii=False)
                        }
                    }
                ]
            }

    adapter = FakeRevisionAdapter(api_key="test-key")
    schema = SchemaSpec(
        name="当前字段契约",
        domain="notice",
        fields=[
            FieldSpec(
                name="title",
                description="标题",
                type="text",
                required=True,
                aliases=["标题"],
            )
        ],
    )

    _, revised_schema, revised_program, _, validation_issues = (
        adapter.revise_schema_and_program_spec(
            user_message="把作者字段对应到发布单位。",
            current_schema_spec=schema,
            current_program_spec=None,
            fallback_program_spec=ProgramSpec(field_programs=[]),
            view_bundle=ViewBundle(
                url="https://example.edu/spec-assistant-unsafe",
                raw_html="<html><body><h1>通知</h1><p>发布单位：教务处</p></body></html>",
                text="通知\n发布单位：教务处",
                lines=["通知", "发布单位：教务处"],
                title="通知",
                headings=["通知"],
            ),
        )
    )

    assert revised_schema.name == "协作字段契约"
    assert not any(program.strategy == "eval" for program in revised_program.field_programs)
    assert any(program.field_name == "author" for program in revised_program.field_programs)
    assert any("非白名单策略" in issue for issue in validation_issues)


@pytest.mark.postgres
def test_spec_assistant_fails_explicitly_without_llm_key(monkeypatch) -> None:
    monkeypatch.setattr("app.api.spec_assistant.settings.llm_api_key", None)
    schema = builtin_request_schema().model_dump(mode="json")
    extraction_response = client.post(
        "/api/extract",
        json={
            "target_url": "https://example.edu/notice/spec-assistant-no-key",
            "html": SAMPLE_HTML,
            "schema_name": "高校通知",
            "schema_spec": schema,
        },
    )
    assert extraction_response.status_code == 200
    extraction = extraction_response.json()

    response = client.post(
        "/api/spec-assistant/revise",
        json={
            "task_id": extraction["task_id"],
            "message": "新增作者字段",
            "schema_spec": extraction["schema_spec"],
            "program_spec": extraction["program_spec"],
        },
    )

    assert response.status_code == 400
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]


def test_direct_workflow_can_skip_persistence() -> None:
    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/no-persist",
            html=SAMPLE_HTML,
            schema_name="高校通知",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    assert state["status"] == "completed"


def test_extraction_workflow_stops_after_failed_collector_node() -> None:
    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="http://127.0.0.1:9/unreachable",
            schema_name="高校通知",
            persist_result=False,
        )
    )

    assert state["status"] == "completed"
    assert any("page_collector_node" in error for error in state["errors"])
    failed_traces = [
        trace for trace in state["agent_traces"] if trace.status == "failed"
    ]
    assert [trace.name for trace in failed_traces] == ["page_collector_node"]


def test_collector_rejects_empty_rendered_page_and_records_attempts(monkeypatch) -> None:
    def fake_rendered(_target_url: str) -> tuple[str, int]:
        return "<html><head></head><body></body></html>", 412

    def fake_http(_target_url: str) -> tuple[str, int]:
        raise ValueError("HTTP Error 412: Precondition Failed")

    monkeypatch.setattr("app.extraction.collector.fetch_rendered_html", fake_rendered)
    monkeypatch.setattr("app.extraction.collector.fetch_html", fake_http)

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.com/blocked-empty-page",
            persist_result=False,
        )
    )

    assert state["errors"]
    assert "page collection failed" in state["errors"][0]
    assert "HTTP 412" in state["errors"][0]
    assert "page_collector_node" in state["errors"][0]


def test_extract_api_returns_400_when_page_collection_fails(monkeypatch) -> None:
    def fake_rendered(_target_url: str) -> tuple[str, int]:
        return "<html><head></head><body></body></html>", 412

    def fake_http(_target_url: str) -> tuple[str, int]:
        raise ValueError("HTTP Error 412: Precondition Failed")

    monkeypatch.setattr("app.extraction.collector.fetch_rendered_html", fake_rendered)
    monkeypatch.setattr("app.extraction.collector.fetch_html", fake_http)

    response = client.post(
        "/api/extract",
        json={"target_url": "https://example.com/blocked-empty-page"},
    )

    assert response.status_code == 400
    assert "page collection failed" in response.json()["detail"]


@pytest.mark.postgres
def test_extract_api_uses_langgraph_workflow() -> None:
    schema = builtin_request_schema().model_dump(mode="json")
    response = client.post(
        "/api/extract",
        json={
            "target_url": "https://example.edu/notice/api-test",
            "html": SAMPLE_HTML,
            "schema_name": "高校通知",
            "schema_spec": schema,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["extraction_result"]["schema_name"] == "高校通知"
    assert data["verification_report"]["passed"] is True

    detail_response = client.get(f"/api/extract/{data['task_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["task_id"] == data["task_id"]
    assert detail["schema_version"]["schema_name"] == "高校通知"
    assert detail["program_spec"]["field_programs"]


@pytest.mark.postgres
def test_extract_api_url_only_generates_schema_instead_of_forcing_builtin(monkeypatch) -> None:
    class FakeAutoSchemaAdapter:
        def generate_schema_spec(self, *, view_bundle):
            return SchemaSpec(
                name="自动字段契约 - 百科人物",
                domain="encyclopedia_person",
                description="AI 根据百科页面生成的人物字段契约",
                fields=[
                    FieldSpec(
                        name="title",
                        description="页面人物名称",
                        type="text",
                        required=True,
                        aliases=["标题"],
                    ),
                    FieldSpec(
                        name="birth_date",
                        description="出生日期",
                        type="date",
                        required=False,
                        aliases=["出生日期"],
                    ),
                ],
            )

        def generate_program_spec(
            self,
            *,
            schema_spec,
            extraction_plan,
            view_bundle,
            fallback_program_spec,
        ):
            return fallback_program_spec

        def extract_field(self, field, view_bundle):
            return None, None

    monkeypatch.setattr(
        "app.extraction.agent_nodes.create_model_adapter",
        lambda **kwargs: FakeAutoSchemaAdapter(),
    )

    response = client.post(
        "/api/extract",
        json={
            "target_url": "https://zh.wikipedia.org/wiki/adolf-hitler",
            "html": "<html><body><h1>阿道夫·希特勒</h1><p>出生日期：1889年4月20日</p></body></html>",
        },
    )

    assert response.status_code == 200
    data = response.json()
    field_names = {field["name"] for field in data["schema_spec"]["fields"]}
    assert data["schema_generation_mode"] == "llm"
    assert data["schema_spec"]["name"] == "自动字段契约 - 百科人物"
    assert "birth_date" in field_names
    assert "deadline" not in field_names


@pytest.mark.postgres
def test_manual_review_can_mark_program_spec_verified_for_reuse() -> None:
    schema = builtin_request_schema().model_dump(mode="json")
    response = client.post(
        "/api/extract",
        json={
            "target_url": "https://example.edu/notice/review-test",
            "html": SAMPLE_HTML,
            "schema_name": "高校通知",
            "schema_spec": schema,
        },
    )
    assert response.status_code == 200
    data = response.json()

    review_response = client.post(
        "/api/reviews/manual",
        json={
            "task_id": data["task_id"],
            "schema_spec": data["schema_spec"],
            "program_spec": data["program_spec"],
            "rule_name": "高校通知详情页抽取规则",
            "mark_program_verified": True,
            "fields": [
                {
                    "field_name": field["field_name"],
                    "value": field["normalized_value"] or "",
                    "accepted": True,
                    "note": "",
                }
                for field in data["extraction_result"]["fields"]
            ],
        },
    )

    assert review_response.status_code == 200
    assert review_response.json()["program_verified"] is True

    verified_response = client.get("/api/program-specs/verified")
    assert verified_response.status_code == 200
    verified_items = verified_response.json()
    assert any(
        item["rule_name"] == "高校通知详情页抽取规则"
        for item in verified_items
    )

    default_state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/reuse-test",
            html=SAMPLE_HTML,
            schema_name="高校通知",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    assert default_state["program_reused"] is False

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/reuse-test",
            html=SAMPLE_HTML,
            schema_name="高校通知",
            schema_spec=builtin_request_schema(),
            persist_result=False,
            reuse_verified_program=True,
        )
    )

    assert state["program_reused"] is True
    assert state["status"] == "completed"


def test_extraction_ignores_unrelated_extra_dates() -> None:
    html = """
    <html>
      <body>
        <h1>关于组织2026年暑期社会实践的通知</h1>
        <p>资料更新日期：2026年01月01日</p>
        <p>发布单位：学生工作处</p>
        <p>发布日期：2026年06月18日</p>
        <p>报名截止：2026年07月10日</p>
        <p>联系人：李老师，联系电话：010-87654321</p>
      </body>
    </html>
    """

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/multi-date",
            html=html,
            schema_name="高校通知",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    fields = {field.field_name: field.normalized_value for field in state["extraction_result"].fields}
    assert fields["publish_date"] == "2026-06-18"
    assert fields["deadline"] == "2026-07-10"


def test_date_fields_ignore_embedded_suffix_dates() -> None:
    html = """
    <html>
      <body>
        <h1>关于开展2026年研究生奖学金评审工作的通知</h1>
        <p>系统更新日期：2026年01月01日</p>
        <p>发布日期：2026年05月22日</p>
        <p>申报截止：2026年06月20日</p>
        <p>发布单位：研究生院</p>
        <p>联系人：王老师，联系电话：010-99887766</p>
      </body>
    </html>
    """

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/suffix-date",
            html=html,
            schema_name="高校通知",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    fields = {field.field_name: field.normalized_value for field in state["extraction_result"].fields}
    assert fields["publish_date"] == "2026-05-22"


def test_program_executor_rejects_unsupported_strategy() -> None:
    class DummyAdapter:
        def extract_field(self, field, view_bundle):
            return None, None

    schema = SchemaSpec(
        name="Unsupported Strategy",
        domain="test",
        fields=[
            FieldSpec(
                name="title",
                description="标题",
                type="text",
                required=True,
                aliases=["标题"],
            )
        ],
    )
    view_bundle = ViewBundle(
        url="https://example.edu/unsupported",
        raw_html="<html><body><h1>测试</h1></body></html>",
        text="测试",
        lines=["测试"],
        title="测试",
        headings=["测试"],
    )
    program_spec = ProgramSpec(
        field_programs=[
            FieldProgramSpec.model_construct(
                field_name="title",
                strategy="bogus",
                enabled=True,
            )
        ]
    )

    try:
        execute_program_spec(
            task_id="test-unsupported",
            schema_spec=schema,
            view_bundle=view_bundle,
            program_spec=program_spec,
            model_adapter=DummyAdapter(),
        )
    except ValueError as exc:
        assert "unsupported ProgramSpec strategy" in str(exc)
    else:
        raise AssertionError("unsupported strategy should raise ValueError")


def test_builtin_schemas_api_exposes_three_domains() -> None:
    response = client.get("/api/schemas")

    assert response.status_code == 200
    names = {schema["name"] for schema in response.json()}
    assert {"高校通知", "招聘公告", "政务公开 / 政策法规"}.issubset(names)


@pytest.mark.postgres
def test_schema_validation_persists_schema_version() -> None:
    schema = {
        "name": "测试Schema版本",
        "description": "用于验证 schema version 持久化",
        "domain": "test",
        "fields": [
            {
                "name": "title",
                "description": "标题",
                "type": "text",
                "required": True,
                "aliases": ["标题"],
                "examples": [],
            }
        ],
    }

    response = client.post("/api/schemas/validate", json=schema)

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["schema_version"]["schema_name"] == "测试Schema版本"

    versions_response = client.get(
        "/api/schemas/versions",
        params={"schema_name": "测试Schema版本"},
    )
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert any(
        version["schema_signature"] == data["schema_version"]["schema_signature"]
        for version in versions
    )


@pytest.mark.postgres
def test_benchmark_api_returns_required_methods(monkeypatch) -> None:
    monkeypatch.setattr("app.benchmark.benchmark_nodes.settings.llm_api_key", None)

    response = client.post("/api/benchmark/run", json={"schema_name": "高校通知"})

    assert response.status_code == 200
    data = response.json()
    methods = {method["method"] for method in data["benchmark_report"]["methods"]}
    assert {
        "Direct LLM",
        "LLM + Schema",
        "Program Only",
        "Hybrid without Verifier",
        "Ours Full",
    }.issubset(methods)

    detail_response = client.get(f"/api/benchmark/reports/{data['task_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["task_id"] == data["task_id"]
    assert detail["benchmark_report"]["methods"]
