import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.mark.postgres
def test_health_endpoint_returns_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "WebStruct-Agent"
    assert data["model_mode"] in {"deepseek", "openai-compatible"}
    assert isinstance(data["llm_configured"], bool)
    assert isinstance(data["llm_model"], str)
    assert data["database_driver"] in {"postgresql+psycopg", "postgresql"}
