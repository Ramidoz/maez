# Instrumentation debt — line numbers are a fragile callsite identity

**Status:** RECORDED, not scheduled. Owner ruling 2026-08-28: do NOT solve
during D1. Do not reopen A3 over it.

## The debt

Several frozen guards identify a callsite as `file:line`:

- `DIRECT_CALLER_INVENTORY` — `tests/test_egress_external_fetch_inventory.py`
- `production_episode_add_calls` — `tests/test_narrative_hook.py`

A line number is not an identity. It is a *position*, and position moves
whenever anything above it changes. Both guards drifted during this session
from A3 commits (`08a7040`, `41ebb53`, `c17b4cf`) that added lines to
`daemon/maez_daemon.py`, `skills/telegram_voice.py` and `cli/maez_chat.py`
without touching a single guarded callsite.

## Why this is worth naming

The failure mode is not the false alarm. It is what a false alarm *trains*.

A guard that reddens for reasons unrelated to what it guards teaches its
reader to re-freeze on sight. Do that reflexively often enough and the one
time the inventory moves because a real new mouth appeared, it gets
re-frozen too — with the same shrug and the same commit message. The guard
does not fail loudly at that point. It fails silently, having already taught
everyone that its red means nothing.

Both drifts this session were checked before re-freezing and both were pure
line-shift:

| Guard | Callsites before → after | Per-file counts | New callsite? |
|---|---|---|---|
| `DIRECT_CALLER_INVENTORY` | 14 → 14 | identical | none |
| `production_episode_add_calls` | 7 → 7 | identical | none |

That check is the thing that must not be skipped, and right now nothing
enforces it — it is a habit, not a mechanism.

## The shape of the fix (NOT to be built now)

Prefer a **structural anchor** over a position:

- file path
- enclosing symbol (qualified: `MaezDaemon._record_episode`)
- AST call identity (callee dotted name + argument arity/keywords)

Line number becomes **diagnostic only** — printed to help a human find the
callsite, never compared.

Under that scheme both drifts above would have been silent no-ops, and a
genuinely new mouth would still fail the guard. The re-freeze judgement
(count and per-file distribution unchanged) would then be mechanical rather
than remembered.

## Related

- `feedback_guard_shape_over_broad_frozen_not_curated.md` — freeze the noise,
  never curate the list. A structural anchor keeps that property; it changes
  only the *identity function*, not the membership rule.
- `feedback_cite_construct_anchors_not_line_ranges.md` — the same principle
  already applied to citations. This debt is that rule, unapplied to guards.
