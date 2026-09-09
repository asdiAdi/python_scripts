"""Dispatcher regression tests."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def run_main(*args: str):
    return subprocess.run(
        [sys.executable, str(REPO / "main.py"), *args],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,  # intentional: tests assert on returncode themselves
    )


def test_list_shows_hello_world():
    proc = run_main("--list")
    assert proc.returncode == 0
    assert "hello-world" in proc.stdout


def test_where_shows_path():
    proc = run_main("--where", "hello-world")
    assert proc.returncode == 0
    assert "hello_world" in proc.stdout
    assert "cli.py" in proc.stdout


def test_where_unknown_fails():
    proc = run_main("--where", "bogus-command")
    assert proc.returncode == 1
    assert proc.stderr.strip() == "error: unknown command 'bogus-command'"
    assert proc.stdout == ""


def test_hello_world_default():
    proc = run_main("hello-world")
    assert proc.returncode == 0
    assert proc.stdout.strip() == "Hello World"


def test_hello_world_with_name():
    proc = run_main("hello-world", "--name", "Bob")
    assert proc.returncode == 0
    assert proc.stdout.strip() == "Hello Bob"


def test_unknown_command_error_only():
    proc = run_main("bogus-command")
    assert proc.returncode == 2
    assert proc.stderr.strip() == "error: unknown command 'bogus-command'"
    assert proc.stdout == ""
    assert "usage" not in proc.stderr.lower()
    assert "main.py" not in proc.stderr
    assert "choose from" not in proc.stderr.lower()
