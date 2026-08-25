#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Reproduce the measurements behind the CHECKPOINT POLICY ruling.

Codex validation (2026-08-24) found the policy's numbers recorded in
canon with nothing committed that re-runs them — "all re-runnable"
exceeded the retained evidence. This script IS the retained evidence.

It answers three questions by execution:
  1. Does SQLite's default autocheckpoint bound the WAL file?
  2. What breaks that bound?
  3. What does an explicit TRUNCATE cost when something else holds the
     write lock?

FILESYSTEM WARNING, learned the hard way: /tmp on this host is tmpfs,
where fsync is nearly free and every latency number is a lie. This
script refuses to run anywhere backed by tmpfs and defaults to /var/tmp
(same NVMe as memory/).

Usage:
  LD_LIBRARY_PATH=vendor/sqlite/lib .venv/bin/python \
      docs/superpowers/witness/wal_bound_probe.py [--commits 20000]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
os.environ.setdefault("MAEZ_TEST_MODE", "1")
os.environ["MAEZ_LEDGER_WRITES"] = "1"

_STAMP = {"taint_labels": ["owner_utterance"], "privacy_access": "public"}


def _refuse_tmpfs(path: str) -> None:
    fstype = subprocess.run(
        ["stat", "-f", "-c", "%T", path], capture_output=True, text=True
    ).stdout.strip()
    if fstype in ("tmpfs", "ramfs"):
        raise SystemExit(
            f"REFUSED: {path} is {fstype}. fsync is free there, so every "
            f"latency number this script prints would be a lie. Use a "
            f"disk-backed directory (--dir)."
        )


def _writer(db: str):
    from core.ledger import migrate
    from core.ledger.writer import LedgerWriter

    migrate.run(db)
    return LedgerWriter(db)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commits", type=int, default=20000)
    ap.add_argument("--dir", default="/var/tmp")
    opts = ap.parse_args()
    _refuse_tmpfs(opts.dir)
    root = tempfile.mkdtemp(prefix="wal_bound_probe_", dir=opts.dir)
    out: dict = {"sqlite": sqlite3.sqlite_version, "commits": opts.commits,
                 "dir": root}

    # --- 1. does the default bound the WAL, with no reader?
    db = os.path.join(root, "plateau.db")
    w = _writer(db)
    wal = db + "-wal"
    marks = []
    for i in range(opts.commits):
        w.write_turn("user_message", f"t{i} " + "x" * 200,
                     surface="probe", **_STAMP)
        if i and i % max(1, opts.commits // 5) == 0:
            marks.append([i, os.path.getsize(wal)])
    marks.append([opts.commits, os.path.getsize(wal)])
    from core.ledger.writer import wal_ceiling_bytes
    out["plateau"] = {
        "marks": marks,
        "ceiling": wal_ceiling_bytes(db, conn=w._conn),
        "bounded": marks[-1][1] <= wal_ceiling_bytes(db, conn=w._conn) * 2,
    }
    w.close()

    # --- 2. what breaks the bound: a reader pinning the snapshot
    db2 = os.path.join(root, "pinned.db")
    w2 = _writer(db2)
    wal2 = db2 + "-wal"
    for i in range(1000):
        w2.write_turn("user_message", f"warm{i} " + "x" * 200,
                      surface="probe", **_STAMP)
    before = os.path.getsize(wal2)
    ro = sqlite3.connect(f"file:{db2}?mode=ro", uri=True)
    ro.execute("BEGIN")
    ro.execute("SELECT count(*) FROM turns").fetchone()
    for i in range(opts.commits):
        w2.write_turn("user_message", f"pin{i} " + "x" * 200,
                      surface="probe", **_STAMP)
    pinned = os.path.getsize(wal2)
    busy_row = w2._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    ro.execute("COMMIT")
    ro.close()
    out["pinned_reader"] = {
        "before_bytes": before, "after_bytes": pinned,
        "growth_factor": round(pinned / max(before, 1), 1),
        "truncate_while_pinned": list(busy_row),
        "truncate_reclaimed_nothing": bool(busy_row[0]) and
        os.path.getsize(wal2) == pinned,
    }
    w2.close()

    # --- 2b. a LARGE TRANSACTION with zero readers does it too
    #     (the false positive that killed the "pinned reader" cause claim)
    db3 = os.path.join(root, "bigtxn.db")
    w3 = _writer(db3)
    w3._conn.execute("BEGIN")
    for i in range(5000):
        w3._conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?)",
            (f"probe_{i}", "y" * 2000),
        )
    w3._conn.execute("COMMIT")
    out["large_transaction_no_readers"] = {
        "wal_bytes": os.path.getsize(db3 + "-wal"),
        "readers": 0,
        "note": "size alone proves shape, never cause",
    }
    w3.close()

    # --- 3. TRUNCATE cost with the write lock genuinely held elsewhere
    db4 = os.path.join(root, "contend.db")
    w4 = _writer(db4)
    for i in range(2000):
        w4.write_turn("user_message", f"c{i} " + "x" * 200,
                      surface="probe", **_STAMP)
    locked, release = threading.Event(), threading.Event()

    def holder():
        c = sqlite3.connect(db4, timeout=0.1)   # created INSIDE the thread
        c.execute("BEGIN IMMEDIATE")
        c.execute("INSERT INTO meta(key,value) VALUES('probe_lock','1')")
        locked.set()
        release.wait(30)
        c.rollback()
        c.close()

    t = threading.Thread(target=holder)
    t.start()
    if not locked.wait(10):
        raise SystemExit("holder never acquired the write lock — probe INVALID")
    t0 = time.perf_counter()
    row = w4._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    release.set()
    t.join()
    out["truncate_under_contention"] = {
        "elapsed_ms": round(elapsed_ms, 1),
        "returned": list(row),
        "busy_timeout_ms": w4._conn.execute(
            "PRAGMA busy_timeout").fetchone()[0],
    }
    t0 = time.perf_counter()
    row2 = w4._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    out["truncate_uncontended"] = {
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
        "returned": list(row2),
    }
    w4.close()

    print(json.dumps(out, indent=2))
    ok = (out["plateau"]["bounded"]
          and out["pinned_reader"]["growth_factor"] > 3
          and out["truncate_under_contention"]["elapsed_ms"] > 1000)
    print("\nPOLICY CLAIMS HOLD" if ok else "\nCLAIMS DID NOT REPRODUCE", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
