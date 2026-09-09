"""Tests for the config command (pure helpers, no disk side effects outside tmp)."""

from pathlib import Path

import common.config as config_module
import scripts.config.cli as config_cli
from scripts.config.cli import init_config, register, run, show_config


def _args(action="path", **kwargs):
    parser_args = {"config_action": action, "_func": run}
    parser_args.update(kwargs)
    return type("Args", (), parser_args)()


def test_init_writes_template(tmp_path):
    target = tmp_path / "sub" / "config.toml"
    out = init_config(target)
    assert out.startswith("wrote: ")
    text = target.read_text(encoding="utf-8")
    assert "[openrouter]" in text
    assert "[recap]" in text


def test_init_no_overwrite_without_force(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text("existing", encoding="utf-8")
    out = init_config(target)
    assert out.startswith("exists: ")
    assert target.read_text(encoding="utf-8") == "existing"
    out = init_config(target, force=True)
    assert out.startswith("wrote: ")
    assert "[openrouter]" in target.read_text(encoding="utf-8")


def test_run_path_default(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert run(_args("path")) == str(tmp_path / "ai" / "config.toml")


def test_show_redacts_secret(monkeypatch, tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[openrouter]\napi_key = "sk-abcdefghijklmnop"\n', encoding="utf-8")
    monkeypatch.setattr(config_module, "config_path", lambda explicit=None: cfg)
    monkeypatch.setattr(config_cli, "config_path", lambda explicit=None: cfg)
    out = show_config()
    assert "sk-a" in out and "mnop" in out
    assert "abcdefghijklm" not in out


def test_show_file_source(monkeypatch, tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[openrouter]\napi_key = "sk-abcdefghijklmnop"\n', encoding="utf-8")
    monkeypatch.setattr(config_module, "config_path", lambda explicit=None: cfg)
    monkeypatch.setattr(config_cli, "config_path", lambda explicit=None: cfg)
    out = show_config()
    assert "[file]" in out
    assert "[env]" not in out


def test_register_has_subcommands():
    import argparse

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    register(sub, "config")
    for action in ("init", "show", "path"):
        ns = parser.parse_args(["config", action])
        assert ns.config_action == action
        assert callable(ns._func)
