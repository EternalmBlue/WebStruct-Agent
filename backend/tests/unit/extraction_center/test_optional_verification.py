import pytest
from app.contracts import ExtractionResult, FieldExtractionResult, FieldSpec, SchemaSpec
from app.features.extraction_center.verifier import is_missing, verify_extraction


@pytest.mark.parametrize("value", [None, "", " \n", []])
def test_optional_absence_does_not_penalize_verification(value):
    schema = SchemaSpec(name="Optional", fields=[FieldSpec(name="value", required=False)])
    report = verify_extraction(
        task_id="optional",
        schema_spec=schema,
        extraction_result=ExtractionResult(
            task_id="optional", schema_name=schema.name,
            fields=[FieldExtractionResult(field_name="value", value=value)],
        ),
    )
    assert report.passed and report.score == 1 and not report.issues


@pytest.mark.parametrize("value", [0, False])
def test_falsy_scalar_is_not_absent(value):
    assert not is_missing(value)


def test_optional_execution_failure_warns_without_failing_validation():
    schema = SchemaSpec(name="Optional", fields=[FieldSpec(name="value", required=False)])
    report = verify_extraction(
        task_id="optional",
        schema_spec=schema,
        extraction_result=ExtractionResult(
            task_id="optional", schema_name=schema.name,
            fields=[FieldExtractionResult(field_name="value", error_message="ambiguous selector")],
        ),
    )
    assert report.passed
    assert [(issue.code, issue.severity) for issue in report.issues] == [
        ("program_execution_failed", "warning"),
    ]
