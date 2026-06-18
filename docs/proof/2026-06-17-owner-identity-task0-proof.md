# Owner-Identity Task 0 — GO/NO-GO Proof Gate

**Date:** 2026-06-17
**Branch:** `web-native-owner-identity`
**Worktree:** `/home/rohit/.config/superpowers/worktrees/maez/web-native-owner-identity`
**Commit under test:** `1e68cff6728677915f782d34dc34a73fb3b670fc`
**Scope:** DOCS/PROOF ONLY. No behavior code changed. This gate verifies three plan
assumptions against the REAL code before any auth-boundary work begins. The failure
mode of this boundary is **owner lockout** (the exact scar from the coherence-organism
NO-GO, which mass-gated everything and locked the owner out), so each claim is proven
concretely rather than asserted.

---

## (a) Route inventory — the enumerated owner-private route set

`_debug_auth_ok()` is the **only owner-private gate that exists today**. It is defined at
`skills/web_interface.py:9738`:

```python
def _debug_auth_ok():
    """Gate for /debug and /api/debug/*. Test_t bypass matches existing
    private-surface pattern; production requires a real owner-bridge token."""
    if request.args.get("test_t", "").strip():
        return True
    token = _request_token()
    if not token:
        return False
    user = accounts.get_by_token(token)
    if not user:
        return False
    return _is_private_owner_bridge(user)
```

Every route handler that calls `_debug_auth_ok()` (one call site per handler, mapped from
the `@app.route` decorator immediately above each call) — **the complete v0 owner-private
list**:

| # | Route path | `@app.route` line | `_debug_auth_ok()` call line | Failure response |
|---|------------|-------------------|------------------------------|------------------|
| 1 | `/debug` | 9753 | 9755 | `redirect("/login")` |
| 2 | `/debug/flow` | 9760 | 9765 | `redirect("/login")` |
| 3 | `/debug/flow/static` | 9770 | 9774 | `redirect("/login")` |
| 4 | `/debug/card-default` | 9779 | 9784 | `redirect("/login")` |
| 5 | `/api/debug/services` | 9789 | 9793 | `401 unauthorized` |
| 6 | `/api/debug/wonderings` | 9897 | 9900 | `401 unauthorized` |
| 7 | `/api/debug/canary-leaks` | 9912 | 9926 | `401 unauthorized` |
| 8 | `/api/debug/trace-labels` | 9961 | 9973 | `401 unauthorized` |
| 9 | `/api/debug/memory-view` | 10001 | 10010 | `401 unauthorized` |
| 10 | `/api/debug/pursuit-decisions` | 10047 | 10059 | `401 unauthorized` |
| 11 | `/api/debug/wondering-events` | 10122 | 10126 | `401 unauthorized` |
| 12 | `/api/debug/cycle-timeline` | 10150 | 10155 | `401 unauthorized` |
| 13 | `/api/debug/cards` | 10181 | 10187 | `401 unauthorized` |
| 14 | `/api/debug/recent-shells` | 10235 | 10241 | `401 unauthorized` |
| 15 | `/api/debug/fabrication-feed` | 10275 | 10282 | `401 unauthorized` |
| 16 | `/api/debug/stats` | 10401 | 10405 | `401 unauthorized` |

There are **16** `_debug_auth_ok()` call sites and **16** route handlers (1:1) — verified by
matching every `_debug_auth_ok` line from the grep against the nearest `@app.route` above it.
The set spans exactly two prefixes: `/debug*` (4 routes) and `/api/debug/*` (12 routes).

**Statement:** This exact 16-route set IS the v0 owner-private list. Nothing else gets
gated. Owner-identity work in this plan operates ONLY on these enumerated routes plus any
new route it introduces and individually names owner-private.

---

## (b) Audit sink decision

Command:

```
grep -nE "def .*audit|append.*jsonl|\.jsonl" skills/user_accounts.py
```

Result: **no matches (exit 1).** There is **NO existing append-only audit primitive** in
`skills/user_accounts.py` — no `audit`-named function, no `.jsonl` append path.

**Conclusion / concrete name:** Task 3 will define a NEW append-only sink at the path:

```
memory/owner_identity_audit.jsonl
```

written by a NEW module:

```
core/governance/owner_identity_audit.py
```

This is a green-field append-only sink — it does not reuse or extend any existing
`user_accounts.py` primitive (none exists). One concrete sink, one concrete writer module.

---

## (c) Real-peer loopback proof

Commands:

```
grep -nE "ProxyFix|wsgi_app =|werkzeug.middleware" skills/web_interface.py   -> no matches (exit 1)
grep -n "app.run(host=" skills/web_interface.py                              -> 10427: app.run(host="127.0.0.1", port=11437, debug=False)
grep -nE "X-Forwarded|X-Real-IP|remote_addr|HTTP_X_FORWARDED" ...            -> no matches (exit 1)
```

Findings:

- **No `ProxyFix`, no `wsgi_app =` reassignment, no `werkzeug.middleware`** anywhere in
  `skills/web_interface.py`. The WSGI peer is the raw, untrusted-header-free peer.
- The app binds **`host="127.0.0.1", port=11437`** (`skills/web_interface.py:10427`) — the
  surface is loopback-bound; it does not listen on `0.0.0.0`.
- **No code reads `X-Forwarded-For`, `X-Real-IP`, `remote_addr`, or `HTTP_X_FORWARDED`
  today.** `_request_is_loopback()` does not exist yet (grep exit 1) — it is a clean Task-3
  addition with no conflicting precedent.

**Conclusion — the mechanism `_request_is_loopback()` MUST implement:**

- Read **`request.remote_addr` ONLY** (the raw WSGI peer address).
- Treat **`127.0.0.0/8`** and **`::1`** (and the IPv4-mapped `::ffff:127.0.0.0/8`) as loopback.
- **NEVER consult `X-Forwarded-For` / `X-Real-IP`** or any caller-supplied header — those are
  client-spoofable and would let a remote caller forge locality.

**Future-proxy caveat:** Today there is no reverse proxy, so `request.remote_addr` IS the
real peer. IF a reverse proxy is ever placed in front of the surface, `remote_addr` becomes
the **proxy's** IP. If that proxy runs on the same host, its connection to the app is itself
loopback and `_request_is_loopback()` would (correctly, per its own peer) return True for
*all* proxied traffic — collapsing the locality distinction. The mitigation is a deployment
discipline, NOT a code change: do **NOT** add `ProxyFix` / trust `X-Forwarded-For` to
recover per-client locality, because that re-opens the spoofing hole. Locality must remain a
property of the real TCP peer.

**Live witness:**

```
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:11437/api/v1/now
-> 200
```

maez-web is up and answering on `127.0.0.1:11437` (HTTP 200), confirming the loopback bind is
live. The `app.run(host="127.0.0.1", ...)` binding is the standing proof regardless of uptime.

---

## (d) OWNER'S EXTRA GUARD — `/api/v1/*` stays open unless individually named owner-private

This is the direct lesson from the **coherence-organism switch-over NO-GO**, which mass-gated
the surface and locked the owner out (owner ≠ private_owner_bridge; daemon 403'd its own
token). v0 must NOT repeat blanket/prefix gating.

**Sampled `/api/v1/*` handlers** — proven to call NO owner gate, return NO 401, and do NO
login redirect within their handler bodies:

| Route | `@app.route` line | Owner gate? 401? login-redirect? |
|-------|-------------------|----------------------------------|
| `/api/v1/now` | 3451 | NONE — open |
| `/api/v1/daemon/state` | 1535 | NONE — open |
| `/api/v1/chat/sessions` | 5952 | NONE — open |
| `/api/v1/services` | 1987 | NONE — open |

Cross-check: **every** `_debug_auth_ok()` call site lives at line 9755 or below (the
`/debug*` + `/api/debug/*` block); **all** `/api/v1/*` route handlers live below line 6050.
There is zero overlap — no `/api/v1/*` handler can reach a `_debug_auth_ok()` gate.

**`_is_private_owner_bridge` — not an access gate, and not on `/api/v1/*`.** Two call sites
exist outside the debug block:

- `skills/web_interface.py:6283` — inside `@app.route("/chat", ...)` (line 6264)
- `skills/web_interface.py:6973` — inside `@app.route("/history")` (line 6959)

Both are on **`/chat` and `/history`, NOT `/api/v1/*`**, and both use the result for
**content personalization** (`owner_bridge` → load private owner history), not to block the
route — neither returns 401 nor redirects. They do not gate access.

`_owner_private_auth_ok` does **not exist** in the codebase today (grep exit 1) — it is a
future Task name, confirming no owner-private helper has leaked onto `/api/v1/*` yet.

**v0 INVARIANT (explicit):** v0 adds owner-gating ONLY to the routes enumerated in (a). No
`/api/v1/*` route is gated unless it is individually named owner-private. **No blanket /
no prefix gating.**

**Exceptions:** NONE. No `/api/v1/*` route is owner-gated today. The `/api/v1/*` surface is
entirely localhost-open at this commit.

---

## Plan-assumption reconciliation

All three plan assumptions verified TRUE against the real code, with no contradictions:

- (a) `_debug_auth_ok()` is the sole owner-private gate; exactly 16 routes, all under
  `/debug*` + `/api/debug/*`. No surprises, no unexpected call sites.
- (b) No existing audit primitive in `user_accounts.py` — green-field sink confirmed.
- (c) No `ProxyFix`, no XFF handling, loopback-bound (`127.0.0.1:11437`), live 200. The
  raw-peer-only design is unobstructed.
- (d) No `/api/v1/*` route is owner-gated today; the two `_is_private_owner_bridge` sites are
  personalization on `/chat` + `/history`, not access gates. The "stays open" invariant holds.

---

TASK 0 VERDICT: GO
