# hello-world

Sample script, copy this folder as a template for new scripts.

## Purpose

Prints `Hello World`.

## Usage

```bash
uv run python main.py hello-world
uv run python main.py hello-world --name Bob
```

## Args

| Arg | Default | Description |
|-----|---------|-------------|
| `--name` | `World` | Who to greet |

## Example

```text
$ uv run python main.py hello-world --name Alice
Hello Alice
```
