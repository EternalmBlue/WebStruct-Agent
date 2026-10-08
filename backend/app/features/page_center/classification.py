"""Classify collection outcomes from generic HTTP/content signals only.

Navigation waiting is the browser boundary's responsibility. This module
deliberately does not inspect challenge-provider markup, scripts, IDs or titles.
"""


def classify_page(html: str, text: str, status_code: int | None) -> tuple[str, list[str]]:
    if status_code in {401, 403, 429, 468}:
        return "access_limited", [f"http_{status_code}"]
    if status_code is not None and status_code >= 400:
        return "server_error", [f"http_{status_code}"]
    if not text.strip():
        return "empty_page", ["empty_visible_text"]
    if status_code is None:
        return "unknown", ["missing_http_response"]
    return "usable_content", []
