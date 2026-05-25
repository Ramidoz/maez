# Codex Engineering Panel Review — Subjective-Duration Meaningful-Salience Seam Pass 5

**Prepared:** 2026-05-25
**Artifact reviewed:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md` (DRAFT v8)
**Brief reviewed:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/reviews/codex-engineering-panel-brief-pass5.md`
**Parent commit:** `fb2f781`
**Verdict:** **RATIFY-CLEAR — PROCEED TO CANONICALIZATION**

Pass-5 was scoped to the v7 -> v8 next-step contradiction only. The contradiction is resolved. The scratch canary now writes through the production write path and verifies through direct SQL against the scratch DB, while the public lookup API remains absolute on refusing sentinel bond ids.

I did not run the §8.2.1 snippet against current `fb2f781` code because this is still a spec-before-implementation artifact; the current production code does not yet contain the new schema/kwargs. The review below verifies that the snippet is internally runnable against the implementation the spec requires.

## Verified Surfaces

| Surface | Evidence | Result |
|---|---:|---|
| Git state | `HEAD fb2f781`; reviewed draft spec + pass-5 brief only | Verified |
| V1 direct SQL canary | §8.2.1 uses `sqlite3.connect(scratch_db_path)` and `conn.execute(...)`, lines 1357-1368 | Verified |
| V1 no public lookup in scratch canary | §8.2.1 no longer calls `lookup_meaningful_salience_event_record(...)` in the canary verification block | Verified |
| V1 SQL predicate | Direct SQL WHERE clause uses `bond_id = ? AND producer_event_id = ?`, bound to `_SCRATCH_FIXTURE_BOND_ID` and `event_id_str`, lines 1362-1368 | Verified |
| V1 row assertions | Assertions use `row[...]` for `meaningfulness_score`, `is_canary`, `salience_event_kind`, `producer_ref`, `bond_id`, lines 1369-1374 | Verified |
| V2 four-row policy table | §4.2.2 table has producer-write, bond-scoped lookup, felt-time aggregate readers, and scratch-canary-path rows, lines 534-539 | Verified |
| V3 reader-class split | §4.2.2 distinguishes production readers from substrate self-test readers, lines 548-564 | Verified |
| V4 RED #50/#51 non-conflict | RED #50 keeps public lookup refusal; RED #51 says canary uses direct SQL and explicitly names non-conflict, lines 1724-1725 | Verified |
| V5 unchanged paths | §6.2.2 accepts `_SCRATCH_FIXTURE`; §7.1 refuses `_SCRATCH_FIXTURE`; §4.2.1 aggregates exclude both sentinels; §8.2.2 live canary still uses public lookup with real bond id | Verified |
| V6 version state | Header DRAFT v8; footer "End of v8 spec draft"; trajectory names v1-v8 | Verified |

## Findings

No blocking findings.

No amendments required.

## Detail

### V1 — Scratch Canary Uses Direct SQL

The previous pass-4 failure was: canary write succeeded, then canary lookup failed because §7.1 refused `_SCRATCH_FIXTURE`. v8 removes that conflict by replacing public lookup verification with direct SQL:

```python
with closing(sqlite3.connect(scratch_db_path)) as conn:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT meaningfulness_score, is_canary, salience_event_kind, "
        "producer_ref, bond_id, producer_event_id "
        "FROM subjective_duration_salience_events "
        "WHERE bond_id = ? AND producer_event_id = ?",
        (_SCRATCH_FIXTURE_BOND_ID, event_id_str),
    ).fetchone()
```

The constants and assertions are in the same snippet: `_SCRATCH_FIXTURE_BOND_ID = "_SCRATCH_FIXTURE"` is defined before use, and the assertions read from `row[...]`. This satisfies the brief's direct-SQL requirement.

### V2/V3 — Sentinel Policy Is Now Explicit

§4.2.2 now has the missing fourth path:

- Producer-path write: `_SCRATCH_FIXTURE` accepted.
- Bond-scoped lookup: `_SCRATCH_FIXTURE` refused.
- Felt-time aggregate readers: `_SCRATCH_FIXTURE` excluded.
- Scratch-canary path: verifies via direct SQL against scratch DB.

The future-reader paragraph now distinguishes production readers, which must exclude sentinel rows, from substrate self-test readers, which may use direct SQL to verify their own writes. That closes the pass-4 ambiguity.

### V4 — RED #50/#51 No Longer Conflict

RED #50 and RED #51 now test different surfaces:

- RED #50: public lookup with `_SCRATCH_FIXTURE` raises `ValueError`; aggregate readers exclude scratch rows.
- RED #51: scratch canary does not use public lookup; it writes through producer path and verifies through direct SQL.

These can both be true.

### V5/V6 — No Regression Found

The v7 surfaces remain intact:

- Producer path has no `_SCRATCH_FIXTURE` raise and retains `_LEGACY`/wildcard refusal.
- Public lookup still refuses `_SCRATCH_FIXTURE`.
- Aggregate readers still use `bond_id NOT IN ('_LEGACY', '_SCRATCH_FIXTURE')` and `is_canary = 0`.
- The live-path canary uses a real bond id through public lookup, not the scratch sentinel.

Spec-wide versioning is coherent for v8.

## Scope Realism

The spec is implementation-ready. The remaining implementation risk is normal RED-first execution risk, not a spec contradiction: the tests must prove the migration, producer kwargs, direct-SQL scratch canary, public lookup refusal, aggregate exclusion, and live-path canary all behave exactly as written.

## Plain-Language Readout

The scratch canary now has a coherent route. It writes through the same write path future producers will use, proving the seam's write-side math. Then it checks its scratch row directly in the scratch database, instead of asking the public lookup API to return a sentinel row the public API is supposed to refuse. That keeps the production boundary strict without blocking the self-test.

Proceed to canonicalization.
