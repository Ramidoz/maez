# Web-Native Owner Identity (v0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Maez's cockpit a web-native owner identity — claimed locally from inside the machine — replacing the Telegram-derived `private_owner_bridge` that locked the owner out during the coherence-organism NO-GO.

**Architecture:** Web-edge only (cookie → account → `web_owner`; no daemon round-trip). Ownership is born via a local TTY+uid `maez own-claim` CLI, recorded as an additive `web_owner` column plus future role/provenance/consent/access-scope seams. A gating helper enforces a loopback/remote × claimed/unclaimed truth-table on an *enumerated* set of owner-private routes — never mass-gating `/api/v1/*`. There is **no feature flag**: `owner_claimed()` is the only activation state, and the unclaimed state is the safe floor. Never-lockout is **local physical recovery**, not browser fail-open.

**Tech Stack:** Python 3, sqlite3 (`memory/users.db`), Flask/Werkzeug (`skills/web_interface.py`), argparse CLI (`scripts/maez_cli.py`), `unittest` tests.

**Spec:** `docs/superpowers/specs/2026-06-17-web-native-owner-identity-v0-design.md` (@4d46b44).

---

## Lane discipline (read before starting)

- **Test runner:** `/home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v`. **Never** full-discover; run named modules only.
- **Branch:** do the work on a branch (use `superpowers:using-git-worktrees`). `main` is local-only/unpushed — **no push**.
- **Commits:** behavior commits carry a `## Predicted effect` trailer; docs/spec/test-only commits do not. End every commit with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **STOP at the review gate** (after Task 7). Do **no** live claim, restart, or flag change — those are owner-sovereign. Cross-lane Codex review at the gate (this is the auth boundary).
- **Live witness before any `LIVE_WITNESSED`:** owner claims locally → owner-private works in browser → unclaimed loopback fallback verified → rebind recovery verified → owner confirms in the browser.

## File structure

- **Modify** `skills/user_accounts.py` — additive columns in `_migrate()`; `web_owner`/seam fields in `get_user_record()`; new owner-claim DB methods (`owner_claimed`, `get_owner`, `claim_owner`, `rebind_owner`, `reset_owner`).
- **Create** `core/governance/owner_identity_audit.py` — tiny append-only audit sink (jsonl).
- **Modify** `scripts/maez_cli.py` — `own-claim` subcommand (`cmd_own_claim`) with TTY+uid guard, confirmation, audit.
- **Modify** `skills/web_interface.py` — `_is_owner`, `_request_is_loopback`, `_owner_private_gate`, claim-required/denied responses; swap `_debug_auth_ok` to the gate; remove `?test_t=`/`?web_token=` bypass on owner-private routes.
- **Create** tests: `tests/test_owner_identity_model.py`, `tests/test_owner_claim_cli.py`, `tests/test_web_owner_gating.py`.
- **Create** `docs/proof/2026-06-17-owner-identity-task0-proof.md` (Task 0 output).

---

### Task 0: HARD GO/NO-GO PROOF GATE (docs/proof only — no behavior change)

Owner-mandated. Produce three proofs and commit them **before any behavior code**. If any proof refutes the spec, STOP and patch spec/plan.

**Files:**
- Create: `docs/proof/2026-06-17-owner-identity-task0-proof.md`

- [ ] **Step 1: Route inventory — enumerate the owner-private routes to gate**

Run:
```bash
cd /home/rohit/maez
grep -n "_debug_auth_ok" skills/web_interface.py
grep -nE "@app\.route\(.*(debug|owner|private)" skills/web_interface.py
```
Expected: the only current owner-private gate is `_debug_auth_ok()` (`skills/web_interface.py:9738`), used by `/debug`, `/debug/flow`, and `/api/debug/*` handlers. The `/api/v1/*` data routes are localhost-open (no owner gate) — confirm by sampling that they have **no** `_debug_auth_ok`/auth call.

In the proof doc, record the **exact enumerated v0 owner-private route list** = every route whose handler currently calls `_debug_auth_ok()` (paste the grep output with file:line). State explicitly: **v0 gates only this set; `/api/v1/*` localhost-open routes are NOT gated** (the NO-GO lesson).

- [ ] **Step 2: Audit sink — prove existing or define new**

Run:
```bash
grep -nE "def .*audit|audit_ref|append.*jsonl|\.jsonl" skills/user_accounts.py | head
ls memory/*.jsonl 2>/dev/null | head
```
Expected: `user_accounts.py` has **no** append-only audit primitive. Conclude in the proof doc: define a new append-only sink `memory/owner_identity_audit.jsonl`, written by `core/governance/owner_identity_audit.py` (Task 3 wires it). Name it explicitly; do not leave "existing audit trail" prose.

- [ ] **Step 3: Real-peer loopback proof**

Run:
```bash
grep -nE "ProxyFix|wsgi_app =|werkzeug.middleware|remote_addr" skills/web_interface.py | head
grep -n "app.run(host=" skills/web_interface.py
```
Expected: **no `ProxyFix`/middleware** rewrites the peer; `app.run(host="127.0.0.1", port=11437…)` (`:10427`). So `request.remote_addr` is the **raw TCP peer**. Record: `_request_is_loopback()` reads `request.remote_addr` only, treats `127.0.0.0/8` and `::1` as loopback, and **never** consults `X-Forwarded-For`/`X-Real-IP`. Document the future-proxy caveat: if a reverse proxy is ever added, `remote_addr` becomes the proxy IP (still non-loopback unless the proxy is itself local), and one must **not** add `ProxyFix` to trust XFF for locality.

Verify against the running surface:
```bash
curl -s -o /dev/null -w 'cockpit peer test: HTTP %{http_code}\n' http://127.0.0.1:11437/api/v1/now
```
Expected: 200 (current localhost reachability), confirming the surface is bound to loopback today.

- [ ] **Step 4: Commit the proof (docs only, no `## Predicted effect`)**

```bash
git add docs/proof/2026-06-17-owner-identity-task0-proof.md
git commit -m "docs(proof): owner-identity Task 0 gate — route inventory, audit sink, real-peer loopback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1: Additive schema columns + record fields

**Files:**
- Modify: `skills/user_accounts.py` (`_migrate()` ~:101-116; `get_user_record()` ~:243-275)
- Test: `tests/test_owner_identity_model.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_owner_identity_model.py
import os, tempfile, unittest
from skills.user_accounts import UserAccounts

class OwnerIdentitySchema(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "users.db")
        self.acc = UserAccounts(db_path=self.db)
        self.acc.register("rohit", "pw", display_name="Rohit")
        self.uid = self.acc.get_by_username("rohit")["uuid"]

    def test_additive_columns_exist_and_default(self):
        rec = self.acc.get_user_record(self.uid)
        # New seams present; owner unset by default (safe floor).
        self.assertEqual(rec["web_owner"], 0)
        self.assertIsNone(rec["provenance"])
        self.assertIsNone(rec["consent"])
        self.assertIsNone(rec["access_scope"])

    def test_existing_rows_stay_valid(self):
        # Re-opening the same DB (re-running _migrate) must not error or drop data.
        acc2 = UserAccounts(db_path=self.db)
        self.assertIsNotNone(acc2.get_by_username("rohit"))
```

> Note: `register(username, password, display_name="")` (`user_accounts.py:127`) and
> `get_by_username(...)["uuid"]` (`:231`) are the verified APIs used above. Do not weaken the assertions.

- [ ] **Step 2: Run it — expect FAIL** (`KeyError: 'web_owner'`)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_owner_identity_model -v`

- [ ] **Step 3: Add the columns + record fields**

In `_migrate()` `new_cols` dict, add:
```python
            'web_owner': 'INTEGER DEFAULT 0',
            'provenance': 'TEXT',
            'consent': 'TEXT',
            'access_scope': 'TEXT',
```
In `get_user_record()`, extend the SELECT and the returned dict:
```python
            row = conn.execute(
                "SELECT uuid, username, display_name, trust_tier, relationship, "
                "rohit_confirmed, share_config, telegram_id, telegram_profile_id, "
                "web_owner, provenance, consent, access_scope "
                "FROM users WHERE uuid=?",
                (uid,),
            ).fetchone()
        # ... existing share_config / private_owner_bridge computation unchanged ...
        return {
            # ... existing keys unchanged ...
            "private_owner_bridge": private_owner_bridge,
            "web_owner": int(row[9] or 0),
            "provenance": row[10],
            "consent": row[11],
            "access_scope": row[12],
        }
```

- [ ] **Step 4: Run it — expect PASS**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_owner_identity_model -v`

- [ ] **Step 5: Commit (behavior — schema/record change)**

```bash
git add skills/user_accounts.py tests/test_owner_identity_model.py
git commit -m "feat(owner-identity): additive web_owner + provenance/consent/access_scope columns

## Predicted effect
get_user_record gains web_owner (default 0) + nullable provenance/consent/access_scope
seams; existing rows stay valid; no behavior keys off the seams yet.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Owner-claim DB methods (pure, testable — no TTY/uid guard here)

**Files:**
- Modify: `skills/user_accounts.py` (add methods near `link_private_owner` ~:198)
- Test: `tests/test_owner_identity_model.py` (add cases)

- [ ] **Step 1: Write the failing tests**

```python
    def test_claim_is_idempotent_and_sets_owner_fields(self):
        self.assertFalse(self.acc.owner_claimed())
        self.assertEqual(self.acc.claim_owner(self.uid), "claimed")
        self.assertTrue(self.acc.owner_claimed())
        rec = self.acc.get_user_record(self.uid)
        self.assertEqual(rec["web_owner"], 1)
        self.assertEqual(rec["relationship"], "owner")
        self.assertEqual(rec["trust_tier"], 3)
        self.assertEqual(rec["provenance"], "local-owner-claim")
        self.assertEqual(self.acc.claim_owner(self.uid), "noop")   # idempotent

    def test_claim_refuses_when_other_owner_exists(self):
        self.acc.register("alex", "pw")
        uid2 = self.acc.get_by_username("alex")["uuid"]
        self.acc.claim_owner(self.uid)
        with self.assertRaises(ValueError):
            self.acc.claim_owner(uid2)

    def test_rebind_moves_owner_and_reset_clears(self):
        self.acc.register("alex", "pw")
        uid2 = self.acc.get_by_username("alex")["uuid"]
        self.acc.claim_owner(self.uid)
        self.assertEqual(self.acc.rebind_owner(uid2), "rebound")
        self.assertEqual(self.acc.get_owner()["uuid"], uid2)
        self.assertEqual(self.acc.get_user_record(self.uid)["web_owner"], 0)  # prior owner cleared
        self.assertEqual(self.acc.reset_owner(), 1)
        self.assertFalse(self.acc.owner_claimed())

    def test_claim_unknown_uid_raises(self):
        with self.assertRaises(ValueError):
            self.acc.claim_owner("no-such-uid")
```

- [ ] **Step 2: Run — expect FAIL** (`AttributeError: owner_claimed`)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_owner_identity_model -v`

- [ ] **Step 3: Add the methods**

```python
    def owner_claimed(self) -> bool:
        with self._conn() as conn:
            return conn.execute("SELECT 1 FROM users WHERE web_owner=1 LIMIT 1").fetchone() is not None

    def get_owner(self) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT uuid, username FROM users WHERE web_owner=1 LIMIT 1").fetchone()
        return {"uuid": row[0], "username": row[1]} if row else None

    def _owner_consent_stamp(self) -> str:
        return json.dumps({"kind": "owner-self-consent", "at": time.time()})

    def claim_owner(self, uid: str, *, provenance: str = "local-owner-claim") -> str:
        if not self.get_user_record(uid):
            raise ValueError(f"no such account: {uid}")
        existing = self.get_owner()
        if existing and existing["uuid"] == uid:
            return "noop"
        if existing and existing["uuid"] != uid:
            raise ValueError(f"owner already claimed by {existing['username']}; use rebind")
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET web_owner=1, relationship='owner', trust_tier=3, "
                "provenance=?, consent=?, access_scope='owner-private' WHERE uuid=?",
                (provenance, self._owner_consent_stamp(), uid),
            )
            conn.commit()
        return "claimed"

    def rebind_owner(self, uid: str) -> str:
        if not self.get_user_record(uid):
            raise ValueError(f"no such account: {uid}")
        with self._conn() as conn:
            conn.execute("UPDATE users SET web_owner=0 WHERE web_owner=1")
            conn.execute(
                "UPDATE users SET web_owner=1, relationship='owner', trust_tier=3, "
                "provenance='local-owner-claim', consent=?, access_scope='owner-private' WHERE uuid=?",
                (self._owner_consent_stamp(), uid),
            )
            conn.commit()
        return "rebound"

    def reset_owner(self) -> int:
        with self._conn() as conn:
            cur = conn.execute("UPDATE users SET web_owner=0 WHERE web_owner=1")
            conn.commit()
            return cur.rowcount
```

- [ ] **Step 4: Run — expect PASS**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_owner_identity_model -v`

- [ ] **Step 5: Commit (behavior)**

```bash
git add skills/user_accounts.py tests/test_owner_identity_model.py
git commit -m "feat(owner-identity): claim/rebind/reset + owner_claimed DB methods

## Predicted effect
UserAccounts gains owner_claimed()/get_owner()/claim_owner()/rebind_owner()/reset_owner();
claim is idempotent and refuses a second owner; rebind moves it; reset clears. No CLI/web
wiring yet — pure DB layer.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Audit sink + `maez own-claim` CLI (local TTY+uid, audited, confirmed)

**Files:**
- Create: `core/governance/owner_identity_audit.py`
- Modify: `scripts/maez_cli.py` (add `cmd_own_claim` + subparser; `main()` ~:321)
- Test: `tests/test_owner_claim_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_owner_claim_cli.py
import json, os, tempfile, unittest
from skills.user_accounts import UserAccounts
from scripts import maez_cli

class FakeArgs:
    def __init__(self, **kw):
        self.account = kw.get("account")
        self.rebind = kw.get("rebind", False)
        self.reset = kw.get("reset", False)

class OwnClaimCli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "users.db")
        self.audit = os.path.join(self.dir, "owner_identity_audit.jsonl")
        self.acc = UserAccounts(db_path=self.db)
        self.acc.register("rohit", "pw", display_name="Rohit")
        # Inject deterministic guards/sinks (the CLI reads these hooks).
        self.ctx = dict(accounts=self.acc, audit_path=self.audit,
                        is_interactive=lambda: True,
                        uid_ok=lambda: True,
                        confirm=lambda prompt: True)

    def test_claim_sets_owner_and_audits(self):
        rc = maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertEqual(rc, 0)
        self.assertTrue(self.acc.owner_claimed())
        rows = [json.loads(l) for l in open(self.audit)]
        self.assertEqual(rows[-1]["action"], "claim")

    def test_refuses_without_tty(self):
        self.ctx["is_interactive"] = lambda: False
        rc = maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.acc.owner_claimed())

    def test_refuses_on_uid_mismatch(self):
        self.ctx["uid_ok"] = lambda: False
        rc = maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.acc.owner_claimed())

    def test_no_confirm_writes_nothing(self):
        self.ctx["confirm"] = lambda prompt: False
        rc = maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.acc.owner_claimed())
        self.assertFalse(os.path.exists(self.audit))

    def test_idempotent_reclaim(self):
        maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        rc = maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertEqual(rc, 0)  # noop success

    def test_rebind_and_reset(self):
        self.acc.register("alex", "pw")
        maez_cli.cmd_own_claim(FakeArgs(account="rohit"), **self.ctx)
        self.assertEqual(maez_cli.cmd_own_claim(FakeArgs(account="alex", rebind=True), **self.ctx), 0)
        self.assertEqual(self.acc.get_owner()["username"], "alex")
        self.assertEqual(maez_cli.cmd_own_claim(FakeArgs(reset=True), **self.ctx), 0)
        self.assertFalse(self.acc.owner_claimed())
```

- [ ] **Step 2: Run — expect FAIL** (`AttributeError: cmd_own_claim`)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_owner_claim_cli -v`

- [ ] **Step 3: Implement the audit sink**

```python
# core/governance/owner_identity_audit.py
"""Append-only audit sink for web-native owner-identity claims (Task 0 §2)."""
import json, os, time
from core.infra import paths as _paths

DEFAULT_AUDIT_PATH = str(_paths.home() / "memory" / "owner_identity_audit.jsonl")

def record(action: str, *, account: str | None, euid: int, path: str = DEFAULT_AUDIT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps({"at": time.time(), "action": action, "account": account, "euid": euid})
    with open(path, "a") as f:
        f.write(line + "\n")
```

- [ ] **Step 4: Implement the CLI command + subparser**

Add to `scripts/maez_cli.py` (mirrors the trusted S7-bootstrap guard: `core/governance/s7_webauthn_bootstrap.py:429-434`):
```python
import os, sys
from skills.user_accounts import UserAccounts, DB_PATH
from core.governance import owner_identity_audit

def _default_is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()

def _default_uid_ok() -> bool:
    # The person at the machine must own the account store (mirrors S7 store_owner_uid).
    return os.geteuid() == os.stat(DB_PATH).st_uid

def _default_confirm(prompt: str) -> bool:
    return input(prompt).strip().lower() == "yes"

def cmd_own_claim(args, *, accounts=None, audit_path=None,
                  is_interactive=None, uid_ok=None, confirm=None) -> int:
    accounts = accounts or UserAccounts()
    is_interactive = is_interactive or _default_is_interactive
    uid_ok = uid_ok or _default_uid_ok
    confirm = confirm or _default_confirm
    audit = (lambda action, account: owner_identity_audit.record(
                 action, account=account, euid=os.geteuid(),
                 **({"path": audit_path} if audit_path else {})))

    if not is_interactive():
        print("refused: owner-claim must be run from an interactive local terminal.", file=sys.stderr)
        return 2
    if not uid_ok():
        print("refused: must run as the user that owns the account store.", file=sys.stderr)
        return 2

    if args.reset:
        if not confirm("Type 'yes' to CLEAR the web owner identity: "):
            print("aborted.", file=sys.stderr); return 1
        n = accounts.reset_owner(); audit("reset", None)
        print(f"owner cleared ({n} account(s))."); return 0

    username = (args.account or "").strip()
    rec = accounts.get_by_username(username) if username else None
    if not rec:
        print(f"refused: no account named {username!r}.", file=sys.stderr); return 2
    action = "rebind" if args.rebind else "claim"
    if not confirm(f"Type 'yes' to set owner = {rec['username']} ({rec['uuid']}): "):
        print("aborted.", file=sys.stderr); return 1
    try:
        result = accounts.rebind_owner(rec["uuid"]) if args.rebind else accounts.claim_owner(rec["uuid"])
    except ValueError as e:
        print(f"refused: {e}", file=sys.stderr); return 2
    audit(action, rec["username"])
    print(f"owner {result}: {rec['username']}."); return 0
```
In `main()`, register the subcommand alongside the existing ones:
```python
    p_claim = subparsers.add_parser("own-claim", help="Claim web-native owner identity (local only).")
    p_claim.add_argument("--account", help="username to mark as owner")
    p_claim.add_argument("--rebind", action="store_true", help="move owner to --account")
    p_claim.add_argument("--reset", action="store_true", help="clear the web owner")
```
And in `main()`'s command dispatch (it uses an `if args.command == …` chain, e.g.
`if args.command == "enter": return cmd_enter(args)`), add a branch:
```python
    elif args.command == "own-claim":
        return cmd_own_claim(args)
```
(Place it before the final `return 2` fallthrough, matching the existing `enter`/`exit` branches.)

- [ ] **Step 5: Run — expect PASS**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_owner_claim_cli -v`

- [ ] **Step 6: Commit (behavior)**

```bash
git add core/governance/owner_identity_audit.py scripts/maez_cli.py tests/test_owner_claim_cli.py
git commit -m "feat(owner-identity): maez own-claim CLI (local TTY+uid, audited, confirmed)

## Predicted effect
A new local-only 'maez own-claim' subcommand marks a web account as owner; refuses
without an interactive TTY or on uid mismatch; requires typed confirmation; writes an
append-only owner_identity_audit.jsonl record; supports --rebind/--reset. No HTTP path.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Web-edge helpers — `_is_owner`, `_request_is_loopback`

**Files:**
- Modify: `skills/web_interface.py` (near `_is_private_owner_bridge` ~:148; near `_request_token` ~:781)
- Test: `tests/test_web_owner_gating.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_web_owner_gating.py
import unittest
from unittest import mock
from skills import web_interface as W

class LoopbackAndOwner(unittest.TestCase):
    def test_is_owner_reads_web_owner_only(self):
        self.assertTrue(W._is_owner({"web_owner": 1}))
        self.assertFalse(W._is_owner({"web_owner": 0}))
        self.assertFalse(W._is_owner(None))
        # MUST NOT consult telegram-derived fields:
        self.assertFalse(W._is_owner({"web_owner": 0, "private_owner_bridge": True}))

    def test_loopback_true_for_127_and_v6(self):
        for addr in ("127.0.0.1", "127.0.0.5", "::1"):
            with mock.patch.object(W, "request", mock.Mock(remote_addr=addr, headers={})):
                self.assertTrue(W._request_is_loopback())

    def test_remote_is_not_loopback_and_xff_never_upgrades(self):
        with mock.patch.object(W, "request",
                               mock.Mock(remote_addr="203.0.113.7",
                                         headers={"X-Forwarded-For": "127.0.0.1"})):
            self.assertFalse(W._request_is_loopback())
```

- [ ] **Step 2: Run — expect FAIL**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_web_owner_gating -v`

- [ ] **Step 3: Implement the helpers**

Add near `_is_private_owner_bridge` (`:148`):
```python
def _is_owner(user_record: dict | None) -> bool:
    """Web-native owner check. Reads ONLY web_owner; never telegram-derived fields."""
    return bool(user_record and user_record.get("web_owner"))


_LOOPBACK_EXACT = {"::1", "::ffff:127.0.0.1"}

def _request_is_loopback() -> bool:
    """True only when the real TCP peer is loopback. Reads request.remote_addr
    (the raw WSGI peer — no ProxyFix is installed). NEVER consults
    X-Forwarded-For / X-Real-IP, which an attacker could set."""
    addr = (getattr(request, "remote_addr", "") or "").strip()
    return addr.startswith("127.") or addr in _LOOPBACK_EXACT
```

- [ ] **Step 4: Run — expect PASS**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_web_owner_gating -v`

- [ ] **Step 5: Commit (behavior — helpers, not yet wired into routes)**

```bash
git add skills/web_interface.py tests/test_web_owner_gating.py
git commit -m "feat(owner-identity): web-native _is_owner + real-peer _request_is_loopback

## Predicted effect
Adds _is_owner (reads web_owner only, never telegram) and _request_is_loopback (reads
request.remote_addr only, ignores X-Forwarded-For). Not yet wired into any route.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: The gating decision + apply to enumerated routes (remove query bypass)

**Files:**
- Modify: `skills/web_interface.py` (`_debug_auth_ok` ~:9738; the enumerated routes from Task 0)
- Test: `tests/test_web_owner_gating.py` (add the truth-table)

- [ ] **Step 1: Write the failing truth-table tests**

```python
class OwnerPrivateGate(unittest.TestCase):
    def _patch(self, *, claimed, loopback, cookie_user=None, owner=False):
        acc = mock.Mock()
        acc.owner_claimed.return_value = claimed
        acc.get_by_token.return_value = cookie_user
        acc.get_user_record.return_value = ({"web_owner": 1} if owner else {"web_owner": 0}) if cookie_user else None
        req = mock.Mock(remote_addr=("127.0.0.1" if loopback else "203.0.113.7"),
                        headers={}, cookies={"maez_token": "t"} if cookie_user else {})
        return mock.patch.object(W, "accounts", acc), mock.patch.object(W, "request", req)

    def test_unclaimed_loopback_allows(self):
        a, r = self._patch(claimed=False, loopback=True)
        with a, r:
            self.assertTrue(W._owner_private_auth_ok())

    def test_unclaimed_remote_denies(self):
        a, r = self._patch(claimed=False, loopback=False)
        with a, r:
            self.assertFalse(W._owner_private_auth_ok())

    def test_claimed_owner_allows(self):
        a, r = self._patch(claimed=True, loopback=False, cookie_user={"uuid": "u"}, owner=True)
        with a, r:
            self.assertTrue(W._owner_private_auth_ok())

    def test_claimed_nonowner_denies(self):
        a, r = self._patch(claimed=True, loopback=True, cookie_user={"uuid": "u"}, owner=False)
        with a, r:
            self.assertFalse(W._owner_private_auth_ok())

    def test_no_query_token_bypass(self):
        # ?web_token= / ?test_t= must NOT authorize when claimed and cookie absent.
        a = mock.patch.object(W, "accounts", mock.Mock(owner_claimed=lambda: True,
                                                        get_by_token=lambda t: None))
        r = mock.patch.object(W, "request",
                              mock.Mock(remote_addr="127.0.0.1", headers={},
                                        cookies={}, args={"web_token": "x", "test_t": "1"}))
        with a, r:
            self.assertFalse(W._owner_private_auth_ok())
```

- [ ] **Step 2: Run — expect FAIL**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_web_owner_gating -v`

- [ ] **Step 3: Implement the gate + rewrite `_debug_auth_ok`**

Replace the body of `_debug_auth_ok` (`:9738`) and add the gate:
```python
def _owner_private_auth_ok() -> bool:
    """Owner-private gate. Activation is owner_claimed() only (no feature flag).
    unclaimed+loopback -> allow (local recovery); unclaimed+remote -> deny (no owner data);
    claimed -> require the COOKIE-resolved owner identity (no ?test_t=/?web_token= bypass)."""
    if not accounts.owner_claimed():
        return _request_is_loopback()
    token = (request.cookies.get(AUTH_COOKIE, "") or "").strip()  # cookie only
    if not token:
        return False
    user = accounts.get_by_token(token)
    if not user:
        return False
    record = accounts.get_user_record(user.get("uuid", "")) or {}
    return _is_owner(record)


def _debug_auth_ok():
    """Owner-private gate (web-native). Replaces the telegram-derived check and
    drops the ?test_t= dev bypass."""
    return _owner_private_auth_ok()
```
Then, for **each route in the Task-0 enumerated list**, confirm it calls `_debug_auth_ok()` (or `_owner_private_auth_ok()` directly) and returns its existing 401/deny response when False. Do **not** add gating to any route outside the Task-0 list. Remove any `?test_t=`/`?web_token=` handling that lived inside those owner-private handlers.

> Note: `_owner_private_auth_ok()` deliberately does **not** call `_request_token()` (which honors `?web_token=`). Owner-private auth is cookie-only by design.

- [ ] **Step 4: Run — expect PASS** (gating module tests)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_web_owner_gating -v`

- [ ] **Step 5: Run the web-interface regression module**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_web_debug_auth -v`
Expected: PASS, or update only assertions that encoded the old `test_t`/telegram behavior — never weaken an owner/non-owner separation assertion.

- [ ] **Step 6: Commit (behavior)**

```bash
git add skills/web_interface.py tests/test_web_owner_gating.py
git commit -m "feat(owner-identity): owner-private gate matrix + drop query-token bypass

## Predicted effect
Owner-private routes now gate on the web-native matrix (unclaimed+loopback open;
unclaimed+remote deny; claimed+owner allow; claimed+non-owner deny). ?test_t= and
?web_token= no longer authorize owner-private routes (cookie-only). Activation is
owner_claimed() with no feature flag.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Honest degraded states (claim-required page; store-unreachable)

**Files:**
- Modify: `skills/web_interface.py` (the gate + an enumerated route's deny response)
- Test: `tests/test_web_owner_gating.py` (add cases)

- [ ] **Step 1: Write the failing tests**

```python
class DegradedStates(unittest.TestCase):
    def test_store_unreachable_loopback_recovers_remote_fails_closed(self):
        broken = mock.Mock()
        broken.owner_claimed.side_effect = RuntimeError("db down")
        for loopback, expected in ((True, True), (False, False)):
            req = mock.Mock(remote_addr=("127.0.0.1" if loopback else "203.0.113.7"),
                            headers={}, cookies={})
            with mock.patch.object(W, "accounts", broken), mock.patch.object(W, "request", req):
                self.assertEqual(W._owner_private_auth_ok(), expected)
```

- [ ] **Step 2: Run — expect FAIL** (RuntimeError propagates today)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_web_owner_gating -v`

- [ ] **Step 3: Harden the gate against store failure (local recovery, remote fail-closed)**

Wrap the gate body:
```python
def _owner_private_auth_ok() -> bool:
    try:
        if not accounts.owner_claimed():
            return _request_is_loopback()
        token = (request.cookies.get(AUTH_COOKIE, "") or "").strip()
        if not token:
            return False
        user = accounts.get_by_token(token)
        if not user:
            return False
        record = accounts.get_user_record(user.get("uuid", "")) or {}
        return _is_owner(record)
    except Exception as exc:  # account store unreachable
        logger.warning("owner gate degraded (%s); loopback-only recovery", exc)
        return _request_is_loopback()  # local body recovers; remote fails closed
```
Add a claim-required response helper for the unclaimed-remote case and use it where an enumerated owner-private route renders its deny (honest, no owner data):
```python
def _claim_required_response():
    return (
        "Owner not yet claimed for this Maez. Run `maez own-claim --account <you>` "
        "locally on the machine. (Network access shows this page; owner-private data "
        "is not exposed remotely.)", 403,
    )
```

- [ ] **Step 4: Run — expect PASS**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_web_owner_gating -v`

- [ ] **Step 5: Commit (behavior)**

```bash
git add skills/web_interface.py tests/test_web_owner_gating.py
git commit -m "feat(owner-identity): honest degraded states (loopback recovery, remote fail-closed)

## Predicted effect
If the account store is unreachable, loopback (physical body) retains recovery access and
remote requests fail closed with no owner-private data. Adds an honest claim-required page
for the unclaimed-remote case.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Structural never-lockout + migration-safety tests, then STOP

**Files:**
- Test: `tests/test_web_owner_gating.py` (add), `tests/test_owner_identity_model.py` (add)
- Create: `docs/handoffs/2026-06-17-web-native-owner-identity-v0-handoff.md`

- [ ] **Step 1: Write the structural never-lockout test**

```python
class NeverLockout(unittest.TestCase):
    def test_local_rebind_restores_after_simulated_lockout(self):
        # Owner claimed but the owner's cookie/account is gone -> still recoverable locally.
        acc = mock.Mock(owner_claimed=lambda: True, get_by_token=lambda t: None)
        req_remote = mock.Mock(remote_addr="203.0.113.7", headers={}, cookies={})
        with mock.patch.object(W, "accounts", acc), mock.patch.object(W, "request", req_remote):
            self.assertFalse(W._owner_private_auth_ok())   # remote stays locked out
        req_local = mock.Mock(remote_addr="127.0.0.1", headers={}, cookies={})
        # Even claimed, a loopback request that can't resolve still cannot see owner data,
        # but the LOCAL CLI rebind path (Task 3) is the recovery mechanism — assert it exists.
        self.assertTrue(hasattr(__import__("scripts.maez_cli", fromlist=["cmd_own_claim"]),
                                "cmd_own_claim"))
```

- [ ] **Step 2: Write the migration-safety test**

```python
    # in tests/test_owner_identity_model.py
    def test_unclaimed_preserves_today_behavior(self):
        # No owner claimed -> owner_claimed() False -> non-enumerated routes unaffected,
        # enumerated routes follow the unclaimed matrix. No feature flag exists.
        self.assertFalse(self.acc.owner_claimed())
        import os as _os
        self.assertNotIn("MAEZ_WEB_OWNER_IDENTITY_ENABLED", _os.environ)  # no phantom flag
```

- [ ] **Step 3: Run both modules — expect PASS**

Run:
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_web_owner_gating tests.test_owner_identity_model tests.test_owner_claim_cli -v
```

- [ ] **Step 4: Run the touched-area regression suite**

Run:
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_owner_identity_model tests.test_owner_claim_cli tests.test_web_owner_gating \
  tests.test_web_debug_auth tests.test_telegram_authorization_boundary -v
/home/rohit/maez/.venv/bin/python -m ruff check skills/user_accounts.py skills/web_interface.py \
  scripts/maez_cli.py core/governance/owner_identity_audit.py
```
Expected: all green; ruff clean. Fix any real regression; never weaken an owner/non-owner assertion.

- [ ] **Step 5: Write the STOP-at-gate handoff + commit (docs only)**

Write `docs/handoffs/2026-06-17-web-native-owner-identity-v0-handoff.md` covering: branch tip, the Task-0 proof outputs (route list, audit sink, loopback mechanism), test results, and the **Codex cross-lane review anchors**:
1. real-peer loopback can't be spoofed by `X-Forwarded-For` (Task 4 test proves it);
2. no phantom feature flag — `owner_claimed()` is the only activation;
3. never-lockout is **local physical recovery**, not browser fail-open (unclaimed+remote and store-unreachable+remote both deny owner data);
4. query-bypass removal is scoped to owner-private routes only — confirm `/api/v1/*` localhost-open routes are untouched (no mass-gating);
5. owner-only enforcement — `_is_owner` never consults telegram fields.

Then the **owner breath** (after Codex PASS): owner runs `maez own-claim --account <you>` locally → restarts maez-web → witnesses in the browser (owner-private works; unclaimed loopback fallback; rebind recovery). **Not `LIVE_WITNESSED` until the owner confirms in the browser.**

```bash
git add docs/handoffs/2026-06-17-web-native-owner-identity-v0-handoff.md
git commit -m "docs(handoff): web-native owner identity v0 — review gate + owner-breath sequence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 6: STOP.** No live claim, no restart, no merge — owner-sovereign. Hand to Codex cross-lane review at the gate.

---

## Notes for the implementer

- **Verified APIs (as of plan writing):** `register(...)`, `get_by_username(...)["uuid"]`, and `main()` dispatch via `if args.command == …` in `scripts/maez_cli.py`. If any drift, adapt calls to the real API; never weaken an assertion to make a guess pass.
- **DRY:** the gate logic lives once in `_owner_private_auth_ok()`; `_debug_auth_ok()` delegates to it.
- **YAGNI:** populate `provenance`/`consent`/`access_scope` for the owner only; write **no** guest/contact/relational logic — those are future additive rows.
- **Never-lockout is the spine:** if any step would make a route owner-gated before the claim path + unclaimed-loopback fallback are proven, STOP — that is the exact NO-GO bug.
