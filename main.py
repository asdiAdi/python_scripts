"""Dispatcher for python-scripts.

Usage:
    python main.py --help
    python main.py --list
    python main.py --where hello-world
    python main.py hello-world [--name NAME]
    python main.py <command> [args...]

Adding a new script:
    1. Create scripts/<snake_name>/cli.py
    2. Implement register(subparsers, command) and run(args)
       - folder <snake_name> is the single source of truth;
         command is <snake_name> with _ -> - (e.g. hello_world -> hello-world).
    3. See scripts/hello_world/cli.py as a template.
    4. No changes to this file are needed.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


class CleanParser(argparse.ArgumentParser):
    """ArgumentParser that prints only `error: ...` with no usage/prog prefix."""

    def error(self, message: str) -> NoReturn:
        if "invalid choice" in message:
            # message looks like: argument <command>: invalid choice: 'foo' (choose from ...)
            attempted = message.split("'", 2)
            name = attempted[1] if len(attempted) >= 3 else message
            print(f"error: unknown command '{name}'", file=sys.stderr)
        else:
            cleaned = message
            # Strip a leading "prog: " if argparse added one.
            if ": " in cleaned:
                cleaned = cleaned.split(": ", 1)[1]
            print(f"error: {cleaned}", file=sys.stderr)
        self.exit(2)


def folder_to_command(folder: str) -> str:
    """Convert a folder name like hello_world to a CLI command like hello-world."""
    return folder.replace("_", "-")


def discover_modules() -> list[tuple[str, Path]]:
    """Find all scripts/*/cli.py candidates. Returns [(command, path), ...] sorted."""
    if not SCRIPTS_DIR.is_dir():
        return []
    found: list[tuple[str, Path]] = []
    for child in sorted(SCRIPTS_DIR.iterdir()):
        cli_file = child / "cli.py"
        if (
            child.is_dir()
            and not child.name.startswith(("_", "."))
            and cli_file.is_file()
        ):
            found.append((folder_to_command(child.name), cli_file))
    return found


def load_module(command: str, path: Path):
    """Load a cli.py file as a module. Module name is namespaced to avoid collisions."""
    mod_name = f"scripts_{command.replace('-', '_')}_cli"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def build_parser(
    modules: dict[str, object] | None = None,
    paths: dict[str, Path] | None = None,
) -> argparse.ArgumentParser:
    parser = CleanParser(
        prog="main.py",
        description="Collection of Python scripts. Pick a subcommand to run.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available script commands with file paths and exit.",
    )
    parser.add_argument(
        "--where",
        metavar="COMMAND",
        default=None,
        help="Print the cli.py path for COMMAND and exit.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    loaded: dict[str, object] = {}
    loaded_paths: dict[str, Path] = {}
    for command, path in discover_modules():
        try:
            mod = load_module(command, path)
        except Exception as exc:  # noqa: BLE001 - keep CLI alive, report culprit
            print(
                f"warning: skipping '{command}' ({path}): {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue
        if not hasattr(mod, "register") or not hasattr(mod, "run"):
            print(
                f"warning: skipping '{command}' ({path}): "
                f"cli.py must define register(subparsers, command) and run(args)",
                file=sys.stderr,
            )
            continue
        mod.register(subparsers, command)
        loaded[command] = mod
        loaded_paths[command] = path

    if modules is not None:
        modules.update(loaded)
    if paths is not None:
        paths.update(loaded_paths)
    return parser


def main(argv: list[str] | None = None) -> int:
    loaded: dict[str, object] = {}
    loaded_paths: dict[str, Path] = {}
    parser = build_parser(loaded, loaded_paths)

    args = parser.parse_args(argv)

    if args.where:
        wanted = args.where
        match = loaded_paths.get(wanted) or next(
            (p for c, p in discover_modules() if c == wanted), None
        )
        if match is not None:
            print(match)
            return 0
        print(f"error: unknown command '{wanted}'", file=sys.stderr)
        return 1

    if args.list:
        if not loaded_paths:
            print("No scripts found in scripts/*/cli.py")
        else:
            print("Available commands:")
            for command in sorted(loaded_paths):
                try:
                    rel = loaded_paths[command].relative_to(REPO_ROOT)
                except ValueError:
                    rel = loaded_paths[command]
                print(f"  {command:<20} ({rel})")
        return 0

    if not args.command:
        parser.print_help()
        print("error: no command given", file=sys.stderr)
        return 2

    func = getattr(args, "_func", None)
    if func is None:
        # Script registered a parser but forgot set_defaults(_func=...).
        mod = loaded.get(args.command)
        func = getattr(mod, "run", None) if mod is not None else None
    if func is None:
        print(
            f"error: command '{args.command}' has no run() entrypoint", file=sys.stderr
        )
        return 1

    result = func(args)
    # Convention: run() may return str (print it), int (exit code), or None.
    if isinstance(result, int):
        return result
    if isinstance(result, str):
        print(result)
        return 0
    if result is not None:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
