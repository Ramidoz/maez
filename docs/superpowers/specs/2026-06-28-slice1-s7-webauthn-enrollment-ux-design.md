# Slice 1 — S7 WebAuthn Enrollment UX — Design & Covenant Brief

**Date:** 2026-06-28. **Lane:** Claude drafts + covenant-reviews; Codex co-reviews; owner performs the ceremony. **Status:** DESIGN ONLY. **Parent:** [authority-model-provenance-firewall design](2026-06-28-authority-model-provenance-firewall-design.md) — this is **Slice 1 of 6**. **Origin:** the S7.1 WebAuthn lock is built but **unarmed** — one bootstrap intent expired 2026-06-13, `0` founder credentials. The backend routes exist; there is no cockpit UX to drive the browser key-tap, which is exactly why it stalled.

## The governing sentence (the law of this slice)
**Build the keyhole and let the owner cut the first key. Do not remodel the house.** This slice arms enrollment/approval UX and **changes no Maez autonomy** — it touches no soul/body/constitution permission and introduces no new authority semantics. The provenance wall (Slice 4) is *not* part of this; until it exists, the authority model is not "secured." This slice locks the front door; it does not close the windows.

## Verified seams (2026-06-28 grep — bind to these, not to memory)
- **Routes** (daemon Flask app, [maez_daemon.py:11163-11230](../../../daemon/maez_daemon.py)): `GET /internal/s7/webauthn/status`, `POST /internal/s7/webauthn/register/begin`, `POST /internal/s7/webauthn/register/finish` (+ `register/backup-card`). Serviced by `S7LocalWebAuthnCeremonyService` + `S7ProductionWebAuthnVerifier` + `S7WebAuthnBootstrapStore`.
- **Ceremony flag:** `live_webauthn_ceremony_enabled()` ([operator_user_boundary.py:652](../../../core/governance/operator_user_boundary.py)). When OFF, `begin`/`finish` return **503** (`s7_ceremony_deferred_response`). `status` is always available.
- **Channel trust + the proxy boundary (CRITICAL — the browser must NEVER hold the token):** the daemon `/internal/...` routes require `_s7_internal_channel_trusted(req)` ([maez_daemon.py:312](../../../daemon/maez_daemon.py)) — a matching token in the `X-Maez-S7-Internal-Channel` header (`S7_INTERNAL_CHANNEL_HEADER`, [maez_daemon.py:285](../../../daemon/maez_daemon.py)), drawn from `S7_INTERNAL_CHANNEL_TOKEN`. The **safe pattern is already implemented**: the browser calls the public proxy `/api/v1/s7/webauthn/...`; the **server-side** proxy `_s7_cockpit_proxy_to_daemon` ([web_interface.py:1872](../../../skills/web_interface.py)) reads the token from env and injects the header when forwarding to the daemon `/internal/...`. **Token stays server-side; the browser only presses the doorbell.**
- **The enrollment flow already substantially EXISTS** in `skills/web_interface.py`: front-end JS (`jsonFetch("/api/v1/s7/webauthn/status" | "/register/begin" | "/register/finish")`, [web_interface.py:1331-1377](../../../skills/web_interface.py)) **and** the `/api/v1/...` proxy routes (gated by `live_webauthn_ceremony_enabled()`, 503 when off). The Origin-not-forwarded / token-server-side boundary is **already tested** (`tests/test_s7_1_daemon_internal_channel.py`, `tests/test_cockpit_proxies_2026_05_05.py`). So Slice 1 **completes/hardens an existing flow — it does not build a page from scratch.**
- **Pre-auth on begin:** `_s7_backup_registration_authorization(...)` runs before `register_begin` and can refuse.
- **Bootstrap intent CLI:** `python -m core.governance.s7_webauthn_bootstrap create --purpose register_primary --ttl-minutes N` → prints `intent_id` + a one-time bearer `token` (an "S7 L1" secret, terminal-visible).
- **Store:** `memory/s7_1_webauthn/ceremony.sqlite3` — `s7_founder_webauthn_credentials` is the table that goes from 0→1 when enrollment succeeds.

## The enrollment flow (what the slice enables, end to end)
1. **Owner** mints a fresh bootstrap intent via the CLI (the old one expired) → `intent_id` + token.
2. **Owner** ensures `live_webauthn_ceremony_enabled()` is on and `S7_INTERNAL_CHANNEL_TOKEN` is provisioned **in the proxy's env** (never the browser).
3. **Browser UI** calls the proxy `/api/v1/s7/webauthn/register/begin`; the **server-side proxy** adds the channel header and forwards to the daemon → returns the WebAuthn `PublicKeyCredentialCreationOptions`.
4. **Browser** `navigator.credentials.create(options)` → **owner touches the YubiKey** → attestation.
5. **Cockpit page** posts the attestation to `register/finish` → founder credential persisted.
6. **`status`** now reports a credential enrolled → **the gate is armed.**

Steps 1, 2, 4 are **owner-only ceremony** (CLI, flag, physical key). Step 3/5 UI is the build. The slice produces the keyhole; the owner cuts the key.

## What gets built (complete + harden the EXISTING flow — do not rebuild)
Task 0 first establishes *why the existing `web_interface.py` flow never reached 0→1* (flag off? expired intent? a broken base64url↔ArrayBuffer conversion? a missing receipt?). Then, only what's missing:
- **Finish/clean the enrollment view** in `skills/web_interface.py`: render every S7 status as a distinct state (no credential / enrolled / ceremony-disabled-503 / channel-untrusted-403 / intent-expired), run the standard WebAuthn `create()` ceremony against the **proxy** `/api/v1/...` routes (never `/internal/...`), and present **clear success/failure receipts** (enrolled ✓ with credential ref, or the precise failure cause incl. user-cancelled).
- **A thin enrollment-readiness surface** so the owner sees *which* precondition is missing (flag on? unexpired intent? credential already enrolled?) instead of a raw 503/403.
- **The credential-boundary hard test (Codex must-fix):** an automated test asserting **no frontend asset contains `S7_INTERNAL_CHANNEL_TOKEN`, `X-Maez-S7-Internal-Channel`, or any channel token written to JS/`localStorage`/`sessionStorage`.** The token lives only in the proxy's server-side env. This guards the boundary as the UI is polished.
- **No backend authority change.** Reuse the daemon routes, the proxy, the ceremony service, the verifier, the store, the flag, and the channel-trust check **exactly as they are.**

## Scope
**IN:** the cockpit enrollment view + receipts; a read-only readiness/status surface; wiring to the existing routes; tests for the view's state-rendering and the readiness logic; a documented owner runbook for the CLI + flag + key-tap.
**OUT (named):** any change to soul/body/constitution permissions; any new authority semantics or gate; the provenance wall (Slice 4); the body-modification proposal UX (Slice 5); the amendment ledger (Slice 3); the soul/constitution split (Slice 2). **No new env flags that grant authority.** Backup-card enrollment may be deferred to a follow-up unless trivially free.

## Task 0 (gates the plan — no ghost substrate)
Before the implementation plan is written, pin the **exact** contracts in live code:
- **(a) Why the existing flow stalled** — run/trace the `web_interface.py` enrollment path against the daemon and identify the actual blocker(s): ceremony flag off, expired intent, a broken base64url↔ArrayBuffer conversion, a missing receipt, or just never-driven. This determines how small the slice really is.
- **(b) The WebAuthn JSON + browser conversion** — the shapes `register_begin`/`register_finish` emit/expect, **and** the browser-side conversion: backend returns **base64url** strings for `challenge` and `user.id`; the frontend must decode them to `ArrayBuffer` for `navigator.credentials.create()`, then serialize the attestation (`id`, `rawId`, `response.{clientDataJSON,attestationObject}`, `type`) back into the exact JSON `register_finish` expects. (Codex must-fix — this conversion is a common silent-failure point and a likely stall cause.)
- **(c) The proxy boundary** — confirm the browser path is `/api/v1/...` only, that `_s7_cockpit_proxy_to_daemon` adds `X-Maez-S7-Internal-Channel` from `S7_INTERNAL_CHANNEL_TOKEN` **server-side**, and that no frontend asset references the token (baseline for the hard test).
- **(d) Pre-auth** — what `_s7_backup_registration_authorization` requires for a *primary* registration.

Anything not confirmed in code is replaced or removed before planning.

## Covenant compliance
- **Arms the key, changes no autonomy** — the load-bearing property; this slice cannot alter what Maez may do to itself.
- **S7 human-gates preserved** ([[feedback_s7_trust_is_human_gated_by_design]]) — enrollment still requires the owner's physical key, the ceremony flag, and the trusted channel; the agent stays structurally locked out. The UX makes the *owner's* path convenient; it does not widen *Maez's*.
- **Honest receipts** ([[feedback_visible_substrate_state_not_chain_of_thought]]) — every state (enrolled / each failure mode) is shown truthfully; no "success" unless the store actually went 0→1.
- **The internal master token never reaches the browser** ([[feedback_brain_is_one_part_tool_calling_substrate_side]] / credential-boundary discipline) — the page presses the doorbell; the trusted server-side proxy carries the secret. Pinned by the hard test. A leaked channel token would let any malicious page or XSS reach the daemon's S7 routes — the exact remote-compromise this whole arc defends against.
- **Convenience is a safety property** — a gate too painful to use gets bypassed; an easy key-tap is what keeps the gate in place.

## Witness
Enrollment succeeds when `s7_founder_webauthn_credentials` goes **0 → 1** and `status` reports the credential, after a real key-tap; and when each failure path (ceremony-off, channel-untrusted, expired intent, rejected/cancelled attestation) renders its correct, distinct receipt. That transition — witnessed live, by the owner's own key — is the proof the keyhole works.

## Predicted effect
The owner can, from the cockpit, see S7's true state and complete founder-credential enrollment with a single key-tap — arming a lock that has sat unarmed since June 13 — while nothing about Maez's permissions, autonomy, or self changes. The door gets its first working key; the house is untouched.
