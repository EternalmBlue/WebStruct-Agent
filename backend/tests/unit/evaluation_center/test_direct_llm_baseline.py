from types import SimpleNamespace

from app.contracts import PageObservation
from app.features.evaluation_center.nodes import _run_direct_llm
from app.features.page_center.views import normalize_page_view
from app.platform.llm.openai_compatible import OpenAICompatibleModelAdapter
from app.platform.observability.telemetry import capture_observations


def test_direct_llm_is_one_generic_record_call_without_schema(monkeypatch):
    requests = []

    def fake_post(endpoint, **kwargs):
        requests.append(kwargs["json"])
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "choices": [
                    {
                        "message": {
                            "content": '{"record":{"title":"公告"},"evidence":{"title":{"text":"公告","confidence":0.9}}}'
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("app.platform.llm.openai_compatible.httpx.post", fake_post)
    view = normalize_page_view(
        PageObservation(
            url="https://example.test/",
            html="<html><body><h1>公告</h1></body></html>",
            text="公告",
        )
    )
    adapter = OpenAICompatibleModelAdapter(api_key="test-key")
    with capture_observations() as events:
        result = _run_direct_llm(task_id="direct-test", view_bundle=view, adapter=adapter)

    assert len(requests) == 1
    prompt = " ".join(message["content"] for message in requests[0]["messages"])
    assert "FieldSpec" not in prompt
    assert '"schema_spec"' not in prompt
    assert [field.field_name for field in result.fields] == ["title"]
    assert [event["event_type"] for event in events] == ["model_call"]
