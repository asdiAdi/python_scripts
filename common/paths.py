"""Path helpers shared by all scripts."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_repo_root() -> Path:
    """Return the python_scripts repo root"""
    return REPO_ROOT


def get_workspace_root() -> Path:
    """Return the workspace root containing this repo."""
    # Default: parent of this repo.
    parent = REPO_ROOT.parent
    if parent.is_dir():
        return parent
    return Path.cwd().resolve()
