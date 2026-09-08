"""Tests for the ask script."""

from argparse import ArgumentParser, Namespace
from unittest.mock import patch

import pytest

from scripts.ask.cli import build_question, build_system_prompt, register, run
import scripts.ask.cli as cli_mod


def test_build_system_prompt_single_sentence():
    s = build_system_prompt(1)
    assert "exactly 1 SINGLE sentence" in s
    assert "No intro" in s


def test_build_system_prompt_multi_sentence():
    s = build_system_prompt(3)
    assert "at most 3 sentences" in s
    assert "No intro" in s


def test_build_question_joins_parts():
    assert build_question(["what", "is", "up?"]) == "what is up?"
    assert build_question(("hello", "world")) == "hello world"


def test_build_question_strips_empty():
    assert build_question([]) == ""
    assert build_question(["  ", "hi", ""]) == "hi"


def test_register_uses_folder_derived_command():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "ask")
    args = parser.parse_args(["ask", "what", "is", "up?"])
    assert args.command == "ask"
    assert args.question == ["what", "is", "up?"]
    assert args.n == 1
    assert args._func is run


def test_register_parses_sentences_flag():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "ask")
    args = parser.parse_args(["ask", "-n", "3", "hello", "there"])
    assert args.n == 3
    assert args.question == ["hello", "there"]


def test_register_rejects_invalid_sentences():
    parser = ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers, "ask")
    with pytest.raises(SystemExit):
        parser.parse_args(["ask", "-n", "0", "hi"])
    with pytest.raises(SystemExit):
        parser.parse_args(["ask", "-n", "abc", "hi"])


def test_run_success_returns_answer():
    class Good:
        def ask(self, question, system=None):
            assert question == "what is up?"
            assert "at most 2 sentences" in system
            return "The sky is blue."

    with patch.object(cli_mod, "PromptClient", return_value=Good()):
        out = run(Namespace(question=["what", "is", "up?"], sentences=2))
    assert out == "The sky is blue."


def test_run_no_question_returns_1(capsys):
    assert run(Namespace(question=[])) == 1
    assert "error: no question given" in capsys.readouterr().err


def test_run_prompt_failure_returns_1(capsys):
    class Boom:
        def ask(self, *a, **k):
            raise RuntimeError("error: no key")

    with patch.object(cli_mod, "PromptClient", return_value=Boom()):
        assert run(Namespace(question=["hi"], sentences=1)) == 1
    assert "error: no key" in capsys.readouterr().err


def test_run_empty_answer_returns_1(capsys):
    class Empty:
        def ask(self, *a, **k):
            return ""

    with patch.object(cli_mod, "PromptClient", return_value=Empty()):
        assert run(Namespace(question=["hi"], sentences=1)) == 1
    assert "error: model did not return an answer" in capsys.readouterr().err
