from typing import Literal

FieldType = Literal["string", "text", "number", "date", "url", "list"]
ProgramStrategy = Literal[
    "css",
    "xpath",
    "regex_on_text",
    "text_near_label",
    "llm_fallback",
]
PostprocessFunction = Literal[
    "strip",
    "normalize_whitespace",
    "normalize_date",
]
AgentStatus = Literal["success", "failed", "skipped"]
