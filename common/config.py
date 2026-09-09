"""User configuration for the installed `ai` package.

Layout (TOML):

    [openrouter]
    api_key = "..."
    model = "..."
    base_url = "..."
    timeout = 30.0
    max_tokens = 1024
    app_url = "..."
    app_name = "..."

    [recap]
    db_path = "~/.config/ai/opencode.db"

Resolution order for the file itself:
    1. $XDG_CONFIG_HOME/ai/config.toml (if XDG_CONFIG_HOME set)
    2. ~/.config/ai/config.toml

Value precedence per key: config file > default.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

APP_DIR_NAME = "ai"
CONFIG_FILE_NAME = "config.toml"

OPENROUTER_SECTION = "openrouter"
RECAP_SECTION = "recap"


def config_path(explicit: str | None = None) -> Path:
    """Return the config file path without touching disk."""
    if explicit and explicit.strip():
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / APP_DIR_NAME / CONFIG_FILE_NAME


def load_file(path: Path | None = None) -> dict[str, Any]:
    """Load and parse the TOML config file. Missing file -> {}."""
    resolved = path if path is not None else config_path()
    if not resolved.is_file():
        return {}
    try:
        with open(resolved, "rb") as fh:
            data = tomllib.load(fh)
    except Exception as exc:
        raise RuntimeError(
            f"error: cannot parse config file '{resolved}': {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"error: config file '{resolved}' must contain TOML tables")
    return data


def get_section(data: dict[str, Any], section: str) -> dict[str, Any]:
    """Return a section table, tolerating a missing or malformed section."""
    raw = data.get(section, {})
    return raw if isinstance(raw, dict) else {}


def resolve_file_value(
    file_value: Any,
    default: Any = None,
) -> Any:
    """Two-layer precedence: config file > default.

    Blank strings (or blank-only) count as unset at the file layer.
    """
    if file_value is not None and not (
        isinstance(file_value, str) and file_value.strip() == ""
    ):
        return file_value
    return default


def redact(value: Any) -> str:
    """Render a value for `ai config show`, masking secrets."""
    if value is None or (isinstance(value, str) and value == ""):
        return "(unset)"
    text = str(value)
    if len(text) <= 8:
        return "****"
    return f"{text[:4]}…{text[-4:]} (set)"
