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
    evidence["no_maez_env"] = "PASS"
    evidence["env"] = dict(sorted(os.environ.items()))
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

    # Import and construct only after containment is proven. Constructing
    # MaezDaemon builds MemoryManager, which mkdirs and opens Chroma at
    # memory_manager.BASE_DB -- the un-redirectable literal. Inside the
    # namespace that resolves into the airlock.
    from daemon.maez_daemon import MaezDaemon

    t0 = time.time()
    daemon = MaezDaemon()
    report["daemon_construct_seconds"] = round(time.time() - t0, 3)

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

    report["finished_at"] = time.time()
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(f"t5 replay complete: {len(interactions)} interactions -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
