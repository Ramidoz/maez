#!/usr/bin/env python3
"""Theme 2 S1 — T5 replay driver (protocol §12.6).

Drives the frozen 20-interaction manifest through the reply machinery,
flags off, inside the containment namespace built by
theme2_s1_airlock.sh. Refuses to run anywhere else.

Usage (inside the namespace only):
    python3 docs/superpowers/witness/theme2_s1_t5_replay.py \
        --manifest docs/superpowers/witness/theme2-s1-replay.json \
        --report   /home/rohit/maez/logs/t5_run.json

The report goes to logs/, which protocol §12.7 excludes from the store
tree and from the archive, so writing it cannot perturb what T5
compares.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import time
import traceback
from pathlib import Path

MAEZ_TREE = Path("/home/rohit/maez")
EXPECTED_MANIFEST_SHA = (
    "2b9faf616941bb6a0ab6294e1323e2dd73cb57389ab021cc2b868f59109cb420"
)

# Gate round 13 item B: --clearenv fixes the environment at namespace ENTRY,
# but importing the daemon runs the shipped secrets loader, which repopulates
# config/.env into os.environ exactly as it does in production
# (maez_daemon.py:34 -> secrets.load_ordinary_config_for_process). That is
# correct behavior to exercise, not a leak to suppress -- but it makes
# "nothing MAEZ-shaped" false, so what T5 asserts is the narrower, true
# thing: no PHASE/S1 flag is set. The list is frozen; S1's own flags join it
# when they exist.
FLAGS_THAT_MUST_BE_UNSET = (
    "MAEZ_LEDGER_WRITES",
    "MAEZ_BIRTH_PHASE",
    "MAEZ_BIRTH_LATCH",
    "MAEZ_S1_PHASE_TRUTH",
)
# Values safe to record verbatim. Everything else is recorded by NAME only:
# config/.env carries credentials, and a witness report is a committed file.
ENV_VALUES_SAFE_TO_RECORD = (
    "HOME", "LANG", "LC_ALL", "PATH", "PWD", "PYTHONDONTWRITEBYTECODE",
    "PYTHONHASHSEED", "TZ", "VIRTUAL_ENV", "MAEZ_LLM_BACKEND",
    "MAEZ_LIVE_FAST_LANE_ENABLED", "MAEZ_WORKING_SELF",
)


def env_snapshot() -> dict:
    return {
        "names": sorted(os.environ),
        "count": len(os.environ),
        "values": {k: os.environ[k] for k in sorted(os.environ)
                   if k in ENV_VALUES_SAFE_TO_RECORD},
        "maez_names": sorted(k for k in os.environ if k.startswith("MAEZ_")),
    }


class ContainmentRefusal(RuntimeError):
    """The driver is not inside the airlock namespace. It will not run."""


def assert_contained() -> dict:
    """Prove containment from inside before importing a single Maez module.

    Three independent checks, all cheap, all recorded. Any failure aborts
    before the reply machinery can construct a store.
    """
    evidence: dict = {}

    # 1. The repo must be read-only. A module-global absolute path can only
    #    be caught by the filesystem, so this is the load-bearing check.
    probe = MAEZ_TREE / ".t5_containment_probe"
    try:
        probe.write_text("x")
    except OSError as e:
        evidence["repo_readonly"] = f"PASS ({e.__class__.__name__}: {e.strerror})"
    else:
        probe.unlink(missing_ok=True)
        raise ContainmentRefusal(
            f"{MAEZ_TREE} is WRITABLE — not inside the airlock namespace"
        )

    # 2. memory/ must be writable, and must not be the live store. The live
    #    store is ~579 MB; an airlock-bound one starts empty.
    mem = MAEZ_TREE / "memory"
    mp = mem / ".t5_containment_probe"
    try:
        mp.write_text("x")
        mp.unlink()
    except OSError as e:
        raise ContainmentRefusal(f"{mem} is not writable: {e}") from e
    live_marker = mem / "db" / "raw"
    if live_marker.exists() and any(live_marker.iterdir()):
        raise ContainmentRefusal(
            f"{live_marker} is populated — this looks like the LIVE store"
        )
    evidence["memory_writable_and_empty"] = "PASS"

    # 3. The network must be unshared (protocol §12.3, hermetic).
    try:
        s = socket.create_connection(("127.0.0.1", 8080), timeout=0.5)
    except OSError as e:
        evidence["network_unreachable"] = f"PASS ({e.__class__.__name__})"
    else:
        s.close()
        raise ContainmentRefusal("127.0.0.1:8080 is reachable — not hermetic")

    # 4. No MAEZ_* flag may be set.
    leaked = sorted(k for k in os.environ if k.startswith("MAEZ_"))
    if leaked:
        raise ContainmentRefusal(f"MAEZ_* set in the namespace: {leaked}")
    evidence["no_maez_env_at_entry"] = "PASS"
    evidence["env_at_entry"] = env_snapshot()
    return evidence


def load_manifest(path: Path) -> list[dict]:
    raw = path.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != EXPECTED_MANIFEST_SHA:
        raise SystemExit(
            f"manifest digest mismatch: expected {EXPECTED_MANIFEST_SHA}, got {got}"
        )
    return json.loads(raw)["interactions"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    report: dict = {
        "protocol": "theme2-s1 protocol §12.6",
        "started_at": time.time(),
        "python": sys.version,
        "interactions": [],
    }
    report["containment"] = assert_contained()

    interactions = load_manifest(Path(args.manifest))
    report["manifest_sha256"] = EXPECTED_MANIFEST_SHA
    report["interaction_count"] = len(interactions)

    sys.path.insert(0, str(MAEZ_TREE))
    import sqlite3

    report["sqlite_version"] = sqlite3.sqlite_version

    # Gate round 12, item B: the ledger is migrated INSIDE the namespace.
    # Doing it before namespace entry left a Python startup -- imports,
    # site/.pth, bytecode, inherited descriptors -- outside the boundary
    # the protocol claims to be total. Nothing runs outside now.
    from core.ledger.migrate import run as migrate_run

    ledger = MAEZ_TREE / "memory" / "ledger.db"
    migrate_run(str(ledger))
    report["ledger_post_migration_sha256"] = hashlib.sha256(
        ledger.read_bytes()).hexdigest()
    report["ledger_post_migration_file_set"] = sorted(
        q.name for q in ledger.parent.iterdir() if q.name.startswith("ledger.db"))

    # Import and construct only after containment is proven. Constructing
    # MaezDaemon builds MemoryManager, which mkdirs and opens Chroma at
    # memory_manager.BASE_DB -- the un-redirectable literal. Inside the
    # namespace that resolves into the airlock.
    from daemon.maez_daemon import MaezDaemon

    # Gate round 13 item B: prove, AFTER the import that reloads config/.env,
    # that no phase/S1 flag is set. This is the environment that actually
    # executes handle_message.
    report["env_after_import"] = env_snapshot()
    set_flags = [f for f in FLAGS_THAT_MUST_BE_UNSET if os.environ.get(f)]
    if set_flags:
        raise SystemExit(f"REFUSED: flags-off violated after import: {set_flags}")
    report["flags_off_after_import"] = "PASS"

    t0 = time.time()
    daemon = MaezDaemon()
    report["daemon_construct_seconds"] = round(time.time() - t0, 3)

    # Gate round 13 finding I: two equally EMPTY store trees agree with each
    # other and prove nothing. Without a positive control, a run in which
    # every handle_message raised would still exit 0 and still produce a
    # "baseline". So: count the store tail's invocations and its observable
    # effect, and fail the run if the tail never executed.
    tail_calls = {"store_telegram": 0}
    _orig_store = daemon.memory.store_telegram

    def _counting_store(*a, **kw):
        tail_calls["store_telegram"] += 1
        return _orig_store(*a, **kw)

    # Observation only: the proxy calls through unchanged and is removed
    # before the store tree is projected.
    daemon.memory.store_telegram = _counting_store

    def collection_counts() -> dict:
        out = {}
        for name in ("raw", "daily", "core"):
            try:
                out[name] = getattr(daemon.memory, name).count()
            except Exception as e:                       # noqa: BLE001
                out[name] = f"error: {type(e).__name__}"
        return out

    report["collection_counts_before"] = collection_counts()

    for item in interactions:
        rec = {"id": item["id"], "at": item["at"], "source": item["source"]}
        t = time.time()
        try:
            reply = daemon.handle_message(item["text"], source=item["source"])
            rec["reply"] = reply
            rec["outcome"] = "returned"
        except Exception as e:                      # noqa: BLE001
            rec["outcome"] = "raised"
            rec["exception"] = f"{type(e).__name__}: {e}"
            rec["traceback"] = traceback.format_exc()
        rec["seconds"] = round(time.time() - t, 3)
        report["interactions"].append(rec)

    daemon.memory.store_telegram = _orig_store
    report["collection_counts_after"] = collection_counts()
    report["store_tail_invocations"] = tail_calls["store_telegram"]

    returned = sum(1 for r in report["interactions"] if r["outcome"] == "returned")
    raised = [r["id"] for r in report["interactions"] if r["outcome"] == "raised"]
    before, after = (report["collection_counts_before"],
                     report["collection_counts_after"])
    grew = any(isinstance(after.get(k), int) and isinstance(before.get(k), int)
               and after[k] > before[k] for k in ("raw", "daily", "core"))
    report["positive_control"] = {
        "interactions_returned": returned,
        "interactions_raised": raised,
        "store_tail_invocations": tail_calls["store_telegram"],
        "collections_grew": grew,
        "verdict": ("PASS" if (returned == len(interactions)
                               and tail_calls["store_telegram"] > 0
                               and grew) else "FAIL"),
    }

    # Gate round 12, item C: flags off, the ledger is NOT "never opened" --
    # the evidence-envelope builder opens it read-only (envelope_builder.py:268,
    # recent_turns.py:97), and a read-only open of a WAL database creates the
    # -shm/-wal sidecars. The main-file digest is what B1 asserts; record the
    # sidecar reality rather than claim it away.
    report["ledger_post_replay_sha256"] = hashlib.sha256(
        (MAEZ_TREE / "memory" / "ledger.db").read_bytes()).hexdigest()
    report["ledger_post_replay_file_set"] = sorted(
        q.name for q in (MAEZ_TREE / "memory").iterdir()
        if q.name.startswith("ledger.db"))
    report["ledger_main_file_unchanged"] = (
        report["ledger_post_replay_sha256"]
        == report["ledger_post_migration_sha256"])

    report["finished_at"] = time.time()
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=str) + "\n")
    pc = report["positive_control"]
    print(f"t5 replay: {len(interactions)} interactions, "
          f"{pc['interactions_returned']} returned, "
          f"tail x{pc['store_tail_invocations']}, "
          f"positive control {pc['verdict']} -> {out}")
    # A run whose positive control failed is not a baseline. Exit non-zero so
    # the orchestration cannot archive it.
    return 0 if pc["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
