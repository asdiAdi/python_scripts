"""Manage the user-level `ai` configuration file."""

from __future__ import annotations

import os
from pathlib import Path

from common.config import (
    OPENROUTER_SECTION,
    RECAP_SECTION,
    config_path,
    get_section,
    load_file,
    redact,
    resolve_file_value,
)

HELP = "Manage ~/.config/ai/config.toml"

TEMPLATE = """\
# `ai` user configuration.
# Get a key at https://openrouter.ai/keys

[openrouter]
api_key = ""
model = ""
base_url = "https://openrouter.ai/api/v1"
# timeout =
# max_tokens =
# app_url =
# app_name =

[recap]
db_path = "~/.local/share/opencode/opencode.db"
"""

SHOW_KEYS = (
    (OPENROUTER_SECTION, "api_key"),
    (OPENROUTER_SECTION, "model"),
    (OPENROUTER_SECTION, "base_url"),
    (OPENROUTER_SECTION, "timeout"),
    (OPENROUTER_SECTION, "max_tokens"),
    (OPENROUTER_SECTION, "app_url"),
    (OPENROUTER_SECTION, "app_name"),
    (RECAP_SECTION, "db_path"),
)


def init_config(path: Path | None = None, force: bool = False) -> str:
    """Write the starter config file. Pure enough for direct unit tests."""
    target = path if path is not None else config_path()
    if target.exists() and not force:
        return f"exists: {target} (use --force to overwrite)"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(TEMPLATE, encoding="utf-8")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return f"wrote: {target}"


def show_config() -> str:
    """Render resolved config values with secrets redacted."""
    data = load_file()
    lines = [f"file: {config_path()}"]
    for section_name, key in SHOW_KEYS:
        raw = get_section(data, section_name).get(key)
        value = resolve_file_value(raw)
        source = "file" if raw not in (None, "") else "default"
        lines.append(f"{section_name}.{key} = {redact(value)} [{source}]")
    return "\n".join(lines)


def register(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help=HELP)
    sub = parser.add_subparsers(dest="config_action", metavar="<action>")
    p_init = sub.add_parser("init", help="Write a starter config file.")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing file.")
    p_init.add_argument("--path", default=None, help="Write to this path instead.")
    sub.add_parser("show", help="Show resolved values (secrets redacted).")
    sub.add_parser("path", help="Print the config file path.")
    parser.set_defaults(_func=run)


def run(args) -> str:
    """Entrypoint called by main.py. Must return str, int, or None."""
    action = getattr(args, "config_action", None)
    if action == "init":
        raw_path = getattr(args, "path", None)
        return init_config(
            Path(raw_path).expanduser() if raw_path else None,
            force=bool(getattr(args, "force", False)),
        )
    if action == "show":
        return show_config()
    if action == "path":
        return str(config_path())
    return f"config file: {config_path()}"
