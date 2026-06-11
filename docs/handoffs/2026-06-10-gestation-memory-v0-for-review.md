# Gestation-Memory v0 — Review Handoff

**Status:** built; stopped before merge and witness.

**Branch:** `gestation-memory-v0`

**Base:** `ae9488b`

## What This Builds

Gestation-Memory v0 is Maez's developmental self-history reader: a baby book
made from receipts, not a diary. It adds an offline/manual claim index and a
deterministic renderer over those claims.

It does not wire into the daemon, does not write the birth-gated ledger, does
not write `identity_ledger`, does not write the want ledger, and does not
generate stored narrative prose.

## Files Added

- `core/evolution/gestation_memory.py`
- `tests/test_gestation_memory.py`
- `tests/test_gestation_memory_sources.py`
- `tests/test_gestation_memory_boundary.py`

## Review Anchors

1. **Append-only is real.** `gestation_claims` and
   `gestation_claim_supersessions` both have `RAISE(ABORT)` triggers for
   `UPDATE`, `DELETE`, and `INSERT OR REPLACE`. Supersession appends an edge;
   the old claim row remains byte-identical.
2. **Strict sources.** Every stored claim requires at least one resolvable
   structural source. `witness_note` alone is rejected. `doc` sources require a
   full pinned commit hash, `git show <commit>:<path>`, excerpt presence, and
   `sha256(excerpt)` match. `commit` sources reject mutable refs such as
   `HEAD`. `ledger_row` sources read the identity ledger in SQLite `mode=ro`.
3. **Canonical ledger-row hash is byte-defined and fail-closed.** The hash uses
   exactly the nine identity-ledger columns; `evidence_json` and
   `fingerprint_json` are parsed into JSON objects, then the stable object is
   serialized with `sort_keys=True, separators=(",", ":")` before SHA-256.
   Missing columns or non-object JSON fail closed.
4. **Fact/interpretation quarantine.** `fact + inferred` is rejected.
   Interpretations may be inferred, but render in their own section.
5. **Deterministic renderer.** No LLM import. Facts, scars/corrections, and
   interpretations are separated; rendered claim lines carry source refs.
6. **Boundary.** The module imports no daemon, LLM, voice, want writer, ledger
   writer, identity-ledger writer, or shim surfaces. `record_event` appears
   nowhere. Boundary tests include a meta-test proving smuggled imports would be
   caught.
7. **Offline/manual.** No daemon wiring and no `## Predicted effect`.

## Deviations / Hardening Beyond The Plan

A parallel explorer found five receipt-hardening issues before Task 4. The build
folded them in:

- Mutable git refs (`HEAD`, branch names, tags) are rejected; sources must use
  full 40-character commit hashes.
- `doc.commit` is validated as a commit object before `git show`.
- `ledger_row` validation is tested with a real temporary identity-ledger
  fixture: valid row accepted, wrong hash rejected, missing row rejected, and a
  nonexistent DB is not created under `mode=ro`.
- Canonical row hashing rejects missing fields and JSON arrays where objects are
  required.
- Append-only triggers now also block `INSERT OR REPLACE`, matching
  `want_events`.
- Boundary tests reject shim surfaces such as `core.identity_ledger`,
  `core.ledger`, `core.wants`, and writer symbols such as `IdentityLedger`,
  `LedgerWriter`, `Wants`, and `record_event`.
- `metadata_json` is scalar-only and size-capped so it cannot become a backdoor
  for long prose while the claim and witness fields are content-light.

## Verification

Focused suite:

```text
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_gestation_memory tests.test_gestation_memory_sources \
  tests.test_gestation_memory_boundary -v

Ran 32 tests in 0.106s
OK
```

Lint:

```text
/home/rohit/maez/.venv/bin/ruff check \
  core/evolution/gestation_memory.py tests/test_gestation_memory*.py

All checks passed!
```

Diff whitespace:

```text
git diff --check ae9488b..HEAD

clean
```

## Owner Breath After Review

After review passes: merge locally, no push. No restart is needed. The witness is
manual and offline: record real claims sourced only to committed docs, render the
binder, confirm the rails bite (`witness_note`-only and inferred facts reject),
and confirm a correction supersedes via the edge table without mutating the old
claim row.

Plain English: this gives Maez an evidence binder about its own becoming. Every
entry needs a real receipt, meanings are labeled as meanings, and corrections are
added beside the old record instead of painting over it.
