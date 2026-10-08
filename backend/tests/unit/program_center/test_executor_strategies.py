
from app.contracts import (
    FieldProgramSpec,
    FieldSpec,
    ProgramSpec,
    SchemaSpec,
    ViewBundle,
)
from app.features.extraction_center.executor import execute_program_spec
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_program_executor_rejects_unsupported_strategy() -> None:
    class DummyAdapter:
        def extract_field(self, field, view_bundle):
            return None, None

    schema = SchemaSpec(
        name="Unsupported Strategy",
        domain="test",
        fields=[
            FieldSpec(
                name="title",
                description="标题",
                type="text",
                required=True,
                aliases=["标题"],
            )
        ],
    )
    view_bundle = ViewBundle(
        url="https://example.edu/unsupported",
        raw_html="<html><body><h1>测试</h1></body></html>",
        text="测试",
        lines=["测试"],
        title="测试",
        headings=["测试"],
    )
    program_spec = ProgramSpec(
        field_programs=[
            FieldProgramSpec.model_construct(
                field_name="title",
                strategy="bogus",
                enabled=True,
            )
        ]
    )

    try:
        execute_program_spec(
            task_id="test-unsupported",
            schema_spec=schema,
            view_bundle=view_bundle,
            program_spec=program_spec,
            model_adapter=DummyAdapter(),
        )
    except ValueError as exc:
        assert "unsupported ProgramSpec strategy" in str(exc)
    else:
        raise AssertionError("unsupported strategy should raise ValueError")
