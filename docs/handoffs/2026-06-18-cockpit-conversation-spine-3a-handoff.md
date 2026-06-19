# Handoff — Cockpit Conversation Spine 3a: Secure the Spine — REVIEW GATE

**Date:** 2026-06-18. **Branch:** `cockpit-conversation-spine-3a-secure` (tip = this handoff commit; see `git log`, local-only, NOT pushed, NOT merged).
**Status:** built + Claude two-stage reviewed (spec + code-quality) per task. **STOPPED at the review gate** — awaiting Codex cross-lane review, then owner breath. NOT `LIVE_WITNESSED`.
**Arc:** decompose-the-organism Organ 3, sub-organ **3a of 3** (3a secure → 3b felt-time → 3c action engine). Spec @`bf382c4`, plan @`1f9e688`. Base = merged `main` @`528d8e0` (Organ 2 LIVE).

## What this organ does (one line)

Closes a **write** hole on the existing cockpit→daemon conversation path: owner-gates the web `api_cockpit_message` send and S7-gates the daemon `/message` receive, so **only the owner browser may send, and only over the private S7 nerve**. No rebuild (Approach A — gate the shared route). No inbound-turn change (felt-time/tools are 3b/3c).

## Commits (3 + this handoff)

- `e7f8bf4` docs(proof): Task 0 — consumer inventory (Approach A), telegram in-process, Organ-2 base (**VERDICT GO**).
- `1c56b7f` feat: S7-gate the daemon `/message` route (gate before parse).
- `13c10f7` feat: owner-gate + S7-token the cockpit message send (preserve contract).

Net vs main: `daemon/maez_daemon.py +2`, `skills/web_interface.py +14`, two test files, one proof doc. **Surgical.**

## Verification (whole-organ, in this worktree)

```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_s7_1_daemon_internal_channel tests.test_cockpit_proxies_2026_05_05
→ Ran 63 tests ... OK
ruff check daemon/maez_daemon.py skills/web_interface.py tests/*  → All checks passed!
```
**Worktree-floor note:** this worktree has no `config/secrets.local.env`, so web-touching modules need `MAEZ_CONFIG=/home/rohit/maez/config`. On merged `main` (which has the file), no override is needed.

## Codex cross-lane review anchors

1. **HARDEN, not rebuild (Approach A).** Two existing functions modified in place; **no new route**. Daemon diff = exactly the 2-line gate; web diff = exactly 4 additions. Task 0 proved the cockpit proxy is the only production HTTP caller of `/message`, so gating the shared route was safe.
2. **Gate-before-parse, both sides.** Daemon: the S7 gate is the FIRST statement, before `request.get_json` — proven by `test_gate_runs_before_body_parse` (malformed body + no token → **403, never 400**; without the gate it would be the route's own 400). Web: the owner gate is the FIRST statement, before `request.get_data()` (non-owner → 401 before the body is read).
3. **The write hole is closed.** Non-owner send → **401** `owner_auth_required`; a tokenless/forged daemon `/message` POST → **403** `s7_internal_channel_untrusted`.
4. **Origin-spoof → 403 pinned on `/message`.** `test_valid_header_plus_origin_still_403` posts a GENUINELY valid token + an `Origin` header → 403 (spec reviewer confirmed the token is valid, so the 403 proves the no-Origin CSRF guard, not a missing token).
5. **The proxy actually SENDS the token.** `test_owner_with_token_sends_s7_header` captures the OUTGOING `urllib.request.Request` and asserts the S7 header value — spec reviewer mutation-tested it (dropping `**s7_headers` fails the test).
6. **Missing token → 502 failed-send, never a reply.** The no-token path returns `{"ok": false, "error": "s7_internal_channel_untrusted"}, 502` and `urlopen` is asserted **not called** (a real failed-send, not send-then-fail). The UI already renders non-OK as "couldn't reach Maez."
7. **Contract preserved.** Success returns the daemon's `(payload, status, Content-Type)` tuple unchanged — `test_preserves_daemon_content_type` (non-JSON daemon Content-Type passes through; mutation-tested against re-hardcoding `application/json`).
8. **`e.close()` in `finally`** in the HTTPError branch (closes even if `e.read()` raises) — the Organ-2 ResourceWarning lesson.
9. **Telegram unaffected** — it reaches `handle_message` in-process (`maez_adapter:1197`), never the HTTP `/message` route (Task-0 proven).
10. **No inbound-path change** — `cockpit_core` / felt-time / tools / the descriptors are untouched. 3a secures *who may send*, not the turn that runs.
11. **Built on the merged Organ-2 base** — reuses `_s7_internal_channel_headers` + `_owner_private_auth_required_response` (no duplication); the web gate is idiomatic with the Organ-2 sibling `api_daemon_state`.

## Codex HOLD (2026-06-19) — RESOLVED: a missed `/message` caller

Codex caught that Task 0's inventory was scoped too narrowly (it missed `ui/`): the **maez-face**
terminal UI (`ui/maez_terminal_ui.py:21,619`) POSTs to daemon `/message` WITHOUT an S7 header, so the
always-on gate would 403 it. **Repo-wide re-inventory** found exactly two production callers — the web
cockpit proxy and maez-face. **Owner decision: RETIRE maez-face** (superseded by the face
visual-direction work). In-repo: RETIRED header on `ui/maez_terminal_ui.py`; `maez-face.service` +
autostart moved to Stopped/disabled in `PROGRESS_PUBLIC.md`; Task-0 proof amended. With maez-face
retired, the only remaining **live production** caller of `/message` is the web cockpit proxy →
Approach A's always-on gate is safe. (Process lesson recorded: Task-0 inventory scans the WHOLE repo.)

## Owner breath (after Codex PASS + merge — owner-sovereign, do NOT do for them)

**No new secret.** 3a uses the SAME `S7_INTERNAL_CHANNEL_TOKEN` already provisioned + live for Organ 2 — nothing to add to `config/secrets.local.env`, no flag (both gates are always-on).

1. **Retire maez-face live** (so the gate doesn't 403 a running face): `systemctl disable --now maez-face.service` and remove `~/.config/autostart/maez-face.desktop`. (If maez-face isn't installed on this box, nothing to do — it's already not a live mouth.)
2. Merge `cockpit-conversation-spine-3a-secure` → main (local; main stays unpushed).
3. Restart `maez` (daemon) + `maez-web` so the gated routes go live. (Token already present from Organ 2's breath.)
4. **Witness:**
   - Owner sends a message from the cockpit → gets Maez's reply (the send now flows owner-gated + S7-locked into the same conversation).
   - Non-owner / no-cookie POST to `/api/v1/cockpit/message` → **401** `owner_auth_required`.
   - Headerless probe of the daemon route → **403**:
     `curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:11435/message -d '{"text":"hi"}'` → 403.
   - (bonus) token absent while sending → cockpit surfaces "couldn't reach Maez" (the 502), never a fabricated reply.

Only after the witness → mark **LIVE_WITNESSED** and record in [[project_organism_decompose_organs]] (Organ 3a). Next: **3b** (felt-time → full owner turn), then **3c** (action engine + web approval ceremony).
