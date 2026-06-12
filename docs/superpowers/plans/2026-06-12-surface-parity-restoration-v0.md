# Surface Parity Restoration v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-attach three organs orphaned on the dead inbound surface — proposal approvals (the owner's consent channel), felt-time, D20 gap detection — plus a loudness guard against the next orphan, behind one strict-parsed flag, and install the Build Ledger that prevents recurrence.

**Architecture:** Surface V2 (`maez_adapter.MaezMessageHandler.__call__`) is the live inbound path; `telegram_voice` is outbound-only since 2026-04-20. Each restoration ports the legacy organ's wiring into the live handler at the correct precedence, calling the SAME engines (no forks). Task 0 first creates `docs/MAEZ_BUILD_LEDGER.md` — the meta-organ that makes built-vs-live state legible — before any wiring.

**Tech Stack:** Python stdlib; existing engines (evolution proposal/dream stores, `subjective_duration`, `capability_gap_detector`, the pending-card pipeline); unittest + ruff.

**Spec:** `docs/superpowers/specs/2026-06-12-surface-parity-restoration-v0-design.md` (@6161134). **Audit:** `docs/SURFACE_PARITY_MAP_2026-06-12.md`. Read both first.

---

## Ground Rules

- Branch `surface-parity-restoration-v0` off main (@6161134). No push.
- STOP at the gate. Merge/flag/restart = owner breaths.
- ONE flag `MAEZ_SURFACE_PARITY_ENABLED`, STRICT parser (`{1,true,yes,on}`). Off ⇒ byte-identical EVERYWHERE incl. prompt bytes. Do NOT add a `bool(os.environ.get(...))` flag — the 0-truthy footgun is a logged HAZARD.
- `## Predicted effect` on the behavior tasks (3, 4, 5).
- Co-author trailer every commit.
- **THE LEDGER MAINTENANCE LAW:** the gate handoff (Task 6) updates every ledger row this arc touches. "Ledger rows updated" is a standing Claude review anchor from this arc on.
- Tests: fakes only; runner `/home/rohit/maez/.venv/bin/python -B -m unittest`; never full-discover.

## File Map

| Path | Responsibility |
|---|---|
| `docs/MAEZ_BUILD_LEDGER.md` (create) | The meta-organ: built-vs-live state, provenance-stamped. |
| `core/cognition/parity_flag.py` (create) | `surface_parity_enabled()` — strict parser. |
| `core/dispatcher/proposal_resolver.py` (create, IF 0b proof path) | Transport-neutral proposal-intent resolver shared by both surfaces. |
| `skills/telegram_voice.py` (modify) | R4 loudness guard; (proof path) delegate to the shared resolver. |
| `skills/surface/maez_adapter.py` (modify ×3) | R3 D20 call; R1 proposal interceptor; R2 felt-time auth. |
| `core/cognition/capability_card.py` (modify) | R2b: felt-time probe replaces the static entry. |
| `tests/test_*` (create/modify) | per task. |
| `docs/handoffs/2026-06-12-surface-parity-gate.md` (create) | STOP-at-gate handoff (updates the ledger). |

---

### Task 0-LEDGER: Create the Build Ledger (FIRST — docs only, no flag)

**Files:** Create `docs/MAEZ_BUILD_LEDGER.md`.

- [ ] **Step 1: Write the ledger** — create `docs/MAEZ_BUILD_LEDGER.md`:

```markdown
# Maez Build Ledger — the hospital chart

The single answer to: what is built, what is live, what is asleep, what is
orphaned, what must never be rebuilt. The Surface Parity Map is the accident
report; this is the chart that prevents the next accident.

## THE MAINTENANCE LAW
Every STOP-at-gate handoff MUST update the rows it touches (status,
last_verified_commit, last_verified_at, updated_by). "Ledger rows updated"
is a standing Claude review anchor. An unmaintained ledger is the
soul-staleness bug with nicer buckets — the law is the mitigation.
Status buckets: LIVE_WITNESSED · LIVE_SHADOW · BUILT_ASLEEP ·
BUILT_ORPHANED · SUPERSEDED_BY_DESIGN · PLANNED_SPEC · PLANNED_PLAN ·
HAZARD · DEFERRED.

| organ/slice | status | live seam | dead seam | flag/env | witness | owner breath | dup-risk | next action | last_verified_commit | last_verified_at | updated_by |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Proposal approvals (O1) | BUILT_ORPHANED | (none) | telegram_voice _try_proposal_intent:2321 / _try_dream_proposal_intent:2184 | MAEZ_SURFACE_PARITY_ENABLED | parity map | restore+witness | port not fork engines | R1 this arc | 6161134 | 2026-06-12 | claude |
| Felt-time / subjective duration (O2) | BUILT_ORPHANED | daemon.handle_message:5059 (ready) | maez_adapter:627 never passes auth | MAEZ_SURFACE_PARITY_ENABLED | parity map | restore+witness | card static entry must become probe | R2/R2b this arc | 6161134 | 2026-06-12 | claude |
| D20 gap detection (O3) | BUILT_ORPHANED | (none) | telegram_voice :3020-3223 | MAEZ_SURFACE_PARITY_ENABLED | parity map | restore+witness | uses pending_card_store, no manual send | R3 this arc | 6161134 | 2026-06-12 | claude |
| Search offer-binding interceptor | SUPERSEDED_BY_DESIGN | n/a | telegram_voice _try_offer_binding_intent | n/a | sense arc | none | DO NOT RESTORE (vending-machine regression) | none | 6161134 | 2026-06-12 | claude |
| Explicit web-search interceptor | SUPERSEDED_BY_DESIGN | n/a | telegram_voice _try_web_search_intent | n/a | sense arc | none | DO NOT RESTORE | none | 6161134 | 2026-06-12 | claude |
| Search-as-a-Sense | LIVE_WITNESSED | web_search.search + dispatcher wing | n/a | MAEZ_SEARCH_AS_SENSE_ENABLED | 2026-06-11/12 witness | none | n/a | none | 27463e7 | 2026-06-12 | claude |
| Page-Read Sense | LIVE_WITNESSED | external_sources FETCH_URL + page_extract | n/a | MAEZ_PAGE_READ_ENABLED | 2026-06-12 witness | none | n/a | none | 95bef07 | 2026-06-12 | claude |
| Evidence-Precedence / Capability-Health | LIVE_WITNESSED | capability_card + focused_cognition + evidence_state | n/a | MAEZ_EVIDENCE_PRECEDENCE_ENABLED | fourth-asking PASS | none | n/a | none | ebcab5b | 2026-06-12 | claude |
| Intake Faculty | LIVE_SHADOW | maez_adapter observe + intake_faculty | n/a | MAEZ_INTAKE_FACULTY_SHADOW | ledger accumulating | none | not graduated; marker regexes frozen pending it | graduation arc | 6d770f7 | 2026-06-12 | claude |
| Grounding shadow | LIVE_SHADOW | minicheck-verifier 8083 | n/a | MAEZ_GROUNDING_SHADOW_ENABLED | data-gated | none | absence-claimability gap (G1) | G1 loop | (prior) | 2026-06-12 | claude |
| Absence-claim shadow | LIVE_SHADOW | evidence_precedence_shadow | n/a | MAEZ_EVIDENCE_PRECEDENCE_ENABLED | rows recorded | none | n/a | none | ebcab5b | 2026-06-12 | claude |
| 0-truthy flag footgun | HAZARD | all bool(env) flags | n/a | (house-wide) | proven by execution | sweep+comment fix | strict parser exists in capability_card/parity_flag | Tier-1 hygiene loop | 6161134 | 2026-06-12 | claude |
| telegram_voice inbound trap | HAZARD | telegram_voice inbound methods look alive | n/a | n/a | parity map | none | next organ could solder here | R4 loudness guard this arc | 6161134 | 2026-06-12 | claude |
| /receipts page-URL | PLANNED_SPEC | attribution_render | n/a | MAEZ_PAGE_READ_ENABLED | G2 | none | trivial | hygiene loop | 6161134 | 2026-06-12 | claude |
| Felt-time first attachment | PLANNED_PLAN | (this arc R2) | n/a | MAEZ_SURFACE_PARITY_ENABLED | n/a | restore | n/a | R2 | 6161134 | 2026-06-12 | claude |
| Faculty graduation | DEFERRED | n/a | n/a | n/a | n/a | n/a | stance=yes over-read pattern | own arc | 6161134 | 2026-06-12 | claude |
| Affordance ledger / browser DOM | DEFERRED | n/a | n/a | n/a | n/a | n/a | senses stage 4-5 | own arc | 6161134 | 2026-06-12 | claude |
```

- [ ] **Step 2: Commit (docs only)**

```bash
cd /home/rohit/maez && git checkout -b surface-parity-restoration-v0
git add docs/MAEZ_BUILD_LEDGER.md
git commit -m "docs(ledger): create the Build Ledger — built-vs-live meta-organ

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 0-PROOFS: Prove the seams (NO wiring until recorded)

- [ ] **0a — the live handler seam:** `sed -n '268,430p' skills/surface/maez_adapter.py` and `grep -n "daemon.handle_message" skills/surface/maez_adapter.py`. Record: `guard_owner_text` (~:273), the open-cards block (:352-377), `_try_search_commitment_intent` (:420), the `daemon.handle_message(...)` call (:627 region). **R3** lands after :273 and before :352. **R1** lands after the card block (:377) and before :420. **R2** modifies the :627 call.

- [ ] **0b — the legacy proposal intents + THE RESOLVER DECISION:** `sed -n '2184,2420p' skills/telegram_voice.py`. Read fully: `_detect_proposal_intent`, `_list_pending_candidates`, `_last_shown_proposal`, the approve/reject/show matchers, `#N` resolution, dream-vs-evolution branching, and which engine calls execute the action. **DECISION (record in the handoff):**
  - **PROOF PATH (preferred):** extract a transport-neutral resolver
    `core/dispatcher/proposal_resolver.py` — pure functions
    `detect_proposal_intent(text) -> (action, explicit_id)`,
    `resolve_target(action, explicit_id, pending, last_shown) -> target|None`
    — that BOTH `telegram_voice` (refactored to delegate) and `maez_adapter`
    call. One parser forever.
  - **FALLBACK (only if the bodies are too entangled to extract this arc):**
    a Surface V2 matcher with STRUCTURAL PARITY TESTS proving equality with
    legacy on: approve/reject/show phrasing, `#N` resolution, last-shown
    binding, multi-proposal disambiguation, dream proposals.
  Record which, and why.

- [ ] **0c — felt-time auth:** `sed -n '2955,2990p' skills/telegram_voice.py` and `sed -n '5055,5135p' daemon/maez_daemon.py`. Record the `SubjectiveDurationOwnerAuth(...)` constructor fields and how the daemon consumes the param — R2 mirrors the constructor in the adapter.

- [ ] **0d — D20 contract:** `sed -n '191,240p' core/infra/capability_gap_detector.py` and `grep -n "card_store\|get_pipeline\|pipe" skills/surface/maez_adapter.py`. Confirm `maybe_fire_capability_proposal(user_text, *, pending_card_store=, chat_id=, user_id=, ...)` returns a dict, never raises, creates cards via `pending_card_store`. Record the adapter's live card-store access (`pipe.card_store`, :357). NO manual sending.

- [ ] **0e:** (branch already created in 0-LEDGER Step 2).

---

### Task 1: The strict-parser flag

**Files:** Create `core/cognition/parity_flag.py`; create `tests/test_parity_flag.py`.

- [ ] **Step 1: Failing test** — `tests/test_parity_flag.py`:

```python
from __future__ import annotations

import os
import unittest

from core.cognition.parity_flag import surface_parity_enabled


class ParityFlagTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None))

    def test_default_off(self):
        self.assertFalse(surface_parity_enabled())

    def test_strict_truthy(self):
        for v in ("1", "true", "yes", "on", "ON", "True"):
            os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = v
            self.assertTrue(surface_parity_enabled(), v)

    def test_zero_is_off_not_on(self):
        # The footgun: bool(os.environ.get) would make "0" truthy.
        for v in ("0", "false", "no", "off", ""):
            os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = v
            self.assertFalse(surface_parity_enabled(), v)
```

- [ ] **Step 2: RED** → ImportError.
- [ ] **Step 3: Implement** — `core/cognition/parity_flag.py`:

```python
"""Strict flag for Surface Parity Restoration v0.

Strict on purpose: "0"/"false"/"off"/"" are OFF. The house-wide
bool(os.environ.get(...)) footgun (where "0" reads truthy) is a logged
HAZARD; this parser is the precedent for the hygiene sweep.
"""
from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def surface_parity_enabled() -> bool:
    return (os.environ.get("MAEZ_SURFACE_PARITY_ENABLED", "") or "").strip().lower() in _TRUTHY
```

- [ ] **Step 4: GREEN.** **Step 5: Commit** (`feat(parity): strict-parsed surface-parity flag`).

---

### Task 2: R4 — the loudness guard (zero behavior; lands early to be witnessed)

**Files:** Modify `skills/telegram_voice.py`; create `tests/test_telegram_voice_loudness.py`.

- [ ] **Step 1: Failing tests** — `tests/test_telegram_voice_loudness.py`:

```python
from __future__ import annotations

import unittest
from pathlib import Path

_SRC = Path("skills/telegram_voice.py").read_text()


class LoudnessGuardTests(unittest.TestCase):
    def test_module_docstring_names_outbound_only_and_the_map(self):
        head = _SRC[:1200]
        self.assertIn("OUTBOUND-ONLY", head)
        self.assertIn("2026-04-20", head)
        self.assertIn("maez_adapter.py", head)

    def test_handle_message_has_once_per_process_warning(self):
        self.assertIn("_INBOUND_WARNED", _SRC)
        self.assertIn("outbound-only", _SRC.lower())
```

- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement** — prepend to the `telegram_voice.py` module docstring (keep existing content below it):

```python
"""OUTBOUND-ONLY since 2026-04-20 (Surface V2 migration).

The inbound methods in this module (_handle_message, _process_message, the
_try_*_intent interceptors) DO NOT FIRE on live owner messages — inbound
Telegram routes through skills/surface/maez_adapter.py. Wire NEW inbound
features into maez_adapter, NOT here. See docs/SURFACE_PARITY_MAP_2026-06-12.md
and docs/MAEZ_BUILD_LEDGER.md. (Three organs were already orphaned here.)
"""
```

and at the top of `_handle_message`'s body (find it: `grep -n "async def _handle_message" skills/telegram_voice.py`), with a module-level `_INBOUND_WARNED = False` near the top:

```python
        global _INBOUND_WARNED
        if not _INBOUND_WARNED:
            _INBOUND_WARNED = True
            logger.warning(
                "telegram_voice._handle_message invoked — this surface is "
                "outbound-only since 2026-04-20; live inbound is maez_adapter. "
                "Is this a test or the Surface V2 kill-switch path?"
            )
```

- [ ] **Step 4: GREEN.** **Step 5: Commit** (`feat(parity): telegram_voice outbound-only loudness guard` — note in body: zero behavior change, prevents the next orphan).

---

### Task 3: R3 — D20 gap detection on Surface V2 (after auth, before interceptors)

**Files:** Modify `skills/surface/maez_adapter.py` (the 0a seam); create `tests/test_surface_parity_d20.py`.

- [ ] **Step 1: Failing tests** — `tests/test_surface_parity_d20.py` (reuse `tests/test_surface_adapter.py` fixtures for `_FakeDaemon`/`MessageEvent` — import or mirror them):

```python
from __future__ import annotations

import asyncio
import os
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path("skills/surface/maez_adapter.py").read_text()


class D20PlacementTests(unittest.TestCase):
    def test_d20_call_is_after_auth_before_card_handling(self):
        # Source-order law: the gap-detector fires before the early-return
        # interceptors, exactly as legacy did (or it re-orphans card turns).
        auth = _SRC.index("guard_owner_text")
        d20 = _SRC.index("maybe_fire_capability_proposal")
        cards = _SRC.index("get_open_for_channel")
        self.assertLess(auth, d20)
        self.assertLess(d20, cards)


class D20BehaviorTests(unittest.TestCase):
    def setUp(self):
        os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None))

    def test_fires_with_pending_card_store_fire_and_forget(self):
        # Build the handler with a fake daemon whose pipe exposes card_store;
        # patch maybe_fire_capability_proposal and assert it is called with
        # pending_card_store=<the live store>, and that an exception inside it
        # does NOT break the reply. (Construct via tests/test_surface_adapter
        # fixtures; assert mock.call_args.kwargs["pending_card_store"] is the
        # store object, and the handler still returns the normal reply when
        # the detector raises.)
        ...

    def test_flag_off_no_d20_call(self):
        os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None)
        # same fixture; assert maybe_fire_capability_proposal NOT called.
        ...
```

(Complete the two `...` bodies using `test_surface_adapter.py`'s handler
construction verbatim — the fixture shape is there; do not weaken the
assertions. The placement test is complete as-is.)

- [ ] **Step 2: RED** (placement test fails; behavior tests fail).
- [ ] **Step 3: Implement** — in `MaezMessageHandler.__call__`, AFTER the `guard_owner_text` result is handled and BEFORE the open-cards block (0a-recorded line), insert:

```python
        # R3 (Surface Parity Restoration v0): D20 capability-gap detection.
        # Placement law: after auth, BEFORE every early-return interceptor —
        # legacy fired here, and a post-card hook would re-orphan card turns.
        # Fire-and-forget; the helper creates cards via pending_card_store and
        # never raises; the existing card pipeline owns visibility. NO manual
        # card send.
        if surface_parity_enabled():
            try:
                from core.infra.capability_gap_detector import maybe_fire_capability_proposal

                _pipe = get_pipeline()
                maybe_fire_capability_proposal(
                    text,
                    pending_card_store=getattr(_pipe, "card_store", None) if _pipe else None,
                    chat_id=chat_id,
                    user_id=user_id,
                )
            except Exception:
                logger.debug("d20 gap detection skipped", exc_info=True)
```

(Use the real local names from 0a: `text`, the chat/user identifiers the
handler already has, and the `get_pipeline()`/`pipe` access pattern at :352.
Import `surface_parity_enabled` from `core.cognition.parity_flag` at module
top. If `get_pipeline()` is already called once below, hoist or reuse — do
not double-call without need.)

- [ ] **Step 4: GREEN.** **Step 5: Commit (behavior)** — `## Predicted effect`: with the flag on, authorized turns run the gap detector before interceptors; it may create a pending capability-proposal card via the existing pipeline; never blocks/changes the reply. Flag off: no call.

---

### Task 4: R2 + R2b — felt-time attachment + the card stops lying

**Files:** Modify `skills/surface/maez_adapter.py` (:627 call); modify `core/cognition/capability_card.py`; tests in `tests/test_surface_parity_felttime.py` + `tests/test_capability_card.py`.

- [ ] **Step 1: Failing tests** — `tests/test_surface_parity_felttime.py`:

```python
class FeltTimeAuthTests(unittest.TestCase):
    def test_flag_on_passes_subjective_duration_auth(self):
        os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None))
        # fake daemon records handle_message kwargs; assert
        # kwargs["subjective_duration_owner_auth"] is not None and is a
        # SubjectiveDurationOwnerAuth (fixture from test_surface_adapter).
        ...

    def test_flag_off_auth_absent(self):
        os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None)
        # assert kwargs.get("subjective_duration_owner_auth") is None.
        ...
```

and append to `tests/test_capability_card.py` (R2b — the EXACT nit phrasing):

```python
class FeltTimeProbeTests(_Env):
    def test_flag_off_returns_exact_legacy_string(self):
        # off-means-off: the felt-time entry is the EXACT pre-arc string.
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"   # card itself on
        os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None)    # parity off
        card = cc.capability_prompt_block()
        self.assertIn("felt time: built, not yet attached", card)

    def test_flag_on_reports_attached(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None))
        card = cc.capability_prompt_block()
        self.assertIn("felt time: attached", card)
        self.assertNotIn("not yet attached", card)

    def test_no_unconditional_static_entry_remains(self):
        # The nit: no UNCONDITIONAL static string. The old string is returned
        # ONLY by the flag-off branch (proven above), the live state by
        # flag-on. So the source must not contain a bare static tuple entry
        # for felt time — it must be a probe.
        import inspect
        src = inspect.getsource(cc)
        self.assertNotIn('("felt time", lambda: "built, not yet attached")', src)
```

- [ ] **Step 2: RED.**
- [ ] **Step 3a: R2b probe** — in `core/cognition/capability_card.py`, replace the static felt-time registry entry with a probe:

```python
def _felt_time_probe() -> str:
    try:
        from core.cognition.parity_flag import surface_parity_enabled

        return "attached" if surface_parity_enabled() else "built, not yet attached"
    except Exception:
        return "unknown (probe error)"
```

and in `_default_registry()` change the felt-time line to `("felt time", _felt_time_probe)`.

- [ ] **Step 3b: R2 auth** — in `maez_adapter.py` at the `daemon.handle_message(...)` call (:627), build and pass the auth, mirroring `telegram_voice.py:2958-2966` (0c-recorded shape):

```python
        _sd_auth = None
        if surface_parity_enabled():
            try:
                from core.evolution.subjective_duration import SubjectiveDurationOwnerAuth

                _sd_auth = SubjectiveDurationOwnerAuth(
                    # mirror the legacy fields recorded in 0c exactly
                    ...
                )
            except Exception:
                logger.debug("subjective duration auth construction failed", exc_info=True)
```

and add `subjective_duration_owner_auth=_sd_auth,` to the `daemon.handle_message(...)` kwargs. **Fill the constructor fields from 0c** (do not guess — the recorded `telegram_voice:2958-2966` shape is authoritative; if a field needs the authorized chat identity, the handler already has it).

- [ ] **Step 4: GREEN.** **Step 5: Commit (behavior)** — `## Predicted effect`: with the flag on, Surface V2 turns carry the felt-time auth so the daemon computes the felt-time line and records owner-contact; the capability card reports `felt time: attached`. Flag off: no auth param, card shows the exact `built, not yet attached` string (byte-identical).

---

### Task 5: R1 — proposal approvals on Surface V2 (the consent channel)

**Files:** per the 0b decision — `core/dispatcher/proposal_resolver.py` (create) + `telegram_voice.py` (delegate) + `maez_adapter.py` (call), OR `maez_adapter.py` + parity tests. Tests: `tests/test_proposal_resolver.py` and/or `tests/test_surface_parity_proposals.py`.

**This task's exact code depends on the 0b read** (the legacy bodies are
entangled with `TelegramVoice` instance state — `_detect_proposal_intent`,
`_list_pending_candidates`, `_last_shown_proposal`). Therefore:

- [ ] **Step 1: Apply the 0b decision.**
  - **PROOF PATH:** create `core/dispatcher/proposal_resolver.py` with pure
    `detect_proposal_intent(text)` and `resolve_target(...)` lifted from the
    legacy bodies (no `self` deps — pass `pending`, `last_shown` in);
    refactor `telegram_voice`'s `_try_proposal_intent`/`_try_dream_proposal_intent`
    to call them (legacy tests must stay green — that proves the extraction
    is faithful); then call the resolver from the adapter.
  - **FALLBACK:** implement the matcher in the adapter + the structural
    parity tests enumerated in 0b.

- [ ] **Step 2: Failing tests** — the resolver's pure-function tests (proof
  path) cover: bare "yes" with no explicit context ⇒ no bind (the
  lighting-hijack guard, telegram_voice:2336-comment); `#N` ⇒ that target;
  "show #N" then "yes" ⇒ last-shown bind; reject; dream-vs-evolution
  routing; no pending ⇒ None (fall-through). The adapter integration test:
  flag-on + a pending proposal + "approve #N" ⇒ the SAME engine call legacy
  makes (fake engine records); card-precedence (a pending CARD beats a
  proposal phrase — assert the open-cards block still wins); flag-off ⇒ no
  proposal interception. (Write each body fully from the 0b read; no `...`
  left in the committed plan-derived tests.)

- [ ] **Step 3: Implement** — the resolver + the adapter interceptor method
  (mirror `_try_search_commitment_intent`'s structure), wired AFTER the
  open-cards block (0a) and BEFORE `_try_search_commitment_intent`,
  flag-gated, fall-through on no-match, replies through the adapter send path
  with audit. Reuse the evolution/dream engine calls — DO NOT fork them.

- [ ] **Step 4: GREEN** — including the legacy proposal tests (proof path)
  unchanged. **Step 5: Commit (behavior)** — `## Predicted effect`: with the
  flag on, an authorized "yes"/"approve #N"/"reject #N"/"show #N" against a
  pending evolution or dream proposal is handled on Surface V2 (executes the
  same engine action as legacy), restoring voice-approval of Maez's
  self-modification; cards still take precedence; bare "yes" with no context
  falls through to chat; flag off: no interception.

---

### Task 6: Verification floor + STOP-at-gate handoff (UPDATES THE LEDGER)

**Files:** Create `docs/handoffs/2026-06-12-surface-parity-gate.md`; modify `docs/MAEZ_BUILD_LEDGER.md`.

- [ ] **Step 1: Focused suite** —

```bash
.venv/bin/python -B -m unittest \
  tests.test_parity_flag tests.test_telegram_voice_loudness \
  tests.test_surface_parity_d20 tests.test_surface_parity_felttime \
  tests.test_capability_card tests.test_proposal_resolver \
  tests.test_surface_parity_proposals tests.test_surface_adapter \
  tests.test_evidence_state -v 2>&1 | tail -5
```
(Drop the resolver/parity test module that the 0b decision didn't create.)
Expected: ALL PASS.

- [ ] **Step 2: ruff** on every touched file → clean.

- [ ] **Step 3: UPDATE THE LEDGER** — in `docs/MAEZ_BUILD_LEDGER.md`, move the three O-rows from `BUILT_ORPHANED` to `BUILT_ASLEEP` (built + wired, awaiting the owner's flag+restart+witness), update their `live seam` to the new adapter functions, `last_verified_commit` to this branch tip, `last_verified_at`, `updated_by=codex`; update the felt-time-attachment PLANNED_PLAN row and the telegram_voice-trap HAZARD row (now guarded). This is the maintenance law's first execution.

- [ ] **Step 4: Write the handoff** — `docs/handoffs/2026-06-12-surface-parity-gate.md`: Task-0 proofs (esp. the 0b RESOLVER DECISION + the R1 parity choice + justification); review anchors (off-means-off byte-identity matrix incl. the felt-time card exact string; R3 source-order; R3 no-manual-card-send / uses pending_card_store; R1 engine-reuse-not-fork + card-precedence + bare-yes-fall-through; ledger rows updated); verification outputs; owner witness = the spec's 3 probes (voice-approve a proposal; "can you feel time?" → LIVE organ + DB row; a crafted capability-gap turn, absence reported honestly) + flag-off spot-check.

- [ ] **Step 5: Commit + STOP** (`docs(parity): STOP-at-gate handoff + ledger update`). Report branch tip + the 0b decision + verification. Claude reviews, then the owner breathes.

---

## Self-Review

1. **Spec coverage:** Build Ledger + maintenance law → Task 0-LEDGER + Task 6 Step 3; strict flag/no-footgun → Task 1; R4 loudness → Task 2; R3 placement+contract → Task 3; R2+R2b off-means-off → Task 4; R1 resolver+precedence+anti-drift → Task 5; witnesses → Task 6. ✓
2. **Placeholders:** the `...` bodies are all explicit "complete from the 0a/0b/0c fixture" instructions with the exact source to copy and the assertion stated — required because the adapter fixtures + legacy bodies are authoritative and must be read, not guessed (the parent prompt authorized this for adapter/engine internals). The R2b nit is baked verbatim into `FeltTimeProbeTests`. No "TBD"/"handle edge cases".
3. **Type consistency:** `surface_parity_enabled()` (Tasks 1,3,4,5 — one home); `maybe_fire_capability_proposal(text, *, pending_card_store=, chat_id=, user_id=)` (Task 3, contract verified); `SubjectiveDurationOwnerAuth(...)` (Task 4, fields from 0c); the felt-time probe replaces the registry tuple (Task 4 ↔ capability_card). ✓
```
