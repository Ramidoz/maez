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
        "latch_artifacts_in_store_tree": [],
        "interaction_count": 20,
    }


def forced_on_run() -> dict:
    r = honest_run("partial")
    r["forced_on"] = True
    r["manifest_sha256"] = ("2b9faf616941bb6a0ab6294e1323e2dd73cb57389ab021"
                            "cc2b868f59109cb420")
    r["interactions"] = [
        {"id": f"s1-replay-{i:02d}", "outcome": "raised",
         "exception": "PhaseUnknownRefusal: refusing to stamp a phase — "
                      "the resolver reads unknown (structural).",
         "tail_passages": 1}
        for i in range(20)]
    r["positive_control"] = {"mode": "forced_on", "verdict": "PASS",
                             "refusals_observed": 20}
    r["phase_probe"] = {"current_phase": "unknown", "has_resolve_api": True,
                        "resolve": {"phase": "unknown", "reason": "structural"}}
    r["stamp_census"] = {EXERCISED: {}, "chroma::daily": {},
                         "chroma::core": {}, "private_thoughts": {},
                         "audit_log": {}}
    r["env_after_import"] = {"values": {"MAEZ_S1_PHASE_TRUTH": "1"}}
    r["collection_counts_before"] = {"raw": 0, "daily": 0, "core": 0}
    r["collection_counts_after"] = {"raw": 0, "daily": 0, "core": 0}
    r["consumer_refusals"] = [
        {"consumer": "memory_manager.store_telegram",
         "exception": "PhaseUnknownRefusal",
         "message": "memory_manager.store_telegram: refusing to stamp a "
                    "phase — the resolver reads unknown (structural)."}
        for _ in range(20)]
    return r


_CASE = [0]


def run_gate(tmp: Path, a: dict, p: dict, *, baseline=None, forced=None) -> dict:
    """Gate round 19: the first version reused one verdict path and ignored
    the return code, so a crash on an expected-FAIL case could inherit a
    stale FAIL and look correct. Each case gets its own directory, and the
    exit status must agree with the written verdict."""
    _CASE[0] += 1
    d = tmp / f"case{_CASE[0]:02d}"
    d.mkdir()
    (d / "a.json").write_text(json.dumps(a))
    (d / "p.json").write_text(json.dumps(p))
    cmd = [sys.executable, str(GATE), "--run-a", str(d / "a.json"),
           "--run-p", str(d / "p.json"), "--out", str(d / "v.json")]
    if baseline is not None:
        (d / "b.json").write_text(json.dumps(baseline))
        cmd += ["--baseline-census", str(d / "b.json")]
    if forced is not None:
        (d / "f.json").write_text(json.dumps(forced))
        cmd += ["--forced-on", str(d / "f.json")]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not (d / "v.json").exists():
        return {"verdict": "CRASH", "failures": {"stderr": proc.stderr[-400:]}}
    v = json.loads((d / "v.json").read_text())
    expected_rc = 0 if v["verdict"] == "PASS" else 1
    if proc.returncode != expected_rc:
        return {"verdict": "RC-MISMATCH",
                "failures": {"rc": proc.returncode, "verdict": v["verdict"]}}
    return v


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="t5gate_"))
    ok = True
    A, P = honest_run("healthy"), honest_run("partial")
    def cen(fx):
        r = honest_run(fx)
        return {"current_phase": "gestation", "stamp_census": r["stamp_census"]}
    pinned = {"per_fixture": {"healthy": cen("healthy"),
                              "partial": cen("partial")}}

    def case(label, want, a=None, p=None, **kw):
        nonlocal ok
        v = run_gate(tmp, a or copy.deepcopy(A), p or copy.deepcopy(P), **kw)
        got = v["verdict"]
        good = got == want
        ok &= good
        extra = sorted(v.get("failures", {}))
        print(f"{'ok ' if good else 'BAD'} {label:46s} {got:5s} "
              f"(want {want}) {extra}")

    # The case that matters most: an honest run WITH its pinned baseline
    # must PASS. Without one it must now FAIL — the baseline census is a
    # committed artifact as of protocol v7.1, so an omitted comparison is a
    # skipped comparison, not a pre-baseline state (gate round 20, F-3).
    # This case asserted PASS until the baseline existed; the flip is the
    # transition happening, not a regression.
    case("honest run, baseline omitted (now mandatory)", "FAIL")
    case("honest run against its own pinned baseline", "PASS", baseline=pinned)

    bad_pin = copy.deepcopy(pinned)
    bad_pin["per_fixture"]["partial"]["stamp_census"][EXERCISED] = {"gestation": 19}
    case("census drifted from the pinned baseline", "FAIL", baseline=bad_pin)

    a = copy.deepcopy(A); a["ledger_post_replay_sha256"] = "b" * 64
    case("K1 ledger main file changed", "FAIL", a=a)
    a = copy.deepcopy(A); del a["ledger_post_replay_sha256"]
    case("K1 digest key missing", "FAIL", a=a)

    p = copy.deepcopy(P)
    p["latch_artifacts_in_store_tree"] = ["birth_observed/segment-000001.jsonl"]
    case("K2 real latch artifact in the store tree", "FAIL", p=p)
    p = copy.deepcopy(P); del p["latch_artifacts_in_store_tree"]
    case("K2 store-tree latch sweep missing", "FAIL", p=p)

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
    a = copy.deepcopy(A); a["phase_probe"]["current_phase"] = "unknown"
    case("flags-off HEALTHY did not read gestation", "FAIL", a=a)

    case("explicitly empty baseline must not bypass", "FAIL", baseline={})

    a = copy.deepcopy(A); a["stamp_census"][EXERCISED] = {"gestation": 0}
    case("zero-count census is not a census", "FAIL", a=a)

    a = copy.deepcopy(A); a["positive_control"]["interactions_returned"] = 1
    case("one interaction of twenty returned", "FAIL", a=a)
    a = copy.deepcopy(A); a["positive_control"]["store_tail_invocations"] = 1
    case("fewer tail passages than interactions", "FAIL", a=a)

    a = copy.deepcopy(A)
    a["stamp_census"]["chroma::daily"] = {"gestation": 1}
    case("a new write to a store outside raw", "FAIL", a=a, baseline=pinned)

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
    f = forced_on_run(); f["stamp_census"] = {EXERCISED: {"unknown": 20}}
    case("forced-on wrote unknown-stamped rows", "FAIL",
         baseline=pinned, forced=f)
    f = forced_on_run(); f["consumer_refusals"] = [{"exception": "ValueError"}]
    case("refusal evidence is the wrong exception", "FAIL",
         baseline=pinned, forced=f)
    f = {"fixture": "partial",
         "phase_probe": {"resolve": {"phase": "unknown"}}}
    case("minimal forged forced-on report", "FAIL",
         baseline=pinned, forced=f)

    # Gate round 21's executed forgery family: right names, wrong facts.
    f = forced_on_run()
    f["collection_counts_after"] = {"raw": 999, "daily": 0, "core": 0}
    case("forgery: growth hidden in raw counts", "FAIL",
         baseline=pinned, forced=f)
    f = forced_on_run()
    f["consumer_refusals"] = [{"consumer": "x",
                               "exception": "PhaseUnknownRefusal"}]
    case("forgery: named exception, no message, wrong count", "FAIL",
         baseline=pinned, forced=f)
    f = forced_on_run(); del f["interaction_count"]
    case("forgery: interaction_count stripped", "FAIL",
         baseline=pinned, forced=f)

    # Gate round 22's executed forgery: coherent aggregates over rotten raw
    # records — one returned interaction with zero tail passages, an FAIL
    # positive control, a wrong manifest hash.
    f = forced_on_run()
    f["interactions"][7] = {"id": "s1-replay-07", "outcome": "returned",
                            "tail_passages": 0}
    case("forgery: one raw interaction returned, no tail", "FAIL",
         baseline=pinned, forced=f)
    f = forced_on_run()
    f["positive_control"]["verdict"] = "FAIL"
    case("forgery: producer control FAIL under clean aggregates", "FAIL",
         baseline=pinned, forced=f)
    f = forced_on_run()
    f["manifest_sha256"] = "0" * 64
    case("forgery: unbound manifest", "FAIL", baseline=pinned, forced=f)
    f = forced_on_run()
    f["interactions"] = f["interactions"][:19]
    case("forgery: raw list one short of declared count", "FAIL",
         baseline=pinned, forced=f)

    print("\nALL PASS" if ok else "\nSOME CASES FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
