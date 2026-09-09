"""Copy bundled templates into the current directory."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

HELP = "Copy a bundled template into the current directory."

FILES_DIR = Path(__file__).resolve().parent / "files"


def available_templates() -> list[str]:
    """Return sorted template names (files and dirs) found under files/."""
    if not FILES_DIR.is_dir():
        return []
    return sorted(p.name for p in FILES_DIR.iterdir() if p.is_file() or p.is_dir())


def copy_template(name: str, dest: Path, force: bool = False) -> list[str]:
    """Copy template into dest, return copied relative paths (posix)."""
    src = FILES_DIR / name
    if src.is_file():
        target = dest / src.name
        if target.exists() and not force:
            raise FileExistsError(f"refusing to overwrite existing file: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        return [src.name]
    if src.is_dir():
        copied: list[str] = []
        for src_file in sorted(src.rglob("*")):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(src)
            target = dest / rel
            if target.exists() and not force:
                raise FileExistsError(f"refusing to overwrite existing file: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_file, target)
            copied.append(rel.as_posix())
        return copied
    raise FileNotFoundError(f"unknown template '{name}'")


def build_message(name: str, copied: list[str], dest: Path) -> str:
    try:
        dest_str = str(dest.resolve())
    except OSError:
        dest_str = str(dest)
    lines = [f"generated '{name}': {len(copied)} file(s) -> {dest_str}"]
    lines.extend(f"  {rel}" for rel in copied)
    return "\n".join(lines)


def build_list_message(templates: list[str]) -> str:
    if not templates:
        return "no templates available"
    lines = ["available templates:"]
    lines.extend(f"  {name}" for name in templates)
    return "\n".join(lines)


def register(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help=HELP)
    parser.add_argument(
        "template",
        nargs="?",
        default=None,
        help="Template to generate (file or directory name under files/).",
    )
    parser.add_argument(
        "-l",
        "-list",
        "--list",
        dest="list_templates",
        action="store_true",
        help="List available templates and exit.",
    )
    parser.add_argument(
        "-f",
        "-force",
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )
    parser.set_defaults(_func=run)


def run(args) -> str | int:
    """Entrypoint called by main.py. Must return str, int, or None."""
    if bool(getattr(args, "list_templates", False)):
        return build_list_message(available_templates())
    dest = Path(os.environ.get("PWD", "")).expanduser()
    name = getattr(args, "template", None) or ""
    if not name:
        print("error: no template given", file=sys.stderr)
        return 1
    force = bool(getattr(args, "force", False))

    try:
        copied = copy_template(name, dest, force=force)
    except FileNotFoundError:
        print("error: unknown template", file=sys.stderr)
        return 1
    except FileExistsError as exc:
        print(f"error: {exc} (use --force to overwrite)", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: copy failed: {exc}", file=sys.stderr)
        return 1
    return build_message(name, copied, dest)
