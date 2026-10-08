
from app.contracts import (
    ExtractionRequest,
    FieldSpec,
    SchemaSpec,
)
from app.features.extraction_center.workflow import run_extraction_workflow
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_schema_agent_infers_schema_for_url_when_no_schema_is_provided(monkeypatch) -> None:
    class FakeSchemaAndProgramAdapter:
        def generate_schema_spec(self, *, view_bundle):
            assert "阿道夫·希特勒" in view_bundle.text
            return SchemaSpec(
                name="自动字段契约 - 百科人物",
                domain="encyclopedia_person",
                description="AI 根据百科页面生成的人物字段契约",
                fields=[
                    FieldSpec(
                        name="title",
                        description="页面人物名称",
                        type="text",
                        required=True,
                        aliases=["标题", "人物名称"],
                    ),
                    FieldSpec(
                        name="birth_date",
                        description="出生日期",
                        type="date",
                        required=False,
                        aliases=["出生", "出生日期"],
                    ),
                    FieldSpec(
                        name="nationality",
                        description="国籍",
                        type="string",
                        required=False,
                        aliases=["国籍"],
                    ),
                ],
            )

        def generate_program_spec(
            self,
            *,
            schema_spec,
            extraction_plan,
            view_bundle,
            fallback_program_spec,
        ):
            return fallback_program_spec

        def extract_field(self, field, view_bundle):
            return None, None

    monkeypatch.setattr(
        "app.features.extraction_center.nodes.create_model_adapter",
        lambda **kwargs: FakeSchemaAndProgramAdapter(),
    )

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://zh.wikipedia.org/wiki/adolf-hitler",
            html="""
            <html>
              <body>
                <h1>阿道夫·希特勒</h1>
                <p>阿道夫·希特勒是德国政治人物。</p>
                <p>出生日期：1889年4月20日</p>
                <p>国籍：德国</p>
              </body>
            </html>
            """,
            persist_result=False,
        )
    )

    field_names = {field.name for field in state["schema_spec"].fields}
    assert state["schema_generation_mode"] == "llm"
    assert state["schema_spec"].name == "自动字段契约 - 百科人物"
    assert "birth_date" in field_names
    assert "deadline" not in field_names
    assert state["extraction_result"].schema_name == "自动字段契约 - 百科人物"
