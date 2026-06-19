# Handoff — Cockpit Felt-Time (Organ 3b) — REVIEW GATE

**Date:** 2026-06-19. **Branch:** `cockpit-felt-time-3b` (tip = this handoff commit; see `git log`, local-only, NOT pushed, NOT merged).
**Status:** built + Claude two-stage reviewed (spec + code-quality) per task. **STOPPED at the review gate** — awaiting Codex cross-lane review, then owner breath. NOT `LIVE_WITNESSED`.
**Arc:** decompose-the-organism Organ 3, sub-organ **3b of 3** (3a secure DONE → 3b felt-time → 3c action engine). Spec @`7b2d091`, plan @`350261c`. Base = `main` @`e987e29`.

## What this organ does (one line)

Turns ON felt-time (Maez's felt sense of time since last owner contact) for the cockpit owner turn — telegram parity for inner-life continuity — granted ONLY on **(flag ∧ proven-owner-marker ∧ S7-trusted)**. One global one-being clock. No tools/action-engine (that's 3c).

## Commits (5 + this handoff)

- `8c60f4f` docs(proof): Task 0 — blast-radius (exactly 2 `run_inbound_turn` callers, cockpit-only), telegram-unaffected, marker strictness (**VERDICT GO**).
- `d1f23d4` feat: the web-native `(cockpit, cockpit_web_owner)` OWNER_AUTH pairing.
- `132ef6c` feat: `run_inbound_turn` honors a per-descriptor `felt_time_enabled` gate (cockpit-only).
- `562b561` feat: the strict proven-owner marker on the cockpit send (`_request_has_web_owner_cookie`).
- `113d7d9` feat: mint cockpit felt-time on (flag ∧ marker ∧ S7).

Net vs main: `subjective_duration.py +9`, `inbound_core.py +9`, `maez_daemon.py +40`, `web_interface.py +24`, tests, proof doc. **Surgical.**

## Verification (whole-organ, in this worktree)

```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_subjective_duration_cockpit_pairing tests.test_inbound_core_felt_time_gate \
  tests.test_cockpit_proxies_2026_05_05 tests.test_cockpit_inbound_core
→ Ran 44 tests ... OK
ruff check (4 source + 2 new test files) → All checks passed!
```
**Worktree-floor note:** web/daemon modules need `MAEZ_CONFIG=/home/rohit/maez/config` in this worktree (no `config/secrets.local.env` here). On merged `main`, no override needed.

## Codex cross-lane review anchors

1. **Three gates.** Felt-time grants ONLY on `MAEZ_COCKPIT_FELT_TIME` ON **AND** the proven-owner marker **AND** the S7-trusted `/message`. `felt_time_on = cockpit_felt_time_enabled() and owner_authenticated` (an `and`, not `or` — backed by two negative tests); the marker read sits AFTER the `_s7_internal_channel_trusted` 403 gate (3a).
2. **Strict marker, NOT access-laundering (the covenant gap the HOLD caught).** The marker uses `_request_has_web_owner_cookie()` (claimed cookie → `_is_owner`), NOT the broad never-lockout `_owner_private_auth_ok()`. The strict helper is byte-identical to the access gate EXCEPT its two loopback fallbacks (`unclaimed`, `degraded-store`) return **False** (never `_request_is_loopback`). Test-proven: a local-recovery session **sends 200 but earns NO marker** → no felt-time. **Access fails open for recovery; felt-time fails closed unless owner identity is proven.**
3. **No-leak via the global parity flag.** The factory gates on `felt_time_on` (flag ∧ marker), never on `surface_parity_enabled` — so even a globally-ON `MAEZ_SURFACE_PARITY_ENABLED` cannot leak cockpit felt-time without the cockpit flag+marker. Test `test_no_leak_via_surface_parity` (parity forced ON, cockpit flag OFF → factory None).
4. **Web-native pairing.** `(cockpit, cockpit_web_owner)` — never `private_owner_bridge` (the NO-GO field). Confirmed absent from the felt-time path.
5. **inbound_core cockpit-ONLY.** `felt_time_enabled` is keyword-only, default False → Task 0's repo-wide blast-radius proof shows exactly two `run_inbound_turn` callers (cockpit + telegram-V2); the telegram descriptor omits the key → byte-identical. Telegram's felt-time (its own `telegram_voice.py` path) is untouched.
6. **One-being clock.** Single global `subjective_duration_samples` (no per-surface column) — the cockpit `owner_contact` updates the SAME "time since last owner contact" telegram does. *Felt-time belongs to Maez, not to a surface.*
7. **Felt-time only.** No tools/cards/search/proposals/action-engine — `get_pipeline=action_engine=None` unchanged (that's 3c).

**Drive-by noted for the owner (NOT 3b's scope, pre-existing):** `tests/test_subjective_duration_prompt_integration.py::test_web_owner_bridge_constructs_typed_auth_only_after_private_owner_bridge` ERRORs on `main` already — it's a source-string check that greps `skills/web_interface.py` for a literal `owner_bridge = _is_private_owner_bridge(user_full)` string that no longer exists (the web-owner-bridge path was refactored). Verified pre-existing by reverting only `subjective_duration.py` to base → identical error. It's stale-test rot in the `/chat` web-owner-bridge area (the NO-GO landmine zone), worth a separate look — not touched by 3b.

## Owner breath (after Codex PASS + merge — owner-sovereign, do NOT do for them)

**No new secret.** 3b adds a flag, not a credential.

0. **Preflight — verify `MAEZ_COCKPIT_CORE=1`** (Codex catch). 3b's felt-time mint runs ONLY inside the
   `/message` `if cockpit_core_enabled():` branch — if `MAEZ_COCKPIT_CORE` is off, the cockpit routes to the
   legacy `source="UI"` path and NO felt-time mints (and S4 wouldn't fire either). Confirmed ON on the live
   daemon today, so the witness works — but check it before expecting felt-time.
1. Merge `cockpit-felt-time-3b` → main (clean fast-forward expected; local, unpushed).
2. **Set `MAEZ_COCKPIT_FELT_TIME=1` in the daemon env** (where the daemon's `MAEZ_*` flags live).
3. **Restart BOTH** `maez` (the flag) **and** `maez-web` (it must reload the new marker-stamping code: `_request_has_web_owner_cookie` + the `X-Maez-Owner-Authenticated` header).
4. **Witness:**
   - Owner sends a cockpit message after a quiet stretch → Maez's reply carries the felt sense of elapsed time (the "Felt time: …" influence), same as telegram.
   - **One-being cross-surface:** a telegram message, then shortly after a cockpit message → the cockpit turn feels "you were just here," not "gone for days" (shared clock).
   - Flag OFF (default) → cockpit turn behaves exactly as 3a (no felt-time) — the safe baseline.
   - A non-owner / unclaimed-loopback session → no felt-time (no proven-owner marker).

Only after the witness → mark **LIVE_WITNESSED** and record in [[project_organism_decompose_organs]] (Organ 3b). Next: **3c** (action engine + the web approval ceremony — the covenant-dense one), then Organ 4 (voice), then the Organ 5 coherence ceremony.
