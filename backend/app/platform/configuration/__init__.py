"""Single TOML configuration boundary. No environment or dotenv overrides."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re
import tomllib

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.engine import make_url


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_name: str = "WebStruct-Agent"
    environment: str = "local"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    llm_api_key: str | None = Field(default=None, repr=False)
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = Field(default=30, gt=0)
    database_url: str = Field(default="sqlite:///backend/webstruct_agent.db", repr=False)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    browser_provider: str = "cloakbrowser"
    browser_sdk_version: str = "0.5.12"
    browser_binary_version: str = "147.0.7727.31"
    browser_executable_path: str = ""
    browser_cache_path: str = ".browser-cache"
    browser_license_key: str = Field(default="", repr=False)
    browser_auto_download: bool = True
    allow_http_fallback: bool = True
    navigation_timeout_ms: int = Field(default=15000, gt=0)
    http_timeout_seconds: float = Field(default=8, gt=0)
    poll_interval_ms: int = Field(default=1000, ge=100)
    health_interval_ms: int = Field(default=5000, ge=100)
    max_workers: int = Field(default=2, ge=1, le=32)
    event_page_size: int = Field(default=200, ge=1, le=1000)
    retain_business_payload: bool = True
    confidence_threshold: float = Field(default=.8, ge=0, le=1)
    estimated_chars_per_token: float = Field(default=4, gt=0)
    frontend_host: str = "127.0.0.1"
    frontend_port: int = Field(default=5173, ge=1, le=65535)
    frontend_api_target: str = "http://127.0.0.1:8000"
    config_path: str = ""
    config_version: str = ""

    @property
    def model_mode(self):
        return "deepseek" if "deepseek" in self.llm_base_url else "openai-compatible"

    @property
    def llm_configured(self):
        return bool(self.llm_api_key and self.llm_api_key.strip())

    @property
    def database_driver(self):
        return make_url(self.database_url).drivername

    def public_config(self):
        return {
            "app_name": self.app_name, "environment": self.environment,
            "config_source": "config.toml", "config_loaded": True,
            "config_version": self.config_version,
            "poll_interval_ms": self.poll_interval_ms,
            "health_interval_ms": self.health_interval_ms,
            "browser_provider": self.browser_provider,
            "browser_auto_download": self.browser_auto_download,
            "llm_configured": self.llm_configured, "llm_model": self.llm_model,
        }

    def redact(self, value: str):
        secrets = [self.llm_api_key, self.browser_license_key]
        try:
            secrets.append(make_url(self.database_url).password)
        except Exception:
            pass
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[redacted]")
        value = re.sub(r"(https?://)[^/\s@]+@", r"\1[redacted]@", value)
        return value[:1000]


SECTIONS = {
    "app": {"name": "app_name", "environment": "environment", "host": "host",
            "port": "port", "cors_origins": "cors_origins"},
    "database": {"url": "database_url"},
    "model": {"api_key": "llm_api_key", "base_url": "llm_base_url", "name": "llm_model",
              "timeout_seconds": "llm_timeout_seconds"},
    "browser": {"provider": "browser_provider", "sdk_version": "browser_sdk_version",
                "binary_version": "browser_binary_version", "executable_path": "browser_executable_path",
                "cache_path": "browser_cache_path", "license_key": "browser_license_key",
                "auto_download": "browser_auto_download",
                "allow_http_fallback": "allow_http_fallback",
                "navigation_timeout_ms": "navigation_timeout_ms", "http_timeout_seconds": "http_timeout_seconds"},
    "monitoring": {k: k for k in ("poll_interval_ms", "health_interval_ms", "max_workers",
                                  "event_page_size", "retain_business_payload")},
    "benchmark": {k: k for k in ("confidence_threshold", "estimated_chars_per_token")},
    "frontend": {"host": "frontend_host", "port": "frontend_port", "api_target": "frontend_api_target"},
}


def load_settings(path: Path | str) -> Settings:
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("config.toml is missing")
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("config.toml: invalid TOML or unreadable file") from None
    values = {}
    for section, entries in document.items():
        if section not in SECTIONS or not isinstance(entries, dict):
            raise ValueError(f"config.toml: unknown section {section}")
        for key, value in entries.items():
            if key not in SECTIONS[section]:
                raise ValueError(f"config.toml: unknown item {section}.{key}")
            values[SECTIONS[section][key]] = value
    try:
        loaded = Settings(**values, config_path=str(path))
    except ValidationError as exc:
        reverse = {v: f"{s}.{k}" for s, items in SECTIONS.items() for k, v in items.items()}
        reasons = [f"{reverse.get(str(e['loc'][0]), str(e['loc'][0]))}: {e['type']}"
                   for e in exc.errors(include_input=False)]
        raise ValueError("config.toml: " + "; ".join(reasons)) from None
    if loaded.browser_provider != "cloakbrowser":
        raise ValueError("config.toml: browser.provider must be cloakbrowser")
    for key in ("llm_base_url", "frontend_api_target"):
        if not getattr(loaded, key).startswith(("http://", "https://")):
            raise ValueError(f"config.toml: {key} requires http(s)")
    try:
        url = make_url(loaded.database_url)
        if url.drivername not in {"sqlite", "postgresql+psycopg"}:
            raise ValueError()
        if url.drivername == "sqlite" and url.database != ":memory:":
            db_path = Path(url.database or "")
            if not db_path.is_absolute():
                db_path = path.parent / db_path
            loaded.database_url = url.set(database=db_path.resolve().as_posix()).render_as_string(
                hide_password=False)
    except Exception:
        raise ValueError("config.toml: database.url invalid or unsupported") from None
    for key in ("browser_cache_path", "browser_executable_path"):
        raw = getattr(loaded, key)
        if raw:
            resolved = Path(raw)
            if not resolved.is_absolute():
                resolved = path.parent / resolved
            setattr(loaded, key, str(resolved.resolve()))
    safe = loaded.model_dump(exclude={"llm_api_key", "browser_license_key",
                                      "database_url", "config_path", "config_version"})
    loaded.config_version = sha256(json.dumps(safe, sort_keys=True).encode()).hexdigest()[:16]
    return loaded


@lru_cache
def get_settings() -> Settings:
    candidates = [
        Path(__file__).resolve().parents[4] / "config.toml",
        Path(__file__).resolve().parents[3] / "config.toml",
        Path.cwd() / "config.toml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return load_settings(candidate)
    raise ValueError("config.toml is missing")


settings = get_settings()
