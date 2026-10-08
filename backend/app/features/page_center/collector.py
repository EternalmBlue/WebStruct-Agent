"""页面采集：把 URL 或输入 HTML 变成 PageObservation。

行为契约：specs/features/page-center.feature（文本块/多视图能力见 views.py）
"""

from __future__ import annotations

import urllib.request

from app.contracts import PageObservation
from app.features.page_center.views import extract_text_blocks
from app.platform.browser import adapter
from app.platform.config import settings
from app.platform.text_processing import html_to_text, normalize_whitespace

HTTP_FETCH_TIMEOUT_SECONDS = settings.http_timeout_seconds
MIN_VISIBLE_TEXT_CHARS = 1


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
            "page collection returned empty visible text" + _format_attempts(collection_attempts)
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
    attempts_order = [("cloakbrowser_rendered", fetch_rendered_html)]
    if settings.allow_http_fallback:
        attempts_order.append(("http_fallback", fetch_html))
    for collector_name, fetcher in attempts_order:
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
    return adapter.fetch(target_url)


def fetch_html(target_url: str) -> tuple[str, int]:
    request = urllib.request.Request(
        target_url,
        headers={"User-Agent": "WebStruct-Agent/0.1 thesis prototype"},
    )
    with urllib.request.urlopen(request, timeout=HTTP_FETCH_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace"), response.status
