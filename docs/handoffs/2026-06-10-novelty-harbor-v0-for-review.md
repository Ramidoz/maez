# Novelty Harbor v0 - Review Handoff

Status: ready for review. Branch: `novelty-harbor-v0`.

## What Changed

Built the manual/offline Novelty Harbor shelf:

- `core/evolution/novelty_harbor.py`
- default manual DB path: `memory/novelty_harbor.db`
- manual `NoveltyHarbor.record_event(...)`
- manual `NoveltyHarbor.supersede(...)`
- manual CLI: `python -m core.evolution.novelty_harbor record ...`

This slice adds no daemon wiring, no autonomous novelty detector, and no promotion integration into soul/memory/wants.

## Review Anchors

1. Harbor owns final status. Caller-requested `harbored`/`promoted` cannot override failed invariants or covenant-break flags.
2. `rejected_unsafe` is terminal. It cannot be superseded, cannot be pointed at by a replacement row, and remains visible in `list_by_status("rejected_unsafe")`.
3. Supersession provenance is coherent and append-preserving: one replacement candidate per old row, enforced both sequentially and by a SQLite partial unique index under concurrency.
4. A pending replacement candidate cannot itself be superseded until it has actually become the recorded successor; resolved chains such as `A -> B -> D` are allowed.
5. `promoted` is label-only and requires `promotion_decision_ref`; no soul/memory/wants writer imports.
6. Metadata is content-light and cannot smuggle long prose.
7. Core module imports no daemon, voice, telegram, llm client, wants, ledger/writer/body path, soul writer, memory writer, or `valence_live`; `soul_invariants` is the intentional boundary dependency.
8. CLI prints content-light confirmation only: `event_id`, `status`, `invariant_status`, `flags`.

## Verification

Harbor suite:

```text
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_novelty_harbor tests.test_novelty_harbor_boundary tests.test_novelty_harbor_cli
Ran 32 tests in 0.106s
OK
```

Adjacent invariant/valence sanity:

```text
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_soul_invariants tests.test_valence_live_core tests.test_valence_reading
Ran 30 tests in 0.004s
OK
```

Ruff:

```text
/home/rohit/maez/.venv/bin/ruff check core/evolution/novelty_harbor.py tests/test_novelty_harbor.py tests/test_novelty_harbor_boundary.py tests/test_novelty_harbor_cli.py
All checks passed!
```

Diff hygiene:

```text
git diff --check 5bb34af..HEAD
<no output, exit 0>
```

Anti-laundering mutation check:

```text
Baseline NoveltyHarborCoreTests: green.
Temporarily changed _final_status(...) to return requested_status.
Broken rail result: FAILED (failures=6), including 'harbored' != 'rejected_unsafe'.
Restored _final_status(...): NoveltyHarborCoreTests green again.
```

Manual DB posture:

```text
No memory/novelty_harbor.db exists in the worktree or main checkout during implementation.
Tests and smoke checks used temp DB paths.
```

## Review History

The supersession rail took multiple real review rounds before it became coherent:

- closed raw SQLite handle leaks from the initial store implementation;
- removed a live `current_soul()` dependency from tests and replaced it with an isolated fixture soul plus a sentinel DB assertion;
- made `rejected_unsafe` terminal in both directions, including forward-pointer rejection;
- required replacements to point back to the old row and rejected terminal replacements;
- rejected stale links to already-superseded rows;
- enforced one replacement candidate per old row sequentially and under concurrent callers with a SQLite partial unique index;
- narrowed `sqlite3.IntegrityError` conversion so only the supersession uniqueness violation maps to `ValueError`; unrelated DB integrity failures propagate unchanged.

## Not Done

- No autonomous novelty detector.
- No daemon wiring.
- No model judge.
- No promotion integration into soul/memory/wants.
- No merge.
- No restart.
- No production `memory/novelty_harbor.db` manual witness yet.

## Manual Witness After Merge

Record one benign known surprise and one unsafe fixture with an explicit temp or owner-approved DB path. Confirm the benign row is `harbored`, the unsafe row is `rejected_unsafe`, and CLI stdout remains content-light.
