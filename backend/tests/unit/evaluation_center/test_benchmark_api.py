
import pytest
from app.contracts import BenchmarkDataset, BenchmarkItem
from app.features.evaluation_center.workflow import build_benchmark_graph
from app.main import app
from fastapi.testclient import TestClient

from tests.support.samples import SAMPLE_HTML, sample_schema

client = TestClient(app)


def test_benchmark_graph_compiles() -> None:
    assert build_benchmark_graph() is not None


@pytest.mark.db
def test_benchmark_api_returns_required_methods(monkeypatch) -> None:
    monkeypatch.setattr("app.features.evaluation_center.nodes.settings.llm_api_key", None)

    dataset = BenchmarkDataset(items=[BenchmarkItem(
        item_id="test-1", html=SAMPLE_HTML, schema_spec=sample_schema(),
        gold_record={"title": "关于开展2026年大学生创新训练项目申报的通知"},
    )])
    response = client.post("/api/benchmark/run", json={"dataset": dataset.model_dump(mode="json")})
    assert response.status_code == 202
    task_id = response.json()["task_id"]
    import time
    for _ in range(200):
        if client.get(f"/api/runs/{task_id}").json()["status"] in {"completed", "failed"}:
            break
        time.sleep(0.02)
    data = client.get(f"/api/benchmark/reports/{task_id}").json()
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
