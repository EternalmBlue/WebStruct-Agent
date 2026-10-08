import json

import pytest
from app.contracts import (
    FieldProgramSpec,
    FieldSpec,
    ProgramSpec,
    SchemaSpec,
    ViewBundle,
)
from app.features.extraction_center.repository import persist_extraction_state
from app.main import app
from app.platform.llm import OpenAICompatibleModelAdapter
from fastapi.testclient import TestClient

from tests.support.samples import SAMPLE_HTML, builtin_request_schema

client = TestClient(app)


@pytest.mark.db
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
        "app.features.spec_assistant_center.router.create_model_adapter",
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
    assert extraction_response.status_code == 202
    task_id = extraction_response.json()["task_id"]
    import time
    for _ in range(100):
        if client.get(f"/api/runs/{task_id}").json()["status"] in {"completed", "failed"}:
            break
        time.sleep(0.02)
    extraction = client.get(f"/api/extract/{task_id}").json()

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


@pytest.mark.db


@pytest.mark.db
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


@pytest.mark.db


@pytest.mark.db
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


@pytest.mark.db


@pytest.mark.db
def test_spec_assistant_fails_explicitly_without_llm_key(monkeypatch) -> None:
    monkeypatch.setattr("app.features.spec_assistant_center.router.settings.llm_api_key", None)
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
    assert extraction_response.status_code == 202
    task_id = extraction_response.json()["task_id"]
    import time
    for _ in range(100):
        if client.get(f"/api/runs/{task_id}").json()["status"] in {"completed", "failed"}:
            break
        time.sleep(0.02)
    extraction = client.get(f"/api/extract/{task_id}").json()

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
    assert "model.api_key in config.toml" in response.json()["detail"]
