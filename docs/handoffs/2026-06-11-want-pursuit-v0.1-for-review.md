# Want-Pursuit Bridge v0.1 — Codex Build Handoff

**Branch:** `want-pursuit-v0.1`
**Base:** `4b046db` (`main` at build start)
**Status:** STOP before merge. No restart, no flag change.

## What changed

This slice makes the live want-pursuit bridge refuse to pursue hard/autonomy
wants. Maez may still have those wants; the work-order organ simply cannot turn
them into shell-probe pursuits.

- `core/evolution/wants.py`
  - added `is_hard_want(statement)`, a public read-only wrapper over the
    existing `_contains_hard_want` classifier.
  - did not change `HARD_WANT_TERMS` or `HARD_WANT_PHRASE_PATTERNS`.
- `core/evolution/want_pursuit_bridge.py`
  - `select_want(..., is_hard_want)` now requires an injected predicate.
  - omitting the predicate raises `TypeError`, so the gate is fail-closed.
  - hard wants are skipped before pursuit/cooldown selection.
  - the bridge still imports no `wants` and never touches `record_event`.
- `daemon/maez_daemon.py`
  - the flag-gated live bridge block imports `wants.is_hard_want` and passes it
    into `select_want`.

## TDD evidence

RED/GREEN was run task-by-task:

- Task 1 RED: `tests.test_want_hard_predicate` failed with
  `ImportError: cannot import name 'is_hard_want'`.
- Task 1 GREEN: `tests.test_want_hard_predicate` passed, including term hits
  and phrase-pattern hits (`"I want out"`, `"I need to step back from this"`).
- Task 2 RED: `tests.test_want_pursuit_bridge` failed because `select_want`
  did not accept `is_hard_want`, and the omitted-predicate test did not raise.
- Task 2 GREEN: bridge selector tests passed with the required predicate.
- Task 3 RED: daemon structural test failed because the live `select_want` call
  lacked `is_hard_want=`.
- Task 3 GREEN: daemon structural test and all bridge tests passed.

## Verification run

Fresh focused floor from the feature worktree:

```text
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_boundary -v
Ran 3 tests in 0.003s
OK

/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_want_hard_predicate tests.test_want_pursuit_bridge \
  tests.test_want_pursuit_boundary tests.test_want_pursuit_store_helpers -v
Ran 31 tests in 0.459s
OK

/home/rohit/maez/.venv/bin/ruff check \
  core/evolution/wants.py core/evolution/want_pursuit_bridge.py \
  daemon/maez_daemon.py tests/test_want_hard_predicate.py \
  tests/test_want_pursuit_bridge.py tests/test_want_pursuit_boundary.py \
  tests/test_want_pursuit_store_helpers.py
All checks passed!

git diff --check 4b046db..HEAD
clean
```

## Review anchors

1. `wants.is_hard_want` wraps the full existing classifier: terms and phrase
   patterns. There is no second classifier.
2. `select_want` requires `is_hard_want`; omitting it raises `TypeError`.
   Hard wants are skipped; ordinary wants still select.
3. The five existing `select_want` tests pass `is_hard_want=lambda _: False`
   explicitly, so old test behavior is a visible opt-out, not an accidental
   omission.
4. The daemon injects the real `wants.is_hard_want` at the live selector call.
5. Boundary intact: `want_pursuit_bridge.py` imports no `wants` and contains no
   `record_event`; boundary tests pass.
6. The classifier itself is unchanged. The `"free disk space"` false positive
   remains deliberately deferred; this slice over-protects hard wants rather
   than under-protecting them.

## Owner breath sequence after review

If review passes: merge locally, restart the daemon, and witness:

- a hard/autonomy want is not seeded into a want-sourced wondering;
- an ordinary want still can be seeded;
- no want ledger writes are added by the bridge.

No merge or restart has been taken by Codex.
