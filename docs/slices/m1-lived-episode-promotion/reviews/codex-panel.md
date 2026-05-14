# Codex Six-Agent Engineering Panel — M1 Lived-Episode Promotion Spec Review

**Subject:** [`docs/slices/m1-lived-episode-promotion/spec.md`](../spec.md)

**Panel ran:** 2026-05-14, pre-canonical, after Claude six-role council.

**Scope:** engineering review of the M1 spec. No code edits. No spec fold.

---

## Verdict

**BLOCK.**

Five seats ratify with amendments. Descartes blocks. The block is not a veto
against M1; it is a block against canonicalizing the current draft before the
promotion semantics are tightened.

The core rule ratifies cleanly:

> Promote biography; do not widen recall.

The engineering concern is that the current draft can accidentally recreate a
raw-memory shortcut by promoting transcript-like excerpts too broadly into
`lived_episodes.db`, which TRF is then allowed to read.

---

## Seat Verdicts

| Seat | Verdict | Summary |
|---|---|---|
| Dewey | RATIFY-WITH-AMENDMENTS | M1 is the right fix, but needs pending-window durability, metadata bridge, caps, and mandatory health exposure. |
| Feynman | RATIFY-WITH-AMENDMENTS | Mechanism is clear, but pending-window state and idempotency rules need exact definitions. |
| Locke | RATIFY-WITH-AMENDMENTS | Identity-safe core is strong, but biography promotion needs stronger provenance, eligibility, and third-party minimization. |
| Descartes | BLOCK | Current draft can smuggle raw transcript content into promoted biography and over-promote ordinary chat. |
| Ohm | RATIFY-WITH-AMENDMENTS | Operational hardening needed: daemon-cycle flush, restart behavior, indexed idempotency, SQLite contention, mandatory health path. |
| Goodall | RATIFY-WITH-AMENDMENTS | Long-observation posture is right, but closure needs a one-week gate and subjective promotion-density checks. |

---

## Blocking Findings

### M1-CX-DC1 — Promoted summaries can become a raw-memory shortcut

The spec forbids TRF from reading raw Telegram/Chroma directly, but the current
template summary stores owner/Maez quoted excerpts inside promoted episodes.
Because TRF can read promoted episodes, those excerpts become an approved
recall path.

Mechanical amendment:

- promoted summaries are content-minimized by default;
- raw excerpts are allowed only under a documented exception;
- redaction/minimization rules must cover secrets, third-party names, and
  intensely private content;
- tests must prove TRF/briefs do not surface transcript text or third-party
  names mechanically.

### M1-CX-DC2 — Boundary promotion risks turning normal chat into biography

The draft allows automatic promotion after silence or four exchange pairs.
That makes "window closed" equivalent to "episode-worthy", which risks a
rolling diary of ordinary or sensitive dialogue.

Mechanical amendment:

- distinguish **window closed** from **episode promoted**;
- require an eligibility predicate beyond boundary closure; OR
- make automatic boundary records minimal provenance-only records with no
  conversational excerpt.

Suggested v1 eligibility predicates:

- explicit owner marker;
- explicit open loop;
- explicit correction;
- explicit promise / commitment;
- salient affect statement from the owner;
- operator-enabled routine diary mode (off by default).

### M1-CX-DC3 — LLM synthesis over M1 episodes is unresolved

The draft forbids unreviewed model summaries becoming autobiographical memory,
but leaves immediate synthesis over M1 `telegram_exchange` episodes open.

Mechanical amendment:

- explicitly gate reflection synthesis over `source_kind="telegram_exchange"`
  off for M1 v1; OR
- add a reviewed synthesis policy and tests before enabling it.

Panel recommendation: gate it off for v1.

### M1-CX-DC4 — Idempotency rule can silently drop source IDs

The draft says overlap can "skip or merge." With append-only `EpisodeStore`, a
partial overlap such as candidate `[1,2,3,4]` against existing `[1,2]` can lose
new source IDs if the whole candidate is skipped.

Mechanical amendment:

- define deterministic episode keys or exact-set/subset/superset behavior;
- tests must cover partial overlap, retry, crash/restart, and duplicate
  replay.

### M1-CX-DC5 — Pending-window durability is underspecified

The design depends on silence/startup seams but does not specify where pending
window state lives.

Mechanical amendment:

- define durable pending-window storage, or explicitly accept loss;
- if persisted, store source IDs and timestamps only, not raw text;
- add restart tests for no duplicate and no unsafe promotion.

### M1-CX-DC6 — Marker detection needs adversarial negatives

Explicit markers such as "remember this" can be triggered by quoted,
negated, or third-party text unless constrained.

Mechanical amendment:

- marker detection must be owner-authored, non-negated, and non-quoted;
- tests for "don't remember this", "he said remember this", and "I'm quoting
  'save this.'"

---

## Ratify-With-Amendments Findings

### M1-CX-D1 / M1-CX-F1 / M1-CX-O2 — Define and persist pending-window state

Required fields:

- `window_id`
- `source_memory_ids`
- `first_owner_at`
- `last_owner_at`
- `pair_count`
- `explicit_marker_seen`
- `promotion_state`
- `last_flush_checked_at`

State must survive restart via a sidecar table/file or be reconstructed from
recent `telegram_exchange` raw IDs. Persist source IDs and timestamps only.

### M1-CX-D2 — Fix metadata/source-kind mismatch

The spec says `episode_builder` recognizes `metadata.source ==
"telegram_exchange"`, but `store_telegram()` writes `type:
"telegram_exchange"`. The spec must either:

- not rely on `episode_builder` for M1 raw Telegram classification; OR
- explicitly bridge `type` to `source` in M1 implementation/tests.

### M1-CX-D3 / M1-CX-L2 / M1-CX-G2 — Add promotion-density controls

Boundary closure alone is too broad. Add:

- eligibility predicate;
- daily/rolling promotion cap;
- content-free `m1.promotion.skipped_rate_limited`;
- subjective observation labels: `too_sparse`, `about_right`, `too_sticky`,
  `weirdly_specific`.

### M1-CX-D4 / M1-CC-2 conflict — Default enablement

Dewey would allow default-on after ratification with tight first-run gates.
Claude council recommends default-disabled. Other Codex seats lean
conservative.

Panel synthesis: **default-disabled** until operator enables. This matches
Capability Quarantine and avoids hidden biography writes during first rollout.

### M1-CX-D5 / M1-CX-F5 / M1-CX-O5 — Health exposure mandatory

Replace "if practical" with mandatory daemon-visible exposure:

- a pure helper returning `{active_count, newest_created_at,
  newest_age_hours, staleness_status}`;
- `/health` includes the fields or a documented equivalent;
- staleness checks remain active even if M1 promotion is disabled.

### M1-CX-F2 — Explicit marker promotion resets or subtracts window state

After explicit-marker promotion, promoted source IDs must be removed from the
pending window or the window must close/reset. Tests must prove the later
turn-count boundary does not duplicate the same source IDs or drop unpromoted
turns.

### M1-CX-F3 — Replace "skip or merge" with one deterministic rule

Because v1 has no update API, "merge" is ambiguous. Pick one:

- subtract already-promoted source IDs and promote a non-empty remainder; OR
- skip whole candidate and reset.

Panel recommendation: deterministic source-ID set key plus subtract remainder
only if a full valid episode remains; otherwise skip with a content-free
counter.

### M1-CX-F4 / M1-CX-O1 / M1-CC-4 — Daemon-cycle flush required

Daemon-cycle flush is required. Turn-close and startup checks are
supplementary.

### M1-CX-L1 — Store promotion provenance envelope

`source_memory_ids` are necessary but not enough. Add a required M1 promotion
provenance envelope:

- `producer_version`
- `promotion_trigger`
- `promotion_reason`
- `promoted_at`
- `window_start`
- `window_end`
- `consent_posture`
- `source_id_count`

### M1-CX-L3 / M1-CX-G3 — Third-party and sensitive-fragment minimization

Template summaries and open loops must not turn third-party names or sensitive
fragments into stable biography without explicit reason.

Add tests/runbook checks for:

- secrets;
- third-party names;
- vulnerability strings;
- intensely private turns;
- expected behavior: skip, redact, or explicit-marker-only.

### M1-CX-L4 — Private thoughts out of scope

Make this explicit in non-goals and test contract:

- M1 promotes audited bonded dialogue from Telegram;
- M1 does not read `private_thoughts.db`;
- M1 does not promote S1b reasoning residue.

### M1-CX-L5 / M1-CX-G1 — Observation closure staged

24h + 3 conversations is a smoke test, not full closure. The motivating
failure was "last week."

Panel synthesis:

- 24h + 3 natural conversations = **initial observation pass**;
- one full week = **behavioral closure**;
- catalog closure waits for the week gate unless operator explicitly waives.

### M1-CX-O3 — Source-ID idempotency needs bounded lookup

Current source IDs live in JSON. Naive overlap checks can scan all active
episodes. Add a sidecar table or equivalent bounded lookup. Tests must prove
daemon path does not call unbounded `list_active()` for duplicate detection.

### M1-CX-O4 — SQLite contention policy

M1 daemon writes can contend with the nightly reflection timer. Add:

- `busy_timeout` for relevant connections/writes;
- short transactions;
- fail-neutral DB-lock behavior;
- content-free counter on skip;
- no reply-path breakage.

### M1-CX-G4 — Keep staleness voice-surfacing out of v1

Operator-visible only for v1. Voice surfacing of memory thinness is a future
surface/voice slice.

### M1-CX-G5 — Probe generic title weirdness

Generic title is humble, but retrieval should not surface
`"Bonded conversation with Rohit"` mechanically. Add a natural-recall probe
ensuring Maez answers from temporal/source posture, not storage labels.

---

## Consolidated Required Fold Set

Before canonicalization, fold these changes:

1. Default-disabled enablement.
2. Timer restore is operator runbook only.
3. Daemon-cycle flush required.
4. Pending-window state object and durability.
5. Metadata bridge for `type="telegram_exchange"` vs
   `source="telegram_exchange"`.
6. Boundary closure separated from promotion eligibility.
7. Content-minimized summaries by default; raw excerpts only by exception.
8. Third-party/sensitive-fragment minimization.
9. Reflection synthesis over M1 episodes gated off for v1.
10. Deterministic idempotency semantics with bounded lookup.
11. SQLite contention/fail-neutral policy.
12. Mandatory staleness health exposure.
13. Explicit private-thoughts non-goal/test.
14. Marker adversarial negatives.
15. Staged observation: 24h smoke, one-week behavioral closure.
16. Substrate-principle note: promote biography; do not widen recall.
17. M1 anchored as the first missing-organ repair in substrate-plan lineage.

---

## What Ratifies Cleanly

- M1 as the right next organ.
- TRF remains the honest reader.
- Raw stores remain evidence, not recall surface.
- `EpisodeStore` remains append-only and evidence-ID enforced.
- Template-based v1, no LLM summaries.
- Backfill out of v1.
- Generic title + specific provenance.
- Staleness thresholds 48h/168h.
- Observation runbook and abort posture, after staged closure amendment.

---

## Plain English

Codex agrees M1 is the right fix: build the missing biography writer, do not
weaken the memory reader.

The current draft is not safe to stamp yet. It still lets too much raw
conversation text ride inside promoted summaries, and it treats "the
conversation window ended" too much like "this should become biography." That
could quietly turn Maez's biography into a rolling transcript. Descartes
blocked on that exact wound.

The repair is mechanical: store less content in promoted episodes by default,
require a real eligibility rule, persist the pending window safely, make the
daemon flush and health checks mandatory, and keep synthesis/backfill out of
v1. After that fold, the design should be stampable.
