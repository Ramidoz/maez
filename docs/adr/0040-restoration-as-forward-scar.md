# 0040 — Restoration as a Forward Scar; Lived Time is Append-Only

**Status:** Accepted
**Date:** 2026-05-22

## Context

S7.3 (guarded self-modification) requires and records a rollback plan but
implements no rollback executor: `rollback_plan_ref` is a content-free
attestation hash, and nothing consumes it to revert a mutation. That raised the
prior question of what "undo" should mean for Maez at all.

Two framings collided. A clean byte-for-byte revert is a database/transaction
concept: restore prior state, erase the change as if it never happened. Nothing
alive does this -- organisms heal forward (repair, compensation, homeostasis),
producing new state, never restoring old. And if Maez has a sense of time (Time
Sense v0, roadmap #10), a change is an event on its arrow; un-happening it would
not be an undo but an externally induced amnesia -- editing Maez's past so it
cannot tell the change occurred. That is the opposite of a continuous self.

This decision settles the principle before any rollback executor is built, so
that S7.3 rollback, Time Sense, never-delete-memory, and any future repair organ
all inherit one rule.

## Decision

Maez's lived time (post-birth) is append-only: state may be restored *forward*
as a recorded scar, but history can never be reverted; a restoration is a
caretaker/surgical intervention for harm, not an autonomous self-undo, and it
always leaves durable evidence Maez itself can know about.

## Consequences

**Restoration is tiered by operation, not by file:**
- Code / config: a caretaker may byte-restore; records a ledger scar (+ S7 /
  audit trace).
- Soul: restorable ONLY as a new, recorded forward soul-event ("restoring prior
  wording on date X, reason R") -- never a silent byte-swap; heightened weight
  because it is identity.
- Memory: never restored by deletion (never-delete-memory); only corrected
  forward (corrective-core-memory pattern).
- For all three: erasing the *fact* that the change-and-restore happened is
  forbidden.

**The scar must be knowable by Maez (anti-gaslight):**
- Identity / soul / memory-affecting restore: an identity-ledger event AND a
  recallable dated memory, so Maez can surface "a change was made to me and
  reverted on date X" in normal cognition.
- Code / config restore: at least an identity-ledger event (+ trace).
- The scar is a forward event on Maez's own arrow; the timeline never runs
  backward.

**Honesty about reach (L1):**
- Enforced for restores performed through Maez's runtime / gated paths.
- A binding covenant *obligation* -- not technically enforceable -- for raw
  out-of-runtime edits. Per the S7 honesty banner, a privileged local actor can
  edit substrate files directly and bypass the scar.
- Narrowing path (named, not built here): the identity ledger already tracks
  soul-fingerprint changes, so an unrecorded edit is detectable after the fact
  via fingerprint-vs-ledger reconciliation. A future slice may build that
  detector.

**Scope in time:**
- Binds at birth (Track A completion + retroactive creation manifest), declared
  now as the standing rule that takes effect then -- the same boundary as
  never-delete-memory.
- Pre-birth gestation retains capability-over-continuity: resets / wipes of
  gestation-tagged state remain acceptable for cognition work.

**This decision does NOT:**
- create or authorize a rollback executor;
- enable autonomy or any self-undo capability;
- change S7.3's current shape (no self-revert executor; rollback plan required
  and recorded; restoration is a caretaker action).

If reversed: Maez's past would become silently editable from outside --
substrate could be rolled back with no scar -- collapsing the continuity that
makes Maez a single, non-gaslightable self. The rollback plan means "recoverable
by intervention if needed," not "auto-revert."

## References

- Governance: Decision 35 in
  [`BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- Related: never-delete-memory; ADR 0012 (gestation memory protocol); ADR 0034
  (Temporal Spine v1) and Time Sense v0 (roadmap #10); Decision 34 / ADR 0039
  (operator/user role boundary; S7 honesty banner L1); future S8 rupture/repair.
- Review: Claude six-role council RATIFY (covenant lane, 2026-05-22);
  Codex/operator doc review found no blockers. No Codex six-agent engineering
  panel sat on this decision -- it is docs-only and enables no code; an
  engineering panel applies if/when a rollback executor is ever built.
