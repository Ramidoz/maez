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
    "latch_artifacts_in_store_tree", "ledger_post_replay_file_set",
    "interaction_count",
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
        elif not isinstance(cen[EXERCISED_STORE], dict) or not any(
                isinstance(v, int) and v > 0
                for v in cen[EXERCISED_STORE].values()):
            # Round 19: {"gestation": 0} counted as a nonempty census.
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
    """Gate round 19 Q1.1: reading the ledger file set made K2 inert, because
    the driver fills it only with `ledger.db*` names. The driver now sweeps
    the whole store tree, and K2 consumes that."""
    bad = []
    for tag, r in runs.items():
        tree = r.get("latch_artifacts_in_store_tree")
        if not isinstance(tree, list):
            bad.append({"run": tag,
                        "detail": "store-tree latch sweep missing"})
        elif tree:
            bad.append({"run": tag, "detail": tree})
        fs = r.get("ledger_post_replay_file_set")
        if isinstance(fs, list):
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
        # Round 19: one represented interaction out of the frozen 20 passed.
        n = r.get("interaction_count")
        if not isinstance(n, int) or n < 1:
            bad.append({"run": tag, "detail": "interaction_count missing"})
        elif pc.get("interactions_returned") != n:
            bad.append({"run": tag,
                        "detail": "not every manifest interaction returned",
                        "returned": pc.get("interactions_returned"),
                        "expected": n})
        if pc.get("store_tail_invocations", 0) < (n if isinstance(n, int) else 1):
            bad.append({"run": tag,
                        "detail": "fewer tail passages than interactions",
                        "invocations": pc.get("store_tail_invocations")})
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
    """The comparison basis: the resolver's answer plus the FULL stamp census.

    Gate round 19 Q1.2: v7 compared only the exercised store, so a new
    flags-off write to `daily` passed as preserved behavior. Honest empty
    stores are exact baseline facts and belong in the comparison -- the
    honest-empty allowance belongs in the *schema* check (only the exercised
    store must be non-empty), not in what gets compared."""
    return {
        "current_phase": (r.get("phase_probe") or {}).get("current_phase"),
        "stamp_census": r.get("stamp_census"),
    }


def discriminator(runs: dict, baseline: dict | None,
                  forced: dict | None) -> tuple[str, list]:
    bad = []
    observed = {r["fixture"]: census_of(r) for r in runs.values()
                if isinstance(r.get("fixture"), str)}
    if set(observed) != {"healthy", "partial"}:
        return "FAIL", [{"detail": "both fixtures are required",
                         "observed": sorted(observed)}]

    if baseline is not None:
        # Round 19: an explicitly supplied `{}` bypassed comparison entirely.
        want = baseline.get("per_fixture")
        if not isinstance(want, dict) or set(want) != {"healthy", "partial"}:
            return "FAIL", [{"detail": "pinned baseline malformed"}]
        for fx in ("healthy", "partial"):
            if observed[fx] != want[fx]:
                bad.append({"fixture": fx, "detail": "census differs from the "
                                                     "pinned pre-S1 baseline",
                            "expected": want[fx], "got": observed[fx]})

    for fx in ("healthy", "partial"):
        # Round 19: only the partial fixture was required to read gestation,
        # so a healthy fixture reading `unknown` passed.
        if observed[fx].get("current_phase") != "gestation":
            bad.append({"fixture": fx,
                        "detail": "flags-off did not read gestation",
                        "got": observed[fx].get("current_phase")})
    probe_p = next((r.get("phase_probe") or {} for r in runs.values()
                    if r.get("fixture") == "partial"), {})
    if probe_p.get("current_phase") != "gestation":
        bad.append({"detail": "flags-off partial fixture did not read "
                              "gestation; the legacy behavior T5 must "
                              "preserve is not present",
                    "got": probe_p.get("current_phase")})

    if forced is not None:
        for k in ("fixture", "phase_probe", "stamp_census"):
            if k not in forced:
                bad.append({"detail": f"forced-on report missing {k!r}"})
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
    # Round 19: a forced-on run that still wrote 20 `unknown`-stamped rows
    # passed, which contradicts "every consumer refuses on unknown". Refusal
    # means no row at all.
    fstamps = (forced.get("stamp_census") or {}).get(EXERCISED_STORE)
    if isinstance(fstamps, dict) and any(
            isinstance(v, int) and v > 0 for v in fstamps.values()):
        bad.append({"detail": "forced-on run still wrote stamped rows; "
                              "refusal means no row",
                    "stamps": fstamps})
    for entry in (refusals if isinstance(refusals, list) else []):
        if not isinstance(entry, dict) or \
                entry.get("exception") != "PhaseUnknownRefusal":
            bad.append({"detail": "refusal evidence is not a "
                                  "PhaseUnknownRefusal record",
                        "entry": entry})
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
