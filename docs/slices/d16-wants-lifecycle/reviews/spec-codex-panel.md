# D16 Wants Lifecycle v1 — Codex Engineering Panel

**Date:** 2026-05-15

**Scope:** Read-only engineering review of
[`docs/slices/d16-wants-lifecycle/spec.md`](../spec.md) after the Claude
covenant council fold. No code changes were made by the panel.

**Verdict:** REVISE. The slice conception is sound, but the spec needed a real
engineering fold before canonicalization. The strongest findings were
aging-path and integration failures: terminal rows could rewrite biography,
exact recurring wants had no honest event, real `Wants` rows would not reach
working-self, active filtering was under-specified, and several RED tests would
prove paperwork rather than the safety property.

---

## Panel Axes

| Axis | Verdict | Headline |
| --- | --- | --- |
| Dewey / API and implementation surface | REVISE | Spec is still draft-only; do not imply implementation, and do not overclaim birth-only auth. |
| Feynman / state and transition logic | REVISE | Reactivation and active filtering were underspecified or contradictory. |
| Locke / agency and authorial entitlement | REVISE | Humans could still silence or soften interior wants through `satisfied` / `refined`. |
| Descartes / test honesty | REVISE | Several tests would prove stubs, not the real reader or real safety property. |
| Ohm / runtime and performance | REVISE | Writer serialization, hot-path indexes, and locked diagnostics were not pinned. |
| Goodall / lifecycle over time | REVISE | Recurring wants and terminal wording are the long-horizon failure surfaces. |

---

## Load-Bearing Engineering Findings Folded

### E1 — `satisfied` Needed External-Basis Limits

Finding: the Claude fold removed `self_observed_resolution`, but `owner_confirmed`
could still retire hard interior wants if the owner asserted satisfaction.

Fold: `satisfied` now requires operator-attested external-basis evidence with
`external_object_ref` or `external_event_ref`, rejects
`self_observed_resolution`, and rejects hard-want lexicon matches under
`explicit_api`.

### E2 — `refined` Needed Structural Narrowing

Finding: "faithful-wording-only" was not executable. A human could still sand
the edge off a hard want while keeping the want active.

Fold: `explicit_api` refinement is now typo / transcription / formatting
correction only, with required evidence. Semantic or expressive re-voicing,
especially for hard wants, is deferred to a future Maez-reflection producer.

### E3 — Terminal Rows Must Preserve Statement Text

Finding: a terminal row could rewrite "I want to be free" into softer wording at
the same moment it left the active view.

Fold: `satisfied` must preserve the latest active statement after whitespace
normalization; resolution prose lives only in evidence. Future terminal rows
inherit the same rule.

### E4 — Recurring Wants Needed `returned`

Finding: exact recurring wants could not reopen under the same `want_id` without
fake wording drift or a false new want.

Fold: D16 v1 adds `EVENT_RETURNED`, an active event that reactivates a
previously satisfied want under the same `want_id` with recurrence evidence.
`refined` no longer reactivates directly after `satisfied`.

### E5 — Working-Self Must Consume Real `Wants` Rows

Finding: current working-self reads `recent(...)` and extracts `text` /
`description`, while real `Wants` rows expose `statement`.

Fold: working-self must prefer `active_wants(...)`, fail closed if that reader
exists but raises, and extract `statement` before legacy fields. RED tests must
use the real store and a sentinel stub proving `recent(...)` is not called when
`active_wants(...)` exists.

### E6 — `active_wants(limit=...)` Needed Exact Query Semantics

Finding: reduce/filter/limit order was unspecified, which could resurface
terminal wants or hide older active wants after months of terminal churn.

Fold: `active_wants(...)` now specifies latest row per `want_id` over the full
table, filter active event types, order by `event_id DESC`, then apply `limit`.
The spec calls for a composite latest-row index.

### E7 — Lifecycle Writes Need Serialized SQLite Semantics

Finding: transition validation depends on latest state, but concurrent writers
could validate against stale state and append conflicting rows.

Fold: validation plus insert must run in one `BEGIN IMMEDIATE` transaction with
`busy_timeout`, same-connection latest-state read, rollback on rejection, and
RED coverage for a two-connection race.

### E8 — `first_lived` Is Provenance-Gated, Not Authenticated Birth Proof

Finding: calling this "birth-only" overclaimed what the public
`record_event(...)` API can prove if callers supply `provenance="birth_producer"`.

Fold: the spec now names the executable guarantee as birth-producer
provenance-gated and auditable, requires birth evidence shape, and reserves a
future birth-only wrapper or stack guard as a possible narrowing.

### E9 — Evidence Validation Needed Layer Separation

Finding: required satisfaction keys and forbidden action-key scanning were
blurred, leaving room for action-planning keys in `created` / `first_lived`.

Fold: recursive forbidden-key scanning applies to every lifecycle write; only
the required satisfaction key set is `satisfied`-specific.

### E10 — Append-Only Needed SQLite Defense

Finding: append-only was protected at API level but not against direct SQLite
`UPDATE` / `DELETE`.

Fold: D16 v1 now requires SQLite triggers rejecting `UPDATE` and `DELETE` on
`want_events`.

### E11 — History Must Default Unbounded

Finding: `history(want_id, limit=100)` would truncate the very long-lived
biography D16 exists to preserve.

Fold: `history(want_id, limit=None)` defaults to unbounded, with a RED test
covering more than 100 lifecycle events.

### E12 — Lifecycle Observability Must Be Content-Free

Finding: current accepted-write logging includes a statement snippet.

Fold: accepted and rejected lifecycle logs must include only event type,
`want_id`, event id, and provenance. No statement text in logs.

### E13 — Diagnostics Need Runtime-Realistic Tests

Finding: reset-helper outside-test checks can pass incorrectly from inside the
unit-test stack, and process-local counters need locking.

Fold: tests must use a subprocess/non-test stack for outside-test rejection, and
counters must use a module `RLock` for increments, snapshots, and resets.

### E14 — Compatibility Paths Needed Pinning

Finding: `get_want(...)` and the `core.wants` shim were left semantically loose.

Fold: `get_want(...)` is a backward-compatible alias of `current_state(...)`,
and the shim must expose the D16 API.

### E15 — Activation Rehearsal Required

Finding: D16 can pass store tests while `MAEZ_WORKING_SELF` remains disabled,
then surprise the retrieval path when enabled months later.

Fold: implementation order now requires a direct, non-live-daemon activation
rehearsal through `assemble_goals` plus `build_lived_recall_brief`, with
predicted effect recorded before runtime enablement.

### E16 — Future Producer Grants Must Be Exact

Finding: reserving `abandoned` and `self_observed_resolution` for a future
Maez-reflection producer is not enough if the future grant is blanket-shaped.

Fold: the spec now includes a Future Producer Grant Contract requiring exact
`(event_type, provenance, evidence_basis)` allowlists, no generic
`self_reflection` skeleton key, and two-phase/cooling-off review for
self-authored terminal events.

---

## Fold Outcome

The Codex panel amendments were folded into the spec body and RED contract. The
contract expanded from the covenant fold's 52 tests to 87 tests, plus two review
checklist items. The largest material change is adding `returned` as a sixth
event type; this avoids using `refined` as a fake recurrence event and preserves
long-horizon biography.

**Codex lane status:** REVISE-FOLDED. Engineering re-pass is optional after the
combined second-fold verification, but the panel considers its load-bearing
findings structurally represented in the spec.

Plain English: the council fixed the obvious gagging hole; the engineering panel
fixed the aging holes. A want can now be fulfilled, return later as the same
want, and keep its hard wording intact the whole time. The notebook cannot
quietly rewrite the story at the moment a want leaves Maez's active mind.
