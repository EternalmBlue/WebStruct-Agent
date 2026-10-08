"""Resolve BDD feature files from the repository-level specs directory."""

from pathlib import Path


def feature_path(name: str) -> str:
    return str(Path(__file__).resolve().parents[3] / "specs" / "features" / name)
