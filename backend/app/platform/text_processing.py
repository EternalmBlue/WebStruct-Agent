from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []
        self._current_tag: str | None = None
        self._ignored: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "template"}:
            self._ignored.append(tag.lower())
        self._current_tag = tag.lower()

    def handle_endtag(self, tag: str) -> None:
        if self._ignored:
            if tag.lower() == self._ignored[-1]:
                self._ignored.pop()
            return
        if tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3", "br"}:
            self.parts.append("\n")
        self._current_tag = None

    def handle_data(self, data: str) -> None:
        if self._ignored:
            return
        text = normalize_whitespace(unescape(data))
        if not text:
            return
        self.parts.append(text)
        if self._current_tag == "title":
            self.title_parts.append(text)
        if self._current_tag in {"h1", "h2", "h3"}:
            self.heading_parts.append(text)


def html_to_text(html: str) -> tuple[str, str, list[str]]:
    parser = _TextExtractor()
    parser.feed(html or "")
    text = "\n".join(
        line
        for line in (normalize_whitespace(part) for part in "".join(parser.parts).splitlines())
        if line
    )
    title = normalize_whitespace(" ".join(parser.title_parts))
    headings = [normalize_whitespace(heading) for heading in parser.heading_parts if heading]
    return text, title, headings


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_date(value: str) -> str:
    text = normalize_whitespace(value)
    match = re.search(
        r"(?P<year>\d{4})\s*[年\-/\.]\s*(?P<month>\d{1,2})\s*[月\-/\.]\s*(?P<day>\d{1,2})\s*日?",
        text,
    )
    if not match:
        match = re.search(
            r"(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})",
            text,
        )
    if not match:
        return text
    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))
    if month < 1 or month > 12 or day < 1 or day > 31:
        return text
    return f"{year:04d}-{month:02d}-{day:02d}"


def strip_tags(html: str) -> str:
    text, _, _ = html_to_text(html)
    return text


def bounded_snippet(text: str, start: int, end: int, radius: int = 60) -> str:
    safe_start = max(0, start - radius)
    safe_end = min(len(text), end + radius)
    return normalize_whitespace(text[safe_start:safe_end])
