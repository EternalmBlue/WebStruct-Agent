"""Pinned CloakBrowser boundary with config-controlled binary provisioning."""
import importlib
import os
import platform
import time
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from app.contracts.collection import CollectedHTML
from app.platform.config import settings
from app.platform.observability.telemetry import observe, timestamp

_sdk_lock = RLock()


class BrowserUnavailableError(RuntimeError):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


@contextmanager
def _sdk_environment(binary: str | None = None):
    values = {
        "CLOAKBROWSER_CACHE_DIR": settings.browser_cache_path,
        "CLOAKBROWSER_AUTO_UPDATE": "false",
        "CLOAKBROWSER_LICENSE_KEY": settings.browser_license_key,
        "CLOAKBROWSER_VERSION": settings.browser_binary_version,
        "CLOAKBROWSER_RELEASE_CHANNEL": "stable",
        "CLOAKBROWSER_DOWNLOAD_URL": "",
    }
    if binary is not None:
        values["CLOAKBROWSER_BINARY_PATH"] = binary
    with _sdk_lock:
        previous = {key: os.environ.get(key) for key in values}
        if binary is None:
            previous_binary = os.environ.pop("CLOAKBROWSER_BINARY_PATH", None)
        else:
            previous_binary = None
        os.environ.update(values)
        try:
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            if binary is None and previous_binary is not None:
                os.environ["CLOAKBROWSER_BINARY_PATH"] = previous_binary


class CloakBrowserAdapter:
    provider = "cloakbrowser"

    def __init__(self):
        self.last_error: str | None = None
        self._resolved_binary_path: Path | None = None
        self.last_probe: dict = {}

    def binary_path(self) -> Path:
        if settings.browser_executable_path:
            return Path(settings.browser_executable_path)
        if self._resolved_binary_path is not None:
            return self._resolved_binary_path
        root = Path(settings.browser_cache_path) / f"chromium-{settings.browser_binary_version}"
        if platform.system() == "Windows":
            return root / "chrome.exe"
        if platform.system() == "Darwin":
            return root / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
        return root / "chrome"

    def _download_binary(self) -> Path:
        module = importlib.import_module("cloakbrowser")
        ensure_binary = getattr(module, "ensure_binary", None)
        if not callable(ensure_binary):
            raise BrowserUnavailableError(
                "CloakBrowser SDK does not expose ensure_binary for automatic provisioning"
            )
        try:
            with _sdk_environment():
                downloaded = ensure_binary(
                    license_key=settings.browser_license_key or None,
                    browser_version=settings.browser_binary_version,
                    release_channel="stable",
                )
        except Exception as exc:
            self.last_error = (
                f"CloakBrowser binary download failed: {exc.__class__.__name__}"
            )
            raise BrowserUnavailableError(self.last_error) from exc
        path = Path(str(downloaded)).resolve()
        if not path.is_file():
            self.last_error = "CloakBrowser download completed without an executable binary"
            raise BrowserUnavailableError(self.last_error)
        self._resolved_binary_path = path
        return path

    def readiness(self) -> dict[str, object]:
        result = {
            "available": False,
            "provider": self.provider,
            "version": settings.browser_sdk_version,
            "binary_version": settings.browser_binary_version,
            "sdk_installed": False,
            "binary_ready": self.binary_path().is_file(),
            "launch_verified": self.last_probe.get("launch_verified", False),
            "navigation_verified": self.last_probe.get("navigation_verified", False),
            "last_probe_at": self.last_probe.get("end_time"),
            "last_error": self.last_error,
            "reason": None,
        }
        try:
            module = importlib.import_module("cloakbrowser")
        except (ImportError, OSError):
            return {**result, "reason": "CloakBrowser SDK is not installed or cannot be loaded"}
        version = str(getattr(module, "__version__", "unknown"))
        result["sdk_installed"] = True
        result["version"] = version
        if version != settings.browser_sdk_version:
            return {**result, "reason": "CloakBrowser SDK version differs from browser.sdk_version"}
        if not callable(getattr(module, "launch", None)):
            return {**result, "reason": "CloakBrowser synchronous launch API is unavailable"}
        if not self.binary_path().is_file():
            if settings.browser_executable_path:
                reason = "configured browser.executable_path does not exist"
            elif settings.browser_auto_download:
                reason = (
                    "CloakBrowser binary missing; automatic download will run "
                    "on first URL collection"
                )
            else:
                reason = (
                    "CloakBrowser binary missing; configure browser.executable_path "
                    "or provision browser.cache_path"
                )
            return {
                **result,
                "reason": reason,
            }
        return {**result, "available": True}

    def fetch(self, target_url: str) -> CollectedHTML:
        return self._fetch(target_url)

    @staticmethod
    def _wait_after_navigation(page, probe: dict) -> str:
        started = time.perf_counter()
        duration = settings.browser_post_navigation_wait_ms
        probe["post_navigation_wait_configured_ms"] = duration
        probe["post_navigation_wait_outcome"] = "disabled"
        try:
            if duration:
                wait_for_timeout = getattr(page, "wait_for_timeout", None)
                if not callable(wait_for_timeout):
                    probe["post_navigation_wait_outcome"] = "unsupported_page_api"
                    raise RuntimeError("browser page does not support navigation waiting")
                probe["post_navigation_wait_outcome"] = "waiting"
                wait_for_timeout(duration)
                probe["post_navigation_wait_outcome"] = "completed"
            return page.content()
        except Exception:
            if probe["post_navigation_wait_outcome"] != "unsupported_page_api":
                probe["post_navigation_wait_outcome"] = "failed"
            raise
        finally:
            probe["post_navigation_wait_ms"] = round((time.perf_counter() - started) * 1000, 3)

    def _fetch(self, target_url: str) -> CollectedHTML:
        self.last_error = None
        probe = {
            "provider": self.provider,
            "sdk_version": settings.browser_sdk_version,
            "binary_version": settings.browser_binary_version,
            "start_time": timestamp(), "end_time": None,
            "launch_verified": False, "navigation_verified": False,
            "launch_latency_ms": None, "navigation_latency_ms": None,
            "download_latency_ms": None, "close_verified": None,
            "redirect_count": None, "result": "failed",
            "initial_http_status": None, "final_http_status": None,
            "post_navigation_wait_ms": 0,
            "post_navigation_wait_outcome": "not_started",
        }
        started = time.perf_counter()
        stage = "readiness"
        try:
            readiness = self.readiness()
            if not readiness["available"]:
                if (
                    settings.browser_auto_download
                    and not settings.browser_executable_path
                    and "binary missing" in str(readiness["reason"])
                ):
                    stage = "download"
                    provision_started = time.perf_counter()
                    self._download_binary()
                    probe["download_latency_ms"] = round((time.perf_counter() - provision_started) * 1000, 3)
                    readiness = self.readiness()
                if not readiness["available"]:
                    raise BrowserUnavailableError(str(readiness["reason"]))
            module = importlib.import_module("cloakbrowser")
            with _sdk_environment(str(self.binary_path())):
                stage = "launch"
                launch_started = time.perf_counter()
                browser = module.launch(
                    headless=True,
                    license_key=settings.browser_license_key or None,
                    browser_version=settings.browser_binary_version,
                    timeout=settings.navigation_timeout_ms,
                )
                probe["launch_latency_ms"] = round((time.perf_counter() - launch_started) * 1000, 3)
                probe["launch_verified"] = True
                try:
                    stage = "navigation"
                    navigation_started = time.perf_counter()
                    page = browser.new_page()
                    document = {"status": None, "count": 0}

                    def record_document(response):
                        if (
                            response.request.is_navigation_request()
                            and response.frame == page.main_frame
                        ):
                            document["status"] = response.status
                            document["count"] += 1

                    page.on("response", record_document)
                    response = page.goto(target_url, timeout=settings.navigation_timeout_ms)
                    probe["navigation_latency_ms"] = round((time.perf_counter() - navigation_started) * 1000, 3)
                    probe["navigation_verified"] = response is not None
                    initial_status = response.status if response else None
                    if document["count"] == 0:
                        document.update(status=initial_status, count=int(response is not None))
                    probe["initial_http_status"] = initial_status
                    stage = "post_navigation_wait"
                    content = self._wait_after_navigation(page, probe)
                    status = document["status"]
                    probe["final_http_status"] = status
                    probe["main_document_response_count"] = document["count"]
                    final_url = getattr(page, "url", target_url)
                    probe["result"] = "success"
                finally:
                    try:
                        browser.close()
                        probe["close_verified"] = True
                    except Exception as close_exc:
                        probe["close_verified"] = False
                        probe["close_error"] = close_exc.__class__.__name__
        except Exception as exc:
            if stage == "launch" and probe["launch_latency_ms"] is None:
                probe["launch_latency_ms"] = round((time.perf_counter() - launch_started) * 1000, 3)
            elif stage == "navigation" and probe["navigation_latency_ms"] is None:
                probe["navigation_latency_ms"] = round((time.perf_counter() - navigation_started) * 1000, 3)
            self.last_error = settings.redact(f"CloakBrowser {stage} failed: {exc.__class__.__name__}: {exc}")
            probe["error_stage"] = stage
            probe["error_code"] = exc.__class__.__name__
            probe["error_message"] = self.last_error
            raise BrowserUnavailableError(self.last_error, probe) from exc
        finally:
            probe["end_time"] = timestamp()
            probe["runtime_ms"] = round((time.perf_counter() - started) * 1000, 3)
            self.last_probe = probe.copy()
            observe("browser_probe", **probe)
        return CollectedHTML(content, status, final_url, probe)


adapter = CloakBrowserAdapter()


def browser_status() -> dict[str, object]:
    return adapter.readiness()
