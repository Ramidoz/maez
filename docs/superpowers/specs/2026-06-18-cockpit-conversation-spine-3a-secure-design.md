# Cockpit Conversation Spine — Organ 3a: Secure the Spine (design)

**Date:** 2026-06-18. Co-designed with Rohit.
**Status:** design approved (always-on auth hardening of the existing cockpit→daemon message path; 4
refinements folded). Awaiting spec review before planning.
**Arc:** decompose-the-organism ([[project_organism_decompose_organs]]), **Organ 3**, sub-organ **3a of 3**
(sequenced 3a secure → 3b felt-time → 3c action engine). Organ 1 LIVE; Organ 2 built + both-lanes-PASS
@`cb7a37f` (awaiting owner breath). This sub-organ closes a **write** hole on the conversation nerve.

## Why this exists — secure the EXISTING spine, do NOT build a second door

The cockpit conversation path **already exists** on `main` and is the only web mouth using it:
- The cockpit UI chat input POSTs to `/api/v1/cockpit/message` (`web/cockpit/terminal-ui.jsx:430`).
- `api_cockpit_message` (`skills/web_interface.py:1739`) proxies the body **verbatim** to the daemon
  `http://127.0.0.1:11435/message` — with **no owner gate** and **no S7 header**.
- The daemon `/message` route (`daemon/maez_daemon.py:10677`) accepts it with **no S7 gate** and routes
  it into the conversation (today `source="UI"`; or `run_inbound_turn(source="cockpit")` when
  `cockpit_core_enabled()`).

**The hole:** anyone who can reach maez-web — or the daemon port directly — can inject messages **as the
owner** into Maez's conversation and memory. This is a *write* hole, strictly worse than Organ 2's read
hole. 3a closes it: **only the owner browser may send, and only over the private S7 nerve.** Telegram is
unaffected — it reaches `handle_message` **in-process** (`skills/surface/maez_adapter.py:1197`), never
through the HTTP `/message` route.

3a is **transport security only** — it changes *who may send*, not the turn that runs. Felt-time and the
action engine are 3b/3c.

## Dependency — sequences AFTER Organ 2

3a reuses two symbols that live on the **unmerged** Organ-2 branch (`cb7a37f`), not yet on `main`:
- `_s7_internal_channel_headers()` (web) — reads the S7 token, raises `RuntimeError` if absent.
- `_owner_private_auth_required_response()` (web) — `jsonify({"ok": False, "error": "owner_auth_required"}), 401`.

So 3a **builds after the owner breathes/merges Organ 2**; its branch bases on main-with-Organ-2. It needs
**no new secret** — the same `S7_INTERNAL_CHANNEL_TOKEN` (managed secret, provisioned via
`config/secrets.local.env` for both services) that Organ 2's breath provisions. Already-on-main rails it
also uses: `_owner_private_auth_ok` (#1 web-native matrix), `_s7_internal_channel_trusted` (daemon, #2).

## The design (additive hardening only)

**1 · Web side — gate BEFORE reading the body, then send the S7 header (refinements 1, 2, 3).**
Modify `api_cockpit_message` in place:
```python
@app.route("/api/v1/cockpit/message", methods=["POST"])
def api_cockpit_message():
    """Proxy the cockpit's chat send to the daemon's /message endpoint. ... (keep docstring)"""
    if not _owner_private_auth_ok():                 # (1) gate BEFORE request.get_data()
        return _owner_private_auth_required_response()  # 401 owner_auth_required
    try:
        s7_headers = _s7_internal_channel_headers()  # raises if token absent
    except RuntimeError:
        return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 502  # (2) failed SEND, not a reply
    import urllib.request as _urlreq
    import urllib.error as _urlerr
    body = request.get_data() or b"{}"
    headers = {"Content-Type": request.headers.get("Content-Type", "application/json"), **s7_headers}
    try:
        req = _urlreq.Request(f"{_DAEMON_BASE}/message", data=body, headers=headers, method="POST")
        with _urlreq.urlopen(req, timeout=_COCKPIT_PROXY_TIMEOUT_S) as resp:
            return Response(resp.read(), status=resp.status, mimetype="application/json")
    except _urlerr.HTTPError as e:
        payload = e.read()
        e.close()                                    # (3) close the HTTPError response (Organ-2 lesson)
        return Response(payload, status=e.code, mimetype="application/json")
    except Exception:
        return jsonify({"ok": False, "error": "daemon_unreachable"}), 502
```
- (1) The owner gate runs **before** `request.get_data()` — an unauthenticated write never enters parsing.
- (2) A missing token is a **non-2xx structured error** (`502` + `{"ok": false, "error":
  "s7_internal_channel_untrusted"}`). The UI already treats non-OK as "couldn't reach Maez" — correct: the
  owner's message was **not delivered**, never a fabricated reply.
- (3) The `HTTPError` branch **closes `e`** after reading (Organ 2's `97bc454` cleanup lesson), so no
  ResourceWarning. (Keep the existing branch's behavior of surfacing the daemon's status/body to the UI.)
- The exact `Response`/`_DAEMON_BASE`/`_COCKPIT_PROXY_TIMEOUT_S` usage stays as the existing route's; only
  the gate, the S7 header, the missing-token 502, and the `e.close()` are added.

**2 · Daemon side — gate BEFORE parsing (refinements 1, 4).** Add to the existing `/message` route, as the
very first statements:
```python
@app.route("/message", methods=["POST"])
def message():
    if not _s7_internal_channel_trusted(request):    # (1) gate BEFORE request.get_json()
        return jsonify({"ok": False, "error": "s7_internal_channel_untrusted"}), 403  # (4) explicit body
    data = request.get_json(silent=True) or {}
    ...  # the existing body — unchanged
```
**Approach A (default):** gate the shared `/message` route. Telegram doesn't use it (in-process), and Task 0
proves the cockpit web proxy is the only **production** HTTP caller. **Approach B (Task-0 fallback only):**
if Task 0 finds a real non-cockpit production HTTP caller, add a dedicated S7-gated
`/internal/cockpit/message` route and repoint the web proxy instead of gating the shared route.

**3 · No inbound-path change.** `cockpit_core_enabled()` / felt-time / tools / the descriptor builders are
untouched. The turn that runs after the gate is whatever runs today — 3a only secures *who* may send.

## Safe posture (the Organ-2 framing)

- **Always-on auth, no new capability.** Both gates are unconditional (no flag). The real-state/turn
  behavior is unchanged for authorized callers; the always-on gates **intentionally** change access — a
  non-owner/remote message send now correctly gets `401`, and a tokenless/forged daemon `/message` call
  now gets `403`. That access change IS the hardening.
- **Telegram unaffected** — in-process path, never the HTTP `/message` route (verify in Task 0).
- **A missing token fails the send honestly** (`502` + reason) — never a fabricated reply, never a silent
  unauthenticated send.

## Covenant rail

Closes a **write** hole: owner-message injection into Maez's conversation + memory. Trust is two-layer —
**owner-identity at the web edge** (`_owner_private_auth_ok`, #1's no-lockout matrix, loopback-unclaimed
OPENS so the local owner is never locked out, [[feedback_s7_trust_is_human_gated_by_design]]) and the
**S7 token on the internal nerve** (constant-time + no-Origin CSRF guard). **Never a telegram-derived
owner** — the prior NO-GO was `owner≠private_owner_bridge`; 3a touches only the web-native `web_owner`
matrix. Singular organism: the cockpit is one mouth into the one conversation
([[project_maez_singular_organism_surfaces]]); the trust boundary is owner-identity, not surface-type.

## Task 0 — proof gate (docs/proof only, committed first)

If any proof refutes the design, STOP and patch.
- **Consumer inventory (load-bearing, decides A vs B):** prove the web `api_cockpit_message` proxy is the
  **only production HTTP caller** of the daemon `/message` route (grep `"/message"`, `:11435/message`,
  `_DAEMON_BASE` across daemon+web+cockpit+scripts+tests; **classify** each hit production vs test — test
  refs are expected and do NOT refute). If a non-test, non-cockpit production HTTP caller exists →
  Approach B (dedicated route). Confirmed-likely: cockpit proxy only; `tests/test_cockpit_proxies_2026_05_05.py`
  + `tests/test_ui_message_history_threading.py` POST `/message` directly (test refs).
- **Telegram-path proof:** confirm telegram reaches `handle_message` in-process (maez_adapter), NOT via the
  HTTP `/message` route — so the daemon S7 gate cannot starve telegram.
- **Existing-test-breakage inventory (Organ-2 lesson):** list every test that POSTs to `/api/v1/cockpit/message`
  (now owner-gated → needs an owner mock) or to daemon `/message` (now S7-gated → needs the header).
  `tests/test_cockpit_proxies_2026_05_05.py`, `tests/test_ui_message_history_threading.py` must be updated,
  not left to break.
- **Clean separation:** the gated routes call NO new web-owner-spine (`_proxy_web_owner_message_to_daemon`,
  the quarry `/chat` bridge) or voice code; 3a touches only the existing two functions.
- **Import resolution (on the Organ-2-merged base):** `_owner_private_auth_ok`,
  `_owner_private_auth_required_response`, `_s7_internal_channel_headers` (web), `_s7_internal_channel_trusted`
  (daemon), `_DAEMON_BASE`, `_COCKPIT_PROXY_TIMEOUT_S` all resolve.

## Testing (TDD; hermetic — mock the owner gate, env the token; never live users.db)

- **Web `/api/v1/cockpit/message`:** non-owner → **401** `owner_auth_required` (gate before body); owner +
  no token → **502** `{"ok": false, "error": "s7_internal_channel_untrusted"}` (no send); owner + token →
  proxies to daemon `/message` and **the outgoing `urllib.request.Request` carries
  `X-Maez-S7-Internal-Channel` = the managed token** (capture the Request, mutation-proof — Organ-2's must-have
  test shape); daemon HTTPError → status/body surfaced and `e` closed (no ResourceWarning); daemon down → 502
  `daemon_unreachable`.
- **Daemon `/message`:** valid S7 header → 200 (existing behavior); headerless / wrong token → **403**
  `{"ok": false, "error": "s7_internal_channel_untrusted"}`; **valid token + `Origin` header → 403** (pin the
  no-Origin guard on the now-gated route). Gate asserted to run **before** `get_json` (a malformed-body
  request with no token still 403s, never 400).
- **Update the existing /message tests** (`test_cockpit_proxies_2026_05_05`, `test_ui_message_history_threading`)
  to carry the S7 header / owner mock so they exercise the gated path instead of breaking.
- Scope-guard: only the message-spine cases; no felt-time / action-engine / `/chat` cases.

## Witness (live, before LIVE_WITNESSED)

1. Owner sends a message from the cockpit → gets Maez's reply (one conversation, same body as telegram).
2. Non-owner / no-cookie POST to `/api/v1/cockpit/message` → **401**.
3. Headerless probe of the daemon route → **403**:
   `curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:11435/message -d '{"text":"hi"}'` → 403.
4. Token absent while sending → cockpit surfaces "couldn't reach Maez" (the 502), never a fabricated reply.
Owner breath = the **same** S7 token Organ 2 provisions (no new secret); merge after Organ 2; restart both.

## Scope

- **IN:** the web `api_cockpit_message` owner-gate + S7-header + missing-token-502 + HTTPError-close; the
  daemon `/message` S7 gate (Approach A); the hermetic tests + the two existing-/message-test updates.
- **OUT (deferred):** felt-time on the cockpit turn (**3b**); the action engine — tools/cards/search/proposals
  + the web approval ceremony (**3c**); the web `/chat` route + any `private_owner_bridge`/telegram-derived
  owner path (the NO-GO landmine — never); the voice spine (Organ 4); the coherence ceremony (Organ 5); any
  change to `cockpit_core_enabled` / the inbound descriptors / `handle_message`.
