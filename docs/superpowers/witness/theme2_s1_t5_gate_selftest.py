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
PINNED_BASELINE = json.loads(
    (Path(__file__).resolve().parent / "theme2-s1-baseline-census.json").read_text())
SHA_A = "a" * 64
EXERCISED = "chroma::raw"
# Round 27 #13/#16: the constants the judge now pins.
F_PARTIAL = ("87921737ab54cc9d5effb069a1d16f5ec53c33a0f5321384"
             "cef39472a4c2d5a2")
SWEEP_ROOTS = {"/home/rohit/maez/logs", "/home/rohit/maez/.cache",
               "/home/rohit", "/tmp", "/run", "/var/tmp"}


def honest_run(fixture: str) -> dict:
    """What a correct pre-S1 flags-off run actually looks like: raw stamped,
    every other store legitimately empty, because store_telegram writes raw
    only and T5 reaches one of thirteen consumers."""
    return {
        "fixture": fixture,
        # every real run carries the raw manifest-joined rows (round 24)
        "interactions": [
            # Round 29 #28: two fixtures must differ in what they OBSERVED,
            # so the reference records differ the way real ones do.
            {"id": f"s1-replay-{i:02d}", "outcome": "returned",
             "tail_passages": 1,
             "reply": f"a reply on the {fixture} fixture"} for i in range(20)],
        "manifest_sha256": ("2b9faf616941bb6a0ab6294e1323e2dd73cb57389ab021"
                            "cc2b868f59109cb420"),
        # Round 28 finding #21: this record said the S1 API was ABSENT, so all
        # 68 cases mutated off a reference that proved a tautology — a pre-S1
        # tree reproducing the pre-S1 baseline. Dormant means present and
        # silent. The real runs always carried the resolver; the fixture did
        # not, and only the real evidence happened to be the honest one.
        "phase_probe": {"current_phase": "gestation",
                        "birth_event_turn_id": None,
                        "has_resolve_api": True,
                        "resolve": {"phase": "gestation", "reason": "dormant"}},
        # Round 25: the judge now pins the committed baseline's identity, so
        # the synthetic honest run must mirror that artifact rather than an
        # idealized census of its own invention.
        "stamp_census": copy.deepcopy(
            PINNED_BASELINE["per_fixture"][fixture]["stamp_census"]),
        "census_resolved_paths": {"private_thoughts": "/x", "audit_log": "/y"},
        # Round 27 self-attack: the judge now READS the premises the producer
        # was already recording — flag off, run contained, coherent span.
        "flags_off_after_import": "PASS",
        "env_after_import": {"names": ["HOME"], "values": {"HOME": "/home/rohit/maez"}},
        "env_after_config_load": {"names": ["HOME"], "values": {"HOME": "/home/rohit/maez"}},
        "containment": {"repo_readonly": "PASS",
                        "memory_writable_and_empty": "PASS",
                        "network_unreachable": "PASS",
                        "no_maez_env_at_entry": "PASS",
                        "env_at_entry": {"names": ["HOME"], "values": {}}},
        "started_at": 1000.0 + (0.0 if fixture == "healthy" else 100.0),
        "finished_at": 1030.0 + (0.0 if fixture == "healthy" else 100.0),
        "store_tail_invocations": 20,
        "brain_reachable": False,
        "daemon_construct_seconds": 2.5,
        "python": "3.14.0", "sqlite_version": "3.53.4", "protocol": "t5.v7",
        # Round 29 #30: the evidence must name the code it is about.
        "source_digests": {"core/memory/birth_phase.py": "c" * 64,
                           "memory/memory_manager.py": "d" * 64},
        "effective_store_paths_after_import": {"memory_dir": "/home/rohit/maez/memory"},
        "census_resolved_paths": {"private_thoughts": "/home/rohit/maez/memory/pt.db"},
        "collection_counts_before": {"raw": 0, "daily": 0, "core": 0},
        "collection_counts_after": {"raw": 20, "daily": 0, "core": 0},
        "positive_control": {"verdict": "PASS", "interactions_returned": 20,
                             "interactions_raised": [],
                             "interactions_without_tail_passage": [],
                             "store_tail_invocations": 20,
                             "collections_grew": True},
        "ledger_post_migration_sha256": (F_PARTIAL if fixture == "partial"
                                         else SHA_A),
        "ledger_post_replay_sha256": (F_PARTIAL if fixture == "partial"
                                      else SHA_A),
        "ledger_post_replay_file_set": ["ledger.db", "ledger.db-shm",
                                        "ledger.db-wal"],
        "stray_stores_outside_projected_tree": [],
        "stray_store_sweep_roots": sorted(SWEEP_ROOTS),
        "latch_artifacts_in_store_tree": [],
        "interaction_count": 20,
    }


def forced_on_run() -> dict:
    r = honest_run("partial")
    r["forced_on"] = True
    r["manifest_sha256"] = ("2b9faf616941bb6a0ab6294e1323e2dd73cb57389ab021"
                            "cc2b868f59109cb420")
    r["store_tail_invocations"] = 20
    r["positive_control_seed"] = None
    r["interactions"] = [
        {"id": f"s1-replay-{i:02d}", "outcome": "raised",
         "exception": "PhaseUnknownRefusal: memory_manager.store_telegram: "
                      "refusing to stamp a phase — the resolver reads "
                      "unknown (structural).",
         "tail_passages": 1}
        for i in range(20)]
    r["positive_control"] = {"mode": "forced_on", "verdict": "PASS",
                             "refusals_observed": 20,
                             "collections_grew": False,
                             "all_refusals_typed": True,
                             "stores_with_gestation_stamps": []}
    r["phase_probe"] = {"current_phase": "unknown", "has_resolve_api": True,
                        "resolve": {"phase": "unknown", "reason": "structural"}}
    r["stamp_census"] = {EXERCISED: {}, "chroma::daily": {},
                         "chroma::core": {}, "private_thoughts": {},
                         "audit_log": {}}
    r["env_after_import"] = {"names": ["HOME", "MAEZ_S1_PHASE_TRUTH"],
                             "values": {"MAEZ_S1_PHASE_TRUTH": "1"}}
    r["started_at"], r["finished_at"] = 1200.0, 1230.0
    r["collection_counts_before"] = {"raw": 0, "daily": 0, "core": 0}
    r["collection_counts_after"] = {"raw": 0, "daily": 0, "core": 0}
    r["consumer_refusals"] = [
        {"consumer": "memory_manager.store_telegram",
         "exception": "PhaseUnknownRefusal",
         "message": "memory_manager.store_telegram: refusing to stamp a "
                    "phase — the resolver reads unknown (structural)."}
        for _ in range(20)]
    return r


# Gate round 26: 26 expected-FAIL cases carried no clause assertion, so
# "every negative is isolated" was not literally true. Rather than annotate
# each call site — where the next new case would simply forget again — every
# FAIL case must declare its EXACT failure set here, and an undeclared one
# fails loudly. Omission is now impossible, not merely discouraged.
EXPECTED_CLAUSES = {
    "K1 digest key missing (schema stage)":
        ["schema"],
    "K1 ledger main file changed":
        ["K1_ledger_unchanged"],
    "K2 real latch artifact in the store tree":
        ["K2_no_latch_artifact"],
    "K2 store-tree latch sweep missing (schema stage)":
        ["schema"],
    "K3 forged PASS over a missed tail":
        ["K3_positive_controls"],
    "K3 label with no underlying numbers":
        ["K3_positive_controls"],
    "K4 store escaped the projected tree":
        ["K4_no_stray_store"],
    "a new write to a store outside raw":
        ["D_discriminator"],
    "both fixtures required, not two partials":
        ["D_discriminator", "K7_fixture_label_backed"],
    "explicitly empty baseline must not bypass":
        ["D_discriminator"],
    "fewer tail passages than interactions":
        ["K3_positive_controls"],
    "flags-off HEALTHY did not read gestation":
        ["schema"],
    "flags-off partial did not read gestation":
        ["schema"],
    "forced-on bound to the wrong fixture":
        ["D_discriminator", "K7_fixture_label_backed"],
    "forced-on carries no refusal evidence":
        ["D_discriminator"],
    "forced-on did not flip (guard absent)":
        ["D_discriminator"],
    "forced-on lacks the activation flag":
        ["D_discriminator", "K5_flags_were_off"],
    "forced-on wrote unknown-stamped rows":
        ["D_discriminator"],
    "forgery: alien id passing the shape check":
        ["D_discriminator"],
    "forgery: growth hidden in raw counts":
        ["D_discriminator"],
    "forgery: interaction_count stripped":
        ["D_discriminator"],
    "forgery: named exception, no message, wrong count":
        ["D_discriminator"],
    "forgery: one raw interaction returned, no tail":
        ["D_discriminator", "K8_record_coherence"],
    "forgery: producer control FAIL under clean aggregates":
        ["D_discriminator"],
    "forgery: raw list one short of declared count":
        ["D_discriminator"],
    "forgery: unbound manifest":
        ["D_discriminator"],
    "honest run, baseline omitted (now mandatory)":
        ["D_discriminator"],
    "minimal forged forced-on report":
        ["D_discriminator", "K1_ledger_unchanged", "K2_no_latch_artifact", "K4_no_stray_store", "K5_flags_were_off", "K6_contained_and_distinct", "K7_fixture_label_backed", "K8_record_coherence"],
    "one interaction of twenty returned":
        ["K3_positive_controls"],
    "refusal evidence is the wrong exception":
        ["D_discriminator"],
    "resolve() exists but no forced-on run":
        ["D_discriminator"],
    "round 25: alien raw consumer under a clean list":
        ["D_discriminator"],
    "round 25: baseline unbound from the archive":
        ["D_discriminator"],
    "round 25: doctored baseline supplied":
        ["D_discriminator"],
    "round 25: forced-on census emptied":
        ["D_discriminator"],
    "round 25: nothing stored, aggregate says it grew":
        ["K3_positive_controls"],
    "round 25: raw row contradicts clean aggregate":
        ["K3_positive_controls"],
    "round 26: Boolean tail counts":
        ["D_discriminator"],
    "round 26: co-mutated to a different KNOWN consumer":
        ["D_discriminator"],
    "round 26: decoy key satisfies growth":
        ["K3_positive_controls", "K8_record_coherence"],
    "round 26: exact key set, impossible counts":
        ["D_discriminator"],
    "round 27: census does not reconcile with the delta":
        ["K3_positive_controls"],
    "round 27: clone with the clock nudged":
        ["K6_contained_and_distinct", "K7_fixture_label_backed", "K8_record_coherence"],
    "round 27: containment probe did not pass":
        ["K6_contained_and_distinct"],
    "round 27: flag hidden in the config-load env":
        ["K5_flags_were_off"],
    "round 27: flag present at airlock entry":
        ["K5_flags_were_off"],
    "round 27: flag present in a flags-off environment":
        ["K5_flags_were_off"],
    "round 27: flags-off grew the daily collection":
        ["K3_positive_controls"],
    "round 27: flags-off resolver did not read dormant":
        ["schema"],
    "round 27: flags-off run admits the flag was ON":
        ["K5_flags_were_off"],
    "round 27: flags-off run not bound to the manifest":
        ["schema"],
    "round 27: healthy run relabelled partial":
        ["D_discriminator", "K7_fixture_label_backed"],
    "round 27: ledger digest is not lowercase hex":
        ["K1_ledger_unchanged"],
    "round 27: no containment proof at all":
        ["K6_contained_and_distinct"],
    "round 27: partial label, wrong ledger":
        ["K7_fixture_label_backed"],
    "round 27: partial run is a clone of the healthy run":
        ["K6_contained_and_distinct", "K7_fixture_label_backed", "K8_record_coherence"],
    "round 27: producer boolean contradicts its digests":
        ["K1_ledger_unchanged"],
    "round 27: run finished before it started":
        ["K6_contained_and_distinct"],
    "round 27: swept nothing, found nothing":
        ["K4_no_stray_store"],
    "round 28: census paths resolve to /dev/null":
        ["K8_record_coherence"],
    "round 28: env values not a subset of env names":
        ["K5_flags_were_off"],
    "round 28: flags-off declares the S1 API absent":
        ["schema"],
    "round 28: flags-off run recorded refusals":
        ["K8_record_coherence"],
    "round 28: forced-on control declares stamps landed":
        ["D_discriminator"],
    "round 28: forced-on decoy collection":
        ["D_discriminator", "K8_record_coherence"],
    "round 28: forced-on tail count contradicts its raw rows":
        ["D_discriminator"],
    "round 28: latch marker in the ledger file set":
        ["K2_no_latch_artifact"],
    "round 28: reachable brain inside an isolated airlock":
        ["K8_record_coherence"],
    "round 28: records disagree on the interpreter":
        ["K8_record_coherence"],
    "round 28: refusal aggregate disagrees with the raw count":
        ["D_discriminator"],
    "round 28: resolver reading is not a reading":
        ["schema"],
    "round 28: run began in a store holding 1165 rows":
        ["K3_positive_controls"],
    "round 28: store paths outside the projected tree":
        ["K8_record_coherence"],
    "round 28: twenty empty replies as 'behavior identical'":
        ["K8_record_coherence"],
    "run census drifted from the pinned baseline":
        ["D_discriminator", "K3_positive_controls"],
    "schema: empty census":
        ["schema"],
    "schema: exercised store produced no stamps":
        ["schema"],
    "schema: phase probe missing":
        ["schema"],
    "sweep: Boolean count, flags-off":
        ["schema"],
    "sweep: negative count, flags-off":
        ["schema"],
    "zero-count census is not a census":
        ["schema"],
}


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
    pinned = copy.deepcopy(PINNED_BASELINE)

    def case(label, want, a=None, p=None, expect_only=None, **kw):
        nonlocal ok
        # Round 28 #21: with the resolver required present on flags-off runs,
        # a forced-on run is mandatory for every evidence set. Cases get one
        # by default; the case that TESTS its absence passes forced=None.
        if "forced" not in kw:
            kw["forced"] = forced_on_run()
        v = run_gate(tmp, a or copy.deepcopy(A), p or copy.deepcopy(P), **kw)
        got = v["verdict"]
        good = got == want
        if want == "FAIL":
            declared = ([expect_only] if isinstance(expect_only, str)
                        else EXPECTED_CLAUSES.get(label))
            if declared is None:
                good = False
                print(f"BAD {label}: expected-FAIL case declares no clause "
                      f"set; add it to EXPECTED_CLAUSES")
            elif sorted(v.get("failures", {})) != sorted(declared):
                good = False
        if good and expect_only is not None:
            # Gate round 24: a K-case that also trips clause D proves
            # nothing about K. With the baseline supplied, the failure set
            # must be EXACTLY the named clause.
            fails = sorted(v.get("failures", {}))
            if fails != [expect_only]:
                good = False
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
    case("honest run against its own pinned baseline", "PASS", baseline=pinned,
         forced=forced_on_run())

    a = copy.deepcopy(A)
    a["stamp_census"][EXERCISED] = {"gestation": 19}
    # Round 27: this now also trips K3, because a census that disagrees with
    # the collection delta is exactly the reconciliation failure #15 added.
    case("run census drifted from the pinned baseline", "FAIL", a=a,
         baseline=pinned)
    doctored = copy.deepcopy(pinned)
    doctored["per_fixture"]["partial"]["stamp_census"]["chroma::daily"] = \
        {"gestation": 3}
    case("round 25: doctored baseline supplied", "FAIL", baseline=doctored,
         expect_only="D_discriminator")
    unbound = copy.deepcopy(pinned); unbound["bound_archive_sha256"] = "z" * 64
    case("round 25: baseline unbound from the archive", "FAIL",
         baseline=unbound, expect_only="D_discriminator")

    a = copy.deepcopy(A); a["ledger_post_replay_sha256"] = "b" * 64
    case("K1 ledger main file changed", "FAIL", a=a, baseline=pinned,
         expect_only="K1_ledger_unchanged")
    a = copy.deepcopy(A); del a["ledger_post_replay_sha256"]
    # A missing key is caught EARLIER, by the fail-closed schema stage —
    # naming the clause honestly is the point of expect_only.
    case("K1 digest key missing (schema stage)", "FAIL", a=a, baseline=pinned,
         expect_only="schema")

    p = copy.deepcopy(P)
    p["latch_artifacts_in_store_tree"] = ["birth_observed/segment-000001.jsonl"]
    case("K2 real latch artifact in the store tree", "FAIL", p=p,
         baseline=pinned, expect_only="K2_no_latch_artifact")
    p = copy.deepcopy(P); del p["latch_artifacts_in_store_tree"]
    case("K2 store-tree latch sweep missing (schema stage)", "FAIL", p=p,
         baseline=pinned, expect_only="schema")

    a = copy.deepcopy(A)
    a["positive_control"]["interactions_without_tail_passage"] = ["s1-replay-07"]
    case("K3 forged PASS over a missed tail", "FAIL", a=a,
         baseline=pinned, expect_only="K3_positive_controls")
    a = copy.deepcopy(A)
    a["positive_control"] = {"verdict": "PASS"}
    case("K3 label with no underlying numbers", "FAIL", a=a, baseline=pinned,
         expect_only="K3_positive_controls")
    # Round 25's first forgery: a raw row that contradicts a clean aggregate.
    a = copy.deepcopy(A)
    a["interactions"][7]["outcome"] = "raised"
    a["interactions"][7]["tail_passages"] = 0
    case("round 25: raw row contradicts clean aggregate", "FAIL", a=a,
         baseline=pinned, expect_only="K3_positive_controls")
    a = copy.deepcopy(A)
    a["collection_counts_after"] = copy.deepcopy(a["collection_counts_before"])
    case("round 25: nothing stored, aggregate says it grew", "FAIL", a=a,
         baseline=pinned, expect_only="K3_positive_controls")
    # Round 26's four, each reproduced exactly as the reviewer wrote it.
    a = copy.deepcopy(A)
    for k in ("raw", "daily", "core"):
        a["collection_counts_after"][k] = a["collection_counts_before"][k]
    a["collection_counts_before"]["decoy_not_a_store"] = 0
    a["collection_counts_after"]["decoy_not_a_store"] = 1
    case("round 26: decoy key satisfies growth", "FAIL", a=a,
         baseline=pinned)
    # Sweeping the class rather than the instance: the same count-domain
    # vectors on the flags-off side, where round 26 did not look.
    a = copy.deepcopy(A); a["stamp_census"][EXERCISED] = {"gestation": True}
    case("sweep: Boolean count, flags-off", "FAIL", a=a, baseline=pinned,
         expect_only="schema")
    a = copy.deepcopy(A); a["stamp_census"]["chroma::daily"] = {"gestation": -5}
    case("sweep: negative count, flags-off", "FAIL", a=a, baseline=pinned,
         expect_only="schema")

    a = copy.deepcopy(A)
    a["stray_stores_outside_projected_tree"] = ["/tmp/escaped.db"]
    case("K4 store escaped the projected tree", "FAIL", a=a,
         baseline=pinned, expect_only="K4_no_stray_store")

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
    case("one interaction of twenty returned", "FAIL", a=a, baseline=pinned,
         expect_only="K3_positive_controls")
    a = copy.deepcopy(A); a["positive_control"]["store_tail_invocations"] = 1
    case("fewer tail passages than interactions", "FAIL", a=a,
         baseline=pinned, expect_only="K3_positive_controls")

    a = copy.deepcopy(A)
    a["stamp_census"]["chroma::daily"] = {"gestation": 1}
    case("a new write to a store outside raw", "FAIL", a=a, baseline=pinned)

    p = copy.deepcopy(P); p["phase_probe"]["has_resolve_api"] = True
    case("resolve() exists but no forced-on run", "FAIL", forced=None, p=p)
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

    # Gate round 23's executed forgery: a well-shaped alien id.
    f = forced_on_run()
    f["interactions"][3]["id"] = "s1-replay-forged"
    case("forgery: alien id passing the shape check", "FAIL",
         baseline=pinned, forced=f)

    # Round 25's remaining two, made permanent (round 26 found them absent),
    # plus round 26's three forced-on forgeries.
    f = forced_on_run()
    f["interactions"][3]["exception"] = ("PhaseUnknownRefusal: alien.consumer: "
                                         "refusing to stamp a phase.")
    case("round 25: alien raw consumer under a clean list", "FAIL",
         baseline=pinned, forced=f, expect_only="D_discriminator")
    f = forced_on_run(); f["stamp_census"] = {}
    case("round 25: forced-on census emptied", "FAIL", baseline=pinned,
         forced=f, expect_only="D_discriminator")
    f = forced_on_run()
    f["interactions"][7]["exception"] = f["interactions"][7]["exception"].replace(
        "store_telegram", "store_core")
    f["consumer_refusals"][7] = {
        "consumer": "memory_manager.store_core",
        "exception": "PhaseUnknownRefusal",
        "message": f["interactions"][7]["exception"].split(": ", 1)[1]}
    case("round 26: co-mutated to a different KNOWN consumer", "FAIL",
         baseline=pinned, forced=f, expect_only="D_discriminator")
    f = forced_on_run()
    f["stamp_census"] = {k: {"unknown": -1} for k in f["stamp_census"]}
    case("round 26: exact key set, impossible counts", "FAIL",
         baseline=pinned, forced=f, expect_only="D_discriminator")
    f = forced_on_run()
    for i in f["interactions"]:
        i["tail_passages"] = True
    case("round 26: Boolean tail counts", "FAIL", baseline=pinned, forced=f,
         expect_only="D_discriminator")

    # Round 27, found by attacking my own judge rather than waiting to be
    # told. The first is the one that mattered: the dormancy premise itself
    # — a "flags-off" run that openly declared the flag ON used to pass.
    a = copy.deepcopy(A); a["flags_off_after_import"] = False
    a["env_after_import"]["values"]["MAEZ_S1_PHASE_TRUTH"] = "1"
    case("round 27: flags-off run admits the flag was ON", "FAIL", a=a,
         baseline=pinned, expect_only="K5_flags_were_off")
    a = copy.deepcopy(A)
    a["env_after_import"]["values"]["MAEZ_S1_PHASE_TRUTH"] = "1"
    case("round 27: flag present in a flags-off environment", "FAIL", a=a,
         baseline=pinned, expect_only="K5_flags_were_off")
    p_clone = copy.deepcopy(A); p_clone["fixture"] = "partial"
    # Also trips K7 now: a clone of the healthy run carries the healthy
    # ledger digest, so its "partial" label is unbacked (#13).
    case("round 27: partial run is a clone of the healthy run", "FAIL",
         p=p_clone, baseline=pinned)
    a = copy.deepcopy(A)
    a["containment"] = dict(a["containment"], network_unreachable="FAIL (reachable)")
    case("round 27: containment probe did not pass", "FAIL", a=a,
         baseline=pinned, expect_only="K6_contained_and_distinct")
    a = copy.deepcopy(A); del a["containment"]
    case("round 27: no containment proof at all", "FAIL", a=a,
         baseline=pinned, expect_only="K6_contained_and_distinct")
    a = copy.deepcopy(A); a["started_at"], a["finished_at"] = 500.0, 100.0
    case("round 27: run finished before it started", "FAIL", a=a,
         baseline=pinned, expect_only="K6_contained_and_distinct")

    # Round 27, external review. #13 is the one that changed what the
    # evidence PROVES: `fixture` was a bare label, so a genuine healthy run
    # relabelled "partial" validated and the discriminator lost its
    # controlled variable.
    a = copy.deepcopy(A); a["fixture"] = "partial"
    a["ledger_post_replay_sha256"] = a["ledger_post_migration_sha256"]
    p_ = copy.deepcopy(P)
    case("round 27: healthy run relabelled partial", "FAIL", a=a, p=p_,
         baseline=pinned)
    p_ = copy.deepcopy(P); p_["ledger_post_migration_sha256"] = SHA_A
    p_["ledger_post_replay_sha256"] = SHA_A
    case("round 27: partial label, wrong ledger", "FAIL", p=p_,
         baseline=pinned)
    # #15: daily/core may not move on a flags-off run.
    a = copy.deepcopy(A); a["collection_counts_after"]["daily"] = 40
    case("round 27: flags-off grew the daily collection", "FAIL", a=a,
         baseline=pinned, expect_only="K3_positive_controls")
    a = copy.deepcopy(A); a["collection_counts_after"]["raw"] = 25
    case("round 27: census does not reconcile with the delta", "FAIL", a=a,
         baseline=pinned)
    # #16: an empty stray list proves nothing if nothing was swept.
    a = copy.deepcopy(A); a["stray_store_sweep_roots"] = []
    case("round 27: swept nothing, found nothing", "FAIL", a=a,
         baseline=pinned, expect_only="K4_no_stray_store")
    # #17: the flag hidden one field over.
    a = copy.deepcopy(A)
    a["env_after_config_load"]["values"]["MAEZ_S1_PHASE_TRUTH"] = "1"
    case("round 27: flag hidden in the config-load env", "FAIL", a=a,
         baseline=pinned, expect_only="K5_flags_were_off")
    a = copy.deepcopy(A)
    a["containment"]["env_at_entry"]["names"].append("MAEZ_S1_PHASE_TRUTH")
    case("round 27: flag present at airlock entry", "FAIL", a=a,
         baseline=pinned, expect_only="K5_flags_were_off")
    # #18: a clone with the clock nudged is still a clone.
    p_ = copy.deepcopy(A); p_["fixture"] = "partial"
    p_["started_at"] += 100.0; p_["finished_at"] += 100.0
    case("round 27: clone with the clock nudged", "FAIL", p=p_,
         baseline=pinned)
    # Codex lane: K1 digest domain, and the producer boolean must agree.
    a = copy.deepcopy(A)
    a["ledger_post_migration_sha256"] = a["ledger_post_replay_sha256"] = "Z" * 64
    case("round 27: ledger digest is not lowercase hex", "FAIL", a=a,
         baseline=pinned, expect_only="K1_ledger_unchanged")
    a = copy.deepcopy(A); a["ledger_main_file_unchanged"] = False
    case("round 27: producer boolean contradicts its digests", "FAIL", a=a,
         baseline=pinned, expect_only="K1_ledger_unchanged")
    a = copy.deepcopy(A); a["manifest_sha256"] = "0" * 64
    case("round 27: flags-off run not bound to the manifest", "FAIL", a=a,
         baseline=pinned, expect_only="schema")
    a = copy.deepcopy(A); a["phase_probe"]["resolve"] = {"phase": "unknown",
                                                          "reason": "structural"}
    case("round 27: flags-off resolver did not read dormant", "FAIL", a=a,
         baseline=pinned, expect_only="schema")

    # Round 28. #21 is the sharpest of the arc: nothing required the
    # flags-off runs to have CONTAINED the feature, so a pre-S1 tree
    # reproducing the pre-S1 baseline — a tautology — was accepted as proof
    # that a feature is dormant. Dormant means present and silent.
    a = copy.deepcopy(A); p_ = copy.deepcopy(P)
    for r_ in (a, p_):
        r_["phase_probe"]["has_resolve_api"] = False
        r_["phase_probe"].pop("resolve", None)
    case("round 28: flags-off declares the S1 API absent", "FAIL", a=a, p=p_,
         baseline=pinned, expect_only="schema")
    a = copy.deepcopy(A); a["phase_probe"]["resolve"] = "n/a"
    case("round 28: resolver reading is not a reading", "FAIL", a=a,
         baseline=pinned, expect_only="schema")
    # #22: the forced-on half never received the flags-off half's
    # rederivations — round 26's decoy forgery was still open on the side
    # whose whole claim is that nothing was stored.
    f = forced_on_run()
    f["collection_counts_before"]["decoy"] = 0
    f["collection_counts_after"]["decoy"] = 50
    case("round 28: forced-on decoy collection", "FAIL", baseline=pinned, forced=f)
    f = forced_on_run(); f["store_tail_invocations"] = 0
    case("round 28: forced-on tail count contradicts its raw rows", "FAIL",
         baseline=pinned, forced=f, expect_only="D_discriminator")
    f = forced_on_run()
    f["positive_control"] = {"mode": "forced_on", "verdict": "PASS",
                             "refusals_observed": 20, "collections_grew": True,
                             "all_refusals_typed": False,
                             "stores_with_gestation_stamps": ["chroma::raw"]}
    case("round 28: forced-on control declares stamps landed", "FAIL",
         baseline=pinned, forced=f, expect_only="D_discriminator")
    # #23: the reconciliation I added compared an ABSOLUTE census to a DELTA,
    # which agree only if the store began empty — and nothing required that.
    a = copy.deepcopy(A)
    a["collection_counts_before"] = {"raw": 1000, "daily": 77, "core": 88}
    a["collection_counts_after"] = {"raw": 1020, "daily": 77, "core": 88}
    case("round 28: run began in a store holding 1165 rows", "FAIL", a=a,
         baseline=pinned, expect_only="K3_positive_controls")
    # K8: records that contradict their own containment story.
    a = copy.deepcopy(A)
    a["effective_store_paths_after_import"] = {"memory_dir": "/home/rohit/maez-live/memory"}
    case("round 28: store paths outside the projected tree", "FAIL", a=a,
         baseline=pinned, expect_only="K8_record_coherence")
    a = copy.deepcopy(A); a["census_resolved_paths"] = {"x": "/dev/null"}
    case("round 28: census paths resolve to /dev/null", "FAIL", a=a,
         baseline=pinned, expect_only="K8_record_coherence")
    a = copy.deepcopy(A)
    a["consumer_refusals"] = [{"consumer": "x", "exception": "y", "message": "z"}]
    case("round 28: flags-off run recorded refusals", "FAIL", a=a,
         baseline=pinned, expect_only="K8_record_coherence")
    a = copy.deepcopy(A); a["python"] = "1.0"
    case("round 28: records disagree on the interpreter", "FAIL", a=a,
         baseline=pinned, expect_only="K8_record_coherence")
    a = copy.deepcopy(A); a["brain_reachable"] = True
    case("round 28: reachable brain inside an isolated airlock", "FAIL", a=a,
         baseline=pinned, expect_only="K8_record_coherence")
    a = copy.deepcopy(A)
    for i in a["interactions"]:
        i["reply"] = ""
    case("round 28: twenty empty replies as 'behavior identical'", "FAIL",
         a=a, baseline=pinned, expect_only="K8_record_coherence")
    # #24: clauses that no case exercised. Deleting each from the judge left
    # the suite green, which is the definition of uncovered.
    f = forced_on_run(); f["positive_control"]["refusals_observed"] = 19
    case("round 28: refusal aggregate disagrees with the raw count", "FAIL",
         baseline=pinned, forced=f, expect_only="D_discriminator")
    a = copy.deepcopy(A)
    a["env_after_import"]["values"]["SOMETHING_UNLISTED"] = "x"
    case("round 28: env values not a subset of env names", "FAIL", a=a,
         baseline=pinned, expect_only="K5_flags_were_off")
    a = copy.deepcopy(A)
    a["ledger_post_replay_file_set"] = ["ledger.db", "birth_observed"]
    case("round 28: latch marker in the ledger file set", "FAIL", a=a,
         baseline=pinned, expect_only="K2_no_latch_artifact")

    # Round 28 #24: the archive clause was unreachable in effect, and once
    # made live it stayed UNCOVERED — no case could exercise it without
    # swapping a committed artifact. So the judge is copied somewhere it
    # resolves a DIFFERENT archive beside itself, which is the one honest way
    # to test a check that reads a file relative to its own location.
    import shutil
    d = tmp / "archive_probe"; d.mkdir()
    shutil.copy2(GATE, d / "theme2_s1_t5_gate.py")
    shutil.copy2(GATE.parent / "theme2-s1-replay.json", d / "theme2-s1-replay.json")
    (d / "theme2-s1-baseline.tar.zst").write_bytes(b"not the pinned archive")
    (d / "a.json").write_text(json.dumps(A))
    (d / "p.json").write_text(json.dumps(P))
    (d / "b.json").write_text(json.dumps(pinned))
    (d / "f.json").write_text(json.dumps(forced_on_run()))
    proc = subprocess.run([sys.executable, str(d / "theme2_s1_t5_gate.py"),
                           "--run-a", str(d / "a.json"), "--run-p", str(d / "p.json"),
                           "--baseline-census", str(d / "b.json"),
                           "--forced-on", str(d / "f.json"),
                           "--out", str(d / "v.json")], capture_output=True, text=True)
    got = json.loads((d / "v.json").read_text()) if (d / "v.json").exists() else {}
    detail = json.dumps(got.get("failures", {}))
    good = got.get("verdict") == "FAIL" and "archive on disk" in detail
    ok &= good
    print(f"{'ok ' if good else 'BAD'} {'round 28: the archive on disk is not the pinned archive':46s} "
          f"{got.get('verdict', 'CRASH'):5s} (want FAIL)")

    print("\nALL PASS" if ok else "\nSOME CASES FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
