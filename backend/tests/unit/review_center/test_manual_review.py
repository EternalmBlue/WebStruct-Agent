
import pytest
from app.contracts import (
    ExtractionRequest,
)
from app.features.extraction_center.workflow import run_extraction_workflow
from app.main import app
from fastapi.testclient import TestClient

from tests.support.samples import SAMPLE_HTML, builtin_request_schema

client = TestClient(app)


@pytest.mark.db
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
    assert response.status_code == 202
    task_id = response.json()["task_id"]
    import time
    for _ in range(100):
        if client.get(f"/api/runs/{task_id}").json()["status"] in {"completed", "failed"}:
            break
        time.sleep(0.02)
    data = client.get(f"/api/extract/{task_id}").json()

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
