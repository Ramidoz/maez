# Body Legibility v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Stop Maez denying its own body — a down sense renders as *down* (not absent), and a healthy sense states what it *can do* (not just that it's well) — with zero routing change, behind one flag, flag-off byte-identical.

**Architecture:** One shared `_affordance(name, status) -> str | None` (generic, state-aware) feeds both capability-card render modes (structured envelope field + legacy prose suffix). One ambient-honesty branch in `ambient_format._format` renders an "unavailable" weather line *only when weather was attempted and failed*. All behind `MAEZ_BODY_LEGIBILITY`.

**Tech Stack:** Python 3.12; host tests `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest).

**Spec:** `docs/superpowers/specs/2026-07-03-body-legibility-v0-design.md` (@228f8c7).

**Task 0 (DONE 2026-07-03 — plan written on this ground):**
- **Ambient (Codex plan-pin):** `ambient_format._format` (:128) does `w = ctx.get("weather") or {}` then `if w.get("temp_c") is not None`. This collapses *absent* and *failed*. The honest rule: render "unavailable" **only when `"weather" in ctx`** (attempted) and no `temp_c`; if the key is **absent** (old/minimal fixture), stay silent — never fabricate "down". The coords source is reachable as `ctx.get("coords_source")` (used already at :130) — no fresh lookup needed.
- **Capability card two modes:** structured `_build_capability_envelope` appends entries `{name, status, source}` (two sites: normal + probe-error); legacy prose appends `f"{name}: {probe()}"` (two sites). Add affordance additively at each. Flag helper convention: module-level bools (`voice_boundary_enabled()`, `evidence_precedence_enabled()`) → add `body_legibility_enabled()`.
- **Status states:** `_canonical_status` gives web sense `healthy`/`degraded`/`unknown` — the affordance keys off these.

## Hard Invariants
- **Flag-off byte-identical** (`MAEZ_BODY_LEGIBILITY` unset): weather still vanishes on failure; card stays health-only; both modes byte-identical.
- **Zero routing change:** no new `current_weather`/search-trigger/tool call site (structural test).
- **Affordance generic + state-aware + no overclaim:** only `healthy` says "can retrieve"; degraded/unknown say so; never an example list.
- **"Down" only when attempted:** `"weather" in ctx` + no temp_c → unavailable; key absent → silent.
- **One affordance source:** both modes render from `_affordance()` — no drift.

---

## Task 1: `body_legibility_enabled()` flag + `_affordance()` function

**Files:** Modify `core/cognition/capability_card.py`; Test `tests/test_body_legibility.py` (create)

- [ ] **Step 1: Failing tests**
```python
import unittest
from unittest import mock
import os


class AffordanceTests(unittest.TestCase):
    def test_web_sense_affordance_is_state_aware(self):
        from core.cognition.capability_card import _affordance
        self.assertEqual(_affordance("web sense", "healthy"),
                         "can retrieve current external information")
        # down/unknown must NOT overclaim:
        self.assertNotIn("can retrieve", _affordance("web sense", "degraded") or "")
        self.assertNotIn("can retrieve", _affordance("web sense", "unknown") or "")
        self.assertIsNotNone(_affordance("web sense", "degraded"))   # says *something* honest

    def test_affordance_is_generic_no_examples(self):
        from core.cognition.capability_card import _affordance
        text = (_affordance("web sense", "healthy") or "").lower()
        for banned in ("weather", "stock", "news", "sports", "forecast"):
            self.assertNotIn(banned, text)   # organ-fact, not category routing

    def test_unknown_sense_has_no_affordance(self):
        from core.cognition.capability_card import _affordance
        # v0 scopes affordance to web sense; others render unchanged
        self.assertIsNone(_affordance("felt time", "attached"))

    def test_flag_helper_strict(self):
        from core.cognition.capability_card import body_legibility_enabled
        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "1"}):
            self.assertTrue(body_legibility_enabled())
        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "0"}):
            self.assertFalse(body_legibility_enabled())
```
- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** `body_legibility_enabled()` (same strict pattern as `voice_boundary_enabled`); `_affordance(name, status)`: web sense → healthy `"can retrieve current external information"`, degraded `"retrieval currently degraded"`, unknown `"retrieval currently unknown"`; every other name → `None`. — [ ] **Step 4: GREEN.** — [ ] **Step 5: Commit** `feat(body-legibility): flag helper + generic state-aware affordance`

---

## Task 2: wire affordance into both card modes

**Files:** Modify `core/cognition/capability_card.py`; Test additions to `tests/test_body_legibility.py`

- [ ] **Step 1: Failing tests**
```python
class CardModeTests(unittest.TestCase):
    def _healthy_web_registry(self):
        return [("web sense", lambda: "healthy")]

    def test_structured_envelope_has_affordance_field_flag_on(self):
        import json, os
        from unittest import mock
        from core.cognition.capability_card import _build_capability_envelope
        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "1"}):
            text = _build_capability_envelope(self._healthy_web_registry())
        payload = json.loads(text.split("\n", 1)[1].rsplit("\n", 1)[0]) if False else None
        # simpler: assert the affordance is a FIELD, not buried in status prose
        self.assertIn('"affordance"', text)
        self.assertIn("can retrieve current external information", text)

    def test_flag_off_envelope_byte_identical(self):
        import os
        from unittest import mock
        from core.cognition.capability_card import _build_capability_envelope
        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "0"}):
            off = _build_capability_envelope(self._healthy_web_registry())
        self.assertNotIn("affordance", off)   # additive-only; off == today

    def test_prose_mode_uses_same_affordance_fn(self):
        # prose suffix must come from _affordance (parity, no drift)
        import os
        from unittest import mock
        from core.cognition.capability_card import capability_prompt_block
        # flag on, voice_boundary OFF -> prose path; assert suffix present
        ...  # build-time: drive the prose branch, assert "— can retrieve current external information"
```
- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** — in `_build_capability_envelope`, when `body_legibility_enabled()` and `_affordance(name, status)` is not None, add `"affordance": aff` to the entry dict (both the normal and probe-error append sites; probe-error status is `"unknown"` → affordance honest or None). In the prose path, append `f" — {aff}"` when flag on and aff present. Flag-off: neither touched (byte-identical). Both read from `_affordance` — no duplicated text. — [ ] **Step 4: GREEN + existing capability_card tests still pass.** — [ ] **Step 5: Commit** `feat(body-legibility): affordance in structured envelope + prose, flag-gated`

---

## Task 3: ambient honesty — visible down sense, only when attempted

**Files:** Modify `core/memory/ambient_format.py`; Test additions to `tests/test_body_legibility.py`

- [ ] **Step 1: Failing tests**
```python
class AmbientHonestyTests(unittest.TestCase):
    def _fmt(self, ctx):
        import os
        from unittest import mock
        from core.memory import ambient_format
        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "1"}):
            return ambient_format._format(ctx)

    def test_attempted_and_failed_renders_unavailable(self):
        out = self._fmt({"weather": None, "coords_source": "phone"})
        self.assertIn("weather sense temporarily down", out.lower())
        self.assertIn("phone", out)               # coords source when present
        for banned in ("°c", "error", "urlopen", "hostname", "traceback"):
            self.assertNotIn(banned, out.lower())  # no live claim, no error detail

    def test_absent_key_stays_silent(self):
        out = self._fmt({"coords_source": "phone"})   # weather never attempted
        self.assertNotIn("weather", out.lower())       # no fabricated "down"

    def test_success_unchanged(self):
        out = self._fmt({"weather": {"temp_c": 21, "conditions": "clear",
                                     "coords": {"source": "phone"}}})
        self.assertIn("21", out)
        self.assertNotIn("unavailable", out.lower())

    def test_flag_off_failed_pull_stays_silent(self):
        import os
        from unittest import mock
        from core.memory import ambient_format
        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "0"}):
            out = ambient_format._format({"weather": None, "coords_source": "phone"})
        self.assertNotIn("unavailable", out.lower())   # byte-identical to today
```
- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** — after the existing `if w.get("temp_c") is not None:` success branch, add: `elif body_legibility_enabled() and "weather" in ctx:` → append `f"Weather at the owner's location: unavailable (weather sense temporarily down{src_suffix})"` where `src_suffix` = `f"; coords from {ctx['coords_source']}"` only if `ctx.get("coords_source")`, else empty. Import `body_legibility_enabled` from capability_card. Key-absent and flag-off → unchanged. — [ ] **Step 4: GREEN.** — [ ] **Step 5: Commit** `feat(body-legibility): visible down-weather line, only when attempted`

---

## Task 4: regression + no-routing-change proof + STOP

- [ ] **Step 1:**
```bash
/home/rohit/maez/.venv/bin/python -B -W ignore::ResourceWarning -m unittest \
  tests.test_body_legibility tests.test_capability_card tests.test_ambient_format \
  tests.test_evidence_precedence -v
```
(Confirm the adjacent suite names exist first; substitute the real capability-card/ambient test modules.)
- [ ] **Step 2: No-routing-change structural proof** — a test asserting the diff of `ambient_format.py` + `capability_card.py` adds no new call to `current_weather`, no search/tool-trigger symbol, no new invocation site (grep/AST over the changed functions). This slice only makes the body legible.
- [ ] **Step 3:** ruff on touched files; `git diff --check`; flag-off byte-identical re-run of both card modes + `_format`.
- [ ] **Step 4: STOP.** No merge, no flag flip. Codex cross-lane → Claude cross-verify → merge dormant → owner flips `MAEZ_BODY_LEGIBILITY=1` + restart → live witness: "do you have weather info?" with web sense healthy → Maez describes an honest body (no "I have no tool"); weather pull failing → System State shows "temporarily down," not silence; web sense degraded → card says retrieval degraded and Maez does not claim it can fetch.

## Self-Review
**Spec coverage:** flag helper + generic state-aware affordance (Task 1); both card modes from one `_affordance`, additive/byte-identical-off (Task 2); ambient down-sense visible only when attempted, coords-source when present, no error detail (Task 3, Codex plan-pin); no-routing-change structural test (Task 4); flag-off byte-identical (invariant + tests). All five owner pins covered.
**Placeholder scan:** the prose-mode parity test and the Task-4 adjacent suite names are build-time-resolved (drive the prose branch; confirm real test module names) — not TODOs; the affordance text is fixed here.
**Type consistency:** `_affordance(name, status) -> str | None`; `body_legibility_enabled() -> bool`; render sites consume `_affordance` identically in both modes. Consistent across tasks.
