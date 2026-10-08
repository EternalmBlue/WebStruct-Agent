"""Context-local observation capture shared by workflows, benchmarks and diagnostics."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from app.platform.configuration import settings

_captures: ContextVar[tuple[list, ...]] = ContextVar("observation_captures", default=())
model_context: ContextVar[dict] = ContextVar("model_context", default={})


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def safe_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        if parts.port:
            host += f":{parts.port}"
        return settings.redact(urlunsplit((parts.scheme, host, parts.path, "", "")))
    except ValueError:
        return "[invalid-url]"


def redact_tree(value):
    if isinstance(value, dict):
        return {key: redact_tree(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_tree(item) for item in value]
    if isinstance(value, str):
        return settings.redact(value)
    return value


@contextmanager
def capture_observations():
    events: list[dict] = []
    token = _captures.set((*_captures.get(), events))
    try:
        yield events
    finally:
        _captures.reset(token)


@contextmanager
def model_operation(purpose: str, field: str | None = None):
    token = model_context.set({"purpose": purpose, "field": field})
    try:
        yield
    finally:
        model_context.reset(token)


def observe(event_type: str, **details):
    event = redact_tree({"event_type": event_type, **details})
    for capture in _captures.get():
        capture.append(event)
    # Import lazily to avoid cycles in platform composition.
    from app.platform.observability import runtime
    runtime.decision(event_type, **{k: v for k, v in event.items() if k != "event_type"})
