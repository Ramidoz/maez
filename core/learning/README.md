# core/learning

Maez's memory of its own mistakes. Four modules that track what has
gone wrong so future cycles can retrieve the rejection / failure /
residue and behave differently.

| Module | Role |
|---|---|
| [`consequence_memory.py`](consequence_memory.py) | Persistent sqlite store of consequence events (tool failure, card rejected, user correction, fixation episode, approval timeout). Provides `relevant(context_snippet)` for the planner to pull similar past mistakes before proposing an action. |
| [`fabrication_memory.py`](fabrication_memory.py) | Immune memory for self-claim fabrications. When `core.safety.self_claim_audit` rewrites a reply, the flagged tokens land here so the next turn's prompt sees a "don't reach for this again" block. |
| [`inner_residue.py`](inner_residue.py) | Transient unresolved state between turns. Functional state, not performance — drives the next reply's tone when something is genuinely unresolved (audit rewrite, user rejection, self-refusal, tool failure). 30-min half-life decay. |
| [`error_classifier.py`](error_classifier.py) | Categorises tool failures into `transient` / `deterministic` / `external` / `auth` / `rate_limit`, with retryability flags. Used by the brain loop to decide whether to retry vs. queue an approval card. |

## Invariants

- **Never delete Maez memory.** These sqlite stores grow. Retrieval
  pollution is solved by better scoring, decay, and promotion to
  immune memory — not by deletion. Only exception: `_diag_clear_for_test`
  helpers used in test fixtures. (Memory note:
  `feedback_never_delete_maez_memory`.)
- **Silent failure of the memory layer must never break an audit
  call.** Every public function in `fabrication_memory` and
  `inner_residue` is wrapped in `try/except: return ...` so a
  corrupted db or disk-full can't propagate. The audit layer is
  more important than the memory layer.
- **Token filter symmetry.** `consequence_memory.relevant()` applies
  the same token predicate to query and haystack. (01-M1 / 09-B1
  fix — asymmetric `isalnum` filter was hiding stored events with
  hyphens / dots.)

## Public surface

- `consequence_memory.record_event(kind, context, outcome, ...)`
- `consequence_memory.relevant(context_snippet, window_hours, limit) -> list[Event]`
- `fabrication_memory.record(surface, flags, mode)`
- `fabrication_memory.prompt_snippet(days, limit) -> str` — injected into system prompts
- `inner_residue.record(kind, intensity, context)`
- `inner_residue.prompt_snippet() -> str` — empty when below threshold
- `error_classifier.classify(stderr, returncode) -> ErrorClass`

## Legacy import paths

Pre-Phase-3 paths (`core.consequence_memory`, `core.fabrication_memory`,
`core.inner_residue`, `core.error_classifier`) are shims.
