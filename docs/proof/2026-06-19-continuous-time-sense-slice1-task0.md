# Task 0 — continuous-time-sense slice1 — HARD PROOF GATE

**Date:** 2026-06-19
**Branch:** `continuous-time-sense-slice1` (base main @911083b)
**Scope:** DOCS/PROOF ONLY. No behavior code changed; no `.py` touched.
**Plan under proof:** `docs/slices/.../2026-06-19-continuous-lived-time-sense-slice1.md` (T1 `compute_version` col + `replay_felt_value()`, T2 read-only `peek()`, T3 flag-gated daemon heartbeat + sparse anchors, T4 `perception_line()`→`peek()`).

Purpose: prove the slice is safe and that the spec's elapsed-vs-felt separation + replay design are faithful to the live code, BEFORE any code.

---

## (a) Consumer inventory (REPO-WIDE)

Grep run across `daemon/ skills/ core/ web/ tests/ scripts/ ui/`:

```
grep -rn "SubjectiveDuration\|subjective_duration\|perception_line\|subjective_duration_prompt_line\|record_salience_event\|Felt time"
```

### `perception_line()` — EVERY caller (repo-wide), classified

| Call site | Prod/Test |
|---|---|
| `core/evolution/subjective_duration.py:583` | **definition** (method) |
| `tests/test_subjective_duration.py:89,90,91,144,408` | TEST |
| `tests/test_subjective_duration_static_boundaries.py:128` | TEST (boundary allow-list) |

**CONFIRMED: `perception_line()` is PROD-UNUSED.** No caller in `daemon/`, `skills/`, `web/`, `scripts/`, `ui/`. The live owner reply path is `subjective_duration_prompt_line()` → `current()`, wired at:
- `daemon/maez_daemon.py:5650-5654` (handle_message)
- `skills/telegram_voice.py:2972-2974` (telegram)
- `skills/web_interface.py:6409-6411` (web /chat owner bridge)

T4 (`perception_line()`→`peek()`, adding a `now_utc` kwarg) therefore changes **only a prod-dead method** consumed solely by tests. **No production positional-arg caller exists that a new `now_utc` kwarg could break** — and T4 adds it keyword-only (`*`) anyway. No FLAG.

### `record_salience_event` call sites (must stay UNCHANGED)

Production:
- `skills/telegram_voice.py:2967`
- `daemon/maez_daemon.py:5447`
- `skills/web_interface.py:6331`
- `core/evolution/drive_driven_curiosity.py:1218`
- definition `core/evolution/subjective_duration.py:590`; internal self-call `:834`

Tests/scratch: `tests/test_subjective_duration*.py`, `tests/test_encounter_producers.py`, `tests/test_charter_floor.py`, `tests/test_curiosity_producer_ceremony.py`, `scripts/scratch_e2e_canary.py`.

Plan touches NONE of these. Slice 1 only appends `compute_version` to `current()`'s INSERT and factors a read-only `_compute`; the salience-event writer is orthogonal.

---

## (b) Elapsed-vs-felt confirm

Read `current()` (`core/evolution/subjective_duration.py:519-560`):

- **`delta_hours` (`:528`)** = `max(0.0, (now - prior_ts).total_seconds() / 3600.0)` — **exact wall-clock subtraction** of two aware UTC datetimes. Pure arithmetic on real clock instants; no temperament, no curve. This is the elapsed quantity.
- **`value` (`:532-539`)** = `compute_subjective_duration_update(prior_value, delta_hours, drag_multiplier, engagement_multiplier, residual_multiplier=1.0+0.35*residual, config)` — a **DERIVED transform**, not elapsed seconds. The body (`:242-244`) is `prior + (upward - downward) * delta` with `upward`/`downward` scaled by drag/engagement/residual and a `1 - prior/10` saturation. Felt value is a function OF elapsed, not elapsed itself.

**CONFIRMED:** elapsed (exact wall-clock) and felt (derived curve output) are cleanly separated in code. The slice's no-dilation guarantee is correctly scoped to **elapsed only**; `felt_value` is legitimately a derived, replayable transform.

---

## (c) Replay-input inventory (load-bearing)

`compute_subjective_duration_update` (`:225-244`) consumes exactly six inputs. Mapping each to its capture source in `current()` (`:529-539`) and the `subjective_duration_samples` schema (`:486-496`):

| Felt-value input | Source in `current()` | Stored column? | Replay-capturable from anchor row? |
|---|---|---|---|
| `prior_value` | `latest["value"]` (`:526`) — the prior anchor's `value` | YES — `value REAL` (`:489`) | YES (read prior row) |
| `delta_hours` | `(now - prior_ts)/3600` (`:528`), from `ts_utc` | YES — `ts_utc TEXT` (`:488`) | YES (two ts) |
| `drag_multiplier` | `_temperament_modulators(...)` (`:530`) | YES — `drag_multiplier REAL` (`:491`); **stored at `:553`** | YES |
| `engagement_multiplier` | `_temperament_modulators(...)` (`:530`) | YES — `engagement_multiplier REAL` (`:492`); **stored at `:554`** | YES |
| `residual_multiplier` = `1.0 + 0.35*residual` | `residual = self._residual_resonance(now)` (`:531`) — LIVE query of salience events | the SCALAR `residual` is stored — `residual_resonance REAL` (`:493`); **stored at `:555`** | YES — replay reads the stored `residual_resonance` scalar and re-derives `1+0.35*r`; it does NOT re-run `_residual_resonance()` |
| `config` | `self.config` (curve constants) | version-stamped by `compute_version` | YES (compute_version selects the curve) |

**Key load-bearing finding — the mood-rewrite risk is AVOIDED by construction:**
`_residual_resonance(now)` (`:840-859`) and `_temperament_modulators(...)` (`:366-386`) DO read live state at original compute time. **But their OUTPUT scalars are persisted as explicit columns in the very row they produced** (`value`, `drag_multiplier`, `engagement_multiplier`, `residual_resonance`). Replay therefore reconstructs `felt_value` purely from `(prior anchor row, this anchor row, compute_version)` — it never re-queries live temperament or live salience events. There is **no felt-value input that would force reading live state at replay time.** No mood-rewrite hazard. No FLAG.

**CONCLUSION:** Every replay input is already an explicit stored column EXCEPT the curve-version stamp. **The ONLY missing replay field is `compute_version`** → replay needs ONE additive column, not a metadata blob.

---

## (d) Explicit-columns + additive-migration confirm

- **`metadata_json` is NOT the structured-field pattern.** Schema (`:486-496`) carries `value`, `felt_time_rate`, `drag_multiplier`, `engagement_multiplier`, `residual_resonance`, `retrospective_density` as **explicit `REAL` columns**. `metadata_json TEXT NOT NULL DEFAULT '{}'` (`:495`) and the INSERT writes the literal `"{}"` (`:557`) — it carries no structured felt fields. Codex's note holds: **the new field MUST be an explicit column**, not stuffed into `metadata_json`. No FLAG.
- **Schema is `CREATE TABLE IF NOT EXISTS` inside `_initialize` (`:482-496`).** A fresh DB gets the new column from the updated DDL; an **existing** DB does NOT (IF NOT EXISTS is a no-op on an existing table). So T1 needs an idempotent guarded `ALTER TABLE subjective_duration_samples ADD COLUMN compute_version INTEGER NOT NULL DEFAULT 1`, gated on a `PRAGMA table_info(subjective_duration_samples)` absence check (mirrors the existing `_migrate_meaningful_salience_seam(conn)` pattern called at `:517`).
- **Back-compatible:** old rows read fine and default to `compute_version = 1` (the current/v1 curve). New rows stamp the current version. Reads tolerate the default. No data rewrite, no destructive migration.

---

## (e) Flood quantify + 3b-intact

**Today's write rate (owner-contact only).** Every `current()` write is gated behind owner auth (`subjective_duration_owner_auth is not None`). The three production callers:
- `daemon/maez_daemon.py:5651` (handle_message, owner reply)
- `skills/telegram_voice.py:2972` (telegram owner)
- `skills/web_interface.py:6409` (web /chat owner bridge)

These fire **once per owner-contact turn** → a handful per day. No background/per-second writer exists today.

**Slice 1 adds:** owner-contact writes (UNCHANGED) + a coarse **~5-minute checkpoint anchor** from the daemon heartbeat. At one anchor / 5 min that is ≈ 288/day (a few hundred/day) — **NOT per-second**, NOT per-cycle. Bounded and sparse.

**3b-intact confirm.** The plan only:
1. APPENDS `compute_version` to `current()`'s INSERT column list/values, and
2. factors a read-only `_compute` that `current()` reuses (peek/replay share it).

It does NOT alter `current()`'s owner-contact mint, `subjective_duration_prompt_line()` (`:896-909`, the live `Felt time:` surface), or the 3b owner-contact gates at the three call sites. Felt-time-3b (`docs/proof/2026-06-18-cockpit-felt-time-3b-task0.md`) stays untouched. No 3b coupling. No FLAG.

---

## (f) Daemon tick site

- **Cheap watchdog zone — `daemon/maez_daemon.py:8750-8769`** (the reasoning loop top, BEFORE the doorman/cognition gate at `:8769+`). Each cycle it already does cheap bookkeeping: `observe_cycle_duration` (`:8753`) and `observe_scalars(self.temperament.current())` (`:8758`), both wrapped in try/except and pure observation. This is a valid spot for a **flag-gated `peek()` refresh that never wakes cognition** — `peek()` is read-only (T2), and the zone is explicitly the pre-cognition cheap-observe band. The existing `temperament.current()` call here proves cheap reads already run per-cycle without triggering a cognition turn. CONFIRMED.
- **Flag pattern to mirror — `cockpit_core_enabled()` / `strict_env_flag` (`daemon/maez_daemon.py:2579-2588`).** Strict on/off parser via `core.infra.env_flags.strict_env_flag`, DEFAULT OFF, "0"/false/no/off/empty/unset → False. The new `MAEZ_CONTINUOUS_TIME_SENSE` flag should mirror this exactly so flag-off is byte-identical to today. CONFIRMED.

---

## Refutation check

- felt-value input not capturable in an anchor → **NONE** (all six map to stored columns + compute_version; live readers' outputs are persisted scalars).
- a production `perception_line()` caller → **NONE** (prod-unused; tests only).
- `metadata_json` being the real structured pattern → **NO** (explicit REAL/INTEGER columns; metadata_json is literal `'{}'`).
- a 3b coupling → **NONE** (plan appends a column + factors a read-only compute; 3b surfaces and gates untouched).

Nothing refutes the plan.

---

## TASK 0 VERDICT: GO
