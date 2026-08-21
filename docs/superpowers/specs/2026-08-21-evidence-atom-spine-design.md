# Evidence-Atom Spine — design pass 7 (one complete schema)

Status: DESIGN, pass 7. Gate: pass 1 (12 blockers) → 2 (10 open, 8 new)
→ 3 (8 closed) → 4 (1 closed, 5 new) → 5 (4 dissolved, 1 closed, 5 new)
→ 6 (**1 closed, 10 open**; 17 false receipts admitted). Reports at
`2026-08-21-spine-gate-round{1..6}.md`. Scope unchanged: D1 atoms +
D2 lineage; D3/D4 deferred with their own gate.

## 0. Why round 6 admitted so much — and the correction

Pass 6 was a **delta document**: "only the changed constructs are
shown, the rest of pass 5's schema stands." The gate had to reconstruct
a "strongest charitable assembly," and the seams between the two passes
were exactly where 17 false receipts walked through. A schema described
across two documents is not a schema.

Pass 7 is therefore **one complete, executable file** — 14 tables, 38
triggers, instantiated and attacked before being written down. No
deltas, no "the rest still stands."

## 1. My capture-order derivation was wrong

Pass 6 derived "children first, parents last" from the fact that
ancestry points backwards in time. The gate found the counterexample:
with child-first capture, a parent row created *after* the child
snapshot still appears in the later parent manifest — and membership
alone cannot tell "was already there" from "appeared afterwards". That
turns a future-created row into **false ancestry**. Undercounting is
safe; inventing ancestry is not.

**Corrected: capture parents first (raw → daily → core)**, which the
gate calls proof-safe, and pay the undercount. And the proof is no
longer trusted to ordering at all — it is enforced (§2, `edge_resolution_is_proved`):
a parent may be marked resolved only if it is in this run's membership
for its own layer **and** that layer's capture boundary closed no later
than the child layer's boundary opened. Every unproved edge is
`parent_resolved = 0` and counts as unknown.

Measured snapshot cost (executed, read-only, live stores): raw 191.0 ms
/ 516.76 MB / 44,037 ids; daily 2.2 ms / 3.51 MB / 92 ids; core 1.8 ms
/ 2.89 MB / 208 ids. Total **195 ms, 523 MB transient**, 327.8 GB free.

## 2. The schema

Every hash column is 64 lowercase hex, enforced. Every table is
append-only by trigger. `scan_runs.run_ordinal` and
`verification_runs.verify_ordinal` are UNIQUE and monotonic, which is
what makes "the most recent covering verification" a defined query
rather than a wish.

**The schema lives in one file, not in this document.**
`docs/superpowers/specs/2026-08-21-spine-schema-v7.sql` is
authoritative: 14 tables, 52 triggers, `integrity_check=ok`.

This document deliberately does **not** embed a copy. Round 6 admitted
17 false receipts precisely because the schema was split across two
documents and had to be reassembled; the confirmation round then found
the same failure returning as drift — the embedded copy had already
fallen behind the file (`lineage_summary.child_layer` was missing from
it). One artifact, one truth: read the `.sql`.



## 2.1 Pass 7.1 — four holes I found in my own schema

Before the gate reported, I ran the round-7 attack directions against
pass 7 myself. Four succeeded. Fixed and retested in both directions:

| Self-attack | Fix |
|---|---|
| A run closes `complete` while membership rows have **neither** atoms **nor** a gap row — silent incompleteness wearing a completed badge | `scan_complete_requires_full_disposition`: every membership row must have a completion marker or a gap row |
| A run records `SNAPSHOT_FAILED`, then closes `complete` anyway — laundering a failed scan | `snapshot_failure_forces_abort`: such a run may only close `aborted` |
| A `lineage_summary` for a child that appears in no membership — ancestry for a memory the run never saw | `lineage_summary_child_is_real` |
| `run_ordinal` advancing while `started_ts` goes backwards, so "the prior run" and "the most recent verification" stop meaning the same thing | `run_ordinal_monotonic_with_time` |

Honest paths re-checked, not just the forbidden ones: a run **does**
close `complete` once every membership row is disposed, and a
snapshot-failed run **does** close as `aborted`.

**One attack I deliberately did NOT block.** Two runs may share a
`snapshot_digest` and `manifest_sha`. That looked like
cross-contamination, but it is the honest signature of *nothing having
changed between runs* — identical id lists hash identically. Blocking
it would reject a true state. The real obligation is a verifier check:
`manifest_sha` must equal the hash of the membership actually recorded
for that run. Restriction is not the same as correctness.


## 2.2 Pass 7.2 — two more, and the line between schema and verifier

| Self-attack | Outcome |
|---|---|
| Atoms of one row attributed to a **different** row in the same layer | Partially closable: the schema cannot see live bytes, but it can refuse a row whose atoms **disagree about their own row hash** — now enforced at insert, not only at seal (`occ_row_hash_consistent`) |
| **Gap spam**: dispose every row as a gap instead of investigating, then close `complete` | A gap is sometimes the truth, so it is not forbidden — it is made **undeniable**: a run closing `complete` with any gaps must first declare them in a coverage note (`gaps_must_be_declared_before_complete`) |

The wrong-row attack is the honest boundary of what any schema can do.
A *fully* self-consistent misattribution — every atom of row B carrying
row A's content and A's hash — is invisible inside the file, because
the truth is in the live store. It cannot earn a PASS: the verifier's
`row_covered` check reads the real row, hashes it, and fails. So the
receipt can exist but can never be read as evidence.

That is the division this design keeps making: the **schema** stops
what is expressible in the file, the **verifier** stops what requires
the world, and PASS is withheld until the verifier has spoken for every
row. Neither half is sufficient; naming which is which is what keeps
the claim honest.


## 2.3 Over-restriction check — an honest run must still complete

Seven rounds of adversarial review create a real pull toward proving
rigor by refusing more. A schema that blocks honest work is a failed
schema, so the design is checked in the constructive direction too: a
complete lifecycle, start to consumable evidence, with **16 steps and
zero blocks**.

1–5 open a run, capture `raw` then `daily` (parents first), record
membership for 3 rows, register the embedding contract.
6–9 atomize a row into two atoms that tile it exactly, embed both under
the contract, record the occurrences, seal the row.
10–11 atomize and seal the remaining raw row and the daily digest.
12 record lineage: one **proved** parent (membership + boundary) and
one honestly **unknown** ancestor, declared count 2.
13 close the run `complete` — permitted because every membership row is
disposed and there are no gaps.
14–16 open a verification run, record `row_covered` for every
membership row, close as `PASS`.

Result: the most recent covering verification reads `PASS`, so the run
is consumable as evidence; 4 atoms, 3 sealed rows, ancestry recorded as
1 known + 1 unknown.

This is the shape the whole design is for: a memory that is fully
visible, provably placed in its row, with ancestry that says exactly
how much it does not know — and no step of it is blocked by the rules
that stop the forgeries.


## 2.4 Pass 7.3 — the verdict round's six fixes

Round 8 returned **BLOCKED with exactly six named fixes** — and real
movement: N26, N29, N30 closed at design level, falsifier readiness
5/12 → 8/12.

The decisive false receipt was elegant: `row_count = 2`,
`membership = 0`, status `complete`, `PASS` with zero findings. Every
rule I had written quantified over *recorded* membership — and the
empty set satisfies "for all" **for free**. A run that recorded nothing
could claim to have verified everything.

| Fix | Rule |
|---|---|
| Bind declared counts to membership before `complete` | `complete_requires_membership_matches_counts` (also: no `complete` with zero captured layers) |
| `PASS` only for a completed scan, non-empty membership, and the full required-check set | `pass_requires_completed_scan_and_checks` |
| Close-state consistency — "finished but still running" is not a state | `close_state_is_consistent` |
| Layer-qualify lineage children — a `daily` child may not borrow a `raw` row's membership | `lineage_summary.child_layer` + updated `lineage_summary_child_is_real` |
| `ROW_VANISHED` requires **current absence**, not merely a prior sighting | `vanished_requires_current_absence` |
| Verification ordinal and time advance together | `verify_ordinal_monotonic_with_time` |

All six rejected on retest; the honest lifecycle still completes in 18
steps under all 49 triggers and ends consumable (`PASS`).

**A note on how one of those retests went.** My first honest-path probe
failed — and my instinct was that I had over-restricted. I had not: the
probe wrote completion markers claiming atoms that did not exist, and
`marker_binds_atoms` correctly refused. The test was wrong, not the
schema. Worth recording, because "my check failed, so my code is
broken" is exactly as unexamined as "my check passed, so my code is
right."


## 2.5 Pass 7.4 — the INSERT paths I left open

The confirmation round ruled 3 of 6 fixes correct and 3 **partial**,
with one clean pattern behind all three: **I guarded `UPDATE` and left
`INSERT` open.**

- A scan run could be *born* `complete`, or born already finished —
  skipping every close-time check at once: counts, membership,
  disposition, declared gaps.
- A layer could be inserted **after** the run closed, raising the
  declared `row_count` after the count↔membership check had already
  run, leaving a stored `complete`/`PASS` describing rows the scan
  never saw.

Fixed by three birth rules: `scan_runs_born_open`,
`scan_layers_only_while_open`, `verification_runs_born_open`. All four
attacks now rejected; the honest lifecycle still completes.

Also from that round: the required-check set was **necessary but not
sufficient** — `snapshot_digest_verified` was missing, so a PASS could
bind the manifest without binding the copied snapshot it was derived
from. Added; the honest lifecycle is now 19 steps.

The lesson generalises past this schema: **a rule enforced on one path
into a state is not a rule about that state.** Every guard here now has
to answer "and what about the other door?"

## 3. What the schema now refuses (round 6's admitted list, retested)

All executed in-memory against the file above; honest operations
re-checked in the same run so the rules are not merely restrictive.

| Round-6 attack | Now |
|---|---|
| Bogus `row_covered` subject not in membership | **rejected** |
| Verification run INSERTed already closed as PASS | **rejected** |
| Fail finding appended after PASS | **rejected** |
| Second contradictory PASS for one scan | **rejected** |
| Atom occurrence for a row not in membership | **rejected** |
| Occurrence whose `splitter_version` ≠ its run's | **rejected** |
| Completion marker whose `atom_count` lies | **rejected** |
| Marker with no atoms at all | **rejected** |
| Atom added after the row was sealed | **rejected** |
| `parent_resolved=1` for a nonexistent parent | **rejected** |
| `ROW_VANISHED` for a never-observed row | **rejected** |
| One-character manifest hash | **rejected** |
| Non-hex artifact hash / invalid contract JSON | **rejected** |
| Membership inserted after scan close; membership UPDATE/DELETE | **rejected** |
| PASS covering 1 of 2 membership rows | **rejected** |

Still ALLOWED, deliberately: an honest occurrence; an honest marker; a
resolved edge with membership **and** temporal proof; an honest PASS
covering every membership row; and a later verification run closing as
**FAIL** — honest disagreement must remain expressible.

## 4. What SQLite still cannot enforce (and the honest answer)

- `content_id == sha256(bytes)`, the vector re-embedding, the
  `occurrence_id` formula, and tiling are **verifier** obligations —
  SQLite has no sha256. They are bound to PASS by requiring a
  `row_covered` finding for **every** membership row, so a run that
  skipped them cannot close as PASS.
- `PRAGMA writable_schema` / `DROP TRIGGER` can still remove rules
  (gate round 5, executed). Answer unchanged and stated as a boundary:
  **detection, not prevention** — `schema_attestation` is recorded per
  run and re-checked; a removed trigger fails the check.

## 5. Unchanged from pass 6

Source-snapshot protocol (online backup → digest → manifest → immutable
read of the copy); `immutable=1` never used on a live store (it
silently omits committed WAL rows — reproduced); coverage begins at the
first manifest and says so; confinement by `O_EXCL|O_NOFOLLOW` +
`st_nlink` + ATTACH authorizer + pragma-verifying `open_spine()`; F5
fixture now exists (`tests/data/spine_mutations.json`, 73 entries,
oracle validated 73/73).

## 6. What this claims

The spine records what a consistent snapshot contained, names that
snapshot's boundary per layer, proves each atom's bytes and vector
recomputable from a recorded contract, proves each atom's place in its
row, marks ancestry resolved only with membership **and** temporal
proof, refuses to read as evidence without a covering PASS, and detects
tampering it cannot prevent.

Not meaning. Not importance. Not organ-readiness. Not completeness —
only that the edges of what it knows are written down.
