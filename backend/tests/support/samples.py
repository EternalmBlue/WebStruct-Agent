"""测试数据基元：所有测试共享的最小页面样本与 Schema 构造方式。"""

from __future__ import annotations

from app.contracts import SchemaSpec

# 含「发布日期」与「申报截止」两种日期的高校通知样本，
# 用于验证抽取过程不会把截止时间误当作发布时间。
NOTICE_HTML = """
<html>
  <head><title>关于开展2026年大学生创新训练项目申报的通知</title></head>
  <body>
    <h1>关于开展2026年大学生创新训练项目申报的通知</h1>
    <p>发布单位：教务处</p>
    <p>发布日期：2026年06月12日</p>
    <p>申报截止：2026年06月30日</p>
    <p>联系人：张老师，联系电话：010-12345678</p>
  </body>
</html>
"""

SAMPLE_HTML = NOTICE_HTML


def sample_schema(name: str = "通知样例") -> SchemaSpec:
    """Explicit test-only schema; production catalog is intentionally empty."""
    return SchemaSpec(
        name=name,
        domain="test_notice",
        description="测试用字段契约",
        fields=[
            {"name": "title", "type": "text", "required": True, "description": "通知标题"},
            {
                "name": "publish_date",
                "type": "date",
                "required": False,
                "description": "发布日期",
                "aliases": ["发布日期"],
            },
            {
                "name": "deadline",
                "type": "date",
                "required": False,
                "description": "报名截止日期",
                "aliases": ["申报截止", "报名截止"],
            },
            {
                "name": "contact",
                "type": "text",
                "required": False,
                "description": "联系人及联系方式",
                "aliases": ["联系人"],
            },
        ],
    )


def builtin_request_schema(name: str = "通知样例") -> SchemaSpec:
    """Compatibility alias for old tests; this never reads a production catalog."""
    return sample_schema(name)


__all__ = ["NOTICE_HTML", "SAMPLE_HTML", "sample_schema", "builtin_request_schema"]
