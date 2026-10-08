"""行为覆盖：configuration-center.feature 的可执行核心契约。"""

from pathlib import Path

from app.platform.configuration import load_settings


def test_config_toml_is_single_source_and_public_projection_is_safe(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text(
        '[model]\napi_key = "toml-secret"\n'
        '[database]\nurl = "sqlite:///data.db"\n'
        '[browser]\nlicense_key = "browser-secret"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-secret")
    settings = load_settings(path)
    assert settings.llm_api_key == "toml-secret"
    assert "toml-secret" not in repr(settings)
    assert "browser-secret" not in repr(settings.public_config())
    assert Path(settings.database_url.removeprefix("sqlite:///")).parent == tmp_path


def test_invalid_or_missing_config_has_actionable_error(tmp_path):
    missing = tmp_path / "missing.toml"
    try:
        load_settings(missing)
    except ValueError as exc:
        assert "config.toml is missing" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("missing config must fail")

    invalid = tmp_path / "config.toml"
    invalid.write_text("[model]\nname = 42\n", encoding="utf-8")
    try:
        load_settings(invalid)
    except ValueError as exc:
        assert "model.name" in str(exc)
        assert "42" not in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid config must fail")
