
from app.contracts import (
    ExtractionRequest,
)
from app.features.extraction_center.workflow import run_extraction_workflow
from app.main import app
from fastapi.testclient import TestClient

from tests.support.samples import builtin_request_schema

client = TestClient(app)


def test_extraction_ignores_unrelated_extra_dates() -> None:
    html = """
    <html>
      <body>
        <h1>关于组织2026年暑期社会实践的通知</h1>
        <p>资料更新日期：2026年01月01日</p>
        <p>发布单位：学生工作处</p>
        <p>发布日期：2026年06月18日</p>
        <p>报名截止：2026年07月10日</p>
        <p>联系人：李老师，联系电话：010-87654321</p>
      </body>
    </html>
    """

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/multi-date",
            html=html,
            schema_name="高校通知",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    fields = {field.field_name: field.normalized_value for field in state["extraction_result"].fields}
    assert fields["publish_date"] == "2026-06-18"
    assert fields["deadline"] == "2026-07-10"


def test_date_fields_ignore_embedded_suffix_dates() -> None:
    html = """
    <html>
      <body>
        <h1>关于开展2026年研究生奖学金评审工作的通知</h1>
        <p>系统更新日期：2026年01月01日</p>
        <p>发布日期：2026年05月22日</p>
        <p>申报截止：2026年06月20日</p>
        <p>发布单位：研究生院</p>
        <p>联系人：王老师，联系电话：010-99887766</p>
      </body>
    </html>
    """

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.edu/notice/suffix-date",
            html=html,
            schema_name="高校通知",
            schema_spec=builtin_request_schema(),
            persist_result=False,
        )
    )

    fields = {field.field_name: field.normalized_value for field in state["extraction_result"].fields}
    assert fields["publish_date"] == "2026-05-22"
