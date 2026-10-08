
import pytest
from app.contracts import (
    ExtractionRequest,
    FieldSpec,
    SchemaSpec,
)
from app.features.extraction_center.workflow import build_extraction_graph, run_extraction_workflow
from app.main import app
from fastapi.testclient import TestClient

from tests.support.samples import SAMPLE_HTML, builtin_request_schema

client = TestClient(app)


def test_extraction_graph_compiles() -> None:
    assert build_extraction_graph() is not None


def test_extraction_workflow_returns_evidence_and_verification() -> None:
    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/001",
            html=SAMPLE_HTML,
            schema_name="高校通知",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    result = state["extraction_result"]
    fields = {field.field_name: field for field in result.fields}

    assert state["status"] == "completed"
    assert fields["title"].normalized_value == "关于开展2026年大学生创新训练项目申报的通知"
    assert fields["publish_date"].normalized_value == "2026-06-12"
    assert fields["deadline"].normalized_value == "2026-06-30"
    assert fields["publish_date"].evidence
    assert state["view_bundle"].metadata["text_block_count"] >= 4
    assert state["verification_report"].passed
    assert len(state["agent_traces"]) >= 9


def test_missing_required_field_records_explicit_fallback_failure_without_key(monkeypatch) -> None:
    monkeypatch.setattr("app.features.extraction_center.nodes.settings.llm_api_key", None)

    schema = SchemaSpec(
        name="Fallback Required",
        domain="test",
        fields=[
            FieldSpec(
                name="title",
                description="标题",
                type="text",
                required=True,
                aliases=["标题"],
            ),
            FieldSpec(
                name="approval_code",
                description="批准编号",
                type="string",
                required=True,
                aliases=["批准编号"],
            ),
        ],
    )

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/fallback-required",
            html="<html><body><h1>测试通知</h1><p>发布日期：2026年06月12日</p></body></html>",
            schema_name=schema.name,
            schema_spec=schema,
            persist_result=False,
        )
    )

    fields = {field.field_name: field for field in state["extraction_result"].fields}
    issues = {issue.code for issue in state["verification_report"].issues}

    assert state["status"] == "completed"
    assert fields["title"].normalized_value == "测试通知"
    assert fields["approval_code"].status == "missing"
    assert "required_field_missing" in issues


@pytest.mark.db


def test_direct_workflow_can_skip_persistence() -> None:
    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/no-persist",
            html=SAMPLE_HTML,
            schema_name="高校通知",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    assert state["status"] == "completed"


def test_extraction_workflow_stops_after_failed_collector_node() -> None:
    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="http://127.0.0.1:9/unreachable",
            schema_name="高校通知",
            persist_result=False,
        )
    )

    assert state["status"] == "failed"
    assert any("page_collector_node" in error for error in state["errors"])
    failed_traces = [
        trace for trace in state["agent_traces"] if trace.status == "failed"
    ]
    assert [trace.name for trace in failed_traces] == ["page_collector_node"]
