# Slice X.0.3 Runtime Closure Coverage Memo

**Status:** Accepted
**Date:** 2026-05-08

## Governance

- ADR 0024 / Decision 23
- MEMORY_PROJECTION_RULES.md
- MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md
- ARCHITECTURAL_THESIS.md

## Scope

Slice X.0.3 replaces X.0.2's manual bypass-completion helper at covered
owner-private surfaces with the `moment_assembly_turn` runtime context
manager. Covered surfaces remain daemon owner turns, CLI owner chat,
owner-web chat, private Telegram text, and Telegram recovery synthesis.

The context manager writes a bypass diagnostic row on clean exit when no
observed diagnostic has been marked. On exception exit, it writes a
bypass row with `bypass_reason: exception`, preserves the original
exception, and lets the owner-private path fail exactly as it would have
without diagnostics.

## Discipline Note

Covenant clauses are documentation discipline, not enforcement. Closure coverage is load-bearing only when backed by tests or runtime checks.

X.0.3 hardens covered surfaces. It does not magically protect a future
owner-private handler that never enters `moment_assembly_turn`; those
paths remain caught by test-time closure coverage and review discipline.

## Failure Boundary

Diagnostic failure cannot cascade into ledger, audit, or prompt paths.
If a diagnostic write fails during clean exit, it is logged once for the
`(surface, lifecycle_phase)` pair and the owner-private reply path
continues. If a diagnostic write fails while an owner-private exception
is already unwinding, the original exception is preserved and the
diagnostic failure is logged without masking it.

## Bypass Note

Slice X.0.3 bumps `MOMENT_ASSEMBLY_DIAGNOSTIC_SCHEMA` to 2, so new
records carry `schema_version: 2`, and adds `bypass_note` to bypass
rows. The bounded `bypass_reason` enum remains the structural
classifier. `bypass_note` is a supplementary single-line field capped at
500 characters; it rejects newlines and `Traceback (` content.

X.0.2 readers ignore unknown fields; X.0.3 readers default missing bypass_note to empty string when reading schema-1 rows.

## Thesis Question

Does this let the bond shape Maez's attention without corrupting what Maez knows to be true?

Yes, structurally. X.0.3 still does not shape attention. It makes missing
observation visible through runtime closure checks at covered
owner-private surfaces, while diagnostics remain separate JSONL records
with `audit_boundary: not_audit_evidence` and no production read path.

## Predicted Effect

Covered owner-private turn paths should keep appending moment-assembly
diagnostic bypass rows, but now through runtime closure coverage instead
of manual completion hooks. Prompt assembly, recall ordering, ledger
truth, and audit evidence should remain unchanged.
