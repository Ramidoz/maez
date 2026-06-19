# Cockpit Felt-Time 3b — Task 0 (HARD PROOF GATE)

**Slice:** cockpit-felt-time-3b · **Organ:** 3b — felt-time for the cockpit owner turn
**Branch:** `cockpit-felt-time-3b` (base main @350261c) · **Date:** 2026-06-19
**Nature:** DOCS/PROOF ONLY. No behavior code changed. Proves the planned build is safe BEFORE any `.py` edit.

## The planned build (what Task 0 must clear)

Organ 3b grants felt-time to the cockpit owner turn ONLY on
`(MAEZ_COCKPIT_FELT_TIME flag ON) AND (proven-owner marker) AND (S7-trusted call)`. The build will:

1. Add a `cockpit` OWNER_AUTH pairing (`"cockpit"` surface, `"cockpit_web_owner"` proof) to `core/evolution/subjective_duration.py`.
2. Add `felt_time_enabled: bool = False` to `run_inbound_turn` and change its felt-time gate from `if surface_parity_enabled():` to `if surface_parity_enabled() or felt_time_enabled:`.
3. Add a STRICT `_request_has_web_owner_cookie()` in `skills/web_interface.py` (NOT the broad access gate) that stamps an `X-Maez-Owner-Authenticated` marker.
4. Mint cockpit felt-time only when (flag AND marker).

---

## (a) BLAST-RADIUS (repo-wide) — the `run_inbound_turn` call-gate change is cockpit-ONLY

Repo-wide grep (`daemon/ skills/ core/ tests/ ui/ web/ scripts/`):

```
$ grep -rn "run_inbound_turn(\|owner_auth_factory\|felt_time_enabled\|surface_parity_enabled" daemon/ skills/ core/ tests/ ui/ web/ scripts/
daemon/inbound_core.py:69:async def run_inbound_turn(
daemon/inbound_core.py:202:    if surface_parity_enabled() and (pipe is not None or not gate_d20_on_pipe):
daemon/inbound_core.py:418:        if surface_parity_enabled():
daemon/inbound_core.py:420:                subjective_duration_owner_auth = owner_auth_factory()
skills/surface/maez_adapter.py:734:        def _owner_auth_factory():
skills/surface/maez_adapter.py:764:            owner_auth_factory=_owner_auth_factory,
skills/surface/maez_adapter.py:791:            return await run_inbound_turn(**self._build_inbound_descriptor(event))
daemon/maez_daemon.py:2654:        owner_auth_factory=lambda: None,
daemon/maez_daemon.py:10726:                    reply = asyncio.run(run_inbound_turn(**descriptor))
tests/test_inbound_core_equivalence.py:301-302  (test mock-patches surface_parity_enabled)
tests/test_parity_flag.py:13-29  (tests the flag helper itself)
tests/test_cockpit_inbound_core.py:89,123,173,221,223  (drives the cockpit descriptor — see (e))
```

`felt_time_enabled` does NOT yet appear anywhere (verified: `grep felt_time_enabled daemon/inbound_core.py skills/web_interface.py` → empty, exit 1). It is a brand-new kwarg.

### Every `run_inbound_turn(**...)` caller and the descriptor it passes

| # | Caller site | Descriptor builder | `owner_auth_factory` it passes | Sets `felt_time_enabled`? |
|---|-------------|--------------------|--------------------------------|---------------------------|
| 1 | `skills/surface/maez_adapter.py:791` (telegram, only under `MAEZ_INBOUND_CORE_V2`) | `_build_inbound_descriptor` (`maez_adapter.py:752`) | `_owner_auth_factory` → `SubjectiveDurationOwnerAuth(surface="telegram_owner", proof="telegram_authorized_user")` (`maez_adapter.py:734-740`) | **NO** — key absent from the dict at `:752-777` |
| 2 | `daemon/maez_daemon.py:10726` (cockpit, only under `MAEZ_COCKPIT_CORE`) | `_build_cockpit_inbound_descriptor` (`maez_daemon.py:2595`) | `owner_auth_factory=lambda: None` (`maez_daemon.py:2654`) | **NO today** — this is the ONE builder Organ 3b will modify to conditionally set it |

There are exactly **two** `run_inbound_turn(**...)` call sites in the whole repo (telegram-V2 and cockpit). No `scripts/`, `ui/`, or `web/` caller exists.

### Conclusion — cockpit-only

`felt_time_enabled: bool = False` (default False) plus `or felt_time_enabled` in the gate at `daemon/inbound_core.py:418` changes behavior for ONLY the cockpit descriptor, because:

- The gate at `:418` controls whether `owner_auth_factory()` is even called (`:420`). With `felt_time_enabled` defaulting False, the gate's truth value is byte-identical to today for any caller that omits the key.
- **Telegram (caller 1)** omits the key → default False → gate value = `surface_parity_enabled()` exactly as today → its `_owner_auth_factory()` path is byte-identical.
- **Cockpit (caller 2)** is the ONLY builder the plan touches. Today it passes `lambda: None`; 3b will set `felt_time_enabled` (and a real factory) ONLY when flag+marker hold.
- No other caller exists to be affected. **REFUTATION CHECK PASSED:** no non-cockpit `run_inbound_turn` caller sets `felt_time_enabled`.

---

## (b) TELEGRAM-UNAFFECTED

Telegram mints felt-time in its OWN path, independent of the cockpit gate:

- **Legacy path** (`skills/telegram_voice.py:2957`): `SubjectiveDurationOwnerAuth(surface="telegram_owner", proof="telegram_authorized_user")`, constructed inline in `_handle_message` after `_is_authorized`. This does not touch `run_inbound_turn` at all.
- **V2 path** (`MAEZ_INBOUND_CORE_V2` ON, `skills/surface/maez_adapter.py:791`): routes through `run_inbound_turn`, with its descriptor's `owner_auth_factory=_owner_auth_factory` (`:764`) returning the same `telegram_owner`/`telegram_authorized_user` auth (`:734-740`).

Telegram's V2 descriptor (`_build_inbound_descriptor`, `:752-777`) does **NOT** set `felt_time_enabled`. So under V2, telegram's felt-time is governed entirely by `surface_parity_enabled()` (the gate's first disjunct) exactly as today — the new `or felt_time_enabled` disjunct is always False for telegram. Telegram's felt-time is therefore unaffected by 3b on **either** path.

**Telegram descriptor `owner_auth_factory`:** `_owner_auth_factory` → `SubjectiveDurationOwnerAuth(surface="telegram_owner", proof="telegram_authorized_user")` (`maez_adapter.py:734-740`).

**REFUTATION CHECK PASSED:** no telegram routing exists that 3b would change.

---

## (c) MARKER STRICTNESS (load-bearing)

`_owner_private_auth_ok` (`skills/web_interface.py:9783-9801`) — the existing BROAD access gate — has THREE True-returning paths:

```python
def _owner_private_auth_ok() -> bool:
    try:
        if not accounts.owner_claimed():
            return _request_is_loopback()          # PATH 2: unclaimed + loopback -> True (:9789-9790)
        token = (request.cookies.get(AUTH_COOKIE, "") or "").strip()
        if not token:
            return False
        user = accounts.get_by_token(token)
        if not user:
            return False
        record = accounts.get_user_record(user.get("uuid", "")) or {}
        return _is_owner(record)                    # PATH 1: claimed + cookie -> _is_owner (:9798)
    except Exception as exc:
        logger.warning("owner gate degraded ...", exc_info=True)
        return _request_is_loopback()               # PATH 3: degraded-store + loopback -> True (:9799-9801)
```

1. **PATH 1 — claimed + cookie → `_is_owner(record)`** (`:9798`): the COOKIE-resolved owner identity. This is the ONLY path that proves a specific owner identity.
2. **PATH 2 — unclaimed + loopback** (`:9789-9790`): returns `_request_is_loopback()` — True for ANY local process, NO owner identity (local-recovery affordance).
3. **PATH 3 — degraded-store + loopback** (`:9799-9801`): on account-store exception, returns `_request_is_loopback()` — again True for ANY local process, NO owner identity.

### Why the new STRICT helper must return False on the two loopback paths

Felt-time is a **durable selfhood mutation** (it writes to the one-being clock — see (f)). It must be minted only on **proven owner identity**, never on mere local presence. PATH 2 and PATH 3 return True for any loopback caller with **no owner-identity proof** — exactly the unauthenticated-localhost case the SLICE 2 covenant already refuses to let mutate selfhood (`mark_s4_promotion_policy=False`, the M1 exclusion).

Therefore the NEW `_request_has_web_owner_cookie()` must:

- Return **True** ONLY on the equivalent of PATH 1 (claimed + valid cookie resolving to `_is_owner`).
- Return **False** on the PATH 2 and PATH 3 loopback branches — i.e. False exactly where `_owner_private_auth_ok` returns True-via-loopback. It must NOT call `_request_is_loopback()` as a fallback. A claimed-but-no-cookie, no-cookie, or unclaimed request must yield False; a store exception must fail closed to False (not loopback).

This makes the marker strictly narrower than the access gate: the access gate may admit a local recovery session, but felt-time is granted only to a cookie-proven owner.

### Imports/symbols the strict helper needs — all already present in `skills/web_interface.py`

- `accounts` — module-level `accounts = UserAccounts()` (`web_interface.py:61`). Its methods:
  - `accounts.owner_claimed` — `UserAccounts.owner_claimed` (`skills/user_accounts.py:226`)
  - `accounts.get_by_token` — (`skills/user_accounts.py:174`)
  - `accounts.get_user_record` — (`skills/user_accounts.py:300`)
- `AUTH_COOKIE = "maez_token"` (`web_interface.py:99`)
- `_is_owner(user_record)` (`web_interface.py:152`)
- (`_request_is_loopback` exists at `web_interface.py:160` — and the strict helper must deliberately NOT use it as a fallback.)

All five are already defined/imported in `skills/web_interface.py`. **No missing import.**

---

## (d) OWNER_AUTH validation

`core/evolution/subjective_duration.py:37-70`:

```python
OWNER_AUTH_SURFACES = frozenset({"daemon_owner", "telegram_owner", "web_owner_bridge", "manual_test"})
OWNER_AUTH_PROOFS = frozenset({"daemon_reviewed_owner_auth", "telegram_authorized_user",
                               "web_private_owner_bridge", "manual_test"})
OWNER_AUTH_PAIRINGS = {
    "daemon_owner": "daemon_reviewed_owner_auth",
    "telegram_owner": "telegram_authorized_user",
    "web_owner_bridge": "web_private_owner_bridge",
    "manual_test": "manual_test",
}
# __post_init__ raises on: unknown surface / unknown proof / PAIRINGS[surface] != proof
```

The planned additions: `"cockpit"` → SURFACES, `"cockpit_web_owner"` → PROOFS, `"cockpit": "cockpit_web_owner"` → PAIRINGS (+ both `Literal[...]` hints on the dataclass fields).

Validation replayed empirically against the live `__post_init__` logic (without editing the `.py`):

```
$ .venv/bin/python -c "...replay __post_init__ with proposed additions..."
cockpit/cockpit_web_owner ->                          PASS
cockpit/telegram_authorized_user (mismatch) ->        reject:mismatch
telegram_owner/telegram_authorized_user (existing) -> PASS
current class validates existing pair:                telegram_owner telegram_authorized_user
```

So `SubjectiveDurationOwnerAuth(surface="cockpit", proof="cockpit_web_owner")` will pass `__post_init__`, and a mismatched pair (e.g. `cockpit`/`telegram_authorized_user`) still raises `ValueError`.

**`private_owner_bridge` is NOT read by the felt-time machinery.** `grep private_owner_bridge core/evolution/subjective_duration.py` returns ONLY the unrelated `web_private_owner_bridge` **proof string** (`:42`, `:49`, `:60`) — the proof half of the existing `web_owner_bridge` pairing. There is no `private_owner_bridge` owner-identity lookup in the felt-time code; owner identity for cockpit will come from the (c) marker, not from any bridge symbol.

---

## (e) EXISTING-TEST inventory

`tests/test_cockpit_inbound_core.py:221`:

```python
self.assertIsNone(descriptor["owner_auth_factory"]())
```

This assertion is inside `test_cockpit_routes_through_core_when_on` (`:201`), which sets ONLY `MAEZ_COCKPIT_CORE=1` (`:212`) — it does **NOT** set `MAEZ_COCKPIT_FELT_TIME`. The planned `_build_cockpit_inbound_descriptor` gains an `owner_authenticated` kwarg defaulting False, and only mints a non-None factory when (flag ON AND marker). With the flag unset in this test and `owner_authenticated` defaulting False, the factory stays `lambda: None` → `descriptor["owner_auth_factory"]()` returns `None` → **the assertion does NOT break.**

**Every other test touching the cockpit descriptor shape** (`grep` over `tests/`, excluding the equivalence harness):

| Test (`tests/test_cockpit_inbound_core.py`) | What it asserts on the descriptor | Broken by `owner_authenticated` kwarg / `felt_time_enabled` key? |
|---|---|---|
| `:120` `mark_s4_promotion_policy` | `descriptor["mark_s4_promotion_policy"]` is False | No — unrelated key |
| `:218` | `descriptor["owner_surface_label"] == "cockpit"` | No |
| `:219` | `descriptor["get_pipeline"] is None` | No |
| `:220` | `descriptor["action_engine"] is None` | No |
| `:221` | `descriptor["owner_auth_factory"]() is None` | No — flag unset → factory stays None (analysis above) |

No test asserts the descriptor's exact key-set / dict equality, and none passes the descriptor into a signature that would reject an unknown `felt_time_enabled` key at call time other than `run_inbound_turn` itself — which will gain `felt_time_enabled` as a real parameter. No test sets `felt_time_enabled` or `owner_authenticated`, so adding them (default False) is additive.

**REFUTATION CHECK PASSED:** no existing test is broken by the new `owner_authenticated` kwarg or `felt_time_enabled` key. The `:221` assertion specifically survives because it runs with the felt-time flag unset.

---

## (f) FLAG DEFAULT + ONE-BEING CLOCK

**Flag default OFF.** `MAEZ_COCKPIT_FELT_TIME` is unset:

```
$ grep -rn "MAEZ_COCKPIT_FELT_TIME" --include=*.py --include=*.sh --include=*.env --include=*.json .
  (no hits)
$ printenv | grep -i COCKPIT_FELT_TIME
  MAEZ_COCKPIT_FELT_TIME UNSET in env
```

The flag appears nowhere in the repo or the environment → default OFF. Felt-time stays off for cockpit until the owner explicitly arms it.

**One-being clock (single global store, NOT per-surface).** The felt-time samples table has no surface/bond column:

```sql
CREATE TABLE IF NOT EXISTS subjective_duration_samples (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc TEXT NOT NULL,
    value REAL NOT NULL,
    felt_time_rate REAL NOT NULL,
    drag_multiplier REAL NOT NULL,
    engagement_multiplier REAL NOT NULL,
    residual_resonance REAL NOT NULL,
    retrospective_density REAL NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
```

(`core/evolution/subjective_duration.py:481-491`; insert `:540`, latest-read `:804` both operate on this one table with no per-surface key.) The clock advances by wall-time delta against the single most-recent sample regardless of which surface recorded it. So when cockpit records an `owner_contact` salience event, it updates the **same** clock telegram does — one being, one felt-time, exactly as required. Cockpit becomes another mouth onto the same body's sense of duration, not a second clock.

---

## TASK 0 VERDICT: GO

All six proofs hold:

- **(a)** Exactly two `run_inbound_turn` callers exist (telegram-V2, cockpit); only the cockpit builder will set `felt_time_enabled`; `default=False` + `or felt_time_enabled` is byte-identical for every other caller. No non-cockpit caller sets the key.
- **(b)** Telegram mints felt-time in its own path on both legacy and V2; its V2 descriptor omits `felt_time_enabled` → 3b cannot change telegram's felt-time either way.
- **(c)** The strict `_request_has_web_owner_cookie()` must return False on the two loopback paths (PATH 2 `:9789-9790`, PATH 3 `:9799-9801`) where the broad access gate returns True; all required symbols (`accounts.owner_claimed`/`get_by_token`/`get_user_record`, `AUTH_COOKIE`, `_is_owner`) are already present in `skills/web_interface.py`.
- **(d)** The proposed OWNER_AUTH additions make `cockpit`/`cockpit_web_owner` pass `__post_init__` and keep mismatches raising (empirically replayed); `private_owner_bridge` is not read by felt-time (only the unrelated `web_private_owner_bridge` proof string).
- **(e)** `:221` does NOT break (flag unset → factory stays None); no other cockpit-descriptor test is broken by the additive `owner_authenticated` kwarg / `felt_time_enabled` key.
- **(f)** `MAEZ_COCKPIT_FELT_TIME` is unset (default OFF); `subjective_duration_samples` is a single global store → cockpit `owner_contact` updates the same one-being clock as telegram.

No proof refutes the plan. The build may proceed.
