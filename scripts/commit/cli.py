"""AI-assisted git commit.

Stages all changes in the repo you ran the command from, asks the model
for Conventional Commit candidates, lets you pick one, and commits it.

"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

from common.prompt import PromptClient

HELP = "Stage all changes, generate a Conventional Commit message with AI, and commit."

# Lockfiles and friends are never sent to the model (silently excluded).
EXCLUDE_SPECS = [
    ":!uv.lock",
    ":!*.lock",
    ":!package-lock.json",
    ":!yarn.lock",
    ":!pnpm-lock.yaml",
    ":!poetry.lock",
    ":!Pipfile.lock",
    ":!Cargo.lock",
    ":!Gemfile.lock",
]

TYPES = "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert"
_SUBJECT_RE = re.compile(rf"^(?:{TYPES})(\([a-z0-9_-]+\))?: .+\S$")


def build_system_prompt(num: int) -> str:
    """Return the Conventional-Commit system prompt."""
    lines = [
        "You write Conventional Commit messages. Rules:",
        "Allowed types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.",
        "Format: <type>[optional scope]: <subject>  e.g. feat(auth): add login rate limit",
        "Scope, when present, is lowercase (letters, digits, -, _).",
        "Subject starts lowercase, imperative mood, no trailing period, max 72 chars.",
        "Single line per message. No body, no footer, no breaking-change notes.",
        f"Output exactly {num} candidate message(s), one per line, most likely first.",
        "No numbering, no bullets, no quotes, no code fences, no explanations.",
    ]
    return "\n".join(lines)


def build_user_prompt(stat: str, status: str, diff: str, num: int) -> str:
    """Return the user prompt carrying the staged change context."""
    return (
        f"Generate {num} Conventional Commit message(s) for the staged changes below.\n"
        f"\n--- git status --porcelain ---\n{status or '(clean)'}\n"
        f"\n--- git diff --cached --stat ---\n{stat or '(no stat)'}\n"
        f"\n--- git diff --cached ---\n{diff or '(no textual diff; guess from filenames above)'}\n"
    )


def parse_candidates(raw: str, num: int) -> list[str]:
    """Extract up to `num` valid single-line Conventional Commit messages."""
    out: list[str] = []
    for line in (raw or "").splitlines():
        s = line.strip()
        # Strip code fences, bullets, numbering, quotes.
        if s.startswith("```"):
            continue
        s = re.sub(r"^[\d]+[.)]\s+", "", s)
        s = re.sub(r"^[-*+]\s+", "", s)
        s = s.strip().strip("\"'").strip().rstrip(".")
        if not s or len(s) > 120:
            continue
        if not _SUBJECT_RE.match(s):
            continue
        if s not in out:
            out.append(s)
        if len(out) >= num:
            break
    return out


def _valid_num(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"--num must be an integer, got {value!r}")
    if n < 1 or n > 5:
        raise argparse.ArgumentTypeError("--num must be between 1 and 5")
    return n


def run_git(*argv: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in `cwd`"""
    return subprocess.run(
        ["git", *argv],
        cwd=os.environ.get("PWD", ""),
        capture_output=True,
        text=True,
        check=False,
    )


def get_staged_diff() -> tuple[str, str, str]:
    """Return (status, stat, diff) for the staged index, lockfiles excluded."""
    status = run_git("status", "--porcelain").stdout.strip()
    stat = run_git("diff", "--cached", "--stat", "--", *EXCLUDE_SPECS).stdout.strip()
    diff = run_git(
        "diff", "--cached", "--no-color", "--unified=3", "--", *EXCLUDE_SPECS
    ).stdout

    return status, stat, diff.strip()


def register(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help=HELP)
    parser.add_argument(
        "-n",
        "--num",
        type=_valid_num,
        default=3,
        help="Number of commit message candidates to generate (1-5, default: 3).",
    )
    parser.set_defaults(_func=run)


def run(args) -> str | int | None:
    """Entrypoint called by main.py. Must return str, int, or None."""
    num = getattr(args, "num", 3)

    if (
        run_git(
            "rev-parse",
            "--is-inside-work-tree",
        ).returncode
        != 0
    ):
        print("error: target is not inside a git repository")
        return 1

    status_before = run_git(
        "status",
        "--porcelain",
    ).stdout.strip()
    if not status_before:
        return "nothing to commit, working tree clean"

    add_proc = run_git(
        "add",
        "-A",
    )
    if add_proc.returncode != 0:
        print(f"error: git add failed: {add_proc.stderr.strip()}", file=sys.stderr)
        return 1

    status, stat, diff = get_staged_diff()

    system = build_system_prompt(num)
    user_prompt = build_user_prompt(stat, status, diff, num)

    candidates: list[str] = []
    raw = ""

    try:
        client = PromptClient()
        raw = client.ask(user_prompt, system=system)
        candidates = parse_candidates(raw, num)
    except RuntimeError as exc:
        run_git(
            "reset",
            "-q",
        )
        print(str(exc), file=sys.stderr)
        return 1

    if not candidates:
        run_git(
            "reset",
            "-q",
        )
        print(
            "error: model did not return a valid Conventional Commit message",
            file=sys.stderr,
        )
        if raw.strip():
            print(raw.strip(), file=sys.stderr)
        return 1

    for i, msg in enumerate(candidates, 1):
        print(f"  {i}) {msg}")

    try:
        choice = (
            input(f"Pick 1-{len(candidates)} to commit [n to abort]: ").strip().lower()
        )
    except EOFError:
        choice = "n"

    if choice in ("", "n", "no", "q", "quit"):
        run_git(
            "reset",
            "-q",
        )
        return None

    try:
        idx = int(choice)
    except ValueError:
        run_git(
            "reset",
            "-q",
        )
        print(f"error: invalid selection {choice!r}", file=sys.stderr)
        return 1
    if idx < 1 or idx > len(candidates):
        run_git(
            "reset",
            "-q",
        )
        print(f"error: invalid selection {choice!r}", file=sys.stderr)
        return 1

    chosen = candidates[idx - 1]
    proc = run_git(
        "commit",
        "-m",
        chosen,
    )
    if proc.returncode != 0:
        print(proc.stderr.strip() or proc.stdout.strip(), file=sys.stderr)
        return 1

    sha = run_git(
        "rev-parse",
        "--short",
        "HEAD",
    ).stdout.strip()
    return f"[{sha}] {chosen}" if sha else f"committed: {chosen}"
