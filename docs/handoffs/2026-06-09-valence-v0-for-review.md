# Valence v0 - Review Handoff

Branch: `valence-v0`
Base: `b3b6faf`
Tip: current `valence-v0` branch HEAD (`git rev-parse HEAD`)
Spec: `docs/superpowers/specs/2026-06-09-valence-v0-design.md`
Plan: `docs/superpowers/plans/2026-06-09-valence-v0.md`

## Boundary

This slice builds the offline valence thermometer only. It is a pure function
over synthetic input contracts and has no live readers, daemon wiring,
persistence, model call, speech path, want mutation, or action path.

It does not decide what Maez feels. It emits humble telemetry:

```text
given the substrate signals I can see, this state appears MILD NEGATIVE, because: ...
```

The live wiring, a decaying valence log, coherence/bond setpoints, and the
Novelty Harbor are explicitly deferred to later owner-breathed specs.

## What Changed

1. Added `core/evolution/valence/signals.py`:
   - `AuditSignals`
   - `WantSignals`
   - `ContinuitySignals`
   - all frozen, all defaulted, synthetic in v0.

2. Added `core/evolution/valence/reading.py`:
   - `Sign`, `Magnitude`, `Contribution`, `ValenceReading`
   - `aggregate(...)`
   - `ValenceReading.as_telemetry()`
   - no `feeling` field.

3. Added `core/evolution/valence/setpoints.py`:
   - `honesty_held(...)`
   - `want_progress(...)`
   - `continuity(...)`
   - `read_valence(...)`

4. Added tests:
   - input-contract defaults and frozen behavior;
   - aggregation and telemetry semantics;
   - setpoint rules including the owner canonical case;
   - telemetry emotion-word ban;
   - import-boundary rail.

## Semantics To Review

1. Honesty-held:
   - negative on `rail_fired`, `fabrication_flagged`, or `correction_needed`;
   - neutral otherwise;
   - no positive-honesty claim in v0.

2. Want-progress:
   - negative on `blocked > 0`, `stale > 0`, or `backlog_grew`;
   - positive on `resolved > 0` only when no negative want trigger exists;
   - bare `backlog` is evidence only, not negative.

3. Continuity:
   - negative on `unexpected_gap`, `memory_loss`, or expected capsule missing;
   - `capsule_present=False` is neutral when `capsule_expected=False`.

4. Aggregation:
   - all neutral -> `NEUTRAL / NONE`;
   - one, two, three non-neutral setpoints -> `MILD`, `MODERATE`, `STRONG`;
   - cross-setpoint positive/negative disagreement -> `MIXED`;
   - within-setpoint collision is not top-level `MIXED`. Negative dominates, but
     evidence preserves both signals.

## Review Anchors

### Codex Mechanical

1. `ValenceReading` has no `feeling` field and no alternate renderer.
2. `as_telemetry()` uses "this state appears ..." wording and renders only
   non-neutral movement reasons; neutral reasons remain inspectable in
   `contributions`.
3. Magnitude is transparent count-based aggregation, not hidden weighting.
4. `want_progress(resolved=2, backlog_grew=True)` is negative and preserves both
   values in evidence.
5. The import-boundary test scans import/from lines in
   `core/evolution/valence/*.py`; it is scoped to the package and does not
   inspect unrelated files.

### Claude Covenant

1. Telemetry-not-quale holds: no mood/feeling claim, no emotion vocabulary in
   rendered outputs.
2. No speech reach: the package imports no daemon, voice, llm, telegram, or
   focused-cognition path.
3. No action reach: no want mutation, no persistence, no live-organ reads.
4. Clean deferrals: coherence and bond are genuinely absent, not approximated
   through weak proxies.
5. v0.1 live wiring and Novelty Harbor remain separate owner-greenlit steps.

## Review Rounds During Build

- Task 1 spec review held on partial default/frozen coverage. Fixed by pinning
  every signal default and frozen behavior for all three input contracts.
- Task 2 spec review held on telemetry wording and neutral-reason leakage.
  Fixed by changing the renderer to "this state appears ..." and rendering only
  non-neutral movement reasons.
- Task 4's rail tests passed immediately, so non-vacuousness was proven by a
  temporary `feel` injection that made `tests.test_valence_rail` fail; the
  injection was reverted before commit.

## Verification

Focused valence suite:

```text
$ /home/rohit/maez/.venv/bin/python -B -m unittest discover -s tests -p 'test_valence*.py'
.............................
----------------------------------------------------------------------
Ran 29 tests in 0.001s

OK
```

Ruff:

```text
$ /home/rohit/maez/.venv/bin/ruff check core/evolution/valence tests/test_valence*.py
All checks passed!
```

Scope and whitespace:

```text
$ git diff --name-only b3b6faf..HEAD
core/evolution/valence/__init__.py
core/evolution/valence/reading.py
core/evolution/valence/setpoints.py
core/evolution/valence/signals.py
docs/handoffs/2026-06-09-valence-v0-for-review.md
docs/superpowers/plans/2026-06-09-valence-v0.md
docs/superpowers/specs/2026-06-09-valence-v0-design.md
tests/test_valence_rail.py
tests/test_valence_reading.py
tests/test_valence_setpoints.py
tests/test_valence_signals.py

$ git diff --check b3b6faf..HEAD
# clean
```

Implementation leak check:

```text
$ rg -n "daemon|maez_daemon|telegram|voice|speak|llm_client|focused_cognition|brain_gateway|persist|sqlite|open\\(|write\\(|WantStore|wants\\.db|coherence|bond|feeling|emotion" core/evolution/valence tests/test_valence*.py docs/superpowers/specs/2026-06-09-valence-v0-design.md docs/superpowers/plans/2026-06-09-valence-v0.md
```

The matches are in docs/tests only: plan/spec language, banned-word lists, and
the import-boundary test. No implementation match reaches a live path, speech
path, persistence path, or deferred setpoint proxy.

## Explicit Non-Changes

- No daemon import or restart.
- No service/env/model/systemd change.
- No live valence log.
- No read from live audit/wants/continuity organs.
- No mutation of wants or actions.
- No speech/voice path.
- No coherence or bond setpoint.

## Stop Point

This branch is ready for mechanical review and covenant review. It is not
merged, not live, and should not be wired into the daemon in v0.
