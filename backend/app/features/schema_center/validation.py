"""Schema 校验规则：把「契约是否成立」判断从 HTTP 层剥离，便于复用与单测。

行为契约：specs/features/schema-center.feature
"""

from app.contracts import SchemaSpec

DATE_SEMANTIC_KEYWORDS = ("日期", "时间", "date")


def validate_schema_spec(schema_spec: SchemaSpec) -> list[str]:
    """返回 SchemaSpec 的全部校验错误；空列表表示校验通过。

    规则三条：
    1. 至少要有一个字段，字段名不能为空；
    2. 必填字段必须带描述（否则 LLM / 程序两端都无从下手）；
    3. date 字段必须能从描述或别名中读出日期语义，避免抽取到错误的日期。
    """
    errors: list[str] = []
    if not schema_spec.fields:
        errors.append("schema must contain at least one field")

    for field in schema_spec.fields:
        if not field.name.strip():
            errors.append("field name must not be empty")
        if field.required and not field.description.strip():
            errors.append(f"required field '{field.name}' should include a description")
        semantics = field.description + " ".join(field.aliases)
        if field.type == "date" and not any(
            keyword in semantics for keyword in DATE_SEMANTIC_KEYWORDS
        ):
            errors.append(f"date field '{field.name}' should include date/time semantics")
    return errors


__all__ = ["DATE_SEMANTIC_KEYWORDS", "validate_schema_spec"]
