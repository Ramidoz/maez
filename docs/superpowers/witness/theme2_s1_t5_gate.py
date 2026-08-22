#!/usr/bin/env python3
"""Theme 2 S1 — T5 gate decision (protocol §12.8, clauses G1..G6).

Gate round 17 found the gate/forensic split declared in prose but absent
from the executable: the orchestrator still let physical projection
differences block publication, while the clauses that actually matter --
ledger unchanged, no latch artifact, the stamp census, record counts --
were recorded but never decided anything. This file is the missing
authority. It consumes the run reports and projections, decides G1..G6,
and exits non-zero on any failure. Nothing else may gate.

    theme2_s1_t5_gate.py --run-a A.json --run-b B.json --run-p P.json \
        --proj-a pa.json --proj-b pb.json [--baseline-census c.json] \
        [--forced-on F.json] --out verdict.json

Pre-S1 there is no forced-on run: G5 records `not-applicable` and the
census this run pins becomes the basis it will later be measured against.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LATCH_MARKERS = ("birth_observed", "segment-", ".tmp")


def load(p: str | None) -> dict | None:
    return json.loads(Path(p).read_text()) if p else None


def g1_no_latch(runs: dict, projs: dict) -> list:
    bad = []
    for tag, pj in projs.items():
        if pj.get("latch_artifacts"):
            bad.append({"tree": tag, "detail": pj["latch_artifacts"]})
    for tag, r in runs.items():
        for name in r.get("ledger_post_replay_file_set", []):
            if any(m in name for m in LATCH_MARKERS):
                bad.append({"run": tag, "detail": name})
    return bad


def g2_ledger_unchanged(runs: dict) -> list:
    bad = []
    for tag, r in runs.items():
        pre = r.get("ledger_post_migration_sha256")
        post = r.get("ledger_post_replay_sha256")
        if not pre or not post:
            bad.append({"run": tag, "detail": "digest missing from the report"})
        elif pre != post:
            bad.append({"run": tag, "pre": pre, "post": post})
    return bad


def g3_stamp_census(runs: dict, baseline: dict | None) -> list:
    """The census must be well formed on every run, agree between the two
    healthy runs, and -- once a baseline exists -- match it exactly per
    fixture. Fail-closed: a store reported `absent` or `error` is a
    failure, not a fact (gate round 17, M(ii))."""
    bad = []
    for tag, r in runs.items():
        cen = r.get("stamp_census")
        if not isinstance(cen, dict) or not cen:
            bad.append({"run": tag, "detail": "no stamp census"})
            continue
        for store, val in sorted(cen.items()):
            if not isinstance(val, dict):
                bad.append({"run": tag, "store": store, "detail": str(val)})
            elif not val:
                bad.append({"run": tag, "store": store,
                            "detail": "store produced no stamps"})
    a, b = runs.get("a", {}).get("stamp_census"), runs.get("b", {}).get("stamp_census")
    if a is not None and b is not None and a != b:
        bad.append({"detail": "healthy runs a and b disagree",
                    "a": a, "b": b})
    if baseline:
        for fixture, want in baseline.get("per_fixture", {}).items():
            tag = {"healthy": "a", "partial": "p"}.get(fixture)
            got = runs.get(tag, {}).get("stamp_census")
            if got != want:
                bad.append({"detail": f"{fixture} census differs from the "
                                      f"pinned baseline",
                            "expected": want, "got": got})
    return bad


def g4_counts(runs: dict) -> list:
    bad = []
    a = runs.get("a", {}).get("collection_counts_after")
    b = runs.get("b", {}).get("collection_counts_after")
    if a is None or b is None:
        bad.append({"detail": "collection counts missing"})
    elif a != b:
        bad.append({"detail": "healthy runs disagree on counts",
                    "a": a, "b": b})
    for tag, r in runs.items():
        for k, v in (r.get("collection_counts_after") or {}).items():
            if not isinstance(v, int):
                bad.append({"run": tag, "collection": k, "detail": str(v)})
    return bad


def g5_discriminator(runs: dict, forced: dict | None) -> tuple[str, list]:
    """The dormancy proof. Pre-S1 it is not applicable; once S1 exists a
    forced-on run against the PARTIAL fixture must NOT match the baseline
    -- the resolver must read unknown and the consumers must refuse."""
    p = runs.get("p")
    if p is None:
        return "FAIL", [{"detail": "no partial-fixture run"}]
    probe = p.get("phase_probe") or {}
    if forced is None:
        if probe.get("has_resolve_api"):
            return "FAIL", [{"detail": "the S1 resolve() API exists but no "
                                       "forced-on run was supplied; G5 is "
                                       "mandatory once S1 exists"}]
        return "NOT-APPLICABLE", []
    fp = forced.get("phase_probe") or {}
    if (fp.get("resolve") or {}).get("phase") != "unknown":
        return "FAIL", [{"detail": "forced-on resolver did not read unknown "
                                   "on the partial fixture",
                         "resolve": fp.get("resolve")}]
    if forced.get("stamp_census") == p.get("stamp_census"):
        return "FAIL", [{"detail": "forced-on census is identical to the "
                                   "flags-off census: the guard is not there"}]
    gest = [s for s, v in (forced.get("stamp_census") or {}).items()
            if isinstance(v, dict) and v.get("gestation")]
    if gest:
        return "FAIL", [{"detail": "forced-on run still stamped gestation",
                         "stores": gest}]
    return "PASS", []


def g6_positive_controls(runs: dict) -> list:
    bad = []
    for tag, r in runs.items():
        pc = r.get("positive_control") or {}
        if pc.get("verdict") != "PASS":
            bad.append({"run": tag, "positive_control": pc})
    return bad


def g7_logical_store_content(projs: dict) -> list:
    """Gate round 17 finding N: logical P2 content -- documents, non-volatile
    metadata, embeddings -- can regress recall while phase stamps and counts
    stay put. That belongs in the gate. Physical HNSW bytes stay forensic."""
    bad = []
    a, b = projs.get("a"), projs.get("b")
    if a is None or b is None:
        return [{"detail": "healthy projections missing"}]
    xa, xb = a.get("extract"), b.get("extract")
    if xa is None or xb is None:
        return [{"detail": "the Chroma extract is mandatory on both runs"}]
    ca, cb = xa.get("collections", {}), xb.get("collections", {})
    if set(ca) != set(cb):
        bad.append({"detail": "collection sets differ",
                    "only_a": sorted(set(ca) - set(cb)),
                    "only_b": sorted(set(cb) - set(ca))})
    for k in sorted(set(ca) & set(cb)):
        for side, c in (("a", ca[k]), ("b", cb[k])):
            if "error" in c:
                bad.append({"collection": k, "tree": side,
                            "detail": c["error"]})
        if ca[k].get("count") != cb[k].get("count"):
            bad.append({"collection": k, "detail": "count differs",
                        "a": ca[k].get("count"), "b": cb[k].get("count")})
        if ca[k].get("vector_sha256") != cb[k].get("vector_sha256"):
            bad.append({"collection": k, "detail": "embedding vectors differ"})
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    for f in ("run-a", "run-b", "run-p", "proj-a", "proj-b"):
        ap.add_argument(f"--{f}", required=True)
    ap.add_argument("--baseline-census")
    ap.add_argument("--forced-on")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    runs = {"a": load(a.run_a), "b": load(a.run_b), "p": load(a.run_p)}
    projs = {"a": load(a.proj_a), "b": load(a.proj_b)}
    baseline = load(a.baseline_census)
    forced = load(a.forced_on)

    g5v, g5bad = g5_discriminator(runs, forced)
    clauses = {
        "G1_no_latch_artifact": g1_no_latch(runs, projs),
        "G2_ledger_unchanged": g2_ledger_unchanged(runs),
        "G3_stamp_census": g3_stamp_census(runs, baseline),
        "G4_record_counts": g4_counts(runs),
        "G6_positive_controls": g6_positive_controls(runs),
        "G7_logical_store_content": g7_logical_store_content(projs),
    }
    failures = {k: v for k, v in clauses.items() if v}
    if g5bad:
        failures["G5_discriminator"] = g5bad
    verdict = {
        "clauses": {k: ("PASS" if not v else "FAIL") for k, v in clauses.items()},
        "G5_discriminator": g5v,
        "failures": failures,
        # The census this run pins, so a later run can be compared to it
        # exactly rather than to a re-derived approximation.
        "pinned_census": {"per_fixture": {
            "healthy": runs["a"].get("stamp_census"),
            "partial": runs["p"].get("stamp_census")}},
        "verdict": "PASS" if not failures else "FAIL",
    }
    Path(a.out).write_text(json.dumps(verdict, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in verdict.items()
                      if k != "pinned_census"}, indent=1))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
