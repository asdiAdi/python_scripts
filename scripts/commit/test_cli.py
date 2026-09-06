"""Tests for the commit script."""

from argparse import ArgumentParser, Namespace

import pytest

from scripts.commit.cli import (
    EXCLUDE_SPECS,
    build_system_prompt,
    build_user_prompt,
    parse_candidates,
    register,
    run,
)
import scripts.commit.cli as cli_mod
from unittest.mock import patch
from types import SimpleNamespace


def _cp(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# --- pure prompts ---


def test_build_system_prompt_contains_rules():
    s = build_system_prompt(3)
    assert "Conventional Commit" in s
    assert "feat" in s
    assert "exactly 3 candidate" in s


def test_build_system_prompt_exact_count():
    assert "exactly 1 candidate" in build_system_prompt(1)
    assert "exactly 5 candidate" in build_system_prompt(5)


def test_build_user_prompt_embeds_context():
    s = build_user_prompt("stat-x", "M foo.py", "diff-x", 2)
    assert "stat-x" in s
    assert "M foo.py" in s
    assert "diff-x" in s
    assert "2" in s


def test_build_user_prompt_fallbacks():
    s = build_user_prompt("", "", "", 3)
    assert "(clean)" in s
    assert "(no stat)" in s
    assert "(no textual diff" in s


# --- parse_candidates ---


def test_parse_candidates_keeps_valid():
    raw = "feat(auth): add login rate limit\nfix: handle empty diff"
    out = parse_candidates(raw, 3)
    assert out == ["feat(auth): add login rate limit", "fix: handle empty diff"]


def test_parse_candidates_strips_decorations():
    raw = "\n".join(
        [
            "1. feat(api): add retry",
            "- fix(db): drop stale lock",
            "* docs: update readme.",
            '"chore: bump deps"',
            "```",
            "```fix: fenced block ignored",
        ]
    )
    out = parse_candidates(raw, 5)
    assert "feat(api): add retry" in out
    assert "fix(db): drop stale lock" in out
    assert "docs: update readme" in out
    assert "chore: bump deps" in out
    assert all(not m.startswith("```") for m in out)


def test_parse_candidates_rejects_dedupes_and_caps():
    raw = "\n".join(
        [
            "oops this is not conventional",
            "feat: first message",
            "feat: first message",  # duplicate
            "x" * 121,  # too long
            "",
            "fix: second message",
            "docs: third message",
        ]
    )
    out = parse_candidates(raw, 2)
    assert out == ["feat: first message", "fix: second message"]


def test_parse_candidates_empty():
    assert parse_candidates("", 3) == []
    assert parse_candidates("hello\nworld\n", 3) == []


# --- _valid_num via parser ---


def test_valid_num_accepts_range():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "commit")
    assert parser.parse_args(["commit", "-n", "1"]).num == 1
    assert parser.parse_args(["commit", "--num", "5"]).num == 5


def test_valid_num_rejects_out_of_range():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "commit")
    with pytest.raises(SystemExit):
        parser.parse_args(["commit", "-n", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["commit", "-n", "6"])
    with pytest.raises(SystemExit):
        parser.parse_args(["commit", "-n", "abc"])


# --- register ---


def test_register_uses_folder_derived_command():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "commit")
    args = parser.parse_args(["commit"])
    assert args.command == "commit"
    assert args.num == 3
    assert args._func is run


def test_register_custom_num():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "commit")
    args = parser.parse_args(["commit", "--num", "2"])
    assert args.num == 2


def test_exclude_specs_cover_lockfiles():
    joined = " ".join(EXCLUDE_SPECS)
    assert "uv.lock" in joined
    assert "package-lock.json" in joined
    assert "Cargo.lock" in joined


# --- run() branches ---

CALLS: list[tuple] = []


def _dispatch(mapping):
    def _inner(*argv):
        CALLS.append(argv)
        key = argv
        if key in mapping:
            return mapping[key]
        return _cp()

    return _inner


def test_run_not_in_repo():
    CALLS.clear()
    with patch.object(cli_mod, "run_git", return_value=_cp(returncode=1)):
        assert run(Namespace(num=3)) == 1


def test_run_clean_tree(capsys):
    def fake(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:2] == ("status", "--porcelain"):
            return _cp(returncode=0, stdout="   \n")
        raise AssertionError(argv)

    with patch.object(cli_mod, "run_git", side_effect=fake):
        assert run(Namespace(num=3)) == "nothing to commit, working tree clean"


def test_run_add_failure():
    def fake(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:2] == ("status", "--porcelain"):
            return _cp(stdout="M foo.py\n")
        if argv[:2] == ("add", "-A"):
            return _cp(returncode=1, stderr="boom")
        raise AssertionError(argv)

    with patch.object(cli_mod, "run_git", side_effect=fake):
        assert run(Namespace(num=3)) == 1


def test_run_prompt_failure_resets(capsys):
    seen = []

    def fake_git(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:2] == ("status", "--porcelain"):
            return _cp(stdout="M foo.py\n")
        if argv[:2] == ("add", "-A"):
            return _cp(returncode=0)
        if argv[:3] == ("diff", "--cached", "--stat"):
            return _cp(stdout="stat")
        if argv[:3] == ("diff", "--cached", "--no-color"):
            return _cp(stdout="diff")
        if argv == ("reset", "-q"):
            seen.append(argv)
            return _cp(returncode=0)
        raise AssertionError(argv)

    class Boom:
        def ask(self, *a, **k):
            raise RuntimeError("error: no key")

    with (
        patch.object(cli_mod, "run_git", side_effect=fake_git),
        patch.object(cli_mod, "PromptClient", return_value=Boom()),
    ):
        assert run(Namespace(num=3)) == 1
    assert ("reset", "-q") in seen


def test_run_no_candidates_resets(capsys):
    seen = []

    def fake_git(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:2] == ("status", "--porcelain"):
            return _cp(stdout="M foo.py\n")
        if argv[:2] == ("add", "-A"):
            return _cp(returncode=0)
        if argv[0] in ("diff",):
            return _cp(stdout="x")
        if argv == ("reset", "-q"):
            seen.append(argv)
            return _cp(returncode=0)
        raise AssertionError(argv)

    class Empty:
        def ask(self, *a, **k):
            return "hello not conventional"

    with (
        patch.object(cli_mod, "run_git", side_effect=fake_git),
        patch.object(cli_mod, "PromptClient", return_value=Empty()),
    ):
        assert run(Namespace(num=3)) == 1
    assert ("reset", "-q") in seen


def test_run_abort_returns_none():
    def fake_git(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:2] == ("status", "--porcelain"):
            return _cp(stdout="M foo.py\n")
        if argv[:2] == ("add", "-A"):
            return _cp(returncode=0)
        if argv[0] == "diff":
            return _cp(stdout="x")
        if argv == ("reset", "-q"):
            return _cp(returncode=0)
        raise AssertionError(argv)

    class Good:
        def ask(self, *a, **k):
            return "feat: add thing"

    with (
        patch.object(cli_mod, "run_git", side_effect=fake_git),
        patch.object(cli_mod, "PromptClient", return_value=Good()),
        patch("builtins.input", return_value="n"),
    ):
        assert run(Namespace(num=1)) is None


def test_run_invalid_selection_returns_1():
    def fake_git(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:2] == ("status", "--porcelain"):
            return _cp(stdout="M foo.py\n")
        if argv[:2] == ("add", "-A"):
            return _cp(returncode=0)
        if argv[0] == "diff":
            return _cp(stdout="x")
        if argv == ("reset", "-q"):
            return _cp(returncode=0)
        raise AssertionError(argv)

    class Good:
        def ask(self, *a, **k):
            return "feat: add thing"

    with (
        patch.object(cli_mod, "run_git", side_effect=fake_git),
        patch.object(cli_mod, "PromptClient", return_value=Good()),
        patch("builtins.input", return_value="99"),
    ):
        assert run(Namespace(num=1)) == 1


def test_run_success_returns_sha_prefixed(capsys):
    def fake_git(*argv):
        if argv[:2] == ("rev-parse", "--is-inside-work-tree"):
            return _cp(returncode=0)
        if argv[:2] == ("status", "--porcelain"):
            return _cp(stdout="M foo.py\n")
        if argv[:2] == ("add", "-A"):
            return _cp(returncode=0)
        if argv[0] == "diff":
            return _cp(stdout="x")
        if argv[:2] == ("commit", "-m"):
            assert argv[2] == "feat: add thing"
            return _cp(returncode=0)
        if argv[:2] == ("rev-parse", "--short"):
            return _cp(stdout="abc1234\n")
        raise AssertionError(argv)

    class Good:
        def ask(self, *a, **k):
            return "feat: add thing"

    with (
        patch.object(cli_mod, "run_git", side_effect=fake_git),
        patch.object(cli_mod, "PromptClient", return_value=Good()),
        patch("builtins.input", return_value="1"),
    ):
        out = run(Namespace(num=1))
    assert out == "[abc1234] feat: add thing"
    printed = capsys.readouterr().out
    assert "1) feat: add thing" in printed
