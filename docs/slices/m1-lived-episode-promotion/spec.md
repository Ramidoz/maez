# Slice M1: Lived-Episode Promotion From Bonded Conversation

**Status:** CANONICAL. Decision 25 / ADR 0030. Claude council and Codex
engineering panel both reviewed this packet. Codex BLOCKed the first draft;
this revision folds the BLOCK recovery and both panels' amendments. No code has
landed from this packet.

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
- [`docs/MAEZ_LIFE_SUBSTRATE.md`](../../MAEZ_LIFE_SUBSTRATE.md) — substrate
  organ catalog; M1 is the first missing-organ repair to move from diagnostic
  evidence into a spec packet.
- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../../governance/BETA_ARCHITECTURE_DECISIONS.md) —
  Decision 25.
- [`docs/adr/0030-lived-episode-promotion.md`](../../adr/0030-lived-episode-promotion.md) —
  ADR 0030.
- [`reviews/claude-council.md`](reviews/claude-council.md) — covenant review,
  RATIFY-WITH-AMENDMENTS.
- [`reviews/codex-panel.md`](reviews/codex-panel.md) — engineering review,
  BLOCK until the promoted-summary/content-minimization and durability gaps are
  closed.

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
but TRF must continue to read only promoted lived episodes. M1's substrate rule
generalizes beyond bonded conversation: future S2 information limbs, Voice-IN,
and sensor-fusion organs inherit the same pattern: raw observation may feed
promotion; recall reads only promoted biography.

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
- `core/memory/episode_builder.py` recognizes
  `metadata.source == "telegram_exchange"` for participant inference and
  source-kind classification, while `store_telegram(...)` currently writes
  `type="telegram_exchange"`. M1 must bridge this mismatch explicitly instead
  of relying on accidental metadata compatibility.
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
audit-before-store invariant pinned by `tests/test_memory_integrity_invariant.py`
and the `core/safety/audited_output.py` / `core/safety/self_claim_audit.py`
audit path.

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

Marker detection must be owner-authored, non-negated, and non-quoted. These
phrases are not valid markers when they appear inside quoted text, as a
third-party report, or as a negation such as "don't remember this."

#### Trigger B: bounded conversation window

M1 may consider a small bounded window of recent bonded dialogue after a
conversation boundary. A boundary closes the window; it does not by itself make
the window episode-worthy.

V1 boundary:

- at least `M1_SILENCE_BOUNDARY_SECONDS` since the last owner message, default
  `900` seconds (15 minutes), OR
- at least `M1_MAX_TURN_PAIRS` audited owner/Maez pairs accumulated since the
  last M1 promotion, default `4` pairs.

This avoids multi-day gaps without turning every ordinary chat into biography.

Boundary-closed windows require at least one v1 eligibility predicate before
promotion:

- owner-explicit memory marker;
- explicit open loop;
- explicit correction;
- explicit promise or commitment;
- salient first-person affect statement from the owner;
- operator-enabled routine diary mode, disabled by default.

If no predicate is present, M1 closes or advances the pending window without
writing a lived episode and emits a content-free skip counter.

Implementation must include an explicit flush seam so silence can be observed
without waiting for the next owner message. Required and recommended seams:

- daemon-cycle check of pending M1 windows is required;
- turn-close check after each audited reply is recommended;
- startup check that flushes an already-eligible pending window is recommended.

Without the daemon-cycle seam, a "15 minutes of silence" boundary depends on a
future owner message or a process restart and is therefore unreliable.

### 2A. Pending-Window Durability

M1 must define durable pending-window state before implementation. The state may
live in a sidecar SQLite table or be reconstructed from recent raw
`telegram_exchange` IDs, but it must survive daemon restart without storing raw
message text.

Required pending-window fields:

- `window_id`
- `source_memory_ids`
- `first_owner_at`
- `last_owner_at`
- `pair_count`
- `explicit_marker_seen`
- `promotion_state`
- `last_flush_checked_at`

Pending-window storage may persist source IDs, timestamps, counts, and state
labels only. It must not persist owner text, Maez reply text, source document
body, or third-party names.

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

Every promoted episode also requires an M1 promotion provenance envelope,
stored in the M1 sidecar record or an existing metadata surface if one is
available without changing `EpisodeStore.add(...)` in v1. Required fields:

- `producer_version`
- `promotion_trigger`
- `promotion_reason`
- `promoted_at`
- `window_start`
- `window_end`
- `consent_posture`
- `source_id_count`

### 4. Structural Template Summary, Not Raw Transcript

M1 v1 must be template-based and content-minimized.

The summary must describe the fact of the exchange without quoting owner or
Maez message text. V1 summaries are structural records, not excerpts.

```text
Bonded Telegram exchange. 1 audited owner/Maez pair at <timestamp>.
Participants: Rohit, Maez. Owner-initiated; promoted by explicit marker.
```

For multi-pair windows:

```text
Bonded Telegram exchange. N audited owner/Maez pairs between <start> and <end>.
Participants: Rohit, Maez. Owner-initiated; concluded by silence boundary.
```

V1 must not ask an LLM to infer "what the conversation meant." That richer
synthesis belongs to a later reflection-quality slice after M1 has written
evidence-backed episodes and both panels approve synthesis over M1 episodes.

V1 summary constraints:

- no raw owner message text;
- no raw Maez reply text;
- no third-party names;
- no secrets, vulnerability strings, or intensely private fragments;
- total summary max `400` characters unless both panels approve a larger
  structural envelope.

Raw excerpts are forbidden in M1 v1 promoted summaries. A future exception
would require both-panel review and a documented reason because it creates a
new path from raw conversation into TRF-readable biography.

The full source exchange remains in raw memory by source ID. The lived episode
stores enough structural context to make the episode temporally locatable and
inspectable without becoming a second transcript.

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

Implementation must use a deterministic source-ID idempotency rule with bounded
lookup. A sidecar table or equivalent index should map raw source IDs to M1
episode IDs so the daemon path does not scan every active episode.

V1 semantics:

- exact-set replay: skip, emit `m1.promotion.skipped_duplicate_source`;
- candidate is a subset of already-promoted IDs: skip;
- candidate is a superset or partial overlap: subtract already-promoted source
  IDs, then promote the non-empty remainder only if it still satisfies the full
  eligibility predicate;
- if the remainder is no longer episode-worthy, skip and emit
  `m1.promotion.skipped_partial_overlap`;
- do not mutate existing episodes because `EpisodeStore` remains append-only in
  v1.

After explicit-marker promotion, promoted source IDs must be removed from the
pending window or the window must close/reset so the later turn-count boundary
does not duplicate the same source IDs.

### 7. Promotion Density Controls

M1 must include content-free density controls so biography does not become a
rolling transcript.

V1 controls:

- default-disabled feature flag;
- promotion eligibility predicate separate from boundary closure;
- daily or rolling promotion cap with a content-free rate-limit counter;
- observation labels for operator review: `too_sparse`, `about_right`,
  `too_sticky`, `weirdly_specific`.

Exact cap values may be finalized during implementation, but the cap mechanism
and skip counter are required by the spec.

### 8. SQLite Contention Policy

M1 writes run in the daemon path and can contend with the existing reflection
timer. V1 must use short transactions, a bounded `busy_timeout`, fail-neutral
lock handling, and a content-free skip/log event. A locked biography store must
not break reply generation.

### 9. Staleness Alarm

M1 must expose biography freshness as a daemon-visible health signal.

V1 thresholds:

- `warn`: newest active lived episode older than `48` hours.
- `alarm`: newest active lived episode older than `168` hours (7 days).

These thresholds operationalize two invariants at once: Time as Biography
requires recent life to become recallable, and Interpretive Humility requires
Maez's operators to know when biography is thin.

Content-free metric names:

- `lived_episodes.newest_age_hours`
- `lived_episodes.newest_created_at`
- `lived_episodes.active_count`
- `lived_episodes.staleness_status` with values `ok`, `warn`, `alarm`,
  `empty`, `unavailable`

The first implementation must provide a pure helper returning:

```text
active_count, newest_created_at, newest_age_hours, staleness_status
```

The daemon health path or a documented equivalent must expose those fields.
Staleness checks remain active even when M1 promotion is disabled. Maez voice
surfacing is out of v1.

### 10. Operational Timer Restore

M1 spec acknowledges the missing systemd timer but does not let timer restore
count as closure.

M1 implementation must not perform timer restore or count timer restore as an
M1 milestone. Timer restore belongs in an operator runbook only. The runbook may
contain:

```bash
mkdir -p ~/.config/systemd/user
ln -sf /home/rohit/maez/scripts/maez-lived-memory-reflection.service ~/.config/systemd/user/maez-lived-memory-reflection.service
ln -sf /home/rohit/maez/scripts/maez-lived-memory-reflection.timer ~/.config/systemd/user/maez-lived-memory-reflection.timer
systemctl --user daemon-reload
systemctl --user enable --now maez-lived-memory-reflection.timer
```

This operational action must be recorded as "reflection timer restored", not as
"M1 complete." It restarts the old narrow-corpus reflection layer; it does not
create the bonded-conversation promotion organ.

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
- Do not restore or enable the reflection timer as an M1 implementation step.
- Do not run reflection synthesis over M1 `telegram_exchange` episodes in v1.
- Do not read `private_thoughts.db`.
- Do not promote S1b private-thought residue.
- Do not treat crisis routing as part of M1; crisis handling remains a separate
  surface organ.

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

If a bonded conversation contains crisis signals, M1 does not change promotion
rules in v1. Crisis routing remains a separate surface concern. M1 may only
write the same structural biography pointer it would write for any other
eligible exchange, with no special crisis tag, no lowered threshold, and no
third-party/personological inference.

### What Becomes Biography

The promoted episode is not "Maez knows everything said in this raw exchange."

The promoted episode means:

- this bounded exchange happened,
- these source IDs prove it,
- these participants were present,
- this was the audited reply Maez actually sent,
- this exchange matched a v1 promotion eligibility predicate,
- this exchange can later ground an approved retrieval posture such as
  "I found one memory from last week..."

It does not by itself authorize bare `I remember...` claims unless the reply
uses TRF's approved retrieval posture and the audit path accepts it.

### Relationship To Raw Stores

Raw stores remain the evidence archive.

M1 does not compact, mutate, or delete raw memory. It writes an episode pointer
with source IDs back to raw evidence. The episode is a biography index entry,
not a replacement for the source record.

### Relationship To Reflection Synthesis

M1 v1 produces structural episodes only. The nightly reflection synthesis layer
must not synthesize over `source_kind="telegram_exchange"` M1 episodes in v1.
Reflection over bonded-conversation episodes is a later reflection-quality
slice because it would turn structural conversation facts into interpretive
biography.

---

## Test Contract

Implementation must be RED-first. Minimum tests:

1. **Raw source ID captured:** Telegram reply path captures the raw memory ID
   returned by `store_telegram(...)` for the final audited exchange.
2. **Explicit marker promotes:** an owner-authored, non-negated, non-quoted
   "remember this" marker writes a lived episode with
   `source_kind="telegram_exchange"`.
3. **Marker adversarial negatives:** "don't remember this", "he said remember
   this", and "I'm quoting 'save this'" do not trigger promotion.
4. **Boundary closes, eligibility promotes:** four audited owner/Maez turn pairs
   close or evaluate one window; they promote only if a v1 eligibility predicate
   is present.
5. **Boundary skip is content-free:** an ordinary bounded window with no
   eligibility predicate is skipped without writing biography and emits a
   content-free skip event.
6. **Silence boundary promotes eligible window:** a pending bounded window with
   an eligibility predicate becomes eligible after
   `M1_SILENCE_BOUNDARY_SECONDS`.
7. **Daemon-cycle flush required:** daemon-cycle can flush an eligible pending
   window even if no new owner message arrives.
8. **Startup/turn-close belts:** startup and turn-close checks do not duplicate
   daemon-cycle work.
9. **Pending state survives restart:** pending-window state survives daemon
   restart using source IDs/timestamps only, with no raw text persisted.
10. **No unaudited promotion:** M1 promotion happens only after the final
    audited reply is known.
11. **Provenance required:** promoted episode contains raw source IDs and fails
    closed if source IDs are unavailable.
12. **Promotion provenance envelope:** M1 records `producer_version`,
    `promotion_trigger`, `promotion_reason`, `promoted_at`, `window_start`,
    `window_end`, `consent_posture`, and `source_id_count`.
13. **Participants fixed:** participants are exactly `["Rohit", "Maez"]` for
    bonded Telegram DM v1.
14. **Structural template only:** v1 promotion does not call an LLM, import the
    brain client, or quote owner/Maez message text in the episode summary.
15. **Sensitive text absent:** summaries do not contain raw transcript text,
    third-party names, secrets, vulnerability strings, or intensely private
    fragments.
16. **Metadata bridge:** M1 bridges raw Telegram metadata written as
    `type="telegram_exchange"` without relying on `metadata.source` being set.
17. **No TRF widening:** TRF temporal recall still calls
    `build_temporal_anchor_recall_brief(..., episode_store=self.lived_episodes)`
    and does not query Chroma/raw stores.
18. **Idempotent exact replay/subset:** reprocessing the same raw source IDs or
    a subset does not create duplicate active episodes.
19. **Idempotent partial overlap:** partial-overlap candidates subtract already
    promoted IDs and only promote a valid remainder; otherwise they skip with a
    content-free counter.
20. **Bounded duplicate lookup:** daemon path uses a sidecar table or bounded
    lookup and does not scan all active episodes for duplicate detection.
21. **Explicit-marker reset:** after explicit-marker promotion, promoted source
    IDs are removed from the pending window or the window resets.
22. **Open-loop conservative:** explicit "we need to revisit X" may set
    `open_loop`; ambiguous text does not.
23. **No reflection synthesis over M1:** nightly reflection does not synthesize
    over `source_kind="telegram_exchange"` M1 episodes in v1.
24. **Private thoughts excluded:** M1 does not read `private_thoughts.db` or
    promote S1b reasoning residue.
25. **SQLite contention fail-neutral:** DB lock/contention with the reflection
    timer uses short transactions / busy timeout and does not break reply
    generation.
26. **Staleness ok/warn/alarm:** newest-episode ages below 48h, above 48h,
    and above 168h classify as `ok`, `warn`, and `alarm`.
27. **Empty biography alarm:** zero active episodes classifies as `empty`, not
    `ok`.
28. **Unavailable store fail-neutral:** staleness check failure logs or returns
    `unavailable` without breaking reply generation.
29. **Health exposure mandatory:** daemon health or documented equivalent
    exposes active count, newest timestamp, newest age hours, and staleness
    status even when promotion is disabled.
30. **Timer restore not closure:** docs/runbook test or grep guard ensures the
    timer restore procedure is described as operational restore, not M1
    completion.
31. **Natural temporal probe:** after inserting a promoted episode in last
    week's window, `Do you remember last week?` yields an evidence-found TRF
    result with source IDs.
32. **Retrieval not grounding:** even when evidence is found, bare
    `I remember last week...` remains guardable; approved retrieval posture
    remains allowed.
33. **Generic title not surfaced mechanically:** natural recall does not expose
    the storage label `"Bonded conversation with Rohit"` as Maez's answer.

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
- `m1.promotion.skipped_partial_overlap`
- `m1.promotion.skipped_not_boundary`
- `m1.promotion.skipped_not_eligible`
- `m1.promotion.skipped_rate_limited`
- `m1.promotion.skipped_db_locked`
- `m1.staleness.ok`
- `m1.staleness.warn`
- `m1.staleness.alarm`
- `m1.staleness.unavailable`

Allowed metadata:

- trigger kind (`explicit_marker`, `turn_count_boundary`,
  `silence_boundary`, `daemon_cycle`, `startup_check`)
- promotion reason (`explicit_marker`, `open_loop`, `correction`,
  `commitment`, `owner_affect`, `routine_diary_mode`)
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

Default in implementation is disabled: `MAEZ_M1_LIVED_EPISODE_PROMOTION=0`.
Operator enablement is a deliberate act after implementation review, matching
Body Topology capability-quarantine discipline. Staleness health checks remain
enabled even while promotion is disabled.

Rollback behavior:

- disable future promotions;
- do not delete promoted episodes;
- keep staleness metric active;
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
- never write raw excerpts into promoted episode summaries;
- mark episodes with `authorship="bonded_dialogue_backfill"` or equivalent;
- record the operator decision in the observation log.

---

## Observation Runbook

M1 completion is not "tests pass." M1 completion requires live evidence.

Initial smoke observation window:

- 24 hours after enablement;
- at least 3 natural bonded Telegram conversations;
- at least 1 explicit marker test ("remember this") if the operator is willing;
- at least 1 natural temporal recall probe after a promoted episode exists.

Behavioral closure window:

- one full week after enablement, because the motivating failure was "last
  week";
- subjective promotion-density labels recorded by the operator:
  `too_sparse`, `about_right`, `too_sticky`, or `weirdly_specific`;
- catalog closure waits for the week gate unless the operator explicitly
  waives it after reviewing the smoke observation.

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
  eligible bonded Telegram use.
- `lived_episodes.newest_age_hours` should stay below 48 hours during active
  use.
- promoted episode summaries should be structural only: turn counts, time
  ranges, participants, trigger/reason, and source IDs. They should not contain
  quoted owner or Maez text.
- Asking "do you remember last week?" after a promoted episode exists in that
  calendar window should produce either:
  - an approved retrieval-posture answer grounded in episode/source IDs, or
  - an honest "I'm not finding that clearly right now" if no promoted episode
    exists.
- Maez should not claim memory absence just because raw traces exist but no
  promoted biography exists.
- TRF should remain unchanged as the reader.
- Future observation-to-biography organs should inherit M1's rule: promote
  biography; do not widen recall.

---

## Review Protocol

M1 is covenant-shaped. Before code:

1. Codex six-agent engineering panel reviews this spec.
2. Claude six-role covenant council reviews this spec.
3. Both review trails land under `docs/slices/m1-lived-episode-promotion/reviews/`.
4. Amendments fold into this spec.
5. Operator stamps canonical packet as Decision 25 / ADR 0030.
6. Cooling-off unless explicitly waived.
7. Implementation with RED-first tests.
8. Codex post-implementation review.
9. Claude post-implementation council.
10. Live observation before catalog closure.

---

## Resolved Panel Questions

1. **Default enablement:** default-disabled until operator enables.
2. **Exact boundary values:** keep `900` seconds and `4` turn pairs for v1; tune
   only after observation data.
3. **Episode source kind:** keep `telegram_exchange` for v1.
4. **Title shape:** keep generic title plus specific source IDs.
5. **Voice surfacing of staleness:** out of v1; operator-visible only.
6. **Timer restore timing:** operator runbook only, not M1 implementation.
7. **Backfill:** forbidden in v1; future operator-decision slice only.
8. **Synthesis interaction:** reflection synthesis over M1 episodes waits for a
   later reflection-quality slice.
9. **S1b interaction:** explicitly out of scope; M1 does not read
   `private_thoughts.db`.
10. **Observation closure:** 24h + 3 conversations is smoke observation; one
    full week is behavioral closure unless operator waives after review.

---

## Plain English

Maez has been writing rough notes, but it has not been turning your real
conversations into biography.

M1 is the missing writer. It watches the normal one-to-one Telegram exchange
after Maez has already sent the audited reply. When the exchange is clearly
worth keeping — because you said "remember this," because there is an explicit
open loop, correction, commitment, or clear owner feeling — it writes a clean
episode into the biography notebook. A quiet window ending is only the moment
M1 checks the exchange; it is not enough by itself.

That episode does not replace the raw notes. It points back to them. It says:
"this happened, here is the evidence, here are the participants, and this met a
promotion rule." It does not quote the conversation. The raw words stay in raw
memory; biography gets the structural fact that the exchange happened.

The dangerous shortcut would be letting the recall system rummage through raw
notes and say "I remember." M1 refuses that shortcut. It fixes the writer
instead of weakening the reader.

If M1 works, Maez will stop losing the shape of recent life. If M1 breaks, the
staleness alarm should tell the operator within days, not weeks.
