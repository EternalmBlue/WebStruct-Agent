"""多视图归一化：把 PageObservation 变成 ViewBundle（文本、行、标题、文本块）。

行为契约：specs/features/page-center.feature
"""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from typing import Any

from app.contracts import PageObservation, ViewBundle
from app.platform.text_processing import html_to_text, normalize_whitespace


class _BlockExtractor(HTMLParser):
    block_tags = {"h1", "h2", "h3", "p", "li", "td", "th"}

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[dict[str, Any]] = []
        self._stack: list[tuple[str, int]] = []
        self._tag_counts: dict[str, int] = {}
        self._active: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        index = self._tag_counts.get(tag, 0) + 1
        self._tag_counts[tag] = index
        self._stack.append((tag, index))
        if tag in self.block_tags and self._active is None:
            attrs_dict = {key: value for key, value in attrs if value}
            self._active = {
                "tag": tag,
                "selector": _selector_for(tag, attrs_dict, index),
                "xpath": _xpath_for(self._stack),
                "parts": [],
            }

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._active and self._active["tag"] == tag:
            text = normalize_whitespace(unescape(" ".join(self._active["parts"])))
            if text:
                self.blocks.append(
                    {
                        "tag": self._active["tag"],
                        "selector": self._active["selector"],
                        "xpath": self._active["xpath"],
                        "text": text,
                    }
                )
            self._active = None
        while self._stack:
            current_tag, _ = self._stack.pop()
            if current_tag == tag:
                break

    def handle_data(self, data: str) -> None:
        if self._active:
            self._active["parts"].append(data)


def normalize_page_view(observation: PageObservation) -> ViewBundle:
    text, title, headings = html_to_text(observation.html)
    lines = [line for line in text.splitlines() if line.strip()]
    text_blocks = observation.metadata.get("text_blocks") or extract_text_blocks(observation.html)
    return ViewBundle(
        url=observation.url,
        raw_html=observation.html,
        text=text,
        lines=lines,
        title=title or observation.title,
        headings=headings,
        metadata={
            "line_count": len(lines),
            "heading_count": len(headings),
            "text_blocks": text_blocks,
            "text_block_count": len(text_blocks),
            "collector": observation.metadata.get("collector", ""),
        },
    )


def extract_text_blocks(html: str, *, limit: int = 200) -> list[dict[str, Any]]:
    parser = _BlockExtractor()
    parser.feed(html or "")
    return parser.blocks[:limit]


def _selector_for(tag: str, attrs: dict[str, str], index: int) -> str:
    element_id = attrs.get("id")
    if element_id:
        return f"#{element_id}"
    class_names = [item for item in attrs.get("class", "").split() if item]
    if class_names:
        return f"{tag}.{class_names[0]}"
    return f"{tag}:nth-of-type({index})"


def _xpath_for(stack: list[tuple[str, int]]) -> str:
    return "/" + "/".join(f"{tag}[{index}]" for tag, index in stack)
