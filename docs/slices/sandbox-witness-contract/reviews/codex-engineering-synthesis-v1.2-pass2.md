# Sandbox-Witness Contract — Codex Engineering Pass-2 Synthesis

**Prepared:** 2026-05-26  
**Artifact reviewed:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1.2  
**Dispatch brief:** `docs/slices/sandbox-witness-contract/reviews/codex-engineering-pass2-brief.md`  
**Review records:** `docs/slices/sandbox-witness-contract/reviews/codex-*-pass2.md`

This document is derivative reconstruction. The six `codex-*-pass2.md` files are the witnessed review record.

---

## Verdict Summary

| Seat | Verdict |
| --- | --- |
| Peirce | STILL OPEN |
| Arendt | STILL OPEN |
| Huygens | STILL OPEN |
| Pauli | STILL OPEN |
| Ohm | STILL OPEN |
| Lovelace / Bernoulli | STILL OPEN |

Engineering pass-2 result: **STILL OPEN.**

v1.2 closed most of the pass-1 engineering trapdoors. The remaining findings are narrow and foldable; no reviewer raised a covenant-axis escalation.

---

## Per-Batch Closure Summary

| Batch | Closure Verdict | Seat Pattern |
| --- | --- | --- |
| 1. Legacy witness migration | CLOSED | 6 CLOSED |
| 2. Immutable witness generations | CLOSED | 6 CLOSED |
| 3. Atomic ratification eligibility | CLOSED-with-NIT | 5 CLOSED, 1 NIT |
| 4. Race-safe staleness anchors | STILL OPEN | 6 STILL OPEN |
| 5. Deterministic observed-effect functions | CLOSED | 6 CLOSED |
| 6. Field-complete taint discipline | CLOSED | 6 CLOSED |
| 7. Alias-resistant I7 enforcement | CLOSED-with-NIT | 4 CLOSED, 1 NIT, 1 STILL OPEN |
| 8. Real path isolation | CLOSED-with-NIT | 5 CLOSED, 1 NIT |
| 9. Exhaustive `SubstrateLocus` | CLOSED | 6 CLOSED |
| 10. Refusal-path matrix | STILL OPEN / split | 3 CLOSED, 3 STILL OPEN |
| 11. Attach-time vs ratify-time cost split | STILL OPEN | 6 STILL OPEN |

---

## Convergent Material Findings

### Batch 4 — WAL / Concurrent DB Cursor Coverage Still Missing

Seats: Peirce, Arendt, Huygens, Pauli, Ohm, Lovelace / Bernoulli.

All six reviewers agreed v1.2 materially closes file hash / deletion / mtime authority, per-locus DB cursor tuples, append-only / monotonic change-table constraints, diagnostic truncation/rotation, secondary-table append, and update/delete-without-cursor coverage. The remaining gap is specific: v1.2 still does not explicitly cover SQLite WAL / concurrent reader-writer behavior for DB cursor authority.

Current v1.2 evidence cited:

- `spec-brief.md:113-114`: staleness anchor prose.
- `spec-brief.md:191-205`: `StalenessAnchorKind` authority notes.
- `spec-brief.md:373-379`: W#5 test anchors.
- `spec-brief.md:401`: concurrent anchor advancement test, but not DB cursor WAL interleaving.

Required v1.3 fold:

- Add DB cursor capture/compare semantics under concurrent SQLite WAL reader/writer behavior.
- State that DB cursor comparison must be taken from a race-safe snapshot / transaction, OR state the cursor authority rule that makes WAL/concurrency impossible or irrelevant for the anchored locus.
- Add a W#5g-style RED anchor: `test_db_cursor_detects_wal_concurrent_writer_between_capture_and_ratification` (or equivalent) proving a concurrent committed write cannot hide behind a stale cursor snapshot.

### Batch 11 — Ratify-Time No-Rerun / Subprocess Count Test Still Missing

Seats: Peirce, Arendt, Huygens, Pauli, Ohm, Lovelace / Bernoulli.

All six reviewers agreed v1.2 closes the prose split between attach-time full subprocess re-verification and ratify-time freshness/locus/generation eligibility checks. The remaining gap is test-spec precision: no W# anchor explicitly counts subprocess invocations or proves ratify-time does not accidentally rerun the expensive verifier.

Current v1.2 evidence cited:

- `spec-brief.md:328-334`: attach-time vs ratify-time verification cost section.
- `spec-brief.md:409`: implementability split.

Required v1.3 fold:

- Add a W#cost / W#13c-style RED anchor that instruments subprocess runner invocation count.
- The test must prove attach-time performs exactly the intended full subprocess re-verification.
- The test must prove ratify-time performs freshness/locus/generation checks with zero full subprocess/test-suite reruns by default.
- Any full rerun at ratification must require a future explicit closed policy such as `FULL_RERUN_AT_RATIFY`.

---

## Split / Borderline Findings

### Batch 10 — Refusal-Path Matrix Needs Per-Reason Rows

Seats STILL OPEN: Peirce, Huygens, Lovelace / Bernoulli.  
Seats CLOSED: Arendt, Pauli, Ohm.

The split is not about whether W#10 should be behavioral. All seats accepted that v1.2 says W#10 is table-driven and asserts `WitnessRefused.reason`. The split is whether the spec itself must include a concrete per-reason matrix rather than leaving the matrix to implementation.

Current v1.2 evidence cited:

- `spec-brief.md:176-189`: `WitnessRefusalReason` vocabulary.
- `spec-brief.md:396-407`: W#10 and matrix prose.

STILL OPEN closure criterion from Peirce/Huygens/Lovelace:

- Add a table mapping each `WitnessRefusalReason` to:
  - one exercised boundary (`construction`, `attachment`, `re-verification`, `ratification-time recheck`, or `migration write-boundary`);
  - the W# fixture that asserts `WitnessRefused.reason`;
  - any applicable witness kind / reserved-cell condition.
- Affirm divergence remains diagnostic/acknowledgment, not refusal.

Synthesis call:

Fold this into v1.3. Even though half the seats marked Batch 10 closed, the requested table is small and directly prevents the Peirce failure mode: vocabulary-only compliance. It is a low-cost closure fold and should not be left to implementation.

### Batch 7 — `__import__` Receipt Parity

Seats STILL OPEN: Pauli.  
Seats NIT: Arendt.  
Seats CLOSED: Peirce, Huygens, Ohm, Lovelace / Bernoulli.

v1.2 already requires dynamic import/reflection restrictions and W#7 fixtures for dynamic import and shim/importlib/getattr/shared-helper laundering. Pauli and Arendt noted that the pass-2 checklist explicitly named `__import__`, while v1.2 does not spell `__import__` in the W#7 anchor text.

Current v1.2 evidence cited:

- `spec-brief.md:127`: alias/dynamic import/runtime provenance prose.
- `spec-brief.md:384-389`: W#7 anchors.

Synthesis call:

Fold as NIT in v1.3: explicitly include `__import__` in W#7e or W#7f. This is receipt parity, not a reopened structural gap.

### Batch 3 — Divergence vs Refused/Stale Wording

Seats NIT: Arendt.  
Seats CLOSED: all others.

Arendt flagged that `spec-brief.md:318-319` groups refused/diverged/stale under one "OR acknowledgment" sentence. Elsewhere the spec says staleness requires re-witnessing, so the material rule is clear, but canonical text should split divergence from refused/stale.

Synthesis call:

Fold as NIT in v1.3: separate the sentence into:

- refused/stale generations cannot ratify until re-witnessed;
- divergent generations can ratify only when the exact divergence generation is acknowledged.

### Batch 8 — Live FD Spelling

Seats NIT: Huygens.  
Seats CLOSED: all others.

Huygens noted W#8b says "live fds"; spelling out `*.db`, `*-wal`, and `*-shm` would match pass-1 wording exactly.

Synthesis call:

Fold as NIT in v1.3: make W#8b name live `*.db`, `*-wal`, and `*-shm` file descriptors.

---

## Material Outcome

v1.2 should not proceed to canonicalization yet.

The v1.3 fold is narrow:

1. Add WAL/concurrent DB cursor semantics + W#5g.
2. Add subprocess-count/no-rerun ratification test + W#cost / W#13c.
3. Add per-reason refusal-path matrix for `WitnessRefusalReason`.
4. Fold three NITs: explicit `__import__`, split divergence/refused/stale wording, spell out live `*.db` / `*-wal` / `*-shm` fds.

No council pass-2 is indicated. No covenant-axis escalation surfaced.

---

## Recommended Next Step

Fold `spec-brief.md` from v1.2 to v1.3 using the narrow list above, then dispatch Codex pass-3 as a closure-only check against the v1.3 deltas.

If pass-3 returns CLOSED / NIT-only, canonicalize as Decision 41 / ADR 0046.

