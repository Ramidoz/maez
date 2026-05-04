# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Trace writer — daily JSONL append, never raises.

One trace per line. File path is ``logs/traces/YYYY-MM-DD.jsonl``,
chosen by UTC date so a long-running daemon doesn't write across two
local-day boundaries in one file. Append-only. Per-line atomic in the
filesystem sense (open-append-close-flush per write); concurrent
writes from the same daemon are serialised by a process-local lock
(no cross-process coordination needed since exactly one daemon writes
to this directory in production).

Failure contract:

- Filesystem error, permission error, JSON encoding error → the writer
  logs a warning and returns False. The caller (``handle_message``)
  must NEVER let trace failure break synthesis. A missed trace is
  acceptable; a missed reply to the owner is not.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.turn_traces.trace_schema import Trace

logger = logging.getLogger("maez.turn_traces.trace_writer")


class TraceWriter:
    """JSONL trace writer. Thread-safe; never raises on caller path."""

    def __init__(self, base_dir: "str | Path"):
        self._base = Path(base_dir)
        self._lock = threading.Lock()

    def _path_for_today(self) -> Path:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._base / f"{date}.jsonl"

    def write(self, trace: "Trace | dict[str, Any]") -> bool:
        """Serialize ``trace`` to one JSONL line. Returns True on
        success, False on any failure. Logs a warning on failure but
        does not propagate the exception."""
        try:
            line = (
                trace.to_jsonl_line()
                if isinstance(trace, Trace)
                else json.dumps(trace, ensure_ascii=False, separators=(",", ":"))
            )
        except (TypeError, ValueError) as exc:
            logger.warning("trace serialization failed (skipping): %s", exc)
            return False

        path = self._path_for_today()
        try:
            with self._lock:
                # Create parent directory lazily so a fresh install
                # (or a wiped logs/ dir) doesn't crash the first call.
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as f:
                    f.write(line)
                    f.write("\n")
            return True
        except OSError as exc:
            logger.warning("trace write failed (skipping): %s", exc)
            return False


_default_writer_singleton: "TraceWriter | None" = None


def default_writer() -> TraceWriter:
    """Process-wide default writer, anchored at ``logs/traces/``
    relative to MAEZ_HOME. Constructed lazily so tests can monkey-patch
    or install their own writer without touching production paths."""
    global _default_writer_singleton
    if _default_writer_singleton is None:
        try:
            from core.paths import home as _home

            base = Path(_home()) / "logs" / "traces"
        except Exception:
            base = Path(__file__).resolve().parents[2] / "logs" / "traces"
        _default_writer_singleton = TraceWriter(base)
    return _default_writer_singleton
