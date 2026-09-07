# generate

Copy a bundled template into the current directory.

## Purpose

Copies a template from `scripts/generate/files/` (file or directory) into the destination directory. Use `--list` to discover template names; existing files are never overwritten unless `--force` is given.

## Usage

```bash
uv run python main.py generate template
uv run python main.py generate --list
uv run python main.py generate --help
```

## Args

| Arg | Default | Description |
| ----- | --------- | ------------- |
| `template` | None (required unless `--list`) | Template to generate (file or directory name under `files/`). |
| `-l, -list, --list` | off | List available templates and exit. |
| `-f, -force, --force` | off | Overwrite existing files. |
