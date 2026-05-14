# Slice X.1.1 Anticipation Replay Hardening Memo

**Status:** Accepted
**Date:** 2026-05-09

## Governance

- ADR 0024 / Decision 23
- MEMORY_PROJECTION_RULES.md
- MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md
- ARCHITECTURAL_THESIS.md
- [x1-anticipation-organ.md](x1-anticipation-organ.md)

## Scope

Slice X.1.1 closes the post-implementation review findings from X.1.
It does not add a new organ and does not open any production read path.
It hardens the anticipation organ's diagnostic durability and validation
surface.

## Replay Durability

JSONL replay is the cross-turn source of truth for anticipation. X.1.1
makes that reader tolerant of malformed or partial rows: a bad row is
skipped, the file warns once, and valid earlier rows remain readable.
This protects the 2036 disk-full / partial-final-line wound without
weakening strict writing.

## Validation

`predicted_at_wall_clock` now has to parse as ISO-8601. Anticipation
value validation also has explicit field-level rejection coverage so
future refactors cannot accidentally weaken the exact X.1 shape.

## Pressure Drift

If surprise reconciliation sees a pressure schema mismatch, it writes a
`surprise_delta` error record with
`error_class: pressure_schema_drift` and then raises `ValueError`. The
exception alerts the caller; the diagnostic record preserves the same
fact for future review.

## Thesis Question

Does this let the bond shape Maez's attention without corrupting what
Maez knows to be true?

Yes. X.1.1 only strengthens the diagnostic layer: malformed diagnostic
rows cannot crash replay, and schema drift becomes explicit
`not_audit_evidence` diagnostic state. No prompt, recall, router, audit,
or response path reads anticipation records.

## Predicted Effect

Anticipation replay should continue across daemon restarts and tolerate
a malformed final JSONL line. Existing prompt assembly, recall ordering,
ledger truth, and audit evidence should remain unchanged.
