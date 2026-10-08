"""行为覆盖：observability-center.feature 的运行协议。"""

import time

import pytest
from app.contracts import ExtractionRequest, FieldSpec, SchemaSpec
from app.platform.observability import runtime

from tests.support.samples import NOTICE_HTML


def _wait_terminal(api_client, task_id: str) -> dict:
    deadline = time.monotonic() + 10
    snapshot = api_client.get(f"/api/runs/{task_id}").json()
    while time.monotonic() < deadline and snapshot["status"] not in {"completed", "failed"}:
        time.sleep(0.02)
        snapshot = api_client.get(f"/api/runs/{task_id}").json()
    return snapshot


@pytest.mark.db
def test_run_events_cursor_and_quality_are_independent(api_client):
    schema = SchemaSpec(
        name="Observability sample",
        domain="test",
        fields=[FieldSpec(name="title", description="标题", type="text", required=True)],
    )
    receipt = api_client.post(
        "/api/extract",
        json=ExtractionRequest(html=NOTICE_HTML, schema_spec=schema).model_dump(mode="json"),
    )
    assert receipt.status_code == 202
    task_id = receipt.json()["task_id"]
    snapshot = _wait_terminal(api_client, task_id)
    assert snapshot["correlation_id"]
    events = api_client.get(f"/api/runs/{task_id}/events").json()
    assert any(event["event_type"] == "task_queued" for event in events["events"])
    assert any(
        event["event_type"] == "node_started" and event["runtime_ms"] is None
        for event in events["events"]
    )
    cursor = events["next_cursor"]
    assert api_client.get(f"/api/runs/{task_id}/events?after_cursor={cursor}").json()["events"] == []
    result = api_client.get(f"/api/extract/{task_id}")
    assert result.status_code == 200
    assert result.json()["status"] == "completed"


def test_retry_creates_new_task_and_keeps_original(api_client):
    receipt = runtime.create("extraction", ["failing_node"], {"target_url": "x"})
    runtime.start(receipt["task_id"])
    runtime.node(receipt["task_id"], "failing_node", "TestAgent", "failed", runtime_ms=1,
                 error_message="expected failure")
    runtime.finish(receipt["task_id"], {"status": "failed", "errors": ["expected failure"]}, 1)
    original_events = api_client.get(
        f"/api/runs/{receipt['task_id']}/events"
    ).json()["events"]
    retry = api_client.post(f"/api/runs/{receipt['task_id']}/retry")
    assert retry.status_code == 202
    assert retry.json()["task_id"] != receipt["task_id"]
    assert retry.json()["correlation_id"] == receipt["correlation_id"]
    retry_snapshot = api_client.get(
        f"/api/runs/{retry.json()['task_id']}"
    ).json()
    assert retry_snapshot["original_task_id"] == receipt["task_id"]
    assert retry_snapshot["correlation_id"] == receipt["correlation_id"]
    assert api_client.get(f"/api/runs/{receipt['task_id']}").json()["status"] == "failed"
    assert api_client.get(
        f"/api/runs/{receipt['task_id']}/events"
    ).json()["events"] == original_events
