# Legacy Public Web Doors Parked - 2026-06-28

## Status

Branch: `park-legacy-public-web-doors`

Commits currently on the branch:

- `13c5f11 docs(web): classify legacy public web doors`
- `c676d1b fix(web): park legacy public maez-web doors`
- final test/docs handoff commit: see `git log --oneline -5` for the current hash. The exact hash changes whenever this handoff is corrected, so it is not self-listed here.

Stop point: review gate. Do not merge/restart until owner/Claude review clears the branch.

## Law

Park doors, not path shapes.

A door lets someone enter, talk through, write into, or read Maez. Cosmetic public pages can remain only if they do not link to, fetch, or describe parked doorways as available.

## What Changed

- Added reversible central parking for legacy public web doors in `skills/web_interface.py`.
- Parked legacy auth/talk/write/read surfaces:
  - `/login`, `/register`, `/link-telegram`, `/chat`, `/history`
  - `/journal`, `/planner`, `/analytics`
  - `/status`, `/api/maez-state`, `/api/session-timeline`
  - `/api/analytics`, `/api/analytics-summary`, `/api/planner-board`
  - `/debug`, `/debug/flow`, `/debug/flow/static`, `/debug/card-default`, `/api/debug/*`
  - `/v1/fast-reply` when the feature flag registers it
- Added owner-gate coverage for owner-private `/api/v1/*` read/write routes that Task 0 classified as HOLD/PARK, including `/api/v1/soul`, `/api/v1/memory`, lived-memory routes, card routes, S7 status, logs, dreams, workshop, and chat-session reads.
- Kept the verified owner surfaces:
  - `/cockpit`, `/cockpit/s7-webauthn-proof`, cockpit static assets
  - `/console`, `/console/last-turn`, `/console/now`, `/console/rail`
  - S7 ceremony write proxies that use the existing internal-channel proxy
  - `/api/v1/cockpit/message`
- Kept `/api/iphone/ingest` because it is token-auth iOS Shortcut ingress, not the old account app.
- Kept `/api/progress-board` because it returns `_planner_public_view(board)`, which filters to `visibility == "public"`.
- Updated kept public pages so they no longer link to parked guest/account surfaces, load `/maez_analytics.js`, fetch parked APIs, or claim the parked guest/analytics paths are live.

## Predicted Effect

After merge and `maez-web` restart:

- Visiting `/login` redirects to `/cockpit` on GET and returns `410 legacy_surface_parked` on POST.
- Calls to `/chat`, `/register`, `/link-telegram`, `/history`, `/status`, `/api/maez-state`, `/api/session-timeline`, `/api/analytics*`, `/api/planner-board`, and `/api/debug/*` return the parked response.
- Untrusted-origin POSTs to parked mutating routes still return the parked response, not the generic origin-guard response.
- `/cockpit`, `/cockpit/s7-webauthn-proof`, and `/console*` continue to serve.
- Owner-private `/api/v1/*` routes fail closed with `401 owner_auth_required` if `_owner_private_auth_ok()` is false.
- `/api/iphone/ingest` still requires `X-Maez-Token` or body `token` and strips body `token` before delegating to the iPhone ingest handler.
- `/api/progress-board` still serves only explicitly-public board items.

Plain English: the old public guest app doors are latched, the owner cockpit is left alone, and the remaining public pages stop pretending the old guest app is still open.

## Verification

RED evidence:

- `tests.test_legacy_public_web_doors_parked` initially failed before implementation with parked routes still live, `/api/v1/*` state routes ungated, and kept pages still pointing at retired doors.
- Review follow-up regression `test_kept_pages_do_not_advertise_parked_guest_or_account_surfaces` failed on stale kept-page guest/account/analytics copy before the copy fix.
- Claude review found `test_fast_reply_absent_when_feature_flag_off` was non-hermetic when the owner-local fast-lane flag is enabled. It now runs in an isolated subprocess with `MAEZ_LIVE_FAST_LANE_ENABLED=0`, while the sibling test still proves `MAEZ_LIVE_FAST_LANE_ENABLED=1` parks `/v1/fast-reply`.

GREEN evidence:

```bash
cd /home/rohit/.config/superpowers/worktrees/maez/park-legacy-public-web-doors
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_legacy_public_web_doors_parked \
  tests.test_app_parked_redirect \
  tests.test_cockpit_proxies_2026_05_05 \
  tests.test_s7_1_daemon_internal_channel \
  tests.test_s7_webauthn_enrollment_asset_boundary
```

Result: `Ran 96 tests in 1.710s - OK`.

```bash
/home/rohit/maez/.venv/bin/ruff check \
  skills/web_interface.py \
  tests/test_legacy_public_web_doors_parked.py
```

Result: `All checks passed!`

```bash
MAEZ_LIVE_FAST_LANE_ENABLED=1 \
  /home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_legacy_public_web_doors_parked.LegacyDoorParkingTests.test_fast_reply_absent_when_feature_flag_off
```

Result: `Ran 1 test - OK`; the off assertion is hermetic even when the parent process has the flag on.

```bash
git diff --check 13c5f11..HEAD
```

Result: no whitespace errors.

Independent code review:

- No Critical or Important findings.
- Minor stale public copy finding was fixed before this handoff.

## Known Non-Goals

- This does not expose or secure port `11437`; the port remains loopback-only. This slice only reduces local/public web attack surface before any future exposure.
- This does not enroll the S7 YubiKey or change authority semantics.
- This does not touch the daemon, Maez voice, routing, salience, memory stores, or birth gates.
- Cosmetic static pages that do not read/write Maez are deferred unless they linked to parked doors.

## Post-Merge Witness

If review clears and the branch is merged:

1. Restart `maez-web.service`.
2. Confirm `/login` GET redirects to `/cockpit`.
3. Confirm `/chat` POST returns `410 legacy_surface_parked`.
4. Confirm `/cockpit` and `/cockpit/s7-webauthn-proof` still serve.
5. Confirm `/api/progress-board` still omits private board items.
6. Confirm `/api/iphone/ingest` still fails without token and reaches the ingest handler with a valid token.
