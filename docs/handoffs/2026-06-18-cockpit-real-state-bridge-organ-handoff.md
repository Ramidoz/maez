# Handoff — Cockpit Real-State Bridge (Organ 2) — REVIEW GATE

**Date:** 2026-06-18. **Branch:** `cockpit-real-state-bridge-organ` (tip `72210c0`, local-only, NOT pushed, NOT merged).
**Status:** built + Claude two-stage reviewed (spec + code-quality) per task. **STOPPED at the review gate** — awaiting Codex cross-lane review, then owner breath. NOT `LIVE_WITNESSED`.
**Arc:** decompose-the-organism Organ 2 ([[project_organism_decompose_organs]]). Spec @24a5fd9, plan @796416c.

## What this organ does (one line)

HARDENS the existing-but-exposed cockpit real-state bridge: closes the daemon's **open** `/internal/cockpit/state` with an S7 gate, **owner-gates** the web `/api/v1/daemon/state`, and makes the web proxy **actually send** the S7 token — so the daemon's live in-memory state is read only by the owner over an authenticated nerve. No rebuild; existing functions modified in place. UI unchanged.

## Commits (4)

- `0bcd39b` docs(proof): Task 0 — consumer inventory, clean separation, imports (**VERDICT GO**).
- `7f12739` feat: S7-gate the daemon `/internal/cockpit/state` (close the open nerve) [amended w/ test-mixin refactor].
- `4917422` feat: web real-state proxy sends the S7 token + honest unreachable reason.
- `72210c0` feat: owner-gate `/api/v1/daemon/state` (close the open web endpoint).

Net diff vs main: `daemon/maez_daemon.py +2`, `skills/web_interface.py +36`, two test files, one proof doc. **370 insertions, surgical.**

## Verification (whole-organ, in this worktree)

```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_s7_1_daemon_internal_channel tests.test_cockpit_real_state_bridge
→ Ran 57 tests ... OK
ruff check daemon/maez_daemon.py skills/web_interface.py tests/*  → All checks passed!
```
**Worktree-floor note** ([[feedback_worktree_floor_confound]]): this worktree lacks `config/secrets.local.env`, so importing `skills.web_interface` requires `MAEZ_CONFIG=/home/rohit/maez/config` (the asset-rich main checkout's secrets). The daemon-test module needs no such env. On main after merge, no MAEZ_CONFIG override is needed.

## Codex cross-lane review anchors

1. **HARDEN, not rebuild.** `_build_cockpit_state` (daemon) and `_daemon_cockpit_state_proxy` (web) and the `MAEZ_COCKPIT_REAL_STATE` flag-switch were MODIFIED in place — verify no duplicate definitions were created (grep: exactly one `def` each). Daemon diff is exactly `+2` lines.
2. **The open daemon nerve is closed.** `/internal/cockpit/state` now gates on `_s7_internal_channel_trusted(request)` (always-on, before `_build_cockpit_state`) → headerless / wrong-token / **valid-token+Origin** all 403. The **Origin-spoof 403 is pinned on the route** via the captured-app test-client (not just a unit test of the gate function) — spec reviewer mutation-style confirmed the token is genuinely valid in that test, so the 403 proves the no-Origin CSRF guard, not a missing token.
3. **The web proxy actually SENDS the token.** `test_proxy_sends_managed_token_header` captures the OUTGOING `urllib.request.Request` and asserts `req.get_header("X-maez-s7-internal-channel") == token` — spec reviewer ran a mutation (stripped `headers=`) and the test correctly FAILED, so a payload-only mock cannot pass with the header unsent.
4. **Flag-on + no/wrong token → honest `unreachable` + reason, NO scrape fallback.** Proxy returns `{"status":"unreachable","reason":"s7_internal_channel_untrusted"}` when the token is absent or the daemon 403s; `daemon_unreachable` when down; `daemon_error` for other HTTP. No branch returns scraped/seed/fabricated state. The endpoint test (`test_owner_flag_on_no_token_is_unreachable_no_scrape`) proves flag-on does NOT silently fall back to the log-scrape.
5. **Owner gate — NO lockout (the exact prior NO-GO).** `/api/v1/daemon/state` gates on the EXISTING #1 `_owner_private_auth_ok()` (loopback-unclaimed→OPEN, claimed+owner→ALLOW, claimed+non-owner→DENY, store-unreachable→loopback-recovers/remote-fails-closed) — the gate adds NO stricter condition, so the local loopback owner is never locked out. Non-owner/remote → 401 `owner_auth_required`. Always-on (before the flag-switch).
6. **Flag-off serves the same source SHAPE to authorized callers** — NOT byte-identical overall: the always-on owner gate intentionally 401s non-owner/remote (the security change). Flag-off owner path = the unchanged `_api_daemon_state_log_scrape()`.
7. **Clean separation.** Daemon handler + web proxy call NO web-owner-spine (`_proxy_web_owner_message_to_daemon`, `handle_message`) or voice code (Task-0 proven). Only consumer of the daemon endpoint is the web proxy; only consumer of the web endpoint is cockpit `sim.jsx` `_pollDaemon` (which already handles legacy/real/unreachable shapes — no UI change).

**Noted for Codex (not a defect, future DRY):** the web file already has a sibling `_s7_cockpit_proxy_to_daemon()` (message-direction, web-owner-spine territory) that inlines the same `X-Maez-S7-Internal-Channel` pattern; the new `_s7_internal_channel_headers()` could later consolidate it, but that's OUT of this slice's scope (it touches the web-owner spine). Left untouched deliberately.

## Owner breath (after Codex PASS + merge — owner-sovereign, do NOT do for them)

1. Merge `cockpit-real-state-bridge-organ` → main (local fast-forward; main stays unpushed).
2. **Provision the S7 token for BOTH services** — add `S7_INTERNAL_CHANNEL_TOKEN=<secret>` to **`config/secrets.local.env`** for both `maez` (daemon) and `maez-web` (NOT model.env — the secrets loader purges launch-env secrets; that was the #2 root cause). It is already a managed secret (`core/infra/secrets.py:22`).
3. Restart both `maez` (daemon) and `maez-web`.
4. **Flip `MAEZ_COCKPIT_REAL_STATE=1`** (default off keeps the legacy log-scrape).
5. **Browser-witness** (logged in as the web owner): the cockpit DaemonPane shows REAL daemon state — live `cycle_count`, `cognition.score`, `last_thought`, `valence`, `reasoning_loop` (not the reconstruction). And a headerless probe of the daemon endpoint 403s:
   `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:11435/internal/cockpit/state` → **403**.
6. Token wrong/absent while flag-on → cockpit shows honest `unreachable` (reason `s7_internal_channel_untrusted`), never a fake state.

Only after the browser witness → mark **LIVE_WITNESSED** and record in [[project_organism_decompose_organs]] (Organ 2). Next organs: web-owner shared spine → voice spine → coherence ceremony.
