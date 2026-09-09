# config

Manage the user-level `ai` configuration file.

## Purpose

Reads/writes `~/.config/ai/config.toml`.
Per-key precedence: config file > default.

## Usage

```bash
ai config init          # write starter ~/.config/ai/config.toml (0600)
ai config init --force  # overwrite existing file
ai config show          # resolved values, secrets redacted
ai config path          # print file location
```

## Example

```text
$ ai config init
wrote: /home/user/.config/ai/config.toml
$ ai config show
file: /home/user/.config/ai/config.toml
openrouter.api_key = sk-a…mnop (set) [file]
openrouter.model = minimax/minimax-m3:free [default]
```
