"""Offline browser events and clock for bounded document-navigation tests."""
from types import SimpleNamespace

CHALLENGE_HTML = (
    "<html><body><div id='slg-box'>Access Forbidden</div>"
    "<script>SafeLineChallenge()</script></body></html>"
)
CONTENT_HTML = "<html><body><main><h1>Resolved heading</h1></main></body></html>"


class BrowserPage:
    def __init__(self, monkeypatch, status=468, resolves=True, error=None):
        self.url = "https://example.test/"
        self.main_frame = object()
        self.status = status
        self.html = CHALLENGE_HTML
        self.resolves = resolves
        self.error = error
        self.clock = 0
        self.waits = []
        self.responses = []
        self.listeners = {}
        self.closed = False
        self.launch_kwargs = None
        self.navigate_count = 0
        monkeypatch.setattr("app.platform.browser.time.perf_counter", lambda: self.clock)

    def on(self, event, callback):
        self.listeners[event] = callback

    def emit(self, status, navigation=True, frame=None):
        response = SimpleNamespace(
            status=status,
            request=SimpleNamespace(is_navigation_request=lambda: navigation),
            frame=self.main_frame if frame is None else frame,
        )
        self.responses.append(status)
        self.listeners["response"](response)
        return response

    def goto(self, url, timeout=None):
        self.navigate_count += 1
        self.url = url
        return self.emit(self.status)

    def content(self):
        return self.html

    def wait_for_timeout(self, milliseconds):
        self.waits.append(milliseconds)
        self.clock += milliseconds / 1000
        if self.error is not None:
            raise self.error
        if self.resolves:
            self.html = CONTENT_HTML
            self.emit(200)
            self.emit(403, navigation=False)
            self.emit(403, frame=object())

    def new_page(self):
        return self

    def close(self):
        self.closed = True

    def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return self
