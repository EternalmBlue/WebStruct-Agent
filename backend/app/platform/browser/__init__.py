"""Pinned CloakBrowser boundary with config-controlled binary provisioning."""
from contextlib import contextmanager
import importlib
import os
from pathlib import Path
import platform
from threading import RLock

from app.platform.config import settings

_sdk_lock = RLock()


class BrowserUnavailableError(RuntimeError):
    pass


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
            "launch_verified": False,
            "reason": None,
        }
        try:
            module = importlib.import_module("cloakbrowser")
        except (ImportError, OSError):
            return {**result, "reason": "CloakBrowser SDK is not installed or cannot be loaded"}
        version = str(getattr(module, "__version__", "unknown"))
        result["version"] = version
        if version != settings.browser_sdk_version:
            return {**result, "reason": "CloakBrowser SDK version differs from browser.sdk_version"}
        if not callable(getattr(module, "launch", None)):
            return {**result, "reason": "CloakBrowser synchronous launch API is unavailable"}
        if self.last_error:
            return {**result, "reason": self.last_error}
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

    def fetch(self, target_url: str) -> tuple[str, int]:
        self.last_error = None
        readiness = self.readiness()
        if not readiness["available"]:
            if (
                settings.browser_auto_download
                and not settings.browser_executable_path
                and "binary missing" in str(readiness["reason"])
            ):
                self._download_binary()
                readiness = self.readiness()
            if not readiness["available"]:
                raise BrowserUnavailableError(str(readiness["reason"]))
        module = importlib.import_module("cloakbrowser")
        try:
            with _sdk_environment(str(self.binary_path())):
                browser = module.launch(
                    headless=True,
                    license_key=settings.browser_license_key or None,
                    browser_version=settings.browser_binary_version,
                    timeout=settings.navigation_timeout_ms,
                )
                try:
                    page = browser.new_page()
                    response = page.goto(target_url, timeout=settings.navigation_timeout_ms)
                    return page.content(), response.status if response else 200
                finally:
                    browser.close()
        except Exception as exc:
            self.last_error = f"CloakBrowser launch/navigation failed: {exc.__class__.__name__}"
            raise BrowserUnavailableError(self.last_error) from exc


adapter = CloakBrowserAdapter()


def browser_status() -> dict[str, object]:
    return adapter.readiness()
