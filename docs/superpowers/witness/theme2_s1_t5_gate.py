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
import hashlib
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


def _manifest_ids() -> list | None:
    manifest_path = Path(__file__).resolve().parent / "theme2-s1-replay.json"
    try:
        return [x["id"] for x in json.loads(
            manifest_path.read_text())["interactions"]]
    except (OSError, KeyError, ValueError):
        return None


EXPECTED_STORES = ("chroma::raw", "chroma::daily", "chroma::core",
                   "private_thoughts", "audit_log")

KNOWN_CONSUMERS = {
    "memory_manager.store", "memory_manager.store_telegram",
    "memory_manager.store_core",
}

COLLECTION_KEYS = ("raw", "daily", "core")

# The flag whose ABSENCE the flags-off runs are supposed to demonstrate.
ACTIVATION_FLAG = "MAEZ_S1_PHASE_TRUTH"

# The T5 replay drives one surface, and every retained interaction reaches
# exactly one stamper. Membership in KNOWN_CONSUMERS was not enough: round 26
# co-mutated an interaction AND its refusal row to a different known consumer
# and the ordered join agreed with itself.
T5_REPLAY_CONSUMER = "memory_manager.store_telegram"


def _plain_int(v) -> bool:
    """`True` is an `int` in Python, and round 26 used that to pass a Boolean
    off as a count. A count is an int and not a bool."""
    return type(v) is int

# Gate round 25 forged a co-mutated pair: a run-a row grew a stamp AND the
# supplied baseline grew the same stamp, so the comparison agreed with itself.
# The baseline is a committed artifact; the judge pins its identity rather
# than accepting whatever the caller hands it. Canonical (sorted, compact)
# JSON so re-serialization is not mistaken for tampering.
PINNED_BASELINE_CANON_SHA = ("7fa5bdb15eb250f4b784cbaf9d56fc6fb9a143d2c4b0a"
                             "8248306460d93d85353")
PINNED_ARCHIVE_SHA = ("328f98d4d9cb222e437e97a74b22cee46a4cac9114d7f3875bb56"
                      "def0b445216")


def _canon_sha(obj) -> str:
    return hashlib.sha256(json.dumps(
        obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
        # Gate round 24: flags-off runs could declare one interaction and
        # omit raw rows. Every run joins the frozen manifest, in ORDER.
        mids = _manifest_ids()
        ints_ = r.get("interactions")
        if mids is None:
            bad.append({"run": tag, "detail": "frozen manifest unreadable"})
        elif not isinstance(ints_, list) \
                or [i.get("id") for i in ints_] != mids:
            bad.append({"run": tag,
                        "detail": "raw interactions do not match the frozen "
                                  "manifest id sequence"})
        elif r.get("interaction_count") != len(mids):
            bad.append({"run": tag,
                        "detail": "interaction_count != manifest length"})
        probe = r.get("phase_probe")
        if not isinstance(probe, dict) or "current_phase" not in probe:
            bad.append({"run": tag, "detail": "phase_probe absent or malformed"})
        cen = r.get("stamp_census")
        # Gate round 24: a census of {} slid through a vacuous loop. The KEY
        # SET is the contract — all five stores, every run.
        if not isinstance(cen, dict) or \
                sorted(cen) != sorted(EXPECTED_STORES):
            bad.append({"run": tag,
                        "detail": "stamp_census does not cover exactly the "
                                  "five expected stores",
                        "got": sorted(cen) if isinstance(cen, dict) else cen})
        else:
            # Round 26 hit the count DOMAIN on the forced-on side only; the
            # same hole was here. Sweep the class, not the instance: every
            # count in every store is a nonnegative plain integer (bools are
            # ints in Python and were used as a forgery vector).
            for store, counts in cen.items():
                if not isinstance(counts, dict) or not all(
                        _plain_int(c) and c >= 0 for c in counts.values()):
                    bad.append({"run": tag,
                                "detail": f"{store} census holds a value that "
                                          f"is not a count", "got": counts})
            if not isinstance(cen[EXERCISED_STORE], dict) or not any(
                    _plain_int(v) and v > 0
                    for v in cen[EXERCISED_STORE].values()):
                # Round 19: {"gestation": 0} counted as a nonempty census.
                bad.append({"run": tag,
                            "detail": f"{EXERCISED_STORE} produced no stamps"})
    return bad


def k5_flags_were_actually_off(runs: dict) -> list:
    """Self-attack, round 27. The ENTIRE dormancy claim is "with the flag off,
    behavior is exactly legacy" — and the judge never checked that the flag
    was off. The producer records `flags_off_after_import` and the env it
    imported under; both were ignored, so a run that openly ADMITTED the flag
    was set passed as the dormancy baseline. Absence of the flag is the
    premise, so it is now evidence."""
    bad = []
    for tag, r in runs.items():
        if r.get("flags_off_after_import") != "PASS":
            bad.append({"run": tag, "detail": "run does not attest that the "
                                              "activation flag was off",
                        "got": r.get("flags_off_after_import")})
        env = (r.get("env_after_import") or {}).get("values")
        if not isinstance(env, dict):
            bad.append({"run": tag, "detail": "no recorded post-import env"})
        elif ACTIVATION_FLAG in env:
            bad.append({"run": tag,
                        "detail": "flags-off run imported with the activation "
                                  "flag present in its environment",
                        "value": env.get(ACTIVATION_FLAG)})
    return bad


def k6_contained_and_distinct(runs: dict) -> list:
    """Self-attack, round 27. Two more premises the judge took on faith:
    (a) the run happened inside the airlock at all — containment was recorded
    and never read, so a run against the LIVE stores passed; and (b) the two
    fixtures were two executions — run-p could be a byte-clone of run-a with
    the label flipped, and one run would answer for both."""
    bad = []
    for tag, r in runs.items():
        c = r.get("containment")
        if not isinstance(c, dict):
            bad.append({"run": tag, "detail": "no containment proof"})
            continue
        for probe in ("repo_readonly", "memory_writable_and_empty",
                      "network_unreachable", "no_maez_env_at_entry"):
            if not str(c.get(probe, "")).startswith("PASS"):
                bad.append({"run": tag, "detail": f"containment probe {probe} "
                                                  f"did not pass",
                            "got": c.get(probe)})
        st, fi = r.get("started_at"), r.get("finished_at")
        if not (isinstance(st, (int, float)) and isinstance(fi, (int, float))
                and not isinstance(st, bool) and not isinstance(fi, bool)
                and 0 < st < fi):
            bad.append({"run": tag, "detail": "run has no coherent wall-clock "
                                              "span", "started_at": st,
                        "finished_at": fi})
    tags = sorted(runs)
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            x, y = runs[tags[i]], runs[tags[j]]
            if x.get("started_at") == y.get("started_at"):
                bad.append({"detail": "two runs share a start time; they are "
                                      "not two executions",
                            "runs": [tags[i], tags[j]]})
            a_ = {k: v for k, v in x.items() if k != "fixture"}
            b_ = {k: v for k, v in y.items() if k != "fixture"}
            if a_ == b_:
                bad.append({"detail": "one run is a clone of the other with "
                                      "only the fixture label changed",
                            "runs": [tags[i], tags[j]]})
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
    """The label is not the fact, and round 25 proved the aggregate is not
    either: a raw row saying `raised`/no-tail sat under a clean
    `positive_control` and passed. Every fact here is DERIVED from the raw
    per-interaction records; the producer's aggregate is then required to
    AGREE with the derivation. Disagreement is itself a failure — one of the
    two is lying and the judge does not get to pick."""
    bad = []
    for tag, r in runs.items():
        pc = r.get("positive_control")
        if not isinstance(pc, dict):
            bad.append({"run": tag, "detail": "no positive control"})
            continue
        if pc.get("verdict") != "PASS":
            bad.append({"run": tag, "positive_control": pc})
            continue
        ints = r.get("interactions")
        if not isinstance(ints, list) or not ints:
            bad.append({"run": tag, "detail": "no raw interactions to derive from"})
            continue
        d_returned = [i.get("id") for i in ints if i.get("outcome") == "returned"]
        d_raised = [i.get("id") for i in ints if i.get("outcome") != "returned"]
        d_no_tail = [i.get("id") for i in ints if not (
            isinstance(i.get("tail_passages"), int) and i["tail_passages"] >= 1)]
        cb = r.get("collection_counts_before") or {}
        ca = r.get("collection_counts_after") or {}
        # Round 26 added `decoy_not_a_store: 0 -> 1` and the unconstrained
        # any() over producer-supplied keys called it growth. Growth means
        # the ONE collection T5's replay path actually writes.
        EXERCISED_COLLECTION = "raw"
        if sorted(set(cb) | set(ca)) != sorted(COLLECTION_KEYS):
            bad.append({"run": tag,
                        "detail": "collection counters are not exactly the "
                                  "three real collections",
                        "got": sorted(set(cb) | set(ca))})
            d_grew = False
        else:
            b_, a_ = cb.get(EXERCISED_COLLECTION), ca.get(EXERCISED_COLLECTION)
            d_grew = (_plain_int(b_) and _plain_int(a_) and a_ > b_)
        # (a) the DERIVED facts must themselves describe a clean flags-off run
        if d_raised:
            bad.append({"run": tag, "detail": "raw rows raised",
                        "ids": d_raised})
        if d_no_tail:
            bad.append({"run": tag,
                        "detail": "raw rows never reached the storage tail",
                        "ids": d_no_tail})
        if not d_grew:
            bad.append({"run": tag, "detail": "no collection grew in the raw "
                                              "counts; nothing was stored"})
        # (b) the producer's aggregate must agree with the derivation
        for field, derived in (("interactions_raised", d_raised),
                               ("interactions_without_tail_passage", d_no_tail)):
            if list(pc.get(field) or []) != derived:
                bad.append({"run": tag,
                            "detail": f"aggregate {field} disagrees with the "
                                      f"raw interactions",
                            "aggregate": pc.get(field), "derived": derived})
        if pc.get("interactions_returned") != len(d_returned):
            bad.append({"run": tag,
                        "detail": "aggregate interactions_returned disagrees "
                                  "with the raw interactions",
                        "aggregate": pc.get("interactions_returned"),
                        "derived": len(d_returned)})
        if pc.get("collections_grew") is not d_grew:
            bad.append({"run": tag,
                        "detail": "aggregate collections_grew disagrees with "
                                  "the raw counts"})
        d_tail = sum(i["tail_passages"] for i in ints
                     if isinstance(i.get("tail_passages"), int))
        for holder, label in ((pc, "aggregate"), (r, "run")):
            if holder.get("store_tail_invocations") != d_tail:
                bad.append({"run": tag,
                            "detail": f"{label} store_tail_invocations "
                                      f"disagrees with the raw rows",
                            "declared": holder.get("store_tail_invocations"),
                            "derived": d_tail})
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

    if baseline is None:
        # Gate round 20, F-list item 3: the pinned baseline census is a
        # committed artifact (protocol v7.1), so omitting it is no longer a
        # pre-baseline state — it is a skipped comparison, and a skipped
        # comparison must fail rather than silently narrow the verdict.
        bad.append({"detail": "no baseline census supplied; comparison "
                              "against the committed pinned baseline is "
                              "mandatory"})
    if baseline is not None:
        # Round 25: a co-mutated run+baseline pair agreed with itself and
        # passed. The pinned baseline is a committed artifact with a frozen
        # identity — the caller supplies bytes, not truth.
        if _canon_sha(baseline) != PINNED_BASELINE_CANON_SHA:
            return "FAIL", [{"detail": "supplied baseline is not the committed "
                                       "pinned baseline census",
                             "canonical_sha256": _canon_sha(baseline)}]
        if baseline.get("bound_archive_sha256") != PINNED_ARCHIVE_SHA:
            return "FAIL", [{"detail": "baseline is not bound to the pinned "
                                       "T5 archive"}]
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

    # Gate round 21 forged a report that PASSED: resolve=unknown, empty
    # census, one refusal merely NAMED PhaseUnknownRefusal, counts set to
    # 999 -- because the gate read labels instead of rederiving facts. The
    # same lesson as K3, applied here: every fact below is recomputed from
    # raw fields, and a missing field is a failure, not a default.
    for k in ("interaction_count", "collection_counts_before",
              "collection_counts_after", "positive_control", "forced_on",
              "interactions", "manifest_sha256"):
        if k not in forced:
            bad.append({"detail": f"forced-on report missing {k!r}"})

    # Gate round 22 forged past the aggregate checks: one invented refusal,
    # a returned interaction with zero tail passages, positive_control FAIL —
    # PASS, because the judge read producer-authored AGGREGATES. The join
    # below is judge-owned, over the RAW per-interaction records, and the
    # empirical shape it encodes is the retained real run's: forced-on, every
    # interaction RAISES PhaseUnknownRefusal at the storage tail, exactly one
    # tail passage each.
    MANIFEST_SHA = ("2b9faf616941bb6a0ab6294e1323e2dd73cb57389ab021cc2b868f"
                    "59109cb420")
    if forced.get("manifest_sha256") != MANIFEST_SHA:
        bad.append({"detail": "forced-on run not bound to the frozen "
                              "manifest", "got": forced.get("manifest_sha256")})
    ints = forced.get("interactions")
    n = forced.get("interaction_count")
    if not isinstance(ints, list) or not isinstance(n, int) \
            or len(ints) != n or n < 1:
        bad.append({"detail": "raw interactions absent or count mismatch",
                    "have": len(ints) if isinstance(ints, list) else None,
                    "declared": n})
    else:
        ids = [i.get("id") for i in ints]
        # Round 23: exact set. Round 24: exact SEQUENCE — order-sensitive.
        manifest_ids = _manifest_ids()
        if manifest_ids is None:
            bad.append({"detail": "frozen manifest unreadable"})
        elif ids != manifest_ids:
            bad.append({"detail": "interaction ids != the frozen manifest "
                                  "sequence (order-sensitive)"})
        for i in ints:
            exc_text = str(i.get("exception", ""))
            # Round 24 forged "NotPhaseUnknownRefusal: refusing to stamp" —
            # substring is not type. The field is "TypeName: message"; the
            # TYPE is compared exactly.
            exc_type = exc_text.split(":", 1)[0].strip()
            if i.get("outcome") != "raised" \
                    or exc_type != "PhaseUnknownRefusal" \
                    or "refusing to stamp" not in exc_text \
                    or not _plain_int(i.get("tail_passages")) \
                    or i.get("tail_passages") != 1:
                bad.append({"detail": "interaction did not raise the typed "
                                      "refusal at exactly one tail passage",
                            "id": i.get("id"), "outcome": i.get("outcome"),
                            "tail_passages": i.get("tail_passages")})
                break
        # Round 25: the raw rows and the refusal list were each plausible
        # and never joined, so an alien consumer could sit in the raw
        # exception while the refusal list stayed clean. Every raw refusal
        # names its own consumer inside the exception text; that name is
        # joined 1:1, IN ORDER, to the refusal list.
        rl = forced.get("consumer_refusals")
        if not isinstance(rl, list) or len(rl) != len(ints):
            bad.append({"detail": "refusal list does not join the raw "
                                  "interactions 1:1",
                        "refusals": len(rl) if isinstance(rl, list) else None,
                        "interactions": len(ints)})
        else:
            for i, row in zip(ints, rl):
                exc = str(i.get("exception", ""))
                head, _, msg = exc.partition(": ")
                who = msg.split(":", 1)[0].strip() if ":" in msg else None
                if head != "PhaseUnknownRefusal" or who != T5_REPLAY_CONSUMER \
                        or not isinstance(row, dict) \
                        or row.get("consumer") != who \
                        or str(row.get("message", "")) != msg:
                    bad.append({"detail": "raw refusal does not join its "
                                          "refusal row under a known "
                                          "reply-path consumer",
                                "id": i.get("id"), "raw_consumer": who,
                                "row_consumer": (row or {}).get("consumer")
                                if isinstance(row, dict) else None})
                    break
    pc = forced.get("positive_control") or {}
    if pc.get("mode") != "forced_on" or pc.get("verdict") != "PASS":
        bad.append({"detail": "producer positive control is not a forced-on "
                              "PASS", "positive_control": pc})
    if isinstance(pc.get("refusals_observed"), int) and isinstance(n, int) \
            and pc.get("refusals_observed") != n:
        bad.append({"detail": "producer refusal aggregate disagrees with "
                              "the raw interactions"})
    if forced.get("forced_on") is not True:
        bad.append({"detail": "report does not attest forced_on=true from "
                              "the producer"})
    n = forced.get("interaction_count")
    refusals_list = forced.get("consumer_refusals")
    if isinstance(n, int) and isinstance(refusals_list, list) \
            and len(refusals_list) != n:
        bad.append({"detail": "refusal count != interaction count",
                    "refusals": len(refusals_list), "interactions": n})
    for r in (refusals_list or []):
        # Round 24 forged 20 rows under "alien.consumer". A refusal is
        # evidence only when its consumer is a censused reply-path stamper
        # and its message names that same consumer.
        if not isinstance(r, dict) \
                or r.get("exception") != "PhaseUnknownRefusal" \
                or "refusing to stamp" not in str(r.get("message", "")) \
                or r.get("consumer") not in KNOWN_CONSUMERS \
                or r.get("consumer", " ") not in str(r.get("message", "")):
            bad.append({"detail": "refusal evidence is not a typed refusal "
                                  "from a known reply-path consumer naming "
                                  "itself", "entry": r})
            break
    cb = forced.get("collection_counts_before") or {}
    ca = forced.get("collection_counts_after") or {}
    for kcol in ("raw", "daily", "core"):
        b_, a_ = cb.get(kcol), ca.get(kcol)
        if not (isinstance(b_, int) and isinstance(a_, int) and a_ == b_):
            bad.append({"detail": f"collection {kcol} not proven flat by "
                                  f"raw counts", "before": b_, "after": a_})
    fcen = forced.get("stamp_census")
    if not isinstance(fcen, dict) or sorted(fcen) != sorted(EXPECTED_STORES):
        # Round 25: `stamp_census = {}` made the emptiness loop below vacuous.
        # Absence of evidence was reading as evidence of absence.
        bad.append({"detail": "forced-on stamp_census does not cover exactly "
                              "the five expected stores",
                    "got": sorted(fcen) if isinstance(fcen, dict) else fcen})
    for store, v in (forced.get("stamp_census") or {}).items():
        # Round 26 supplied {"unknown": -1} for all five stores: the key set
        # was exact and the ">0" test never fired. A count is a nonnegative
        # plain integer, and under refusal every one of them is zero.
        if not isinstance(v, dict) or not all(
                _plain_int(c) and c == 0 for c in v.values()):
            bad.append({"detail": f"store {store} census is not a set of zero "
                                  f"counts", "got": v})

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
        "K5_flags_were_off": k5_flags_were_actually_off(runs),
        "K6_contained_and_distinct": k6_contained_and_distinct(runs),
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
