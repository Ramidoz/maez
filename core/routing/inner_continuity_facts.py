from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from urllib.parse import quote


def inner_continuity_facts_enabled() -> bool:
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_INNER_CONTINUITY_FACTS")


def inner_continuity_prompt_block(
    *,
    dream_db_path: Path | str | None = None,
    wonderings_db_path: Path | str | None = None,
    now: datetime | None = None,
) -> str:
    if not inner_continuity_facts_enabled():
        return ""
    return build_inner_continuity_facts(
        dream_db_path=dream_db_path,
        wonderings_db_path=wonderings_db_path,
        now=now,
    )


def build_inner_continuity_facts(
    *,
    dream_db_path: Path | str | None = None,
    wonderings_db_path: Path | str | None = None,
    now: datetime | None = None,
) -> str:
    now_utc = _utc_now(now)
    dream_line = _dream_line(dream_db_path, now_utc)
    wondering_line = _wondering_line(wonderings_db_path, now_utc)
    lines = [line for line in (dream_line, wondering_line) if line]
    if not lines:
        return ""
    return "INNER CONTINUITY FACTS\n" + "\n".join(f"- {line}" for line in lines)


def _utc_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _readonly_conn(path: Path | str | None):
    if path is None:
        return None
    db_path = Path(path)
    if not db_path.exists():
        return None
    uri = "file:" + quote(str(db_path.resolve()), safe="/:") + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _dream_db_path() -> Path | None:
    try:
        from core.evolution.dream_state import DEFAULT_DB_PATH

        return Path(DEFAULT_DB_PATH)
    except Exception:
        return None


def _wonderings_db_path() -> Path | None:
    try:
        from core import paths

        return paths.wonderings_db()
    except Exception:
        return None


def _dream_line(path: Path | str | None, now: datetime) -> str:
    db_path = path if path is not None else _dream_db_path()
    try:
        conn = _readonly_conn(db_path)
        if conn is None:
            return ""
        with closing(conn):
            rows = conn.execute(
                "SELECT id, created_at FROM dream_proposals "
                "WHERE status = 'pending' "
                "ORDER BY created_at ASC, id ASC"
            ).fetchall()
    except sqlite3.Error:
        return ""
    if not rows:
        return ""
    aged = [
        (int(row[0]), max(0.0, now.timestamp() - float(row[1])))
        for row in rows
    ]
    ids = ", ".join(f"#{dream_id} age {_age_label(age)}" for dream_id, age in aged)
    oldest = _age_label(max(age for _dream_id, age in aged))
    count = len(aged)
    noun = "proposal" if count == 1 else "proposals"
    return f"dream {noun}: {count} pending ({ids}); oldest {oldest}."


def _wondering_line(path: Path | str | None, now: datetime) -> str:
    db_path = path if path is not None else _wonderings_db_path()
    try:
        from core.evolution.wonderings import _QUARANTINED_SOURCES

        quarantined = tuple(sorted(str(source) for source in _QUARANTINED_SOURCES))
    except Exception:
        quarantined = ("digestion",)
    try:
        conn = _readonly_conn(db_path)
        if conn is None:
            return ""
        placeholders = ",".join("?" for _ in quarantined)
        source_clause = (
            f"AND COALESCE(source, '') NOT IN ({placeholders})"
            if quarantined
            else ""
        )
        with closing(conn):
            rows = conn.execute(
                "SELECT created_at FROM wonderings "
                "WHERE status IN ('open', 'active') "
                f"{source_clause} "
                "ORDER BY created_at ASC",
                quarantined,
            ).fetchall()
    except sqlite3.Error:
        return ""
    if not rows:
        return ""
    ages = [max(0.0, now.timestamp() - float(row[0])) for row in rows]
    count = len(ages)
    return f"open wonderings: {count}; oldest {_age_label(max(ages))}."


def _age_label(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    days = hours // 24
    remaining_hours = hours % 24
    if remaining_hours:
        return f"{days}d {remaining_hours}h"
    return f"{days}d"
