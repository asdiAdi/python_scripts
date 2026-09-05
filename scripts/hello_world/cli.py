"""Hello World sample script.

Template for all scripts in this repo. Every script folder must provide:
    - register(subparsers, command): adds an argparse subcommand for `command`
    - run(args): executes the script, returns str | int | None

The folder name is the single source of truth:
    scripts/hello_world/ -> command hello-world (via folder_to_command).

Copy this folder to start a new script:
    cp -r scripts/hello_world scripts/my_tool
"""

from __future__ import annotations

HELP = "Print Hello World (sample script)."


def build_message(name: str = "World") -> str:
    """Return greeting. Pure function so it is trivially testable."""
    return f"Hello {name}" if name != "World" else "Hello World"


def register(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help=HELP)
    parser.add_argument(
        "--name",
        default="World",
        help="Who to greet (default: World).",
    )
    parser.set_defaults(_func=run)


def run(args) -> str:
    """Entrypoint called by main.py. Must return str, int, or None."""
    name = getattr(args, "name", "World")
    return build_message(name)
