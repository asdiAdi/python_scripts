"""Tests for the recap script."""

from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import sqlite3

import pytest

from scripts.recap.cli import (
    build_system_prompt,
    build_user_prompt,
    clean_bullets,
    fetch_parts,
    parse_date_window,
    register,
    resolve_db_path,
    run,
)
import scripts.recap.cli as cli_mod
from unittest.mock import patch

MANILA = ZoneInfo("Asia/Manila")
NOW = datetime(2026, 9, 7, 12, 0, tzinfo=MANILA)


# --- register ---


def test_register_uses_folder_derived_command():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "recap")
    args = parser.parse_args(["recap"])
    assert args.command == "recap"
    assert args.date == []
    assert args.bullets == 5
    assert args.db is None
    assert args.model is None
    assert args._func is run


def test_register_parses_date_and_flags():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "recap")
    args = parser.parse_args(["recap", "yesterday", "-b", "3"])
    assert args.date == ["yesterday"]
    assert args.bullets == 3
    args = parser.parse_args(["recap", "--bullets", "all", "--db", "/tmp/x.db"])
    assert args.bullets is None
    assert args.db == "/tmp/x.db"


def test_valid_bullets_accepts_range_and_all():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "recap")
    assert parser.parse_args(["recap", "-b", "1"]).bullets == 1
    assert parser.parse_args(["recap", "-b", "20"]).bullets == 20
    assert parser.parse_args(["recap", "-b", "all"]).bullets is None


def test_valid_bullets_rejects_out_of_range():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "recap")
    with pytest.raises(SystemExit):
        parser.parse_args(["recap", "-b", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["recap", "-b", "21"])
    with pytest.raises(SystemExit):
        parser.parse_args(["recap", "-b", "abc"])


# --- pure prompts ---


def test_build_system_prompt_capped():
    s = build_system_prompt(5)
    assert "at most 5 bullet" in s
    assert "Bullet points only" in s


def test_build_system_prompt_uncapped():
    s = build_system_prompt(None)
    assert "as many bullet" in s


def test_build_user_prompt_embeds_groups_and_label():
    groups = [{"name": "myproj", "parts": [{"text": "did a thing"}]}]
    s = build_user_prompt(groups, "today")
    assert "today" in s
    assert "myproj" in s
    assert "did a thing" in s


def test_build_user_prompt_truncates():
    big = "x" * (cli_mod.MAX_PROMPT_CHARS + 100)
    groups = [{"name": "p", "parts": [{"text": big}]}]
    s = build_user_prompt(groups, "today")
    assert len(s) <= cli_mod.MAX_PROMPT_CHARS + 100
    assert "[truncated" in s


def test_clean_bullets_normalizes():
    raw = "\n".join(
        [
            "1. first thing",
            "* second thing",
            "+ third thing",
            "```",
            "plain line",
            "",
            "- already a bullet",
        ]
    )
    out = clean_bullets(raw)
    lines = out.splitlines()
    assert lines[0] == "- first thing"
    assert lines[1] == "- second thing"
    assert lines[2] == "- third thing"
    assert all(line.startswith("- ") for line in lines)


def test_clean_bullets_empty():
    assert clean_bullets("") == ""
    assert clean_bullets("```\n```") == ""


# --- date parsing ---


def test_parse_today_and_yesterday():
    s_ms, e_ms, label = parse_date_window("today", NOW)
    assert label == "today"
    assert e_ms - s_ms == 24 * 3600 * 1000
    s2, e2, label2 = parse_date_window("yesterday", NOW)
    assert label2 == "yesterday"
    assert s2 == s_ms - 24 * 3600 * 1000
    assert e2 == s_ms


def test_parse_relative_windows():
    _, _, label = parse_date_window("last-week", NOW)
    assert label == "last-week"
    _, _, label = parse_date_window("last-month", NOW)
    assert label == "last-month"
    _, _, label = parse_date_window("last-year", NOW)
    assert label == "last-year"


def test_parse_month_only():
    _, _, label = parse_date_window("january", NOW)
    assert label == "2026-01"
    _, _, label = parse_date_window("january 2023", NOW)
    assert label == "2023-01"


def test_parse_exact_date():
    s_ms, e_ms, label = parse_date_window("2026-09-01", NOW)
    assert label == "2026-09-01"
    assert e_ms - s_ms == 24 * 3600 * 1000


def test_parse_invalid_raises():
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        parse_date_window("not-a-date-xyzzy-!!", NOW)


# --- db path + fetch ---


def test_resolve_db_path_explicit():
    assert resolve_db_path("/tmp/x.db") == Path("/tmp/x.db")
    assert resolve_db_path("~/x.db") == Path.home() / "x.db"


def test_resolve_db_path_env(monkeypatch):
    monkeypatch.setenv("OPENCODE_DB_PATH", "/tmp/env.db")
    assert resolve_db_path(None) == Path("/tmp/env.db")


def test_resolve_db_path_default(monkeypatch):
    monkeypatch.delenv("OPENCODE_DB_PATH", raising=False)
    assert str(resolve_db_path(None)).endswith("opencode.db")


def _make_db(path: Path, rows: list[tuple[str, str, int]]):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT)")
    con.execute("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT)")
    con.execute(
        "CREATE TABLE part (message_id TEXT, data TEXT, time_created INTEGER)"
    )
    con.execute("INSERT INTO session VALUES ('s1', '/repo/myproj')")
    con.execute("INSERT INTO message VALUES ('m1', 's1')")
    for data, _mid, ts in rows:
        con.execute(
            "INSERT INTO part VALUES ('m1', ?, ?)", (data, ts)
        )
    con.commit()
    con.close()


def test_fetch_parts_groups_by_folder(tmp_path):
    db = tmp_path / "opencode.db"
    good = json.dumps({"type": "text", "text": "hello"})
    _make_db(db, [(good, "m1", 1_000)])
    groups = fetch_parts(db, 0, 2_000)
    assert groups == [{"name": "myproj", "parts": [{"type": "text", "text": "hello"}]}]


def test_fetch_parts_missing_file(tmp_path):
    with pytest.raises(RuntimeError, match="database not found"):
        fetch_parts(tmp_path / "nope.db", 0, 1)


def test_fetch_parts_filters_window(tmp_path):
    db = tmp_path / "opencode.db"
    good = json.dumps({"type": "text", "text": "in window"})
    outside = json.dumps({"type": "text", "text": "outside"})
    non_text = json.dumps({"type": "tool", "text": "skip me"})
    _make_db(
        db,
        [
            (good, "m1", 1_000),
            (outside, "m1", 99_000),
            (non_text, "m1", 1_000),
        ],
    )
    groups = fetch_parts(db, 0, 2_000)
    texts = [p["text"] for g in groups for p in g["parts"]]
    assert texts == ["in window"]


# --- run() ---


def test_run_no_activity():
    with (
        patch.object(cli_mod, "parse_date_window", return_value=(0, 1, "today")),
        patch.object(cli_mod, "fetch_parts", return_value=[]),
    ):
        assert run(Namespace(date=[], bullets=5, db=None, model=None)) == (
            "no activity found for today"
        )


def test_run_db_not_found():
    with (
        patch.object(cli_mod, "parse_date_window", return_value=(0, 1, "today")),
        patch.object(
            cli_mod,
            "fetch_parts",
            side_effect=RuntimeError("error: database not found: /x"),
        ),
    ):
        assert run(Namespace(date=[], bullets=5, db="/x", model=None)) == 1


def test_run_bad_date():
    import argparse

    with patch.object(
        cli_mod,
        "parse_date_window",
        side_effect=argparse.ArgumentTypeError("could not parse date 'x'"),
    ):
        assert run(Namespace(date=["x"], bullets=5, db=None, model=None)) == 1


def test_run_success_caps_bullets():
    groups = [{"name": "p", "parts": [{"text": "hi"}]}]

    class Good:
        def ask(self, *a, **k):
            return "- b1\n- b2\n- b3\n"

    with (
        patch.object(cli_mod, "parse_date_window", return_value=(0, 1, "today")),
        patch.object(cli_mod, "fetch_parts", return_value=groups),
        patch.object(cli_mod, "PromptClient", return_value=Good()),
    ):
        out = run(Namespace(date=[], bullets=2, db=None, model=None))
    assert out == "- b1\n- b2"


def test_run_success_unlimited():
    groups = [{"name": "p", "parts": [{"text": "hi"}]}]

    class Good:
        def ask(self, *a, **k):
            return "- b1\n- b2\n- b3\n"

    with (
        patch.object(cli_mod, "parse_date_window", return_value=(0, 1, "today")),
        patch.object(cli_mod, "fetch_parts", return_value=groups),
        patch.object(cli_mod, "PromptClient", return_value=Good()),
    ):
        out = run(Namespace(date=[], bullets=None, db=None, model=None))
    assert out == "- b1\n- b2\n- b3"


def test_run_prompt_failure_returns_1():
    groups = [{"name": "p", "parts": [{"text": "hi"}]}]

    class Boom:
        def ask(self, *a, **k):
            raise RuntimeError("error: no key")

    with (
        patch.object(cli_mod, "parse_date_window", return_value=(0, 1, "today")),
        patch.object(cli_mod, "fetch_parts", return_value=groups),
        patch.object(cli_mod, "PromptClient", return_value=Boom()),
    ):
        assert run(Namespace(date=[], bullets=5, db=None, model=None)) == 1


def test_run_empty_model_output_returns_1():
    groups = [{"name": "p", "parts": [{"text": "hi"}]}]

    class Empty:
        def ask(self, *a, **k):
            return "   \n"

    with (
        patch.object(cli_mod, "parse_date_window", return_value=(0, 1, "today")),
        patch.object(cli_mod, "fetch_parts", return_value=groups),
        patch.object(cli_mod, "PromptClient", return_value=Empty()),
    ):
        assert run(Namespace(date=[], bullets=5, db=None, model=None)) == 1
