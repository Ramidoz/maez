# Codex Six-Agent Council — S1a.1 Closure Review

**Subject:** `494b7c5` (`test(private-thoughts): close S1a1 council amendments`)

**Date:** 2026-05-13

**Why this ran post-hoc:** the C1-C6 closure commit landed before Codex's six-agent engineering council sat on the closure. That was a process miss. This review records the recovery pass and the follow-up fixes it required.

## Verdict

**BLOCK, then RATIFY-WITH-AMENDMENTS after mechanical closure.**

The closure was directionally right, but the council found implementation-level gaps that mattered:

| seat | finding | closure |
|---|---|---|
| Dewey | Legacy rows without valid `context.source` were attributed to registry producers instead of staying `legacy_unknown`. | Added regression coverage and changed migration fallback to durable `legacy_unknown`. |
| Feynman | Docs overclaimed "AST guard" and implied behavior reads were audit-visible. | Reworded to static source-token guard and forensic-only audit-before-handle provenance. |
| Locke | `legacy_unknown` was a durable producer value but not explicitly defined in the registry doc. | Added a Producer Identity Registry section. |
| Descartes | Already-migrated rows from the parent commit were not repaired on reopen. | Migration normalization now reruns idempotently even when no columns are added. |
| Ohm | `sqlite3.executescript()` inside migration could implicitly commit schema changes before index DDL failed. | Replaced index DDL execution with per-statement `conn.execute()` inside the transaction and added rollback regression coverage. |
| Goodall | A chatty recent signal class could hide an older rare class; valid enum values in invalid registry tuples could still surface. | Behavior aggregation now scans per class and read-side validation enforces the full `signal_kind`/`producer_id`/`signal_class` registry tuple. |

## Predicted Effect

- Direct-SQL rows with valid enum values but invalid registry tuples do not surface to behavior.
- Recent high-volume rows in one class do not hide older valid rows in another class.
- Migration failures after index DDL rollback schema changes and leave `PRAGMA user_version` unchanged.
- Legacy rows with unproven producer identity remain `legacy_unknown`; parent-migrated rows with valid `context.source` repair on reopen.
- The registry doc stays in sync with code enum values through a committed test.
- S1b remains planning-unblocked only; implementation still requires cooling-off plus live-readiness check or explicit operator waiver.

## Boundary Note

This is Codex's engineering council. It does not replace Claude's six-role covenant council. The Claude council already ratified S1a.1 with amendments; this document records the Codex-side recovery review for the mechanical closure commit.
