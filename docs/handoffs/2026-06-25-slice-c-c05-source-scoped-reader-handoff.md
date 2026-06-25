# Slice C C0.5 — Source-Scoped Private Reader Handoff

Branch: `slice-c-c05-source-scoped-reader`
Status: STOPPED at review gate.

Not merged. Not restarted. No flags changed.

## What Changed

- Added `PrivateThoughts.recent_by_source(...)`, a store-level reader that locks on the exact producer identity in `context_json`:
  `json_extract(context_json, '$.source') = ?`.
- The reader also enforces `memory_phase`, `context.consent_tier`, and `context.allowed_flows` in SQL before `LIMIT`.
- Retrofitted `MaezDaemon._lean_idle_recent_private_thoughts()` to call:
  `recent_by_source(HEARTBEAT_VERSION, limit=2)`.
- Kept `select_private_reader_thoughts(...)` as the in-memory double-lock after the SQL door.

## Task 0 Decisions

- JSON1 source scoping works against the real runtime store:
  - `source-scope` for `daemon_cycle.reasoning_residue`: `4507`
  - `flow-each` for `private_reader`: `4523`
- The exact heartbeat source is `lean_idle_heartbeat.v0`.
- `ConsentTier` currently exposes only `OWNER_PRIVATE`, so the wrong-consent regression test uses a crafted direct-SQL context mutation.
- Source-key law: lock on `context.source`, not `provenance`, `producer_id`, or `signal_class`.
  `record_signal()` writes `provenance = kind_value`, so provenance is the note kind, not the heartbeat notebook identity.

## Tests That Pin The C0 Findings

- Newest foreign rows never surface:
  `reasoning_residue` and `clinical_boundary` rows newer than a heartbeat row are excluded.
- A heartbeat row buried below 25 newer foreign rows still surfaces, proving SQL-level source scoping instead of global recent-window filtering.
- A heartbeat-source row with wrong phase, missing `private_reader`, or wrong consent is excluded.
- The daemon adapter no longer calls `recent(20)`; the test fails if that fragile path is used.

## Verification

Latest local verification before this handoff:

```text
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_private_thoughts_source_scope tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon -v

Ran 41 tests in 0.540s
OK
```

```text
/home/rohit/maez/.venv/bin/ruff check \
  core/infra/private_thoughts.py daemon/maez_daemon.py \
  tests/test_private_thoughts_source_scope.py tests/test_lean_idle_daemon.py

All checks passed!
```

## Review Gate

Claude/Codex covenant review should verify:

- The door locks on `context.source == HEARTBEAT_VERSION` only.
- `provenance`, `producer_id`, and `signal_class` are not used as the source identity.
- Foreign producers, including `clinical_boundary`, are structurally unreachable before `LIMIT`.
- Consent, flow, and phase are enforced in the SQL gate.
- `_lean_idle_recent_private_thoughts()` no longer uses global `recent(20)`.
- No behavior change is intended today; this is correctness and isolation plumbing for the private idle loop.

## Owner Breath After PASS

After review clears:

1. Merge this branch.
2. Restart Maez.
3. Confirm heartbeat still runs normally.
4. Once a heartbeat thought exists, confirm `recent_private_thoughts` can surface heartbeat rows and never foreign rows.

C1 broker remains BLOCKED until C0.5 is merged and witnessed.
