from __future__ import annotations

import asyncio
import urllib.request
from html import unescape
from html.parser import HTMLParser
from typing import Any

from playwright.async_api import async_playwright

from app.domain import PageObservation, ViewBundle
from app.extraction.text_processing import html_to_text, normalize_whitespace

HTTP_FETCH_TIMEOUT_SECONDS = 8
PLAYWRIGHT_NAVIGATION_TIMEOUT_MS = 15000
MIN_VISIBLE_TEXT_CHARS = 1


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


def collect_page(
    *,
    target_url: str,
    schema_name: str = "",
    input_html: str = "",
) -> PageObservation:
    html = input_html.strip()
    status_code = 200
    collector = "supplied_html"
    collection_attempts: list[str] = []

    if not html and target_url.startswith(("http://", "https://")):
        html, status_code, collector, collection_attempts = _collect_remote_html(target_url)

    if not html:
        raise ValueError("page collection requires supplied html or an http(s) target_url")

    text, title, _ = html_to_text(html)
    if not _has_visible_text(text):
        raise ValueError(
            "page collection returned empty visible text"
            + _format_attempts(collection_attempts)
        )
    blocks = extract_text_blocks(html)
    return PageObservation(
        url=target_url,
        html=html,
        text=text,
        title=title,
        status_code=status_code,
        metadata={
            "collector": collector,
            "collection_attempts": collection_attempts,
            "schema_name": schema_name,
            "text_blocks": blocks,
            "text_block_count": len(blocks),
        },
    )


def _collect_remote_html(target_url: str) -> tuple[str, int, str, list[str]]:
    attempts: list[str] = []
    for collector_name, fetcher in (
        ("playwright_rendered", fetch_rendered_html),
        ("http", fetch_html),
    ):
        try:
            html, status_code = fetcher(target_url)
        except Exception as exc:
            attempts.append(f"{collector_name}: {exc.__class__.__name__}: {exc}")
            continue

        text, _, _ = html_to_text(html)
        if status_code >= 400:
            attempts.append(f"{collector_name}: HTTP {status_code}")
            continue
        if not _has_visible_text(text):
            attempts.append(f"{collector_name}: empty visible text")
            continue
        attempts.append(f"{collector_name}: HTTP {status_code}, text {len(text)} chars")
        return html, status_code, collector_name, attempts

    raise ValueError("page collection failed" + _format_attempts(attempts))


def _has_visible_text(text: str) -> bool:
    return len(normalize_whitespace(text)) >= MIN_VISIBLE_TEXT_CHARS


def _format_attempts(attempts: list[str]) -> str:
    if not attempts:
        return ""
    return "; attempts: " + " | ".join(attempts)


def fetch_rendered_html(target_url: str) -> tuple[str, int]:
    return asyncio.run(_fetch_rendered_html_async(target_url))


async def _fetch_rendered_html_async(target_url: str) -> tuple[str, int]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="WebStruct-Agent/0.1 thesis prototype",
            viewport={"width": 1366, "height": 900},
        )
        response = await page.goto(
            target_url,
            wait_until="networkidle",
            timeout=PLAYWRIGHT_NAVIGATION_TIMEOUT_MS,
        )
        html = await page.content()
        status_code = response.status if response else 200
        await browser.close()
        return html, status_code


def fetch_html(target_url: str) -> tuple[str, int]:
    request = urllib.request.Request(
        target_url,
        headers={"User-Agent": "WebStruct-Agent/0.1 thesis prototype"},
    )
    with urllib.request.urlopen(request, timeout=HTTP_FETCH_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace"), response.status


def normalize_page_view(observation: PageObservation) -> ViewBundle:
    text, title, headings = html_to_text(observation.html)
    lines = [line for line in text.splitlines() if line.strip()]
    text_blocks = observation.metadata.get("text_blocks") or extract_text_blocks(
        observation.html
    )
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
