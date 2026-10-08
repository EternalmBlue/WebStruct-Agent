
import pytest
from app.contracts import (
    FieldSpec,
    SchemaSpec,
)
from app.main import app
from fastapi.testclient import TestClient

from tests.support.samples import SAMPLE_HTML, builtin_request_schema

client = TestClient(app)


def test_extract_api_returns_400_when_page_collection_fails(monkeypatch) -> None:
    def fake_rendered(_target_url: str) -> tuple[str, int]:
        return "<html><head></head><body></body></html>", 412

    def fake_http(_target_url: str) -> tuple[str, int]:
        raise ValueError("HTTP Error 412: Precondition Failed")

    monkeypatch.setattr("app.features.page_center.collector.fetch_rendered_html", fake_rendered)
    monkeypatch.setattr("app.features.page_center.collector.fetch_html", fake_http)

    response = client.post(
        "/api/extract",
        json={"target_url": "https://example.com/blocked-empty-page"},
    )

    assert response.status_code == 202
    task_id = response.json()["task_id"]
    import time
    for _ in range(50):
        if client.get(f"/api/runs/{task_id}").json()["status"] in {"completed", "failed"}:
            break
        time.sleep(0.02)
    result = client.get(f"/api/extract/{task_id}")
    assert result.status_code == 200
    assert result.json()["status"] == "failed"
    assert any("page collection failed" in item for item in result.json()["errors"])




@pytest.mark.db
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

    assert response.status_code == 202
    task_id = response.json()["task_id"]
    import time
    for _ in range(100):
        if client.get(f"/api/runs/{task_id}").json()["status"] in {"completed", "failed"}:
            break
        time.sleep(0.02)
    data = client.get(f"/api/extract/{task_id}").json()
    assert data["status"] == "completed"
    assert data["extraction_result"]["schema_name"] == "通知样例"
    assert data["verification_report"]["passed"] is True

    detail_response = client.get(f"/api/extract/{data['task_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["task_id"] == data["task_id"]
    assert detail["schema_version"]["schema_name"] == "通知样例"
    assert detail["program_spec"]["field_programs"]




@pytest.mark.db
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
        "app.features.extraction_center.nodes.create_model_adapter",
        lambda **kwargs: FakeAutoSchemaAdapter(),
    )

    response = client.post(
        "/api/extract",
        json={
            "target_url": "https://zh.wikipedia.org/wiki/adolf-hitler",
            "html": "<html><body><h1>阿道夫·希特勒</h1><p>出生日期：1889年4月20日</p></body></html>",
        },
    )

    assert response.status_code == 202
    task_id = response.json()["task_id"]
    import time
    for _ in range(100):
        if client.get(f"/api/runs/{task_id}").json()["status"] in {"completed", "failed"}:
            break
        time.sleep(0.02)
    data = client.get(f"/api/extract/{task_id}").json()
    field_names = {field["name"] for field in data["schema_spec"]["fields"]}
    assert data["schema_generation_mode"] == "llm"
    assert data["schema_spec"]["name"] == "自动字段契约 - 百科人物"
    assert "birth_date" in field_names
    assert "deadline" not in field_names
