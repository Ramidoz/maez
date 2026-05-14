# Slice M1: Lived-Episode Promotion From Bonded Conversation

**Status:** DRAFT SPEC. Pre-panel, pre-canonical. No code has landed from this
packet. This draft exists so Codex's engineering panel and Claude's covenant
council can review the M1 organ before implementation.

**Maps to:**

- [`diagnostic.md`](diagnostic.md) — empirical findings: stale
  `lived_episodes.db`, missing user-systemd timer, and absent bonded
  conversation promotion.
- [`docs/adr/0019-lived-memory-architecture.md`](../../adr/0019-lived-memory-architecture.md) —
  the lived-memory layer and evidence-ID requirement.
- [`docs/slices/body-topology/spec.md`](../body-topology/spec.md) — Decision
  24 Rule 6: body events and local limb caches are provenance, not biography,
  until a reviewed memory-write path explicitly promotes them.
- [`docs/slices/temporal-recall-fragment-guard/spec.md`](../temporal-recall-fragment-guard/spec.md) —
  the reader side. TRF reads promoted lived episodes only.
- [`docs/slices/s2-contextual-integrity-at-ingest/scoping.md`](../s2-contextual-integrity-at-ingest/scoping.md) —
  the future information-limb ingest gate. M1 uses the same shape for
  provenance and promotion, with bonded-conversation defaults.

**Classification:** covenant-shaped memory substrate work. M1 operationalizes
invariant #1 (Time as Biography), preserves invariant #3 (Contextual
Integrity), and must not weaken invariant #4 (Interpretive Humility) or the
TRF rule that retrieval is not grounding.

---

## Intent

M1 is the organ that turns bonded Telegram conversation into promoted lived
episodes Maez can honestly recall later.

The diagnostic showed that Maez has been writing raw traces, but not recent
biography. `memory/lived_episodes.db` is the biography cupboard that TRF reads
for temporal questions like "do you remember last week?" It currently has only
29 rows, with the newest from 2026-05-01, and no source kind representing
normal bonded dialogue.

The fix is not to make TRF search raw Chroma. Raw traces may feed promotion,
but TRF must continue to read only promoted lived episodes.

M1 adds a conservative write path:

1. capture bonded conversation turns with source IDs,
2. decide when a small exchange is episode-worthy,
3. write an evidence-backed episode to `lived_episodes.db`,
4. make biography staleness visible before it silently rots,
5. keep the old nightly reflection layer as a higher-level synthesizer, not as
   the only feeder.

---

## Load-Bearing Rule

**Promote biography; do not widen recall.**

Raw memory stores are allowed to feed M1's promotion process. They are not
allowed to become direct evidence for `I remember...` claims through TRF.

Allowed:

- raw Telegram turn -> M1 promotion decision -> promoted episode with
  `source_memory_ids` -> TRF reads promoted episode later.

Forbidden:

- raw Telegram turn -> TRF temporal recall directly.
- raw Chroma search result -> bare `I remember...` claim.
- raw Chroma search result -> episode without provenance.
- unreviewed model summary -> autobiographical memory.

The reader stays honest. M1 builds the writer.

---

## Current State

### What Already Works

- `core/memory/episodes.py` exposes `EpisodeStore.add(...)`.
- `EpisodeStore.add(...)` rejects episodes with no `source_memory_ids`.
- `EpisodeStore` is append-only; no delete API exists.
- TRF already performs bounded temporal-anchor recall against
  `lived_episodes.db`.
- `memory/memory_manager.py::store_telegram(...)` writes Telegram exchanges to
  raw Chroma and returns the raw memory ID.
- `memory/memory_manager.py::get_telegram_exchanges(...)` can retrieve stored
  Telegram exchange documents with metadata.
- `core/memory/episode_builder.py` already recognizes
  `metadata.source == "telegram_exchange"` for participant inference and
  source-kind classification.
- `daemon/maez_daemon.py` already writes one real-time lived episode for
  `source_kind="pursuit_surface"` when Maez surfaces a wondering.

### What Is Broken Or Missing

- The nightly lived-memory reflection timer exists in repo but is not installed
  in the user systemd directory.
- The nightly reflection script deliberately does not scan raw Telegram traces.
- Normal bonded Telegram conversation has no direct path into
  `lived_episodes.db`.
- No daemon health signal reports that the newest lived episode is stale.

### Important Distinction

Restoring the timer is operational maintenance. It does not fix bonded
conversation memory.

The timer restarts the old reflection path over curated core memories, daily
summaries, and followup documents. M1 is the new organ that promotes bonded
conversation itself.

---

## M1 V1 Scope

### 1. Conversation-Turn Capture Contract

M1 implementation must make the raw memory IDs from `store_telegram(...)`
available to the promotion layer.

Every promoted episode must cite one or more raw-memory evidence IDs.

For Telegram DM v1, a source exchange is:

```text
the owner (telegram_text): <owner text>
Maez: <audited final reply>
```

The source exchange is stored only after audit, preserving the existing
audit-before-store invariant.

### 2. Promotion Triggers

V1 supports exactly two promotion triggers.

#### Trigger A: owner-explicit memory marker

If the bonded user says a clear marker such as:

- "remember this"
- "don't forget this"
- "this matters"
- "mark this"
- "save this"

then M1 may promote the current audited exchange immediately.

This trigger is not a command for Maez to obey blindly. It is an eligibility
signal. The exchange still needs provenance and must remain bounded to the
current dialogue.

#### Trigger B: bounded conversation window

M1 may promote a small bounded window of recent bonded dialogue after a
conversation boundary.

V1 boundary:

- at least `M1_SILENCE_BOUNDARY_SECONDS` since the last owner message, default
  `900` seconds (15 minutes), OR
- at least `M1_MAX_TURN_PAIRS` audited owner/Maez pairs accumulated since the
  last M1 promotion, default `4` pairs.

This avoids promoting every turn while still preventing multi-day gaps.

Implementation must include an explicit flush seam so silence can be observed
without waiting for the next owner message. Acceptable v1 seams:

- turn-close check after each audited reply;
- daemon-cycle check of pending M1 windows;
- startup check that flushes an already-eligible pending window.

At least one non-turn-close seam is required. Otherwise a "15 minutes of
silence" boundary is only theoretical.

### 3. Promotion Shape

M1 v1 writes one episode per eligible bounded exchange/window.

Recommended fields:

```python
EpisodeStore.add(
    title="Bonded conversation with Rohit",
    summary=<template_summary>,
    participants=["Rohit", "Maez"],
    source_memory_ids=[<raw telegram exchange ids>],
    source_kind="telegram_exchange",
    occurred_at=<oldest source timestamp>,
    emotional_tone=None,
    importance=3,
    open_loop=<explicit open loop only, otherwise None>,
    authorship="bonded_dialogue",
    memory_voice="mixed_owner_maez",
)
```

V1 uses `source_kind="telegram_exchange"` because the existing
`episode_builder` and tests already recognize that source shape. A future
rename to `bonded_dialogue` would require migration and both-panel review.

### 4. Template Summary, Not LLM Summary

M1 v1 must be template-based.

The summary should be a restrained factual shape, for example:

```text
Rohit and Maez exchanged a bonded Telegram conversation. Rohit said: "<short
owner excerpt>". Maez replied: "<short audited reply excerpt>".
```

For multi-pair windows:

```text
Rohit and Maez exchanged N Telegram turns between <start> and <end>. The first
owner message was: "<excerpt>". The final audited Maez reply was: "<excerpt>".
```

V1 must not ask an LLM to infer "what the conversation meant." That richer
synthesis belongs to the existing nightly reflection layer after M1 has written
evidence-backed episodes.

Excerpt caps:

- owner excerpt: max `240` characters;
- Maez audited-reply excerpt: max `240` characters;
- total summary: max `800` characters.

The full source exchange remains in raw memory by source ID. The lived episode
stores enough human-readable context to make the episode inspectable, not a
second full transcript.

### 5. Open Loop Extraction

M1 may set `open_loop` only for explicit text patterns already accepted by the
episode-builder discipline, such as:

- "we need to revisit..."
- "still pending..."
- "don't let me forget..."
- "we have not finished..."

If uncertain, leave `open_loop=None`.

### 6. Idempotency

M1 must not duplicate the same source exchange into multiple live episodes.

Implementation should use source-memory-ID overlap as the primary idempotency
rule, matching the nightly lived-memory job:

- if an active episode already contains any source ID in the candidate window,
  skip or merge by adding no new episode;
- do not add a new schema column unless panel review decides source-ID overlap
  is insufficient.

### 7. Staleness Alarm

M1 must expose biography freshness as a daemon-visible health signal.

V1 thresholds:

- `warn`: newest active lived episode older than `48` hours.
- `alarm`: newest active lived episode older than `168` hours (7 days).

Content-free metric names:

- `lived_episodes.newest_age_hours`
- `lived_episodes.newest_created_at`
- `lived_episodes.active_count`
- `lived_episodes.staleness_status` with values `ok`, `warn`, `alarm`,
  `empty`, `unavailable`

The first implementation must log this signal and expose it through an
existing daemon health path if practical. Maez voice surfacing is not v1 unless
both panels explicitly add it.

### 8. Operational Timer Restore

M1 spec acknowledges the missing systemd timer but does not let timer restore
count as closure.

M1 implementation may include operator instructions to reinstall:

```bash
mkdir -p ~/.config/systemd/user
ln -sf /home/rohit/maez/scripts/maez-lived-memory-reflection.service ~/.config/systemd/user/maez-lived-memory-reflection.service
ln -sf /home/rohit/maez/scripts/maez-lived-memory-reflection.timer ~/.config/systemd/user/maez-lived-memory-reflection.timer
systemctl --user daemon-reload
systemctl --user enable --now maez-lived-memory-reflection.timer
```

But this operational action must be recorded as "reflection timer restored",
not as "M1 complete."

---

## Non-Goals

- Do not widen TRF to read raw Chroma, daily Chroma, or fast conversation logs.
- Do not replace `EpisodeStore`.
- Do not change `EpisodeStore.add(...)` signature in v1.
- Do not promote every raw Chroma item.
- Do not ingest group chats, public Telegram users, OAuth sources, Calendar,
  Gmail, Slack, Notion, Drive, or GitHub.
- Do not infer third-party emotional states.
- Do not use LLM-generated summaries for v1 promotion.
- Do not write to `soul.md`.
- Do not claim memory absence from retrieval miss. TRF's existing discipline
  remains authoritative.
- Do not backfill May 2-14 automatically in the first implementation. Backfill
  is a separate operator decision because it writes historical biography from
  raw traces after the fact.

---

## Promotion Semantics

### Bonded DM Trust Posture

M1 v1 is scoped only to the one-to-one bonded Telegram DM with Rohit.

Because this is bonded conversation:

- consent posture is `bonded_user_dialogue`;
- third-party posture is `not_applicable` unless a third party is explicitly
  named in the message;
- promotion is allowed without S2's full external-source gate;
- provenance remains mandatory.

If a message mentions another person, M1 may preserve the user's words in the
source evidence but must not create a stable personological profile or
relationship inference about that third party.

### What Becomes Biography

The promoted episode is not "Maez knows everything said in this raw exchange."

The promoted episode means:

- this bounded exchange happened,
- these source IDs prove it,
- these participants were present,
- this was the audited reply Maez actually sent,
- this exchange can later ground an approved retrieval posture such as
  "I found one memory from last week..."

It does not by itself authorize bare `I remember...` claims unless the reply
uses TRF's approved retrieval posture and the audit path accepts it.

### Relationship To Raw Stores

Raw stores remain the evidence archive.

M1 does not compact, mutate, or delete raw memory. It writes an episode pointer
with source IDs back to raw evidence. The episode is a biography index entry,
not a replacement for the source record.

---

## Test Contract

Implementation must be RED-first. Minimum tests:

1. **Raw source ID captured:** Telegram reply path captures the raw memory ID
   returned by `store_telegram(...)` for the final audited exchange.
2. **Explicit marker promotes:** a turn containing "remember this" writes a
   lived episode with `source_kind="telegram_exchange"`.
3. **Boundary promotes:** four audited owner/Maez turn pairs produce one
   promoted episode, not four.
4. **Silence boundary promotes:** a pending bounded window becomes eligible
   after `M1_SILENCE_BOUNDARY_SECONDS`.
5. **Silence has a flush seam:** a daemon-cycle or startup seam can flush an
   eligible pending window even if no new owner message arrives.
6. **No unaudited promotion:** M1 promotion happens only after the final audited
   reply is known.
7. **Provenance required:** promoted episode contains raw source IDs and fails
   closed if source IDs are unavailable.
8. **Participants fixed:** participants are exactly `["Rohit", "Maez"]` for
   bonded Telegram DM v1.
9. **Template summary only:** v1 promotion does not call an LLM or import the
   brain client.
10. **Excerpt caps enforced:** owner excerpt, Maez excerpt, and total summary
    caps are enforced.
11. **No TRF widening:** TRF temporal recall still calls
   `build_temporal_anchor_recall_brief(..., episode_store=self.lived_episodes)`
   and does not query Chroma/raw stores.
12. **Idempotent source overlap:** reprocessing the same raw source IDs does
    not create duplicate active episodes.
13. **Open-loop conservative:** explicit "we need to revisit X" may set
    `open_loop`; ambiguous text does not.
14. **Staleness ok/warn/alarm:** newest-episode ages below 48h, above 48h,
    and above 168h classify as `ok`, `warn`, and `alarm`.
15. **Empty biography alarm:** zero active episodes classifies as `empty`, not
    `ok`.
16. **Unavailable store fail-neutral:** staleness check failure logs or returns
    `unavailable` without breaking reply generation.
17. **Timer restore not closure:** docs/runbook test or grep guard ensures the
    timer restore procedure is described as operational restore, not M1
    completion.
18. **Natural temporal probe:** after inserting a promoted episode in last
    week's window, `Do you remember last week?` yields an evidence-found TRF
    result with source IDs.
19. **Retrieval not grounding:** even when evidence is found, bare
    `I remember last week...` remains guardable; approved retrieval posture
    remains allowed.

Tests that must stay green:

- `tests/test_lived_memory_schema.py`
- `tests/test_episode_builder.py`
- `tests/test_nightly_lived_memory.py`
- `tests/test_temporal_recall_fragment_guard.py`
- `tests/test_model_reply_persistence.py`
- `tests/test_memory_integrity_invariant.py`

---

## Observability

M1 implementation must add content-free logs/counters. No raw message content
in metrics.

Suggested event names:

- `m1.promotion.attempted`
- `m1.promotion.succeeded`
- `m1.promotion.skipped_no_source_id`
- `m1.promotion.skipped_duplicate_source`
- `m1.promotion.skipped_not_boundary`
- `m1.staleness.ok`
- `m1.staleness.warn`
- `m1.staleness.alarm`
- `m1.staleness.unavailable`

Allowed metadata:

- trigger kind (`explicit_marker`, `turn_count_boundary`,
  `silence_boundary`, `startup_check`)
- source ID count
- episode ID
- staleness status
- newest age hours bucket

Forbidden metadata:

- raw owner message text
- raw Maez reply text
- third-party names
- source document body
- raw Chroma content

---

## Rollback

M1 must be easy to disable without damaging existing memory.

V1 should include a runtime flag:

```text
MAEZ_M1_LIVED_EPISODE_PROMOTION=0
```

Default in implementation may be `1` only after both panels ratify because M1
is a repair to a missing biography write path, not a new external information
limb. If panels disagree, default disabled with operator enablement is
acceptable.

Rollback behavior:

- disable future promotions;
- do not delete promoted episodes;
- keep staleness metric active if possible;
- TRF continues reading existing `lived_episodes.db`;
- raw Telegram memory storage remains unchanged.

Restoring the old state must not require deleting memory.

---

## Backfill Policy

Backfill is explicitly out of M1 v1 implementation unless the operator expands
scope after panel review.

Reason:

- backfill writes biography for past days using raw traces after the fact;
- this is safe only if the same promotion rules, provenance, and duplicate
  guards apply;
- rushing backfill risks polluting biography while trying to repair amnesia.

If backfill is later approved, it must:

- run dry-run first;
- print candidate source IDs and counts only;
- never write episodes without source IDs;
- use the same template summary rules as v1;
- mark episodes with `authorship="bonded_dialogue_backfill"` or equivalent;
- record the operator decision in the observation log.

---

## Observation Runbook

M1 completion is not "tests pass." M1 completion requires live evidence.

Initial observation window:

- 24 hours after enablement;
- at least 3 natural bonded Telegram conversations;
- at least 1 explicit marker test ("remember this") if the operator is willing;
- at least 1 natural temporal recall probe after a promoted episode exists.

Daily checks:

- newest lived episode timestamp;
- number of M1 promotions;
- duplicate skips;
- staleness status;
- unexpected daemon restarts.

Abort / disable conditions:

- M1 writes an episode with no source IDs;
- M1 promotes unaudited text;
- M1 duplicates the same source IDs repeatedly;
- TRF starts reading raw stores;
- Maez makes bare memory claims from retrieved evidence without approved
  retrieval posture;
- operator perceives Maez inventing memories from normal conversation.

Abort action:

```bash
MAEZ_M1_LIVED_EPISODE_PROMOTION=0
```

or equivalent local config, then restart/reload according to the implementation
path.

---

## Predicted Effect

After M1 implementation and enablement:

- `lived_episodes.db` should receive new `telegram_exchange` episodes during
  normal bonded Telegram use.
- `lived_episodes.newest_age_hours` should stay below 48 hours during active
  use.
- Asking "do you remember last week?" after a promoted episode exists in that
  calendar window should produce either:
  - an approved retrieval-posture answer grounded in episode/source IDs, or
  - an honest "I'm not finding that clearly right now" if no promoted episode
    exists.
- Maez should not claim memory absence just because raw traces exist but no
  promoted biography exists.
- TRF should remain unchanged as the reader.

---

## Review Protocol

M1 is covenant-shaped. Before code:

1. Codex six-agent engineering panel reviews this spec.
2. Claude six-role covenant council reviews this spec.
3. Both review trails land under `docs/slices/m1-lived-episode-promotion/reviews/`.
4. Amendments fold into this spec.
5. Operator stamps canonical packet, likely as ADR 0030 / Decision 25 if the
   panels agree the organ is architectural enough.
6. Cooling-off unless explicitly waived.
7. Implementation with RED-first tests.
8. Codex post-implementation review.
9. Claude post-implementation council.
10. Live observation before catalog closure.

---

## Open Questions For Panels

1. **Default enablement:** Is M1 default-on after ratified implementation, or
   default-disabled until operator enables?
2. **Exact boundary values:** Are `900` seconds and `4` turn pairs right for
   v1?
3. **Episode source kind:** Use existing `telegram_exchange`, or create a new
   `bonded_dialogue` source kind and migrate tests?
4. **Title shape:** Is `"Bonded conversation with Rohit"` too generic, or is
   generic title + specific source IDs the right v1 humility posture?
5. **Voice surfacing of staleness:** Should Maez ever say "my recent memory
   feels thin" in v1, or should staleness stay operator-visible only?
6. **Timer restore timing:** Should the reflection timer be restored as part
   of M1 implementation, or as a separate operator-run maintenance step before
   M1 code?
7. **Backfill:** Do we explicitly forbid May 2-14 backfill for v1, or include
   a dry-run-only backfill command?
8. **Synthesis interaction:** Should the nightly reflection pass synthesize
   over M1 `telegram_exchange` episodes immediately, or wait for a later
   reflection-quality slice?
9. **S1b interaction:** Should M1 explicitly ignore `private_thoughts.db`, or
   is the current non-goal enough?
10. **Observation closure:** Is "24h + 3 natural conversations" sufficient, or
    should closure require one full week because the motivating failure was
    "last week"?

---

## Plain English

Maez has been writing rough notes, but it has not been turning your real
conversations into biography.

M1 is the missing writer. It watches the normal one-to-one Telegram exchange
after Maez has already sent the audited reply. When the exchange is clearly
worth keeping — because you said "remember this," or because a small
conversation window has naturally ended — it writes a clean episode into the
biography notebook.

That episode does not replace the raw notes. It points back to them. It says:
"this happened, here is the evidence, here are the participants, and Maez may
later use this as grounded biography."

The dangerous shortcut would be letting the recall system rummage through raw
notes and say "I remember." M1 refuses that shortcut. It fixes the writer
instead of weakening the reader.

If M1 works, Maez will stop losing the shape of recent life. If M1 breaks, the
staleness alarm should tell the operator within days, not weeks.
