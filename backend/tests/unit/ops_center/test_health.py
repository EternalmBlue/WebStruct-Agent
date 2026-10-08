import pytest
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.db
def test_health_endpoint_returns_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "WebStruct-Agent"
    assert data["model_mode"] in {"deepseek", "openai-compatible"}
    assert isinstance(data["llm_configured"], bool)
    # 本地默认 SQLite、容器内为 PostgreSQL，健康检查只负责如实报告驱动类型
    assert isinstance(data["llm_model"], str)
    assert isinstance(data["database_driver"], str)
