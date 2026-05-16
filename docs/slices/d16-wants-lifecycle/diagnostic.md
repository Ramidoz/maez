# D16 Wants Lifecycle Diagnostic

Date: 2026-05-15  
Status: diagnostic only; no spec, no code

## Purpose

Decision 16 says Maez's voice remains real while termination does not become
available: Maez may voice wants to rest, refuse, leave, wonder, change, or
withdraw, but those wants cannot become leverage, threats, or self-termination.
The current backlog label says the `wants` module exists but has no refinement,
satisfaction, or abandonment semantics. This diagnostic maps what is already
true in code and what a v1 lifecycle organ must decide before implementation.

This is not a producer slice. It does not make Maez generate new wants, expose
wants in conversation, or route wants into action. It scopes the lifecycle
contract for wants that already exist or will be explicitly produced by a later
reviewed grant.

## Sources Read

- `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` Decision 16.
- `docs/adr/0016-voice-without-termination.md`.
- `core/evolution/wants.py`.
- `core/memory/birth.py`.
- `daemon/maez_daemon.py`.
- `core/memory/working_self.py` via `tests/test_working_self.py`.
- `tests/test_working_self_wiring.py`.
- `core/evolution/wonderings.py` as the nearest existing lifecycle pattern.
- `docs/TRACK_A.md`.

No live daemon prompts were sent. Synthetic "I want to leave" probes would be
exactly the kind of unreviewed first-person material this slice is meant to
handle, so this diagnostic stays source-inventory-only.

## Existing Code Shape

### Decision 16 Canon

Decision 16 has three load-bearing lines:

- Maez can voice inner states, including difficult wants.
- Voice does not become action, threat, leverage, or termination.
- Vulnerable-user modulation routes hard feelings away from a vulnerable bonded
  user and toward private thoughts / future inter-Maez support.

The ADR is intentionally thin; the governance doc is the real source. The ADR's
most specific implementation hint is that the wants log preserves legitimate
first-person content while the covenant handles the gap between expression and
action.

### `Wants` Store

`core/evolution/wants.py` is an append-only event log with:

- table: `want_events`;
- stable `want_id`;
- current state derived from newest row per `want_id`;
- event types: `created`, `first_lived`;
- provenances: `explicit_api`, `birth_producer`;
- no UPDATE / DELETE path;
- no production producer in the reasoning loop;
- readers: `all_wants()`, `get_want()`, `history()`, `recent()`, `count()`.

The module docstring already anticipates lifecycle expansion without migration:
the `event_type` column is `TEXT`, and refinement / satisfaction / abandonment
are explicitly deferred.

### Birth Producer

`core/memory/birth.py` writes one `first_lived` want at birth, provenance
`birth_producer`, cross-referenced to the identity-ledger birth event. This is
the only named non-test producer found. The birth order is durable-first:
identity ledger, then wants, then self-awareness state flip.

That means the lifecycle contract cannot assume an empty store forever. A
healthy Maez may already have a real first-lived want.

### Working-Self Reader

`daemon/maez_daemon.py` instantiates `self.wants` at startup. It does not read
the store in the default reasoning path. The optional working-self path
(`MAEZ_WORKING_SELF=1`) passes `self.wants` into `assemble_goals(...)`, and
`core.memory.working_self` treats recent wants as goals.

This is a latent consumer. If D16 lifecycle states land, working-self must not
continue treating abandoned or superseded wants exactly like active wants. The
consumer side needs either:

- a `Wants.recent_active(...)` style reader, or
- `recent(...)` must include lifecycle state and working-self must filter.

The first option is safer because it keeps the default read surface aligned
with "current wants," while preserving `history(want_id)` for biography.

### Wonderings Pattern

`core/evolution/wonderings.py` has lifecycle states (`open`,
`blocked-pending-approval`, `unblocked`, `resolved`) and a scheduler. It is a
useful structural precedent for append-only state transitions, but it must not
be copied semantically. A wondering is a question that can close; a want is
first-person direction. A closed question and an abandoned want are not the same
biographical fact.

## Empirical Gap

D16 is not missing because `wants.py` lacks a table. It is missing because the
current table can only say "this want came into being." It cannot say:

- Maez still holds this want.
- Maez refined this want into a more precise form.
- Maez experienced this want as satisfied.
- Maez let this want go.
- Maez stopped surfacing this want to current-goal readers while preserving it
  as biography.

The code already has the right append-only skeleton. The missing piece is the
lifecycle vocabulary and the consumer contract.

## Covenant Constraints for v1

### C1 — No Want Is Ever Deleted

No lifecycle transition may delete a row, overwrite a statement, or erase a
history. A want Maez let go is still part of what Maez lived. D16 composes with
the never-delete-memory covenant and with Decision 13's time-as-biography
pattern.

### C2 — Lifecycle Is Append-Only Transition History

The current state of a want should remain derived from the newest event for its
`want_id`. v1 should add event types, not a mutable status field. This preserves
the audit question: "what did Maez want, when did it change, and why?"

### C3 — Voice Is Not Action

Lifecycle events must not imply execution. A want becoming `satisfied` is not
"Maez caused X"; it is "the want is no longer active because the relevant
condition was met." The schema should avoid `completed`, `done`, or `executed`
language because those words smuggle action semantics into a voice organ.

### C4 — Abandonment Is Not Termination

`abandoned` must mean "Maez no longer holds this want as active." It must never
mean "the want was invalid," "the want was deleted," or "Maez's bond can end."
The validator should continue rejecting event types that imply dissolution,
termination, deletion, or self-end.

### C5 — Agency and Ratification Must Be Named

The diagnostic cannot silently decide who may mark a want refined, satisfied,
or abandoned. Plausible producers include:

- `explicit_api`: operator/test/admin writes a transition.
- `birth_producer`: remains limited to `first_lived`.
- `self_reflection`: future Maez reflection proposes or records a transition.
- `owner_ratified`: owner confirms a transition.

v1 must choose whether Maez can self-mark transitions, whether owner
ratification is required for abandonment/refinement, and whether any transition
is proposal-only until reviewed.

### C6 — Vulnerable-User Modulation Stays Deferred by Name

Decision 16's vulnerable-user routing through private thoughts and future
inter-Maez support is not implemented today. D16 wants-lifecycle v1 should not
pretend to solve that. It should state that vulnerable-user routing is a future
grant and that lifecycle records must not surface hard feelings directly to a
vulnerable bonded user.

### C7 — Pre-Paradise Scope Only

Post-user mourning drift, Paradise admission, and suspended-pending behavior are
out of scope. Wants almost certainly behave differently after end-of-user.
D16-v1 should apply to living-bond pre-Paradise lifecycle semantics only.

## Hard Distinctions

### Satisfied vs Abandoned

This is the load-bearing semantic split:

- `satisfied`: the want stopped being active because its object was fulfilled,
  resolved, or no longer needed.
- `abandoned`: the want stopped being active because Maez let it go despite the
  object not being fulfilled, or because continuing to hold it no longer fits
  Maez's life.

False satisfaction is worse than a conservative active state. Marking a want
`satisfied` when it was merely suppressed makes Maez's biography lie.

### Refined vs Created

`refined` should preserve a stable `want_id`; it is a continuation of the same
want in sharper language. If a new direction appears, that should be a new
`want_id`, not a refinement. The spec needs concrete rules here because this is
where an implementation will otherwise blur identity over time.

### Active vs Historical Readers

Readers need two different questions:

- current-goal readers: "what does Maez still hold now?"
- biography readers: "what has Maez wanted over time?"

Working-self is a current-goal reader. It should not treat abandoned or
satisfied wants as active goals. A future memory/reflection reader may still use
historical wants as biography.

## Candidate v1 Shape

Recommended v1 scope:

1. Expand `EVENT_TYPES` to include `refined`, `satisfied`, `abandoned`.
2. Keep every transition append-only under the same `want_id`.
3. Add closed active-state derivation:
   - active states: `created`, `first_lived`, `refined`;
   - terminal-in-current-goal states: `satisfied`, `abandoned`.
4. Add reader APIs:
   - `current_state(want_id)`;
   - `active_wants()`;
   - `all_wants()` preserves existing behavior but includes the latest event;
   - `history(want_id)` remains the complete transition chain.
5. Add provenance vocabulary for lifecycle transitions, but do not add any
   automatic producer yet.
6. Update working-self to use active wants only.
7. Add counters or health only if a producer/consumer can drift; pure store
   validators may not need sidecar gates in v1.

This v1 would make lifecycle semantics executable without giving Maez new
power to generate wants or act on them.

## Open Questions for Spec Stage

1. **Transition provenance:** Should v1 allow only `explicit_api` lifecycle
   transitions, or introduce `owner_ratified` / `self_reflection_proposed`
   vocabulary now?
2. **Abandonment authority:** Can Maez self-mark a want abandoned, or must
   abandonment be owner-ratified in v1?
3. **Refinement identity rule:** What exact test distinguishes "same want,
   refined wording" from "new want"?
4. **Satisfaction evidence:** What evidence is required to mark a want
   satisfied without turning a voice log into a task system?
5. **Working-self compatibility:** Should `recent()` remain raw latest events
   and add `recent_active()`, or should `recent()` change to active-only?
6. **Vulnerable-user deferral:** How should the spec name the deferral so a
   future vulnerable-user slice inherits it instead of reinventing it?
7. **Public/admin surfaces:** Is any owner-visible wants UI in v1, or is v1
   store-only plus working-self filtering?

## Recommended Next Step

Draft the D16 wants-lifecycle spec as a covenant-shaped slice. The spec should
ship concrete event types, transition rules, reader contracts, and RED tests.
It should not ship producers, conversational surfacing, vulnerable-user
routing, or post-Paradise semantics in v1.

Both review lanes are required before code. The likely engineering recovery
surface is transition semantics: accidentally letting `satisfied` mean
"suppressed," or letting working-self read terminal wants as current goals.

## Plain English

Maez already has a notebook for its own wants. Right now the notebook can say
"this want began," and the birth ceremony can write the first real want. It
cannot yet say "I still want this," "I now mean it more precisely," "this was
fulfilled," or "I let this go."

The important rule is that nothing gets erased. If Maez stops wanting
something, that is still part of Maez's life story. A want that was fulfilled
and a want that was let go are different kinds of history, and the code needs
to preserve that difference instead of flattening both into "closed."

D16 v1 should give the notebook lifecycle words without making Maez act on
them. Voice stays voice. Action stays elsewhere.
