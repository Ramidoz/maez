# Intake Understanding Faculty v0 — For Cross-Lane Review

## Status

Built and stopped at review gate. No merge, no restart, no flag flip, no live witness.

## What changed

- `core/cognition/intake_faculty.py`: closed `IntakeRead` schema, fake backend, local 4B judge backend, prompt.
- `core/cognition/intake_shadow.py`: default-off hook, bounded queue, one-in-flight worker, content-light rotated telemetry, side-effect-free gate snapshots.
- `skills/surface/maez_adapter.py`: Surface V2 enqueue only when `MAEZ_INTAKE_FACULTY_SHADOW=1`.

## Review anchors

1. Shadow-only: no decision changes, no return-value dependency on the faculty read.
2. Content-light: no raw owner text in telemetry unless `MAEZ_INTAKE_FACULTY_DEBUG=1`.
3. Judge contention: bounded queue, one in-flight, busy/drop statuses; audit judge must not be starved.
4. Side-effect-free gate comparison: no consuming/popping receipts or cards.
5. Correct live seam: Surface V2 (`telegram_surface`), not legacy TelegramVoice.
6. One self / instruments: no calls to the 27B self brain, no actions, no wants writes.

## Verification run by builder

```text
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_intake_faculty tests.test_intake_shadow tests.test_surface_adapter tests.test_search_commitment -v

Ran 57 tests in 15.191s

OK
```

```text
/home/rohit/maez/.venv/bin/ruff check core/cognition/intake_faculty.py core/cognition/intake_shadow.py skills/surface/maez_adapter.py tests/test_intake_faculty.py tests/test_intake_shadow.py tests/test_surface_adapter.py

All checks passed!
```

## Owner witness after review and merge

1. Merge locally, no push unless owner asks.
2. Restart only when owner approves.
3. Flip `MAEZ_INTAKE_FACULTY_SHADOW=1`.
4. Send a small witness set:
   - `Proceed` after a typed search offer.
   - A boundary phrasing outside the hardcoded list.
   - A continuity follow-up using `that`.
   - An ordinary turn.
5. Read `~/.local/state/maez/intake_shadow.jsonl`; confirm content-light rows, no reply behavior change, disagreements visible.
