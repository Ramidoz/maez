# Daemon Reply-Mode Resolver — Slice 1 (behavior-preserving extraction) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Checkbox steps.
>
> From spec `docs/superpowers/specs/2026-05-30-daemon-reply-mode-resolver-design.md` (Rohit-amended). **Slice 1 only.** Branch off `main` (HEAD `c7a0b14`, post-v2). Slice 2 (B4/B5 precedence flip) is a separate later plan.

**Goal:** Extract `MaezDaemon.handle_message`'s reply decision into one pure `resolve_reply_mode(signals) -> ReplyDecision` + a `match` dispatcher, with **byte-identical** behavior to today — including the B4 bug (honest-empty before focused). No behavior change; the win is that precedence is now declared in one place.

**Architecture:** New pure module `core/routing/reply_mode.py` (enum + signals + decision + resolver). `handle_message` computes signals in **two phases** (pre-tail → resolve → if `skip_tail` return; else tail signals → dispatch), moving each current branch's execution verbatim into a `match` arm. Behavior-preservation is proven two ways: a resolver **oracle truth-table** (resolver == a reference replica of today's `if/elif`/early-returns over an exhaustive signal matrix) and **integration golden tests** (each mode's reply + side-effects unchanged; clinical/camera call none of trace/web/audit/memory/ledger/LLM).

**Tech Stack:** Python 3, `unittest` (pytest NOT installed → `.venv/bin/python -m unittest`), `unittest.mock`, `ruff`.

**HARD CONSTRAINTS:** byte-identical routing + reply + side-effects (B4 bug preserved); `skip_tail` modes (CLINICAL/CAMERA) must still bypass trace/web/audit/memory/ledger/LLM — proven by spies, not just text equality; `DATED_HONESTY`/`BACKEND_ERROR` are execution outcomes, not initial resolver winners; no new flag; no new prompt logs for skip_tail turns.

---

## File map
- **Create** `core/routing/reply_mode.py` — `ReplyMode`, `ReplyDecisionSignals`, `ReplyDecision`, `resolve_reply_mode`.
- **Create** `tests/test_reply_mode.py` — oracle truth-table.
- **Modify** `daemon/maez_daemon.py` — phased signal collection + `match` dispatch in `handle_message` (verbatim execution moves).
- **Modify** the daemon `handle_message` test module (`tests/test_memory_integrity_invariant.py` or a new `tests/test_reply_mode_dispatch.py`) — integration golden tests incl. skip_tail spies.

---

## Task 1: Pure resolver module (encodes TODAY's order, incl. the B4 bug)

**Files:** Create `core/routing/reply_mode.py`; Create `tests/test_reply_mode.py`.

- [ ] **Step 1: Write the failing oracle truth-table test**

`tests/test_reply_mode.py`:
```python
import itertools
import unittest


def _today_oracle(s) -> str:
    """Reference replica of handle_message's CURRENT decision (early returns +
    if/elif chain), in true precedence order. Slice 1's resolver must match this
    for every signal combination. (Encodes the B4 bug deliberately.)"""
    if s.clinical_matched:
        return "CLINICAL"
    if s.camera_answer is not None:
        return "CAMERA"
    if s.authoritative_tool_reply:
        return "TOOL"
    if s.echo_reply:
        return "ECHO"
    if s.honest_empty_candidate:        # today: honest_empty BEFORE focused (B4 bug)
        return "HONEST_EMPTY"
    if s.focused_candidate:
        return "FOCUSED"
    return "LEGACY"


class ResolveReplyModeOracleTests(unittest.TestCase):
    def test_matches_today_for_full_signal_matrix(self):
        from core.routing.reply_mode import ReplyDecisionSignals, resolve_reply_mode
        bool_fields = [
            "clinical_matched", "authoritative_tool_reply", "echo_reply",
            "honest_empty_candidate", "focused_candidate",
        ]
        for combo in itertools.product([False, True], repeat=len(bool_fields)):
            for camera in (None, "the camera is on"):
                kw = dict(zip(bool_fields, combo))
                kw["camera_answer"] = camera
                s = ReplyDecisionSignals(**kw)
                with self.subTest(**kw):
                    self.assertEqual(resolve_reply_mode(s).mode.value, _today_oracle(s))

    def test_skip_tail_only_for_clinical_and_camera(self):
        from core.routing.reply_mode import (
            ReplyDecisionSignals, ReplyMode, resolve_reply_mode,
        )
        for kw, expect_skip in [
            (dict(clinical_matched=True), True),
            (dict(camera_answer="on"), True),
            (dict(authoritative_tool_reply=True), False),
            (dict(echo_reply=True), False),
            (dict(honest_empty_candidate=True), False),
            (dict(focused_candidate=True), False),
            (dict(), False),  # LEGACY
        ]:
            d = resolve_reply_mode(ReplyDecisionSignals(**kw))
            with self.subTest(**kw):
                self.assertEqual(d.skip_tail, expect_skip)
                if expect_skip:
                    self.assertEqual(d.skip_reason, "deterministic_policy_reply")
                    self.assertIn(d.mode, (ReplyMode.CLINICAL, ReplyMode.CAMERA))

    def test_call_purpose_matches_today_labels(self):
        from core.routing.reply_mode import ReplyDecisionSignals, resolve_reply_mode
        # today's _legacy_call_purpose ladder: echo_reply / honest_empty / legacy_candidate(focused) / llm_synthesis
        self.assertEqual(resolve_reply_mode(ReplyDecisionSignals(echo_reply=True)).call_purpose, "echo_reply")
        self.assertEqual(resolve_reply_mode(ReplyDecisionSignals(honest_empty_candidate=True)).call_purpose, "honest_empty")
        self.assertEqual(resolve_reply_mode(ReplyDecisionSignals(focused_candidate=True)).call_purpose, "legacy_candidate")
        self.assertEqual(resolve_reply_mode(ReplyDecisionSignals()).call_purpose, "llm_synthesis")
```

- [ ] **Step 2: Run → FAIL** (`No module named 'core.routing.reply_mode'`).

- [ ] **Step 3: Implement `core/routing/reply_mode.py`**

```python
"""Single declared-precedence resolver for MaezDaemon.handle_message reply modes.

Slice 1 is behavior-preserving: resolve_reply_mode encodes TODAY's actual
precedence (early returns + if/elif chain), including the known B4 ordering bug
(HONEST_EMPTY before FOCUSED). Slice 2 flips exactly two lines to fix B4/B5.

DATED_HONESTY and BACKEND_ERROR are EXECUTION OUTCOMES of FOCUSED / LEGACY, not
initial resolver winners — they are not returned by resolve_reply_mode.
"""
from dataclasses import dataclass
from enum import Enum


class ReplyMode(Enum):
    CLINICAL = "CLINICAL"
    CAMERA = "CAMERA"
    TOOL = "TOOL"
    ECHO = "ECHO"
    HONEST_EMPTY = "HONEST_EMPTY"
    FOCUSED = "FOCUSED"
    LEGACY = "LEGACY"
    # execution outcomes (not initial resolver results):
    DATED_HONESTY = "DATED_HONESTY"
    BACKEND_ERROR = "BACKEND_ERROR"


@dataclass(frozen=True)
class ReplyDecisionSignals:
    # pre-tail (skip_tail-eligible) signals:
    clinical_matched: bool = False
    camera_answer: "str | None" = None
    # tail signals (precomputed flags mirroring today's candidate booleans):
    authoritative_tool_reply: bool = False
    echo_reply: bool = False
    honest_empty_candidate: bool = False   # == today's _honest_empty_candidate (B4 bug preserved)
    focused_candidate: bool = False        # == today's _focused_candidate


@dataclass(frozen=True)
class ReplyDecision:
    mode: ReplyMode
    call_purpose: str
    skip_tail: bool = False
    skip_reason: "str | None" = None


_CALL_PURPOSE = {
    ReplyMode.CLINICAL: "clinical_boundary",
    ReplyMode.CAMERA: "camera_direct",
    ReplyMode.TOOL: "authoritative_tool",
    ReplyMode.ECHO: "echo_reply",
    ReplyMode.HONEST_EMPTY: "honest_empty",
    ReplyMode.FOCUSED: "legacy_candidate",   # matches today's _legacy_call_purpose for focused
    ReplyMode.LEGACY: "llm_synthesis",
}


def resolve_reply_mode(s: ReplyDecisionSignals) -> ReplyDecision:
    """TODAY's precedence (byte-identical). Order is the contract; Slice 2 edits it."""
    if s.clinical_matched:
        return ReplyDecision(ReplyMode.CLINICAL, _CALL_PURPOSE[ReplyMode.CLINICAL],
                             skip_tail=True, skip_reason="deterministic_policy_reply")
    if s.camera_answer is not None:
        return ReplyDecision(ReplyMode.CAMERA, _CALL_PURPOSE[ReplyMode.CAMERA],
                             skip_tail=True, skip_reason="deterministic_policy_reply")
    if s.authoritative_tool_reply:
        return ReplyDecision(ReplyMode.TOOL, _CALL_PURPOSE[ReplyMode.TOOL])
    if s.echo_reply:
        return ReplyDecision(ReplyMode.ECHO, _CALL_PURPOSE[ReplyMode.ECHO])
    if s.honest_empty_candidate:                 # B4 bug: before FOCUSED. Slice 2 flips this.
        return ReplyDecision(ReplyMode.HONEST_EMPTY, _CALL_PURPOSE[ReplyMode.HONEST_EMPTY])
    if s.focused_candidate:
        return ReplyDecision(ReplyMode.FOCUSED, _CALL_PURPOSE[ReplyMode.FOCUSED])
    return ReplyDecision(ReplyMode.LEGACY, _CALL_PURPOSE[ReplyMode.LEGACY])
```
(Note: the `_CALL_PURPOSE` values must equal today's `_legacy_call_purpose` ladder where it exists — echo_reply / honest_empty / legacy_candidate(focused) / llm_synthesis. CLINICAL/CAMERA/TOOL had no `_legacy_call_purpose` entry today; their labels are new structural metadata used by NO logging in Slice 1, per the spec.)

- [ ] **Step 4: Run → PASS** (`.venv/bin/python -m unittest tests.test_reply_mode -v`).
- [ ] **Step 5: Commit** `feat(daemon): pure reply-mode resolver encoding current precedence (Slice 1 scaffolding)`

---

## Task 2: Phased signal collection + `match` dispatch in `handle_message`

**Files:** Modify `daemon/maez_daemon.py`. Test: integration golden tests (extend `tests/test_memory_integrity_invariant.py` or new `tests/test_reply_mode_dispatch.py`).

- [ ] **Step 1: Write the failing integration golden tests**

Using the existing `handle_message` test harness in `tests/test_memory_integrity_invariant.py` (the `_build_daemon_for_handle_message` fixture + `MaezDaemon.handle_message(...)` calls). Add a class that pins behavior preservation per mode AND the skip_tail bypass via spies:
```python
class ReplyModeDispatchGoldenTests(unittest.TestCase):
    # (reuse the module's daemon fixture + mocking style)

    def test_clinical_skips_entire_tail(self):
        # craft a clinical-boundary owner text; spy on the tail seams and assert NONE fire.
        daemon = self._build_daemon_for_handle_message()
        with (
            mock.patch.object(daemon, "store_telegram") as store,
            mock.patch("daemon.maez_daemon.audit_assistant_text") as audit,
            # trace / web-search / ledger / llm_client.chat spies per the module's seams:
            mock.patch("core.llm_client.chat") as llm,
        ):
            reply = MaezDaemon.handle_message(daemon, "<clinical-trigger text>", source="telegram_surface")
            self.assertTrue(reply)                 # deterministic clinical answer returned
            store.assert_not_called()
            audit.assert_not_called()
            llm.assert_not_called()

    def test_camera_skips_entire_tail(self): ...   # same shape, camera-presence question

    def test_echo_focused_honest_empty_legacy_unchanged(self):
        # for each non-skip mode, assert the reply equals the pre-refactor reply
        # for a representative input (golden strings captured from main@c7a0b14).
        ...
```
**Executor:** capture the golden reply strings + the set of tail seams that fire for each mode by running the representative inputs on `main@c7a0b14` BEFORE refactoring (record them in the test). The clinical/camera spies are the load-bearing assertions (spec amendment 1).

- [ ] **Step 2: Run → FAIL** (the resolver isn't wired; or the spies show the refactor not yet applied — write tests first, they fail/error until Step 3).

- [ ] **Step 3: Rewire `handle_message` — phased, verbatim execution moves.**

In `daemon/maez_daemon.py::handle_message`:
1. **Pre-tail phase** (at the current clinical/camera early-return site ~3248–3265): compute `clinical_matched`/`clinical_answer` and `camera_answer` as today; build a partial `ReplyDecisionSignals(clinical_matched=..., camera_answer=...)`; call `resolve_reply_mode`. If `decision.skip_tail`: set `reply = clinical_answer or camera_answer` (the existing deterministic value), run the existing `_mark_m1_s4_policy`/crisis-write side effects that are part of those branches today, and `return reply` — **before** trace start, web search, evidence assembly, audit, memory, ledger, LLM. (This reproduces today's two early returns, now routed through the resolver.)
2. **Tail phase** (only reached when no skip_tail): compute the remaining signals at their CURRENT safe points (don't move web/evidence/echo/date/focused/tool computation earlier — preserve side-effect ordering). After they're all computed, build the full `ReplyDecisionSignals(authoritative_tool_reply=bool(authoritative_tool_reply), echo_reply=bool(_current_turn_echo_reply), honest_empty_candidate=_honest_empty_candidate, focused_candidate=_focused_candidate)` and call `resolve_reply_mode` again (cheap, pure).
3. Replace the `if authoritative_tool_reply: ... elif ... else:` chain (~3899–4044) with a `match decision.mode:` whose arms contain the **verbatim** current branch bodies (TOOL→`reply = authoritative_tool_reply`; ECHO→`reply = _current_turn_echo_reply`; HONEST_EMPTY→the build_honest_empty block incl. its `record_focused_cognition_run`; FOCUSED→the focused block incl. its execution fallback to DATED_HONESTY/LEGACY and all telemetry; LEGACY→the megaprompt block incl. BACKEND_ERROR except-handler). Keep `_focused_used`/`reply is None` exactly as today inside the FOCUSED/LEGACY arms (Slice 1 does not refactor the execution-fallback internals — only the top-level branch selection).
4. Use `decision.call_purpose` wherever `_legacy_call_purpose` is used today (single source); delete the `_legacy_call_purpose` string ladder.
5. Leave the post-`reply` tail (leak-strip, pursuit, audit, fragment-guard, memory, ledger, trace) **untouched**.

- [ ] **Step 4: Run → PASS** (the golden + skip-tail-spy tests).
- [ ] **Step 5: Commit** `refactor(daemon): route handle_message replies through resolve_reply_mode (phased, byte-identical)`

---

## Task 3: Regression + lint

- [ ] **Step 1:** `.venv/bin/python -m unittest tests.test_reply_mode tests.test_memory_integrity_invariant tests.test_focused_cognition tests.test_living_recall tests.test_routing_observation tests.test_trace_emission -v` → OK (the daemon/handle_message/focused/trace suites unchanged).
- [ ] **Step 2:** `.venv/bin/ruff check core/routing/reply_mode.py daemon/maez_daemon.py tests/test_reply_mode.py` → clean.
- [ ] **Step 3:** Broad floor: confirm only the 3 documented pre-existing failures. Report honestly.
- [ ] **Step 4: Commit** `test(daemon): reply-mode resolver Slice 1 regression`

---

## Witness (Claude, after green): full switchboard on the diff
This is a high-blast-radius daemon refactor, so the full Claude 6-role switchboard fires on the Slice-1 diff — Logical especially verifies byte-identical routing (oracle + golden), and the Adversary verifies the skip_tail bypass is exactly preserved (no tail seam newly fires for clinical/camera, none newly skipped for the others). No live witness needed for Slice 1 (behavior-preserving; the golden tests + suites are the proof). Live witness happens after **Slice 2** (the behavior change).

## Self-Review
**Spec coverage:** pure resolver + signals + ReplyDecision + skip_tail/skip_reason (Task 1) = spec §1,2,3,5 ✓; phased collection w/ skip_tail-before-tail-signals + clinical/camera-skip-all-seams golden (Task 2) = spec amendment 1 ✓; DATED_HONESTY/BACKEND_ERROR as execution outcomes not resolver winners (Task 1 enum comment + Task 2 step 3 keeps fallback internal) = spec amendment 2 ✓; byte-identical incl B4 bug + oracle truth-table (Task 1) = spec staged-Slice-1 ✓; call_purpose single source (Task 2 step 4) = spec §2 ✓.
**Placeholder scan:** Task 1 is full code + tests. Task 2's verbatim-move bodies reference the exact current line ranges from the dispatch map (3248–3265 early returns; 3899–4044 chain) rather than re-pasting ~200 daemon lines — the move is "relocate these exact blocks into match arms unchanged," and the golden+spy tests are the precise behavior contract. The golden reply strings + tail-seam spy targets are captured from `main@c7a0b14` before refactor (named in Step 1), not invented.
**Type consistency:** `ReplyDecisionSignals` bool fields + `camera_answer: str|None`; `ReplyDecision{mode,call_purpose,skip_tail,skip_reason}`; `ReplyMode` enum values; `resolve_reply_mode(signals)->ReplyDecision`; oracle field names == signal field names; `_CALL_PURPOSE` values == today's labels.
