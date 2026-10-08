
from app.contracts import (
    ExtractionRequest,
    FieldProgramSpec,
    ProgramSpec,
)
from app.features.extraction_center.workflow import run_extraction_workflow
from app.main import app
from app.platform.llm import ModelProviderError
from fastapi.testclient import TestClient

from tests.support.samples import SAMPLE_HTML, builtin_request_schema

client = TestClient(app)


def test_programmer_agent_generates_url_specific_program_spec_with_llm(monkeypatch) -> None:
    class FakeProgramSpecAdapter:
        def generate_program_spec(
            self,
            *,
            schema_spec,
            extraction_plan,
            view_bundle,
            fallback_program_spec,
        ):
            assert view_bundle.url == "https://example.edu/notice/ai-program"
            return ProgramSpec(
                field_programs=[
                    FieldProgramSpec(
                        field_name="title",
                        strategy="css",
                        selector="h1.notice-title",
                        postprocess=["strip", "normalize_whitespace"],
                    ),
                    *fallback_program_spec.field_programs,
                ]
            )

        def extract_field(self, field, view_bundle):
            return None, None

    monkeypatch.setattr(
        "app.features.extraction_center.nodes.create_model_adapter",
        lambda **kwargs: FakeProgramSpecAdapter(),
    )

    html = """
    <html>
      <body>
        <h1 class="notice-title">AI ProgrammerAgent 娴嬭瘯閫氱煡</h1>
        <p>鍙戝竷鏃ユ湡锛?026骞?6鏈?2鏃?/p>
        <p>鐢虫姤鎴锛?026骞?6鏈?0鏃?/p>
      </body>
    </html>
    """

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/ai-program",
            html=html,
            schema_name="楂樻牎閫氱煡",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    title_programs = [
        program
        for program in state["program_spec"].field_programs
        if program.field_name == "title"
    ]
    assert state["program_reused"] is False
    assert state["program_generation_mode"] == "llm"
    assert title_programs[0].selector == "h1.notice-title"
    assert state["extraction_result"].get_field("title").normalized_value == "AI ProgrammerAgent 娴嬭瘯閫氱煡"


def test_programmer_agent_falls_back_to_deterministic_program_spec_without_key(monkeypatch) -> None:
    monkeypatch.setattr("app.features.extraction_center.nodes.settings.llm_api_key", None)

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/no-program-key",
            html=SAMPLE_HTML,
            schema_name="楂樻牎閫氱煡",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    assert state["status"] == "completed"
    assert state["program_reused"] is False
    assert state["program_generation_mode"] == "deterministic_fallback"
    assert "model.api_key in config.toml" in state["program_generation_error"]


def test_programmer_agent_falls_back_when_llm_program_spec_generation_fails(monkeypatch) -> None:
    class BrokenProgramSpecAdapter:
        def generate_program_spec(
            self,
            *,
            schema_spec,
            extraction_plan,
            view_bundle,
            fallback_program_spec,
        ):
            raise ModelProviderError("bad ProgramSpec JSON")

        def extract_field(self, field, view_bundle):
            return None, None

    monkeypatch.setattr(
        "app.features.extraction_center.nodes.create_model_adapter",
        lambda **kwargs: BrokenProgramSpecAdapter(),
    )

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/broken-program",
            html=SAMPLE_HTML,
            schema_name="楂樻牎閫氱煡",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    assert state["status"] == "completed"
    assert state["program_generation_mode"] == "deterministic_fallback"
    assert state["program_generation_error"] == "bad ProgramSpec JSON"
    assert state["program_spec"].field_programs
