from typing import Any

from pydantic import BaseModel, Field


class PageObservation(BaseModel):
    url: str
    html: str = ""
    text: str = ""
    title: str = ""
    status_code: int = 200
    metadata: dict[str, Any] = Field(default_factory=dict)


class ViewBundle(BaseModel):
    url: str
    raw_html: str = ""
    text: str = ""
    lines: list[str] = Field(default_factory=list)
    title: str = ""
    headings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
