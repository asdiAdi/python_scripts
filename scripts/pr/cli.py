"""Generate a GitHub-ready PR title and body from the branch diff."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from common.prompt import PromptClient

HELP = "Generate a GitHub-ready PR title and body from the branch diff vs base."

MAX_PROMPT_CHARS = 80000

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


def build_system_prompt() -> str:
    """Return the PR-writing system prompt following GitHub best practices."""
    return "\n".join(
        [
            "You write concise, high-quality GitHub pull request titles and descriptions.",
            "",
            "First line is the title: Conventional-Commit style (<type>[scope]: <subject>),",
            "imperative mood, lowercase subject, no trailing period, max 72 chars.",
            "",
            "Then a blank line, then the body in markdown with exactly these sections:",
            "",
            "## Summary",
            "1-2 sentences max. What changed and why it matters. No restating the title.",
            "Skip obvious context; assume the reader can read the diff.",
            "",
            "## Changes",
            "3-6 bullets max, one line each. Only user-visible or architecturally notable",
            "changes — skip trivial renames, formatting, or self-evident edits.",
            "Reference specific files/symbols/functions from the diff, not vague summaries.",
            "If the diff has more than 6 meaningful changes, group related ones into a single bullet.",
            "",
            "## Notes",
            "Only include real risks, breaking changes, or follow-ups, 1-2 bullets max.",
            "If none, this section must be exactly: None",
            "",
        ]
    )


def build_user_prompt(
    branch: str,
    base: str,
    log: str,
    stat: str,
    status: str,
    diff: str,
) -> str:
    """Return the user prompt carrying the branch-vs-base context."""
    full = (
        f"Generate a GitHub-ready PR title and body for branch '{branch or '(unknown)'}'"
        f" compared against base '{base}'.\n"
        f"\n--- git log {base}..HEAD --oneline ---\n{log or '(no commits ahead)'}\n"
        f"\n--- git status --porcelain ---\n{status or '(clean)'}\n"
        f"\n--- git diff {base}...HEAD --stat ---\n{stat or '(no stat)'}\n"
        f"\n--- git diff {base}...HEAD ---\n{diff or '(no textual diff; guess from filenames above)'}\n"
    )
    if len(full) > MAX_PROMPT_CHARS:
        full = full[:MAX_PROMPT_CHARS] + "\n..."
    return full


def run_git(*argv: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in `cwd`."""
    return subprocess.run(
        ["git", *argv],
        cwd=os.environ.get("PWD", ""),
        capture_output=True,
        text=True,
        check=False,
    )


def get_branch_context(base: str) -> tuple[str, str, str, str, str]:
    """Return (branch, log, stat, status, diff) for branch vs base."""
    branch = run_git("branch", "--show-current").stdout.strip()
    if not branch:
        branch = run_git("rev-parse", "--short", "HEAD").stdout.strip()
    log = run_git("log", f"{base}..HEAD", "--oneline").stdout.strip()
    status = run_git("status", "--porcelain").stdout.strip()
    stat = run_git(
        "diff", f"{base}...HEAD", "--stat", "--", *EXCLUDE_SPECS
    ).stdout.strip()
    diff = run_git(
        "diff", f"{base}...HEAD", "--no-color", "--unified=3", "--", *EXCLUDE_SPECS
    ).stdout.strip()
    return branch, log, stat, status, diff


def register(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help=HELP)
    parser.add_argument(
        "--base",
        type=_valid_base,
        default="main",
        help="Base branch to diff against (default: main).",
    )
    parser.set_defaults(_func=run)


def run(args) -> str | int | None:
    """Entrypoint called by main.py. Must return str, int, or None."""
    base = getattr(args, "base", "main") or "main"
    if not base.strip():
        print("error: base branch must not be empty", file=sys.stderr)
        return 1

    if run_git("rev-parse", "--is-inside-work-tree").returncode != 0:
        print("error: target is not inside a git repository", file=sys.stderr)
        return 1

    if run_git("rev-parse", "--verify", "--quiet", base).returncode != 0:
        print(f"error: base branch '{base}' not found", file=sys.stderr)
        return 1

    branch, log, stat, status, diff = get_branch_context(base)

    if not log and not stat and not diff:
        current = branch or "(unknown)"
        return f"nothing to describe, no differences between {current} and {base}"

    system = build_system_prompt()
    user_prompt = build_user_prompt(branch, base, log, stat, status, diff)

    try:
        client = PromptClient()
        answer = client.ask(user_prompt, system=system)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not answer or not answer.strip():
        print("error: model did not return a PR description", file=sys.stderr)
        return 1
    return answer.strip()


def _valid_base(value: str) -> str:
    if not value or not value.strip():
        raise argparse.ArgumentTypeError("base branch must not be empty")
    return value
