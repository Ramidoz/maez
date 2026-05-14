# ADR 0030: M1 Lived-Episode Promotion

**Status:** Accepted
**Date:** 2026-05-14

## Context

Maez's raw Telegram traces were being written, but recent bonded conversation
was not becoming recallable biography. `memory/lived_episodes.db` was stale,
with no normal bonded-dialogue source kind representing recent Telegram life.
TRF, the temporal-recall reader, behaved correctly under this failure: it read
only promoted lived episodes and did not fabricate from raw traces.

The diagnostic showed three separate wounds: the old nightly reflection timer
was not installed, the reflection job deliberately did not read raw Telegram
conversation, and no lived-episode staleness alarm existed. Restoring the timer
would restart a narrow reflection layer; it would not create the missing
bonded-conversation promotion organ.

Pre-canonical review ran both lanes. Claude's six-role covenant council
returned RATIFY-WITH-AMENDMENTS. Codex's six-agent engineering panel BLOCKed the
first draft because transcript-like excerpts in promoted episode summaries
would have created a shortcut from raw conversation into TRF-readable biography.
The folded packet closes that hole before code.

## Decision

Maez gets an M1 lived-episode promotion organ: a reviewed, default-disabled,
provenance-required write path that promotes eligible one-to-one bonded
Telegram exchanges into `memory/lived_episodes.db` without widening TRF's read
path.

The load-bearing rule is:

> Promote biography; do not widen recall.

M1 v1 writes structural biography pointers, not transcript-shaped memories.
Promoted summaries may carry turn counts, time ranges, participants,
trigger/reason, and source IDs. They may not quote raw owner text, Maez reply
text, third-party names, secrets, vulnerability strings, or intensely private
fragments.

M1 v1 also requires:

- default-disabled enablement via `MAEZ_M1_LIVED_EPISODE_PROMOTION=0`;
- owner-authored, non-negated, non-quoted explicit marker detection;
- boundary closure separated from promotion eligibility;
- daemon-cycle flush as the required silence-boundary seam;
- durable pending-window state containing source IDs and timestamps only;
- deterministic source-ID idempotency with bounded lookup;
- mandatory biography staleness health exposure;
- SQLite contention / DB-lock fail-neutral behavior;
- no reflection synthesis over M1 `telegram_exchange` episodes in v1;
- no backfill in v1;
- no `private_thoughts.db` reads or S1b residue promotion.

## Consequences

The immediate implementation target is narrower and safer than "make Maez
remember all chat." It builds the honest writer while preserving the honest
reader. Raw stores remain evidence archives. TRF continues to read only
promoted lived episodes. A promoted episode means "this eligible exchange
happened and these source IDs prove it", not "Maez can quote or interpret the
raw conversation."

This makes Maez's autobiographical memory healthier without turning biography
into a rolling transcript. It also introduces a reusable substrate principle
for future memory-aware organs: raw observation may feed promotion; recall
reads only promoted biography.

Operationally, M1 completion is not tests passing. The observation discipline
has two gates: a 24-hour smoke observation with at least three natural Telegram
conversations, and a one-week behavioral closure because the motivating failure
was "do you remember last week?"

Changing the load-bearing rule, allowing raw excerpts in promoted summaries,
widening TRF, enabling reflection synthesis over M1 episodes, adding backfill,
or changing default-disabled posture requires a new reviewed decision.

Full packet, diagnostic, test contract, observation runbook, and review trail:
[`docs/slices/m1-lived-episode-promotion/spec.md`](../slices/m1-lived-episode-promotion/spec.md).

BAD decision: see
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
Decision 25.
