# Slice X.0.2 Bypass Auto-Fire Memo

**Status:** Accepted
**Date:** 2026-05-08

## Governance

- ADR 0024 / Decision 23
- MEMORY_PROJECTION_RULES.md
- MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md
- ARCHITECTURAL_THESIS.md

## Scope

Slice X.0.2 closes the X.0 prerequisite that a completed owner-private
turn must leave a diagnostic completion row. The center is not "call
`write_bypassed_record` somewhere"; the center is: owner-private turn
closure is malformed unless exactly one diagnostic completion row exists
for that turn.

The production seam is `complete_moment_assembly_turn`. It is allowlisted
only for daemon owner turns, CLI owner chat, owner-web chat, private
Telegram text, and Telegram recovery synthesis. Public Telegram,
public/guest web chat, proactive surfaces, proposal/edit/training
surfaces, and task-status narration remain outside this slice.

Completion rows remain JSONL diagnostics with
`audit_boundary: not_audit_evidence`. Production prompt assembly, recall,
ledger truth, and audit evidence do not read them.

## Runtime Enforcement Boundary

X.0.2 enforces the closure-coverage invariant at test time (simulated
turns produce exactly one row) and via covenant clause (any new
owner-private turn surface must call `complete_moment_assembly_turn` or
document exclusion). The runtime closure-coverage enforcement, meaning a
turn-context manager raising on malformed closure in production, is
deferred to X.0.3. X.0.3 must ship before X.1 wires the first
observed-diagnostic consumer.

Until X.0.3 lands, a determined contributor adding a new owner-private
turn handler in a new file could bypass the diagnostic without tripping
the AST check; the covenant clause is the protection against that, not
structural runtime enforcement.

## Completion Shape

Bypass rows carry `bypass_reason`, `lifecycle_phase`, and
`source_id_synthetic`. The bounded bypass reasons are `not_called`,
`early_return`, `exception`, `deliberate_skip`, and `unspecified`.

When a real ledger turn id exists, `source_id_synthetic` is false and
the real turn id is used. When no real turn id exists, the diagnostic
uses `completion:<surface>:<uuid>` and sets `source_id_synthetic` true.

## Thesis Question

Does this let the bond shape Maez's attention without corrupting what Maez knows to be true?

Yes, structurally. X.0.2 still does not shape attention. It only makes
missing observation visible at owner-private turn close, while keeping
diagnostics separated from prompt context, recall ordering, ledger
truth, and audit evidence.

## Predicted Effect

Owner-private conversation paths gain diagnostic JSONL bypass rows unless
an observed diagnostic has already been written. No prompt, recall,
ledger-truth, or audit-evidence behavior should change.
