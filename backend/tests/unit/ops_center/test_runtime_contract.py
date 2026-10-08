import time

from app.contracts import ExtractionRequest, FieldSpec, SchemaSpec
from app.platform.configuration import load_settings
from app.platform.observability import runtime

from tests.support.samples import NOTICE_HTML


def test_toml_only_and_safe_projection(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text(
        '[model]\napi_key="test-secret"\n[database]\nurl="sqlite:///data.db"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-secret")
    loaded = load_settings(config)
    assert loaded.llm_api_key == "test-secret"
    assert str(tmp_path).replace("\\", "/") in loaded.database_url
    assert "test-secret" not in str(loaded.public_config())
    assert "test-secret" not in repr(loaded)


def test_acceptance_events_and_quality_are_independent(api_client):
    schema = SchemaSpec(name="Notice", description="test", domain="test", fields=[
        FieldSpec(name="title", description="标题", type="text", required=True, aliases=["标题"]),
        FieldSpec(name="publish_date", description="发布日期", type="date", required=True, aliases=["发布日期"]),
    ])
    response = api_client.post("/api/extract", json=ExtractionRequest(
        html=NOTICE_HTML, schema_spec=schema,
    ).model_dump(mode="json"))
    assert response.status_code == 202
    receipt = response.json()
    assert receipt["status"] == "queued"
    task_id = receipt["task_id"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        status = api_client.get(f"/api/runs/{task_id}").json()
        if status["status"] in {"completed", "failed"}:
            break
        time.sleep(.02)
    assert status["status"] == "completed"
    assert status["total_node_count"] == 9
    events = api_client.get(f"/api/runs/{task_id}/events").json()
    assert any(e["status"] == "running" and e["runtime_ms"] is None
               for e in events["events"] if e["event_type"] == "node_started")
    cursor = events["next_cursor"]
    assert not api_client.get(f"/api/runs/{task_id}/events?after_cursor={cursor}").json()["events"]
    assert api_client.get(f"/api/extract/{task_id}").status_code == 200


def test_metadata_and_restart_without_business_payload():
    receipt = runtime.create("extraction", ["slow_node"], request=None)
    runtime.start(receipt["task_id"])
    runtime.recover_interrupted()
    status = runtime.snapshot(receipt["task_id"])
    assert status["status"] == "failed"
    assert "restart" in status["errors"][0]
