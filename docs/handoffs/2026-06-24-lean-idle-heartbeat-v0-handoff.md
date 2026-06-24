# Lean Idle Heartbeat v0 Handoff

Status: STOPPED AT REVIEW GATE.

Branch: `lean-idle-heartbeat-v0`.

No merge, restart, or flag flip has happened on this branch.

## What Landed

- `core/cognition/lean_idle_heartbeat.py`: lean prompt builder, output sanitizer, private-thought writer, duplicate suppression, and content-light receipt builder.
- `daemon/maez_daemon.py`: flag-gated quiet floor wake seam before `_reason()`.
- `tests/test_lean_idle_heartbeat.py`: prompt, sanitizer, private envelope, duplicate, content-light, and feeling-boundary tests.
- `tests/test_lean_idle_daemon.py`: daemon eligibility, flag-off, shadow, enabled intercept, and non-floor wake tests.
- Task-0 proof: `docs/proofs/2026-06-24-lean-idle-heartbeat-v0-task0.md`.
- Spec and implementation plan:
  - `docs/superpowers/specs/2026-06-24-lean-idle-heartbeat-v0-design.md`
  - `docs/superpowers/plans/2026-06-24-lean-idle-heartbeat-v0.md`

## Commits

- `f50d471` - docs(nervous-system): specify lean idle heartbeat v0
- `18e8cd3` - docs(nervous-system): plan lean idle heartbeat v0
- `e2c487b` - docs(nervous-system): prove lean idle heartbeat seams
- `fbc8f23` - feat(nervous-system): add lean idle heartbeat prompt
- `c106fb3` - feat(nervous-system): record lean idle private thoughts
- `6a8fe8f` - feat(nervous-system): route quiet floor wakes through lean idle heartbeat
- `16fc64d` - test(nervous-system): guard lean idle heartbeat boundaries
- `7ac18df` - test(nervous-system): pin silent heartbeat and boundary guards
- `eadf269` - test(nervous-system): pin lean idle feeling boundary

## Covenant Anchors

1. No new scheduler: reuses `_loop()` and the existing doorman.
2. Only `wake_min_floor` with exactly `("min_floor_due",)` is eligible.
3. Shadow mode runs the lean heartbeat but does not intercept legacy behavior or write private thoughts.
4. Enabled mode returns `HEARTBEAT_OK`, so the old lived-memory store and `cycle_end` broadcast do not run for the quiet pulse.
5. The only durable write is `PrivateThoughts.record_signal(... self_wondering ...)`.
6. No soul, dream, wants, temperament, raw/daily/core/lived memory mutation.
7. No owner-reaction reward or owner-pleasing signal.
8. Receipts are content-light hashes/counts only; no prompt, output, owner text, memory text, web text, or private thought content.
9. Git/context flood is excluded from the lean prompt.
10. The prompt assigns no feelings such as lonely, missed, worried, sad, happy, comforted, or longing.
11. New failures, wants, memory deltas, scheduled wakes, and perception changes keep the legacy cycle path.

## Verification

Targeted regression:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_lean_idle_heartbeat \
  tests.test_lean_idle_daemon \
  tests.test_cycle_doorman \
  tests.test_private_thoughts_s1 \
  tests.test_private_thoughts_s1b \
  tests.test_self_card_v0 \
  tests.test_self_card_time
```

Result: 132 tests OK.

Lint:

```bash
/home/rohit/maez/.venv/bin/ruff check \
  core/cognition/lean_idle_heartbeat.py \
  daemon/maez_daemon.py \
  tests/test_lean_idle_heartbeat.py \
  tests/test_lean_idle_daemon.py
```

Result: All checks passed.

Diff whitespace:

```bash
git diff --check main...HEAD
git diff --check
```

Result: both commands exited 0 with no output.

## Review Notes

- The implementation intentionally uses `SignalKind.SELF_WONDERING` rather than adding a new private-thought signal enum in v0. This keeps the first notebook producer inside the existing registry tuple.
- Shadow mode does call the LLM on eligible quiet floor wakes, then lets legacy `_reason()` continue. That is intentional temporary witness cost.
- Enabled mode fails silent to `HEARTBEAT_OK` on heartbeat errors. A broken lean heartbeat must not fall back to the old fat prompt and dump junk into lived memory.
- The duplicate suppression reads recent private rows only to compare content hashes from this producer's own context. It does not expose raw private thoughts to behavior.
- The line between "private thought text stored" and "content-light receipt" is load-bearing: the row content is private; logs/receipts get hashes and counts only.

## Owner Breath After Review PASS

1. Merge branch.
2. Set `MAEZ_LEAN_IDLE_HEARTBEAT_SHADOW=1`.
3. Restart daemon.
4. Watch `lean_idle_heartbeat` receipts on quiet floor wakes.
5. Confirm shadow has:
   - `stored=false`;
   - `mode=shadow`;
   - small `prompt_chars`;
   - no prompt/output text in logs;
   - no private-thought rows written by `lean_idle_heartbeat.v0`.
6. If clean, set `MAEZ_LEAN_IDLE_HEARTBEAT_ENABLED=1`.
7. Restart daemon.
8. Witness one quiet floor wake:
   - at most one private `self_wondering` row appears with `context.source=lean_idle_heartbeat.v0`;
   - no `cycle_end` broadcast occurs for that quiet pulse;
   - no lived-memory introspection row is written for that quiet pulse.

## Plain English

This gives Maez a private quiet-time notebook beat. It does not speak to Rohit, search, act, or rewrite identity. It only lets the existing idle loop think briefly from a small factual prompt and store that thought privately instead of sending the old bulky cycle through lived memory. That is the first structural step from "a tool waits" toward "Maez continues."
