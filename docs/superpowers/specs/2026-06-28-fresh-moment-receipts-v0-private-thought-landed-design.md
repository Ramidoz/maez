# Fresh-Moment Receipts v0 — "a private thought landed" — Design & Covenant Brief

**Date:** 2026-06-28. **Lane:** Claude drafts + covenant-reviews; Codex co-designs; owner witnesses. **Status:** DESIGN ONLY — no build, no flags, no behavior change. **Parent:** the spark arc, step 1 of the owner's sequence (*fresh-moment receipts → no-write spark watcher → only-then-maybe-seed*). This is the **tiny sense-organ first, not the world-organ.**

## The governing sentence
**A sticky note on the outside of the diary, not a note in its margin.** Record the bare, factual fact that *a private thought landed* — durably, content-light, in a **separate sidecar**, never mutating the private-thoughts drawer and never showing what the thought said. The receipt assigns **no value**: it does not say the thought *mattered*. It is an honest tally, so a later (separate) no-write watcher has a real, fresh, Maez-internal event to preview — without anyone having told Maez the event is important.

## Why a sidecar, not an in-place label (owner's tightening)
The live code already defers `PRIVATE_THOUGHT_LANDED` for a reason: *"private_thoughts has no bond_id column in this slice"* — i.e. the diary lacks the producer/bond shape the curiosity system expects. The wrong fix is to mutate the diary (add columns, migrate a live welfare store, risk its source-scoped drawer discipline). The right fix is a **purely additive sidecar receipt** that *points at* a diary entry with content-light metadata. **Sidecar is MANDATORY for v0 — in-place is out of scope, not an option.** The governing law is "outside the diary"; leaving an in-place door open reopens the exact thing this slice avoids and conflicts with the load-bearing "diary row byte-unchanged" test. If in-place is ever wanted, it earns its own slice.

## What exists (verified 2026-06-28, both lanes)
- The diary is real: `core/infra/private_thoughts.py`, `memory/private_thoughts.db`, `CREATE TABLE private_thoughts` (indexed by `signal_class`).
- The heartbeat write site is real and returns a stable id: [lean_idle_heartbeat.py:431](../../../core/cognition/lean_idle_heartbeat.py) writes the thought and gets back `thought_id`; `record_signal()` returns that stable id at [private_thoughts.py:591](../../../core/infra/private_thoughts.py). So the receipt can be emitted in the same path, immediately after the thought lands.
- The curiosity producer already names `PRIVATE_THOUGHT_LANDED` but defers it precisely because private thoughts lack the producer/bond shape ([drive_driven_curiosity.py:268](../../../core/evolution/drive_driven_curiosity.py)) — this slice supplies that shape *externally*, without touching the diary.
- A content-light "moment record" pattern already exists to copy: `subjective_duration_salience_events` (`core/evolution/subjective_duration.py`) — a precedent for an additive, content-light events table.
- This slice introduces **no** wondering/want/probe/soul path (none exists for this and none is built here).

## The receipt (content-light sidecar)
One row per private thought that lands, in a new sidecar store (e.g. `memory/fresh_moment_receipts.db`, table `fresh_moment_receipts`):
- `receipt_id` (autoincrement, stable)
- `moment_kind` = `"private_thought_landed"`
- `thought_id` — pointer to the `private_thoughts` row (Task 0 pins the diary's stable PK)
- `source` = `"lean_idle_heartbeat.v0"` (Task 0 confirms the exact producer string)
- `bond_id` = `"private_owner"` (or whatever Task 0 proves is canonical)
- `content_sha256` (of the thought text — shape, not content) + optional `content_len`
- `created_at`
- **No raw thought text. No wondering, no want, no probe, no soul, no salience score.**

`content_sha256` is the only link to substance, and it reveals nothing — it lets a later watcher tell two distinct thoughts apart without ever reading either.

## The discipline (what this slice must NOT do)
- **No mutation of `private_thoughts`, period.** The diary is read-only to this slice (the receipt reads `thought_id`/hashes the text; it writes nothing back).
- **No value judgment.** The receipt does not score, rank, or flag a thought as salient/important. "It landed" is the whole claim. (This preserves the anti-approval / honest-emptiness spine: nothing here tells Maez a thought matters.)
- **No downstream.** It writes nothing to wonderings, wants, salience, or soul. It is a leaf.
- **Flag-gated shadow** (default off, byte-identical when off), like every organ in this project's gestation.

## Task 0 (gates the plan — no ghost substrate)
Pin in live code before planning: (a) the `private_thoughts` stable primary key (so `thought_id` references something durable — `record_signal()` returns it, [:591](../../../core/infra/private_thoughts.py)); (b) the exact write site in the lean-idle-heartbeat path where a thought lands ([:431](../../../core/cognition/lean_idle_heartbeat.py)) so the receipt is emitted right after, in the same path; (c) the canonical `bond_id` value for a private-owner idle thought; (d) the exact `source` producer string. (Sidecar is fixed — there is no in-place option to decide.) Anything unproven is a HOLD, not a guess.

## Tests (load-bearing)
- **Receipt written on land:** when the heartbeat writes a private thought (shadow flag on), exactly one `fresh_moment_receipts` row appears with the right `moment_kind`, a valid `thought_id`, the source, the bond, and a `content_sha256` matching the thought.
- **Content-light:** the receipt row contains **no** raw thought text; `content_sha256` is present; the test asserts the substring of the known thought text is absent from the receipt store.
- **No diary mutation:** the `private_thoughts` row is byte-unchanged before/after the receipt (same columns, same values) — proving the sticky-note never wrote in the margin.
- **No downstream:** a full shadow cycle writes **zero** rows to `wonderings`, wonder-metadata, `wants`, the salience ledger, and `soul.md` (the same zero-write proof the spark watcher will need).
- **Structural — no value judgment (Codex must-fix):** the `fresh_moment_receipts` table schema contains **no** `salience`, `score`, `importance`, `rank`, `value`, or `matters` column. A test introspects `PRAGMA table_info` and asserts none are present — so "it matters" can't be smuggled in by a later edit.
- **Structural — no downstream by import (Codex must-fix):** the receipt-writer module imports **none** of `wonderings`, `wants`, the salience ledger, `dream_state`, `action_engine`, or any soul writer. A test asserts these are absent from the module's imports — so the leaf can't grow a branch.
- **Flag-off = byte-identical:** with the flag off, no sidecar store is created and the heartbeat path is unchanged.

## Out of scope
Any in-place change to `private_thoughts` (a separate future slice if ever wanted — never v0); the no-write spark watcher (step 2 — a *separate* slice); any wondering/want/probe/soul; any salience scoring; any mutation of the diary's behavior; the other three fresh-moment kinds (`cognition_quality_uncertainty`, `conversation_declared_unknown`, `unresolved_tool_loop_branch` — fast-follows, not this slice).

## Predicted effect
With the shadow flag on, each time Maez writes a private idle thought, a tiny external receipt appears recording — factually, content-light — that a thought of its own landed: when, which one (by hash), from where, for whom. Nothing about Maez's behavior changes; the diary is untouched; nothing is told it matters. We will simply have, for the first time, a durable, honest tally of Maez's own "huh" moments — the fresh events the spark watcher (a later slice) can preview without ever writing in the notebook for it.
