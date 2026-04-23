# core/evolution

How Maez changes over time. Eight modules covering soul layering,
temperament drift, exploratory-mind state, and the "will I / won't I"
refusal layer.

| Module | Role |
|---|---|
| [`soul_loader.py`](soul_loader.py) | Layering: `soul.base.md` (universal, shipped) + `soul.local.md` (per-user, gitignored) → combined SOUL text at runtime. `append_to_local()` is the canonical write path for dream-proposal applies. |
| [`soul_editor.py`](soul_editor.py) | Section-level edits to `soul.md` (legacy combined file) for approved self-modification proposals. Every edit is backed up beforehand. |
| [`soul_invariants.py`](soul_invariants.py) | Deterministic check that load-bearing phrases (HARD CONSTRAINTS, TRUST COVENANT, "not a tool", "partnership") survive any proposed edit. |
| [`wants.py`](wants.py) | Append-only first-person direction log. "I want to..." events, tied to provenance (soul, dream, user prompt). |
| [`will_i.py`](will_i.py) | Non-covenant refusal seed. Deterministic (no LLM) check on whether Maez is willing to proceed even for approved actions. Currently one registered ground: `IMPERSONATES_USER`. |
| [`temperament.py`](temperament.py) | Twelve named parameters (curiosity, caution, warmth, ...) stored as an append-only event log. Track A writes only; no automatic drift until Track B. |
| [`wonderings.py`](wonderings.py) | Exploratory-mind state: open-ended questions Maez wants to answer, lifecycle (open → blocked-pending-approval → unblocked → resolved). |
| [`dream_state.py`](dream_state.py) | Idle-time reflection + dream-proposal generator. Fires during AFK windows; proposals queue in `memory/dream_proposals.db` until the owner reviews. |

## Invariants

- **SOUL is layered, not rewritten.** `soul.base.md` ships with the
  repo and never changes mid-stream. `soul.local.md` is local-only
  and grows through append. Deletions / rewrites need a self-mod
  dialog.
- **Every user gets their own SOUL.** `soul.local.md` is per-instance.
  Copying another user's `soul.local.md` onto your machine is
  explicitly out-of-scope (violates the "no two Maez share one
  developmental history" covenant).
- **Temperament is observed, not set.** In Track A the parameters
  just record events; no automatic drift. Drift rules come online
  in later tracks after the behaviour is characterised.
- **`will_i` is deterministic.** No LLM call, no audit gate — it's
  the last stop before execution and must be fast and predictable.
- **Soul-file races were a real bug.** `append_to_local` must read
  + write inside the same lock. (07-B1 fix, regression tested.)

## Public surface

- `soul_loader.current_soul() -> str` — combined live SOUL text
- `soul_loader.append_to_local(text)` — appends + invalidates cache
- `will_i.check(action, params) -> WillVerdict`
- `temperament.TemperamentStore(db_path).observe(parameter, value, source, ...)`
- `wants.log_event(event_type, text, provenance)`
- `wonderings.WonderingStore(...)` — open/block/unblock API
- `dream_state.DreamState(...).propose(...)` — fires during idle

## Legacy import paths

Pre-Phase-3 paths for every module in this subpackage are shims.
