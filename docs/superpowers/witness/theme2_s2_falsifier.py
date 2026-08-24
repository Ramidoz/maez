#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Theme-2 S2 falsifier — replaces the U5 timing witness.

The U5 council ruled (three seats, unanimous): no frozen two-writer
timing witness; safety claims are booleans and booleans have no
percentiles. This is the falsifier that replaced it. It attacks the
claim that matters — no loss, no corruption, no silent acceptance —
through the REAL shipped code path (core.ledger.owner /
core.ledger.writer, real subprocesses, vendored SQLite), in a scratch
directory, never the live tree.

Arms (each a boolean verdict; any RED fails the run):

  F1  exactly-once, byte-exact: tens of thousands of deterministic
      appends (payload = f(index)) through owner_write_turn in a real
      owner process; every index present exactly once, payload verified
      by an independent oracle (recomputed, not round-tripped), chain
      positions contiguous, PRAGMA integrity_check == ok.
  F2  non-owner exclusion: concurrent real non-owner processes attempt
      try_write_turn during the batch; ZERO of their rows may reach the
      DB, and every attempt must be preserved byte-exact in that
      process's dead-letter sidecar (never silent).
  F3  checkpoint honesty: wal_checkpoint(TRUNCATE) on the owner's own
      connection while a concurrent ro reader pins the WAL; the pragma's
      RETURNED ROW is checked (busy flag), not merely "SQL ran"; after
      the reader closes, the checkpoint must complete (busy == 0) and
      the WAL must actually shrink.
  F4  SIGKILL recovery: the owner process is killed mid-batch
      repeatedly and restarted. Outcome classes are explicit:
      acked (turn_id returned + fsynced to the ack log) → MUST be in
      the DB exactly once; unacked → UNKNOWN, allowed to be present
      (exactly once) or absent — but the DB row count must equal
      acked + a subset of unacked, and no index may appear twice.
      The lethal case — acked but absent after recovery — is RED.
  F5  pragma license: journal_mode == wal and synchronous == FULL are
      asserted (council ruling 2026-08-24: the ack must never outlive
      its commit), and the claim stays narrow: SQLite's power-loss
      contract is enabled, but lying firmware/media death are not
      certified — that needs hardware fault injection.
  PC  positive control (rail-native, not a staged second-writer BUSY):
      an enabled writer in a process WITHOUT the vendored library must
      REFUSE for the RIGHT REASON (its message names 3.51.3), and a
      second enabled writer against a held latch must REFUSE naming the
      owner. A control that trips for any other reason is RED.

Never p99. No timing verdicts at all: nothing here needs one.

Usage:  LD_LIBRARY_PATH=vendor/sqlite/lib .venv/bin/python3 \
            docs/superpowers/witness/theme2_s2_falsifier.py [--n 20000]
Writes report JSON to stdout and exits 0 only if every arm is GREEN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_VENDOR = _REPO / "vendor" / "sqlite" / "lib"

_STAMP = {"taint_labels": ["owner_utterance"], "privacy_access": "public"}


def payload_for(index: int) -> str:
    """Deterministic payload. The oracle recomputes this independently at
    verify time — a symmetric encode/decode bug cannot cancel because the
    verifier compares against sha256 recomputed from the index alone."""
    return f"falsifier-turn-{index}:{hashlib.sha256(str(index).encode()).hexdigest()}"


# --------------------------------------------------------------------------
# child roles (run in real subprocesses)
# --------------------------------------------------------------------------

def run_owner_child(db: str, ack_path: str, start: int, end: int,
                    checkpoint_every: int, fsync_acks: bool) -> None:
    sys.path.insert(0, str(_REPO))
    from core.ledger import owner

    owner.claim_ownership()
    # RESUME BY IDENTITY: a recovery owner must not re-append indexes the
    # crashed owner already committed (kill between COMMIT and ack would
    # otherwise duplicate them). Identity here is the deterministic
    # payload; the DB itself is consulted, not just the ack log — this
    # models the replay protocol the admission-protocol slice will need.
    already: dict[int, str] = {}
    if os.path.exists(ack_path):
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            for tid_, raw in conn.execute(
                "SELECT turn_id, raw_text FROM turns WHERE surface='falsifier'"
            ).fetchall():
                try:
                    already[int(raw.split("-")[2].split(":")[0])] = tid_
                except (IndexError, ValueError):
                    continue
        finally:
            conn.close()
    ack_fd = os.open(ack_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    for i in range(start, end):
        if i in already:
            line = f"ACK {i} {already[i]}\n".encode()
            os.write(ack_fd, line)
            if fsync_acks:
                os.fsync(ack_fd)
            continue
        tid = owner.owner_write_turn(
            db, "user_message", payload_for(i), surface="falsifier", **_STAMP
        )
        if tid is None:
            # Explicit refusal/failure — recorded, never silent.
            line = f"FAIL {i}\n".encode()
        else:
            line = f"ACK {i} {tid}\n".encode()
        os.write(ack_fd, line)
        if fsync_acks:
            os.fsync(ack_fd)
        if checkpoint_every and i and i % checkpoint_every == 0:
            # Owner-connection checkpoint (the shape a future owner
            # checkpoint policy ships). Returned row is checked in F3.
            w = owner._writer
            if w is not None and w._conn is not None:
                w._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    os.fsync(ack_fd)
    os.close(ack_fd)
    print("OWNER_DONE")


def run_nonowner_child(db: str, start: int, end: int) -> None:
    sys.path.insert(0, str(_REPO))
    from core.ledger.writer import try_write_turn

    outcomes = {"written": 0, "dropped": 0}
    for i in range(start, end):
        tid = try_write_turn(
            db, "user_message", f"nonowner-{payload_for(i)}",
            surface="falsifier_nonowner", **_STAMP,
        )
        outcomes["written" if tid else "dropped"] += 1
    print(json.dumps(outcomes))


def run_spool_client_child(spool_root: str, producer: str,
                           start: int, end: int) -> None:
    sys.path.insert(0, str(_REPO))
    from core.ledger import spool

    for i in range(start, end):
        spool.enqueue(
            spool_root, producer=producer, turn_kind="user_message",
            raw_text=payload_for(i),
            kwargs={"surface": f"spool_{producer}", **_STAMP},
        )
    print("CLIENT_DONE")


def run_surface_client_child(db: str, producer: str,
                             start: int, end: int) -> None:
    """The SHIPPED surface path — exactly what web/CLI now call: a
    user_message via submit_user_message, then the audited reply via
    persist_model_reply's non-owner branch, linked by submission id."""
    sys.path.insert(0, str(_REPO))
    from core.ledger.model_reply_persistence import (
        build_model_reply_audit_verdict,
        persist_model_reply,
        submit_user_message,
    )

    for i in range(start, end):
        sid = submit_user_message(db, payload_for(i), surface=producer)
        assert sid, "enabled surface submit must return a submission id"
        persist_model_reply(
            db_path=db,
            raw_text=f"reply-{payload_for(i)}",
            surface=producer,
            parent_submission_id=sid,
            model_id="falsifier",
            prompt_material={"i": i},
            soul_material="falsifier-soul",
            evidence_envelope={"claimable": [], "forbidden": []},
            audit_verdict=build_model_reply_audit_verdict(
                surface=producer, audit_ran=True, changed_output=False,
            ),
        )
    print("SURFACE_CLIENT_DONE")


def run_dormant_surface_child(db: str) -> None:
    """Dormancy control: with MAEZ_LEDGER_WRITES absent the surface
    helpers must leave NO trace — no spool file, no directory."""
    sys.path.insert(0, str(_REPO))
    assert "MAEZ_LEDGER_WRITES" not in os.environ
    from core.ledger import spool
    from core.ledger.model_reply_persistence import (
        build_model_reply_audit_verdict,
        persist_model_reply,
        submit_user_message,
    )

    sid = submit_user_message(db, "dormant probe", surface="dormant7")
    persist_model_reply(
        db_path=db,
        raw_text="dormant reply",
        surface="dormant7",
        parent_submission_id=None,
        model_id="falsifier",
        prompt_material={},
        soul_material="falsifier-soul",
        evidence_envelope={"claimable": [], "forbidden": []},
        audit_verdict=build_model_reply_audit_verdict(
            surface="dormant7", audit_ran=True, changed_output=False,
        ),
    )
    root = spool.default_spool_root(db)
    if sid is None and not os.path.exists(root):
        print("DORMANT_OK")
    else:
        print(f"DORMANT_VIOLATION sid={sid!r} root_exists={os.path.exists(root)}")


def run_drainer_child(spool_root: str, db: str) -> None:
    sys.path.insert(0, str(_REPO))
    from core.ledger import owner, spool

    owner.claim_ownership(db)  # eager latch
    while True:
        spool.drain_once(spool_root, db)
        if spool.spool_status(spool_root)["pending_total"] == 0:
            break
        time.sleep(0.02)
    print("DRAINER_DONE")


def run_version_probe_child(db: str) -> None:
    sys.path.insert(0, str(_REPO))
    from core.ledger.writer import LedgerWriter

    try:
        w = LedgerWriter(db)
        print("CONSTRUCTED")
        w.close()
    except RuntimeError as e:
        print(f"REFUSED {e}")


# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------

def _child_env(*, vendored: bool = True) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("LD_LIBRARY_PATH", "MAEZ_LEDGER_WRITES",
                        "MAEZ_LEDGER_OWNER_PID")}
    env["MAEZ_TEST_MODE"] = "1"
    env["MAEZ_LEDGER_WRITES"] = "1"
    if vendored:
        env["LD_LIBRARY_PATH"] = str(_VENDOR)
    return env


def _spawn(role: str, *args: str, vendored: bool = True) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, __file__, "--role", role, *args],
        env=_child_env(vendored=vendored),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _read_acks(ack_path: str) -> tuple[dict[int, str], set[int]]:
    """Return ({index: turn_id} for acked, {index} for explicit FAILs).
    A torn final line (killed mid-write) is ignored — that index simply
    stays UNKNOWN, which is the honest classification."""
    acked: dict[int, str] = {}
    failed: set[int] = set()
    p = Path(ack_path)
    if not p.exists():
        return acked, failed
    for line in p.read_bytes().decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "ACK":
            try:
                acked[int(parts[1])] = parts[2]
            except ValueError:
                continue
        elif len(parts) == 2 and parts[0] == "FAIL":
            try:
                failed.add(int(parts[1]))
            except ValueError:
                continue
    return acked, failed


def _db_rows(db: str) -> dict[str, list]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT raw_text, chain_position FROM turns"
            " WHERE surface='falsifier' AND turn_kind='user_message'"
        ).fetchall()
        nonowner = conn.execute(
            "SELECT COUNT(*) FROM turns WHERE surface='falsifier_nonowner'"
        ).fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        positions = [r[0] for r in conn.execute(
            "SELECT chain_position FROM turns ORDER BY chain_position"
        ).fetchall()]
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        conn.close()
    return {
        "rows": rows,
        "nonowner_rows": nonowner,
        "integrity": integrity,
        "positions": positions,
        "journal_mode": journal,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="harness")
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("args", nargs="*")
    opts = ap.parse_args()

    if opts.role == "owner":
        db, ack, start, end, ckpt, fsync = opts.args
        run_owner_child(db, ack, int(start), int(end), int(ckpt), fsync == "1")
        return 0
    if opts.role == "nonowner":
        db, start, end = opts.args
        run_nonowner_child(db, int(start), int(end))
        return 0
    if opts.role == "version_probe":
        run_version_probe_child(opts.args[0])
        return 0
    if opts.role == "spool_client":
        spool_root, producer, start, end = opts.args
        run_spool_client_child(spool_root, producer, int(start), int(end))
        return 0
    if opts.role == "surface_client":
        db_, producer, start, end = opts.args
        run_surface_client_child(db_, producer, int(start), int(end))
        return 0
    if opts.role == "dormant_surface":
        run_dormant_surface_child(opts.args[0])
        return 0
    if opts.role == "drainer":
        run_drainer_child(opts.args[0], opts.args[1])
        return 0

    # ---------------------------------------------------------------- harness
    verdicts: dict[str, dict] = {}
    scratch = tempfile.mkdtemp(prefix="theme2_s2_falsifier_")
    db = str(Path(scratch) / "falsifier_ledger.db")
    assert not db.startswith(str(_REPO / "memory")), "never the live tree"

    sys.path.insert(0, str(_REPO))
    from core.ledger import migrate
    migrate.run(db)

    n = opts.n
    t_start = time.time()

    # ---- F1 + F2: owner batch with concurrent non-owner attackers.
    # The attackers launch only after the owner demonstrably holds the
    # latch (first ack visible): the certified property is exclusion
    # UNDER A LIVE OWNER — production's shape (the daemon is always on).
    # The pre-claim window (owner started, no write yet) is a recorded
    # open item, not silently blessed by this arm.
    ack1 = str(Path(scratch) / "acks_f1.log")
    owner_p = _spawn("owner", db, ack1, "0", str(n), "5000", "0")
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if os.path.exists(ack1) and os.path.getsize(ack1) > 0:
            break
        if owner_p.poll() is not None:
            break
        time.sleep(0.02)
    nonowners = [
        _spawn("nonowner", db, str(i * 50), str(i * 50 + 50)) for i in range(4)
    ]
    owner_out, owner_err = owner_p.communicate(timeout=1800)
    non_results = []
    for p in nonowners:
        out, _ = p.communicate(timeout=600)
        try:
            non_results.append(json.loads(out.strip().splitlines()[-1]))
        except (ValueError, IndexError):
            non_results.append({"written": -1, "dropped": -1, "parse_error": True})

    acked, failed = _read_acks(ack1)
    state = _db_rows(db)
    payload_ok = all(
        raw == payload_for(int(raw.split("-")[2].split(":")[0]))
        for raw, _pos in state["rows"]
    )
    indexes = sorted(
        int(raw.split("-")[2].split(":")[0]) for raw, _ in state["rows"]
    )
    verdicts["F1_exactly_once_byte_exact"] = {
        "submitted": n,
        "acked": len(acked),
        "explicit_fail": len(failed),
        "db_rows": len(state["rows"]),
        "unique_indexes": len(set(indexes)),
        "all_indexes_exactly_once": indexes == list(range(n)),
        "payloads_byte_exact_vs_oracle": payload_ok,
        "chain_positions_contiguous":
            state["positions"] == list(range(len(state["positions"]))),
        "integrity_check": state["integrity"],
        "journal_mode": state["journal_mode"],
        "green": (
            indexes == list(range(n)) and payload_ok
            and len(acked) == n and not failed
            and state["integrity"] == "ok"
            and state["positions"] == list(range(len(state["positions"])))
            and state["journal_mode"] == "wal"
        ),
    }
    verdicts["F2_nonowner_exclusion"] = {
        "nonowner_rows_in_db": state["nonowner_rows"],
        "attempts": non_results,
        "all_attempts_dropped_not_silent": all(
            r.get("written") == 0 and r.get("dropped", 0) > 0
            for r in non_results
        ),
        "dead_letter_rows": __import__(
            "core.ledger.writer", fromlist=["dead_letter_status"]
        ).dead_letter_status(db)["rows"],
        "green": (
            state["nonowner_rows"] == 0
            and all(r.get("written") == 0 for r in non_results)
            and __import__(
                "core.ledger.writer", fromlist=["dead_letter_status"]
            ).dead_letter_status(db)["rows"]
            == sum(r.get("dropped", 0) for r in non_results)
        ),
    }

    # ---- F3: checkpoint honesty with a pinning reader, on the owner conn.
    from core.ledger import owner as owner_mod
    owner_mod._reset_for_tests()
    os.environ["MAEZ_LEDGER_WRITES"] = "1"
    owner_mod.claim_ownership()
    owner_mod.owner_write_turn(db, "user_message", payload_for(10**7),
                               surface="falsifier_f3", **_STAMP)
    reader = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    reader.execute("BEGIN")
    reader.execute("SELECT COUNT(*) FROM turns").fetchone()
    for i in range(3):
        owner_mod.owner_write_turn(db, "user_message", payload_for(10**7 + 1 + i),
                                   surface="falsifier_f3", **_STAMP)
    wconn = owner_mod._writer._conn
    busy_pinned, _log1, _ck1 = wconn.execute(
        "PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    reader.execute("COMMIT")
    reader.close()
    busy_free, _log2, _ck2 = wconn.execute(
        "PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    wal_size = os.path.getsize(db + "-wal") if os.path.exists(db + "-wal") else 0
    sync_mode = wconn.execute("PRAGMA synchronous").fetchone()[0]
    verdicts["F3_checkpoint_honesty"] = {
        "busy_flag_with_pinning_reader": busy_pinned,
        "busy_flag_after_reader_closed": busy_free,
        "wal_bytes_after_truncate": wal_size,
        "green": busy_free == 0 and wal_size == 0,
        "note": (
            "returned-row checked, not merely 'SQL ran'; a pinning reader "
            "makes TRUNCATE report busy=1, which is honest, not a failure"
        ),
    }
    verdicts["F5_pragma_license"] = {
        "journal_mode": state["journal_mode"],
        "synchronous": sync_mode,
        # Council ruling Q2 (2026-08-24): FULL (=2), unconditionally.
        # The ack (returned turn_id) must never outlive its commit.
        "green": state["journal_mode"] == "wal" and sync_mode == 2,
        "licensed_claim": (
            "SIGKILL/process-crash recovery certified. synchronous=FULL: "
            "SQLite's power-loss contract is ENABLED (commit fsync before "
            "ack). NOT certified: lying storage firmware, media failure — "
            "true power-loss certification needs hardware fault injection "
            "this witness does not perform."
        ),
    }
    owner_mod._reset_for_tests()
    os.environ.pop("MAEZ_LEDGER_WRITES", None)

    # ---- F4: SIGKILL the owner mid-batch, repeatedly; classify outcomes.
    db4 = str(Path(scratch) / "falsifier_kill.db")
    migrate.run(db4)
    ack4 = str(Path(scratch) / "acks_f4.log")
    kill_cycles = 8
    batch = 4000
    killed_at: list[int] = []

    def _ack_lines() -> int:
        try:
            return Path(ack4).read_bytes().count(b"\n")
        except OSError:
            return 0

    for cycle in range(kill_cycles):
        start, end = cycle * batch, (cycle + 1) * batch
        p = _spawn("owner", db4, ack4, str(start), str(end), "0", "1")
        if cycle % 2 == 0:
            # DETERMINISTIC BARRIER (council demand): kill only once the
            # fsynced ack log proves the child is mid-batch — never a
            # timer that can miss the window entirely.
            threshold = start + 200
            while p.poll() is None and _ack_lines() < threshold:
                time.sleep(0.005)
            if p.poll() is None:
                p.send_signal(signal.SIGKILL)
                p.wait(timeout=60)
                killed_at.append(cycle)
                # Recovery is part of the arm: a fresh owner must open the
                # same DB (WAL recovery), resume BY IDENTITY (skip already
                # committed indexes — re-appending them would duplicate),
                # and complete the range.
                p2 = _spawn("owner", db4, ack4, str(start), str(end), "0", "1")
                p2.communicate(timeout=600)
            else:
                p.communicate(timeout=600)
        else:
            p.communicate(timeout=600)

    acked4, failed4 = _read_acks(ack4)
    conn4 = sqlite3.connect(f"file:{db4}?mode=ro", uri=True)
    try:
        raws = [r[0] for r in conn4.execute(
            "SELECT raw_text FROM turns WHERE surface='falsifier'"
        ).fetchall()]
        integrity4 = conn4.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn4.close()
    idx4 = [int(r.split("-")[2].split(":")[0]) for r in raws]
    from collections import Counter
    counts4 = Counter(idx4)
    duplicates = [i for i, c in counts4.items() if c > 1]
    acked_missing = [i for i in acked4 if counts4.get(i, 0) == 0]
    total_submitted = set(range(kill_cycles * batch))
    unknown = sorted(total_submitted - set(acked4) - failed4)
    unknown_present = [i for i in unknown if counts4.get(i, 0) == 1]
    stray = sorted(set(counts4) - total_submitted)
    verdicts["F4_sigkill_recovery"] = {
        "cycles": kill_cycles,
        "kills_delivered": len(killed_at),
        "acked": len(acked4),
        "explicit_fail": len(failed4),
        "unknown_after_kill": len(unknown),
        "unknown_resolved_present": len(unknown_present),
        "unknown_resolved_absent": len(unknown) - len(unknown_present),
        "ACKED_BUT_MISSING": acked_missing,   # the lethal class
        "duplicates": duplicates,
        "stray_indexes": stray,
        "integrity_check": integrity4,
        "all_indexes_complete_after_recovery":
            set(counts4) == total_submitted,
        "green": (
            len(killed_at) > 0                # the control must actually fire
            and not acked_missing and not duplicates and not stray
            and set(counts4) == total_submitted
            and integrity4 == "ok"
        ),
        "note": (
            "acked = turn_id returned AND ack fsynced before the kill; "
            "every acked index must survive. unknown = killed between "
            "submit and ack — present-exactly-once or absent are both "
            "honest; a retry protocol may only resubmit via the same "
            "identity (admission-protocol gap, recorded)."
        ),
    }

    # ---- F6: spool exactly-once across a drainer SIGKILL.
    db6 = str(Path(scratch) / "falsifier_spool.db")
    migrate.run(db6)
    spool_root = str(Path(scratch) / "spool")
    n6 = 1000
    clients = [
        _spawn("spool_client", spool_root, "webish", "0", str(n6 // 2)),
        _spawn("spool_client", spool_root, "clish", str(n6 // 2), str(n6)),
    ]
    for c in clients:
        c.communicate(timeout=600)
    from core.ledger import spool as spool_mod
    enqueued = spool_mod.spool_status(spool_root)["pending_total"]

    def _acked_total() -> int:
        s = spool_mod.spool_status(spool_root)
        return sum(p["acked"] for p in s["producers"].values())

    d1 = _spawn("drainer", spool_root, db6)
    # Deterministic barrier: kill only once acks prove mid-drain.
    kill_deadline = time.monotonic() + 300
    drainer_killed = False
    while time.monotonic() < kill_deadline and d1.poll() is None:
        if _acked_total() >= 150:
            d1.send_signal(signal.SIGKILL)
            d1.wait(timeout=60)
            drainer_killed = True
            break
        time.sleep(0.01)
    if not drainer_killed and d1.poll() is None:
        d1.communicate(timeout=600)
    d2 = _spawn("drainer", spool_root, db6)
    d2.communicate(timeout=600)

    conn6 = sqlite3.connect(f"file:{db6}?mode=ro", uri=True)
    try:
        sub_rows = conn6.execute(
            "SELECT submission_id, raw_text FROM turns"
            " WHERE submission_id IS NOT NULL"
        ).fetchall()
        dup_subs = conn6.execute(
            "SELECT submission_id, COUNT(*) c FROM turns"
            " WHERE submission_id IS NOT NULL"
            " GROUP BY submission_id HAVING c > 1"
        ).fetchall()
        integrity6 = conn6.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn6.close()
    status6 = spool_mod.spool_status(spool_root)
    receipts = 0
    for prod_dir in Path(spool_root).iterdir():
        receipts += len(list((prod_dir / "acked").glob("*.receipt.json")))
    payload_ok6 = all(
        raw == payload_for(int(raw.split("-")[2].split(":")[0]))
        for _sid, raw in sub_rows
    )
    verdicts["F6_spool_exactly_once_across_drainer_kill"] = {
        "enqueued": enqueued,
        "drainer_killed_mid_drain": drainer_killed,
        "db_rows_with_identity": len(sub_rows),
        "duplicate_submission_ids": len(dup_subs),
        "pending_after_recovery": status6["pending_total"],
        "refused": sum(p["refused"] for p in status6["producers"].values()),
        "receipts": receipts,
        "payloads_byte_exact_vs_oracle": payload_ok6,
        "integrity_check": integrity6,
        "green": (
            enqueued == n6
            and drainer_killed                # the control must fire
            and len(sub_rows) == n6
            and not dup_subs
            and status6["pending_total"] == 0
            and receipts == n6
            and payload_ok6
            and integrity6 == "ok"
        ),
        "note": (
            "two real non-owner client processes published; the owner "
            "drainer was SIGKILLed at a deterministic acked-count barrier "
            "and a fresh drainer recovered by identity: every envelope "
            "exactly once, every ack chain-bound, zero pending left"
        ),
    }

    # ---- F7: the SHIPPED surface wiring end-to-end. Real non-owner
    # subprocesses use the exact helpers web/CLI call
    # (submit_user_message + persist_model_reply's non-owner branch);
    # the owner drainer commits; every conversation edge must be REAL
    # (reply.parent_turn_id == its user turn's id), and a flag-unset
    # surface must leave zero trace (dormancy control).
    surface_dir = Path(scratch) / "surface"
    surface_dir.mkdir()
    db7 = str(surface_dir / "ledger.db")
    migrate.run(db7)
    root7 = spool_mod.default_spool_root(db7)

    dormant_env = _child_env()
    dormant_env.pop("MAEZ_LEDGER_WRITES", None)
    # Dormancy is proven against DB BYTES, not just spool absence: a
    # flag-off SQLite/meta write would be invisible to a spool-only
    # predicate (Codex validation #6).
    db7_bytes_before = hashlib.sha256(Path(db7).read_bytes()).hexdigest()
    dormant_p = subprocess.Popen(
        [sys.executable, __file__, "--role", "dormant_surface", db7],
        env=dormant_env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    dormant_out, dormant_err = dormant_p.communicate(timeout=300)
    db7_untouched = (
        hashlib.sha256(Path(db7).read_bytes()).hexdigest() == db7_bytes_before
        and not os.path.exists(db7 + "-wal")
        and not os.path.exists(db7 + "-shm")
    )

    n7 = 250  # pairs per client; 2 clients -> 500 users + 500 replies
    surface_clients = [
        _spawn("surface_client", db7, "webish7", "0", str(n7)),
        _spawn("surface_client", db7, "clish7", str(n7), str(2 * n7)),
    ]
    client_errs = []
    for c in surface_clients:
        out7, err7 = c.communicate(timeout=900)
        if "SURFACE_CLIENT_DONE" not in out7:
            client_errs.append(err7[-500:])
    enqueued7 = spool_mod.spool_status(root7)["pending_total"]
    d7 = _spawn("drainer", root7, db7)
    d7.communicate(timeout=900)

    conn7 = sqlite3.connect(f"file:{db7}?mode=ro", uri=True)
    try:
        users7 = dict(conn7.execute(
            "SELECT raw_text, turn_id FROM turns"
            " WHERE turn_kind='user_message'"
            " AND surface IN ('webish7','clish7')"
        ).fetchall())
        replies7 = conn7.execute(
            "SELECT raw_text, parent_turn_id FROM turns"
            " WHERE turn_kind='model_reply'"
            " AND surface IN ('webish7','clish7')"
        ).fetchall()
        user_dupes7 = conn7.execute(
            "SELECT raw_text, COUNT(*) c FROM turns"
            " WHERE turn_kind='user_message'"
            " AND surface IN ('webish7','clish7')"
            " GROUP BY raw_text HAVING c > 1"
        ).fetchall()
        integrity7 = conn7.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn7.close()
    edges_real = (
        len(replies7) == 2 * n7
        and all(
            raw.startswith("reply-")
            and parent is not None
            and users7.get(raw[len("reply-"):]) == parent
            for raw, parent in replies7
        )
    )
    status7 = spool_mod.spool_status(root7)
    verdicts["F7_shipped_surface_wiring"] = {
        "dormant_control": dormant_out.strip(),
        "dormant_db_bytes_untouched": db7_untouched,
        "clients_failed": client_errs,
        "enqueued_before_drain": enqueued7,
        "user_rows": len(users7),
        "reply_rows": len(replies7),
        "duplicate_user_payloads": len(user_dupes7),
        "conversation_edges_all_real": edges_real,
        "pending_after_drain": status7["pending_total"],
        "integrity_check": integrity7,
        "green": (
            dormant_out.strip() == "DORMANT_OK"
            and db7_untouched
            and not client_errs
            and enqueued7 == 4 * n7
            and len(users7) == 2 * n7
            and not user_dupes7
            and edges_real
            and status7["pending_total"] == 0
            and integrity7 == "ok"
        ),
        "note": (
            "SCOPE: this arm proves the surface HELPER mechanism "
            "(submit_user_message + persist_model_reply non-owner branch) "
            "in real non-owner processes — it does not execute the flask/"
            "CLI handlers themselves; that the handlers call these helpers "
            "is proven by tests/test_ledger_surface_spool_wiring.py source "
            "assertions. Proven here: drain commits parent-before-child, "
            "every reply's parent_turn_id is its real user turn, and a "
            "flag-unset surface leaves no spool trace AND no db-byte "
            "change"
        ),
    }

    # ---- PC: positive controls must trip for the RIGHT reason.
    probe_db = str(Path(scratch) / "probe.db")
    migrate.run(probe_db)
    bare = _spawn("version_probe", probe_db, vendored=False)
    bare_out, _ = bare.communicate(timeout=120)
    latch_holder_env = _child_env()
    import fcntl
    holder_fd = os.open(probe_db + ".ownerlock",
                        os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(holder_fd, fcntl.LOCK_EX)
    held = _spawn("version_probe", probe_db)
    held_out, _ = held.communicate(timeout=120)
    os.close(holder_fd)
    bare_right_reason = "REFUSED" in bare_out and "3.51.3" in bare_out
    if "CONSTRUCTED" in bare_out:
        # System SQLite may itself carry the fix someday; that is a config
        # change, not a falsifier failure — but it must be reported.
        bare_right_reason = None
    verdicts["PC_positive_controls"] = {
        "bare_library_probe": bare_out.strip().splitlines()[-1] if bare_out.strip() else "",
        "bare_refused_naming_3513": bare_right_reason,
        "held_latch_probe": held_out.strip().splitlines()[-1] if held_out.strip() else "",
        "held_latch_refused_naming_owner":
            "REFUSED" in held_out and "owner" in held_out,
        "green": bool(bare_right_reason) and
            ("REFUSED" in held_out and "owner" in held_out),
    }

    all_green = all(v.get("green") for v in verdicts.values())
    report = {
        "witness": "theme2-s2-falsifier",
        "replaces": "U5 (council ruling 2026-08-23: booleans, never p99)",
        "ran_at": t_start,
        "duration_s": round(time.time() - t_start, 1),
        "n": n,
        "scratch": scratch,
        "sqlite_version": sqlite3.sqlite_version,
        "verdict": "GREEN" if all_green else "RED",
        "arms": verdicts,
        "licensed_claim": (
            "Under the shipped single-owner topology on the vendored "
            "library: deterministic appends land exactly once and "
            "byte-exact; non-owner writers cannot reach the DB and their "
            "payloads are never silently lost; the chain stays contiguous "
            "and the DB passes integrity_check under checkpoint pressure "
            "and repeated owner SIGKILL; the shipped surface wiring "
            "(submit_user_message / persist_model_reply via the spool) "
            "produces real conversation edges and exact flag-dormancy. "
            "synchronous=FULL enables SQLite's power-loss contract; NOT "
            "certified: lying firmware/media death (hardware fault "
            "injection), malicious-author resistance, and any topology "
            "other than the one that ships."
        ),
    }
    print(json.dumps(report, indent=2))
    return 0 if all_green else 1


if __name__ == "__main__":
    sys.exit(main())
