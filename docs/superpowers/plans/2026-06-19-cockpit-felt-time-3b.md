# Cockpit Felt-Time (Organ 3b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn ON felt-time (Maez's felt sense of time since last owner contact) for the cockpit owner turn — telegram parity for inner-life continuity — granted ONLY on (flag ∧ proven-owner-marker ∧ S7-trusted).

**Architecture:** Add a web-native `cockpit` owner-auth pairing; the web proxy stamps a proven-owner marker (strict cookie check, NOT the broad access gate); the daemon mints cockpit felt-time only when the dedicated `MAEZ_COCKPIT_FELT_TIME` flag AND the marker are present; a bounded `run_inbound_turn` call-gate honors the cockpit flag without touching any other surface. One global one-being felt-time clock.

**Tech Stack:** Python 3, Flask, `core/evolution/subjective_duration.py`, `daemon/inbound_core.py`, `daemon/maez_daemon.py`, `skills/web_interface.py`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-06-19-cockpit-felt-time-3b-design.md` (@7b2d091).

---

## Lane discipline

- Test runner: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v` — named modules only, NEVER full-discover. **Web/daemon-touching modules need `MAEZ_CONFIG=/home/rohit/maez/config`** in the worktree (worktree-floor confound).
- Branch (use `superpowers:using-git-worktrees`): `cockpit-felt-time-3b`, based on `main` @`e987e29`. `main` local-only — **no push**.
- `## Predicted effect` on behavior commits; docs/proof/test-only omit it. End commits with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **STOP at the review gate** (after Task 5). No merge/restart/flag-flip (owner-sovereign). Cross-lane Codex review at the gate.
- **Scope guard:** touch ONLY `core/evolution/subjective_duration.py`, `daemon/inbound_core.py`, `daemon/maez_daemon.py`, `skills/web_interface.py`, their tests, and the proof/handoff docs. NO tools/cards/search/action-engine (3c), NO web `/chat`, NO voice, NO telegram-path change.

## The three gates (the covenant invariant)

Felt-time is granted ONLY on **(1) `MAEZ_COCKPIT_FELT_TIME` ON ∧ (2) the proven-owner marker ∧ (3) the S7-trusted call)**. The **no-leak** safety: the cockpit factory gates on the flag itself, so the global `MAEZ_SURFACE_PARITY_ENABLED` can never leak cockpit felt-time without the cockpit flag+marker. The marker is the **strict** `_request_has_web_owner_cookie()` (claimed cookie → `_is_owner`), NOT the broad never-lockout `_owner_private_auth_ok()`.

## File structure

- **Modify** `core/evolution/subjective_duration.py` — add the `cockpit`/`cockpit_web_owner` OWNER_AUTH pairing.
- **Modify** `daemon/inbound_core.py` — add the `felt_time_enabled` param + the `or` to the call-gate.
- **Modify** `skills/web_interface.py` — add `_request_has_web_owner_cookie()` + the marker constant; stamp the marker in `api_cockpit_message` only on the strict proof.
- **Modify** `daemon/maez_daemon.py` — add `cockpit_felt_time_enabled()` + the marker constant; mint cockpit felt-time in `_build_cockpit_inbound_descriptor`; read the marker in `/message`.
- **Modify** `tests/test_cockpit_inbound_core.py`, plus tests in `tests/test_subjective_duration_prompt_integration.py` (or a focused new module) and the web test module.
- **Create** `docs/proof/2026-06-19-cockpit-felt-time-3b-task0.md` (Task 0).

---

### Task 0: HARD PROOF GATE (docs/proof only — committed first, REPO-WIDE)

**Files:** Create `docs/proof/2026-06-19-cockpit-felt-time-3b-task0.md`

- [ ] **Step 1: Blast-radius — every `run_inbound_turn` caller (repo-wide)**
```bash
cd <worktree>
grep -rn "run_inbound_turn(\|owner_auth_factory\|felt_time_enabled\|surface_parity_enabled" \
  daemon/ skills/ core/ tests/ ui/ web/ scripts/
```
Enumerate EVERY `run_inbound_turn(**...)` caller and the descriptor it passes. Prove: adding `felt_time_enabled: bool = False` to the signature + `or felt_time_enabled` to the gate changes behavior for ONLY the cockpit descriptor — every other descriptor omits the key → defaults False → its `owner_auth_factory()` call path is byte-identical. List each caller + its `owner_auth_factory`.

- [ ] **Step 2: Telegram-unaffected proof**

Confirm telegram mints felt-time in its OWN path (`skills/telegram_voice.py:2957`, `SubjectiveDurationOwnerAuth(surface="telegram_owner", proof="telegram_authorized_user")`), and that telegram's `run_inbound_turn` descriptor (if `MAEZ_INBOUND_CORE_V2` routes telegram through the core) does NOT set `felt_time_enabled`. So 3b cannot change telegram's felt-time either way. Record the telegram descriptor's `owner_auth_factory`.

- [ ] **Step 3: Marker strictness — strict helper must exclude the loopback paths**

Read `_owner_private_auth_ok` (`skills/web_interface.py:9783`) and quote its three True paths: claimed+cookie→`_is_owner` (`:9797-9798`), unclaimed+loopback (`:9789-9790`), degraded-store→loopback (`:9799-9801`). Prove the new `_request_has_web_owner_cookie()` must return **False** on the two loopback paths (so it returns False exactly where the access gate returns True-via-loopback). Confirm `accounts.owner_claimed`, `accounts.get_by_token`, `accounts.get_user_record`, `AUTH_COOKIE`, `_is_owner` are all already imported/defined in the module.

- [ ] **Step 4: OWNER_AUTH validation + existing-test inventory**
```bash
sed -n '37,72p' core/evolution/subjective_duration.py     # SURFACES/PROOFS/PAIRINGS + dataclass
grep -n "owner_auth_factory\|assertIsNone" tests/test_cockpit_inbound_core.py
```
Confirm: the new `("cockpit","cockpit_web_owner")` pair will pass `__post_init__` (both added to SURFACES/PROOFS/PAIRINGS); a mismatched pair still raises. Confirm `tests/test_cockpit_inbound_core.py:221` asserts `descriptor["owner_auth_factory"]()` is None — with the new `owner_authenticated` defaulting False AND the flag off, **it STAYS None** (so it should NOT break; verify by reading the test's setup — is `MAEZ_COCKPIT_FELT_TIME` unset there?).

- [ ] **Step 5: Flag default + one-being clock**

Confirm `MAEZ_COCKPIT_FELT_TIME` is unset (default OFF via `strict_env_flag`). Confirm the felt-time store is a single global `subjective_duration_samples` table (`core/evolution/subjective_duration.py` — grep `subjective_duration_samples`), NOT per-surface — so the cockpit `owner_contact` updates the same clock telegram does (one being). End the doc with `TASK 0 VERDICT: GO` or `NO-GO — <reason>`.

- [ ] **Step 6: Commit (docs only)**
```bash
git add docs/proof/2026-06-19-cockpit-felt-time-3b-task0.md
git commit -m "docs(proof): cockpit-felt-time-3b Task 0 — blast-radius, telegram-unaffected, marker strictness

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1: The `cockpit` OWNER_AUTH pairing (isolated foundation)

**Files:** Modify `core/evolution/subjective_duration.py:37-71`. Test: `tests/test_subjective_duration_cockpit_pairing.py` (new, focused).

- [ ] **Step 1: Write the failing test** — create `tests/test_subjective_duration_cockpit_pairing.py`:
```python
import unittest
from core.evolution.subjective_duration import SubjectiveDurationOwnerAuth


class CockpitOwnerAuthPairing(unittest.TestCase):
    def test_cockpit_pair_constructs(self):
        auth = SubjectiveDurationOwnerAuth(surface="cockpit", proof="cockpit_web_owner")
        self.assertEqual(auth.surface, "cockpit")
        self.assertEqual(auth.proof, "cockpit_web_owner")

    def test_cockpit_surface_with_wrong_proof_raises(self):
        with self.assertRaises(ValueError):
            SubjectiveDurationOwnerAuth(surface="cockpit", proof="telegram_authorized_user")

    def test_unknown_cockpit_proof_alone_raises(self):
        with self.assertRaises(ValueError):
            SubjectiveDurationOwnerAuth(surface="telegram_owner", proof="cockpit_web_owner")
```

- [ ] **Step 2: Run — expect FAIL** (`"cockpit"` not in SURFACES → `ValueError("unknown ... surface")`)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_subjective_duration_cockpit_pairing -v`

- [ ] **Step 3: Add the pairing.** In `core/evolution/subjective_duration.py`, extend the three structures and BOTH `Literal[...]` hints:
```python
OWNER_AUTH_SURFACES = frozenset({"daemon_owner", "telegram_owner", "web_owner_bridge", "cockpit", "manual_test"})
OWNER_AUTH_PROOFS = frozenset(
    {
        "daemon_reviewed_owner_auth",
        "telegram_authorized_user",
        "web_private_owner_bridge",
        "cockpit_web_owner",
        "manual_test",
    }
)
OWNER_AUTH_PAIRINGS = {
    "daemon_owner": "daemon_reviewed_owner_auth",
    "telegram_owner": "telegram_authorized_user",
    "web_owner_bridge": "web_private_owner_bridge",
    "cockpit": "cockpit_web_owner",
    "manual_test": "manual_test",
}
```
And in the dataclass, add to BOTH `Literal[...]`:
```python
    surface: Literal["daemon_owner", "telegram_owner", "web_owner_bridge", "cockpit", "manual_test"]
    proof: Literal[
        "daemon_reviewed_owner_auth",
        "telegram_authorized_user",
        "web_private_owner_bridge",
        "cockpit_web_owner",
        "manual_test",
    ]
```
(Web-native — `cockpit_web_owner`, NOT `private_owner_bridge`.)

- [ ] **Step 4: Run — expect PASS**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_subjective_duration_cockpit_pairing -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/evolution/subjective_duration.py tests/test_subjective_duration_cockpit_pairing.py
git add core/evolution/subjective_duration.py tests/test_subjective_duration_cockpit_pairing.py
git commit -m "feat(felt-time): add the web-native cockpit OWNER_AUTH pairing

## Predicted effect
SubjectiveDurationOwnerAuth now accepts (surface=cockpit, proof=cockpit_web_owner) — the web-native
owner-auth the cockpit felt-time turn will mint. A mismatched pair still raises. No behavior change to
existing surfaces (additive enum entries). Never private_owner_bridge.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: The `run_inbound_turn` call-gate (bounded, cockpit-only)

**Files:** Modify `daemon/inbound_core.py` (`run_inbound_turn` signature + the `surface_parity_enabled()` gate, ~:417). Test: `tests/test_inbound_core_felt_time_gate.py` (new, focused).

- [ ] **Step 1: Write the failing test** — create `tests/test_inbound_core_felt_time_gate.py`:
```python
import inspect
import unittest
from unittest import mock
from daemon import inbound_core


class RunInboundTurnFeltTimeGate(unittest.TestCase):
    def test_signature_has_felt_time_enabled_default_false(self):
        sig = inspect.signature(inbound_core.run_inbound_turn)
        self.assertIn("felt_time_enabled", sig.parameters)
        self.assertEqual(sig.parameters["felt_time_enabled"].default, False)

    def test_gate_source_honors_felt_time_enabled(self):
        # The gate must call the factory when surface_parity OR felt_time_enabled.
        src = inspect.getsource(inbound_core.run_inbound_turn)
        self.assertIn("surface_parity_enabled() or felt_time_enabled", src)
```
> Source-assert is the hermetic way to pin the gate without running the full async turn (which needs a live daemon). The behavioral effect — "factory called when `felt_time_enabled` even if parity off" — is proven end-to-end in Task 4's daemon descriptor tests + the live witness.

- [ ] **Step 2: Run — expect FAIL** (no `felt_time_enabled` param / gate text)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_inbound_core_felt_time_gate -v`

- [ ] **Step 3: Add the param + widen the gate.** In `daemon/inbound_core.py`, add `felt_time_enabled: bool = False` to the `run_inbound_turn` keyword-only params (near `owner_auth_factory`), and change the gate:
```python
        subjective_duration_owner_auth = None
        if surface_parity_enabled() or felt_time_enabled:
            try:
                subjective_duration_owner_auth = owner_auth_factory()
            except Exception:
                logger.debug(
                    "subjective duration auth construction failed",
                    exc_info=True,
                )
```
(Default False → every existing caller/descriptor that omits the key is byte-identical: when parity is off and `felt_time_enabled` defaults False, the factory is NOT called, exactly as today.)

- [ ] **Step 4: Run — expect PASS** (+ the existing inbound_core suite stays green)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_inbound_core_felt_time_gate -v`
Then the existing cockpit inbound suite (regression, with the env): `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_inbound_core -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check daemon/inbound_core.py tests/test_inbound_core_felt_time_gate.py
git add daemon/inbound_core.py tests/test_inbound_core_felt_time_gate.py
git commit -m "feat(felt-time): run_inbound_turn honors a per-descriptor felt_time_enabled gate

## Predicted effect
run_inbound_turn now calls owner_auth_factory() when surface_parity_enabled() OR felt_time_enabled (new
keyword, default False). Descriptors that omit the key (telegram, web, every non-cockpit caller) are
byte-identical to today. This lets the cockpit grant felt-time on its own flag without flipping the
global parity flag.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: The strict owner marker (web side)

**Files:** Modify `skills/web_interface.py` (add `_request_has_web_owner_cookie()` + `_OWNER_AUTHENTICATED_HEADER`; stamp the marker in `api_cockpit_message`). Test: `tests/test_cockpit_proxies_2026_05_05.py` (add to it).

- [ ] **Step 1: Write the failing tests** — ADD to `tests/test_cockpit_proxies_2026_05_05.py` (it has `self.client` + `_make_urlopen_response`; read it first, add don't clobber):
```python
class CockpitOwnerMarker(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as wi
        self.wi = wi
        wi.app.config["TESTING"] = True
        self.client = wi.app.test_client()

    def _send_capturing(self):
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["req"] = req
            return _make_urlopen_response(b'{"reply":"ok"}', status=200)
        return captured, fake_urlopen

    def test_claimed_owner_cookie_stamps_marker(self):
        captured, fake = self._send_capturing()
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.object(self.wi, "_request_has_web_owner_cookie", return_value=True), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(captured["req"].get_header("X-maez-owner-authenticated"), "1")

    def test_local_recovery_send_allowed_marker_absent(self):
        # _owner_private_auth_ok True (loopback recovery) but strict proof False -> send, NO marker
        captured, fake = self._send_capturing()
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=True), \
             mock.patch.object(self.wi, "_request_has_web_owner_cookie", return_value=False), \
             mock.patch.dict(os.environ, {"S7_INTERNAL_CHANNEL_TOKEN": "t"}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(captured["req"].get_header("X-maez-owner-authenticated"))

    def test_non_owner_401_no_send(self):
        with mock.patch.object(self.wi, "_owner_private_auth_ok", return_value=False):
            r = self.client.post("/api/v1/cockpit/message", json={"text": "hi"})
        self.assertEqual(r.status_code, 401)


class RequestHasWebOwnerCookie(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as wi
        self.wi = wi
        wi.app.config["TESTING"] = True

    def _call_in_request(self, **patches):
        with self.wi.app.test_request_context("/", headers={}):
            with mock.patch.multiple(self.wi.accounts, **patches):
                return self.wi._request_has_web_owner_cookie()

    def test_unclaimed_returns_false(self):
        self.assertFalse(self._call_in_request(owner_claimed=mock.Mock(return_value=False)))

    def test_store_error_returns_false(self):
        self.assertFalse(self._call_in_request(
            owner_claimed=mock.Mock(side_effect=RuntimeError("db down"))))

    def test_claimed_owner_cookie_returns_true(self):
        with self.wi.app.test_request_context("/", headers={"Cookie": f"{self.wi.AUTH_COOKIE}=tok"}):
            with mock.patch.multiple(
                self.wi.accounts,
                owner_claimed=mock.Mock(return_value=True),
                get_by_token=mock.Mock(return_value={"uuid": "u1"}),
                get_user_record=mock.Mock(return_value={"web_owner": 1}),
            ), mock.patch.object(self.wi, "_is_owner", return_value=True):
                self.assertTrue(self.wi._request_has_web_owner_cookie())
```
> Adjust `mock.patch.multiple(self.wi.accounts, ...)` to however the module references the accounts store (it's `accounts.owner_claimed(...)` etc.). If `_is_owner` is the real gate on the record, the claimed test patches it True; the unclaimed/error tests return False before `_is_owner` is reached.

- [ ] **Step 2: Run — expect FAIL** (`_request_has_web_owner_cookie` undefined; no marker on the Request)

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_proxies_2026_05_05 -v`

- [ ] **Step 3: Add the strict helper + the constant, and stamp the marker.** In `skills/web_interface.py`, near `_owner_private_auth_ok` (~:9783):
```python
_OWNER_AUTHENTICATED_HEADER = "X-Maez-Owner-Authenticated"


def _request_has_web_owner_cookie() -> bool:
    """Stricter than _owner_private_auth_ok: a COOKIE that resolves to a CLAIMED web_owner.
    No unclaimed-loopback recovery, no degraded-store fallback — felt-time (owner-only inner
    life) requires proven owner identity, not access. Returns False on any uncertainty."""
    try:
        if not accounts.owner_claimed():
            return False
        token = (request.cookies.get(AUTH_COOKIE, "") or "").strip()
        if not token:
            return False
        user = accounts.get_by_token(token)
        if not user:
            return False
        record = accounts.get_user_record(user.get("uuid", "")) or {}
        return _is_owner(record)
    except Exception:
        return False
```
Then in `api_cockpit_message` (~:1764, after the existing owner gate + `s7_headers` block, where `headers` is built), stamp the marker only on the strict proof:
```python
    headers = {
        "Content-Type": request.headers.get("Content-Type", "application/json"),
        **s7_headers,
    }
    if _request_has_web_owner_cookie():
        headers[_OWNER_AUTHENTICATED_HEADER] = "1"
```
(The send itself stays gated on the existing `_owner_private_auth_ok()` from 3a — never-lockout. Only the marker is strict.)

- [ ] **Step 4: Run — expect PASS** (new classes + every existing test in the module)

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_proxies_2026_05_05 -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check skills/web_interface.py tests/test_cockpit_proxies_2026_05_05.py
git add skills/web_interface.py tests/test_cockpit_proxies_2026_05_05.py
git commit -m "feat(felt-time): stamp the proven-owner marker on the cockpit send (strict, not access)

## Predicted effect
api_cockpit_message now stamps X-Maez-Owner-Authenticated: 1 ONLY when _request_has_web_owner_cookie()
(claimed cookie -> _is_owner) is True — proven owner, not mere access. The send stays allowed by the
broad _owner_private_auth_ok() gate, so local-recovery / degraded-store sessions can still talk to Maez
but earn no marker (and thus no felt-time). Non-owner still 401s.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: The daemon cockpit felt-time wiring (flag + mint + marker read)

**Files:** Modify `daemon/maez_daemon.py` (`cockpit_felt_time_enabled()`, `_OWNER_AUTHENTICATED_HEADER`, `_build_cockpit_inbound_descriptor`, the `/message` cockpit branch). Test: `tests/test_cockpit_inbound_core.py` (add + update the existing assertion).

- [ ] **Step 1: Write the failing tests** — ADD to `tests/test_cockpit_inbound_core.py` (read it first; reuse its imports/harness). The existing `:221` `assertIsNone(descriptor["owner_auth_factory"]())` stays (flag-off default). Add:
```python
class CockpitFeltTimeDescriptor(unittest.TestCase):
    def _descriptor(self, *, flag, owner_authenticated):
        from daemon import maez_daemon as md
        env = {"MAEZ_COCKPIT_FELT_TIME": "1"} if flag else {}
        with mock.patch.dict(os.environ, env, clear=False):
            if not flag:
                os.environ.pop("MAEZ_COCKPIT_FELT_TIME", None)
            return md._build_cockpit_inbound_descriptor(
                _FakeDaemon(), text="hi", chat_history=None,
                owner_authenticated=owner_authenticated,
            )

    def test_flag_off_factory_none_even_with_marker(self):
        d = self._descriptor(flag=False, owner_authenticated=True)
        self.assertIsNone(d["owner_auth_factory"]())
        self.assertFalse(d["felt_time_enabled"])

    def test_flag_on_no_marker_factory_none(self):
        d = self._descriptor(flag=True, owner_authenticated=False)
        self.assertIsNone(d["owner_auth_factory"]())
        self.assertFalse(d["felt_time_enabled"])

    def test_flag_on_with_marker_mints_cockpit_auth(self):
        d = self._descriptor(flag=True, owner_authenticated=True)
        auth = d["owner_auth_factory"]()
        self.assertEqual((auth.surface, auth.proof), ("cockpit", "cockpit_web_owner"))
        self.assertTrue(d["felt_time_enabled"])

    def test_no_leak_via_surface_parity(self):
        # Global parity ON but cockpit flag OFF -> still None (factory gates on the flag itself).
        with mock.patch("daemon.inbound_core.surface_parity_enabled", return_value=True):
            d = self._descriptor(flag=False, owner_authenticated=True)
            self.assertIsNone(d["owner_auth_factory"]())
```
> Reuse the module's existing `_FakeDaemon` (or the minimal daemon stub the file already uses to call `_build_cockpit_inbound_descriptor`). If the file builds the descriptor differently, match its existing pattern. The no-leak test asserts the FACTORY returns None regardless of parity — the factory is the safety gate.

ALSO add a `/message` marker-read test (reuse the `_DaemonAppClientMixin` captured-app client from `tests/test_s7_1_daemon_internal_channel.py` if this module imports it, or assert at the descriptor-call boundary): an S7-trusted POST with `X-Maez-Owner-Authenticated: 1` → the handler passes `owner_authenticated=True` into `_build_cockpit_inbound_descriptor`; without the header → False. (Patch `_build_cockpit_inbound_descriptor` to capture its `owner_authenticated` kwarg.)

- [ ] **Step 2: Run — expect FAIL** (`owner_authenticated` kwarg unknown; no `felt_time_enabled` key)

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_inbound_core -v`

- [ ] **Step 3: Add the flag helper + constant + mint + marker read.** In `daemon/maez_daemon.py`:

(a) Near `cockpit_core_enabled` (~:2579):
```python
def cockpit_felt_time_enabled() -> bool:
    """Return True iff ``MAEZ_COCKPIT_FELT_TIME`` is 1/true/yes/on. DEFAULT OFF.
    Gates whether the cockpit owner turn mints felt-time (owner-only inner life)."""
    from core.infra.env_flags import strict_env_flag
    return strict_env_flag("MAEZ_COCKPIT_FELT_TIME")


_OWNER_AUTHENTICATED_HEADER = "X-Maez-Owner-Authenticated"
```

(b) `_build_cockpit_inbound_descriptor` — add the kwarg + the conditional mint. Change the signature and the `owner_auth_factory` line:
```python
def _build_cockpit_inbound_descriptor(daemon, *, text: str, chat_history, owner_authenticated: bool = False) -> dict:
    ...
    from core.evolution.subjective_duration import SubjectiveDurationOwnerAuth
    felt_time_on = cockpit_felt_time_enabled() and owner_authenticated
    ...
    return dict(
        ...
        owner_auth_factory=(
            (lambda: SubjectiveDurationOwnerAuth(surface="cockpit", proof="cockpit_web_owner"))
            if felt_time_on else (lambda: None)
        ),
        felt_time_enabled=felt_time_on,
        ...
    )
```
(Keep every other descriptor key unchanged. `felt_time_enabled` is now a key in the dict → it splats into `run_inbound_turn(**descriptor)`, which accepts it as of Task 2.)

(c) The `/message` cockpit branch (~:10716) — read the marker inside the S7-gated handler and pass it:
```python
            if cockpit_core_enabled():
                from daemon.inbound_core import run_inbound_turn
                owner_authenticated = request.headers.get(_OWNER_AUTHENTICATED_HEADER) == "1"
                descriptor = _build_cockpit_inbound_descriptor(
                    self,
                    text=text,
                    chat_history=chat_history,
                    owner_authenticated=owner_authenticated,
                )
```
(The handler is already S7-gated by 3a, so the marker is only trustable here.)

- [ ] **Step 4: Run — expect PASS** (new + the existing `:221` assertion, which stays None at flag-off default)

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_cockpit_inbound_core -v`

- [ ] **Step 5: ruff + commit (behavior)**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check daemon/maez_daemon.py tests/test_cockpit_inbound_core.py
git add daemon/maez_daemon.py tests/test_cockpit_inbound_core.py
git commit -m "feat(felt-time): mint cockpit felt-time on (flag AND proven-owner marker AND S7)

## Predicted effect
The cockpit owner turn now mints SubjectiveDurationOwnerAuth(cockpit, cockpit_web_owner) — and thus felt
time — only when MAEZ_COCKPIT_FELT_TIME is on AND the S7-gated /message carries the proven-owner marker.
Flag off, or marker absent, keeps owner_auth_factory()=None (today's behavior). The factory gates on the
flag itself, so the global surface_parity flag cannot leak cockpit felt-time. One global one-being clock.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: STOP-at-gate handoff

**Files:** Create `docs/handoffs/2026-06-19-cockpit-felt-time-3b-handoff.md`.

- [ ] **Step 1: Whole-organ green + ruff**
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_subjective_duration_cockpit_pairing tests.test_inbound_core_felt_time_gate \
  tests.test_cockpit_proxies_2026_05_05 tests.test_cockpit_inbound_core -v
/home/rohit/maez/.venv/bin/python -m ruff check core/evolution/subjective_duration.py daemon/inbound_core.py daemon/maez_daemon.py skills/web_interface.py tests/test_subjective_duration_cockpit_pairing.py tests/test_inbound_core_felt_time_gate.py
```
Expected: all green; ruff clean.

- [ ] **Step 2: Write the handoff + commit (docs).** Cover: branch tip, the Task-0 verdict, the diff, test results, and the **Codex cross-lane anchors**: (1) **three gates** — felt-time only on flag ∧ proven-owner-marker ∧ S7; (2) **strict marker, not access-laundering** — the marker uses `_request_has_web_owner_cookie()` (claimed cookie → `_is_owner`), NOT the broad `_owner_private_auth_ok()`; local-recovery/degraded sessions send but earn no marker (test-proven); (3) **no-leak-via-parity** — the factory gates on the flag itself, so `MAEZ_SURFACE_PARITY_ENABLED` can't leak cockpit felt-time (test-proven); (4) **web-native pairing** — `(cockpit, cockpit_web_owner)`, never `private_owner_bridge`; (5) **inbound_core cockpit-only** — `felt_time_enabled` defaults False, every other descriptor byte-identical (Task-0 blast-radius + the gate test); (6) **one-being clock** — single global `subjective_duration_samples`, cockpit + telegram share "time since last owner contact"; (7) **felt-time only** — no tools/cards/search/action-engine. Then the **owner breath**: **no new secret** — flip `MAEZ_COCKPIT_FELT_TIME=1` in the daemon env, **restart BOTH `maez` (flag) and `maez-web` (marker-stamping code)**, then witness: (a) cockpit message after a quiet stretch → Maez's reply carries the felt sense; (b) cross-surface — a telegram message then a cockpit message → "you were just here" (shared clock); (c) flag OFF (default) → 3a baseline, no felt-time; (d) non-owner / unclaimed-loopback session → no felt-time. **Not `LIVE_WITNESSED` until the owner confirms.**
```bash
git add docs/handoffs/2026-06-19-cockpit-felt-time-3b-handoff.md
git commit -m "docs(handoff): cockpit felt-time 3b — review gate + owner-breath sequence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 3: STOP.** No merge/restart/flag — owner-sovereign. Hand to Codex cross-lane review.

---

## Notes for the implementer

- **The three gates are the whole point** — felt-time grants ONLY on flag ∧ proven-owner-marker ∧ S7. Each is independently tested; don't collapse them.
- **Strict ≠ broad** — the marker uses `_request_has_web_owner_cookie()` (proven owner), the SEND uses `_owner_private_auth_ok()` (never-lockout access). Do not swap them.
- **The factory is the safety gate** — it gates on `felt_time_on` (flag ∧ marker), so even if the global parity flag is on, no cockpit felt-time leaks. The `no_leak` test pins this.
- **Cockpit-only blast radius** — `felt_time_enabled` defaults False on `run_inbound_turn`; only the cockpit descriptor sets it. Every other surface is byte-identical (Task 0 proves it repo-wide).
- **Hermetic** — env the flags, mock `accounts` / `_owner_private_auth_ok` / `_request_has_web_owner_cookie`; never the live `users.db`. Web/daemon modules need `MAEZ_CONFIG=/home/rohit/maez/config`.
- **The existing `test_cockpit_inbound_core.py:221` should NOT break** — `owner_authenticated` defaults False + flag off → factory still None. If it breaks, you changed a default wrong.
