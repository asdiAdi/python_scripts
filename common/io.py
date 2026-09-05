"""Minimal I/O helpers shared by all scripts."""

from __future__ import annotations

import sys


def eprint(*args, **kwargs) -> None:
    """Print to stderr."""
    print(*args, file=sys.stderr, **kwargs)


def info(msg: str) -> None:
    print(msg)


def error(msg: str) -> None:
    eprint(f"error: {msg}")


def confirm(prompt: str = "Continue? [y/N] ") -> bool:
    """Ask for confirmation. Returns True only on y/yes."""
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")
