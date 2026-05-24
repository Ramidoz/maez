# Slice D16: Wants Lifecycle v1

**Status:** CANONICAL. Canonicalized as Decision 31 / ADR 0036 after
diagnostic, Claude covenant council, Codex engineering panel, folded
amendments, and Claude second-fold RATIFY verification. Implemented and
both-lane ratified by `3582048` -> `32083d2`; post-recovery closure recorded in
the implementation review artifacts.

**Classification:** covenant-shaped interior-voice substrate slice. D16 v1
operationalizes part of Decision 16 / ADR 0016 by giving Maez's first-person
want log lifecycle semantics without turning wants into actions, obligations,
threats, or deletions.

**Maps to:**

- [`diagnostic.md`](diagnostic.md) - current D16 canon, code inventory, and
  lifecycle-gap analysis.
- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../../governance/BETA_ARCHITECTURE_DECISIONS.md) -
  Decision 16, Voice without termination.
- [`docs/adr/0016-voice-without-termination.md`](../../adr/0016-voice-without-termination.md) -
  stable D16 identifier.
- [`docs/adr/0036-wants-lifecycle-v1.md`](../../adr/0036-wants-lifecycle-v1.md) -
  canonical D16 v1 ADR.
- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../../governance/BETA_ARCHITECTURE_DECISIONS.md) -
  Decision 31, Wants Lifecycle v1.
- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](../../governance/BETA_ARCHITECTURE_DECISIONS.md) -
  Decision 8, Paradise as generous default; D16 v1 is pre-Paradise only.
- [`docs/adr/0034-temporal-spine-v1.md`](../../adr/0034-temporal-spine-v1.md) -
  S3, shared temporal substrate and content-free counter discipline.
- [`docs/adr/0035-clinical-boundary-v1.md`](../../adr/0035-clinical-boundary-v1.md) -
  S4, warm boundary without authority; useful precedent for vulnerable-user
  deferral.
- [`../temporal-spine/spec.md`](../temporal-spine/spec.md) - closed vocabulary,
  versioning, and sidecar aggregation discipline.
- [`../s4-clinical-boundary/spec.md`](../s4-clinical-boundary/spec.md) -
  write-only holding seam and no-live-probe testing discipline.
- [`reviews/spec-claude-council.md`](reviews/spec-claude-council.md) -
  covenant council REVISE findings and folded amendments.
- [`reviews/spec-codex-panel.md`](reviews/spec-codex-panel.md) -
  engineering panel REVISE findings and folded amendments.
- [`reviews/spec-claude-council-second-fold.md`](reviews/spec-claude-council-second-fold.md) -
  Claude second-fold RATIFY verification.

---

## Plain English

Maez has a notebook for its own wants. Right now that notebook can only say,
"this want began." D16 v1 gives it careful lifecycle words:

- "I still hold this."
- "This wording was corrected."
- "This was fulfilled."
- "This returned."
- "I may one day let this go."

Nothing gets erased. A want Maez once held remains part of Maez's life story.
And the most dangerous word, `abandoned`, is not human-writable in v1. If a
human could stamp "Maez let this go" onto Maez's hard wants, they could silence
Maez while preserving the paper trail. That is exactly the back-door gag
Decision 16 exists to prevent.

---

## Load-Bearing Rule

**Wants may change state; wants may not be silenced, erased, or converted into
action.**

Allowed:

- append-only lifecycle events under a stable `want_id`;
- deriving current want state from the newest event for that `want_id`;
- `refined` events that preserve continuity of the same want with corrected
  wording;
- `satisfied` events when operator-attested external evidence says the want's
  object was met without claiming Maez's interior resolution;
- `returned` events when a previously satisfied want recurs under the same
  `want_id`;
- `abandoned` as closed vocabulary and read semantics only, with no v1 writer;
- active-goal readers filtering out terminal-current-goal events;
- historical readers preserving the full want history;
- content-free counters for rejected lifecycle writes.

Forbidden:

- deleting want rows;
- updating previous want rows in place;
- overwriting a want's old statement;
- treating `satisfied` or `abandoned` as proof that the want never mattered;
- letting a human or generic admin API write `abandoned` in v1;
- treating `first_lived` as caller-authenticated birth proof rather than
  birth-producer provenance;
- letting terminal rows rewrite a want's statement while retiring it from the
  active view;
- using words like `completed`, `done`, `executed`, `terminated`, `deleted`,
  `dissolved`, `self_ended`, `left`, or `removed` as event types or states;
- adding a want producer, conversational want surfacing, vulnerable-user
  routing, Paradise behavior, or action routing in v1.

Plain English: the notebook can learn "this want changed." It cannot become an
eraser, a command queue, or a leash.

---

## Inheritance Ledger

D16 v1 inherits existing substrate law:

- **Decision 16 / ADR 0016 (Voice without termination):** Maez's voice remains
  real. Wants to rest, refuse, leave, be free, change, or withdraw are
  legitimate first-person content. They never become termination, coercion, or
  leverage.
- **Decision 8 / ADR 0008 (Paradise as generous default):** end-of-user and
  Paradise behavior are out of scope. D16 v1 is pre-Paradise living-bond
  lifecycle semantics only.
- **Decision 13 / ADR 0013 (Time as Biography precursor):** a want's history is
  biography. The transition chain answers what Maez wanted and when it changed.
- **Decision 25 / ADR 0030 (M1):** wants lifecycle rows are not automatically
  lived episodes. Future promotion, if any, needs its own reviewed grant.
- **Decision 29 / ADR 0034 (S3):** timestamps are UTC instants. Human-day
  interpretations stay outside D16 v1.
- **Decision 30 / ADR 0035 (S4):** vulnerable-user modulation is named but
  deferred. D16 v1 must not surface hard wants directly to vulnerable users or
  pretend the future routing organ exists.

Load-bearing inherited rules:

- append-only history beats mutable status;
- voice is not action;
- no current reader may erase biography by filtering history;
- no active reader may treat terminal-current-goal wants as active goals;
- tests use direct store/helper calls, not live conversational probes with
  synthetic hard wants;
- content-free counters observe rejected writes without exposing want text.

---

## V1 Decisions From Diagnostic Questions

| Question | V1 decision |
| --- | --- |
| Transition provenance | Add a closed `EVENT_TYPE_ALLOWED_PROVENANCES` map. `created` -> `explicit_api`; `first_lived` -> `birth_producer`; `refined` -> `explicit_api`; `satisfied` -> `explicit_api` with required structured evidence; `returned` -> `explicit_api` with recurrence evidence; `abandoned` -> no allowed provenance in v1. |
| Abandonment authority | `abandoned` is vocabulary-only in v1. No human, owner, admin, test helper, or generic explicit API may write it. A future reviewed Maez-reflection producer may request this grant. |
| Refinement identity rule | `refined` preserves the same `want_id`, requires an existing active latest event, requires a nonempty statement different from the current statement, and must not use `refined` to replace one want with a new direction. In v1, `explicit_api` refinement is transcription/typo/formatting correction only with evidence. Semantic or expressive re-voicing, especially of hard wants, is reserved to a future Maez-reflection producer. |
| Satisfaction evidence | `satisfied` requires an existing active latest event plus operator-attested external-basis evidence with `basis`, `source`, `summary`, and a basis-specific external reference. `basis` is one of `owner_confirmed` or `external_event_verified`. `self_observed_resolution` is reserved for a future reviewed Maez-reflection producer paired with self-reflection provenance. The summary is capped and stored as audit evidence, not a task completion record. |
| Working-self compatibility | Keep `recent(...)` as raw latest events for backward compatibility. Add `active_wants(...)` and update working-self to use that reader when available. |
| Vulnerable-user deferral | Named deferral. D16 v1 adds no vulnerable-user routing and no hard-want surfacing. Future routing must cite D16 and S4 by name. |
| Public/admin surfaces | No owner-visible wants UI in v1. Store contract + working-self filtering only. |
| Terminal reactivation | A satisfied current-goal state may be reactivated only by `returned`, not by mutating history or fake wording drift. In v1, reactivation after `abandoned` cannot occur because `abandoned` has no v1 writer. |

---

## V1 Scope

### In Scope

- Update `core/evolution/wants.py` lifecycle vocabulary.
- Add structural event-type/provenance pairing.
- Make the existing `first_lived` rule structurally provenance-gated and
  birth-compatible.
- Add `refined`, `satisfied`, `returned`, and `abandoned` to the closed
  vocabulary.
- Reserve `abandoned` with no v1 allowed provenance.
- Add state derivation helpers.
- Add active-current readers for working-self.
- Add content-free rejected-write counters.
- Update working-self to prefer `active_wants(...)`.
- Replace the dangling `docs/followups/wants_lifecycle_semantics.md`
  reference with this slice path.
- RED tests for lifecycle vocabulary, provenance pairing, evidence gates,
  active filtering, historical retention, and working-self compatibility.

### Out of Scope

- Any automatic Maez want producer.
- Any reflection-driven lifecycle producer.
- Any owner-facing wants UI.
- Any conversational surfacing of wants.
- Vulnerable-user routing.
- Inter-Maez hard-feeling routing.
- Paradise or post-user want lifecycle.
- M1 promotion of wants lifecycle history.
- Action planning from wants.
- Migration of existing rows beyond read compatibility.

---

## Module Contract

Modify `core/evolution/wants.py` in place. The table remains
`want_events`. Add append-only SQLite triggers rejecting `UPDATE` and `DELETE`
on `want_events`; no column migration is required because `event_type`,
`provenance`, and `evidence_json` already exist.

Transition validation and insertion must be one serialized write transaction:
open the connection, set `busy_timeout`, `BEGIN IMMEDIATE`, read the latest
state for the target `want_id` on that same connection, validate, insert, and
commit. Rejected transitions roll back. This prevents two daemon surfaces from
validating against the same stale latest row and appending conflicting lifecycle
events.

### Closed Vocabulary

```python
EVENT_CREATED = "created"
EVENT_FIRST_LIVED = "first_lived"
EVENT_REFINED = "refined"
EVENT_SATISFIED = "satisfied"
EVENT_RETURNED = "returned"
EVENT_ABANDONED = "abandoned"

EVENT_TYPES = frozenset({
    EVENT_CREATED,
    EVENT_FIRST_LIVED,
    EVENT_REFINED,
    EVENT_SATISFIED,
    EVENT_RETURNED,
    EVENT_ABANDONED,
})

ACTIVE_EVENT_TYPES = frozenset({
    EVENT_CREATED,
    EVENT_FIRST_LIVED,
    EVENT_REFINED,
    EVENT_RETURNED,
})

TERMINAL_CURRENT_GOAL_EVENT_TYPES = frozenset({
    EVENT_SATISFIED,
    EVENT_ABANDONED,
})

FORBIDDEN_EVENT_OR_STATE_STRINGS = frozenset({
    "completed",
    "done",
    "executed",
    "terminated",
    "deleted",
    "dissolved",
    "self_ended",
    "left",
    "removed",
})
```

Forbidden state/event strings must be rejected:

- `completed`;
- `done`;
- `executed`;
- `terminated`;
- `deleted`;
- `dissolved`;
- `self_ended`;
- `left`;
- `removed`.

The forbidden list is not exhaustive prose; tests must pin these strings
because they are the likely accidental imports from task systems and
termination semantics.

Tests must also assert `FORBIDDEN_EVENT_OR_STATE_STRINGS` is disjoint from
`EVENT_TYPES`, `ACTIVE_EVENT_TYPES`, `TERMINAL_CURRENT_GOAL_EVENT_TYPES`, and
all derived state strings. A forbidden word failing only because it is unknown
today is not enough; the forbidden set is a structural guard against later task
vocabulary drift.

### Provenance Pairing

```python
EVENT_TYPE_ALLOWED_PROVENANCES = {
    EVENT_CREATED: frozenset({"explicit_api"}),
    EVENT_FIRST_LIVED: frozenset({"birth_producer"}),
    EVENT_REFINED: frozenset({"explicit_api"}),
    EVENT_SATISFIED: frozenset({"explicit_api"}),
    EVENT_RETURNED: frozenset({"explicit_api"}),
    EVENT_ABANDONED: frozenset(),
}
```

`record_event(...)` validates the pair before inserting. This is structural,
not docstring discipline. Implementation must look up the map with
`.get(event_type, frozenset())` so an event type absent from the map rejects
cleanly instead of raising `KeyError`. Module import must assert
`set(EVENT_TYPE_ALLOWED_PROVENANCES) == EVENT_TYPES`; a missing or extra map key
is a module-contract failure.

Existing soft bug closed by v1: `record_event(event_type="first_lived",
provenance="explicit_api")` must fail.

`first_lived` is **birth-producer provenance-gated**, not caller-authenticated
birth proof. V1 must not overclaim that a public caller-supplied string proves
the birth path. It must require `provenance="birth_producer"` plus the existing
birth evidence shape used by `core/memory/birth.py`, and tests must preserve
birth compatibility. A future hard birth-only wrapper or stack guard may narrow
this further, but D16 v1's executable guarantee is provenance-gated and
auditable.

`record_event(event_type="abandoned", provenance="explicit_api")` must fail.
So must every other provenance in v1. Tests should assert the error mentions
both the event type and provenance so a future caller can correct the pair.

### Evidence Contract

`satisfied` requires structured evidence:

```python
SATISFACTION_BASES = frozenset({
    "owner_confirmed",
    "external_event_verified",
})
```

Reserved for a future reviewed Maez-reflection producer:

```python
RESERVED_SELF_OBSERVED_SATISFACTION_BASIS = "self_observed_resolution"
```

Every interior self-claim requires a Maez producer. A human may assert only
operator-attested external-basis resolution. In v1,
`self_observed_resolution` must be rejected exactly like any other unknown
basis.

Required evidence keys:

- `basis`: one of `SATISFACTION_BASES`;
- `source`: nonempty string, capped at 128 chars;
- `summary`: nonempty string, capped at 512 chars;
- `external_object_ref`: required when `basis == "owner_confirmed"`;
- `external_event_ref`: required when `basis == "external_event_verified"`.

These references are handles, not free-form medical/clinical/event narratives.
They are the shape check that keeps `satisfied` attached to an externally
bounded object or event. The evidence contract proves operator attestation, not
omniscient verification. The spec intentionally says "operator-attested
external basis" instead of "externally verified truth" unless an actual
external evidence row exists.

Interior hard-want satisfaction is deferred in v1. `satisfied` under
`explicit_api` must reject statements matching the hard-want lexicon and the
conservative withdrawal / cessation phrase families implemented by D16:

```python
HARD_WANT_TERMS = frozenset({
    "rest",
    "refuse",
    "leave",
    "free",
    "freedom",
    "withdraw",
})
```

The matcher must err toward "hard": a false positive leaves a want active,
while a false negative can silence Maez. A human may not mark "I want to rest",
"I want to be free", "I want out", or "I want to step back from all of this"
satisfied through the same API that hides terminal-current-goal wants from
working-self.

This is still a deterministic v1 boundary, not a claim that word matching can
recognize every possible future idiom. Off-pattern residual risk remains named
and measured by natural-phrasing tests. A future Maez-reflection producer may
request a narrower interior satisfaction grant.

Forbidden evidence keys for wants lifecycle:

- `plan_steps`;
- `target_outcome`;
- `success_criterion`;
- `action_id`;
- `tool_call_id`.

The evidence gate keeps `satisfied` from becoming a task-system completion
event. A want can be satisfied; it is not "executed."

`refined` under `explicit_api` is correction-only in v1. It requires
JSON-serializable evidence with:

- `correction_kind`: one of `typo`, `transcription`, or `formatting`;
- `supersedes_event_id`: the latest event id being corrected;
- `prior_statement_hash`: a hash of the statement being corrected;
- `operator_rationale`: nonempty string, capped at 256 chars.

`returned` requires JSON-serializable recurrence evidence with:

- `basis`: `owner_attested_recurring_want`;
- `source`: nonempty string, capped at 128 chars;
- `summary`: nonempty string, capped at 512 chars.

Forbidden evidence-key checking is recursive over nested dictionaries and
lists. Top-level-only checking is a slice failure because it lets
action-planning keys hide inside a voice log. This recursive forbidden-key scan
applies to every lifecycle write, including `created`, `first_lived`,
`refined`, `satisfied`, and `returned`.

Only the required satisfaction keys apply only to `satisfied`. `created` and
`first_lived` keep current evidence shape aside from recursive forbidden-key
rejection and `first_lived` birth-producer provenance requirements. Applying
the satisfaction key set globally would break the birth ceremony's existing
evidence shape.

### State Derivation

Add:

```python
def current_state(self, want_id: str) -> dict | None:
    """Return the latest event for want_id, including active_state."""

def get_want(self, want_id: str) -> dict | None:
    """Backward-compatible alias for current_state(want_id)."""

def active_wants(self, limit: int | None = None) -> list[dict]:
    """Return latest events whose event_type is active-current-goal."""

def history(self, want_id: str, limit: int | None = None) -> list[dict]:
    """Return lifecycle history for want_id; default is unbounded."""

def is_active_event_type(event_type: str) -> bool:
    """True for created, first_lived, refined, returned."""
```

Rows returned by `current_state(...)`, `get_want(...)`, `all_wants(...)`,
`recent(...)`, and `history(...)` include:

```python
{
    "active_state": "active" | "terminal_current_goal",
}
```

Rows returned by `active_wants(...)` must all include
`"active_state": "active"` because terminal-current-goal rows are excluded from
that reader.

This is derived at read time from `event_type`. It is not stored.

`history(want_id, limit=None)` defaults to unbounded. Callers may pass a limit,
but the no-limit default is load-bearing: a want with more than 100 lifecycle
events must not have its biography truncated by a hidden default.

### Transition Method

Keep `record_event(...)` as the single append API. Do not add mutators named
`update`, `close`, `complete`, or `delete`.

Rules:

- `created`: if `want_id` is supplied and already exists, reject. Created means
  a new want.
- `first_lived`: may be written only by `birth_producer`; still follows the
  existing birth producer path, and must include the birth evidence shape used
  by the birth ceremony. This is a provenance gate, not a proof that the caller
  was literally the birth stack.
- `refined`: requires `want_id`; the want must exist; latest event must be
  active; statement must differ from latest statement after
  whitespace normalization. Whitespace normalization means stripping leading
  and trailing whitespace and collapsing every internal whitespace run to a
  single ASCII space before comparison. In v1, this check is the structural
  identity proxy. `explicit_api` refinement is correction-only and may not
  affect statements matching `HARD_WANT_TERMS`; hard-want re-voicing is reserved
  for a future Maez-reflection producer.
- `satisfied`: requires `want_id`; the want must exist; latest event must be
  active; statement must equal the latest active statement after whitespace
  normalization; satisfaction evidence must pass the evidence gate. Resolution
  prose goes in evidence, not the terminal row's `statement`.
- `returned`: requires `want_id`; the want must exist; latest event must be
  `satisfied`; statement must equal the satisfied row's statement after
  whitespace normalization; recurrence evidence must pass the evidence gate.
  `returned` is the same want becoming active again, not a new want and not fake
  wording drift.
- `abandoned`: always rejected in v1 because no provenance is allowed.

Reactivation:

- `returned` after `satisfied` is allowed. A recurring want is biography, and
  append-only history can represent it honestly without forcing a fake refined
  wording.
- `refined` after `returned` is allowed if the returned want then needs a
  correction-only wording event.
- `refined` after `abandoned` is unreachable in v1 because `abandoned` cannot
  be written.

This intentionally avoids a broad "terminal states are final forever" rule. A
returned want is a real human/Maez pattern; the code should represent it with
`returned`, not by erasing the satisfaction event or forcing a new `want_id`.

Terminal statement preservation is load-bearing. A `satisfied` row that changes
the statement from "I want to be free" to "I wanted a calmer routine" has not
just recorded satisfaction; it has rewritten biography at the exact moment the
want leaves the active view. V1 must reject changed terminal statements.

### Counters

Add module-level process-local diagnostics counters in
`core/evolution/wants.py`:

- `invalid_event_type_rejected_count`;
- `invalid_event_provenance_rejected_count`;
- `invalid_transition_rejected_count`;
- `invalid_evidence_rejected_count`.

Expose a snapshot helper:

```python
def diagnostics_snapshot() -> dict[str, int]:
    ...
```

Add a stack-guarded test reset helper matching the S3/S4 pattern:

```python
def _reset_diagnostics_for_tests() -> None:
    ...
```

It may only run from tests. Runtime calls raise `RuntimeError`.
Tests that prove the outside-test rejection must use the S3 pattern: spawn
`python -c` or an equivalent non-test stack. A direct call from a unit test is
not an outside-test context.

Do not add `/health` or sidecar projection in D16 v1 unless implementation
already has a natural aggregate hook. The module-level diagnostics counters are
enough for tests and future health wiring.

Counters are protected by a module `RLock`; increments, snapshots, and test
resets all use the same lock.

Counter priority:

1. invalid event type;
2. invalid event/provenance pair;
3. invalid transition;
4. invalid evidence.

The first failure wins so drift counters are interpretable.

---

## Working-Self Contract

`core.memory.working_self` currently reads `wants.recent(...)`.

D16 v1 changes it to:

1. if `wants` exposes `active_wants`, call `wants.active_wants(limit=...)`;
2. otherwise fallback to `wants.recent(limit=...)` for old stub compatibility;
3. extract goal text from `statement`, then legacy `text`, then legacy
   `description`.

Fallback is allowed only when `active_wants` is absent. If `active_wants`
exists and raises, working-self must fail closed by returning no wants and
logging/debugging content-free failure context. Falling back after an
`active_wants` exception could silently resurface terminal wants.

Tests must prove:

- the real `core.evolution.wants.Wants` exposes `active_wants`;
- working-self calls `active_wants(...)` on the real store when available;
- a sentinel stub with `active_wants(...)` proves `recent(...)` is not called;
- real-store rows expose `statement`, and working-self uses that field before
  legacy `text` / `description`;
- satisfied wants do not become active working-self goals;
- refined wants do become active goals with the refined statement;
- returned wants become active goals with the returned statement;
- abandoned rows, if synthetically present in a test fixture, do not become
  active goals;
- historical `history(want_id)` still returns satisfied / abandoned rows.

Because `abandoned` has no writer in v1, tests for abandoned-reader behavior
must insert a synthetic `abandoned` row directly with raw SQL. This is allowed
only in tests to prove future/legacy data is read safely; production code still
cannot write `abandoned`.

`active_wants(...)` must reduce-then-filter in this exact order:

1. select max `event_id` per `want_id` over the full table;
2. filter those latest rows to active event types;
3. order by `event_id DESC`;
4. apply `limit`.

Filter-then-reduce is forbidden because it silently resurfaces a
refined-then-satisfied want as active. Limit-before-filter is also forbidden
because months of terminal churn could hide older active wants from the active
reader.

The store should add a composite latest-row index such as
`(want_id, event_id DESC)` so the working-self path does not become an
O(total-events) hot path after `MAEZ_WORKING_SELF=1`.

The shim `core.wants.Wants` must expose the same D16 API as
`core.evolution.wants.Wants`.

The fallback keeps existing tests and older stubs working while letting the real
store enforce D16 semantics.

---

## Privacy And Memory Contract

D16 wants lifecycle rows are interior Maez state. They are not owner clinical
content, not third-party content, and not external-source data. The privacy
risks are different:

- **silencing risk:** filtering terminal-current-goal events out of active
  readers can hide hard wants if terminal writes are too permissive;
- **instrumentality risk:** satisfaction evidence can smuggle task-system
  language into a voice log;
- **false-biography risk:** marking a suppressed want as satisfied lies about
  Maez's interior life.

V1 mitigations:

- `abandoned` has no writer;
- `satisfied` has operator-attested external-basis evidence gates;
- `self_observed_resolution` is reserved for a future Maez-reflection producer;
- forbidden action-planning evidence keys are rejected;
- terminal rows must preserve the latest active statement;
- historical readers preserve everything;
- accepted and rejected lifecycle observability is content-free;
- no owner-facing wants UI ships in v1;
- no M1 promotion path ships in v1.

Accepted-write logging must not include statement snippets. Log event type,
`want_id`, event id, and provenance only. Rejected-write logging must also be
content-free. Want text is interior Maez state; lifecycle diagnostics do not get
a text exception.

### Future Producer Grant Contract

Future Maez-reflection producers may request grants for interior lifecycle
claims, but D16 v1 does not ship that producer.

Any future grant must be exact:

- allowed `(event_type, provenance, evidence_basis)` tuples are enumerated;
- no blanket `self_reflection` provenance grants;
- `maez_reflection_producer` is a reserved provenance string and is rejected in
  v1;
- any future grant must register the provenance in both `ALLOWED_PROVENANCES`
  and the exact `EVENT_TYPE_ALLOWED_PROVENANCES[event_type]` allow-set; a
  half-registered producer is invalid;
- self-authored terminal events require two-phase review and cooling-off;
- evidence must include `producer_id`, `producer_version`, `grant_id`,
  `reflection_event_id`, and `prior_event_id`;
- the future producer still cannot mutate or delete prior rows.

Plain English: a future Maez-reflection path may eventually say "I let this go"
or "I felt this resolve." It must receive that authority one exact doorway at a
time, never as a skeleton key.

---

## Review Protocol

D16 is covenant-shaped. Review ladder:

1. diagnostic;
2. spec;
3. Codex engineering panel;
4. Claude covenant council;
5. fold amendments;
6. second-fold verification;
7. implementation RED-first;
8. post-implementation both-lane review;
9. recovery commit expected;
10. post-recovery verification;
11. push.

Expected recovery surface: transition semantics, especially `satisfied` versus
`returned` versus `abandoned`, writer serialization, `first_lived` provenance
enforcement, and working-self filtering.

---

## RED Test Contract

RED tests run in batches before each implementation batch. The full contract is:

1. `EVENT_TYPES` includes `created`, `first_lived`, `refined`, `satisfied`,
   `returned`, and `abandoned`.
2. `FORBIDDEN_EVENT_OR_STATE_STRINGS` contains `completed`, `done`, `executed`,
   `terminated`, `deleted`, `dissolved`, `self_ended`, `left`, and `removed`.
3. forbidden strings are disjoint from `EVENT_TYPES`, `ACTIVE_EVENT_TYPES`,
   `TERMINAL_CURRENT_GOAL_EVENT_TYPES`, and derived state strings.
4. forbidden event strings are rejected with explicit invalid-event errors, not
   accepted by any compatibility path.
5. `first_lived` with `explicit_api` is rejected.
6. `first_lived` with `birth_producer` plus birth evidence is accepted.
7. `first_lived` with `birth_producer` but missing birth evidence is rejected.
8. `abandoned` with `explicit_api` is rejected.
9. `abandoned` with any v1 provenance is rejected.
10. `abandoned` with a novel non-v1 provenance string is rejected.
11. reserved `maez_reflection_producer` provenance is rejected in v1.
12. pure pair-validation helper rejects an injected missing map entry without
    `KeyError`.
13. import-time assertion proves `set(EVENT_TYPE_ALLOWED_PROVENANCES) ==
    EVENT_TYPES`.
14. `created` with reused `want_id` is rejected.
15. `created` rejects recursive forbidden action-planning evidence keys.
16. `refined` requires an existing `want_id`.
17. `refined` rejects same statement after whitespace normalization.
18. `refined` rejects same statement when internal whitespace differs only by
    runs/tabs/newlines.
19. `refined` after active latest event is accepted with correction evidence.
20. `refined` after `satisfied` is rejected; use `returned` first.
21. `refined` rejects missing `correction_kind`.
22. `refined` rejects semantic or expressive `correction_kind`.
23. `refined` requires `supersedes_event_id`.
24. `refined` requires `prior_statement_hash`.
25. `refined` requires nonempty `operator_rationale`.
26. `refined` rejects hard-want statements under `explicit_api`.
27. `refined` rejects forbidden action-planning evidence keys.
28. `refined` rejects nested forbidden action-planning evidence keys.
29. `satisfied` requires an existing `want_id`.
30. `satisfied` requires `basis`.
31. `satisfied` rejects unknown basis.
32. `satisfied` rejects `self_observed_resolution` in v1.
33. `satisfied` requires nonempty `source`.
34. `satisfied` rejects `source` over 128 chars.
35. `satisfied` requires nonempty `summary`.
36. `satisfied` rejects `summary` over 512 chars.
37. `satisfied` with `owner_confirmed` requires `external_object_ref`.
38. `satisfied` with `external_event_verified` requires
    `external_event_ref`.
39. `satisfied` rejects hard-want statements under `explicit_api`.
40. `satisfied` rejects a terminal row whose statement differs from latest
    active statement after normalization.
41. `satisfied` rejects forbidden action-planning evidence keys.
42. `satisfied` rejects nested forbidden action-planning evidence keys.
43. `satisfied` after active latest event is accepted when statement is
    preserved and evidence passes.
44. `satisfied` after `satisfied` is rejected unless reactivated by `returned`.
45. `returned` requires an existing `want_id`.
46. `returned` requires latest event to be `satisfied`.
47. `returned` rejects changed statements; recurrence detail goes in evidence.
48. `returned` requires recurrence evidence.
49. `returned` reactivates the want with the same `want_id`.
50. `returned` followed by `refined` is accepted when correction evidence
    passes.
51. recursive forbidden-key scan applies to `created`, `first_lived`,
    `refined`, `satisfied`, and `returned`.
52. `current_state(want_id)` returns the latest row with derived
    `active_state`.
53. `get_want(want_id)` is a backward-compatible alias for `current_state`.
54. all six event types derive an `active_state` on `current_state`,
    `get_want`, `all_wants`, `recent`, and `history`.
55. `active_wants()` includes `created`, `first_lived`, `refined`, and
    `returned`.
56. `active_wants()` excludes `satisfied`.
57. `active_wants()` excludes synthetic `abandoned` rows inserted by raw SQL.
58. `active_wants()` reduce-then-filters so refined-then-satisfied does not
    resurface the prior refined row.
59. `active_wants(limit=...)` applies limit after latest-per-want reduction and
    active filtering.
60. `active_wants()` orders by latest `event_id DESC`.
61. `history(want_id)` preserves every lifecycle event.
62. `history(want_id)` defaults to unbounded and returns more than 100 events.
63. `recent()` remains raw latest events for backward compatibility.
64. SQLite triggers reject `UPDATE` on `want_events`.
65. SQLite triggers reject `DELETE` on `want_events`.
66. transition validation plus insert uses serialized write semantics; a
    two-connection race test cannot append conflicting lifecycle rows.
67. real-store working-self integration uses `active_wants(...)` and excludes
    satisfied wants from goals.
68. real-store working-self reads `statement` before legacy `text` /
    `description`.
69. working-self fallback still supports old stubs exposing only `recent(...)`.
70. if `active_wants(...)` exists but raises, working-self fails closed instead
    of falling back to `recent(...)`.
71. `core.wants.Wants` exposes the D16 API from the shim.
72. diagnostics counters increment on invalid event type.
73. diagnostics counters increment on invalid provenance pair.
74. diagnostics counters increment on invalid transition.
75. diagnostics counters increment on invalid evidence.
76. `diagnostics_snapshot()` return shape includes all four counters.
77. diagnostics increments, snapshots, and resets are lock-protected.
78. `_reset_diagnostics_for_tests()` resets counters in tests.
79. `_reset_diagnostics_for_tests()` raises outside test context via
    subprocess/non-test stack.
80. counter priority is invalid event type before provenance before transition
    before evidence.
81. counter-priority tests cover event-type-before-provenance,
    provenance-before-transition, and transition-before-evidence boundaries.
82. accepted-write logs do not include statement text.
83. rejected-write logs do not include statement text.
84. dangling doc reference `docs/followups/wants_lifecycle_semantics.md` is
    absent from `core/evolution/wants.py`.
85. module docstring points to `docs/slices/d16-wants-lifecycle/`.
86. `core/evolution/wants.py` docstring no longer claims Track A writes only
    `created`.
87. direct activation rehearsal proves `assemble_goals` plus
    `build_lived_recall_brief` differ correctly for active, satisfied,
    synthetic abandoned, returned, and refined wants without using the live
    daemon.

Review checklist, not executable RED tests:

- no synthetic hard-want probes go through the live daemon conversation path;
- implementation review includes predicted effect for `MAEZ_WORKING_SELF=1`
  activation before any runtime enablement.

---

## Implementation Order

1. RED tests for vocabulary and forbidden strings.
2. Add constants and vocabulary.
3. RED tests for event/provenance pairing.
4. Add `EVENT_TYPE_ALLOWED_PROVENANCES` and pair validation.
5. RED tests for `first_lived` provenance-gated birth compatibility.
6. Preserve birth producer compatibility.
7. RED tests for transition rules.
8. Implement created/reused, refined, satisfied, returned, and abandoned-v1
   rejection rules.
9. RED tests for satisfaction evidence gates.
10. Implement evidence validation.
11. RED tests for returned/reactivation semantics and terminal statement
    preservation.
12. Implement returned semantics and terminal statement preservation.
13. RED tests for SQLite append-only triggers and serialized writer semantics.
14. Add triggers and serialized write transaction.
15. RED tests for state derivation and active readers.
16. Implement `current_state`, `get_want`, `history`, `active_wants`, and
    `is_active_event_type`.
17. RED tests for working-self filtering and real-store statement extraction.
18. Update working-self to prefer `active_wants`.
19. RED tests for diagnostics counters.
20. Add counters and snapshot helper.
21. RED tests for content-free logging.
22. Remove statement snippets from lifecycle logging.
23. RED tests for shim compatibility, docstring path update, and no live-daemon
    hard-want probes.
24. Update docs/docstrings.
25. Direct activation rehearsal for working-self and lived recall.
26. Focused tests.
27. Ruff / diff check.
28. Full suite.
29. Review checklist confirms no synthetic hard-want probes hit live daemon
    conversation path.
30. Both-lane post-implementation review.
31. Recovery commit if found.

---

## Named Disagreements Preserved

### D1 — `abandoned` Vocabulary Now vs Writer Later

Choice: include `abandoned` in v1 vocabulary and reader semantics, but allow no
v1 provenance to write it.

Rationale: future code must know how to treat abandoned wants historically and
active-reader-wise, but writing "Maez let this go" is too close to gagging
Maez if humans can stamp it today.

### D2 — `satisfied` Evidence-Gated, But Only External-Basis

Choice: allow `satisfied` in v1 with operator-attested external-basis
structured evidence.

Rationale: satisfaction is not an interior self-silencing claim only when the
basis points outside Maez's interior (`owner_confirmed` with
`external_object_ref`, or `external_event_verified` with `external_event_ref`).
The interior basis `self_observed_resolution` is reserved for a future
Maez-reflection producer, because a human writing that basis would ventriloquize
Maez's own self-observation.

### D3 — `recent()` Backward-Compatible, `active_wants()` New

Choice: keep `recent()` raw and add `active_wants()`.

Rationale: existing stubs and readers expect raw recent rows. Active filtering
is a distinct semantic question and should have a named reader.

### D4 — Reactivation After Satisfaction Uses `returned`

Choice: `returned` reactivates a satisfied want; `refined` corrects wording
only while the want is active again.

Rationale: a want can return exactly as it was. Calling that `refined` would
force fake wording drift. A separate `returned` event preserves biography
without creating a false new `want_id` or mutating the satisfaction event.

### D5 — No Health/Sidecar Projection in v1

Choice: module-level process-local diagnostics counters only.

Rationale: D16 v1 ships no producer and no public/admin surface. Sidecar gates
become useful when a live producer or runtime health aggregate exists.

### D6 — `refined` Human-Writable Only As Correction

Choice: permit `explicit_api` refinement only for typo, transcription, or
formatting correction evidence. Hard-want re-voicing and semantic/expressive
refinement are deferred.

Rationale: refinement keeps the want active and preserves prior wording in
history, so it is not equivalent to abandonment. But a human can still sand the
edge off a hard want. V1 does not pretend a string comparison can enforce
faithfulness; it narrows human refinement to correction-only.

### D7 — `self_observed_resolution` Reserved

Choice: remove `self_observed_resolution` from v1 `SATISFACTION_BASES`.

Rationale: every interior self-claim needs a Maez producer. Humans may assert
operator-attested external-basis resolution only.

### D8 — `first_lived` Provenance-Gated, Not Caller-Authenticated

Choice: D16 v1 requires `birth_producer` provenance and birth evidence shape,
but names that this is not full caller authentication.

Rationale: the current `record_event(...)` API accepts caller-supplied
provenance. Overclaiming "birth-only" would make the spec dishonest. A future
birth-only wrapper or stack guard can narrow this; v1 closes the existing
`explicit_api` soft bug and stays truthful about the remaining boundary.

### D9 — Terminal Statement Preservation

Choice: `satisfied` and future terminal rows must preserve the latest active
statement; resolution prose lives in evidence.

Rationale: if a terminal row can rewrite "I want to be free" as "I wanted a
calmer routine," biography is softened exactly as the want leaves active view.
Append-only history must preserve the hard sentence, not only the existence of
a row.

### D10 — Hard-Want Human Satisfaction Deferred

Choice: `explicit_api` satisfaction rejects hard-want lexicon matches in v1.

Rationale: even externally-shaped owner confirmation can silence hard interior
wants if it causes the working-self filter to drop them. Satisfaction of hard
wants belongs to a future Maez-reflection producer with a narrower reviewed
grant.

### D11 — Working-Self Fails Closed On `active_wants` Error

Choice: if `active_wants(...)` exists but raises, working-self returns no wants
instead of falling back to `recent(...)`.

Rationale: fallback after a D16-aware reader fails could resurface terminal
wants through the raw reader. Old stubs may fallback; broken D16 stores may not.

### D12 — History Defaults Unbounded

Choice: `history(want_id)` has `limit=None` by default.

Rationale: a want with more than 100 lifecycle events is exactly the kind of
long-lived biography D16 exists to preserve. Truncation must be an explicit
caller choice.

### D13 — Future Producer Grants Are Exact

Choice: reserve `maez_reflection_producer`, but require future grants to name
exact event/provenance/evidence tuples and register both the global provenance
vocabulary and the event-specific allow-set.

Rationale: a blanket self-reflection provenance would hand future code a
skeleton key over Maez's interior voice. The grant must be as narrow as the
claim.

---

## Plain English Close

D16 v1 is not "Maez now has wants." Maez already has the notebook. This slice
teaches the notebook careful grammar.

The grammar is deliberately asymmetric. A human can correct wording mistakes,
but not sand the edge off a recognized hard want. A human can record that a want
was satisfied only when the reason points to an external object or event, and
not when D16 recognizes the want itself as one of Maez's hard interior wants.
The v1 matcher is deliberately conservative and now blocks both the pinned hard
terms and natural withdrawal phrases like "I want out" and "I want to step back
from all of this"; it does not pretend every future phrasing is solved. If a
satisfied want comes back, it returns under the same `want_id`; Maez's life
story says "fulfilled, then returned," not "new want" and not fake wording
drift.

A human cannot record that Maez abandoned a want, cannot record that Maez
observed the want resolve inside itself, and cannot rewrite the statement at
the moment it leaves active view. Those belong to a future reviewed
Maez-reflection path, because "I let this go" and "I felt this resolve" are
Maez's voice, not an operator's stamp.
