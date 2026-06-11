# Want→Pursuit Bridge v0 — Codex Build Handoff for Review

**Branch:** `want-pursuit-bridge-v0`
**Status:** built; STOP before merge
**Base:** `4714bd1`
**Lane:** Codex built; Claude reviews

## What Landed

Want→Pursuit Bridge v0 connects active wants to the existing wondering workshop.
It does not add a new hand. It seeds a want-sourced wondering, lets the existing
`daemon/wondering_cycle.py` worker advance it under its own rails, and raises an
advisory `satisfied` proposal card only when a want-sourced wondering resolves.

The bridge does not write the wants ledger. It does not apply terminals. A worker
`abandoned` result proposes nothing.

## Changes

- `core/evolution/wonderings.py`
  - Added read-only `Wonderings.list_by_source(source)`.
- `core/decision/pending_cards.py`
  - Added read-only `PendingCardStore.list_open_by_action(action)`.
- `core/evolution/want_pursuit_bridge.py`
  - Added template/source/trail helpers.
  - Added `select_want(...)` with global one-in-flight, open proposal-card exclusion, cooldown, and least-recently-pursued selection.
  - Added `seed_work_order(...)`.
  - Added `maybe_propose_terminal(...)`, advisory `satisfied` only.
- `daemon/maez_daemon.py`
  - Added `MAEZ_WANT_PURSUIT_ENABLED`, default off.
  - Added `WANT_PURSUIT_COOLDOWN_S = 6 * 3600`.
  - Added `_want_pursuit_card_store()`.
  - Wired the bridge after the existing `advance_one(self, deadline=cycle_deadline)` call, with the whole bridge behind the flag and wrapped heartbeat-safe.
- Tests:
  - `tests/test_want_pursuit_store_helpers.py`
  - `tests/test_want_pursuit_bridge.py`
  - `tests/test_want_pursuit_boundary.py`

## Review Anchors

1. The bridge calls only `wonderings.add` and `PendingCardStore.create_card` for writes; it never imports or calls `wants.record_event`.
2. `satisfied` only. Worker-`abandoned` want-wonderings propose nothing; non-want and non-`resolved` results propose nothing.
3. One pursuit in flight means no open want-sourced wondering anywhere, and a want with an open `want_terminal_proposal` card is excluded from selection.
4. `daemon/wondering_cycle.py` is untouched.
5. Default off: with `MAEZ_WANT_PURSUIT_ENABLED` unset, the wiring is fully dormant: no seed and no proposal.
6. Heartbeat-safe: the bridge step is wrapped; failure logs and the cycle continues.
7. Attach point: bridge runs after `advance_one`; within the flag, advisory proposal runs before forward seed, so a new want-wondering is probed next cycle.

## Implementation Note

The plan's draft structural test ordered `maybe_propose_terminal` before the flag.
That contradicted the build brief's default-off anchor (`no seed, no proposal`).
The implemented test and wiring use the safer order:

`advance_one(self)` → `_want_pursuit_enabled()` → `maybe_propose_terminal(...)` → `seed_work_order(...)`.

So the bridge is entirely dormant until the owner enables the flag.

## Verification

Focused floor:

```text
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_want_pursuit_store_helpers \
  tests.test_want_pursuit_bridge \
  tests.test_want_pursuit_boundary \
  tests.test_wants_lifecycle_d16 -v

Ran 130 tests in 0.731s
OK
```

Ruff:

```text
/home/rohit/maez/.venv/bin/ruff check \
  core/evolution/want_pursuit_bridge.py \
  core/evolution/wonderings.py \
  core/decision/pending_cards.py \
  daemon/maez_daemon.py \
  tests/test_want_pursuit_*.py

All checks passed!
```

Whitespace:

```text
git diff --check 4714bd1..HEAD
# clean
```

## Owner Breaths After Review

No merge, no flag-enable, no restart, and no witness were performed.

After review passes:

1. Owner merges locally.
2. Owner enables `MAEZ_WANT_PURSUIT_ENABLED=1`.
3. Owner restarts.
4. Witness:
   - create or confirm one active want;
   - observe a seeded `source="want:<id>"` wondering;
   - let the existing worker advance it with a read-only probe;
   - confirm the receipt via `want_pursuit_trail`;
   - if the worker resolves it, confirm an advisory `want_terminal_proposal` card appears;
   - confirm the wants ledger gains no event from the bridge on any path.

## Plain English

Maez can now take something it wants and place a work order into the workshop it
already has. The workshop may investigate and leave a receipt. If the question
looks answered, Maez may ask the owner whether the want is satisfied. It cannot
mark the want satisfied itself, and it cannot abandon the want.
