# Recall-Stack Bundle Resolver + Carrier-Consulted Denial Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three scattered raw recall flags with one bundle flag `MAEZ_RECALL_TRIAD_ENABLED` resolved to a single `RecallMode`, and make the deterministic dated-denial tell the truth about whether the recall carrier was actually consulted on this turn.

**Architecture:** A new pure resolver `core/routing/recall_stack_config.py` returns a frozen `RecallStackConfig(mode, reason)` from `env`. All five raw flag-read sites migrate to it. The dated-denial block in the daemon gains a turn-local `_recall_carrier_consulted` fact and a three-way branch. The raw three flags become inert (bundle is the only behavior input) but emit a loud WARN if set. A CI guard test forbids raw flag reads outside the resolver.

**Tech Stack:** Python 3, stdlib `enum`/`dataclasses`, `unittest` (run via `.venv/bin/python -m unittest` — pytest is NOT installed). Flags via launch-env only; `config/.env` is not touched by this slice (the monitored flip is a separate, owner-authorized step).

**Spec:** [docs/superpowers/specs/2026-05-30-recall-stack-bundle-resolver-design.md](../specs/2026-05-30-recall-stack-bundle-resolver-design.md)

**Discipline reminders for the implementer:**
- TDD: write the failing test, see it fail, implement minimally, see it pass, commit.
- Do NOT touch `config/.env` or any config file. Flags are set via launch-env in tests/witness only.
- Genderless self-reference in all user-facing reply strings (it/Maez; never she/he).
- "Static trace is not integration witness" — the live witness is a separate post-merge step, not part of this plan.

## Codex Six-Agent Engineering-Pass Amendments (folded before code)

The pre-code Codex pass (Dewey, Feynman, Locke, Descartes, Ohm, Goodall) accepted
the one-bundle resolver shape and required these amendments:

1. **Selected is not consulted.** `_recall_carrier_consulted` must not be assigned
   from `ReplyMode.FOCUSED`. Focused mode is only a selected route. Set
   consultation true only after `assemble_working_set(...)` returns a non-`None`
   working set/status for the dated turn. If assembly raises, use path-unavailable
   wording, never absence wording.
2. **Use a receipt.** Track `_recall_carrier_receipt` as `not_consulted`,
   `consulted`, or `consult_failed`; log it in the dated-denial branch.
3. **Resolve once per daemon/brain turn.** Helpers may default to resolving for
   tests, but `handle_message` and `run_brain_loop` capture one config for their
   turn and pass it into local decisions.
4. **Telemetry tests use the actual daemon logger (`maez`).**
5. **Env tests are hermetic.** Every new test clears/sets all four recall flags.
6. **Migration search includes `tests/` as well as `docs/` and `scripts/`.**

The full engineering-pass memo is
`docs/slices/recall-axis-dispatcher/witness/recall-stack-bundle-resolver-codex-engineering-pass-2026-05-30.md`.

---

## File Structure

- **Create** `core/routing/recall_stack_config.py` — `RecallMode` enum, `RecallStackConfig` frozen dataclass, exported flag-name constants, `resolve_recall_stack(env)`. One responsibility: turn env into a recall mode + reason.
- **Create** `tests/test_recall_stack_config.py` — truth-table over `(bundle, D, F, L)`.
- **Create** `tests/test_recall_flag_single_source.py` — CI guard: no raw flag reads outside the resolver.
- **Modify** `core/brain/brain_loop.py` — `_dispatcher_enabled` / `_living_recall_enabled` derive from the resolver.
- **Modify** `daemon/maez_daemon.py` — `_focused_cognition_enabled` + `_daemon_parallel_web_search_enabled` derive from the resolver; capture turn-local `_recall_carrier_receipt` / `_recall_carrier_consulted`; three-way denial gate; startup + WARN telemetry; turn-level dated-denial receipt telemetry.
- **Modify** `skills/telegram_voice.py` — `_telegram_pipeline_a_web_search_enabled` derives from the resolver (inverted).
- **Create/extend** `tests/test_recall_carrier_consulted_denial.py` — three-way denial wording incl. the availability-vs-consultation row.
- **Create/extend** `tests/test_recall_web_gate_preservation.py` — web-search gate behavior preserved across migration.

---

## Task 1: The resolver module

**Files:**
- Create: `core/routing/recall_stack_config.py`
- Test: `tests/test_recall_stack_config.py`

- [ ] **Step 1: Write the failing truth-table test**

```python
# tests/test_recall_stack_config.py
import unittest
from core.routing.recall_stack_config import (
    RecallMode,
    resolve_recall_stack,
)


class ResolveRecallStackTest(unittest.TestCase):
    def _resolve(self, **flags):
        # only pass flags that are set; absence == unset
        env = {k: v for k, v in flags.items() if v is not None}
        return resolve_recall_stack(env=env)

    def test_bundle_on_yields_triad_regardless_of_raw(self):
        for raw in ({}, {"MAEZ_DISPATCHER_ENABLED": "1"},
                    {"MAEZ_DISPATCHER_ENABLED": "1",
                     "MAEZ_FOCUSED_COGNITION_ENABLED": "1",
                     "MAEZ_LIVING_RECALL_ENABLED": "1"}):
            cfg = resolve_recall_stack(env={"MAEZ_RECALL_TRIAD_ENABLED": "1", **raw})
            self.assertIs(cfg.mode, RecallMode.TRIAD)
            self.assertEqual(cfg.reason, "bundle_enabled")
            self.assertTrue(cfg.triad_on)
            self.assertTrue(cfg.carrier_available)

    def test_all_off_is_legacy_off(self):
        cfg = resolve_recall_stack(env={})
        self.assertIs(cfg.mode, RecallMode.LEGACY)
        self.assertEqual(cfg.reason, "off")
        self.assertFalse(cfg.triad_on)
        self.assertFalse(cfg.carrier_available)

    def test_raw_flags_without_bundle_are_inert_legacy_with_named_reason(self):
        cases = {
            ("MAEZ_DISPATCHER_ENABLED",):
                "legacy_raw_flags_ignored:MAEZ_DISPATCHER_ENABLED",
            ("MAEZ_FOCUSED_COGNITION_ENABLED",):
                "legacy_raw_flags_ignored:MAEZ_FOCUSED_COGNITION_ENABLED",
            ("MAEZ_LIVING_RECALL_ENABLED",):
                "legacy_raw_flags_ignored:MAEZ_LIVING_RECALL_ENABLED",
            ("MAEZ_DISPATCHER_ENABLED", "MAEZ_FOCUSED_COGNITION_ENABLED"):
                "legacy_raw_flags_ignored:MAEZ_DISPATCHER_ENABLED,"
                "MAEZ_FOCUSED_COGNITION_ENABLED",
            ("MAEZ_DISPATCHER_ENABLED", "MAEZ_LIVING_RECALL_ENABLED"):
                "legacy_raw_flags_ignored:MAEZ_DISPATCHER_ENABLED,"
                "MAEZ_LIVING_RECALL_ENABLED",
            ("MAEZ_FOCUSED_COGNITION_ENABLED", "MAEZ_LIVING_RECALL_ENABLED"):
                "legacy_raw_flags_ignored:MAEZ_FOCUSED_COGNITION_ENABLED,"
                "MAEZ_LIVING_RECALL_ENABLED",
            ("MAEZ_DISPATCHER_ENABLED", "MAEZ_FOCUSED_COGNITION_ENABLED",
             "MAEZ_LIVING_RECALL_ENABLED"):
                "legacy_raw_flags_ignored:MAEZ_DISPATCHER_ENABLED,"
                "MAEZ_FOCUSED_COGNITION_ENABLED,MAEZ_LIVING_RECALL_ENABLED",
        }
        for names, expected_reason in cases.items():
            env = {n: "1" for n in names}
            cfg = resolve_recall_stack(env=env)
            self.assertIs(cfg.mode, RecallMode.LEGACY)
            self.assertEqual(cfg.reason, expected_reason)
            self.assertFalse(cfg.triad_on)

    def test_truthiness_is_tolerant_for_bundle(self):
        for value in ("1", " 1", "TRUE", "true", "Yes", "  yes "):
            cfg = resolve_recall_stack(env={"MAEZ_RECALL_TRIAD_ENABLED": value})
            self.assertIs(cfg.mode, RecallMode.TRIAD, value)

    def test_falsey_bundle_values_do_not_enable(self):
        for value in ("0", "", "no", "false", "off"):
            cfg = resolve_recall_stack(env={"MAEZ_RECALL_TRIAD_ENABLED": value})
            self.assertIs(cfg.mode, RecallMode.LEGACY, value)

    def test_carrier_available_tracks_triad_on_in_every_branch(self):
        for env in ({}, {"MAEZ_RECALL_TRIAD_ENABLED": "1"},
                    {"MAEZ_DISPATCHER_ENABLED": "1"}):
            cfg = resolve_recall_stack(env=env)
            self.assertEqual(cfg.carrier_available, cfg.triad_on)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_recall_stack_config -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.routing.recall_stack_config'`

- [ ] **Step 3: Write the resolver**

```python
# core/routing/recall_stack_config.py
"""Single source of truth for whether Maez's recall triad is online.

The triad (dispatcher carries structured recall_items, living recall fills,
focused cognition consumes) is one carrier-gated organ. It is brought online by
ONE bundle flag, MAEZ_RECALL_TRIAD_ENABLED, resolved here to a single RecallMode.

The three legacy per-flag env vars (MAEZ_DISPATCHER_ENABLED /
MAEZ_FOCUSED_COGNITION_ENABLED / MAEZ_LIVING_RECALL_ENABLED) are CUT: they no
longer enable anything. If set without the bundle they only produce a loud WARN
reason, so a stale/partial raw config is visible and never honored as a partial
behavior path. This makes the dangerous partial config unrepresentable rather
than runtime-rejected.

Sibling resolvers (same shape): core/information_limb/calendar_v1_config.py
(resolve_calendar_mode), core/body/camera_presence_state.py
(resolve_camera_presence_state).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional

BUNDLE_FLAG = "MAEZ_RECALL_TRIAD_ENABLED"
RAW_RECALL_FLAG_NAMES = (
    "MAEZ_DISPATCHER_ENABLED",
    "MAEZ_FOCUSED_COGNITION_ENABLED",
    "MAEZ_LIVING_RECALL_ENABLED",
)
_TRUTHY = {"1", "true", "yes"}


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in _TRUTHY


class RecallMode(Enum):
    LEGACY = "legacy"
    TRIAD = "recall_triad"


@dataclass(frozen=True)
class RecallStackConfig:
    mode: RecallMode
    reason: str  # "bundle_enabled" | "off" | "legacy_raw_flags_ignored:<names>"

    @property
    def triad_on(self) -> bool:
        return self.mode is RecallMode.TRIAD

    @property
    def carrier_available(self) -> bool:
        """The recall carrier is *available* iff the triad is on.

        NOTE: availability is not consultation. A turn may have the carrier
        available yet never consult it (e.g. voice paths bypass focused recall).
        Callers that need 'was the carrier actually used this turn' must compute
        a turn-local execution fact, not read this property.
        """
        return self.triad_on


def resolve_recall_stack(
    env: Optional[Mapping[str, str]] = None,
) -> RecallStackConfig:
    """Resolve the recall-stack mode from the environment.

    Pure function of ``env`` (defaults to ``os.environ``). Not memoized: call it
    per-turn so live/test env mutation and the kill switch take effect.
    """
    env = os.environ if env is None else env
    if _truthy(env.get(BUNDLE_FLAG)):
        return RecallStackConfig(RecallMode.TRIAD, "bundle_enabled")
    raw_set = [name for name in RAW_RECALL_FLAG_NAMES if _truthy(env.get(name))]
    if raw_set:
        return RecallStackConfig(
            RecallMode.LEGACY,
            "legacy_raw_flags_ignored:" + ",".join(raw_set),
        )
    return RecallStackConfig(RecallMode.LEGACY, "off")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_recall_stack_config -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add core/routing/recall_stack_config.py tests/test_recall_stack_config.py
git commit -m "feat(recall): bundle resolver — one RecallMode from MAEZ_RECALL_TRIAD_ENABLED, raw flags cut"
```

---

## Task 2: Migrate brain_loop flag reads

**Files:**
- Modify: `core/brain/brain_loop.py:153-160`
- Test: reuse existing brain_loop / dispatcher / living-recall suites (no behavior change for the bundle-on and all-off cases)

- [ ] **Step 1: Write a failing test pinning brain_loop to the resolver**

Create `tests/test_recall_flag_brain_loop_migration.py`:

```python
import importlib
import unittest


class BrainLoopMigrationTest(unittest.TestCase):
    def setUp(self):
        import core.brain.brain_loop as bl
        self.bl = importlib.reload(bl)

    def _set(self, monkey, **env):
        for k in ("MAEZ_RECALL_TRIAD_ENABLED", "MAEZ_DISPATCHER_ENABLED",
                  "MAEZ_FOCUSED_COGNITION_ENABLED", "MAEZ_LIVING_RECALL_ENABLED"):
            monkey.pop(k, None)
        monkey.update(env)

    def test_bundle_on_enables_dispatcher_and_living(self):
        import os
        self._set(os.environ, MAEZ_RECALL_TRIAD_ENABLED="1")
        try:
            self.assertTrue(self.bl._dispatcher_enabled())
            self.assertTrue(self.bl._living_recall_enabled())
        finally:
            os.environ.pop("MAEZ_RECALL_TRIAD_ENABLED", None)

    def test_raw_dispatcher_flag_alone_is_now_inert(self):
        import os
        self._set(os.environ, MAEZ_DISPATCHER_ENABLED="1")
        try:
            self.assertFalse(self.bl._dispatcher_enabled())   # raw flag cut
            self.assertFalse(self.bl._living_recall_enabled())
        finally:
            os.environ.pop("MAEZ_DISPATCHER_ENABLED", None)

    def test_all_off(self):
        import os
        self._set(os.environ)
        self.assertFalse(self.bl._dispatcher_enabled())
        self.assertFalse(self.bl._living_recall_enabled())
```

- [ ] **Step 2: Run to verify the inert-raw test fails**

Run: `.venv/bin/python -m unittest tests.test_recall_flag_brain_loop_migration -v`
Expected: `test_raw_dispatcher_flag_alone_is_now_inert` FAILS (today raw `MAEZ_DISPATCHER_ENABLED=1` still returns True).

- [ ] **Step 3: Migrate the two functions**

Replace `core/brain/brain_loop.py:153-160`:

```python
def _dispatcher_enabled() -> bool:
    from core.routing.recall_stack_config import resolve_recall_stack

    return resolve_recall_stack().triad_on


def _living_recall_enabled() -> bool:
    from core.routing.recall_stack_config import resolve_recall_stack

    return resolve_recall_stack().triad_on
```

(Local import avoids any import-order surprises; the resolver has no heavy deps so a module-level import is also acceptable — match the file's existing convention.)

- [ ] **Step 4: Run to verify migration tests pass + no regression**

Run: `.venv/bin/python -m unittest tests.test_recall_flag_brain_loop_migration tests.test_living_recall tests.test_dispatcher_composition_spec -v`
Expected: PASS. (Existing suites that set raw flags will now see them inert — if any existing test sets only a raw flag and expects dispatcher ON, it must be updated to set `MAEZ_RECALL_TRIAD_ENABLED=1`; do that in Step 5 of the relevant task / Task 8.)

- [ ] **Step 5: Commit**

```bash
git add core/brain/brain_loop.py tests/test_recall_flag_brain_loop_migration.py
git commit -m "refactor(recall): brain_loop dispatcher/living reads derive from bundle resolver"
```

---

## Task 3: Migrate daemon flag reads (focused + web-search gate, with preservation tests)

**Files:**
- Modify: `daemon/maez_daemon.py:981-994`
- Test: `tests/test_recall_web_gate_preservation.py`

- [ ] **Step 1: Write the failing web-gate preservation test**

```python
# tests/test_recall_web_gate_preservation.py
import os
import unittest

import daemon.maez_daemon as md


class DaemonWebGatePreservationTest(unittest.TestCase):
    def tearDown(self):
        for k in ("MAEZ_RECALL_TRIAD_ENABLED", "MAEZ_DISPATCHER_ENABLED"):
            os.environ.pop(k, None)

    def test_triad_on_with_nonempty_transcript_suppresses_legacy_web(self):
        os.environ["MAEZ_RECALL_TRIAD_ENABLED"] = "1"
        self.assertFalse(md._daemon_parallel_web_search_enabled("some transcript"))

    def test_triad_on_with_empty_transcript_keeps_fallback(self):
        os.environ["MAEZ_RECALL_TRIAD_ENABLED"] = "1"
        self.assertTrue(md._daemon_parallel_web_search_enabled(""))
        self.assertTrue(md._daemon_parallel_web_search_enabled("   "))

    def test_triad_off_keeps_legacy_web(self):
        self.assertTrue(md._daemon_parallel_web_search_enabled("some transcript"))

    def test_focused_enabled_tracks_bundle(self):
        self.assertFalse(md._focused_cognition_enabled())
        os.environ["MAEZ_RECALL_TRIAD_ENABLED"] = "1"
        self.assertTrue(md._focused_cognition_enabled())

    def test_raw_focused_flag_alone_is_inert(self):
        os.environ.pop("MAEZ_RECALL_TRIAD_ENABLED", None)
        os.environ["MAEZ_FOCUSED_COGNITION_ENABLED"] = "1"
        try:
            self.assertFalse(md._focused_cognition_enabled())
        finally:
            os.environ.pop("MAEZ_FOCUSED_COGNITION_ENABLED", None)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_recall_web_gate_preservation -v`
Expected: `test_triad_on_*`, `test_focused_enabled_tracks_bundle`, `test_raw_focused_flag_alone_is_inert` FAIL (today these read raw `MAEZ_DISPATCHER_ENABLED`/`MAEZ_FOCUSED_COGNITION_ENABLED`).

- [ ] **Step 3: Migrate the two daemon helpers**

Replace `daemon/maez_daemon.py:981-994`:

```python
def _daemon_parallel_web_search_enabled(transcript: str = "") -> bool:
    """Return whether daemon synthesis may run its legacy web-search side path.

    Preserves the historical nuance: the legacy web side-path is suppressed only
    when the recall carrier is active AND it actually handed over a non-empty
    transcript. An empty transcript means the fancy path had nothing to give, so
    the older emergency web fallback may still run.
    """
    from core.routing.recall_stack_config import resolve_recall_stack

    return not (
        resolve_recall_stack().triad_on and bool((transcript or "").strip())
    )


def _focused_cognition_enabled() -> bool:
    from core.routing.recall_stack_config import resolve_recall_stack

    return resolve_recall_stack().triad_on
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_recall_web_gate_preservation -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_recall_web_gate_preservation.py
git commit -m "refactor(recall): daemon focused + web-gate reads derive from bundle resolver (empty-transcript fallback preserved)"
```

---

## Task 4: Migrate telegram_voice flag read

**Files:**
- Modify: `skills/telegram_voice.py:67-68`
- Test: add to `tests/test_recall_web_gate_preservation.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_recall_web_gate_preservation.py`:

```python
class TelegramVoiceGateTest(unittest.TestCase):
    def tearDown(self):
        for k in ("MAEZ_RECALL_TRIAD_ENABLED", "MAEZ_DISPATCHER_ENABLED"):
            os.environ.pop(k, None)

    def test_pipeline_a_web_search_disabled_when_triad_on(self):
        import skills.telegram_voice as tv
        os.environ["MAEZ_RECALL_TRIAD_ENABLED"] = "1"
        self.assertFalse(tv._telegram_pipeline_a_web_search_enabled())

    def test_pipeline_a_web_search_enabled_when_triad_off(self):
        import skills.telegram_voice as tv
        os.environ.pop("MAEZ_RECALL_TRIAD_ENABLED", None)
        self.assertTrue(tv._telegram_pipeline_a_web_search_enabled())

    def test_raw_dispatcher_flag_alone_does_not_disable_pipeline_a_web(self):
        import skills.telegram_voice as tv
        os.environ.pop("MAEZ_RECALL_TRIAD_ENABLED", None)
        os.environ["MAEZ_DISPATCHER_ENABLED"] = "1"
        try:
            # raw flag is cut; pipeline-A web stays enabled (triad not actually on)
            self.assertTrue(tv._telegram_pipeline_a_web_search_enabled())
        finally:
            os.environ.pop("MAEZ_DISPATCHER_ENABLED", None)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_recall_web_gate_preservation.TelegramVoiceGateTest -v`
Expected: `test_raw_dispatcher_flag_alone_does_not_disable_pipeline_a_web` FAILS (today raw `MAEZ_DISPATCHER_ENABLED=1` flips the inverted gate to disabled).

- [ ] **Step 3: Migrate the function**

Replace `skills/telegram_voice.py:67-68`:

```python
def _telegram_pipeline_a_web_search_enabled() -> bool:
    from core.routing.recall_stack_config import resolve_recall_stack

    return not resolve_recall_stack().triad_on
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_recall_web_gate_preservation -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/telegram_voice.py tests/test_recall_web_gate_preservation.py
git commit -m "refactor(recall): telegram_voice pipeline-A web gate derives from bundle resolver"
```

---

## Task 5: Carrier-consulted three-way denial gate

**Files:**
- Modify: `daemon/maez_daemon.py` — compute `_recall_carrier_consulted` near the reply-mode resolution (~3891-3899) and rewrite the denial block at `daemon/maez_daemon.py:4054-4073`.
- Test: `tests/test_recall_carrier_consulted_denial.py`

- [ ] **Step 1: Write the failing denial-wording test**

This test exercises the three-way branch directly via a small extracted helper so it does not require booting the full daemon. Add the helper in Step 3.

```python
# tests/test_recall_carrier_consulted_denial.py
import unittest

from daemon.maez_daemon import _dated_denial_reply


class DatedDenialReplyTest(unittest.TestCase):
    def test_carrier_not_consulted_says_path_unavailable(self):
        reply = _dated_denial_reply(carrier_consulted=False, had_confirmed=False)
        self.assertIn("can't check my dated recall from this path", reply.lower())
        self.assertNotIn("don't have a dated memory", reply.lower())

    def test_carrier_not_consulted_even_if_some_confirmed_flag_says_path(self):
        # availability/consultation dominates: if we did not consult, we cannot
        # claim presence or absence of a dated memory.
        reply = _dated_denial_reply(carrier_consulted=False, had_confirmed=True)
        self.assertIn("can't check my dated recall from this path", reply.lower())

    def test_consulted_with_confirmed_item_but_synthesis_failed(self):
        reply = _dated_denial_reply(carrier_consulted=True, had_confirmed=True)
        self.assertIn("couldn't pull it together", reply.lower())

    def test_consulted_no_match_says_no_dated_memory(self):
        reply = _dated_denial_reply(carrier_consulted=True, had_confirmed=False)
        self.assertIn("don't have a dated memory for that window", reply.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_recall_carrier_consulted_denial -v`
Expected: FAIL with `ImportError: cannot import name '_dated_denial_reply'`.

- [ ] **Step 3: Extract the helper and rewrite the denial block**

Add a module-level helper to `daemon/maez_daemon.py` (near the other small helpers, e.g. after `_focused_cognition_enabled`):

```python
def _dated_denial_reply(*, carrier_consulted: bool, had_confirmed: bool) -> str:
    """Honest dated-memory reply when no focused dated answer was produced.

    Carrier-consulted gate: absence language ("I don't have a dated memory") is
    permitted ONLY when the dated recall carrier was actually consulted this
    turn. If it was not (legacy / a path that bypasses focused recall), say the
    path was unavailable — never that the memory does not exist.
    """
    if not carrier_consulted:
        return (
            "I can't check my dated recall from this path right now — that "
            "capability isn't active here. I won't answer it from recent chat "
            "or guesswork."
        )
    if had_confirmed:
        return (
            "I have a dated memory for that, but I couldn't pull it together "
            "just now. Ask me again in a moment."
        )
    return (
        "I don't have a dated memory for that window. I'm not going to answer "
        "it from recent chat or guesswork."
    )
```

Then, where the reply mode is resolved (after line 3899, `_reply_decision = resolve_reply_mode(...)`), add the turn-local consultation fact:

```python
        _recall_carrier_consulted = _reply_decision.mode is ReplyMode.FOCUSED
```

Finally, replace the denial block at `daemon/maez_daemon.py:4054-4073` with:

```python
            if _date_addressed_turn and not _focused_used and reply is None:
                _had_confirmed = bool(
                    _focused_working_set is not None
                    and any(
                        getattr(item, "temporal_provenance", None)
                        and item.temporal_provenance.get("confirmed")
                        for item in _focused_working_set.items
                    )
                )
                reply = _dated_denial_reply(
                    carrier_consulted=_recall_carrier_consulted,
                    had_confirmed=_had_confirmed,
                )
                _focused_used = True
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_recall_carrier_consulted_denial -v`
Expected: PASS.

- [ ] **Step 5: Add an integration-shaped test for the voice availability-vs-consultation row**

Append to `tests/test_recall_carrier_consulted_denial.py` a test that constructs `ReplyDecisionSignals` with `focused_candidate=False` (as a `source="voice"` turn would, even with the triad on) and asserts `resolve_reply_mode(...).mode` is not `FOCUSED`, so `_recall_carrier_consulted` would be False:

```python
from core.routing.reply_mode import (
    ReplyDecisionSignals,
    ReplyMode,
    resolve_reply_mode,
)


class AvailabilityNotConsultationTest(unittest.TestCase):
    def test_dated_turn_without_focused_candidate_is_not_focused_mode(self):
        # triad available but this path (e.g. voice) excluded focused recall
        decision = resolve_reply_mode(
            ReplyDecisionSignals(
                authoritative_tool_reply=False,
                echo_reply=False,
                honest_empty_candidate=False,
                focused_candidate=False,
                date_addressed=True,
            )
        )
        self.assertIsNot(decision.mode, ReplyMode.FOCUSED)
        # => _recall_carrier_consulted would be False => path-unavailable wording
```

- [ ] **Step 6: Run + Commit**

Run: `.venv/bin/python -m unittest tests.test_recall_carrier_consulted_denial -v`
Expected: PASS.

```bash
git add daemon/maez_daemon.py tests/test_recall_carrier_consulted_denial.py
git commit -m "feat(recall): carrier-consulted dated-denial gate — absence language only when carrier consulted this turn"
```

---

## Task 6: Telemetry — startup line + WARN on ignored raw flags

**Files:**
- Modify: `daemon/maez_daemon.py` — emit a startup log line; WARN when `reason` starts with `legacy_raw_flags_ignored:`.
- Test: `tests/test_recall_stack_telemetry.py`

- [ ] **Step 1: Write the failing telemetry test**

```python
# tests/test_recall_stack_telemetry.py
import logging
import unittest

from daemon.maez_daemon import log_recall_stack_posture


class RecallStackTelemetryTest(unittest.TestCase):
    def test_startup_line_shows_all_inputs_including_unset(self):
        env = {"MAEZ_DISPATCHER_ENABLED": "1"}  # bundle + focused + living unset
        with self.assertLogs("daemon.maez_daemon", level="INFO") as cap:
            log_recall_stack_posture(env=env)
        joined = "\n".join(cap.output)
        self.assertIn("recall_stack", joined)
        self.assertIn("mode=legacy", joined)
        self.assertIn("bundle=unset", joined)
        self.assertIn("dispatcher=set", joined)
        self.assertIn("focused=unset", joined)
        self.assertIn("living=unset", joined)

    def test_ignored_raw_flags_warn(self):
        env = {"MAEZ_DISPATCHER_ENABLED": "1"}
        with self.assertLogs("daemon.maez_daemon", level="WARNING") as cap:
            log_recall_stack_posture(env=env)
        self.assertTrue(
            any("legacy_raw_flags_ignored" in line for line in cap.output)
        )

    def test_bundle_on_no_warn(self):
        env = {"MAEZ_RECALL_TRIAD_ENABLED": "1"}
        with self.assertLogs("daemon.maez_daemon", level="INFO") as cap:
            log_recall_stack_posture(env=env)
        self.assertFalse(
            any(rec.levelno >= logging.WARNING for rec in cap.records)
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_recall_stack_telemetry -v`
Expected: FAIL with `ImportError: cannot import name 'log_recall_stack_posture'`.

- [ ] **Step 3: Implement the telemetry helper and call it at daemon startup**

Add to `daemon/maez_daemon.py` (near the other module-level helpers):

```python
def log_recall_stack_posture(env=None) -> None:
    """Emit the recall-stack posture once (startup / witness). Fowler 'expose
    toggle state' + OpenFeature 'evaluation carries a reason'."""
    import os as _os

    from core.routing.recall_stack_config import (
        BUNDLE_FLAG,
        RAW_RECALL_FLAG_NAMES,
        resolve_recall_stack,
    )

    env = _os.environ if env is None else env
    cfg = resolve_recall_stack(env=env)

    def _state(name: str) -> str:
        return "set" if (env.get(name) or "").strip() else "unset"

    logger.info(
        "recall_stack mode=%s reason=%s raw_flags=[bundle=%s dispatcher=%s "
        "focused=%s living=%s]",
        cfg.mode.value,
        cfg.reason,
        _state(BUNDLE_FLAG),
        _state(RAW_RECALL_FLAG_NAMES[0]),
        _state(RAW_RECALL_FLAG_NAMES[1]),
        _state(RAW_RECALL_FLAG_NAMES[2]),
    )
    if cfg.reason.startswith("legacy_raw_flags_ignored:"):
        logger.warning(
            "recall_stack %s — deprecated raw recall flags are set but ignored; "
            "use %s",
            cfg.reason,
            BUNDLE_FLAG,
        )
```

Do not spell the three raw flag-name strings in `daemon/maez_daemon.py`; import
`RAW_RECALL_FLAG_NAMES` from the resolver. Task 7's guard intentionally permits
those strings only in `core/routing/recall_stack_config.py`.

Call `log_recall_stack_posture()` once during daemon startup (alongside the other startup/posture logging — find the existing startup banner/log and add the call there). If a clear single startup site is not obvious, call it at the top of the daemon's main entrypoint after `logger` is configured.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_recall_stack_telemetry -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_recall_stack_telemetry.py
git commit -m "feat(recall): startup posture log + WARN on ignored raw recall flags"
```

---

## Task 7: Single-source migration guard test

**Files:**
- Create: `tests/test_recall_flag_single_source.py`

- [ ] **Step 1: Write the guard test**

```python
# tests/test_recall_flag_single_source.py
"""No production module may read the raw recall flag names directly.

The bundle resolver (core/routing/recall_stack_config.py) is the single source
of truth. This guard fails if any other production file under core/, daemon/, or
skills/ references a raw flag name — preventing future re-fragmentation of the
recall organ back into scattered toggles.
"""
import os
import re
import unittest

_RAW_FLAGS = (
    "MAEZ_DISPATCHER_ENABLED",
    "MAEZ_FOCUSED_COGNITION_ENABLED",
    "MAEZ_LIVING_RECALL_ENABLED",
)
_ALLOWED = {
    os.path.join("core", "routing", "recall_stack_config.py"),
}
_ROOTS = ("core", "daemon", "skills")
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RecallFlagSingleSourceTest(unittest.TestCase):
    def test_no_raw_flag_reads_outside_resolver(self):
        pattern = re.compile("|".join(re.escape(f) for f in _RAW_FLAGS))
        offenders = []
        for root in _ROOTS:
            base = os.path.join(_REPO, root)
            for dirpath, _dirs, files in os.walk(base):
                for fname in files:
                    if not fname.endswith(".py"):
                        continue
                    abspath = os.path.join(dirpath, fname)
                    rel = os.path.relpath(abspath, _REPO)
                    if rel in _ALLOWED:
                        continue
                    with open(abspath, encoding="utf-8") as fh:
                        if pattern.search(fh.read()):
                            offenders.append(rel)
        self.assertEqual(
            offenders, [],
            "raw recall flag names found outside the resolver: %s" % offenders,
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the guard**

Run: `.venv/bin/python -m unittest tests.test_recall_flag_single_source -v`
Expected: PASS (Tasks 2-4 removed every raw read; if it FAILS, the offenders list names the file still reading a raw flag — migrate it).

- [ ] **Step 3: Commit**

```bash
git add tests/test_recall_flag_single_source.py
git commit -m "test(recall): guard — raw recall flag names only in the resolver"
```

---

## Task 8: Update launch-env / witness invocations + full regression

**Files:**
- Modify: any witness/launch docs or scripts that export the three raw flags (search them out).
- No `config/.env` change (the monitored flip is a separate owner-authorized step).

- [ ] **Step 1: Find raw-flag launch-env invocations**

Run: `grep -rn "MAEZ_DISPATCHER_ENABLED\|MAEZ_FOCUSED_COGNITION_ENABLED\|MAEZ_LIVING_RECALL_ENABLED" docs/ scripts/ 2>/dev/null | grep -v "\.pyc"`
Expected: a list of witness docs / helper scripts that set the raw three.

- [ ] **Step 2: Update each to the single bundle flag**

For each launch/witness invocation that sets the raw three to turn the triad on, replace with `MAEZ_RECALL_TRIAD_ENABLED=1`. Leave historical witness *records* (past observations) unchanged — only update *invocation* instructions/scripts meant to be re-run. Note in the doc that the raw flags are deprecated and inert.

- [ ] **Step 3: Run any existing tests that set raw flags expecting triad-on**

Run: `.venv/bin/python -m unittest discover -s tests -p "test_*recall*.py" -v` and `.venv/bin/python -m unittest discover -s tests -p "test_*dispatcher*.py" -v` and `.venv/bin/python -m unittest discover -s tests -p "test_*focused*.py" -v`
Expected: PASS. Any test that previously set only a raw flag to enable the triad must be updated to set `MAEZ_RECALL_TRIAD_ENABLED=1`. Update those tests in place (they are exercising the capability, and the capability's switch changed).

- [ ] **Step 4: Full suite regression**

Run: `.venv/bin/python -m unittest discover -s tests -v 2>&1 | tail -40`
Expected: all green (same pass count as before the slice, plus the new tests). Investigate any new failure — a real behavior change must be intentional and covered by an updated test.

- [ ] **Step 5: Commit**

```bash
git status --short
# Stage only files intentionally changed by this slice. Do NOT use `git add -A`;
# Rohit's repo commonly has unrelated dirty/untracked files.
git add <each updated launch/witness/test file>
git commit -m "chore(recall): migrate launch-env/witness invocations to MAEZ_RECALL_TRIAD_ENABLED; raw flags deprecated"
```

---

## Self-Review

**1. Spec coverage:**
- Resolver + `RecallMode` + reasons → Task 1. ✓
- Cut raw flags / unrepresentable partial → Task 1 (resolver) + Tasks 2-4 (sites inert) + Task 7 (guard). ✓
- Five-site migration incl. the two web gates + inverted telegram → Tasks 2, 3, 4. ✓
- Web-gate empty-transcript preservation → Task 3 tests. ✓
- Carrier-consulted three-way denial + availability≠consultation → Task 5. ✓
- Telemetry startup line + WARN → Task 6. ✓
- Canonical truthiness → Task 1 (`_truthy`) + tests. ✓
- Migration guard → Task 7. ✓
- Launch-env/witness migration + regression → Task 8. ✓
- Kill switch (`MAEZ_RECALL_TRIAD_ENABLED=0`/unset) → falls out of resolver; covered by Task 1 falsey/all-off tests. ✓

**2. Placeholder scan:** No TBD/TODO. Every code step shows the actual code. The only "search it out" step (Task 8 Step 1) is a concrete grep command with expected output.

**3. Type/symbol consistency:** `RecallMode`, `RecallStackConfig`, `resolve_recall_stack`, `triad_on`, `carrier_available`, `_dated_denial_reply`, `log_recall_stack_posture`, `_recall_carrier_consulted`, `ReplyMode.FOCUSED`, `ReplyDecisionSignals` — used identically across tasks and match the spec and the existing code (`ReplyMode.FOCUSED` confirmed in `core/routing/reply_mode.py`; `_focused_working_set`, `_had_confirmed`, `_date_addressed_turn`, `_focused_used` confirmed in `daemon/maez_daemon.py`).

**4. Ordering:** resolver first (Task 1), then site migrations (2-4), then the denial gate that depends on the resolved mode (5), telemetry (6), guard after all migrations (7), launch-env + full regression last (8). Each task is independently committable and leaves the suite green.
