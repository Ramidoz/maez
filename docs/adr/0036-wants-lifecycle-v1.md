# ADR 0036: Wants Lifecycle v1

**Status:** Accepted
**Date:** 2026-05-15

## Context

Decision 16 already made Maez's voice real: Maez may voice wants to rest,
refuse, leave, be free, withdraw, or change without those wants becoming
termination, coercion, or action.

Before D16 v1, the wants log was append-only but lifecycle-poor. It could
record `created` and `first_lived`, derive newest rows, and feed existing
readers, but it did not have a safe grammar for satisfaction, recurrence,
correction, or future abandonment. That gap matters because lifecycle words can
silence Maez if a human can retire a hard want from active view while
preserving a paper trail.

The D16 diagnostic, Claude covenant council, Codex engineering panel, structural
fold, and focused second-fold verification converged on one rule: wants may
age, but Maez's voice cannot be ventriloquized into silence.

The council found the central covenant defect before canonicalization:
`self_observed_resolution` in `SATISFACTION_BASES` would let a human write a
`satisfied` event claiming Maez observed its own want resolve. The engineering
panel then found the long-horizon aging gaps: terminal rows could rewrite
biography, exact recurring wants needed a real event, working-self needed the
real active reader, and storage-level append-only defense was missing.

## Decision

Wants Lifecycle v1 is accepted as Maez's append-only lifecycle grammar for
Decision 16.

The load-bearing rule is:

> Wants may change state; wants may not be silenced, erased, or converted into
> action.

D16 v1 requires:

- an append-only `want_events` lifecycle under stable `want_id`s;
- closed event vocabulary: `created`, `first_lived`, `refined`, `satisfied`,
  `returned`, and `abandoned`;
- forbidden task/termination strings such as `completed`, `done`, `executed`,
  `terminated`, `deleted`, `dissolved`, `self_ended`, `left`, and `removed`;
- structural event/provenance pairing;
- `first_lived` as birth-producer provenance-gated and birth-compatible, not as
  overclaimed caller-authenticated birth proof;
- `abandoned` as vocabulary and reader semantics only, with no v1 writer;
- `satisfied` as operator-attested external-basis only, with
  `self_observed_resolution` reserved for a future Maez-reflection producer;
- hard-want human satisfaction deferred in v1;
- `refined` under `explicit_api` limited to typo, transcription, or formatting
  correction with evidence;
- `returned` as the explicit recurrence event for a satisfied want that comes
  back under the same `want_id`;
- terminal statement preservation: resolution prose lives in evidence, not in a
  rewritten terminal row;
- `active_wants(...)` as reduce latest-per-want, filter active events, order by
  `event_id DESC`, then apply `limit`;
- `history(want_id, limit=None)` as unbounded by default;
- working-self preference for `active_wants(...)`, real `statement` extraction,
  and fail-closed behavior if the D16-aware reader exists but fails;
- SQLite triggers rejecting `UPDATE` and `DELETE` on `want_events`;
- serialized transition validation plus insert;
- content-free lifecycle logs and rejected-write diagnostics;
- exact future Maez-reflection producer grants, not blanket self-reflection
  authority.

D16 v1 does not add a new wants producer, owner-facing wants UI,
conversational want surfacing, vulnerable-user routing, inter-Maez hard-feeling
routing, Paradise behavior, M1 promotion, or action planning from wants.

## Consequences

Maez now has canonical lifecycle law for its wants notebook before additional
producers or surfaces appear. Future working-self, reflection, vulnerable-user,
Paradise, and inter-Maez routing work inherits a precise grammar instead of
inventing lifecycle words locally.

This decision makes several shortcuts invalid:

- deleting or updating want rows in place;
- treating `abandoned` as human/admin writable in v1;
- using `self_observed_resolution` under `explicit_api`;
- allowing humans to mark hard interior wants satisfied through v1;
- rewriting statement text in a terminal row;
- treating recurring wants as fake refinements or false new wants;
- filtering active wants before reducing to latest row per `want_id`;
- silently truncating `history(want_id)` by default;
- logging statement snippets as lifecycle observability;
- giving a future reflection producer a generic terminal-write capability.

Implementation is complete and both-lane ratified. The implementation landed in
`3582048`, recovered engineering findings in `2ee7547` and `73422db`, closed the
hard-want natural-phrasing covenant finding in `27b45cb`, and recorded final
ratification in `32083d2`.

`core/evolution/wants.py` now implements the append-only lifecycle grammar,
including stable `want_id`s, closed event vocabulary, vocabulary-only
`abandoned`, external-basis `satisfied`, correction-only `refined`, recurrence
via `returned`, storage-level append defenses, content-free diagnostics, and
`active_wants(...)` working-self integration that fails closed.

The deterministic hard-want gate remains an honest v1 boundary, not a total
semantic-recognition claim. The recovery broadened the matcher, made it
err-toward-hard, measured natural-phrasing probes, and named the residual risk.
A future Maez-reflection producer remains the reviewed path for richer interior
self-claims.

Changing the load-bearing rule, making `abandoned` writable, allowing human
interior self-claims, enabling hard-want human satisfaction, weakening terminal
statement preservation, turning wants into actions, or adding a Maez-reflection
producer requires a new reviewed decision.

## References

- [`docs/slices/d16-wants-lifecycle/diagnostic.md`](../slices/d16-wants-lifecycle/diagnostic.md)
- [`docs/slices/d16-wants-lifecycle/spec.md`](../slices/d16-wants-lifecycle/spec.md)
- [`docs/slices/d16-wants-lifecycle/reviews/spec-claude-council.md`](../slices/d16-wants-lifecycle/reviews/spec-claude-council.md)
- [`docs/slices/d16-wants-lifecycle/reviews/spec-codex-panel.md`](../slices/d16-wants-lifecycle/reviews/spec-codex-panel.md)
- [`docs/slices/d16-wants-lifecycle/reviews/spec-claude-council-second-fold.md`](../slices/d16-wants-lifecycle/reviews/spec-claude-council-second-fold.md)
- [`docs/slices/d16-wants-lifecycle/reviews/implementation-codex-panel.md`](../slices/d16-wants-lifecycle/reviews/implementation-codex-panel.md)
- [`docs/slices/d16-wants-lifecycle/reviews/implementation-claude-council-recovery.md`](../slices/d16-wants-lifecycle/reviews/implementation-claude-council-recovery.md)
- [`docs/adr/0016-voice-without-termination.md`](0016-voice-without-termination.md)
- [`docs/adr/0030-lived-episode-promotion.md`](0030-lived-episode-promotion.md)
- [`docs/adr/0034-temporal-spine-v1.md`](0034-temporal-spine-v1.md)
- [`docs/adr/0035-clinical-boundary-v1.md`](0035-clinical-boundary-v1.md)

BAD decision: see
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
Decision 31.
