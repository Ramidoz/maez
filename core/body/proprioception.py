"""Proprioception store: body vitals as sensed aggregates, not narration."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from statistics import median


def default_proprioception_db_path() -> Path:
    return Path("/home/rohit/maez/memory/proprioception.db")


class ProprioceptionStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS samples (
                    ts REAL NOT NULL,
                    cpu_pct REAL NOT NULL,
                    ram_pct REAL NOT NULL,
                    gpu_pct REAL NOT NULL,
                    gpu_temp_c REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_proprioception_ts ON samples(ts)"
            )

    def record(
        self,
        *,
        ts: float,
        cpu_pct: float,
        ram_pct: float,
        gpu_pct: float,
        gpu_temp_c: float,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO samples (ts, cpu_pct, ram_pct, gpu_pct, gpu_temp_c)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    float(ts),
                    float(cpu_pct),
                    float(ram_pct),
                    float(gpu_pct),
                    float(gpu_temp_c),
                ),
            )

    def aggregate(self, *, since_ts: float) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT cpu_pct, ram_pct, gpu_pct, gpu_temp_c
                FROM samples
                WHERE ts >= ?
                ORDER BY ts ASC
                """,
                (float(since_ts),),
            ).fetchall()

        fields = ("cpu_pct", "ram_pct", "gpu_pct", "gpu_temp_c")
        if not rows:
            return {"samples": 0, **{field: None for field in fields}}

        columns = list(zip(*rows, strict=True))
        out = {"samples": len(rows)}
        for field, values in zip(fields, columns, strict=True):
            vals = [float(v) for v in values]
            out[field] = {
                "min": min(vals),
                "median": float(median(vals)),
                "max": max(vals),
            }
        return out
