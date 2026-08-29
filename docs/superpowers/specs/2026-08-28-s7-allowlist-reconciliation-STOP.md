# S7 action-route allowlist — bounded reconciliation, STOPPED at rule 6

**Date:** 2026-08-28 · **Scope:** the 186-row table in
`docs/superpowers/specs/2026-08-07-s7-action-binding-design.md`, guarded by
`tests/test_s7_action_route_allowlist.py`.

**Outcome: the table was NOT regenerated.** Five real new calls appeared, and
the owner's rule 6 says stop and report rather than bless a regenerated
inventory.

## What the table represents

One row per S7 authority site: `(file, enclosing symbol, syntactic role,
construct, line)`. Structural identity is `(file, symbol, construct)`; the line
is where that site sat when the table was ratified on **2026-08-13** (`a16ce59`).

## Reconciliation, mechanically derived from the current tree

Structural identity compared ignoring line number:

| Classification | Count |
|---|---|
| SAME STRUCTURAL CALL, LINE MOVED | **125 of 186** |
| REAL NEW CALL (within pinned files) | 0 |
| REAL REMOVED CALL | 0 |
| CALL CHANGED SEMANTICS / NEEDS REVIEW | 0 |
| UNRESOLVED | 0 |

Line drift is confined to five files and is pure movement:

| Rows moved | File |
|---:|---|
| 54 | `core/governance/s7_guarded_execution.py` |
| 43 | `core/governance/operator_user_boundary.py` |
| 18 | `core/governance/s7_webauthn_ceremony.py` |
| 8 | `daemon/maez_daemon.py` |
| 2 | `core/governance/s7_webauthn_bootstrap.py` |

The guard's own sibling tests already agree and all pass:
`test_identity_ignoring_lines_is_already_exact`,
`test_no_pinned_site_has_disappeared`, `test_no_unpinned_site_exists`,
`test_the_totals_match_exactly`, `test_multiplicity_is_carried_not_collapsed`.
So condition 5 (all 125 stale entries are line movement) **is satisfied**.

## Why it stopped anyway: five real new calls in unpinned files

`test_no_tracked_call_lives_outside_the_allowlisted_files` — the discovery half,
which exists precisely because a pinned table cannot see a NEW road — reports:

```
core/governance/birth_authorization.py
    build_birth_envelope()                  -> build_work_request_envelope
    mint_and_consume_birth_authorization()  -> _open_s7_connection_from_held_store
    mint_and_consume_birth_authorization()  -> consume_for_execution_with_committed_row
    mint_and_consume_birth_authorization()  -> render_request_statement
core/governance/s7_covenant_ceremony.py
    provision_covenant_phase_table_at()     -> _open_s7_connection_from_held_store
```

These are not drift. Both files were created **after** the table was ratified —
`s7_covenant_ceremony.py` on 2026-08-19 (`3325adf`), `birth_authorization.py` on
2026-08-27 (`d8ab031`) — and neither is named anywhere in the ratified design
doc. They were never scoped out; they were never added.

Two of them reach `_open_s7_connection_from_held_store`, a **private** function,
from outside its module. Whether that is intended is a governance question, not
a bookkeeping one.

## The debt note, now with evidence

`2026-08-28-callsite-inventory-fragility-DEBT.md` argued the danger of a
chronically-red guard is not the false alarm but what it trains. This is that
prediction, confirmed: the discovery half **did** fire when the first new road
appeared on 2026-08-19, and again on 2026-08-27. Nobody acted, because the file
was already red for an unrelated reason — stale line numbers. A real finding sat
behind that noise for nine days.

The guard worked. The reading of it did not.

## Recommendation (narrow, no migration)

The structural/positional split **already exists** in this file:
`test_identity_ignoring_lines_is_already_exact` is authoritative identity;
`test_every_row_sits_on_the_line_it_claims` is position. They are separate tests
over the same table.

So the improvement needs no framework redesign and no re-ratification: make the
line test **diagnostic** — report drift, name the files, do not fail — while the
structural test and the discovery guard stay hard. Then a red in this file
always means a road changed or appeared, never that a line moved. Line numbers
stay in the table as human wayfinding.

Not done here: it changes the meaning of a ratified guard, which is the owner's
call.

## What is still owed

1. A ruling on the five unpinned S7 roads: ratify them into the table, or
   record why they stand outside it. `birth_authorization.py` sits under the
   FROZEN birth gate, so this is not a clerical add.
2. Only then a line refresh for the 125 moved rows.
3. Green guard plus a mutation proof (synthetic call turns it red, removal
   turns it green).
