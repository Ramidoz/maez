"""Private sqlite store for A2 continuity-fingerprint probe samples."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid
from typing import Any


def _default_db_path() -> Path:
    try:
        from core.infra import paths

        return paths.memory_dir() / "continuity_fingerprint.db"
    except Exception:
        return (
            Path(__file__).resolve().parents[2]
            / "memory"
            / "continuity_fingerprint.db"
        )


_SCHEMA = """
CREATE TABLE IF NOT EXISTS probe_runs (
    run_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    era TEXT NOT NULL,
    self_card_applied INTEGER NOT NULL,
    base_model TEXT NOT NULL,
    soul_base_hash TEXT,
    soul_local_hash TEXT,
    frame_text_hash TEXT NOT NULL,
    policy_hash TEXT NOT NULL,
    embedder_id TEXT NOT NULL,
    battery_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS probe_answers (
    run_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    dist_short REAL DEFAULT NULL,
    dist_mid REAL DEFAULT NULL,
    dist_long REAL DEFAULT NULL,
    PRIMARY KEY (run_id, question_id),
    FOREIGN KEY (run_id) REFERENCES probe_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_probe_runs_ts ON probe_runs(ts);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ContinuityStore:
    """A2-private store for probe answers and derived distances.

    Stores answer text and scalar distances only. Embedding vectors are never
    persisted.
    """

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con  # sqlite-raw-ok: private factory; every caller wraps in contextlib.closing()

    def _initialize(self) -> None:
        with closing(self._connect()) as con, con:
            con.executescript(_SCHEMA)

    def record_run(
        self,
        *,
        snapshot: dict[str, Any],
        embedder_id: str,
        battery_version: str,
        answers: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        run_id: str | None = None,
        ts: str | None = None,
    ) -> str:
        run_id = run_id or uuid.uuid4().hex
        ts = ts or _now_iso()
        era = f"{battery_version}|{embedder_id}"
        with closing(self._connect()) as con, con:
            con.execute(
                """
                INSERT INTO probe_runs (
                    run_id, ts, era, self_card_applied, base_model,
                    soul_base_hash, soul_local_hash, frame_text_hash,
                    policy_hash, embedder_id, battery_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    ts,
                    era,
                    1 if snapshot.get("self_card_applied") else 0,
                    str(snapshot.get("base_model") or ""),
                    snapshot.get("soul_base_hash"),
                    snapshot.get("soul_local_hash"),
                    str(snapshot.get("frame_text_hash") or ""),
                    str(snapshot.get("policy_hash") or ""),
                    embedder_id,
                    battery_version,
                ),
            )
            con.executemany(
                """
                INSERT INTO probe_answers (
                    run_id, question_id, answer_text,
                    dist_short, dist_mid, dist_long
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        str(answer["question_id"]),
                        str(answer["answer_text"]),
                        answer.get("dist_short"),
                        answer.get("dist_mid"),
                        answer.get("dist_long"),
                    )
                    for answer in answers
                ],
            )
        return run_id

    def list_runs(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT * FROM probe_runs ORDER BY ts ASC, run_id ASC"
            ).fetchall()
        return [self._run_row_to_dict(row) for row in rows]

    def answers_for(self, run_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as con:
            rows = con.execute(
                """
                SELECT * FROM probe_answers
                WHERE run_id = ?
                ORDER BY question_id ASC
                """,
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _run_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        out = dict(row)
        out["self_card_applied"] = bool(out["self_card_applied"])
        return out
