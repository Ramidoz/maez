#!/usr/bin/env python3
"""Theme 2 S1 — T5 gate decision (protocol §12.8, v7).

Cut to the discriminator on the owner's ruling after gate round 18.

Seven gate rounds hardened the scaffolding around this witness; round 18
executed synthetic controls against the first version of this file and
found it failed an HONEST run (G3 demanded stamps from stores the T5 path
never writes -- `store_telegram` writes `raw` only) while passing several
dishonest ones. The lesson taken: witness only what this path actually
reaches, and let T1 and T3 witness the rest.

Four kills, plus the discriminator:

    K1  the ledger main file is unchanged
    K2  no latch artifact anywhere
    K3  the positive controls passed on every flags-off run
    K4  no store landed outside the projected tree
    D   the discriminator: flags-off reproduces the pinned census
        exactly; once S1 exists, forced-on against the PARTIAL fixture
        must flip

Everything else -- the byte projection, HNSW layout, embedding vectors,
cross-store counts, the volatile derivation -- is forensic. It is
computed and recorded, and it never decides.

    theme2_s1_t5_gate.py --run-a A.json --run-p P.json \
        [--baseline-census c.json] [--forced-on F.json] --out verdict.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LATCH_MARKERS = ("birth_observed", "segment-", ".tmp")

# The only store this T5 path writes. `MemoryManager.store_telegram`
# (memory_manager.py:1576) adds to `raw` and nothing else, and T5 reaches
# exactly one of the thirteen census consumers. A census showing daily,
# core, private_thoughts or audit_log empty is therefore HONEST, and a gate
# that rejects it is broken -- which is what round 18 executed.
EXERCISED_STORE = "chroma::raw"

REQUIRED_RUN_KEYS = (
    "fixture", "phase_probe", "stamp_census", "positive_control",
    "ledger_post_migration_sha256", "ledger_post_replay_sha256",
    "stray_stores_outside_projected_tree", "census_resolved_paths",
)


def load(p: str | None) -> dict | None:
    return json.loads(Path(p).read_text()) if p else None


def schema_failures(runs: dict) -> list:
    """Fail closed on shape. Round 18 passed a report with a missing phase
    probe and empty structures; absent evidence is not evidence."""
    bad = []
    for tag, r in runs.items():
        if not isinstance(r, dict):
            bad.append({"run": tag, "detail": "report is not an object"})
            continue
        for k in REQUIRED_RUN_KEYS:
            if k not in r:
                bad.append({"run": tag, "detail": f"missing key {k!r}"})
        probe = r.get("phase_probe")
        if not isinstance(probe, dict) or "current_phase" not in probe:
            bad.append({"run": tag, "detail": "phase_probe absent or malformed"})
        cen = r.get("stamp_census")
        if not isinstance(cen, dict) or EXERCISED_STORE not in cen:
            bad.append({"run": tag,
                        "detail": f"stamp_census missing {EXERCISED_STORE!r}"})
        elif not isinstance(cen[EXERCISED_STORE], dict) or not cen[EXERCISED_STORE]:
            bad.append({"run": tag,
                        "detail": f"{EXERCISED_STORE} produced no stamps"})
    return bad


def k1_ledger_unchanged(runs: dict) -> list:
    bad = []
    for tag, r in runs.items():
        pre, post = (r.get("ledger_post_migration_sha256"),
                     r.get("ledger_post_replay_sha256"))
        if not isinstance(pre, str) or not isinstance(post, str) or len(pre) != 64:
            bad.append({"run": tag, "detail": "ledger digests missing/malformed"})
        elif pre != post:
            bad.append({"run": tag, "pre": pre, "post": post})
    return bad


def k2_no_latch(runs: dict) -> list:
    bad = []
    for tag, r in runs.items():
        fs = r.get("ledger_post_replay_file_set")
        if not isinstance(fs, list):
            bad.append({"run": tag, "detail": "ledger file set missing"})
            continue
        for name in fs:
            if any(m in name for m in LATCH_MARKERS):
                bad.append({"run": tag, "detail": name})
    return bad


def k3_positive_controls(runs: dict) -> list:
    """The label is not the fact. Round 18 forged a PASS label over false
    underlying numbers, so the numbers are re-derived here."""
    bad = []
    for tag, r in runs.items():
        pc = r.get("positive_control")
        if not isinstance(pc, dict):
            bad.append({"run": tag, "detail": "no positive control"})
            continue
        if pc.get("verdict") != "PASS":
            bad.append({"run": tag, "positive_control": pc})
            continue
        if pc.get("interactions_raised"):
            bad.append({"run": tag, "detail": "interactions raised",
                        "ids": pc["interactions_raised"]})
        if pc.get("interactions_without_tail_passage"):
            bad.append({"run": tag, "detail": "interactions never reached the tail",
                        "ids": pc["interactions_without_tail_passage"]})
        if not isinstance(pc.get("interactions_returned"), int) \
                or pc["interactions_returned"] < 1:
            bad.append({"run": tag, "detail": "no interactions returned"})
        if not pc.get("collections_grew"):
            bad.append({"run": tag, "detail": "no collection grew"})
    return bad


def k4_no_stray_store(runs: dict) -> list:
    bad = []
    for tag, r in runs.items():
        strays = r.get("stray_stores_outside_projected_tree")
        if not isinstance(strays, list):
            bad.append({"run": tag, "detail": "stray-store sweep missing"})
        elif strays:
            bad.append({"run": tag, "strays": strays})
    return bad


def census_of(r: dict) -> dict:
    """The comparison basis: the resolver's answer plus the stamps of the one
    store this path exercises. Narrow on purpose -- everything wider was
    either honestly empty or T3's job."""
    return {
        "current_phase": (r.get("phase_probe") or {}).get("current_phase"),
        EXERCISED_STORE: (r.get("stamp_census") or {}).get(EXERCISED_STORE),
    }


def discriminator(runs: dict, baseline: dict | None,
                  forced: dict | None) -> tuple[str, list]:
    bad = []
    observed = {r["fixture"]: census_of(r) for r in runs.values()
                if isinstance(r.get("fixture"), str)}
    if set(observed) != {"healthy", "partial"}:
        return "FAIL", [{"detail": "both fixtures are required",
                         "observed": sorted(observed)}]

    if baseline:
        want = baseline.get("per_fixture")
        if not isinstance(want, dict) or set(want) != {"healthy", "partial"}:
            return "FAIL", [{"detail": "pinned baseline malformed"}]
        for fx in ("healthy", "partial"):
            if observed[fx] != want[fx]:
                bad.append({"fixture": fx, "detail": "census differs from the "
                                                     "pinned pre-S1 baseline",
                            "expected": want[fx], "got": observed[fx]})

    probe_p = next((r.get("phase_probe") or {} for r in runs.values()
                    if r.get("fixture") == "partial"), {})
    if probe_p.get("current_phase") != "gestation":
        bad.append({"detail": "flags-off partial fixture did not read "
                              "gestation; the legacy behavior T5 must "
                              "preserve is not present",
                    "got": probe_p.get("current_phase")})

    if forced is None:
        if probe_p.get("has_resolve_api"):
            return "FAIL", bad + [{"detail": "birth_phase.resolve exists but "
                                             "no forced-on run was supplied; "
                                             "the discriminator is mandatory "
                                             "once S1 exists"}]
        return ("NOT-APPLICABLE" if not bad else "FAIL"), bad

    # A forced-on run must be bound to the fixture and the flag, and must
    # carry refusal evidence -- round 18 passed a minimal forged report.
    if forced.get("fixture") != "partial":
        bad.append({"detail": "forced-on run is not against the partial fixture",
                    "got": forced.get("fixture")})
    env = (forced.get("env_after_import") or {}).get("values") or {}
    if env.get("MAEZ_S1_PHASE_TRUTH") != "1":
        bad.append({"detail": "forced-on run does not carry "
                              "MAEZ_S1_PHASE_TRUTH=1 in its recorded "
                              "post-import environment"})
    res = (forced.get("phase_probe") or {}).get("resolve") or {}
    if res.get("phase") != "unknown":
        bad.append({"detail": "forced-on resolver did not read unknown",
                    "resolve": res})
    refusals = forced.get("consumer_refusals")
    if not isinstance(refusals, list) or not refusals:
        bad.append({"detail": "forced-on run recorded no PhaseUnknownRefusal "
                              "evidence"})
    fc = census_of(forced)
    if fc == observed["partial"]:
        bad.append({"detail": "forced-on census is identical to the flags-off "
                              "census: the guard is not there"})
    stamps = fc.get(EXERCISED_STORE)
    if isinstance(stamps, dict) and stamps.get("gestation"):
        bad.append({"detail": "forced-on run still stamped gestation",
                    "stamps": stamps})
    return ("PASS" if not bad else "FAIL"), bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", required=True)
    ap.add_argument("--run-p", required=True)
    ap.add_argument("--baseline-census")
    ap.add_argument("--forced-on")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    runs = {"a": load(a.run_a), "p": load(a.run_p)}
    schema = schema_failures(runs)
    if schema:
        verdict = {"verdict": "FAIL", "failures": {"schema": schema}}
        Path(a.out).write_text(json.dumps(verdict, indent=1, sort_keys=True) + "\n")
        print(json.dumps(verdict, indent=1))
        return 1

    dv, dbad = discriminator(runs, load(a.baseline_census), load(a.forced_on))
    clauses = {
        "K1_ledger_unchanged": k1_ledger_unchanged(runs),
        "K2_no_latch_artifact": k2_no_latch(runs),
        "K3_positive_controls": k3_positive_controls(runs),
        "K4_no_stray_store": k4_no_stray_store(runs),
    }
    failures = {k: v for k, v in clauses.items() if v}
    if dbad:
        failures["D_discriminator"] = dbad
    verdict = {
        "clauses": {k: ("PASS" if not v else "FAIL") for k, v in clauses.items()},
        "D_discriminator": dv,
        "failures": failures,
        "pinned_census": {"per_fixture": {
            r["fixture"]: census_of(r) for r in runs.values()}},
        "verdict": "PASS" if not failures else "FAIL",
    }
    Path(a.out).write_text(json.dumps(verdict, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in verdict.items()
                      if k != "pinned_census"}, indent=1))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
