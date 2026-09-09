# recap

Summarize opencode.db activity in bullets.

## Purpose

Queries `opencode.db` text parts for a date window and asks the model for bullet points only. Day boundaries are 6am Manila. Month specs cover the whole month; exact dates cover one day.

## Usage

```bash
uv run python main.py recap
uv run python main.py recap yesterday
uv run python main.py recap last-week -b 3
uv run python main.py recap "january 2023" --bullets all
uv run python main.py recap --help
```

## Args

| Arg | Default | Description |
|-----|---------|-------------|
| `date` | `today` | `today` \| `yesterday` \| `last-week` \| `last-month` \| `last-year` \| `january` \| `'january 2023'` \| `YYYY-MM-DD` \| `'Jan 2'` \| unix timestamp. Months cover the whole month; exact dates cover 1 day. |
| `-b, --bullets` | `5` | Maximum bullets (1-20, fewer is OK) or `'all'` for uncapped output. |

DB path and model come from `~/.config/ai/config.toml` (`recap.db_path`, `openrouter.model`).

## Example

```text
$ uv run python main.py recap yesterday -b 2
- Fixed login retry handling
- Updated recap README
```

Empty window returns `no activity found for <label>`. Failures print `error: ...` to stderr with exit `1` (missing DB, bad date, model error). Requires `openrouter.api_key` in config.
