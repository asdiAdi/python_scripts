# commit

AI-assisted git commit: stages all changes, asks the model for Conventional Commit candidates, lets you pick one, and commits it.

## Purpose

Stages all changes (`git add -A`), generates `--num` Conventional Commit candidates from the staged diff via `common.prompt.PromptClient`, prompts to pick one, and runs `git commit -m`. Resets the index (`git reset -q`) on abort or failure. Lockfiles (`uv.lock`, `*.lock`, `package-lock.json`, etc.) are silently excluded from the diff sent to the model.

## Usage

```bash
uv run python main.py commit
uv run python main.py commit -n 5
uv run python main.py commit --num 1
uv run python main.py commit --help
```

## Args

| Arg | Default | Description |
|-----|---------|-------------|
| `-n, --num` | `3` | Number of commit message candidates to generate (1-5). |

## Example

```text
$ uv run python main.py commit -n 2
  1) feat(auth): add login rate limit
  2) fix(auth): handle empty token
Pick 1-2 to commit [n to abort]: 1
[abc1234] feat(auth): add login rate limit
```

Abort with `n` (or empty input, `q`): unstages and returns without committing. Requires `OPENROUTER_API_KEY`; fails with `error: ...` and exit `1` outside a git repo, on clean tree returns `nothing to commit, working tree clean`.
