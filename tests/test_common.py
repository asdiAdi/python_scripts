"""Tests for common helpers."""

from pathlib import Path

from common.paths import get_repo_root, get_workspace_root


def test_repo_root_contains_main():
    assert (get_repo_root() / "main.py").is_file()


def test_workspace_root_is_parent_of_repo():
    assert get_workspace_root() == get_repo_root().parent
    assert isinstance(get_workspace_root(), Path)
