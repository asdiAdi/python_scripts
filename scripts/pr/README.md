# pr

Generate a GitHub-ready PR title and body from the branch diff vs base.

## Purpose

Diffs the current branch against `--base` (default `main`) via `git diff main...HEAD`, plus `git log`, `git status`, and `git diff --stat`, then asks the model via `common.prompt.PromptClient` for a title + `## Summary` / `## Changes` / `## Testing` / `## Notes` body.

## Usage

```bash
uv run python main.py pr
uv run python main.py pr --base main
uv run python main.py pr --base develop
uv run python main.py pr --help
```

## Args

| Arg      | Default | Description                  |
| -------- | ------- | ---------------------------- |
| `--base` | `main`  | Base branch to diff against. |

## Example

```text
$ uv run python main.py pr
feat(auth): add login rate limit

## Summary
Adds per-user login rate limiting to reduce brute-force risk.

## Changes
- Add rate limiter in auth module
- ...

## Testing
- TODO: add tests

## Notes
None
```
