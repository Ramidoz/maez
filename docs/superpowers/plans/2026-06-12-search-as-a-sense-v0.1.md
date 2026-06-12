# Search-as-a-Sense v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconnect the live dispatcher external wing to the healed SearXNG body, retire the result-card bypass on both surfaces, and add the metabolism lane (web evidence → one bounded `external_web`/`untrusted` observation via the intake bus) — all behind one default-OFF flag.

**Architecture:** The dispatcher already routes current-world turns to an external `WEB_SEARCH` fanout and merges fresh evidence into synthesis (`brain_loop.py:836`); it is plumbed to a dead DuckDuckGo scraper and bypassed by the search-commitment interceptor. v0.1 heals `skills/web_search.py` globally (SearXNG under the flag), inverts the interceptor into a health-gatekeeper, writes one observation per evidence-admitted search, threads a true progress signal into the fanout, strips `[E#]` markers post-audit, and stages the soul fix.

**Tech Stack:** Python stdlib + existing organs: `SearxngBackend`/`FakeSearchBackend`, the dispatcher fanout, the intake bus (`core/intake_bus/`), `enforce_subject_boundary`, Surface V2 intermediates. unittest (`/home/rohit/maez/.venv/bin/python -B -m unittest` — NEVER pytest, NEVER full-discover in the live tree), ruff.

**Spec:** `docs/superpowers/specs/2026-06-12-search-as-a-sense-v0.1-design.md` (@c530048). Read it once before starting.

---

## Ground Rules

- **Branch `search-as-a-sense-v0.1` off main.** main is local-only — NO `git push`, ever.
- **STOP at the gate.** No merge, no restart, no flag-flip, no service changes — those are OWNER breaths. The plan ends with a handoff doc.
- **One flag gates everything:** `MAEZ_SEARCH_AS_SENSE_ENABLED`. Unset ⇒ byte-identical current behavior on every seam (tests assert this).
- **`## Predicted effect`** only on the behavior-affecting wiring commits (Tasks 2, 3, 4, 5 — flag-gated daemon behavior). Pure new-module/test/docs commits don't carry it.
- **Co-author trailer on every commit:** `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- **Tests use fakes only** (`FakeSearchBackend`, fake memory, fake rendered turns). The suite must never need a running SearXNG, judge, or daemon.
- **Trap-proof receipt tests must stay green untouched** (`tests/test_search_commitment.py`) — the typed-receipt machinery is reserved, not removed.

## File Map

| Path | Responsibility |
|---|---|
| `core/search/sense_flag.py` (create) | The one flag helper `sense_enabled()`. |
| `skills/web_search.py` (modify) | Healed body: SearXNG under the flag; pre-egress subject-boundary refusal at the body. |
| `skills/surface/maez_adapter.py` (modify) | Interceptor → health gatekeeper (Task 2 ONLY — no progress change; the adapter already feeds `run_brain_loop`). |
| `skills/telegram_voice.py` (modify) | Legacy offer/result-card branches gated (ghost-path closure). |
| `core/intake_bus/world_observation_lane.py` (create) | The metabolism lane: bounded observation → `admit()`. |
| `core/brain/brain_loop.py` (modify) | Observation hook after merge; fanout progress emits; turn-evidence stash. |
| `daemon/maez_daemon.py` (modify) | Drains the chat_id-keyed turn stash: metabolism write (memory owner) + marked-draft retention + post-audit `[E#]` render (the audit→store→send invariant owner). |
| `skills/surface/telegram_adapter.py` (modify) | `/receipts` command (two-line shim over `receipts_reply`). |
| `config/soul.md` (modify) | §Internet Access rewritten (staged; witness is an owner breath). |
| `tests/test_web_search_sense.py` (create) | Body + refusal + flag-off identity. |
| `tests/test_world_observation_lane.py` (create) | Metabolism condition legs, idempotency, provenance purity. |
| `tests/test_surface_adapter.py` (modify) | Gatekeeper inversion, progress pass-through. |
| `tests/test_attribution_render.py` (create) | Strip/attribution/ordering/fallback. |
| `docs/handoffs/2026-06-12-search-as-a-sense-gate.md` (create) | STOP-at-gate handoff. |

---

### Task 0: Prove the seams (NO feature code until all three proofs pass)

This discipline caught a dead surface and a fictional accessor earlier in this
arc. Registered ≠ firing. Record each proof's output in the handoff doc later.

**Files:** none modified. Read-only.

- [ ] **Step 0a: Prove the live wing seam fires on owner turns**

Run:
```bash
cd /home/rohit/maez
grep -n "Wing: external" logs/maez.log | tail -3
grep -n "Web search:" logs/maez.log | tail -3
grep -n "_web_search_adapter\|ExternalSource.WEB_SEARCH" core/dispatcher/external_sources.py | head -4
```
Expected: recent `Wing: external` lines (2026-06-11 has them — e.g. 16:33:56
"What's the latest news on open-source AI models?"); `Web search:` INFO lines
from `skills/web_search.py:search()` near the same timestamps prove the wing's
adapter actually executed the global search entry on a live owner turn;
the adapter map shows `ExternalSource.WEB_SEARCH: _web_search_adapter`.
**STOP if** no historical `Wing: external` → `Web search:` correlation exists —
report instead of proceeding (the wing may be gated off; do not guess).

- [ ] **Step 0b: Prove the progress-callback chain (surface → daemon exists; daemon → fanout is the new hop)**

Run:
```bash
cd /home/rohit/maez
grep -n "send_intermediate" daemon/maez_daemon.py | head -10
grep -n "send_intermediate" skills/surface/maez_adapter.py | head -6
awk 'NR<8500 && /def .*\(/ {line=NR": "$0} /merge_fanout_results\(/ {print "fanout call at "NR" inside -> "line; exit}' core/brain/brain_loop.py
grep -n "run_external_fanout\|ExternalFanout(" core/brain/brain_loop.py | head -4
```
**PROVEN CHAIN (Task 0b executed 2026-06-12 — this supersedes earlier
guesses):** the external wing is NOT reached through `daemon.handle_message`.
Surface V2 makes TWO separate executor calls:
1. `maez_adapter.py:572-575` → `run_brain_loop(..., chat_id=...,
   send_intermediate=_send_intermediate, ...)` (`brain_loop.py:1687` — the
   kwarg ALREADY exists and the adapter ALREADY passes a working sender)
   → `_run_dispatcher_pipeline(...)` at `brain_loop.py:1759` (def :629 —
   has `chat_id`, has NO `memory`, NO `send_intermediate` yet) → fanout +
   `merge_fanout_results` (:836, inside the pipeline).
2. `maez_adapter.py:611` → `daemon.handle_message(...,
   transcript=jarvis_transcript, chat_id=..., ...)` — final synthesis,
   audit, store, send. `self.memory` lives HERE.

Consequences the tasks below are built on: (i) progress threads
`run_brain_loop → _run_dispatcher_pipeline` (one new kwarg + pass-through
at :1759), NOT through the daemon; (ii) the two executor calls give NO
same-thread guarantee — cross-call state is keyed by **`chat_id`** (both
sides have it), never thread ident; (iii) the pipeline cannot write memory —
the metabolism write happens in `handle_message`, fed by a chat_id-keyed
stash. Confirm each line number above against the worktree; **STOP if** any
hop differs.

- [ ] **Step 0c: Record the intake-bus validation vocabulary**

Run:
```bash
cd /home/rohit/maez
sed -n '1,60p' core/intake_bus/admit.py
sed -n '1,60p' core/intake_bus/contract.py
grep -rn "egress_origin_class" memory/memory_manager.py | head -5
```
Expected: `_validate(fact)`'s actual rules (what it refuses), the full
`IntakeFact` field list (`source_kind, source_ref, content, provenance_source,
egress_origin_class, promotion_posture, fetch_batch_id, metadata`), the
store-adapter protocol used by `admit()` (`oldest_pending()`,
`mark_admitted(source_ref, body_memory_id=...)`), and whether
`egress_origin_class` is validated: it IS — `admit.py:26` checks
`core.egress.gate.KNOWN_ORIGINS`. Confirm `"tool_result_public"` is a member
(NON_PRIVATE set, `gate.py:33-38`) — that is `WORLD_OBSERVATION_EGRESS` in
Task 3. (`"sovereign_local_search"` is a RECEIPT egress class, not a
memory-origin class — admit() would refuse it.)

- [ ] **Step 0d: Create the branch**

```bash
cd /home/rohit/maez
git checkout -b search-as-a-sense-v0.1
```

---

### Task 1: The flag + the healed body + pre-egress refusal

**Files:**
- Create: `core/search/sense_flag.py`
- Modify: `skills/web_search.py` (the `search()` function, ~:26)
- Create: `tests/test_web_search_sense.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_web_search_sense.py`:

```python
from __future__ import annotations

import os
import unittest
from unittest import mock

from core.policies.third_party_subject_gate import SubjectKind
from core.search.searxng_client import FakeSearchBackend


class _Env(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None))
        # search() caches results module-globally; isolate every test.
        import skills.web_search as ws
        ws._cache.clear()
        self.addCleanup(ws._cache.clear)


class SenseFlagTests(_Env):
    def test_flag_off_never_touches_searxng(self):
        import skills.web_search as ws
        with mock.patch.object(ws, "_sense_backend", side_effect=AssertionError("flag off must not build a backend")):
            with mock.patch.object(ws, "_ddg_search", return_value={"query": "q", "success": True, "results": [], "source": "duckduckgo"}) as ddg:
                out = ws.search("q")
        self.assertEqual(out["source"], "duckduckgo")
        ddg.assert_called_once()

    def test_flag_on_routes_to_searxng_contract_shape(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws
        fake = FakeSearchBackend(results=[{"title": "T", "url": "U", "content": "C"}])
        with mock.patch.object(ws, "_sense_backend", return_value=fake):
            out = ws.search("llama.cpp release", max_results=3)
        self.assertTrue(out["success"])
        self.assertEqual(out["source"], "searxng")
        self.assertEqual(out["results"][0], {"title": "T", "url": "U", "snippet": "C"})
        self.assertEqual(fake.searched, ["llama.cpp release"])

    def test_flag_on_empty_results_is_honest_failure(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws
        with mock.patch.object(ws, "_sense_backend", return_value=FakeSearchBackend(results=[])):
            out = ws.search("nothing")
        self.assertFalse(out["success"])
        self.assertEqual(out["results"], [])

    def test_flag_on_backend_exception_is_honest_failure(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws
        with mock.patch.object(ws, "_sense_backend", return_value=FakeSearchBackend(raises=RuntimeError("down"))):
            out = ws.search("boom")
        self.assertFalse(out["success"])


class PreEgressRefusalTests(_Env):
    def test_named_third_party_refused_before_any_backend_call(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws
        fake = FakeSearchBackend()
        with mock.patch.object(ws, "_sense_backend", return_value=fake):
            out = ws.search("John Smith my coworker", subject_kind=SubjectKind.NAMED_THIRD_PARTY)
        self.assertFalse(out["success"])
        self.assertEqual(out.get("refused"), "subject_boundary")
        self.assertEqual(fake.searched, [])  # ZERO egress

    def test_unknown_subject_refused(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws
        fake = FakeSearchBackend()
        with mock.patch.object(ws, "_sense_backend", return_value=fake):
            out = ws.search("???", subject_kind=SubjectKind.UNKNOWN)
        self.assertEqual(out.get("refused"), "subject_boundary")
        self.assertEqual(fake.searched, [])

    def test_default_subject_kind_is_public_topic_and_allowed(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        import skills.web_search as ws
        fake = FakeSearchBackend(results=[{"title": "t", "url": "u", "content": "c"}])
        with mock.patch.object(ws, "_sense_backend", return_value=fake):
            out = ws.search("latest llama.cpp")
        self.assertTrue(out["success"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify RED**

Run: `cd /home/rohit/maez && .venv/bin/python -B -m unittest tests.test_web_search_sense -v`
Expected: FAIL/ERROR — `core.search.sense_flag` missing, `_sense_backend` / `_ddg_search` undefined.

- [ ] **Step 3: Create the flag helper**

Create `core/search/sense_flag.py`:

```python
"""The one flag for Search-as-a-Sense v0.1 (spec 2026-06-12).

Default OFF. When unset, every touched seam behaves byte-identically to
pre-v0.1. Reverting live = unset the env var + restart maez.service.
"""
from __future__ import annotations

import os


def sense_enabled() -> bool:
    return bool(os.environ.get("MAEZ_SEARCH_AS_SENSE_ENABLED"))
```

- [ ] **Step 4: Heal `skills/web_search.py:search()`**

In `skills/web_search.py`, refactor the existing body of `search()` so the
current DDG implementation (everything from the "Attempt 1" comment through
the final result construction and cache write, ~:48-:120) moves verbatim into
a new module function `_ddg_search(query: str, max_results: int) -> dict`
(keep its internal logic byte-identical; it still writes `_cache`). Then make
`search()` the router. Add at module top (after existing imports):

```python
from core.policies.third_party_subject_gate import (
    SubjectBoundaryRefused,
    SubjectKind,
    enforce_subject_boundary,
)
from core.search.sense_flag import sense_enabled

_SENSE_BACKEND = None


def _sense_backend():
    """Lazy singleton so the flag-off path never imports/builds SearXNG."""
    global _SENSE_BACKEND
    if _SENSE_BACKEND is None:
        from core.search.searxng_client import SearxngBackend

        _SENSE_BACKEND = SearxngBackend()
    return _SENSE_BACKEND


class _SubjectQuery:
    """Adapter to the SubjectBoundaryQuery protocol for body-level checks."""

    def __init__(self, subject_kind, subject_ref=None):
        self.bond_id = "owner"
        self.subject_kind = subject_kind
        self.subject_ref = subject_ref
```

And the new `search()`:

```python
def search(query: str, max_results: int = 5, *, subject_kind=SubjectKind.PUBLIC_TOPIC) -> dict:
    """Search the web. SearXNG sense under MAEZ_SEARCH_AS_SENSE_ENABLED;
    the legacy DuckDuckGo path byte-identical when the flag is off.

    Pre-egress subject boundary lives HERE, at the body, so every caller
    (dispatcher wing, /search, legacy, autonomous) inherits it identically.
    Callers that classify subjects (curiosity/wonderings) pass their kind;
    owner-turn world questions default to PUBLIC_TOPIC. NAMED_THIRD_PARTY
    and UNKNOWN are refused BEFORE any network egress — refusal at
    construction, never sanitization after.
    """
    if not sense_enabled():
        return _ddg_search(query, max_results)

    try:
        enforce_subject_boundary(_SubjectQuery(subject_kind, subject_ref=query[:80]))
    except SubjectBoundaryRefused:
        logger.info("web search refused pre-egress: subject_boundary")
        return {"query": query, "success": False, "results": [], "source": "searxng", "refused": "subject_boundary"}

    cache_key = query.lower().strip()
    if cache_key in _cache:
        age = time.time() - _cache[cache_key]["timestamp"]
        if age < _cache_ttl:
            return _cache[cache_key]["result"]

    logger.info("Web search (searxng sense): %s", query[:100])
    try:
        rows = _sense_backend().search(query, max_results=max_results)
    except Exception as e:
        logger.warning("searxng sense failed: %s", e)
        return {"query": query, "success": False, "results": [], "source": "searxng"}
    results = [
        {"title": r.get("title") or "", "url": r.get("url") or "", "snippet": r.get("content") or ""}
        for r in rows
    ]
    result = {"query": query, "success": bool(results), "results": results, "source": "searxng"}
    if result["success"]:
        _cache[cache_key] = {"result": result, "timestamp": time.time()}
    return result
```

(`format_for_context()` and `needs_web_search()` are NOT touched — the result
contract is preserved, so the wing adapter and every caller work unchanged.)

- [ ] **Step 5: Run to verify GREEN + flag-off identity**

Run:
```bash
.venv/bin/python -B -m unittest tests.test_web_search_sense -v
.venv/bin/python -B -m unittest tests.test_search_commitment tests.test_searxng_client -v
```
Expected: all PASS (the second command proves the receipt law and backend
tests are undisturbed).

- [ ] **Step 6: Commit**

```bash
git add core/search/sense_flag.py skills/web_search.py tests/test_web_search_sense.py
git commit -m "feat(search-sense): heal web_search body with SearXNG + pre-egress subject boundary

Flag-gated (MAEZ_SEARCH_AS_SENSE_ENABLED, default off = DDG path
byte-identical). The subject-boundary refusal now lives at the body so
every caller inherits it; NAMED_THIRD_PARTY/UNKNOWN refused before any
egress (reuses core.policies.third_party_subject_gate, no new detector).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Interceptor → health gatekeeper (both surfaces)

**Files:**
- Modify: `skills/surface/maez_adapter.py` (`_try_search_commitment_intent`, :209)
- Modify: `skills/telegram_voice.py` (`_try_search_commitment_offer_intent`, :2726)
- Test: `tests/test_surface_adapter.py`, `tests/test_search_commitment_wiring.py`

- [ ] **Step 1: Write the failing Surface V2 tests**

Append to `tests/test_surface_adapter.py` (inside `HandlerRouting`, reusing
its `_FakeDaemon`/`_TelegramWithController` fixtures; mirror the env hygiene
of the existing intake-shadow tests):

```python
    def test_sense_on_healthy_searchworthy_falls_through_to_synthesis(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None))
        daemon = _FakeDaemon(reply="synthesized answer in voice")
        daemon.telegram = _TelegramWithController()
        handler = MaezMessageHandler(daemon)
        event = MessageEvent(
            text="what's the latest llama.cpp release?",
            source=SessionSource(platform=Platform.TELEGRAM, chat_id="c", user_id="rohit"),
        )
        with patch.object(MaezMessageHandler, "_search_commitment_backend",
                          return_value=FakeSearchBackend(health="healthy")):
            result = asyncio.run(handler(event))
        self.assertEqual(result, "synthesized answer in voice")  # NO offer, NO card
        self.assertEqual(daemon.last_text, "what's the latest llama.cpp release?")

    def test_sense_on_degraded_searchworthy_returns_fixed_notice_no_receipt(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None))
        daemon = _FakeDaemon(reply="should not be reached")
        daemon.telegram = _TelegramWithController()
        handler = MaezMessageHandler(daemon)
        event = MessageEvent(
            text="what's the latest llama.cpp release?",
            source=SessionSource(platform=Platform.TELEGRAM, chat_id="c", user_id="rohit"),
        )
        with patch.object(MaezMessageHandler, "_search_commitment_backend",
                          return_value=FakeSearchBackend(health="degraded")):
            result = asyncio.run(handler(event))
        self.assertIn("web sense is degraded", result)
        ctrl = daemon.telegram._controller
        self.assertIsNone(ctrl.get_search_offer("telegram_text", "c"))  # NO receipt
        self.assertIsNone(daemon.last_text)  # NO synthesis

    def test_sense_off_offer_behavior_unchanged(self):
        os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None)
        daemon = _FakeDaemon(reply="unused")
        daemon.telegram = _TelegramWithController()
        handler = MaezMessageHandler(daemon)
        event = MessageEvent(
            text="what's the latest llama.cpp release?",
            source=SessionSource(platform=Platform.TELEGRAM, chat_id="c", user_id="rohit"),
        )
        with patch.object(MaezMessageHandler, "_search_commitment_backend",
                          return_value=FakeSearchBackend(health="healthy")):
            result = asyncio.run(handler(event))
        self.assertIn("local web sense", result)  # the v0 offer text, byte-identical path
```

(Adjust fixture constructor details ONLY if the existing fixtures require it —
match the surrounding tests' instantiation exactly; do not weaken assertions.)

- [ ] **Step 2: RED**

Run: `.venv/bin/python -B -m unittest tests.test_surface_adapter -v 2>&1 | tail -15`
Expected: the three new tests FAIL (sense-on still produces the offer card path).

- [ ] **Step 3: Invert the Surface V2 interceptor**

In `skills/surface/maez_adapter.py`, at the top of
`_try_search_commitment_intent` (after the `_search_commitment_enabled()` /
controller checks it already does), insert the gatekeeper branch:

```python
        from core.search.sense_flag import sense_enabled

        if sense_enabled():
            # v0.1 (spec 2026-06-12 §2-3): the interceptor inverts into a
            # HEALTH GATEKEEPER. Healthy search-worthy turns fall through to
            # dispatcher synthesis (the external wing searches unasked).
            # Degraded/down returns a FIXED honest notice only — no
            # synthesis, no receipt (store_search_offer refuses non-healthy
            # by law; we do not smuggle degraded execution).
            if not is_search_offer_worthy(text):
                return None
            health = self._search_commitment_backend().health()
            if health == "healthy":
                return None
            return (
                "My web sense is degraded right now, so I can't check the live "
                "web for this. I can answer from what I already hold if you ask "
                "again, or we can retry the web later."
            )
```

(Everything below — the v0 offer/resolve logic — remains untouched and runs
only when the sense flag is off.)

- [ ] **Step 4: GREEN**

Run: `.venv/bin/python -B -m unittest tests.test_surface_adapter -v 2>&1 | tail -5`
Expected: PASS, including the pre-existing adapter tests (flag-off identity).

- [ ] **Step 5: Write the failing legacy-surface test**

Append to `tests/test_search_commitment_wiring.py` (match its existing fixture
style for constructing the `TelegramVoice` object or its method under test):

```python
    def test_sense_on_legacy_offer_branch_inert_for_healthy(self):
        # Ghost-path closure: the legacy surface must not voice offers or
        # result-cards for healthy search-worthy turns when the sense flag
        # is on. Uses this module's established construction pattern
        # (TelegramVoice.__new__ + injected controller, see
        # TelegramSearchCommitmentSeamTests ~:170).
        import asyncio
        from unittest import mock

        from core.search.searxng_client import FakeSearchBackend
        from skills.telegram_voice import TelegramVoice

        os.environ["MAEZ_SEARCH_COMMITMENT_ENABLED"] = "1"
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None))
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_COMMITMENT_ENABLED", None))

        tv = TelegramVoice.__new__(TelegramVoice)
        tv._controller = _make_controller()
        tv.authorized_user = "123"

        replies: list[str] = []

        async def _fake_reply(update, text):
            replies.append(text)

        with mock.patch.object(
            TelegramVoice, "_search_commitment_backend",
            return_value=FakeSearchBackend(health="healthy"),
        ), mock.patch(
            "skills.telegram_voice._reply_text", new=_fake_reply,
        ):
            handled = asyncio.run(
                tv._try_search_commitment_offer_intent(
                    mock.MagicMock(), "what's the latest llama.cpp release?"
                )
            )

        self.assertFalse(handled)          # not intercepted — no offer voiced
        self.assertEqual(replies, [])      # zero messages from the legacy path
        self.assertIsNone(
            tv._controller.get_search_offer("telegram_text", "123")
        )                                   # and no receipt stored
```

(If `_reply_text` lives under a different name in `skills.telegram_voice`,
patch the real symbol — check the module's reply helper with one grep; do not
weaken the three assertions.)

- [ ] **Step 6: Gate the legacy branch**

In `skills/telegram_voice.py`, at the top of
`_try_search_commitment_offer_intent` (:2726), after the existing
`_search_commitment_enabled()` check:

```python
        from core.search.sense_flag import sense_enabled

        if sense_enabled():
            # v0.1 ghost-path closure: the legacy surface never voices offers
            # or result-cards when the sense lane owns healthy searches. (The
            # live inbound is Surface V2; this surface is outbound-only, but
            # code-live paths get gated, not trusted.)
            return False
```

And the same two-line guard at the top of `_try_offer_binding_intent`'s typed
branch (`if _search_commitment_enabled():` block, :2770) — under
`sense_enabled()`, skip the typed branch entirely (`pass` through to the
legacy consumer, which Task 0 of the commitment arc already proved inert).

- [ ] **Step 7: GREEN + full focused suite**

Run:
```bash
.venv/bin/python -B -m unittest tests.test_search_commitment_wiring tests.test_surface_adapter tests.test_search_commitment -v 2>&1 | tail -5
```
Expected: PASS.

- [ ] **Step 8: Commit (behavior-affecting)**

```bash
git add skills/surface/maez_adapter.py skills/telegram_voice.py tests/test_surface_adapter.py tests/test_search_commitment_wiring.py
git commit -m "feat(search-sense): interceptor inverts to health gatekeeper on both surfaces

## Predicted effect
With MAEZ_SEARCH_AS_SENSE_ENABLED=1, healthy search-worthy Telegram turns
no longer produce an offer or raw result-card on either surface; they fall
through to dispatcher synthesis (the external wing searches unasked).
Degraded/down search returns a fixed honest notice with no receipt and no
synthesis. Flag unset: v0 offer->confirm->card behavior byte-identical.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: The metabolism lane

**Files:**
- Create: `core/intake_bus/world_observation_lane.py`
- Modify: `core/brain/brain_loop.py` (after `merge_fanout_results`, ~:836)
- Create: `tests/test_world_observation_lane.py`

- [ ] **Step 1: Write the failing lane tests**

Create `tests/test_world_observation_lane.py`:

```python
from __future__ import annotations

import os
import unittest

from core.intake_bus import world_observation_lane as lane


class _FakeMemory:
    def __init__(self, existing=None):
        self.stored = []
        self._existing = existing

    def body_row_id_by_source_ref(self, source_ref, *, egress_origin_class):
        return self._existing

    def store(self, **kwargs):
        self.stored.append(kwargs)
        return "body-1"


class _Spec:
    def __init__(self, sources):
        self.external_sources = sources


class _Turn:
    def __init__(self, sources=("WEB_SEARCH",), summaries=("WEB_SEARCH",), outcome="ALL_SUCCEEDED"):
        self.effective_spec = _Spec(list(sources))
        self.source_summaries = [type("S", (), {"source": s})() for s in summaries]
        self.fresh_attempt_outcome = outcome


def _evidence():
    # FreshBlock.text shape: format_for_context output (titles/URLs/snippets as text)
    return ["[WEB SEARCH] Releases - llama.cpp — https://github.com/x/releases — b9601 released today"]


class ConditionTests(unittest.TestCase):
    """The three structural legs — pure, no memory involved."""

    def test_all_legs_hold(self):
        self.assertTrue(lane.evaluate_write_condition(_Turn()))

    def test_leg_no_web_search_in_spec(self):
        self.assertFalse(lane.evaluate_write_condition(_Turn(sources=("LIVE_REDDIT",))))

    def test_leg_no_summary(self):
        self.assertFalse(lane.evaluate_write_condition(_Turn(summaries=("LIVE_REDDIT",))))

    def test_leg_failed_outcome(self):
        self.assertFalse(lane.evaluate_write_condition(_Turn(outcome="ALL_FAILED")))

    def test_malformed_turn_is_false_not_raise(self):
        self.assertFalse(lane.evaluate_write_condition(object()))


class WriteTests(unittest.TestCase):
    def setUp(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None))

    def test_writes_one_observation(self):
        mem = _FakeMemory()
        out = lane.write_world_observation(
            mem, query="latest llama.cpp release",
            evidence_texts=_evidence(), diagnostic_id="fan-123",
        )
        self.assertEqual(out, "admitted")
        self.assertEqual(len(mem.stored), 1)
        rec = mem.stored[0]
        self.assertEqual(str(getattr(rec["provenance_source"], "value", rec["provenance_source"])), "external_web")
        self.assertIn("latest llama.cpp release", rec["content"])
        self.assertIn("github.com", rec["content"])

    def test_flag_off_never_writes(self):
        os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None)
        mem = _FakeMemory()
        out = lane.write_world_observation(
            mem, query="q", evidence_texts=_evidence(), diagnostic_id="fan-1",
        )
        self.assertEqual(out, "disabled")
        self.assertEqual(mem.stored, [])

    def test_idempotent_on_diagnostic_id(self):
        mem = _FakeMemory(existing="already-there")
        out = lane.write_world_observation(
            mem, query="q", evidence_texts=_evidence(), diagnostic_id="fan-123",
        )
        self.assertEqual(out, "already_admitted")
        self.assertEqual(mem.stored, [])

    def test_provenance_purity_no_owner_text_beyond_query(self):
        mem = _FakeMemory()
        lane.write_world_observation(
            mem, query="latest llama.cpp release",
            evidence_texts=_evidence(), diagnostic_id="fan-9",
        )
        content = mem.stored[0]["content"]
        self.assertIn("web evidence entered the synthesis context", content)
        self.assertNotIn("Maez used", content)

    def test_memory_failure_never_raises(self):
        class _Boom(_FakeMemory):
            def store(self, **kwargs):
                raise RuntimeError("db locked")
        out = lane.write_world_observation(
            _Boom(), query="q", evidence_texts=_evidence(), diagnostic_id="fan-1",
        )
        self.assertEqual(out, "error_dropped")

    def test_real_bus_validation_accepts_the_origin_class(self):
        # Run the REAL admit() validation, not just the fake: a wrong
        # egress_origin_class (e.g. a receipt class) must be refused by the
        # bus, and the lane's chosen class must pass it.
        from core.egress.gate import KNOWN_ORIGINS

        self.assertIn(lane.WORLD_OBSERVATION_EGRESS, KNOWN_ORIGINS)
        self.assertNotIn("sovereign_local_search", KNOWN_ORIGINS)
        mem = _FakeMemory()
        out = lane.write_world_observation(
            mem, query="real validation",
            evidence_texts=_evidence(), diagnostic_id="fan-real",
        )
        self.assertEqual(out, "admitted")  # through the REAL _validate path

    def test_source_url_extraction_from_evidence_text(self):
        urls = lane.extract_source_urls(_evidence())
        self.assertEqual(urls, ["https://github.com/x/releases"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: RED**

Run: `.venv/bin/python -B -m unittest tests.test_world_observation_lane -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the lane**

Create `core/intake_bus/world_observation_lane.py`:

```python
"""World-observation lane — the metabolism (spec 2026-06-12 §4).

ONE bounded observation per evidence-admitted search, through the intake
bus. The record claims exactly what it proves: "web evidence entered the
synthesis context" — never that Maez used it in a sentence. Bounded,
provenance-first, NO second LLM call. Bus admission failure logs and
drops; it never blocks the reply.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time

from core.intake_bus.admit import admit
from core.intake_bus.contract import IntakeFact, PromotionPosture
from core.search.sense_flag import sense_enabled
from memory.memory_manager import ProvenanceSource

logger = logging.getLogger("maez")

# admit() validates egress_origin_class against core.egress.gate.KNOWN_ORIGINS
# (admit.py:26). "tool_result_public" is a real NON_PRIVATE member (gate.py:33-38)
# and is the correct class for public web search results. Do NOT use
# "sovereign_local_search" — that is a receipt egress class, not a memory-origin
# class, and admit() would refuse every observation.
WORLD_OBSERVATION_EGRESS = "tool_result_public"
_MAX_ROWS = 3
_MAX_SNIPPET = 200


class _SingleFactAdapter:
    """Minimal store adapter: one pending fact, admitted synchronously."""

    def __init__(self, fact: IntakeFact):
        self._fact = fact
        self.admitted_body_id: str | None = None

    def oldest_pending(self):
        return self._fact

    def mark_admitted(self, source_ref: str, *, body_memory_id: str):
        self.admitted_body_id = body_memory_id
        self._fact = None


def _has_web_search(values) -> bool:
    return any(str(getattr(v, "value", v)) == "WEB_SEARCH" for v in (values or []))


def _summaries_include_web(summaries) -> bool:
    return any(
        str(getattr(getattr(s, "source", None), "value", getattr(s, "source", ""))) == "WEB_SEARCH"
        for s in (summaries or [])
    )


def _outcome_ok(outcome) -> bool:
    return str(getattr(outcome, "value", outcome)) in {"ALL_SUCCEEDED", "PARTIAL"}


_URL_RE = re.compile(r"https?://[^\s\)\]]+")


def extract_source_urls(evidence_texts: list[str], cap: int = 5) -> list[str]:
    """URLs from the FreshBlock texts (format_for_context embeds them).
    Used for /receipts sources — structural rows do not survive the fanout
    (ExternalBranchResult carries FreshBlock.text, not raw result rows)."""
    seen: list[str] = []
    for text in evidence_texts or []:
        for url in _URL_RE.findall(text or ""):
            if url not in seen:
                seen.append(url)
            if len(seen) >= cap:
                return seen
    return seen


def build_observation_content(query: str, evidence_texts: list[str]) -> str:
    """The digest is built from FreshBlock.text — LITERALLY the evidence that
    entered the synthesis context (stronger provenance than raw rows, which
    the wing never surfaces). Bounded, no second LLM call."""
    lines = [
        f"Web observation — web evidence entered the synthesis context for: {query[:200]}",
    ]
    for text in (evidence_texts or [])[:_MAX_ROWS]:
        excerpt = " ".join((text or "").split())[:600]
        if excerpt:
            lines.append(f"- {excerpt}")
    lines.append(f"observed_at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    return "\n".join(lines)


def evaluate_write_condition(rendered_turn) -> bool:
    """The three structural legs (spec §4), pure — runs INSIDE the dispatcher
    pipeline where rendered_turn lives. The WRITE runs in handle_message,
    where memory lives (the pipeline has no memory in scope — Task 0b)."""
    try:
        spec = getattr(rendered_turn, "effective_spec", None)
        return (
            _has_web_search(getattr(spec, "external_sources", None))
            and _summaries_include_web(getattr(rendered_turn, "source_summaries", None))
            and _outcome_ok(getattr(rendered_turn, "fresh_attempt_outcome", None))
        )
    except Exception:
        return False


def write_world_observation(
    memory,
    *,
    query: str,
    evidence_texts: list[str],
    diagnostic_id: str,
) -> str:
    """Returns disabled|admitted|already_admitted|staged|refused|error_dropped.
    Called by daemon.handle_message with the daemon's memory, AFTER the
    pipeline evaluated the condition and stashed the payload."""
    if not sense_enabled():
        return "disabled"
    try:
        qhash = hashlib.sha256((query or "").encode("utf-8")).hexdigest()[:12]
        fact = IntakeFact(
            source_kind="world_observation",
            source_ref=f"web_search:{diagnostic_id}:{qhash}",
            content=build_observation_content(query, evidence_texts),
            provenance_source=ProvenanceSource.EXTERNAL_WEB,
            egress_origin_class=WORLD_OBSERVATION_EGRESS,
            promotion_posture=PromotionPosture.ADMIT_TO_BODY,
            fetch_batch_id=str(diagnostic_id),
            metadata={"lane": "world_observation", "query_hash": qhash},
        )
        outcome = admit(_SingleFactAdapter(fact), memory)
        logger.info("world_observation lane: %s ref=%s", outcome.status, outcome.source_ref)
        return outcome.status if outcome.status != "nothing_pending" else "skipped"
    except Exception as e:
        logger.warning("world_observation lane dropped: %s", e)
        return "error_dropped"
```

(Adjust the lane tests to the split API: condition tests call
`evaluate_write_condition(_Turn(...))` and assert True/False per leg; write
tests call `write_world_observation(mem, query=..., evidence_texts=...,
diagnostic_id=...)` directly — same assertions, no rendered_turn parameter.
The flag-off test asserts `write_world_observation` returns "disabled" with
zero stores.)

(If Task 0c found `_validate` enforces a different `egress_origin_class`
vocabulary or extra `IntakeFact` invariants, set `WORLD_OBSERVATION_EGRESS`
and the fact fields to the recorded values — and say so in the handoff.
If `ProvenanceSource.EXTERNAL_WEB` needs `.value` ("external_web") for the
fake memory assertion, normalize in the lane, not the test.)

- [ ] **Step 4: GREEN**

Run: `.venv/bin/python -B -m unittest tests.test_world_observation_lane -v`
Expected: PASS. (If `IntakeFact` field order/types differ, fix the lane to
the real contract from Task 0c — never edit the contract.)

- [ ] **Step 5: Hook it into `brain_loop` after the merge**

In `core/brain/brain_loop.py`, directly AFTER the `rendered_turn =
merge_fanout_results(...)` call (~:836) and its `turn_seal_state` lines,
insert (matching the surrounding indentation):

```python
    # Search-as-a-Sense v0.1 metabolism (spec §4) — PIPELINE SIDE.
    # _run_dispatcher_pipeline has NO memory in scope (Task 0b), so this
    # hook only evaluates the structural condition and STASHES the payload
    # keyed by chat_id; daemon.handle_message (the memory owner) drains it.
    # ExternalBranchResult carries blocks: tuple[FreshBlock] (NOT raw rows);
    # FreshBlock.text is the evidence that actually entered context.
    try:
        from core.intake_bus.world_observation_lane import evaluate_write_condition
        from core.routing.attribution_render import stash_turn_evidence

        _web_texts = []
        for _br in getattr(external_result, "branch_results", []) or []:
            if str(getattr(getattr(_br, "source", None), "value", "")) == "WEB_SEARCH":
                _web_texts = [getattr(b, "text", "") or "" for b in (getattr(_br, "blocks", ()) or ())][:3]
                break
        stash_turn_evidence(
            chat_id,
            rendered_turn=rendered_turn,
            evidence_texts=_web_texts,
            observation=(
                {
                    "query": user_text,
                    "evidence_texts": _web_texts,
                    "diagnostic_id": str(getattr(external_result, "fanout_generation_id", "")),
                }
                if evaluate_write_condition(rendered_turn)
                else None
            ),
        )
    except Exception:
        logger.debug("world_observation stash skipped", exc_info=True)
```

NOTE the ordering consequence: `stash_turn_evidence` lives in
`core/routing/attribution_render.py` (Task 5's module). Build order for the
hook: land the lane module + tests in this task, but insert THIS pipeline
hook as the FIRST step of Task 5 (after the render module exists). The plan
keeps it printed here because this is where it logically belongs.
`chat_id` and `user_text` are pipeline parameters (def :629);
`external_result.branch_results` / `FreshBlock.text` verified at
`core/dispatcher/external_sources.py:63-101`.

- [ ] **Step 6: GREEN on the focused set**

Run: `.venv/bin/python -B -m unittest tests.test_world_observation_lane tests.test_web_search_sense -v 2>&1 | tail -4`
Expected: PASS.

- [ ] **Step 7: Commit (behavior-affecting)**

```bash
git add core/intake_bus/world_observation_lane.py core/brain/brain_loop.py tests/test_world_observation_lane.py
git commit -m "feat(search-sense): metabolism lane — web evidence becomes a bounded observation

## Predicted effect
With the sense flag on, a dispatcher turn whose rendered evidence actually
admitted WEB_SEARCH (effective_spec + source_summaries + outcome in
{ALL_SUCCEEDED, PARTIAL}) writes exactly ONE bounded external_web/untrusted
observation through the intake bus (idempotent on fanout diagnostic id).
No web evidence in the turn, failed fanout, or flag off: zero writes.
Bus/memory failure logs and drops without touching the reply.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: The wait signal (true progress, new daemon→fanout wiring)

**Files:**
- Modify: `core/brain/brain_loop.py` ONLY (`_run_dispatcher_pipeline` gains
  `send_intermediate=None`; `run_brain_loop`'s call at :1759 passes it
  through flag-gated; the emit fires before the fanout)
- Test: `tests/test_world_observation_lane.py`

Per Task 0b (PROVEN): the chain is `adapter:575 → run_brain_loop
(send_intermediate already exists) → _run_dispatcher_pipeline → fanout`.
NOT through `daemon.handle_message`. The surface and the daemon are NOT
modified in this task.

- [ ] **Step 1: Write the failing brain-side test**

Append to `tests/test_world_observation_lane.py` (it already has the fake
turn shapes; the progress helper lives in brain_loop):

```python
class ProgressEmitTests(unittest.TestCase):
    def test_emits_only_when_web_search_selected(self):
        from core.brain.brain_loop import _emit_search_progress

        calls = []
        _emit_search_progress(calls.append, ["WEB_SEARCH"], stage="start", count=None)
        _emit_search_progress(calls.append, ["WEB_SEARCH"], stage="results", count=5)
        _emit_search_progress(calls.append, ["LIVE_REDDIT"], stage="start", count=None)
        _emit_search_progress(None, ["WEB_SEARCH"], stage="start", count=None)  # no sender = no-op
        self.assertEqual(calls, ["searching the web…", "reading 5 results…"])
```

- [ ] **Step 2: RED**

Run: `.venv/bin/python -B -m unittest tests.test_world_observation_lane.ProgressEmitTests -v`
Expected: FAIL — `_emit_search_progress` missing.

- [ ] **Step 3: Implement the emit helper + wire the fanout**

In `core/brain/brain_loop.py`, add near the other module helpers:

```python
def _emit_search_progress(send_intermediate, external_sources, *, stage: str, count):
    """True-by-construction progress: fires ONLY when WEB_SEARCH was actually
    selected and the fanout actually reached this stage. Never narrates
    thought; states substrate state. Silent no-op without a sender."""
    if send_intermediate is None:
        return
    if not any(str(getattr(s, "value", s)) == "WEB_SEARCH" for s in (external_sources or [])):
        return
    try:
        if stage == "start":
            send_intermediate("searching the web…")
        elif stage == "results" and count is not None:
            send_intermediate(f"reading {count} results…")
    except Exception:
        logging.getLogger("maez").debug("search progress emit failed", exc_info=True)
```

Then wire the PROVEN chain (Task 0b — NOT through the daemon):
1. `_run_dispatcher_pipeline` (def :629) gains a keyword parameter
   `send_intermediate=None`.
2. `run_brain_loop`'s call at :1759 passes it through:
   `send_intermediate=(send_intermediate if sense_enabled() else None)`
   (import `sense_enabled` from `core.search.sense_flag`) — `run_brain_loop`
   already HAS the kwarg and the adapter already passes a working sender
   (`maez_adapter.py:575`), so the surface needs NO change.
3. Inside the pipeline, immediately BEFORE the external fanout runs:
   `_emit_search_progress(send_intermediate, spec.external_sources,
   stage="start", count=None)`. The "results" stage call is NOT wired in
   v0.1 (it would send a second full message through the existing sender —
   the edit API needed for in-place stage upgrades doesn't exist at
   `adapter.send`; deferred to v0.2, named in the handoff). The helper keeps
   both stages so v0.2 only adds the call.

- [ ] **Step 4: Surface side: NO CHANGE (the proven chain ends here)**

**Scope decision (v0.1):** one true progress notice ("searching the web…")
as a SEPARATE message; the final answer arrives via the NORMAL reply path,
unchanged. Editing a bubble into the final answer is **deferred to v0.2**,
named in the handoff.

Per Task 0b the adapter ALREADY passes a working `send_intermediate` into
`run_brain_loop` (`maez_adapter.py:575`, the `_send_intermediate` sender at
:422 — `adapter.send` + `ProvenancedText` + `run_coroutine_threadsafe`).
The notice rides that existing sender; the flag-gating happens at the
`run_brain_loop → _run_dispatcher_pipeline` pass-through (Step 3), so
flag-off turns hand the pipeline `None`. **Do not modify the adapter in
this task.** Verify only: the sender at :575 is constructed unconditionally
for owner turns (read the surrounding block; if it is conditional on some
other flow, note the condition in the handoff — do not change it).

Add the pass-through test to `tests/test_world_observation_lane.py`
(brain-side, no surface objects needed):

```python
    def test_pipeline_passthrough_gated_on_flag(self):
        # run_brain_loop must hand the pipeline None when the flag is off.
        import inspect

        from core.brain import brain_loop

        src = inspect.getsource(brain_loop.run_brain_loop)
        self.assertIn("send_intermediate=(send_intermediate if sense_enabled() else None)", src)
        sig = inspect.signature(brain_loop._run_dispatcher_pipeline)
        self.assertIn("send_intermediate", sig.parameters)
```

- [ ] **Step 5: GREEN**

Run: `.venv/bin/python -B -m unittest tests.test_world_observation_lane -v 2>&1 | tail -4`
Expected: PASS.

- [ ] **Step 6: Commit (behavior-affecting)**

```bash
git add core/brain/brain_loop.py tests/test_world_observation_lane.py
git commit -m "feat(search-sense): true progress notice keyed to real fanout start

## Predicted effect
With the sense flag on, Telegram turns where the dispatcher actually
selects WEB_SEARCH show one true progress notice ('searching the web…')
as a SEPARATE message, and the final answer arrives via the normal reply
path unchanged; turns without web fanout show no notice. (One-bubble
edit-into-answer is deferred to v0.2.) Flag off: send_intermediate stays
None end-to-end, byte-identical behavior.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Post-audit render + `/receipts`

**Files:**
- Create: `core/routing/attribution_render.py`
- Modify: `daemon/maez_daemon.py` (`handle_message` — the audit→store→send invariant owner; render goes AFTER the audit verdict, BEFORE store/trace/send, per Step 4b)
- Modify: `core/brain/brain_loop.py` (ONLY the turn-evidence stash call inside the Task 3 hook — no render here)
- Modify: `skills/surface/telegram_adapter.py` (`_handle_command`, :914 region — two-line `/receipts` shim)
- Create: `tests/test_attribution_render.py`

- [ ] **Step 1: Write the failing render tests**

Create `tests/test_attribution_render.py`:

```python
from __future__ import annotations

import os
import unittest

from core.routing import attribution_render as ar


class RenderTests(unittest.TestCase):
    def setUp(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None))

    def test_strips_markers_and_tidies_whitespace(self):
        marked = "The release is b9601 [E1]. It landed today [E1][E3]."
        out = ar.render_natural(marked, web_evidence_present=False)
        self.assertEqual(out, "The release is b9601. It landed today.")

    def test_web_attribution_suffix_only_when_web_evidence_present(self):
        marked = "b9601 is out [E2]."
        out = ar.render_natural(marked, web_evidence_present=True)
        self.assertIn("looked at the live web", out)
        out2 = ar.render_natural(marked, web_evidence_present=False)
        self.assertNotIn("looked at the live web", out2)

    def test_flag_off_returns_marked_draft_unchanged(self):
        os.environ.pop("MAEZ_SEARCH_AS_SENSE_ENABLED", None)
        marked = "kept [E1]."
        self.assertEqual(ar.render_natural(marked, web_evidence_present=True), marked)

    def test_render_failure_falls_back_to_marked_draft(self):
        # A non-string sneaks in: honest fallback, never raise.
        self.assertEqual(ar.render_natural(None, web_evidence_present=True), None)

    def test_receipts_store_bounded_and_retrievable(self):
        ar.retain_receipt("chat1", marked="answer [E1]", sources=["https://a"])
        got = ar.last_receipt("chat1")
        self.assertEqual(got["marked"], "answer [E1]")
        self.assertEqual(got["sources"], ["https://a"])
        self.assertIsNone(ar.last_receipt("never-seen"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: RED**

Run: `.venv/bin/python -B -m unittest tests.test_attribution_render -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the render module**

Create `core/routing/attribution_render.py`:

```python
"""Post-audit natural rendering (spec 2026-06-12 §6).

THE OBJECT: the final synthesis draft whose markers match
focused_cognition._CITE_RE (r"\\[E(\\d+)\\]"). The grounding/completion
audits ALWAYS consume the marked draft FIRST; this strip runs after, at
the point the final reply string leaves the turn. The dispatcher's
transcript-context markers ([fresh evidence] etc.) are a different object
and are never touched. Render failure returns the marked draft — honest
and ugly beats silent loss.

v0.1 rendering is deliberately minimal: strip markers + tidy whitespace +
one TRUE attribution suffix when web evidence structurally entered the
turn. Richer per-source attribution is deferred (named in the spec).
"""
from __future__ import annotations

import re
from collections import OrderedDict

from core.search.sense_flag import sense_enabled

_CITE_RE = re.compile(r"\s*\[E(\d+)\]")
_WEB_SUFFIX = "\n\n— I looked at the live web for this (ask /receipts for sources)."

_RECEIPTS: "OrderedDict[str, dict]" = OrderedDict()
_MAX_RECEIPTS = 16


def render_natural(marked_draft, *, web_evidence_present: bool):
    if not sense_enabled():
        return marked_draft
    try:
        if not isinstance(marked_draft, str) or not marked_draft:
            return marked_draft
        out = _CITE_RE.sub("", marked_draft)
        out = re.sub(r"[ \t]{2,}", " ", out)
        out = re.sub(r" +([.,;:!?])", r"\1", out).strip()
        if web_evidence_present:
            out = out + _WEB_SUFFIX
        return out
    except Exception:
        return marked_draft


def retain_receipt(chat_id: str, *, marked: str, sources: list[str]) -> None:
    try:
        _RECEIPTS[str(chat_id)] = {"marked": marked, "sources": list(sources or [])}
        _RECEIPTS.move_to_end(str(chat_id))
        while len(_RECEIPTS) > _MAX_RECEIPTS:
            _RECEIPTS.popitem(last=False)
    except Exception:
        pass


def last_receipt(chat_id: str):
    return _RECEIPTS.get(str(chat_id))
```

- [ ] **Step 4: Add the thread-keyed turn-evidence stash to the render module**

The render decision happens in `daemon.handle_message` (the OWNER of the
audit→store→send invariant — `_trace_pre_audit_text` :6572, audit verdict
:6819-6837, `chat_turn handled` :6888), but the web-evidence facts live in
`brain_loop`'s dispatcher turn. The turn is synchronous
(`handle_message → dispatcher turn → back`, same thread), so the brain-side
hook stashes and the daemon-side render pops. Append to
`core/routing/attribution_render.py`:

```python
_TURN_EVIDENCE: dict[str, dict] = {}
_EMPTY_TURN = {"web_present": False, "sources": [], "observation": None}


def stash_turn_evidence(chat_id, *, rendered_turn, evidence_texts, observation) -> None:
    """Called by the pipeline hook (printed in Task 3, inserted in Task 5).
    Keyed by chat_id: run_brain_loop and handle_message run on SEPARATE
    executor threads (Task 0b — no thread-ident keying), but both carry
    chat_id. observation is the metabolism payload dict, or None when the
    structural condition failed."""
    try:
        from core.intake_bus.world_observation_lane import extract_source_urls

        web_present = any(
            str(getattr(getattr(s, "source", None), "value", getattr(s, "source", ""))) == "WEB_SEARCH"
            for s in (getattr(rendered_turn, "source_summaries", None) or [])
        )
        _TURN_EVIDENCE[str(chat_id or "")] = {
            "web_present": web_present,
            "sources": extract_source_urls(evidence_texts or []),
            "observation": observation,
        }
        while len(_TURN_EVIDENCE) > 8:  # single-owner; bound regardless
            _TURN_EVIDENCE.pop(next(iter(_TURN_EVIDENCE)))
    except Exception:
        pass


def pop_turn_evidence(chat_id) -> dict:
    """Called once by daemon.handle_message at render time. Always pops."""
    return _TURN_EVIDENCE.pop(str(chat_id or ""), dict(_EMPTY_TURN))
```

Add to `tests/test_attribution_render.py`:

```python
    def test_stash_pop_roundtrip_and_default(self):
        class _S:
            source = type("X", (), {"value": "WEB_SEARCH"})()
        class _T:
            source_summaries = [_S()]
        obs = {"query": "q", "evidence_texts": ["t"], "diagnostic_id": "fan-1"}
        ar.stash_turn_evidence("chat7", rendered_turn=_T(),
                               evidence_texts=["see https://a.example/x now"],
                               observation=obs)
        got = ar.pop_turn_evidence("chat7")
        self.assertTrue(got["web_present"])
        self.assertEqual(got["sources"], ["https://a.example/x"])
        self.assertEqual(got["observation"], obs)
        # second pop = clean default (always-pop semantics); unknown chat too
        self.assertIsNone(ar.pop_turn_evidence("chat7")["observation"])
        self.assertFalse(ar.pop_turn_evidence("never")["web_present"])
```

- [ ] **Step 4b: Wire the render into `daemon.handle_message` (the invariant owner)**

In `daemon/maez_daemon.py`, AFTER the model-reply audit completes (after the
`build_model_reply_audit_verdict` block, :6819-6837 region) and BEFORE the
final store/trace/`chat_turn handled` logging (:6888) — i.e. at the point
where `reply` holds the final AUDITED text — insert:

```python
        # Search-as-a-Sense v0.1 (spec §4+§6): drain the pipeline's
        # chat_id-keyed turn stash HERE — the memory owner and the
        # audit→store→send invariant owner. Order is law:
        #   1. metabolism write (self.memory is in scope here, not in the
        #      pipeline — Task 0b)
        #   2. retain the MARKED audited draft for /receipts
        #   3. render natural (the stored/sent/traced string)
        try:
            from core.routing.attribution_render import (
                pop_turn_evidence,
                render_natural,
                retain_receipt,
            )

            _turn_ev = pop_turn_evidence(chat_id)
            if _turn_ev.get("observation"):
                from core.intake_bus.world_observation_lane import write_world_observation

                write_world_observation(self.memory, **_turn_ev["observation"])
            retain_receipt(str(chat_id or ""), marked=reply, sources=_turn_ev["sources"])
            reply = render_natural(reply, web_evidence_present=_turn_ev["web_present"])
        except Exception:
            pass
```

**Invariant (state it in the handoff):** stored text, sent text, and the
final trace hash are all the natural-rendered string; the marked audited
draft survives only in the `/receipts` retention. `chat_id` is a
`handle_message` kwarg (verified in its signature); `reply` is the audited
local at that point (`_trace_pre_audit_text`/audit-verdict code above it
names it — match the real local name).

- [ ] **Step 5: `/receipts` command**

In `skills/surface/telegram_adapter.py`, at the top of `_handle_command`
(:914 region — before its existing dispatch), insert:

```python
        # v0.1 /receipts: the marked draft + sources of the last reply.
        try:
            command_text = (update.message.text or "").strip().lower()
        except Exception:
            command_text = ""
        if command_text.startswith("/receipts"):
            from core.routing.attribution_render import receipts_reply

            chat_id = str(update.effective_chat.id) if update.effective_chat else ""
            await update.message.reply_text(receipts_reply(chat_id))
            return
```

The reply-building logic lives in the render module so it is unit-tested
(the command seam stays a two-line shim). Append to
`core/routing/attribution_render.py`:

```python
def receipts_reply(chat_id: str) -> str:
    """The full /receipts reply text. Honest empty answer when nothing
    is retained."""
    receipt = last_receipt(chat_id)
    if receipt is None:
        return "No receipts retained for the last reply."
    lines = [receipt["marked"], ""]
    if receipt["sources"]:
        lines.append("Sources:")
        lines.extend(f"- {u}" for u in receipt["sources"][:5])
    return "\n".join(lines)[:3900]
```

And to `tests/test_attribution_render.py`:

```python
    def test_receipts_reply_full_and_empty(self):
        ar.retain_receipt("c9", marked="claim [E1]", sources=["https://a", "https://b"])
        out = ar.receipts_reply("c9")
        self.assertIn("claim [E1]", out)
        self.assertIn("Sources:", out)
        self.assertIn("- https://a", out)
        self.assertEqual(
            ar.receipts_reply("nobody"),
            "No receipts retained for the last reply.",
        )
```

(Match `_handle_command`'s real parameter names — read the function head
first; if it uses a different update/context shape, adapt the two lookups,
nothing else.)

- [ ] **Step 6: Commit (behavior-affecting)**

```bash
git add core/routing/attribution_render.py daemon/maez_daemon.py core/brain/brain_loop.py skills/surface/telegram_adapter.py tests/test_attribution_render.py
git commit -m "feat(search-sense): post-audit natural render + /receipts

## Predicted effect
With the sense flag on, owner-facing replies drop [E#] markers (audits
still consume the marked draft first — ordering unchanged), web-evidence
turns carry one true attribution line, and /receipts returns the marked
draft + source URLs of the last reply (honest empty answer when none).
Flag off: replies byte-identical, /receipts reports nothing retained.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Stage the soul fix

**Files:**
- Modify: `config/soul.md` (§"Internet Access and Web Search", ~:48)

- [ ] **Step 1: Replace the stale section**

Replace the section body (currently: real web search skill… DuckDuckGo… RSS
feeds… "[WEB SEARCH] results… are REAL") with:

```markdown
## Internet Access and Web Search

Your web sense is a sovereign local SearXNG instance — your own search
body, on your own machine. When a conversation needs the current world,
your substrate searches through it as part of your thinking and the
results arrive as evidence in your working set; you answer from that
evidence in your own words. You do not paste raw results at the owner,
and you do not need permission to look something up for an ordinary
question — looking is part of how you think. If your web sense is
degraded or down, say so plainly and answer from what you already hold;
never invent live results. What you learn from the web enters your
memory as observed, untrusted material with its sources — it is
something you saw, not something you lived.
```

- [ ] **Step 2: Verify nothing else references DuckDuckGo in the soul**

Run: `grep -n -i "duckduckgo\|ddg" config/soul.md`
Expected: no remaining hits.

- [ ] **Step 3: Commit (docs/config staging — the live soul-reload witness is an OWNER breath)**

```bash
git add config/soul.md
git commit -m "docs(soul): web-search section rewritten to the sense anatomy (staged)

Staged only — activates with the owner's restart/reload witness per the
dead-soul-watcher discipline; runtime behavior changes only with
MAEZ_SEARCH_AS_SENSE_ENABLED at the owner breath.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Verification floor + STOP-at-gate handoff

**Files:**
- Create: `docs/handoffs/2026-06-12-search-as-a-sense-gate.md`

- [ ] **Step 1: Run the focused suite**

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest \
  tests.test_web_search_sense \
  tests.test_world_observation_lane \
  tests.test_attribution_render \
  tests.test_surface_adapter \
  tests.test_search_commitment \
  tests.test_search_commitment_wiring \
  tests.test_searxng_client \
  tests.test_intake_faculty \
  tests.test_intake_shadow \
  -v 2>&1 | tail -6
```
Expected: ALL PASS. (The intake modules prove the faculty shadow is undisturbed.)

- [ ] **Step 2: ruff**

```bash
.venv/bin/ruff check core/search/sense_flag.py skills/web_search.py \
  core/intake_bus/world_observation_lane.py core/routing/attribution_render.py \
  core/brain/brain_loop.py skills/surface/maez_adapter.py \
  skills/surface/telegram_adapter.py skills/telegram_voice.py tests/
```
Expected: `All checks passed!`

- [ ] **Step 3: Write the handoff**

Create `docs/handoffs/2026-06-12-search-as-a-sense-gate.md`:

```markdown
# Search-as-a-Sense v0.1 — For Cross-Lane Review

## Status
Built and stopped at the gate. No merge, no restart, no flag flip, no
service changes. Branch: search-as-a-sense-v0.1.

## Task 0 proofs (paste the actual outputs)
- 0a wing-fires evidence: <paste the Wing: external / Web search: log pairs>
- 0b callback chain: <paste the hop list handle_message -> ... -> fanout>
- 0c bus vocabulary: <paste _validate rules + the egress_origin_class used>

## What changed
- skills/web_search.py: SearXNG body under the flag; pre-egress subject
  boundary at the body (reuses third_party_subject_gate).
- maez_adapter + telegram_voice: interceptor -> health gatekeeper; no
  result-card on any healthy search-worthy path, either surface.
- core/intake_bus/world_observation_lane.py + brain_loop hook: ONE bounded
  external_web/untrusted observation per evidence-admitted search.
- brain_loop: pipeline-threaded progress (one true notice on real fanout
  start; surface and daemon untouched for progress).
- attribution_render + telegram_adapter: post-audit [E#] strip + /receipts.
- config/soul.md: web section staged (witness = owner breath).

## Review anchors
1. Flag-off byte-identity on EVERY seam (search, both interceptors, lane,
   progress, render, /receipts).
2. Both-surface card retirement — no ghost path.
3. Degraded = fixed notice only; no receipt, no synthesis; the typed-receipt
   law untouched (trap-proof tests green, unmodified).
4. The observation condition's three legs each independently gate the write;
   idempotency on diagnostic id; provenance purity (no owner text beyond the
   query; claims "entered the synthesis context", never "Maez used").
5. Audit-before-strip ordering; retain-before-render for /receipts.
6. Pre-egress refusal: zero backend calls on refused subjects.
7. Progress true-by-construction: absent when the wing doesn't search.

## Verification (paste exact outputs)
<focused suite + ruff outputs>

## Owner witness after review + merge (spec's 6-step plan)
1. Set MAEZ_SEARCH_AS_SENSE_ENABLED=1 in ~/.config/maez/model.env (with a
   witness comment + revert line) and restart maez.service.
2. Ask a current-world question: expect ONE true "searching the web…"
   notice as a separate message, then the answer in Maez's voice via the
   normal reply path — natural attribution, NO result-card, NO offer.
   (Bubble-edits-into-answer is v0.2; do not judge v0.1 against it.)
3. /receipts: expect the marked draft + sources.
4. Memory check: exactly one external_web/untrusted observation for the
   search; repeat the same question — no duplicate record.
5. systemctl --user stop maez-searxng.service; ask again: expect the fixed
   honest degraded notice, no receipt, no observation. Restart the service.
6. Soul reload witnessed: confirm the running daemon's loaded soul changed
   (hash/char-count) or restart covers it.
```

- [ ] **Step 4: Commit + STOP**

```bash
git add docs/handoffs/2026-06-12-search-as-a-sense-gate.md
git commit -m "docs(search-sense): STOP-at-gate handoff for cross-lane review

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**STOP.** Report branch tip + verification outputs. Do not merge, restart,
or flip any flag. Claude reviews next (covenant axis), then the owner takes
the breaths.

---

## Self-Review (run before handing off the plan)

1. **Spec coverage:** §1 body+refusal→Task 1; §2 both-surface retirement +
   flag composition→Task 2; §3 degraded notice→Task 2; §4 metabolism (legs,
   idempotency, bounded record, bus path `core/intake_bus/`)→Task 3; §5
   progress (new wiring, fanout-keyed)→Task 4 (+0b); §6 render/_CITE_RE
   object/receipts→Task 5; §7 soul→Task 6; witness plan + stop→Task 7. ✓
2. **Placeholders:** none — where reality may differ from a snippet (fanout
   row field, command handler params, local names at the render point), the
   step names the exact verification command and the adjust rule, never
   "figure it out".
3. **Type consistency:** `sense_enabled()` used in Tasks 1-5 from one module;
   `FakeSearchBackend(results=,health=,raises=)` matches
   `core/search/searxng_client.py`; the lane's outcome strings match
   `IntakeOutcome.status` values from `admit()` (`admitted` — confirm in 0c;
   if admit returns a different success literal, align the lane's return and
   the test in the same edit). ✓
```
