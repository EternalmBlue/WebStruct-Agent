
from app.contracts import (
    ExtractionRequest,
)
from app.features.extraction_center.workflow import run_extraction_workflow
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_cloakbrowser_auto_downloads_missing_pinned_binary(monkeypatch, tmp_path) -> None:
    from types import SimpleNamespace

    from app.platform.browser import CloakBrowserAdapter
    from app.platform.config import settings

    monkeypatch.setattr(settings, "browser_auto_download", True)
    monkeypatch.setattr(settings, "browser_executable_path", "")
    monkeypatch.setattr(settings, "browser_cache_path", str(tmp_path))
    expected = (
        tmp_path / f"chromium-{settings.browser_binary_version}" / "chrome.exe"
    )
    calls: list[dict[str, object]] = []

    class FakePage:
        def goto(self, _url, timeout=None):
            return SimpleNamespace(status=200)

        def content(self):
            return "<html><body><h1>downloaded</h1></body></html>"

    class FakeBrowser:
        def new_page(self):
            return FakePage()

        def close(self):
            return None

    class FakeModule:
        __version__ = settings.browser_sdk_version

        @staticmethod
        def ensure_binary(**kwargs):
            calls.append(kwargs)
            expected.parent.mkdir(parents=True, exist_ok=True)
            expected.write_bytes(b"fake-binary")
            return str(expected)

        @staticmethod
        def launch(**_kwargs):
            return FakeBrowser()

    monkeypatch.setattr(
        "app.platform.browser.importlib.import_module",
        lambda _name: FakeModule,
    )
    adapter = CloakBrowserAdapter()

    html, status = adapter.fetch("https://example.com/downloaded")

    assert status == 200
    assert "downloaded" in html
    assert expected.is_file()
    assert calls[0]["browser_version"] == settings.browser_binary_version
    assert adapter.binary_path() == expected.resolve()


def test_collector_rejects_empty_rendered_page_and_records_attempts(monkeypatch) -> None:
    def fake_rendered(_target_url: str) -> tuple[str, int]:
        return "<html><head></head><body></body></html>", 412

    def fake_http(_target_url: str) -> tuple[str, int]:
        raise ValueError("HTTP Error 412: Precondition Failed")

    monkeypatch.setattr("app.features.page_center.collector.fetch_rendered_html", fake_rendered)
    monkeypatch.setattr("app.features.page_center.collector.fetch_html", fake_http)

    state = run_extraction_workflow(
        ExtractionRequest(
            target_url="https://example.com/blocked-empty-page",
            persist_result=False,
        )
    )

    assert state["errors"]
    assert "page collection failed" in state["errors"][0]
    assert "HTTP 412" in state["errors"][0]
    assert "page_collector_node" in state["errors"][0]
