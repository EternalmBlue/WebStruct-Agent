"""Compatibility import; configuration lives in platform.configuration."""
from app.platform.configuration import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
