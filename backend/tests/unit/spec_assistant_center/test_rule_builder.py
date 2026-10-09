import pytest
from fastapi.testclient import TestClient

from app.contracts import (
    FieldEvidence,
    FieldExtractionResult,
    FieldProgramSpec,
    FieldSpec,
    ProgramSpec,
    SchemaSpec,
    ViewBundle,
)
from app.features.extraction_center.repository import persist_extraction_state
from app.main import app


client = TestClient(app)


def _snapshot_payload(task_id: str) -> None:
    schema = SchemaSpec(
        name="资源",
        fields=[
            FieldSpec(
                name="title",
                description="资源标题",
                type="text",
                required=True,
                aliases=["标题"],
            )
        ],
    )
    persist_extraction_state(
        {
            "task_id": task_id,
            "target_url": "https://example.com/post/1",
            "status": "completed",
            "schema_spec": schema,
            "view_bundle": ViewBundle(
                url="https://example.com/post/1",
                raw_html="<html><body><h1>资源标题</h1></body></html>",
                text="资源标题",
                lines=["资源标题"],
                title="资源标题",
            ),
            "program_spec": ProgramSpec(field_programs=[]),
            "agent_traces": [],
            "errors": [],
        }
    )


@pytest.mark.db
def test_value_collaboration_is_field_scoped(monkeypatch):
    class FakeAdapter:
        def revise_field_value(self, *, field, view_bundle, guidance_value="", evidence_text=""):
            evidence = FieldEvidence(
                field_name=field.name,
                source="llm_fallback",
                text="资源标题",
                start_char=0,
                end_char=4,
                score=0.92,
            )
            return (
                FieldExtractionResult(
                    field_name=field.name,
                    value="资源标题",
                    normalized_value="资源标题",
                    confidence=0.92,
                    evidence=[evidence],
                    strategy="llm_fallback",
                    status="extracted",
                ),
                ProgramSpec(
                    field_programs=[
                        FieldProgramSpec(
                            field_name=field.name,
                            strategy="css",
                            selector="h1",
                        )
                    ]
                ),
            )

    _snapshot_payload("builder-value-test")
    monkeypatch.setattr(
        "app.features.spec_assistant_center.builder._adapter",
        lambda: FakeAdapter(),
    )
    response = client.post(
        "/api/spec-assistant/fields/value",
        json={
            "task_id": "builder-value-test",
            "field": {
                "name": "title",
                "description": "资源标题",
                "type": "text",
                "required": True,
                "aliases": ["标题"],
                "examples": [],
            },
            "guidance_value": "资源标题",
        },
    )
    assert response.status_code == 200
    assert response.json()["result"]["field_name"] == "title"
    assert response.json()["program_spec"]["field_programs"][0]["field_name"] == "title"


@pytest.mark.db
def test_collaboration_rejects_evidence_outside_snapshot():
    _snapshot_payload("builder-evidence-test")
    response = client.post(
        "/api/spec-assistant/fields/value",
        json={
            "task_id": "builder-evidence-test",
            "field": {
                "name": "title",
                "description": "资源标题",
                "type": "text",
                "required": True,
                "aliases": [],
                "examples": [],
            },
            "evidence_text": "页面不存在的内容",
        },
    )
    assert response.status_code == 400
    assert "absent" in response.json()["detail"]
