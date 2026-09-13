"""Tests for the pr script."""

from argparse import ArgumentParser, Namespace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import scripts.pr.cli as cli_mod
from scripts.pr.cli import (
    EXCLUDE_SPECS,
    MAX_PROMPT_CHARS,
    build_system_prompt,
    build_user_prompt,
    register,
    run,
)


def _cp(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# --- pure prompts ---


def test_build_system_prompt_has_pr_sections():
    s = build_system_prompt()
    assert "## Summary" in s
    assert "## Changes" in s
    assert "## Testing" in s
    assert "## Notes" in s


def test_build_user_prompt_embeds_context():
    s = build_user_prompt(
        "feat-x",
        "main",
        "abc log",
        "stat-x",
        "M foo.py",
        "diff-x",
    )
    assert "feat-x" in s
    assert "main" in s
    assert "abc log" in s
    assert "stat-x" in s
    assert "M foo.py" in s
    assert "diff-x" in s


def test_build_user_prompt_fallbacks():
    s = build_user_prompt("", "main", "", "", "", "")
    assert "(unknown)" in s
    assert "(no commits ahead)" in s
    assert "(clean)" in s
    assert "(no stat)" in s
    assert "(no textual diff" in s


def test_build_user_prompt_truncates_diff():
    big = "x" * (MAX_PROMPT_CHARS + 1000)
    s = build_user_prompt("b", "main", "log", "stat", "status", big)
    assert len(s) <= MAX_PROMPT_CHARS + 10
    assert s.endswith("\n...")


def test_max_prompt_chars_targets_20k_tokens():
    assert MAX_PROMPT_CHARS == 80000


# --- register ---


def test_register_defaults_to_main():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "pr")
    args = parser.parse_args(["pr"])
    assert args.command == "pr"
    assert args.base == "main"
    assert args._func is run


def test_register_custom_base():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "pr")
    args = parser.parse_args(["pr", "--base", "develop"])
    assert args.base == "develop"


def test_register_rejects_empty_base():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "pr")
    with pytest.raises(SystemExit):
        parser.parse_args(["pr", "--base", "   "])


def test_exclude_specs_cover_lockfiles():
    joined = " ".join(EXCLUDE_SPECS)
    assert "uv.lock" in joined
    assert "package-lock.json" in joined
    assert "Cargo.lock" in joined


# --- run() branches ---


def test_run_not_in_repo(capsys):
    with patch.object(cli_mod, "run_git", return_value=_cp(returncode=1)):
        assert run(Namespace(base="main")) == 1
    assert "not inside a git repository" in capsys.readouterr().err


def test_run_missing_base(capsys):
    def fake(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:3] == ("rev-parse", "--verify", "--quiet"):
            return _cp(returncode=1)
        raise AssertionError(argv)

    with patch.object(cli_mod, "run_git", side_effect=fake):
        assert run(Namespace(base="main")) == 1
    assert "base branch 'main' not found" in capsys.readouterr().err


def test_run_no_diff_returns_message():
    def fake(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:3] == ("rev-parse", "--verify", "--quiet"):
            return _cp(returncode=0)
        if argv[:2] == ("branch", "--show-current"):
            return _cp(stdout="feat-x\n")
        if argv[0] in ("log", "status", "diff"):
            return _cp(stdout="")
        raise AssertionError(argv)

    with patch.object(cli_mod, "run_git", side_effect=fake):
        out = run(Namespace(base="main"))
    assert out == "nothing to describe, no differences between feat-x and main"


def test_run_prompt_failure_returns_1(capsys):
    def fake_git(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:3] == ("rev-parse", "--verify", "--quiet"):
            return _cp(returncode=0)
        if argv[:2] == ("branch", "--show-current"):
            return _cp(stdout="feat-x\n")
        if argv[0] == "log":
            return _cp(stdout="abc do thing\n")
        if argv[0] in ("status", "diff"):
            return _cp(stdout="x")
        raise AssertionError(argv)

    class Boom:
        def ask(self, *a, **k):
            raise RuntimeError("error: no key")

    with (
        patch.object(cli_mod, "run_git", side_effect=fake_git),
        patch.object(cli_mod, "PromptClient", return_value=Boom()),
    ):
        assert run(Namespace(base="main")) == 1
    assert "error: no key" in capsys.readouterr().err


def test_run_empty_answer_returns_1(capsys):
    def fake_git(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:3] == ("rev-parse", "--verify", "--quiet"):
            return _cp(returncode=0)
        if argv[:2] == ("branch", "--show-current"):
            return _cp(stdout="feat-x\n")
        if argv[0] == "log":
            return _cp(stdout="abc do thing\n")
        if argv[0] in ("status", "diff"):
            return _cp(stdout="x")
        raise AssertionError(argv)

    class Empty:
        def ask(self, *a, **k):
            return "   "

    with (
        patch.object(cli_mod, "run_git", side_effect=fake_git),
        patch.object(cli_mod, "PromptClient", return_value=Empty()),
    ):
        assert run(Namespace(base="main")) == 1
    assert "did not return a PR description" in capsys.readouterr().err


def test_run_success_returns_answer():
    def fake_git(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:3] == ("rev-parse", "--verify", "--quiet"):
            return _cp(returncode=0)
        if argv[:2] == ("branch", "--show-current"):
            return _cp(stdout="feat-x\n")
        if argv[0] == "log":
            return _cp(stdout="abc do thing\n")
        if argv[0] in ("status", "diff"):
            return _cp(stdout="x")
        raise AssertionError(argv)

    class Good:
        def ask(self, user_prompt, system=None):
            assert "feat-x" in user_prompt
            assert "## Summary" in system
            return "feat(x): add thing\n\n## Summary\nDoes x."

    with (
        patch.object(cli_mod, "run_git", side_effect=fake_git),
        patch.object(cli_mod, "PromptClient", return_value=Good()),
    ):
        out = run(Namespace(base="main"))
    assert out.startswith("feat(x): add thing")
