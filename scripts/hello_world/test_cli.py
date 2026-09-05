"""Tests for the hello_world sample script."""

from argparse import ArgumentParser, Namespace

from scripts.hello_world.cli import build_message, register, run


def test_register_uses_folder_derived_command():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "hello-world")
    args = parser.parse_args(["hello-world", "--name", "Bob"])
    assert args.command == "hello-world"
    assert run(args) == "Hello Bob"


def test_default_returns_hello_world():
    assert run(Namespace(name="World")) == "Hello World"


def test_build_message_default():
    assert build_message() == "Hello World"


def test_build_message_with_name():
    assert build_message("Bob") == "Hello Bob"


def test_run_with_custom_name():
    assert run(Namespace(name="Alice")) == "Hello Alice"
