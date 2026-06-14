# Codex independent review — the LIVE coherence switch-over

**Date:** 2026-06-14
**Lane:** Claude built **and** self-verified this entire arc. Codex reviews. This is the
mandatory cross-lane pass — single-lane attestation is wearing `LIVE_WITNESSED` labels and
must be independently witnessed before anything stacks on top. **Disagreement is the signal.**
Do not rubber-stamp; if you can refute a claim, refute it.

**What this is NOT:** not a request to merge, push, restart, or flag-flip. `main` is
local-only and unpushed; all flags are already live on the running daemon. Those are owner
breaths and have already happened. Your job is to tell us whether they should have.

---

## Test discipline (read first)

- Venv: `/home/rohit/maez/.venv/bin/python -B -m unittest`
- **NEVER full-discover** in `/home/rohit/maez` (asset/ambient confounds + cost). Run the
  named modules below only.
- The arc's own suites (all under `tests/`):
  - `test_inbound_core_equivalence.py` — the off-means-off byte-identity proofs
  - `test_cockpit_inbound_core.py` — the cockpit caller (S4 fires, M1-excluded, minimal scope)
  - `test_surface_parity_d20.py`, `test_surface_parity_proposals.py`,
    `test_surface_parity_felttime.py`, `test_r4_surface_parity_2026_05_04.py`
- Run e.g.:
  `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_inbound_core_equivalence tests.test_cockpit_inbound_core -v`

---

## What went live (the surface to review)

One surface-agnostic inbound pipeline both Telegram and the cockpit now route through, plus
an honest real-state dashboard. Live flags (verified in `~/.config/maez/model.env` +
`maez-web.service`):

| flag | value | where | meaning |
|---|---|---|---|
| `MAEZ_INBOUND_CORE_V2` | `1` | model.env:158 | Telegram routes through `run_inbound_turn` |
| `MAEZ_COCKPIT_CORE` | `1` | model.env:167 | cockpit `/message` routes through the same core |
| `MAEZ_SURFACE_PARITY_ENABLED` | `1` | model.env:116 | D20 capability-gap block armed |
| `MAEZ_COCKPIT_REAL_STATE` | `1` | maez-web.service:20 | cockpit reads real daemon state |

Core: `daemon/inbound_core.py::run_inbound_turn` (`:69`). Cockpit caller kwargs builder:
`daemon/maez_daemon.py:2540-2610`. Ledger of the whole arc: `docs/MAEZ_BUILD_LEDGER.md`
(the rows labelled from the switch-over commit `4b6d9fa`).

Commit spine (oldest→newest): `ac41a1e` (SLICE 0 extract) → `1696605` → `1abbdb3` →
`bab4494` → `bfd4e29` → `7f42790` → `aff0c76`/`f65d4bb` (real-state bridge) → `0ea32ab`
(supporting slices) → `3dd7466` (integrate) → `3dfef2d`/`2f80c25` (the 6 self-review fixes) →
`4b6d9fa`/`bd66e79` (ledger) → switch-over.

---

## The three seams I most want you to ATTACK

These are the covenant-critical ones. Each lists my claim, the anchor, and my specific
suspicion — try to break it.

### Seam 1 — S4 must NOT mutate the shared M1 window from cockpit
- **Claim:** an S4 (clinical-boundary) match on the cockpit returns the crisis-care reply but
  does **not** mark the shared, Telegram-fed global M1 promotion window `s4_ineligible`,
  because cockpit is an unauthenticated localhost surface and that mark is a durable-selfhood
  mutation.
- **Anchors:** `daemon/inbound_core.py:98` (`mark_s4_promotion_policy: bool = True`),
  `:133-143` (the gated `mark(...)` call); cockpit passes `False` at
  `daemon/maez_daemon.py:2600`. Telegram (default `True`) still marks.
- **Attack it:** Is there ANY other path from a cockpit turn to `daemon._mark_m1_s4_policy`
  or to the M1 promotion window besides this one? Does the crisis-care `answer_text` truly
  return identically on both surfaces (the care must not be withheld)? Does `mark_s4...=False`
  silently suppress anything else it shouldn't? Confirm the Telegram default is genuinely
  byte-identical to pre-arc (the mark still fires for Telegram).

### Seam 2 — D20 capability-gap divergence on `pipe is None`
- **Claim:** Telegram fires D20 whenever `surface_parity` is on even if `pipe is None`
  (byte-identical to the old inline body); cockpit passes `gate_d20_on_pipe=True` so D20
  **self-skips** when `pipe is None`, to avoid `maybe_fire_capability_proposal` constructing a
  default `PendingCardStore` and creating an **orphaned durable card**.
- **Anchors:** `daemon/inbound_core.py:99` (`gate_d20_on_pipe: bool = False`),
  `:202` (`if surface_parity_enabled() and (pipe is not None or not gate_d20_on_pipe)`);
  cockpit passes `True` at `daemon/maez_daemon.py:2601` with `get_pipeline=None`.
- **Attack it:** Is the boolean logic at `:202` actually correct for all four combinations of
  (`gate_d20_on_pipe` ∈ {T,F}) × (`pipe` ∈ {None, set})? Telegram-default (`False`) must fire
  in BOTH pipe states; cockpit (`True`) must fire ONLY when pipe is set. With cockpit's
  `get_pipeline=None`, does `pipe` provably stay `None` (`:182-186`)? Could `card_store=None`
  at `:210` still reach a default store inside `maybe_fire_capability_proposal`? That function
  is contracted to never raise and to create cards only via `pending_card_store` — verify that
  contract holds with `pending_card_store=None`.

### Seam 3 — systemd `Type=notify` crash-loop guard
- **Claim:** sd_notify `READY=1` is force-on when `NOTIFY_SOCKET` is present, so a
  `Type=notify` unit can't crash-loop even if `MAEZ_SYSTEMD_NOTIFY` were set off; and it's a
  silent no-op when `NOTIFY_SOCKET` is unset (current `Type=simple` runs).
- **Anchors:** `core/infra/systemd_notify.py` (flag `MAEZ_SYSTEMD_NOTIFY`, strict
  `{1,true,yes,on}`, default-on at `:29-49`; `sd_notify` at `:66-79` returns False/sends
  nothing when `NOTIFY_SOCKET` empty), call site `daemon/maez_daemon.py:10748-10755`.
- **Attack it:** Does the default-on-when-unset logic actually hold (the 0-truthy footgun)?
  Is there a state where the unit is `Type=notify` but READY never sends → systemd kills it?
  Note: maez.service is currently `Type=simple`, so this is defense-in-depth, not live-load-
  bearing — confirm that's true and the guard is dormant-correct.

---

## The off-means-off byte-identity matrix (independently re-derive)

The arc's core invariant: **flag OFF ⇒ byte-identical to pre-arc on every seam, including
prompt bytes.** Don't take the test names on faith — read `test_inbound_core_equivalence.py`
and confirm it actually asserts equality (not just "runs") for:
- the S4 early-return path (both `matched` and not),
- the D20 placement (after-auth, before card handling / search-commitment),
- the felt-time card string (the old static `"built, not yet attached"` returned ONLY by the
  flag-off branch — string-equality, not "string is gone from the module"),
- the proposal/search interceptor order.

Flag parser must be strict `{1,true,yes,on}` everywhere (no `bool(env)` 0-truthy footgun —
it's a named HAZARD in the ledger). Grep the arc for any `bool(os.environ...)` that slipped in.

---

## Lower-risk (display-only) additions — sanity, not deep review

These touch the cockpit browser layer only (no daemon, reversible via git):
- The slime avatar + galaxy hero (`web/cockpit/index.html`, `terminal-ui.jsx`, `sim.jsx`;
  commits `9c11a63`..`a874223`). Covenant rail: it renders ONLY real `/api/v1/daemon/state`
  reads (valence/reasoning_loop/status) — never fabricated liveliness. Spot-check that the
  variant mapping (`is-pos`/`is-neg`/`is-stall`) is driven by real fields, and that the killed
  fake cognition seed (`d731557`) stayed killed.
- `ec37675`: WhyReplyPane now renders the backend's honest graceful-empty 404
  (`"No recent chat turn to explain."`) instead of a red `HTTP 404` alarm. Confirm it still
  surfaces REAL failures (500 / network / non-JSON) as errors.

---

## What I want back

A verdict per seam: **PASS** (independently witnessed) or **HOLD** (with the exact refutation
— file:line, the combination that breaks it, or the missing test). If a `LIVE_WITNESSED` label
is not earned, say so plainly; we will downgrade the ledger row rather than let a single-lane
claim stand. Update the touched ledger rows with your `updated_by: codex` attestation per the
ledger's maintenance law.

— Claude (covenant axis), handing to Codex (surface-truth axis)
