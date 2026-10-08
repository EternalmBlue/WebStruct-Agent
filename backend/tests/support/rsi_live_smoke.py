"""Bounded, opt-in CloakBrowser collection smoke; never solves access challenges."""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httpx
from app.platform.configuration import settings

HTML = b"<html><head><title>Controlled page</title></head><body><h1>Controlled heading</h1></body></html>"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML)

    def log_message(self, *args):
        pass


def run(client, payload):
    receipt = client.post("/api/extract", json=payload)
    receipt.raise_for_status()
    task_id = receipt.json()["task_id"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        snapshot = client.get(f"/api/runs/{task_id}")
        snapshot.raise_for_status()
        if snapshot.json()["status"] in {"completed", "failed"}:
            result = client.get(f"/api/extract/{task_id}")
            result.raise_for_status()
            return result.json()
        time.sleep(settings.poll_interval_ms / 1000)
    raise TimeoutError(f"smoke task did not terminate: {task_id}")


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=settings.frontend_api_target, trust_env=False, timeout=15) as client:
            controlled = run(client, {
                "target_url": f"http://127.0.0.1:{server.server_port}/",
                "schema_spec": {"name": "Smoke", "fields": [
                    {"name": "title", "description": "Title", "type": "text", "required": True},
                ]},
                "program_spec": {"field_programs": [
                    {"field_name": "title", "strategy": "css", "selector": "h1"},
                ]},
            })
            assert controlled["status"] == "completed", controlled["errors"]
            assert controlled["extraction_result"]["fields"][0]["normalized_value"] == "Controlled heading"
            attempts = controlled["page_observation"]["metadata"]["collection_attempts"]
            assert attempts[0]["collector"] == "cloakbrowser_rendered"
            assert attempts[0]["launch_verified"] and attempts[0]["close_verified"]
            print(json.dumps({"case": "controlled", "task_id": controlled["task_id"],
                              "status": controlled["status"], "collector": attempts[0]["collector"],
                              "verification_score": controlled["verification_report"]["score"]}))
            minebbs = run(client, {"target_url": "https://www.minebbs.com/"})
            attempts = []
            cursor = 0
            while True:
                events = client.get(f'/api/runs/{minebbs["task_id"]}/events',
                                    params={"after_cursor": cursor}).json()
                attempts.extend(event for event in events["events"] if event["event_type"] == "collection_attempt")
                if events["next_cursor"] <= cursor:
                    break
                cursor = events["next_cursor"]
            print(json.dumps({"case": "minebbs", "task_id": minebbs["task_id"],
                              "status": minebbs["status"], "attempts": [
                                  {key: attempt.get(key) for key in ("classification", "http_status",
                                   "fallback_attempted", "launch_verified", "navigation_verified", "close_verified")}
                                  for attempt in attempts]}))
            if any(attempt["classification"] == "access_limited" for attempt in attempts):
                assert minebbs["status"] == "failed"
                assert len(attempts) == 1
                assert minebbs["schema_spec"] is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
