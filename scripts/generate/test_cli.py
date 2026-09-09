"""Tests for the generate script."""

from argparse import ArgumentParser, Namespace
from pathlib import Path

import pytest

import scripts.generate.cli as cli_mod
from scripts.generate.cli import (
    available_templates,
    build_list_message,
    build_message,
    copy_template,
    register,
    run,
)


# --- register ---


def test_register_uses_folder_derived_command():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "generate")
    args = parser.parse_args(["generate"])
    assert args.command == "generate"
    assert args.template is None
    assert args.list_templates is False
    assert args.force is False
    assert args._func is run


def test_register_parses_template_positional():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "generate")
    args = parser.parse_args(["generate", "static-workflow"])
    assert args.template == "static-workflow"


def test_register_list_aliases():
    for flag in ("-l", "-list", "--list"):
        parser = ArgumentParser(prog="main.py")
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers, "generate")
        args = parser.parse_args(["generate", flag])
        assert args.list_templates is True


def test_register_force_aliases():
    for flag in ("-f", "-force", "--force"):
        parser = ArgumentParser(prog="main.py")
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers, "generate")
        args = parser.parse_args(["generate", "static-workflow", flag])
        assert args.force is True


# --- available_templates ---


def test_available_templates_lists_bundled():
    templates = available_templates()
    assert templates == sorted(templates)
    assert "static-workflow" in templates


def test_available_templates_empty_when_dir_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_mod, "FILES_DIR", tmp_path / "nope")
    assert available_templates() == []


# --- copy_template ---


def test_copy_template_dir(tmp_path):
    copied = copy_template("static-workflow", tmp_path)
    assert copied == [".github/workflows/deploy.yml"]
    target = tmp_path / ".github" / "workflows" / "deploy.yml"
    assert target.is_file()
    assert (
        target.read_text()
        == (
            cli_mod.FILES_DIR
            / "static-workflow"
            / ".github"
            / "workflows"
            / "deploy.yml"
        ).read_text()
    )


def test_copy_template_file(tmp_path, monkeypatch):
    src_dir = tmp_path / "templates"
    src_dir.mkdir()
    (src_dir / "hello.txt").write_text("hi\n")
    monkeypatch.setattr(cli_mod, "FILES_DIR", src_dir)
    dest = tmp_path / "dest"
    assert copy_template("hello.txt", dest) == ["hello.txt"]
    assert (dest / "hello.txt").read_text() == "hi\n"


def test_copy_template_unknown_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="unknown template"):
        copy_template("nosuch", tmp_path)


def test_copy_template_refuses_overwrite_without_force(tmp_path):
    copy_template("static-workflow", tmp_path)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        copy_template("static-workflow", tmp_path)


def test_copy_template_force_overwrites(tmp_path):
    copy_template("static-workflow", tmp_path)
    target = tmp_path / ".github" / "workflows" / "deploy.yml"
    target.write_text("stale\n")
    copied = copy_template("static-workflow", tmp_path, force=True)
    assert copied == [".github/workflows/deploy.yml"]
    assert "Deploy to S3" in target.read_text()


# --- pure messages ---


def test_build_list_message():
    assert build_list_message([]) == "no templates available"
    msg = build_list_message(["b", "a"])
    assert msg == "available templates:\n  b\n  a"


def test_build_message(tmp_path):
    msg = build_message("static-workflow", [".github/workflows/deploy.yml"], tmp_path)
    assert msg.startswith("generated 'static-workflow': 1 file(s) -> ")
    assert str(tmp_path.resolve()) in msg
    assert "  .github/workflows/deploy.yml" in msg


# --- run() ---


def test_run_list_returns_templates():
    out = run(Namespace(template=None, list_templates=True, force=False))
    assert out.startswith("available templates:")
    assert "static-workflow" in out


def test_run_no_template_returns_1(capsys):
    assert run(Namespace(template=None, list_templates=False, force=False)) == 1
    assert "error: no template given" in capsys.readouterr().err


def test_run_unknown_template_returns_1(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("PWD", str(tmp_path))
    assert run(Namespace(template="nosuch", list_templates=False, force=False)) == 1
    assert "error: unknown template" in capsys.readouterr().err


def test_run_success_copies_into_pwd(monkeypatch, tmp_path):
    monkeypatch.setenv("PWD", str(tmp_path))
    out = run(Namespace(template="static-workflow", list_templates=False, force=False))
    assert isinstance(out, str)
    assert "generated 'static-workflow': 1 file(s)" in out
    assert (tmp_path / ".github" / "workflows" / "deploy.yml").is_file()


def test_run_refuses_overwrite_without_force(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("PWD", str(tmp_path))
    assert (
        run(Namespace(template="static-workflow", list_templates=False, force=False))
        != 1
    )
    capsys.readouterr()
    assert (
        run(Namespace(template="static-workflow", list_templates=False, force=False))
        == 1
    )
    assert "refusing to overwrite" in capsys.readouterr().err


def test_run_force_overwrites(monkeypatch, tmp_path):
    monkeypatch.setenv("PWD", str(tmp_path))
    run(Namespace(template="static-workflow", list_templates=False, force=False))
    out = run(Namespace(template="static-workflow", list_templates=False, force=True))
    assert isinstance(out, str)
    assert "generated 'static-workflow'" in out


def test_run_defaults_to_cwd_without_pwd(monkeypatch, tmp_path):
    monkeypatch.delenv("PWD", raising=False)
    monkeypatch.chdir(tmp_path)
    out = run(Namespace(template="static-workflow", list_templates=False, force=False))
    assert isinstance(out, str)
    assert (tmp_path / ".github" / "workflows" / "deploy.yml").is_file()
    assert str(tmp_path.resolve()) in out or str(tmp_path) in out


def test_run_empty_template_treated_as_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("PWD", str(tmp_path))
    assert run(Namespace(template="", list_templates=False, force=False)) == 1
    assert "error: no template given" in capsys.readouterr().err


def test_run_returns_pathlib_dest_str(monkeypatch, tmp_path):
    monkeypatch.delenv("PWD", raising=False)
    monkeypatch.chdir(tmp_path)
    out = run(Namespace(template="static-workflow", list_templates=False, force=True))
    assert isinstance(out, str)
    assert Path(tmp_path / ".github" / "workflows" / "deploy.yml").is_file()
