
import pytest
from app.features.schema_center.catalog import get_builtin_schemas
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_schema_catalog_is_empty_without_persisted_user_or_model_schemas() -> None:
    response = client.get("/api/schemas")

    assert response.status_code == 200
    assert get_builtin_schemas() == {}




@pytest.mark.db
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
