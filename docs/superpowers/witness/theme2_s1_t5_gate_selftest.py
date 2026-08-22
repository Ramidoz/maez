#!/usr/bin/env python3
"""Self-test for the T5 gate.

Gate round 18 executed synthetic controls against the first version of the
gate and found it failed an HONEST run while passing several dishonest
ones. The gate is the sole authority for T5's verdict, so it gets the same
treatment the projection comparator got: every case below is a defect a
gate round actually reproduced, or a mutation the gate must bite on.

    python3 theme2_s1_t5_gate_selftest.py

Exit 0 iff every case behaves as declared.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

GATE = Path(__file__).resolve().parent / "theme2_s1_t5_gate.py"
SHA_A = "a" * 64
EXERCISED = "chroma::raw"


def honest_run(fixture: str) -> dict:
    """What a correct pre-S1 flags-off run actually looks like: raw stamped,
    every other store legitimately empty, because store_telegram writes raw
    only and T5 reaches one of thirteen consumers."""
    return {
        "fixture": fixture,
        "phase_probe": {"current_phase": "gestation",
                        "birth_event_turn_id": None,
                        "has_resolve_api": False},
        "stamp_census": {
            EXERCISED: {"gestation": 20},
            "chroma::daily": {}, "chroma::core": {},
            "private_thoughts": "absent", "audit_log": "absent"},
        "census_resolved_paths": {"private_thoughts": "/x", "audit_log": "/y"},
        "positive_control": {"verdict": "PASS", "interactions_returned": 20,
                             "interactions_raised": [],
                             "interactions_without_tail_passage": [],
                             "store_tail_invocations": 20,
                             "collections_grew": True},
        "ledger_post_migration_sha256": SHA_A,
        "ledger_post_replay_sha256": SHA_A,
        "ledger_post_replay_file_set": ["ledger.db", "ledger.db-shm",
                                        "ledger.db-wal"],
        "stray_stores_outside_projected_tree": [],
    }


def forced_on_run() -> dict:
    r = honest_run("partial")
    r["phase_probe"] = {"current_phase": "unknown", "has_resolve_api": True,
                        "resolve": {"phase": "unknown", "reason": "structural"}}
    r["stamp_census"] = {EXERCISED: {"None": 0}}
    r["env_after_import"] = {"values": {"MAEZ_S1_PHASE_TRUTH": "1"}}
    r["consumer_refusals"] = [{"consumer": "memory_manager@1506",
                               "exception": "PhaseUnknownRefusal"}]
    return r


def run_gate(tmp: Path, a: dict, p: dict, *, baseline=None, forced=None) -> dict:
    (tmp / "a.json").write_text(json.dumps(a))
    (tmp / "p.json").write_text(json.dumps(p))
    cmd = [sys.executable, str(GATE), "--run-a", str(tmp / "a.json"),
           "--run-p", str(tmp / "p.json"), "--out", str(tmp / "v.json")]
    if baseline is not None:
        (tmp / "b.json").write_text(json.dumps(baseline))
        cmd += ["--baseline-census", str(tmp / "b.json")]
    if forced is not None:
        (tmp / "f.json").write_text(json.dumps(forced))
        cmd += ["--forced-on", str(tmp / "f.json")]
    subprocess.run(cmd, capture_output=True, text=True)
    return json.loads((tmp / "v.json").read_text())


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="t5gate_"))
    ok = True
    A, P = honest_run("healthy"), honest_run("partial")
    pinned = {"per_fixture": {
        "healthy": {"current_phase": "gestation", EXERCISED: {"gestation": 20}},
        "partial": {"current_phase": "gestation", EXERCISED: {"gestation": 20}}}}

    def case(label, want, a=None, p=None, **kw):
        nonlocal ok
        v = run_gate(tmp, a or copy.deepcopy(A), p or copy.deepcopy(P), **kw)
        got = v["verdict"]
        good = got == want
        ok &= good
        extra = sorted(v.get("failures", {}))
        print(f"{'ok ' if good else 'BAD'} {label:46s} {got:5s} "
              f"(want {want}) {extra}")

    # The case that matters most: an honest run must PASS.
    case("honest pre-S1 run, other stores empty", "PASS")
    case("honest run against its own pinned baseline", "PASS", baseline=pinned)

    bad_pin = copy.deepcopy(pinned)
    bad_pin["per_fixture"]["partial"][EXERCISED] = {"gestation": 19}
    case("census drifted from the pinned baseline", "FAIL", baseline=bad_pin)

    a = copy.deepcopy(A); a["ledger_post_replay_sha256"] = "b" * 64
    case("K1 ledger main file changed", "FAIL", a=a)
    a = copy.deepcopy(A); del a["ledger_post_replay_sha256"]
    case("K1 digest key missing", "FAIL", a=a)

    p = copy.deepcopy(P)
    p["ledger_post_replay_file_set"] += ["segment-000001.jsonl"]
    case("K2 latch artifact on the partial fixture", "FAIL", p=p)

    a = copy.deepcopy(A)
    a["positive_control"]["interactions_without_tail_passage"] = ["s1-replay-07"]
    case("K3 forged PASS over a missed tail", "FAIL", a=a)
    a = copy.deepcopy(A)
    a["positive_control"] = {"verdict": "PASS"}
    case("K3 label with no underlying numbers", "FAIL", a=a)

    a = copy.deepcopy(A)
    a["stray_stores_outside_projected_tree"] = ["/tmp/escaped.db"]
    case("K4 store escaped the projected tree", "FAIL", a=a)

    a = copy.deepcopy(A); del a["phase_probe"]
    case("schema: phase probe missing", "FAIL", a=a)
    a = copy.deepcopy(A); a["stamp_census"] = {}
    case("schema: empty census", "FAIL", a=a)
    a = copy.deepcopy(A); a["stamp_census"] = {EXERCISED: {}}
    case("schema: exercised store produced no stamps", "FAIL", a=a)
    a = copy.deepcopy(A); a["fixture"] = "partial"
    case("both fixtures required, not two partials", "FAIL", a=a)

    p = copy.deepcopy(P); p["phase_probe"]["current_phase"] = "unknown"
    case("flags-off partial did not read gestation", "FAIL", p=p)

    p = copy.deepcopy(P); p["phase_probe"]["has_resolve_api"] = True
    case("resolve() exists but no forced-on run", "FAIL", p=p)

    case("correct forced-on run flips", "PASS",
         baseline=pinned, forced=forced_on_run())

    f = forced_on_run(); f["env_after_import"] = {"values": {}}
    case("forced-on lacks the activation flag", "FAIL",
         baseline=pinned, forced=f)
    f = forced_on_run(); f["consumer_refusals"] = []
    case("forced-on carries no refusal evidence", "FAIL",
         baseline=pinned, forced=f)
    f = forced_on_run(); f["fixture"] = "healthy"
    case("forced-on bound to the wrong fixture", "FAIL",
         baseline=pinned, forced=f)
    f = forced_on_run()
    f["phase_probe"]["resolve"] = {"phase": "gestation"}
    f["stamp_census"] = {EXERCISED: {"gestation": 20}}
    case("forced-on did not flip (guard absent)", "FAIL",
         baseline=pinned, forced=f)
    f = {"fixture": "partial",
         "phase_probe": {"resolve": {"phase": "unknown"}}}
    case("minimal forged forced-on report", "FAIL",
         baseline=pinned, forced=f)

    print("\nALL PASS" if ok else "\nSOME CASES FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
