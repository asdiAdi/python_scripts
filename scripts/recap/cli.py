"""Recap opencode activity.

Queries opencode.db text parts and asks
the AI to summarize in bullet points only.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from common.prompt import PromptClient

HELP = "Summarize opencode.db activity in bullets."
MANILA = ZoneInfo("Asia/Manila")
ENV_DB_PATH = "OPENCODE_DB_PATH"
DEFAULT_DB = "~/.local/share/opencode/opencode.db"

DAY_START_HOUR = 6
MAX_PROMPT_CHARS = 30000


def _month_number(token: str) -> int | None:
    """Month number for a full/abbreviated English month name, else None."""
    key = token.strip().lower().rstrip(".")
    if key == "sept":  # common variant; calendar abbr is "Sep"
        return 9
    for i in range(1, 13):
        if key in (calendar.month_name[i].lower(), calendar.month_abbr[i].lower()):
            return i
    return None


def _month_window(year: int, month: int) -> tuple[int, int, str]:
    """Whole-month window: 1st 06:00 Manila -> 1st 06:00 of next month."""
    start = datetime(year, month, 1, DAY_START_HOUR, tzinfo=MANILA)
    if month == 12:
        end = datetime(year + 1, 1, 1, DAY_START_HOUR, tzinfo=MANILA)
    else:
        end = datetime(year, month + 1, 1, DAY_START_HOUR, tzinfo=MANILA)
    return (
        int(start.timestamp() * 1000),
        int(end.timestamp() * 1000),
        f"{year}-{month:02d}",
    )


def _parse_month_only(spec: str, now: datetime) -> tuple[int, int, str] | None:
    """Whole-month window for month-only specs, else None."""
    tokens = re.sub(r"[,/\\-]", " ", spec.strip().lower()).split()
    if not tokens:
        return None
    # Numeric YYYY-MM form (checked before token split rejects the month part).
    m = re.fullmatch(r"(\d{4})[/\\-](\d{1,2})", spec.strip())
    if m and 1 <= int(m.group(2)) <= 12:
        return _month_window(int(m.group(1)), int(m.group(2)))
    year: int | None = None
    month: int | None = None
    rest: list[str] = []
    for tok in tokens:
        if re.fullmatch(r"\d{4}", tok):
            year = int(tok)
            continue
        num = _month_number(tok)
        if num is not None:
            month = num
        else:
            rest.append(tok)
    if rest:
        return None
    if month is None:
        return None
    if year is None:
        year = now.year
    return _month_window(year, month)


def resolve_db_path(explicit: str | None) -> Path:
    """Return the opencode.db path. Reads env only as fallback."""
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get(ENV_DB_PATH, "").strip()
    if env:
        return Path(env).expanduser()
    return Path(DEFAULT_DB).expanduser()


def _day_window(day: datetime) -> tuple[datetime, datetime]:
    """Snap a Manila-aware datetime to its 6am-anchored day window."""
    start = day.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _today_6am(now: datetime) -> datetime:
    """Most recent 6am at or before now (ongoing 6am-anchored day start)."""
    candidate = now.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    if now < candidate:
        candidate -= timedelta(days=1)
    return candidate


def parse_date_window(spec: str, now: datetime | None = None) -> tuple[int, int, str]:
    """Parse a date spec into (start_ms, end_ms, label).

    start_ms inclusive, end_ms exclusive. All boundaries are 6am Manila.
    """
    from dateutil import parser as date_parser

    now = now or datetime.now(MANILA)
    if now.tzinfo is None:
        now = now.replace(tzinfo=MANILA)
    else:
        now = now.astimezone(MANILA)

    key = (spec or "").strip().lower().replace("_", "-")
    key = re.sub(r"\s+", "-", key).strip("-")

    if key in ("today",):
        start = _today_6am(now)
        end = start + timedelta(days=1)
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000), "today"
    if key in ("yesterday",):
        start = _today_6am(now) - timedelta(days=1)
        end = start + timedelta(days=1)
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000), "yesterday"
    if key in ("last-week", "lastweek", "past-week"):
        today_start = _today_6am(now)
        # Monday-start calendar week containing the ongoing day.
        ongoing_day = today_start.date()
        monday = ongoing_day - timedelta(days=ongoing_day.weekday())
        this_mon_6am = datetime(
            monday.year, monday.month, monday.day, DAY_START_HOUR, tzinfo=MANILA
        )
        start = this_mon_6am - timedelta(days=7)
        end = this_mon_6am
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000), "last-week"
    if key in ("last-month", "lastmonth", "past-month"):
        this_month_start = datetime(
            now.year, now.month, 1, DAY_START_HOUR, tzinfo=MANILA
        )
        if now < this_month_start:
            # 1st 00:00-06:00 still belongs to the previous month window.
            this_month_start = _prev_month_start(this_month_start)
        start = _prev_month_start(this_month_start)
        end = this_month_start
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000), "last-month"
    if key in ("last-year", "lastyear", "past-year"):
        this_year_start = datetime(now.year, 1, 1, DAY_START_HOUR, tzinfo=MANILA)
        if now < this_year_start:
            # Jan 1st 00:00-06:00 still belongs to the previous year window.
            this_year_start = this_year_start.replace(year=this_year_start.year - 1)
        start = this_year_start.replace(year=this_year_start.year - 1)
        end = this_year_start
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000), "last-year"

    # Month-only specs ("january", "january 2023", "2023-01"): whole month.
    month_window = _parse_month_only(spec, now)
    if month_window is not None:
        return month_window

    # Bare unix timestamp (seconds or ms): snap to its 6am-anchored day.
    if re.fullmatch(r"-?\d+", key):
        ts = int(key)
        if ts > 10_000_000_000:  # already milliseconds
            dt = datetime.fromtimestamp(ts / 1000, MANILA)
        else:
            dt = datetime.fromtimestamp(ts, MANILA)
        start, end = _day_window(dt)
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000), key

    try:
        dt = date_parser.parse(spec.strip(), default=now)
    except (ValueError, OverflowError) as exc:
        raise argparse.ArgumentTypeError(
            f"could not parse date {spec!r} (try YYYY-MM-DD, 'Jan 2', 'yesterday')"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MANILA)
    else:
        dt = dt.astimezone(MANILA)
    start, end = _day_window(dt)
    label = start.date().isoformat()
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000), label


def _prev_month_start(month_start: datetime) -> datetime:
    """Return 1st 6am Manila of the month before month_start's month."""
    first_of_month = month_start.replace(day=1)
    prev_month_last_day = first_of_month - timedelta(days=1)
    return datetime(
        prev_month_last_day.year,
        prev_month_last_day.month,
        1,
        DAY_START_HOUR,
        tzinfo=MANILA,
    )


def fetch_parts(db_path: Path, start_ms: int, end_ms: int) -> list[dict]:
    """Query text parts in [start_ms, end_ms). Pure I/O, parameterized."""
    if not db_path.is_file():
        raise RuntimeError(f"error: database not found: {db_path}")
    uri = f"file:{db_path}?immutable=1"
    try:
        con = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise RuntimeError(f"error: could not open database: {exc}") from exc
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT s.directory AS directory, p.data AS data
            FROM part p
            LEFT JOIN message m ON m.id = p.message_id
            LEFT JOIN session s ON s.id = m.session_id
            WHERE p.data->>'type' = 'text'
              AND p.data->>'metadata' IS NULL
              AND p.time_created >= ? AND p.time_created < ?
            ORDER BY p.time_created ASC
            """,
            (start_ms, end_ms),
        )
        rows = cur.fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(f"error: query failed: {exc}") from exc
    finally:
        con.close()

    grouped: dict[str, list[dict]] = {}
    for directory, data in rows:
        try:
            item = json.loads(data) if isinstance(data, str) else data
        except json.JSONDecodeError, TypeError:
            continue
        if not isinstance(item, dict):
            continue
        folder = Path(directory).name if directory else "(unknown)"
        grouped.setdefault(folder, []).append(
            {"type": str(item.get("type", "text")), "text": str(item.get("text", ""))}
        )
    return [{"name": name, "parts": parts} for name, parts in sorted(grouped.items())]


def build_system_prompt(max_bullets: int | None) -> str:
    """Return the bullets-only system prompt."""
    if max_bullets is None:
        count_rule = "Output as many bullet point(s) as needed to cover everything."
    else:
        count_rule = (
            f"Output at most {max_bullets} bullet point(s); "
            "fewer is fine if there is less to say."
        )
    return (
        "You summarize a developer's coding assistant activity. Rules:\n"
        f"{count_rule}\n"
        "Bullet points only: each line starts with '- '. No intro, no outro, "
        "no numbering, no code fences, no explanations outside bullets.\n"
        "Make each bullet point as short and non-dev readable as possible\n"
        "Sort them by the most important bullet point"
    )


def build_user_prompt(groups: list[dict], label: str) -> str:
    """Return the user prompt carrying the DB rows.

    Truncates to MAX_PROMPT_CHARS so huge windows don't blow model limits.
    """
    lines = [f"Summarize this opencode activity for {label}.", ""]
    for group in groups:
        lines.append(f"## {group['name']}")
        for part in group["parts"]:
            text = part.get("text", "").strip()
            if text:
                lines.append(text)
        lines.append("")
    full = "\n".join(lines).strip()
    if len(full) > MAX_PROMPT_CHARS:
        full = (
            full[:MAX_PROMPT_CHARS]
            + "\n[truncated: activity exceeded 30000 characters]"
        )
    return full


def clean_bullets(raw: str) -> str:
    """Normalize model output to dash bullets."""
    out: list[str] = []
    for line in (raw or "").splitlines():
        s = line.strip()
        if not s or s.startswith("```"):
            continue
        s = re.sub(r"^[\d]+[.)]\s+", "", s)
        s = re.sub(r"^[*+]\s+", "- ", s)
        if not s.startswith("- "):
            s = f"- {s.lstrip('- ').strip()}"
        out.append(s)
    return "\n".join(out).strip()


def _valid_bullets(value: str) -> int | None:
    if isinstance(value, str) and value.strip().lower() == "all":
        return None
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--bullets must be 1-20 or 'all', got {value!r}"
        )
    if n < 1 or n > 20:
        raise argparse.ArgumentTypeError("--bullets must be between 1 and 20 or 'all'")
    return n


def register(subparsers, command: str) -> None:
    parser = subparsers.add_parser(command, help=HELP)
    parser.add_argument(
        "date",
        nargs="*",
        help="today (default) | yesterday | last-week | last-month | last-year | january | 'january 2023' | YYYY-MM-DD | 'Jan 2' | unix timestamp. Months cover the whole month; exact dates cover 1 day.",
    )
    parser.add_argument(
        "-b",
        "--bullets",
        type=_valid_bullets,
        default=5,
        help="Maximum bullets (1-20, default: 5, fewer is OK) or 'all' for uncapped output.",
    )
    parser.add_argument(
        "--db",
        default=None,
        help=f"Path to opencode.db (default: ${ENV_DB_PATH} or {DEFAULT_DB}).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override OpenRouter model (default: $OPENROUTER_MODEL).",
    )
    parser.set_defaults(_func=run)


def run(args) -> str | int | None:
    """Entrypoint called by main.py. Must return str, int, or None."""
    spec = " ".join(getattr(args, "date", []) or []).strip()
    if not spec:
        spec = "today"
    max_bullets = getattr(args, "bullets", 5)
    unlimited = max_bullets is None
    db_path = resolve_db_path(getattr(args, "db", None))
    model = getattr(args, "model", None)

    try:
        start_ms, end_ms, label = parse_date_window(spec)
    except argparse.ArgumentTypeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        groups = fetch_parts(db_path, start_ms, end_ms)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not groups or not any(g["parts"] for g in groups):
        return f"no activity found for {label}"

    system = build_system_prompt(None if unlimited else max_bullets)
    user_prompt = build_user_prompt(groups, label)

    try:
        client = PromptClient()
        raw = client.ask(user_prompt, system=system, model=model)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    cleaned = clean_bullets(raw)
    if not cleaned:
        print("error: model did not return usable bullets", file=sys.stderr)
        if raw.strip():
            print(raw.strip(), file=sys.stderr)
        return 1
    # Enforce the max on our side (line-based, safe: never merges bullets).
    # Skipped with -b all: the AI decides how many bullets to output.
    if unlimited:
        return cleaned
    lines = cleaned.splitlines()[:max_bullets]
    return "\n".join(lines)
