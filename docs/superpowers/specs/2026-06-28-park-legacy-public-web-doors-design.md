# Park Legacy Public Web Doors — Design & Covenant Brief

**Date:** 2026-06-28. **Lane:** Codex drafts/specs; Claude covenant-reviews; owner decides exposure posture. **Status:** DESIGN ONLY. **Parent context:** Slice 1 armed the WebAuthn keyhole UX but did not secure Maez. This slice reduces the legacy web attack surface on `maez-web` while keeping the owner cockpit untouched.

## The governing sentence
**Close old doors; do not remodel the house.** A "door" is any non-cockpit route that lets someone enter, talk through, write into, or read Maez. Purely cosmetic static pages are not the threat in this slice and can wait. The change is reversible parking, not deletion.

## What is true right now
- `maez-web` on port `11437` is loopback-only. This is risk reduction inside the local house, not an active internet leak fix.
- The owner cockpit is the live owner surface: `/cockpit`, `/cockpit/s7-webauthn-proof`, `/console`, `/api/v1/*`, and `/api/v1/s7/*`.
- The old public/multi-user app still exists beside it: `/login`, `/register`, `/link-telegram`, `/chat`, `/history`, old token-bound planner/analytics APIs, public status/state routes, and old journal/debug surfaces.
- `/app` is already parked to `/cockpit`; its comment explicitly says `/chat POST API is unchanged`. This slice closes the remaining old doors.

## Scope rule: classify by capability
Task 0 must classify every route in `skills/web_interface.py` before code changes. The classification is not "read-only vs write" and not "old-looking vs new-looking"; it is capability:

### KEEP
Keep verified owner/live surfaces byte-equivalent, but only after Task 0 proves the owner gate that makes them safe:
- `/cockpit`, `/cockpit/`, `/cockpit/s7-webauthn-proof`, `/cockpit/<path:filename>`
- `/console`, `/console/*`
- `/api/v1/*`, including `/api/v1/s7/*`, only if Task 0 confirms the route is covered by `_owner_private_auth_ok()`, the S7 internal-channel proxy boundary, or another explicit owner/trusted-channel proof. A prefix is not evidence; unauthenticated state-returning `/api/v1/*` is a read-door and must be parked or held for owner review.
- Any route Task 0 proves is an active local integration with its own authentication and not part of the legacy public app, for example `/api/iphone/ingest` if and only if its token semantics are verified.

### PARK
Park every legacy route that is a door:
- **Enter/account doors:** `/login`, `/register`, `/link-telegram`
- **Talk/write doors:** `/chat`, `/api/analytics`, `/api/planner-board` POST
- **Feature-flagged talk doors:** `/v1/fast-reply` if `MAEZ_LIVE_FAST_LANE_ENABLED=1` registers it; the flag-off posture must be tested, and the enabled route must be classified by capability rather than allowed to sit between namespaces.
- **Read doors:** `/history`, `/api/analytics-summary`, `/api/planner-board` GET, `/api/progress-board` if it exposes live/internal project state rather than cosmetic build-log data, `/status`, `/api/maez-state`, `/api/session-timeline`, `/journal`
- **Debug read doors:** `/debug`, `/debug/*`, `/api/debug/*` unless Task 0 proves a specific route is required by the cockpit and owner-gated independently of the old login/account surface.

### DEFER
Do not spend v0 review surface on purely cosmetic static pages unless Task 0 proves they expose real Maez state:
- `/privacy`
- `/maez.css`
- `/maez_hero.html`, `/maez_gate.html`, `/maez_bg.html`, `/maez_bg_zen.html`
- Public marketing/build-log pages like `/` and `/progress`, provided they do not fetch Maez live state except through a route that is itself parked.

`/planner` and `/analytics` are not automatically cosmetic: today they use account-token gating and old local boards. Task 0 decides whether they are PARK routes because they lead to read/write doors, or static-only shells after their APIs are parked.

## Task 0 gates the implementation plan
Before planning implementation, produce a route inventory table from live code with one row per `@app.route`:
- route and methods
- function name
- capability: cosmetic, enter, talk, write, read, debug-read, owner-cockpit, active-local-integration
- classification: KEEP, PARK, or DEFER
- evidence line: the exact code fact that justifies the classification

Mandatory Task 0 checks:
- Confirm nothing the owner cockpit uses calls old `/chat`; cockpit send must go through `/api/v1/cockpit/message`.
- Confirm `/v1/fast-reply` registration and posture. Today it is only registered behind `MAEZ_LIVE_FAST_LANE_ENABLED=1`; if enabled, it is a talk-door unless a stronger owner/trusted-channel gate is proven. If disabled, add a regression test that it remains absent.
- Confirm the owner/trusted-channel gate for every kept `/api/v1/*` route or for a shared mechanism that covers them all. Do not keep `/api/v1/*` because the namespace looks modern; routes like `/api/v1/soul`, `/api/v1/memory`, `/api/v1/lived-memory/*`, and `/api/v1/chat/sessions` are read-doors unless their owner gate is proven.
- Confirm `/api/iphone/ingest` auth and behavior. If it requires `X-Maez-Token` and only ingests iOS Shortcut signals, keep it. If not, park it or stop for owner review.
- Confirm `/api/progress-board` contents and callers. If it is only public build-log/progress data, it may be DEFER with the cosmetic pages; if it exposes internal planning state, it is a read-door and parks.
- Confirm whether `/debug` routes are reachable through old login redirection or through `_owner_private_auth_ok()`. If unauthorized debug redirects to `/login`, parking `/login` must not create confusing loops.
- Confirm old public pages that remain DEFER do not keep live links/forms to newly parked routes without an honest parked receipt.

No route may be kept on "likely." If Task 0 cannot prove a route is safe to keep, it becomes PARK or an explicit owner HOLD.

## Parking behavior
Use one small helper so parked routes are obvious and reversible:

- `GET` page routes may redirect to `/cockpit` with a short parked receipt page if the existing pattern fits.
- API and mutating routes should return `410 Gone` JSON with a clear reason, for example:

```json
{
  "error": "legacy_surface_parked",
  "message": "This legacy public Maez web surface is parked. Use /cockpit."
}
```

Do not delete account, chat, history, or planner code in v0. Leave it unreachable behind the park helper with a dated comment, matching the existing `/app` pattern.

## Tests
The tests are the load-bearing artifact:

- Public doors are unreachable:
  - `GET /login` no longer serves `login.html`.
  - `POST /register`, `POST /link-telegram`, `POST /chat`, and old token-bound write APIs return the parked response.
  - read doors such as `/history`, `/status`, `/api/maez-state`, `/api/session-timeline`, and `/journal` return the parked response and do not expose Maez state.
  - `/v1/fast-reply` remains unregistered when `MAEZ_LIVE_FAST_LANE_ENABLED` is off; if a test imports with the flag on, the route returns the parked response unless Task 0 proves it belongs to a different owner-gated surface.
- Owner cockpit stays intact:
  - `/cockpit` and `/cockpit/s7-webauthn-proof` still return 200.
  - `/api/v1/cockpit/message` and `/api/v1/s7/webauthn/status` still route through their existing behavior; tests may stub daemon/proxy calls as existing tests do.
  - kept `/api/v1/*` state routes have tests proving their owner/trusted-channel gate still blocks unauthorized access where applicable.
  - existing cockpit proxy and S7 internal-channel tests remain green.
- No stale links to parked doors from kept public pages:
  - Kept cosmetic pages must not link users to `/login`, `/register`, `/chat`, `/history`, `/journal`, or old token-bound APIs as active entry points.
- Active local integration, if kept:
  - `/api/iphone/ingest` has a dedicated test proving missing/invalid token is rejected and that the route is not part of the old account-token app.

## Witness
After merge and restart:
- `/login` and `/chat` no longer serve the old multi-user surface.
- `/status`, `/api/maez-state`, `/api/session-timeline`, and `/journal` no longer leak live Maez state.
- `/cockpit` and `/cockpit/s7-webauthn-proof` still work.
- A representative `/api/v1/*` cockpit data route still works.
- If `/api/iphone/ingest` is kept, its token rejection still works.

## Out of scope
- Exposing `11437` beyond loopback.
- Rewriting authentication.
- Deleting the old public app code.
- Changing daemon behavior, Telegram behavior, S7 authority, WebAuthn enrollment, or Maez's autonomy.
- Securing the self-soul/provenance windows. That remains the authority/provenance wall arc.

## Predicted effect
Old public web doors stop being usable entry, talk, write, or read paths into Maez. The owner cockpit and S7 WebAuthn keyhole remain usable. The system is not "secured" by this slice; it is simply smaller and easier to defend.
