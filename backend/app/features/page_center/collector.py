"""页面采集：把 URL 或输入 HTML 变成 PageObservation。

行为契约：specs/features/page-center.feature（文本块/多视图能力见 views.py）
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from hashlib import sha256

from app.contracts import PageObservation
from app.contracts.collection import CollectedHTML
from app.features.page_center.classification import classify_page
from app.features.page_center.single_page import assess_page_intent, select_body_content
from app.features.page_center.views import extract_text_blocks
from app.platform.browser import adapter
from app.platform.config import settings
from app.platform.observability.telemetry import observe, safe_url, timestamp
from app.platform.text_processing import html_to_text


class PageCollectionError(ValueError):
    def __init__(self, attempts):
        self.attempts = attempts
        reason = " | ".join(
            f"{a['collector']}: HTTP {a['http_status']}, {a['classification']}"
            f": {a.get('error_message') or ('empty visible text' if a['classification'] == 'empty_page' else '')}"
            for a in attempts
        )
        super().__init__("page collection failed; attempts: " + reason)


def collect_page(
    *,
    target_url: str,
    schema_name: str = "",
    input_html: str = "",
    requested_intent: str | None = None,
) -> PageObservation:
    if input_html.strip():
        fetchers = [("supplied_html", lambda _: CollectedHTML(input_html.strip(), 200, target_url))]
    elif target_url.startswith(("http://", "https://")):
        fetchers = [("cloakbrowser_rendered", fetch_rendered_html)]
        if settings.allow_http_fallback:
            fetchers.append(("http_fallback", fetch_html))
    else:
        raise ValueError("page collection requires supplied html or an http(s) target_url")
    attempts = []
    for collector, fetcher in fetchers:
        started = time.perf_counter()
        attempt = {"collector": collector, "start_time": timestamp(),
                   "http_status": None, "final_url": safe_url(target_url),
                   "classification": "network_error", "classification_signals": [],
                   "fallback_attempted": collector == "http_fallback", "result": "failed"}
        try:
            fetched = fetcher(target_url)
            if not isinstance(fetched, CollectedHTML):
                html, status = fetched
                fetched = CollectedHTML(html, status, target_url)
            text, title, _ = html_to_text(fetched.html)
            classification, signals = classify_page(fetched.html, text, fetched.status_code)
            intent_assessment = assess_page_intent(
                fetched.html,
                requested_intent=None if requested_intent == "auto" else requested_intent,
            )
            body_selection = select_body_content(fetched.html)
            attempt.update(fetched.metadata)
            attempt.update(http_status=fetched.status_code, final_url=safe_url(fetched.final_url),
                           classification=classification, classification_signals=signals,
                           title=settings.redact(title), html_chars=len(fetched.html),
                          visible_text_chars=len(text),
                           page_intent=intent_assessment.intent,
                           page_intent_confidence=intent_assessment.confidence,
                           page_intent_gate_passed=intent_assessment.gate_passed,
                           result="success" if classification == "usable_content" else "failed")
        except Exception as exc:
            attempt.update(getattr(exc, "details", {}))
            attempt.update(error_code=exc.__class__.__name__, error_message=settings.redact(str(exc)))
        attempt.update(end_time=timestamp(), runtime_ms=round((time.perf_counter() - started) * 1000, 3))
        attempts.append(attempt)
        observe("collection_attempt", **attempt)
        if attempt["result"] == "success":
            blocks = extract_text_blocks(fetched.html)
            observe("collection_result", collector=collector, result="success",
                    fallback=collector == "http_fallback", runtime_ms=attempt["runtime_ms"],
                    classification=attempt["classification"])
            return PageObservation(
                url=fetched.final_url, html=fetched.html, text=text, title=title,
                status_code=fetched.status_code,
                metadata={"collector": collector, "collection_attempts": attempts,
                          "page_classification": attempt["classification"],
                          "page_intent": intent_assessment.model_dump(mode="json"),
                          "body_selection": body_selection.model_dump(mode="json"),
                          "page_hash": sha256(fetched.html.encode()).hexdigest(),
                          "schema_name": schema_name, "text_blocks": blocks,
                          "text_block_count": len(blocks)},
            )
        if attempt["classification"] == "access_limited":
            observe("collection_fallback", result="skipped", reason="access_control_boundary",
                    collector=collector)
            break
    observe("collection_result", result="failed", collector=attempts[-1]["collector"],
            classification=attempts[-1]["classification"], fallback=False)
    raise PageCollectionError(attempts)


def fetch_rendered_html(target_url: str):
    return adapter.fetch(target_url)


def fetch_html(target_url: str) -> CollectedHTML:
    request = urllib.request.Request(
        target_url,
        headers={"User-Agent": "WebStruct-Agent/0.1 thesis prototype"},
    )
    try:
        response = urllib.request.urlopen(request, timeout=settings.http_timeout_seconds)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return CollectedHTML(response.read().decode("utf-8", errors="replace"),
                             response.code, response.geturl())
