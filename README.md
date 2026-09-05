# python-scripts

A collection of small Python scripts, each self-contained with its own tests and docs.

## Quickstart

```bash
uv sync --group dev
uv run python main.py --list
uv run python main.py hello-world --name Alice
# → Hello Alice
```

## Add a script

```bash
cp -r scripts/hello_world scripts/my_tool
# edit scripts/my_tool/cli.py, test_cli.py, README.md
uv run pytest scripts/my_tool/test_cli.py -v
```

## Tests

```bash
uv run pytest -v            # everything
uv run pytest scripts/hello_world/test_cli.py -v
uv run pytest tests/test_main.py -v
```

## Project map

| Path | What |
| ------ | ------ |
| `main.py` | Dispatcher |
| `common/` | Shared helpers |
| `scripts/` | Python Scripts |
| `tests/` | Dispatcher tests |
