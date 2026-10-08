from types import SimpleNamespace

import pytest
from app.features.page_center.collector import PageCollectionError, collect_page
from app.platform.browser import BrowserUnavailableError, CloakBrowserAdapter
from app.platform.config import settings
from app.platform.observability.telemetry import capture_observations
from playwright.sync_api import Error as BrowserError

from tests.support.browser_pages import CHALLENGE_HTML, CONTENT_HTML, BrowserPage


@pytest.mark.parametrize("stage", ["launch", "navigation"])
def test_failure_probe_keeps_duration_and_navigation_cleanup(stage, monkeypatch):
    browser = SimpleNamespace(
        new_page=lambda: SimpleNamespace(
            on=lambda *_args: None, goto=lambda *args, **kwargs: fail(),
        ),
        close=lambda: closed.append(True),
    )
    closed = []

    def fail():
        raise TimeoutError("bounded timeout")

    adapter = CloakBrowserAdapter()
    monkeypatch.setattr(adapter, "readiness", lambda: {"available": True})
    monkeypatch.setattr("app.platform.browser.importlib.import_module", lambda *args:
                        SimpleNamespace(launch=lambda **kwargs: fail() if stage == "launch" else browser))
    with capture_observations() as events:
        with pytest.raises(BrowserUnavailableError):
            adapter.fetch("https://example.test/")
    probe = events[-1]
    assert probe["event_type"] == "browser_probe"
    assert probe["error_stage"] == stage
    assert probe[f"{stage}_latency_ms"] is not None
    assert "bounded timeout" in probe["error_message"]
    assert probe["launch_verified"] is (stage == "navigation")
    assert bool(closed) is (stage == "navigation")
    if stage == "navigation":
        assert probe["close_verified"] is True


def install_page(monkeypatch, page):
    adapter = CloakBrowserAdapter()
    monkeypatch.setattr(settings, "browser_post_navigation_wait_ms", 500)
    monkeypatch.setattr(adapter, "readiness", lambda: {"available": True})
    monkeypatch.setattr(
        "app.platform.browser.importlib.import_module",
        lambda *_args: SimpleNamespace(launch=page.launch),
    )
    monkeypatch.setattr("app.features.page_center.collector.adapter", adapter)
    return adapter


@pytest.mark.parametrize("initial_status", [468, 200])
def test_challenge_uses_final_main_document_response(initial_status, monkeypatch):
    page = BrowserPage(monkeypatch, status=initial_status)
    adapter = install_page(monkeypatch, page)
    result = adapter.fetch(page.url)
    assert result.status_code == 200
    assert result.html == CONTENT_HTML
    assert result.metadata["initial_http_status"] == initial_status
    assert result.metadata["final_http_status"] == 200
    assert result.metadata["post_navigation_wait_outcome"] == "completed"
    assert result.metadata["post_navigation_wait_ms"] == 500
    assert result.metadata["main_document_response_count"] == 2
    assert page.closed
    assert page.navigate_count == 1
    assert page.launch_kwargs == {
        "headless": True, "license_key": settings.browser_license_key or None,
        "browser_version": settings.browser_binary_version,
        "timeout": settings.navigation_timeout_ms,
    }


def test_persistent_challenge_stops_at_deadline_without_http_fallback(monkeypatch):
    page = BrowserPage(monkeypatch, resolves=False)
    adapter = install_page(monkeypatch, page)
    calls = []
    monkeypatch.setattr("app.features.page_center.collector.fetch_html", calls.append)
    with pytest.raises(PageCollectionError) as error:
        collect_page(target_url=page.url)
    assert not calls
    assert len(error.value.attempts) == 1
    assert error.value.attempts[0]["classification"] == "access_limited"
    assert adapter.last_probe["post_navigation_wait_ms"] == 500
    assert adapter.last_probe["post_navigation_wait_outcome"] == "completed"
    assert page.waits == [500]
    assert page.closed


@pytest.mark.parametrize("status", [200, 401, 403, 429])
def test_all_documents_wait_without_content_recognition(status, monkeypatch):
    page = BrowserPage(monkeypatch, status=status, resolves=False)
    page.html = CONTENT_HTML
    adapter = install_page(monkeypatch, page)
    result = adapter.fetch(page.url)
    assert result.status_code == status
    assert page.waits == [500]
    assert result.metadata["post_navigation_wait_outcome"] == "completed"


def test_marker_disappearance_does_not_override_468_status(monkeypatch):
    page = BrowserPage(monkeypatch, resolves=False)

    def remove_markers(milliseconds):
        page.clock += milliseconds / 1000
        page.html = CONTENT_HTML
    page.wait_for_timeout = remove_markers
    install_page(monkeypatch, page)
    with pytest.raises(PageCollectionError) as error:
        collect_page(target_url=page.url)
    assert error.value.attempts[0]["http_status"] == 468
    assert error.value.attempts[0]["classification"] == "access_limited"
    assert error.value.attempts[0]["post_navigation_wait_outcome"] == "completed"


def test_post_navigation_wait_can_be_disabled(monkeypatch):
    page = BrowserPage(monkeypatch)
    adapter = install_page(monkeypatch, page)
    monkeypatch.setattr(settings, "browser_post_navigation_wait_ms", 0)
    result = adapter.fetch(page.url)
    assert not page.waits
    assert result.html == CHALLENGE_HTML
    assert result.metadata["post_navigation_wait_outcome"] == "disabled"

    page.resolves = False
    monkeypatch.setattr(settings, "browser_post_navigation_wait_ms", 100)
    result = adapter.fetch(page.url)
    assert page.waits == [100]
    assert result.metadata["post_navigation_wait_ms"] == 100


def test_wait_failure_retains_duration_and_closes_browser(monkeypatch):
    page = BrowserPage(monkeypatch, error=RuntimeError("wait failure"))
    adapter = install_page(monkeypatch, page)
    with pytest.raises(BrowserUnavailableError) as error:
        adapter.fetch(page.url)
    assert error.value.details["error_stage"] == "post_navigation_wait"
    assert error.value.details["post_navigation_wait_ms"] == 500
    assert error.value.details["post_navigation_wait_outcome"] == "failed"
    assert page.closed


def test_dom_snapshot_failure_is_explicit_and_browser_is_closed(monkeypatch):
    page = BrowserPage(monkeypatch)
    adapter = install_page(monkeypatch, page)
    def content():
        raise BrowserError("Unable to retrieve content because the page is navigating.")
    page.content = content
    with pytest.raises(BrowserUnavailableError):
        adapter.fetch(page.url)
    assert page.waits == [500]
    assert page.closed
