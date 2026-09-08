# ask

Ask AI any question, answered in one easy sentence.

## Usage

```bash
uv run python main.py ask "what is the capital of France?"
uv run python main.py ask what is the capital of France?
uv run python main.py ask -n 3 what happened today?
uv run python main.py ask --help
```

## Args

| Arg | Default | Description |
|-----|---------|-------------|
| `question` | (required) | Question to ask the AI (one or more words). |
| `-n` | `1` | Number of sentences in the answer (integer >= 1). |

## Example

```text
$ uv run python main.py ask what is the capital of France?
Paris is the capital of France.
```
