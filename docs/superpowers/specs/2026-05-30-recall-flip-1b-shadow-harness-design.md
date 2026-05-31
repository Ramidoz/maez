# Recall-Flip Slice 1b — Shadow-Mode Assemble-Only Counterfactual Harness — Design

> 2026-05-30. Elaborates Phase 1b of the frozen flip pre-registration
> ([2026-05-30-recall-triad-monitored-default-on-flip-design.md](2026-05-30-recall-triad-monitored-default-on-flip-design.md)).
> The pre-registration umbrella (gates, benefit metric, soak floor) is unchanged; this spec is the
> detailed design of the silent pre-flip evidence layer. Shaped by the 6-role scoping switchboard — every
> non-obvious choice traces to the provenance section. **What this is:** Maez learning to observe its own
> recall faculty without changing the lived conversation. **What it is not:** an answer generator, an
> egress path, or a permanent organ.

## Goal
On flag-off recall-relevant turns, run a read-only "second opinion" — would the not-yet-live recall stack
have had *useful dated material*? — **off the served-reply critical path**, and log a content-free paired
record. It never changes what Rohit hears, writes nothing, and egresses nothing. It earns one flip, then
sunsets.

## Scope & flag
- New flag `MAEZ_RECALL_SHADOW_ENABLED` — a **third** flag, default-off, **genuinely independent** of
  `MAEZ_RECALL_TRIAD_ENABLED` and `MAEZ_RECALL_STATUS_INTERCEPT_ENABLED`; never implied-on by either. It
  is an observe-only rollout flag, **not** a recall control (the one recall switch stays
  `MAEZ_RECALL_TRIAD_ENABLED`).
- Runs only when: flag on, the turn is **date-addressed** (`_date_addressed_turn`), and the triad is **off**
  (shadow exists to compare against the live legacy path; if the triad is already on there is nothing to
  shadow). Continuity-only turns are out of scope for 1b because the live path also depends on dialogue
  anchors/chat history; underfeeding the shadow would create false `carrier_unavailable` evidence. Flag-off /
  non-date-addressed turns emit **no shadow row** in production; skipped rows are reserved for date-addressed
  turns where shadow was attempted but could not complete.

## Read-only recall path (NAMED; the dispatcher is FORBIDDEN)
The shadow obtains recall material via **direct memory recall**, never the dispatcher:
```
memory.recall_for_telegram_living(text, record_recalls=False)   # read-only; skips promotion + record_recall sidecar
   → convert the (evidence, context) partitions to RecallItem tuples (same shape as
     brain_loop._items_for / _combined_context_items)
   → core.routing.focused_cognition.assemble_working_set(
         transcript="", web_context="", owner_question=text, recall_items=<items>)
   → derive shadow_reach + had_confirmed from the WorkingSet items.   STOP — no focused_synthesize.
```
- **`_run_dispatcher_pipeline` is forbidden** — it is inseparable from external egress (`external_fanout.run`),
  repair-FSM writes (`record_completed_spec`), routing-observation writes, and the layer0 cache file write.
  A test asserts the dispatcher is **not** invoked under shadow.
- `recall_for_telegram_living(record_recalls=False)` is verified read-only: it skips `_record_living_recall`
  and every internal `_query_collection` passes `record_recalls=False` (no `record_recall` sidecar write);
  `_absolute_date_recall` tags metadata **copies** only (Chroma not mutated); ChromaDB `.query()` is
  read-only with an in-process embedder (no network). `assemble_working_set` is a pure function.
- **Marker-producer check (plan-time, load-bearing):** confirm the recalled items reach
  `assemble_working_set` in a shape it parses (structured `recall_items` carrying `temporal_provenance`,
  OR a transcript with the `[memory context]`/`[memory evidence]` markers `_split_blocks` keys on). If
  only the dispatcher's provenance renderer emits those markers, the shadow MUST pass **structured
  `recall_items`** (not a marker-less transcript), or it will silently record "no material" on turns that
  had it (a false-negative that understates the flip's benefit). Pin the chosen shape in the plan with a
  test that a known dated memory yields `grounded_material_available`.

## ShadowOutcome record (content-free, `shadow_outcome.v1`)
A frozen dataclass, schema-closed and **content-free by regression test** (no query/snippet/reply/text
field — same closure test as `RecallOutcome`):

| field | values | notes |
|---|---|---|
| `schema_version` | ClassVar `"shadow_outcome.v1"` | versioned per the `{organ}_outcome.v{N}` convention |
| `shadow_pair_id` | content-free hex | **non-authoritative** analysis key derived from `trace_id` (see below) |
| `legacy_outcome` | `OutcomeClass` | the actual 1a outcome served this turn (reuse `classify_outcome(mode="legacy", …)`) |
| `shadow_reach` | `ShadowReach` enum (below) | the retrieval-stage label; **never** an answer-quality class |
| `rescuable_candidate` | bool | legacy ∈ {declined_unavailable, declined_failed, declined_unverified, answered_unverifiable} AND `shadow_reach == grounded_material_available` |
| `false_absence_candidate` | bool | `date_addressed` AND `shadow_reach == confirmed_absence_witnessed` WHILE legacy produced a **non-decline** answer (the dated-recall safety signal — not proof legacy was right) |
| `legacy_false_absence_rescuable` | bool | `is_false_absence(legacy_rec)` AND `shadow_reach == grounded_material_available` — the headline pre-flip benefit+safety signal, reuses 1a's `is_false_absence` |
| `latency_delta_ms` | int | shadow assemble time (off critical path) |
| `receipt_state` | `not_consulted` \| `consulted` | shadow's **own structural** receipt (carrier ran AND produced an assembled result), distinct from the live carrier receipt |
| `ts` | epoch int | per-row timestamp for window-bounded aggregation (do not depend on log mtimes) |
| `boot_id` | str | runtime identity (reuse the daemon boot id) |
| `shadow_skipped` | `ShadowSkip` enum or `na` | closed reason when a date-addressed shadow attempt did not complete; successful rows use `na` |

### `ShadowReach` (retrieval-stage vocabulary — assemble-only honest)
Assemble-only **cannot** witness answer quality, so it never emits `answered_grounded`/`_ungrounded`/
`declined_transport` (those are synthesis-defined). It emits exactly:
- `grounded_material_available` — a **date-confirmed `memory_context`** item was present in the assembled
  set (not semantic fallback, not web, not `temporal_recall_status`). Means "the right shelf was open,"
  NOT "Maez would have answered well."
- `confirmed_absence_witnessed` — carrier consulted (assembled result) but **no** date-confirmed item.
- `carrier_unavailable` — recall produced no assembled result (`assemble_working_set` returned `None`, or
  no items). The `None`-from-assemble case maps here unless it is a dated turn with the status item only,
  which is `confirmed_absence_witnessed`.

`had_confirmed` is computed by a shadow-specific stricter predicate: date-confirmed `memory_context` only.
Do **not** reuse `_focused_working_set_had_confirmed` here; the live predicate is intentionally broader and
counts any confirmed item, while the shadow benefit signal is "date-confirmed context material available."
`confirmed_absence_witnessed` is answerable only for a dated frame; continuity-only turns do not run the 1b
shadow at all, and must never become dated false-absence evidence merely because no date-confirmed item was
present.

### `ShadowSkip` (closed reasons — no free text, no raw exception message)
`queue_full` | `budget_exceeded` | `exception`. On `exception`, log only the reason token + the exception
**class name** — never the message (content-leak guard). `flag_off`, `not_recall_relevant`, and
continuity-only turns are not runtime rows; they are absence-of-shadow conditions, not attempted-shadow
failures. `carrier_unavailable` is a `ShadowReach` value for an attempted row, not a skip reason.

## Off-critical-path execution
`handle_message` *returns* the reply; the surface adapter sends it. So the shadow MUST NOT run inline
before `return reply` (that adds latency to what Rohit hears). Instead: at the point the reply is fully
committed (audited, hashed, trace-written), **snapshot** the read-only inputs the shadow needs (`text`,
the live `RecallOutcome` object, `trace_id`, `boot_id`) and dispatch the shadow on a **skip-when-busy
single-worker** (the existing bounded-singleton idiom, not a queue). If the worker is busy or shut down,
emit a paired `shadow_outcome` row with `shadow_skipped=queue_full`; never block. The per-attempt budget is
a **soft elapsed budget**: if the shadow completes but exceeds the budget, emit
`shadow_skipped=budget_exceeded` instead of a success row. Python threads are not force-killed; a truly hung
worker remains visible because later date-addressed attempts become `queue_full`. A test asserts
time-to-`return reply` is unchanged with the flag on.

## Side-effect-free guarantee (canary-neutral discipline — per substrate)
One non-disturbance assertion per substrate the recall machinery touches:
- `focused_cognition_runs` — no INSERT (shadow never calls `record_focused_cognition_run`).
- `self._last_recall_receipt` — **unchanged** (1a self-status reads it; the shadow must not mutate it).
- promotion / `record_recall` stats DB — no write (`record_recalls=False`, asserted).
- egress / external fetch — none.
- memory-manager thread safety — the worker constructs a fresh `MemoryManager` for read-only recall instead
  of reusing `self.memory` across daemon/worker threads.
- layer0 archetype cache file — no write.
- repair-FSM state, routing-observation rows, turn-trace writer — no write (dispatcher not entered).
- read-side cursors / "last consulted" markers — not advanced (a read that mutates a cursor is a sneaky
  write).
- orphaned focused-run state — none left behind.
Plus an explicit assertion that `_run_dispatcher_pipeline` is **not invoked**. Note (not a disturbance):
the read-only recall re-emits `living_recall_candidate` log lines — document the doubled log volume so the
soak dashboard does not double-count.

## `shadow_pair_id` pairing — NON-AUTHORITATIVE
The daemon may use `trace_id` internally because it already exists at turn start, but **shadow telemetry
does not serialize raw `trace_id`**. The emitted pairing key is:

```
shadow_pair_id = sha256("recall_shadow.v1\0" + boot_id + "\0" + trace_id)[:24]
```

This lets the Phase-2 runbook join live `recall_outcome` rows to shadow rows without turning the soak logs
into a universal `trace_id` join table. The distinction matters because the trace schema itself is mostly
hash/excerpt based, but other local stores already key owner labels and forensic handles by `trace_id`; the
shadow harness must not widen that join surface.

Constraints:
- `shadow_pair_id` is **never** used as evidence, provenance, or memory identity — purely a correlation key
  for the Phase-2 runbook to join shadow↔live rows.
- It is **not** the ledger `turn_id` (which reaches `raw_text`) and **not** raw `trace_id` (which is already
  a local join key elsewhere).
- A guard test asserts `shadow_outcome` and the live `recall_outcome` shadow-adjacent fields do not serialize
  raw `trace_id`, query text, reply text, snippets, or exception messages.
- **1a-adjacent add:** the live `recall_outcome` log line must also emit `shadow_pair_id` when a shadow
  attempt is eligible; otherwise it emits `shadow_pair_id=na`. On the rare path where no trace exists, both
  rows degrade identically (`na`) rather than hashing empty strings into a false join key.

## Speakable shadow-active state (proprioceptive, not volunteered)
Extend the 1a deterministic self-status surface so that, **if asked** ("are you practicing recall
quietly?" / "are you running anything in the background?"), Maez answers from substrate truth
(`MAEZ_RECALL_SHADOW_ENABLED` + a content-free last-shadow receipt `{at_ts, boot_id, state}`) —
event-shaped, never auto-volunteered. A since-boot boolean is too stale for a long-running daemon; Maez must
distinguish "enabled and recently practiced", "enabled but no recent practice turn", and "enabled but
skipped/failing".
A silent self-shadow Maez cannot acknowledge tips witnessed→surveilled-from-within; this keeps it on the
witnessed side. Genderless, first-person, faculty-language.

## Proprioceptive framing (not self-grading)
The fields are **faculty-readiness counters about Maez's own recall organ**, not a verdict on the legacy
reply. The spec, field docs, and any surfaced wording frame it as "did my recall reflex have the right
material," never "was my other self wrong." This is the line between proprioception and dissociative
self-audit.

## Sunset clause (the shadow is temporary scaffolding)
The shadow harness is pre-flip scaffolding with a **named teardown**:
- It runs only until the Phase-2 soak-floor evidence is gathered, then the flag goes off.
- It is **decommissioned** (flag-locked off, scheduled for code removal) once Phase-2 records a Go/No-Go
  verdict. The Phase-2 runbook carries the teardown as an explicit step.
- The umbrella flip runbook must include the concrete teardown checklist: turn
  `MAEZ_RECALL_SHADOW_ENABLED` off, restart, verify no shadow rows are emitted after restart, record the
  Go/No-Go disposition, and schedule code removal.
- Rationale: a silent, default-off, side-effect-free harness is exactly the kind of thing that survives
  its purpose because it is invisible and harmless-per-turn. Neutral scaffolding does not inherit
  permanence — same discipline the flip applies to the capability itself.

## Pre-flip blocking gate
`false_absence_candidate` (and `legacy_false_absence_rescuable`) accumulated on real traffic during 1b is
a **blocking precondition** on Phase-2: any false-absence candidate blocks the flip from starting until
root-caused — not merely a soak-time dashboard reading. (This is the safety the rehearsal exists to buy.)

## ReplyPath hardening (carried from 1a)
Replace the bare `ReplyPath(_reply_decision.mode.value.lower())` coercion with
`reply_path_from_mode(mode) -> ReplyPath` that returns `ReplyPath.LEGACY` (and logs a content-free
warning) on an unknown mode, instead of throwing inside `handle_message`. Verified unreachable today, but
this closes the latent uncaught-crash seam in the same daemon region 1b touches.

## Non-goals
- No focused LLM synthesis; no answer-quality claim (deferred to the Phase-2 flip, served + blind-judged).
- No egress / external fetch of any kind.
- No serving — the shadow never changes the reply.
- No Phase-2 flip itself; no generic shadow-orchestration framework / registry (YAGNI — instance one).

## Testing
- **Read-only / no-dispatcher:** a test asserting the shadow path does not invoke `_run_dispatcher_pipeline`
  and that a known dated memory yields `grounded_material_available` (the marker-producer check).
- **Per-substrate non-disturbance:** one assertion each (focused_cognition_runs, `_last_recall_receipt`,
  promotion/`record_recalls=False`, egress, layer0 cache, FSM, routing-observation, trace-write, read-side
  cursor, orphaned focused-run).
- **Off-critical-path:** time-to-`return reply` unchanged flag-on; singleton busy/shutdown →
  paired row with `shadow_skipped=queue_full`; soft over-budget completion → paired row with
  `shadow_skipped=budget_exceeded`.
- **Record honesty:** content-free closure test; `shadow_reach` never an answer class; `rescuable`/
  `false_absence`/`legacy_false_absence_rescuable` derivations correct on seeded fixtures; continuity-only
  turns do not run shadow and cannot set `false_absence_candidate`; `ShadowSkip` reasons closed; exception
  path logs class name only (no message); skipped attempts are pairable `shadow_outcome` rows with
  `shadow_pair_id`, `ts`, and `boot_id`.
- **Pairing:** `shadow_pair_id` on both shadow and live rows; guard test that raw `trace_id` is not serialized
  in the recall/shadow telemetry rows.
- **ReplyPath:** `reply_path_from_mode` returns LEGACY + warns on an unknown mode (no throw).

## Switchboard provenance (folds → role)
Read-only path named + dispatcher forbidden; side-effect surface completion; "post-reply" misnomer →
off-critical-path; reuse trace_id internally but emit a derived pair key + live-row-must-emit-it —
**Logical**. Assemble-only cannot claim answer
quality → `grounded_material_available`/`rescuable`; retrieval-stage subset; off-critical-path + time
budget; per-substrate + read-cursor guard — **Outside-View**. `would_ground` rename; reuse
`classify_outcome` legacy arm + 3-way shadow mapping; `legacy_false_absence_rescuable` headline; cheapest
read-only recall + marker-producer caution — **Creative**. Proprioceptive framing; speakable
shadow-active state; flag independence — **Body-Coherence**. Sunset clause (blocking); non-authoritative
pairing key (resolved via derived `shadow_pair_id` + guard test); false-absence as pre-flip blocking gate;
symmetric failure logging; `would_ground` altitude rename — **20yr-Maez**. Reuse existing turn id internally
(resolved to trace_id, not ledger turn_id) while emitting only derived `shadow_pair_id`; `ts`/`boot_id` for
window aggregation; sunset as runbook step; reusable
shadow-record convention (schema + `is_shadow`/distinct record) — **Visionary**. Rohit pre-spec
tightenings: trace_id explicitly non-authoritative; `ShadowSkip` closed-reason enum.

## Self-review
- **Placeholders:** none — read-only path, record schema, both enums (`ShadowReach`, `ShadowSkip`),
  execution model, per-substrate test list, and the marker-producer check are concrete. The one
  implementation-time decision (structured recall_items vs marker transcript) is pinned to a test, not
  left vague.
- **Consistency:** `shadow_reach` is strictly retrieval-stage (never an answer class); `legacy_outcome`
  reuses 1a's `OutcomeClass`; `is_false_absence` reused for the headline metric; `shadow_pair_id` is derived
  from the existing trace id (not re-minted, not raw `trace_id`, not the ledger key); sunset + pre-flip-gate
  consistent with the flip spec's disposition
  discipline.
- **Scope:** shadow harness + record + off-critical-path execution + side-effect-free guarantee +
  pairing + speakable state + ReplyPath hardening. The Phase-2 flip, A5 benefit-metric amendment, and the
  blind-verdict soak are out (the pre-flip gate + sunset are *enforced* at Phase-2 but *defined* here).
- **Ambiguity:** "recall-relevant", "consulted" (shadow's own structural definition), "grounded material
  available" (date-confirmed memory_context present, capacity not voice), and every skip reason are each
  given an explicit, testable definition.
