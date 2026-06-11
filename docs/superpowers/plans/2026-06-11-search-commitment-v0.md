# Search Commitment v0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Maez hold the thread of its own search offer — it offers a web search only when its search body is healthy, and "yeah sure" fires that exact, low-stakes, sovereign-local search and nothing else.

**Architecture:** A substrate-decided offer→confirm→execute loop. Pure-logic core (typed `OfferReceipt` + a conjunctive resolver) + a swappable `SearchBackend` (SearXNG live, Fake for tests) + capability health, wired at the *proven-live* Telegram↔controller seam, entirely behind a default-off flag and built against a fake so the daemon never needs SearXNG to run the suite.

**Tech Stack:** Python 3.14, stdlib (`dataclasses`, `time`, `re`, `enum`), `httpx` (already used in-tree); SearXNG (owner-installed local service, witness step only).

**Spec:** `docs/superpowers/specs/2026-06-11-search-commitment-v0-design.md` @ `3450729`.

---

## Standing constraints (read first)
- **Lane:** Codex builds / Claude reviews. main local-only @ `3450729` — **never `git push`**.
- **Test runner:** `/home/rohit/maez/.venv/bin/python -B -m unittest <module>` (NOT pytest).
- **Default-OFF:** `MAEZ_SEARCH_COMMITMENT_ENABLED` gates the whole organ. Flag unset ⇒ byte-identical current behavior. A test pins this.
- **`## Predicted effect`** on exactly ONE commit — the Task 6 wiring (the only behavior-touching change; still flag-gated).
- **Co-author trailer** on every commit: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **The daemon never needs SearXNG to test** — daemon-side code uses `FakeSearchBackend`; only `SearxngBackend` touches a live SearXNG, and only behind the flag at the owner witness.
- **STOP at the gate (Task 7):** build everything green-with-Fake, then stop. Installing/starting SearXNG, flipping the flag, restarting — all OWNER breaths.

## Verified code facts (don't re-derive)
- `core/conversation_controller.py` = a shim. Real module: **`core/brain/conversation_controller.py`**.
- `ConversationController` is instantiated live at **`skills/telegram_voice.py:913`** (`self._controller = ConversationController(...)`). That `TelegramVoice` surface is the live seam.
- **`handle_user_message()` (:349) has NO caller** — extraction-in-progress, **NOT the live seam.** Do not wire to it without Task 0 proof.
- Legacy offer-binding methods on the controller: `maybe_store_offer()` (:746), `maybe_store_probe_bridge_offer()` (:791), `consume_offer_approval()` (:843). `has_awaiting_card(channel, chat_id)` (:419).
- `skills/web_search.py:search()` (:26) is the GLOBAL search entry — **do not touch** (v0 scopes SearXNG to the commitment path).

## File structure
| File | Responsibility |
|---|---|
| `core/search/searxng_client.py` (create) | `SearchBackend` interface, `SearxngBackend` (live), `FakeSearchBackend` (tests), `searxng_health()`. |
| `core/search/search_commitment.py` (create) | `OfferReceipt` dataclass, `is_clear_yes()`, `resolve_affirmation()` (the conjunction). Pure logic, no I/O. |
| `core/brain/conversation_controller.py` (modify) | typed offer slot; legacy supersession (3 methods, flag-gated); offer-create + affirmation-resolve at the Task-0 seam. |
| `skills/telegram_voice.py` (modify, per Task 0) | the live witness surface — ensure offer/resolve is reached on a real message. |
| `scripts/maez-searxng.template.service` (create) | inert systemd unit for owner-installed SearXNG. |
| `tests/test_search_commitment.py`, `tests/test_searxng_client.py` (create) | unit tests. |
| `docs/handoffs/2026-06-11-search-commitment-gate.md` (create) | STOP-at-gate witness handoff. |

---

### Task 0: PROVE the live Telegram↔controller seam (diagnostic — NO code, NO commit)

**Why:** `handle_user_message()` is dead (no caller). Wiring offer logic to a dead method ships nothing live. This task produces the *attach-point decision* every later wiring task depends on. `file-exists != runtime-active`.

- [ ] **Step 1: Trace what `TelegramVoice` actually calls on the controller**

```bash
cd /home/rohit/maez
# the controller is created here; find every method TelegramVoice invokes on it
sed -n '900,1000p' skills/telegram_voice.py | grep -nE "_controller\.|self\._controller"
grep -nE "_controller\." skills/telegram_voice.py | head -30
# do the legacy offer methods fire from TelegramVoice (or anywhere live)?
grep -rnE "maybe_store_offer|consume_offer_approval|maybe_store_probe_bridge_offer|has_awaiting_card" skills/ daemon/ | grep -vE "__pycache__|def "
```

- [ ] **Step 2: Find the per-message reply point in `TelegramVoice`**

Identify the method that handles an inbound user message and produces/sends the reply (the one that runs per Telegram turn). That method (or the controller method it delegates to) is the **attach point** for: (a) creating an offer after a search-worthy reply, and (b) resolving an affirmation on the *next* message.

- [ ] **Step 3: Decide and record the attach point** (write findings into the Task 7 handoff doc, "Seam" section). Exactly one of:
  - **(a)** A live controller method (called by `TelegramVoice` per message) exists → wire there.
  - **(b)** No clean controller per-message hook → add a minimal controller API (`store_search_offer(...)`, `resolve_search_affirmation(...)`) and call it from the proven `TelegramVoice` message handler.
  - **(c)** The legacy offer methods *are* fired live from `TelegramVoice` → those call sites are the supersession points for Task 5.

No code lands until this is recorded. **If Task 0 reveals the seam is fundamentally different from this plan's assumption, STOP and escalate** rather than forcing the wiring.

---

### Task 1: `SearchBackend` interface + `FakeSearchBackend`

**Files:** Create `core/search/searxng_client.py`; Create `tests/test_searxng_client.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_searxng_client.py
import unittest
from core.search.searxng_client import SearchBackend, FakeSearchBackend


class FakeBackendTests(unittest.TestCase):
    def test_interface_is_abstract(self):
        with self.assertRaises(TypeError):
            SearchBackend()

    def test_returns_scripted_results_and_records_query(self):
        b = FakeSearchBackend(results=[{"title": "T", "url": "U", "content": "C"}])
        out = b.search("llama.cpp")
        self.assertEqual(out[0]["title"], "T")
        self.assertEqual(b.searched, ["llama.cpp"])

    def test_health_is_scriptable(self):
        self.assertEqual(FakeSearchBackend(health="degraded").health(), "degraded")

    def test_search_can_raise(self):
        with self.assertRaises(RuntimeError):
            FakeSearchBackend(raises=RuntimeError("boom")).search("q")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails** — `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_searxng_client -v` → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Minimal implementation**

```python
# core/search/searxng_client.py
"""Sovereign search body (SearXNG) behind a swappable backend.

The daemon talks to a SearchBackend; only SearxngBackend touches a live SearXNG,
and only behind MAEZ_SEARCH_COMMITMENT_ENABLED at the owner witness. Tests use
FakeSearchBackend — the suite never needs a running SearXNG.
"""
from __future__ import annotations

import abc

HEALTHY, DEGRADED, DOWN = "healthy", "degraded", "down"


class SearchBackend(abc.ABC):
    @abc.abstractmethod
    def search(self, query: str, max_results: int = 8) -> list[dict]:
        raise NotImplementedError

    @abc.abstractmethod
    def health(self) -> str:  # HEALTHY | DEGRADED | DOWN
        raise NotImplementedError


class FakeSearchBackend(SearchBackend):
    """Tests only. Scripted results + scriptable health. Never loads SearXNG."""

    def __init__(self, results=None, health=HEALTHY, raises=None):
        self._results = results if results is not None else [{"title": "t", "url": "u", "content": "c"}]
        self._health = health
        self._raises = raises
        self.searched: list[str] = []

    def search(self, query, max_results=8):
        self.searched.append(query)
        if self._raises is not None:
            raise self._raises
        return list(self._results)[:max_results]

    def health(self):
        return self._health
```

- [ ] **Step 4: Run to verify pass** — `... -m unittest tests.test_searxng_client -v` → PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add core/search/searxng_client.py tests/test_searxng_client.py
git commit -m "feat(search-commitment): SearchBackend interface + FakeSearchBackend

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `SearxngBackend` + `searxng_health` (live client; mocked in tests)

**Files:** Modify `core/search/searxng_client.py`; Modify `tests/test_searxng_client.py`.

- [ ] **Step 1: Write the failing test** (append)

```python
from unittest import mock
from core.search.searxng_client import SearxngBackend, HEALTHY, DEGRADED, DOWN


class SearxngBackendTests(unittest.TestCase):
    def _resp(self, payload, status=200):
        r = mock.Mock(); r.status_code = status
        r.json.return_value = payload; r.raise_for_status.return_value = None
        return r

    def test_search_normalizes_results(self):
        b = SearxngBackend()
        payload = {"results": [{"title": "T", "url": "U", "content": "C", "engine": "brave"}]}
        with mock.patch("core.search.searxng_client.httpx.get", return_value=self._resp(payload)):
            out = b.search("llama.cpp", max_results=8)
        self.assertEqual(out, [{"title": "T", "url": "U", "content": "C"}])

    def test_health_healthy_when_results(self):
        b = SearxngBackend()
        with mock.patch("core.search.searxng_client.httpx.get",
                        return_value=self._resp({"results": [{"title": "x"}], "unresponsive_engines": []})):
            self.assertEqual(b.health(), HEALTHY)

    def test_health_degraded_when_no_results(self):
        b = SearxngBackend()
        with mock.patch("core.search.searxng_client.httpx.get",
                        return_value=self._resp({"results": [], "unresponsive_engines": [["x", "captcha"]]})):
            self.assertEqual(b.health(), DEGRADED)

    def test_health_down_on_transport_error(self):
        b = SearxngBackend()
        with mock.patch("core.search.searxng_client.httpx.get", side_effect=Exception("refused")):
            self.assertEqual(b.health(), DOWN)
```

- [ ] **Step 2: Run to verify it fails** — FAIL (ImportError: SearxngBackend).

- [ ] **Step 3: Minimal implementation** (append to `core/search/searxng_client.py`)

```python
import time

import httpx


class SearxngBackend(SearchBackend):
    """Live SearXNG client. Local JSON API; health cached briefly. CONFIRM the
    /search?q=...&format=json shape in the owner-gated smoke (the audition proved
    it) — adapt here if the live shape differs, do not force."""

    def __init__(self, base_url: str = "http://127.0.0.1:8888", timeout_s: float = 8.0, health_ttl_s: float = 30.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._health_ttl = health_ttl_s
        self._health_val: str | None = None
        self._health_ts = 0.0

    def search(self, query, max_results=8):
        r = httpx.get(self._base + "/search", params={"q": query, "format": "json"}, timeout=self._timeout)
        r.raise_for_status()
        rows = r.json().get("results", [])[:max_results]
        return [{"title": x.get("title"), "url": x.get("url"), "content": x.get("content")} for x in rows]

    def _probe(self) -> str:
        try:
            r = httpx.get(self._base + "/search", params={"q": "healthcheck", "format": "json"}, timeout=self._timeout)
            if r.status_code != 200:
                return DOWN
            return HEALTHY if r.json().get("results") else DEGRADED
        except Exception:
            return DOWN

    def health(self, now: float | None = None) -> str:
        t = time.time() if now is None else now
        if self._health_val is not None and (t - self._health_ts) < self._health_ttl:
            return self._health_val
        self._health_val, self._health_ts = self._probe(), t
        return self._health_val
```

- [ ] **Step 4: Run to verify pass** — PASS (8 tests total).

- [ ] **Step 5: Commit**

```bash
git add core/search/searxng_client.py tests/test_searxng_client.py
git commit -m "feat(search-commitment): SearxngBackend + cached health probe (mocked in tests)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `OfferReceipt` + `is_clear_yes` classifier

**Files:** Create `core/search/search_commitment.py`; Create `tests/test_search_commitment.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_search_commitment.py
import unittest
from core.search.search_commitment import OfferReceipt, is_clear_yes


class ReceiptTests(unittest.TestCase):
    def _r(self, **kw):
        base = dict(action_type="web_search", stakes="low_read", offered_query="llama.cpp news",
                    created_ts=1000.0, ttl_seconds=300.0, ttl_turns=3, requires_confirmation=True,
                    confirmation_mode="clear_yes_ok", executor="searxng",
                    egress_class="sovereign_local_search")
        base.update(kw)
        return OfferReceipt(**base)

    def test_fresh_within_window(self):
        self.assertTrue(self._r().is_fresh(now_ts=1100.0, turns_since=1))

    def test_stale_by_time(self):
        self.assertFalse(self._r().is_fresh(now_ts=1400.0, turns_since=1))

    def test_stale_by_turns(self):
        self.assertFalse(self._r().is_fresh(now_ts=1100.0, turns_since=4))


class ClearYesTests(unittest.TestCase):
    def test_clear_yes(self):
        for t in ["yeah sure", "sure", "yes please", "go ahead", "ok do it", "yep", "yes"]:
            self.assertTrue(is_clear_yes(t), t)

    def test_not_clear_yes(self):
        for t in ["hmm", "k maybe", "not sure", "what do you mean", "no", "later", ""]:
            self.assertFalse(is_clear_yes(t), t)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails** — FAIL (ModuleNotFoundError).

- [ ] **Step 3: Minimal implementation**

```python
# core/search/search_commitment.py
"""Typed search-offer commitments — the dignity fix, made structural.

Pure logic, no I/O: an OfferReceipt born at the substrate's offer decision, and a
conjunctive resolver that fires ONLY a low-stakes, sovereign-local, fresh,
clearly-confirmed, healthy search — never a write, a paid-API egress, a stale
offer, or a search while an approval card is awaiting.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# clear-yes: bias toward following through (a stray search is cheap; the miss is the wound),
# but exclude bare acknowledgments / negations / questions.
_CLEAR_YES = re.compile(
    r"^\s*(yes|yeah|yep|yup|sure|ok(ay)?\s+(do|go|search|please)|go ahead|do it|please do|sounds good|"
    r"yes please|ok do it|search it)\b",
    re.IGNORECASE,
)


def is_clear_yes(text: str) -> bool:
    return bool(_CLEAR_YES.match((text or "").strip()))


@dataclass
class OfferReceipt:
    action_type: str          # "web_search"
    stakes: str               # "low_read"
    offered_query: str        # the EXACT query that may run
    created_ts: float
    ttl_seconds: float
    ttl_turns: int
    requires_confirmation: bool
    confirmation_mode: str    # "clear_yes_ok"
    executor: str             # "searxng"
    egress_class: str         # "sovereign_local_search"

    def is_fresh(self, now_ts: float, turns_since: int) -> bool:
        return (now_ts - self.created_ts) <= self.ttl_seconds and turns_since <= self.ttl_turns
```

- [ ] **Step 4: Run to verify pass** — PASS.

- [ ] **Step 5: Commit**

```bash
git add core/search/search_commitment.py tests/test_search_commitment.py
git commit -m "feat(search-commitment): OfferReceipt + clear_yes_ok classifier

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `resolve_affirmation` conjunction (the trap-proof core)

**Files:** Modify `core/search/search_commitment.py`; Modify `tests/test_search_commitment.py`.

- [ ] **Step 1: Write the failing test** (append) — the three MANDATORY trap-proof tests + the egress rail

```python
from core.search.search_commitment import resolve_affirmation, ResolveDecision


class ResolverTests(unittest.TestCase):
    def _r(self, **kw):
        base = dict(action_type="web_search", stakes="low_read", offered_query="llama.cpp news",
                    created_ts=1000.0, ttl_seconds=300.0, ttl_turns=3, requires_confirmation=True,
                    confirmation_mode="clear_yes_ok", executor="searxng",
                    egress_class="sovereign_local_search")
        base.update(kw)
        return OfferReceipt(**base)

    def _resolve(self, receipt, text, *, health="healthy", card=False):
        return resolve_affirmation(receipt, text, health=health, has_awaiting_card=card,
                                   now_ts=1100.0, turns_since=1)

    def test_happy_path_executes_exact_query(self):
        d = self._resolve(self._r(), "yeah sure")
        self.assertTrue(d.execute)
        self.assertEqual(d.query, "llama.cpp news")  # the egress rail: the STORED query

    def test_no_receipt(self):
        self.assertFalse(self._resolve(None, "yeah sure").execute)

    def test_not_clear_yes(self):
        self.assertFalse(self._resolve(self._r(), "hmm maybe").execute)

    def test_stale(self):
        d = resolve_affirmation(self._r(), "yeah sure", health="healthy", has_awaiting_card=False,
                                now_ts=2000.0, turns_since=1)
        self.assertFalse(d.execute)
        self.assertEqual(d.reason, "stale_offer")

    def test_unhealthy_blocks(self):
        self.assertFalse(self._resolve(self._r(), "yeah sure", health="down").execute)

    # --- the three MANDATORY trap-proof tests ---
    def test_high_stakes_blocked_even_with_clear_yes(self):
        d = self._resolve(self._r(stakes="write"), "yeah sure")
        self.assertFalse(d.execute)
        self.assertEqual(d.reason, "stakes_too_high")

    def test_keyed_egress_blocked_even_with_clear_yes(self):
        d = self._resolve(self._r(egress_class="external_keyed"), "yeah sure")
        self.assertFalse(d.execute)
        self.assertEqual(d.reason, "egress_not_sovereign")

    def test_awaiting_card_wins_over_yes(self):
        d = self._resolve(self._r(), "yeah sure", card=True)
        self.assertFalse(d.execute)
        self.assertEqual(d.reason, "card_precedence")
```

- [ ] **Step 2: Run to verify it fails** — FAIL (ImportError: resolve_affirmation).

- [ ] **Step 3: Minimal implementation** (append to `core/search/search_commitment.py`)

```python
from typing import Optional


@dataclass
class ResolveDecision:
    execute: bool
    reason: str
    query: Optional[str] = None


def resolve_affirmation(receipt, text, *, health, has_awaiting_card, now_ts, turns_since) -> ResolveDecision:
    """The conjunctive gate. Auto-execute ONLY when every guard holds. Order is
    chosen so the safety-critical reasons (card, stakes, egress) are explicit."""
    if receipt is None:
        return ResolveDecision(False, "no_pending_offer")
    if has_awaiting_card:
        return ResolveDecision(False, "card_precedence")        # an approval card wins over a search
    if not is_clear_yes(text):
        return ResolveDecision(False, "not_clear_yes")
    if not receipt.is_fresh(now_ts, turns_since):
        return ResolveDecision(False, "stale_offer")
    if receipt.stakes != "low_read":
        return ResolveDecision(False, "stakes_too_high")        # trap-proof: no write on "sure"
    if receipt.egress_class != "sovereign_local_search":
        return ResolveDecision(False, "egress_not_sovereign")   # trap-proof: no paid-API egress on "sure"
    if health != "healthy":
        return ResolveDecision(False, "search_unhealthy")
    return ResolveDecision(True, "execute", query=receipt.offered_query)  # egress rail: the STORED query only
```

- [ ] **Step 4: Run to verify pass** — `... -m unittest tests.test_search_commitment -v` → PASS (all).

- [ ] **Step 5: Commit**

```bash
git add core/search/search_commitment.py tests/test_search_commitment.py
git commit -m "feat(search-commitment): resolver conjunction + trap-proof (stakes/egress/card) + egress rail

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Legacy supersession — disable all 3 untyped offer writers under the flag

**Files:** Modify `core/brain/conversation_controller.py`; Test: a new `tests/test_conversation_offer_supersession.py`.

**Read first:** Task 0's findings — confirm whether the 3 legacy methods are reached live and from where. Gate them at the method head (earliest, safest): when the flag is on, each returns its inert/no-op value without writing/reading the old offer slot.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_conversation_offer_supersession.py
import os
import unittest
from unittest import mock
from core.brain import conversation_controller as cc


class SupersessionTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None)

    def test_flag_on_short_circuits_all_three(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None))
        ctrl = _make_controller()  # see helper note below
        # none of the legacy writers may touch the old offer slot under the flag
        ctrl.maybe_store_offer(_a_reply_that_would_have_offered())
        ctrl.maybe_store_probe_bridge_offer(_a_probe_bridge_reply())
        self.assertIsNone(_read_legacy_offer_slot(ctrl))
        # and the legacy consumer does not fire
        fired = ctrl.consume_offer_approval(_an_affirmation_turn())
        self.assertFalse(_fired(fired))
```

> **Implementer note:** the helpers (`_make_controller`, `_a_reply_that_would_have_offered`, `_read_legacy_offer_slot`, etc.) must be written against the REAL controller constructor + the real legacy-method signatures (read them at `core/brain/conversation_controller.py:746/791/843`). Construct the minimal controller the methods need; assert the old offer slot stays empty under the flag. Keep the assertion (old slot untouched / consumer inert under flag) exact.

- [ ] **Step 2: Run to verify it fails** — the legacy methods still write the slot.

- [ ] **Step 3: Minimal implementation** — add a flag check at the head of each of the three methods:

```python
import os

def _search_commitment_enabled() -> bool:
    return bool(os.environ.get("MAEZ_SEARCH_COMMITMENT_ENABLED"))

# at the top of maybe_store_offer(...), maybe_store_probe_bridge_offer(...):
#     if _search_commitment_enabled():
#         return None            # typed receipt governs offers now
# at the top of consume_offer_approval(...):
#     if _search_commitment_enabled():
#         return <the method's inert "no offer consumed" value>   # read the real return contract
```

(Match each method's existing return type for the inert value — read the signatures. Flag OFF ⇒ unchanged.)

- [ ] **Step 4: Run to verify pass.** Also run the existing controller suite to confirm flag-off is unchanged:
`/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_conversation_offer_supersession <existing controller tests> -v`

- [ ] **Step 5: Commit**

```bash
git add core/brain/conversation_controller.py tests/test_conversation_offer_supersession.py
git commit -m "feat(search-commitment): supersede all 3 legacy untyped-offer writers under the flag

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Wire offer-creation + affirmation-resolution at the Task-0 seam (the ONE behavior commit)

**Files:** Modify `core/brain/conversation_controller.py` (+ `skills/telegram_voice.py` per Task 0); Test: `tests/test_search_commitment_wiring.py`.

This is the behavior-touching task, all flag-gated. Use the attach point Task 0 proved. Add two controller methods and call them from the proven `TelegramVoice` per-message path:

- `store_search_offer(channel, chat_id, query, *, health) -> bool` — when the flag is on AND a search-worthy reply is being produced AND `health == healthy`: build the `OfferReceipt` (authoritative `offered_query=query`), store it in the new typed slot, return True (so the reply can voice the offer). If `health != healthy`: store nothing, return False (caller voices honest degradation). Flag off ⇒ return False, store nothing.
- `resolve_search_affirmation(channel, chat_id, text, backend, *, now_ts, turns_since) -> Optional[list[dict]]` — when the flag is on: load the typed slot → `resolve_affirmation(receipt, text, health=backend.health(), has_awaiting_card=self.has_awaiting_card(channel, chat_id), now_ts, turns_since)`. If `execute`: run `backend.search(decision.query)`, clear the slot, return results. Else return None. Flag off ⇒ return None.

- [ ] **Step 1: Write the failing tests** (with `FakeSearchBackend`)

```python
# tests/test_search_commitment_wiring.py
import os, unittest
from unittest import mock
from core.search.searxng_client import FakeSearchBackend
from core.brain import conversation_controller as cc


class WiringTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None)
        self.ctrl = _make_controller()

    def test_default_off_no_offer_no_search(self):
        # flag unset: store returns False, resolve returns None, no backend touch
        be = FakeSearchBackend()
        self.assertFalse(self.ctrl.store_search_offer("tg", "c1", "llama.cpp", health="healthy"))
        self.assertIsNone(self.ctrl.resolve_search_affirmation("tg", "c1", "yeah sure", be, now_ts=1.0, turns_since=1))
        self.assertEqual(be.searched, [])

    def test_offer_then_yes_executes_exact_query(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None))
        be = FakeSearchBackend(results=[{"title": "T", "url": "U", "content": "C"}])
        self.assertTrue(self.ctrl.store_search_offer("tg", "c1", "llama.cpp news", health="healthy"))
        out = self.ctrl.resolve_search_affirmation("tg", "c1", "yeah sure", be, now_ts=1.0, turns_since=1)
        self.assertEqual(out[0]["title"], "T")
        self.assertEqual(be.searched, ["llama.cpp news"])   # exact stored query

    def test_degraded_creates_no_offer(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None))
        self.assertFalse(self.ctrl.store_search_offer("tg", "c1", "q", health="degraded"))

    def test_awaiting_card_blocks_resolution(self):
        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None))
        be = FakeSearchBackend()
        self.ctrl.store_search_offer("tg", "c1", "q", health="healthy")
        with mock.patch.object(self.ctrl, "has_awaiting_card", return_value=True):
            out = self.ctrl.resolve_search_affirmation("tg", "c1", "yeah sure", be, now_ts=1.0, turns_since=1)
        self.assertIsNone(out)            # the card wins; no search fired
        self.assertEqual(be.searched, [])
```

- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement** the two methods on the controller (typed slot stored on the conversation/session state — mirror where the legacy slot lived). Then, **per Task 0**, call them from the `TelegramVoice` per-message path: after producing a search-worthy reply, `store_search_offer(...)` and have the reply voice the offer; on each inbound message, first `resolve_search_affirmation(...)` and if it returns results, render them as the reply (this is the follow-through). Keep all of it `if _search_commitment_enabled()`.
- [ ] **Step 4: Run to verify pass** + the full touched-module floor: `... -m unittest tests.test_search_commitment tests.test_searxng_client tests.test_search_commitment_wiring tests.test_conversation_offer_supersession -v`. `ruff check core/search/ core/brain/conversation_controller.py`.
- [ ] **Step 5: Commit (the ONE `## Predicted effect` commit)**

```bash
git add core/search/search_commitment.py core/brain/conversation_controller.py skills/telegram_voice.py tests/test_search_commitment_wiring.py
git commit -m "feat(search-commitment): wire honest offer->confirm->search at the live telegram seam (default-OFF)

## Predicted effect
With MAEZ_SEARCH_COMMITMENT_ENABLED unset (default): zero behavior change — store/resolve return
False/None before touching anything. When enabled: a search-worthy turn with healthy SearXNG creates
a typed offer Maez voices; the next 'yeah sure' fires ONLY that exact low-stakes sovereign-local
search (not stale, not while a card awaits, never a write/keyed-egress). Degraded/down -> no offer,
honest 'web search unavailable'. Legacy untyped offer paths are inert under the flag.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Inert SearXNG service unit + STOP-at-gate handoff

**Files:** Create `scripts/maez-searxng.template.service`; Create `docs/handoffs/2026-06-11-search-commitment-gate.md`.

- [ ] **Step 1: Write the systemd unit template** (owner installs; merge does NOT start it)

```ini
# scripts/maez-searxng.template.service
# Owner installs to ~/.config/systemd/user/maez-searxng.service and starts it as the
# witness breath. The merge does not install or start this. SearXNG cloned+built by the owner
# (the audition proved: pip install of requirements.txt then the editable install on py3.14).
[Unit]
Description=Maez sovereign search body (SearXNG, local-only)
After=default.target

[Service]
Type=simple
Environment=SEARXNG_SETTINGS_PATH=%h/.config/maez/searxng-settings.yml
ExecStart=%h/searxng/.venv/bin/python -m searx.webapp
Restart=on-failure

[Install]
WantedBy=default.target
```

- [ ] **Step 2: Write the handoff doc** — must record: Task 0's proven seam; that everything is green-with-Fake + flag-off-inert; and the **owner witness sequence** (the only remaining steps): (1) cross-lane covenant review (Codex/owner) — focus the trap-proof conjunction (stakes/egress/card), the egress rail, default-off, legacy supersession, and the Task-0 seam; (2) owner installs+starts `maez-searxng.service` with a `searxng-settings.yml` (limiter off, json format, bind 127.0.0.1:8888, secret_key set); (3) owner-gated smoke: confirm `SearxngBackend.search/health` shape against the live service; (4) flip `MAEZ_SEARCH_COMMITMENT_ENABLED=1`, restart, run a live `offer → "yeah sure" → results` loop + a `degraded → no offer` check; (5) watch **sustained-load** reliability (the audit was a snapshot).

- [ ] **Step 3: Run the full touched-module floor + ruff, record counts in the handoff.**
- [ ] **Step 4: Commit**

```bash
git add scripts/maez-searxng.template.service docs/handoffs/2026-06-11-search-commitment-gate.md
git commit -m "docs(search-commitment): inert SearXNG unit + STOP-at-gate witness handoff

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review notes (for the implementer)
- **Task 0 is load-bearing and FIRST.** `handle_user_message` is dead; the live seam is `TelegramVoice` (`skills/telegram_voice.py:913`) ↔ the controller. Prove the exact per-message hook before any wiring. If reality differs from this plan's assumption, STOP and escalate — don't force.
- **The trap-proof conjunction is the covenant core** — the three tests (`test_high_stakes_blocked`, `test_keyed_egress_blocked`, `test_awaiting_card_wins`) and the egress-rail test (`searched == [exact stored query]`) must pass honestly; they are why "yeah sure" can never become mutate-or-egress.
- **Default-off is sacred** — `test_default_off_no_offer_no_search` proves flag-unset is byte-identical. Never weaken it.
- **The daemon never imports/loads SearXNG for tests** — only `SearxngBackend` (mocked) and the owner-installed service touch it.
- **Names used across tasks:** `SearchBackend.search/health`, `FakeSearchBackend(results=, health=, raises=)`, `SearxngBackend(base_url=, timeout_s=)`, `OfferReceipt(...8 fields...).is_fresh(now_ts, turns_since)`, `is_clear_yes(text)`, `resolve_affirmation(receipt, text, *, health, has_awaiting_card, now_ts, turns_since) -> ResolveDecision(execute, reason, query)`, `_search_commitment_enabled()`, `store_search_offer(...)`, `resolve_search_affirmation(...)`. Keep them identical.
