"""Opt-in local UI smoke using the project's pinned CloakBrowser, not a default browser."""
import json
import tempfile
from pathlib import Path

import cloakbrowser
import httpx
from app.platform.browser import _sdk_environment, adapter
from app.platform.configuration import settings


def main():
    api = settings.frontend_api_target
    ui = f"http://{settings.frontend_host}:{settings.frontend_port}"
    with httpx.Client(trust_env=False) as client:
        response = client.post(
            api + "/api/extract",
            json={"html": '<title>Verify you are human</title><div id="slg-box">Access Forbidden</div><script>SafeLineChallenge()</script>'},
            timeout=10,
        )
    response.raise_for_status()
    task_id = response.json()["task_id"]
    screenshots = Path(tempfile.gettempdir()) / "webstruct-rsi-smoke"
    screenshots.mkdir(exist_ok=True)
    with _sdk_environment(str(adapter.binary_path())):
        browser = cloakbrowser.launch(headless=True, browser_version=settings.browser_binary_version)
        try:
            for width, height in [(1440, 1000), (390, 844)]:
                page = browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(ui)
                page.evaluate(
                    "taskId => localStorage.setItem('webstruct.activeTaskId', taskId)",
                    task_id,
                )
                page.reload()
                page.get_by_text("证据与诊断", exact=False).wait_for(timeout=15000)
                page.get_by_text("证据与诊断", exact=False).first.click()
                page.get_by_text("监督迭代比较", exact=True).wait_for()
                assert not errors, errors
                overflow = page.evaluate(
                    "document.documentElement.scrollWidth > window.innerWidth"
                )
                assert not overflow, f"horizontal overflow at {width}"
                output = screenshots / f"diagnostics-{width}.png"
                page.screenshot(path=str(output), full_page=True)
                print(json.dumps({"width": width, "page_errors": errors,
                                  "horizontal_overflow": overflow, "screenshot": str(output)}))
                page.close()
        finally:
            browser.close()


if __name__ == "__main__":
    main()
