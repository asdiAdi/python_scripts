"""Path helpers shared by all scripts.

Repo layout assumed:
    <workspace>/              e.g. ~/script_projects/
    <workspace>/python_scripts/   this project

WORKSPACE_ROOT resolution order:
    1. $WORKSPACE_ROOT env var (if set and valid)
    2. Parent of this repo (python_scripts/ -> script_projects/)
    3. Fallback: cwd
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_repo_root() -> Path:
    """Return the python_scripts repo root (directory containing main.py)."""
    return REPO_ROOT


def get_workspace_root() -> Path:
    """Return the workspace root containing this repo."""
    env = os.environ.get("WORKSPACE_ROOT")
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p
    # Default: parent of this repo.
    parent = REPO_ROOT.parent
    if parent.is_dir():
        return parent
    return Path.cwd().resolve()
