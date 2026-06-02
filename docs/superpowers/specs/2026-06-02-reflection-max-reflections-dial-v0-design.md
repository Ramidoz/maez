# Reflection Max-Reflections Dial v0 — Design

**Date:** 2026-06-02
**Status:** Owner-specified (design provided by owner); spec formalizes it before implementation.
**Scope (narrow, owner-set):** *Give the nightly reflection hook an honest, supported "how many reflections per night" dial, defaulting to today's behavior (3), so limited regularization can run at 1/night without a dead/misleading flag.*

---

## 1. Why (don't let convenience set metabolism shape)

The daemon reflection hook calls `run_synthesis_pass` **without** `max_reflections`, so it hard-uses the default **3/night** (`daemon/maez_daemon.py:1755-1760`). There is **no** env/config for it anywhere (`--synthesis-max` is CLI-only and never reaches the daemon path). The owner's intended limited-regularization posture is **1 reflection/night** during a 2-night observation window. Adding `MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS` to `model.env` *without wiring it* would be a dead, misleading surface (set 1, get 3 silently). So we build the real dial first — letting Maez's metabolism shape be chosen deliberately, not by the absence of a knob.

---

## 2. The change — daemon hook reads a max dial

In `daemon/maez_daemon.py`:

1. **New env helper** (mirrors the existing `_reflection_synthesis_enabled` style):

```python
def _reflection_synthesis_max_reflections(environ: object | None = None) -> int:
    env = os.environ if environ is None else environ
    raw = (env.get("MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS", "") or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 3
    return value if value >= 1 else 3
```

- **Default 3** when unset (today's behavior exactly).
- **Safe fallback to 3** on any invalid value (non-int, ≤0).

2. **Pass it through** in `_run_reflection_synthesis_nightly`'s `run_synthesis_pass(...)` call:

```python
        run_synthesis_pass(
            episode_store=getattr(daemon, "lived_episodes"),
            llm_call=llm_call,
            report=report,
            dry_run=dry_run,
            max_reflections=_reflection_synthesis_max_reflections(),
        )
```

Nothing else changes — `run_synthesis_pass` already accepts `max_reflections` (default 3); `synthesize_reflections` already caps to it.

---

## 3. Tests

- **Env reaches the hook:** with `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1` and `MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS=1`, drive `_run_reflection_synthesis_nightly` with `run_synthesis_pass` patched; assert it received `max_reflections=1`.
- **Unset keeps default:** with the max var unset (ENABLED=1), assert `run_synthesis_pass` received `max_reflections=3` — today's behavior preserved.
- (Optional, cheap) **Invalid → 3:** `MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS="abc"` or `"0"` → 3.

---

## 4. Unchanged

- `run_synthesis_pass`, `synthesize_reflections`, `persist_reflections`, the provenance stamp, the prompt (voice/fairness/grounding), input hygiene, the reasoning cap, the terminal-state/invalid-witness mechanics. This only chooses *how many* reflections a nightly run draws.

---

## 5. After the dial lands — the limited regularization (owner-run config, no restart)

`~/.config/maez/model.env` gains:

```env
MAEZ_REFLECTION_SYNTHESIS_ENABLED=1
MAEZ_REFLECTION_SYNTHESIS_WRITE=1
MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS=1
```

- **No restart** — takes effect on the next natural daemon restart.
- **2-night observation window**, 1 reflection/night.
- After the first night: resolve each new reflection's provenance (`reflection_synthesis`/`maez_self`), citations (zero `reflection` → no recursion), and fair tone (watch the "lies/lying" word-family attaching to Maez's *self*-model). If clean across the window → reflection stays a regular organ; if the word-family creeps self-ward → tighten the rail.

---

## 6. Non-goals

- NOT changing default behavior (unset = 3, exactly as today).
- NOT a restart (gentle activation).
- NOT enabling writes by code (the flags are owner-run config, §5).
- NOT a new CLI surface (the CLI already has `--synthesis-max`; this is the daemon/env path).
- NOT touching the prompt, grounding, hygiene, cap, or provenance.
