"""Ask AI any question."""

from __future__ import annotations

import argparse
import sys

from common.prompt import PromptClient

HELP = "Ask AI any question, answered in one easy sentence."


def build_system_prompt(sentences: int = 1) -> str:
    """Return the single-sentence system prompt."""
    if sentences == 1:
        count_rule = "Answer in exactly 1 SINGLE sentence."
    else:
        count_rule = f"Answer in at most {sentences} sentences."
    return (
        f"{count_rule} Use simple, easy-to-understand language. "
        "No intro, no bullets, no code fences, no extra sentences."
    )


def build_question(parts: list[str] | tuple[str, ...]) -> str:
    """Join question word parts into a single string."""
    return " ".join(p for p in (parts or []) if p).strip()


def _valid_sentences(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--sentences must be an integer >= 1, got {value!r}"
        )
    if n < 1:
        raise argparse.ArgumentTypeError("--sentences must be >= 1")
    return n


def register(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help=HELP)
    parser.add_argument(
        "question",
        nargs="+",
        help="Question to ask the AI (one or more words).",
    )
    parser.add_argument(
        "-n",
        type=_valid_sentences,
        default=1,
        help="Number of sentences in the answer (default: 1).",
    )
    parser.set_defaults(_func=run)


def run(args) -> str | int:
    """Entrypoint called by main.py. Must return str, int, or None."""
    question = build_question(getattr(args, "question", []))
    if not question:
        print("error: no question given", file=sys.stderr)
        return 1
    sentences = getattr(args, "sentences", 1)
    system = build_system_prompt(sentences)
    try:
        client = PromptClient()
        answer = client.ask(question, system=system)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not answer:
        print("error: model did not return an answer", file=sys.stderr)
        return 1
    return answer
