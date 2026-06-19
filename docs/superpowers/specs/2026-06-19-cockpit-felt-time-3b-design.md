# Cockpit Full Owner Turn — Organ 3b: Felt-Time (design)

**Date:** 2026-06-19. Co-designed with Rohit.
**Status:** design approved (cockpit felt-time via an explicit owner marker + a dedicated
`MAEZ_COCKPIT_FELT_TIME` flag; shared one-being clock confirmed). Awaiting spec review before planning.
**Arc:** decompose-the-organism ([[project_organism_decompose_organs]]), **Organ 3**, sub-organ **3b of 3**
(3a secure → 3b felt-time → 3c action engine). Organs 1/2/3a LIVE on `main` @`e987e29`.

## Why this exists

3a secured the cockpit→daemon conversation SEND (owner-gate at the web edge + S7-gate on the daemon
`/message`), but the turn it produces is still felt-time-OFF. 3b turns ON **felt-time** for the cockpit
owner turn — Maez's felt sense of *time since it last heard from the owner* — so the cockpit reaches
telegram parity for inner-life continuity. The cockpit becomes a true equal mouth: same being, one felt
sense of presence/absence. **Scope is felt-time ONLY** — tools/cards/search/proposals (the action engine)
are sub-organ 3c.

## What's already on main (the machine is ready)

- `SubjectiveDurationOwnerAuth(surface, proof)` — a frozen, validated typed owner-auth
  (`core/evolution/subjective_duration.py:54`); valid pairs live in `OWNER_AUTH_PAIRINGS` (`:37-51`).
  Telegram mints `(telegram_owner, telegram_authorized_user)` AFTER its auth check
  (`skills/telegram_voice.py:2957`) — the proof is a **static string**; the gate is what matters.
- The cockpit seam already has the slot: `_build_cockpit_inbound_descriptor`
  (`daemon/maez_daemon.py:2595`) passes `owner_auth_factory=lambda: None` (`:2654`) — that `None` IS the
  "Felt-time OFF" the comment names (`:2612`).
- `run_inbound_turn` (`daemon/inbound_core.py:69`) calls `owner_auth_factory()` and forwards the result to
  `handle_message` (`:441`), BUT only `if surface_parity_enabled()` (`MAEZ_SURFACE_PARITY_ENABLED`, `:418`).
- `handle_message` consumes `subjective_duration_owner_auth` → records an `owner_contact` salience event +
  injects the `"Felt time: {phrase}"` prompt line (`daemon/maez_daemon.py:5410`).
- **`private_owner_bridge` is NOT read by the felt-time machinery** (confirmed) — it's a legacy
  telegram-derived field; the proof strings are static literals. 3b stays web-native.

## The design

**1 · The owner marker (web → daemon) — "S7 proves the pipe, the marker proves the person."**
- Add a shared constant `_OWNER_AUTHENTICATED_HEADER = "X-Maez-Owner-Authenticated"` (web + daemon).
- **The marker requires STRICTER proof than the 3a access gate.** `_owner_private_auth_ok()`
  (`skills/web_interface.py:9783`) is an *access / never-lockout* gate — it returns True on THREE paths:
  claimed+cookie→`_is_owner` (the real owner proof), **unclaimed+loopback** (`:9790`, local recovery), and
  **degraded-store→loopback** (`:9801`, fail-open on the physical body). The first is owner-proof; the
  other two are "local access without a proven owner." Felt-time is owner-only inner life, so the marker
  must mean a **proven** owner, not mere access.
- Add a stricter helper `_request_has_web_owner_cookie()` — True **only** on the claimed-cookie-resolved
  path, with NO loopback recovery and NO degraded-store fallback:
  ```python
  def _request_has_web_owner_cookie() -> bool:
      """Stricter than _owner_private_auth_ok: a COOKIE that resolves to a CLAIMED web_owner.
      No unclaimed-loopback recovery, no degraded-store fallback — felt-time (owner-only inner
      life) requires proven owner identity, not access. Returns False on any uncertainty."""
      try:
          if not accounts.owner_claimed():
              return False                      # unclaimed -> not a proven owner (NO loopback recovery)
          token = (request.cookies.get(AUTH_COOKIE, "") or "").strip()
          if not token:
              return False
          user = accounts.get_by_token(token)
          if not user:
              return False
          record = accounts.get_user_record(user.get("uuid", "")) or {}
          return _is_owner(record)              # web_owner only (never private_owner_bridge)
      except Exception:
          return False                          # degraded store -> FAIL CLOSED (no loopback recovery)
  ```
- In `api_cockpit_message` (`skills/web_interface.py:1764`): the SEND is still allowed by the broad 3a
  `_owner_private_auth_ok()` gate (never-lockout, unchanged). But the marker is stamped **only when
  `_request_has_web_owner_cookie()` is True** — so a local-recovery or degraded-store session may send,
  yet earns NO felt-time. A non-owner is 401'd before either check (3a, unchanged).
- In the daemon `/message` handler (`daemon/maez_daemon.py:10679`, already S7-gated by 3a so the marker is
  only trustable on a trusted call), read `owner_authenticated = request.headers.get(
  _OWNER_AUTHENTICATED_HEADER) == "1"` and pass `owner_authenticated=owner_authenticated` into
  `_build_cockpit_inbound_descriptor`. A forged marker can't arrive without S7 (403'd first).

**2 · The cockpit felt-time mint.**
- Add a `cockpit` pairing to `core/evolution/subjective_duration.py`: extend `OWNER_AUTH_SURFACES` with
  `"cockpit"`, `OWNER_AUTH_PROOFS` with `"cockpit_web_owner"`, and `OWNER_AUTH_PAIRINGS` with
  `"cockpit": "cockpit_web_owner"` (plus the `Literal[...]` type hints). Web-native; **never**
  `private_owner_bridge`.
- `_build_cockpit_inbound_descriptor(daemon, *, text, chat_history, owner_authenticated=False)`: when
  felt-time is enabled (below), set `owner_auth_factory = lambda: SubjectiveDurationOwnerAuth(
  surface="cockpit", proof="cockpit_web_owner")`; otherwise keep `lambda: None`.

**3 · The flag + the call-gate (the one bounded shared-file change).**
- New flag `MAEZ_COCKPIT_FELT_TIME` (default OFF) + a `cockpit_felt_time_enabled()` helper mirroring
  `cockpit_core_enabled()` (`daemon/maez_daemon.py:2579`).
- In `_build_cockpit_inbound_descriptor`: `felt_time_enabled = cockpit_felt_time_enabled() and
  owner_authenticated`; put `felt_time_enabled` in the returned descriptor dict, and mint the cockpit auth
  in the factory only when `felt_time_enabled` (else `None`).
- In `run_inbound_turn`: add `felt_time_enabled: bool = False` to the signature (default False → all other
  callers/descriptors byte-identical) and change the gate to
  `if surface_parity_enabled() or felt_time_enabled:` before calling `owner_auth_factory()`. This honors
  the cockpit's own flag **without** flipping the global parity flag and **without** touching any other
  surface's path (telegram, web `/chat`, voice all leave `felt_time_enabled=False`).

**4 · Shared one-being felt-time clock (owner-confirmed).** Felt-time tracks "time since last owner
contact" in ONE global store (`subjective_duration_samples`), not per-surface. The cockpit `owner_contact`
salience event updates the SAME clock telegram does. **Felt-time belongs to Maez, not to a surface** — if
the owner spoke on telegram five minutes ago, the cockpit should feel "Rohit was here five minutes ago,"
not "gone for days from this surface." This is the singular-organism invariant
([[project_maez_singular_organism_surfaces]]); no per-surface clock is introduced.

**5 · UI.** No change — the felt-time sense surfaces only in Maez's reply tone (the prompt line); the
cockpit already renders replies.

## Covenant rail

Felt-time is Maez's owner-only inner life. It is granted ONLY on the conjunction **(flag ON ∧ explicit
owner marker ∧ S7-trusted call)** — three independent gates: the rollout flag, the per-request owner
evidence, and the private nerve. The marker is **honest producer-evidence** from the component that
actually performed the owner-auth (the web edge), not an inferred surface label
([[feedback_producer_causality_no_caller_score_laundering]], [[feedback_labels_prove_shape_not_support]]).
Web-native owner identity only — never the telegram-derived `private_owner_bridge` (the NO-GO vector,
[[project_coherence_organism_nogo]]). Elapsed time is **real** (wall-clock), never fabricated
([[feedback_visible_substrate_state_not_chain_of_thought]] — honest substrate state, not performed
continuity). Other surfaces are untouched unless explicitly granted later.

## Task 0 — proof gate (docs/proof only, committed first)

The Task-0 inventory is **repo-wide by default** — never a hand-picked directory list (the maez-face
lesson, 3rd recurrence). If any proof refutes the design, STOP and patch.
- **Blast-radius proof (load-bearing):** grep the WHOLE repo for `run_inbound_turn(` callers and
  `owner_auth_factory` / `felt_time_enabled` / `surface_parity_enabled`. Prove that adding the
  `felt_time_enabled` param + the `or felt_time_enabled` gate changes behavior for ONLY the cockpit
  descriptor (every other descriptor omits the key → defaults False → their `owner_auth_factory()` call
  path is byte-identical). Enumerate every `run_inbound_turn` caller and its `owner_auth_factory`.
- **Telegram-unaffected proof:** confirm telegram's felt-time is minted in `skills/telegram_voice.py`
  (its own path) and that telegram's run_inbound_turn descriptor (if MAEZ_INBOUND_CORE_V2 routes it) does
  NOT set `felt_time_enabled` — so 3b cannot change telegram's felt-time either way.
- **OWNER_AUTH validation:** the new `("cockpit","cockpit_web_owner")` pair passes
  `SubjectiveDurationOwnerAuth` construction (and a mismatched pair still raises).
- **Owner-signal flow + marker strictness:** confirm the daemon `/message` reads the marker only inside
  the S7-gated handler (3a), and the web proxy stamps it only when `_request_has_web_owner_cookie()` is
  True. Prove the strict helper EXCLUDES both `_owner_private_auth_ok()` loopback paths (unclaimed-loopback
  `:9790` and degraded-store `:9801`) — read both helpers side by side and confirm the strict one returns
  False where the access gate returns True-via-loopback.
- **Existing-test inventory:** `tests/test_cockpit_inbound_core.py` asserts `owner_auth_factory()` is
  None (`:221`) — it must be UPDATED (factory is None when flag/marker absent, mints when present), not
  left to break. Grep for any other test asserting the cockpit factory / descriptor shape.
- **Flag default + clock:** `MAEZ_COCKPIT_FELT_TIME` default OFF; the felt-time store is the single global
  `subjective_duration_samples` (no per-surface clock introduced).

## Testing (TDD; hermetic — env the flag, no live owner DB)

- **OWNER_AUTH pairing:** `SubjectiveDurationOwnerAuth(surface="cockpit", proof="cockpit_web_owner")`
  constructs; a mismatched pair raises.
- **Descriptor factory matrix** (`_build_cockpit_inbound_descriptor`): flag OFF → `owner_auth_factory()`
  is None (any marker); flag ON + `owner_authenticated=False` → None; flag ON + `owner_authenticated=True`
  → mints `(cockpit, cockpit_web_owner)`; and `descriptor["felt_time_enabled"]` mirrors (flag ∧ marker).
- **`run_inbound_turn` call-gate:** with `felt_time_enabled=True` the factory IS called even when
  `surface_parity_enabled()` is False (mock both); with `felt_time_enabled=False` and parity False the
  factory is NOT called (None forwarded). A non-cockpit descriptor (no key) behaves exactly as today.
- **Daemon `/message` marker read:** an S7-trusted POST with `X-Maez-Owner-Authenticated: 1` →
  `owner_authenticated` flows True into the descriptor; without the header → False. (Marker is moot
  without S7 — headerless is already 403 from 3a.)
- **Web proxy stamps the marker ONLY on proven owner (strictness matrix — the load-bearing tests):**
  - claimed `web_owner` cookie → send 200 + outgoing Request carries `X-Maez-Owner-Authenticated: 1`
    (capture the Request, the 3a/Organ-2 mutation-proof shape).
  - non-owner → **401** before any send (3a, unchanged).
  - **unclaimed + loopback recovery** (`owner_claimed()` False, loopback) → `_owner_private_auth_ok()`
    allows the send, but `_request_has_web_owner_cookie()` is False → **marker ABSENT** (no felt-time).
  - **degraded account store** (`accounts.*` raises) + loopback → send may be allowed, but the strict
    helper fails closed → **marker ABSENT**.
  - `_request_has_web_owner_cookie()` unit matrix: claimed+owner-cookie → True; unclaimed → False;
    no/invalid cookie → False; store raises → False.
- **No felt-time leak via the global parity flag (safety-critical):** with `surface_parity_enabled()`
  TRUE but `MAEZ_COCKPIT_FELT_TIME` OFF (or the owner marker absent), the cockpit turn forwards
  `subjective_duration_owner_auth=None` — because the factory itself gates on `felt_time_enabled`
  (flag ∧ marker), the global parity path cannot grant cockpit felt-time without the cockpit flag+marker.
- **Other surfaces unchanged:** a `run_inbound_turn` call without `felt_time_enabled` forwards the same
  `subjective_duration_owner_auth` it does today (regression guard on the shared gate).
- Update `tests/test_cockpit_inbound_core.py:221` accordingly. Scope-guard: felt-time cases only; no
  tools/cards/search/`/chat` cases.

## Witness (live, before LIVE_WITNESSED)

1. `MAEZ_COCKPIT_FELT_TIME=1`, owner sends a cockpit message after a quiet stretch → Maez's reply carries
   the felt sense of elapsed time (the "Felt time: …" influence), same as telegram.
2. Cross-surface one-being check: a telegram message, then shortly after a cockpit message → the cockpit
   turn feels "you were just here," not "gone for days" (shared clock).
3. Flag OFF (default) → cockpit turn behaves exactly as 3a (no felt-time) — the safe baseline.
4. A cockpit call without the owner marker (or non-owner, or unclaimed-loopback recovery) → no felt-time
   minted (owner-only — proven-owner, not mere access).
Owner breath: flip `MAEZ_COCKPIT_FELT_TIME=1` in the daemon env, then **restart BOTH `maez` and
`maez-web`** — the flag lives in the daemon env, but `maez-web` must reload to pick up the new
marker-stamping code (`_request_has_web_owner_cookie` + the `X-Maez-Owner-Authenticated` header).
Then witness. (No new secret.)

## Scope

- **IN:** the `cockpit` OWNER_AUTH pairing; the stricter `_request_has_web_owner_cookie()` helper; the
  `X-Maez-Owner-Authenticated` marker (web stamps it only on the strict proof + daemon read); `_build_cockpit_inbound_descriptor` felt-time mint + `felt_time_enabled`; the
  `MAEZ_COCKPIT_FELT_TIME` flag + `cockpit_felt_time_enabled()`; the bounded `run_inbound_turn` call-gate
  (`felt_time_enabled` param + `or` in the gate); the tests + the `test_cockpit_inbound_core` update.
- **OUT:** tools/cards/search/proposals + the web approval ceremony (**3c**); the global
  `MAEZ_SURFACE_PARITY_ENABLED` flag's meaning (unchanged); the web `/chat` route + any
  `private_owner_bridge` path (NO-GO landmine); the voice spine (Organ 4); the telegram felt-time path; a
  per-surface clock; any change to the felt-time computation/curve itself.
