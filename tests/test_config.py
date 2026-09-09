"""Tests for common.config (TOML-only precedence + path resolution)."""

from common.config import config_path, load_file, resolve_file_value


def test_config_path_explicit(tmp_path):
    assert config_path(str(tmp_path / "x.toml")) == tmp_path / "x.toml"


def test_config_path_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_path() == tmp_path / "ai" / "config.toml"


def test_load_missing_returns_empty(tmp_path):
    assert load_file(tmp_path / "nope.toml") == {}


def test_resolve_file_value():
    assert resolve_file_value("from-file", "dflt") == "from-file"
    assert resolve_file_value(None, "dflt") == "dflt"
    assert resolve_file_value("", "dflt") == "dflt"
    assert resolve_file_value("   ", "dflt") == "dflt"
