# Evidence-Precedence / Capability-Health v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Live-true outranks recalled-stale — a probed capability card on every turn (kills the stale-self-model wounds), the precedence rule inside the existing evidence directive, and a shadow detector for absence-claims-about-fresh-evidence — all behind `MAEZ_EVIDENCE_PRECEDENCE_ENABLED`, default-OFF.

**Architecture:** Three thin seams on existing organs: a new `capability_card` module appended into the ambient system message via a combined-block seam (escaping both silent-vanish gates verified at `daemon:5762-5775`); two precedence lines appended inside `evidence_state.build_evidence_precedence_directive`; a new structural detector observing the marked audited draft beside `retain_receipt`, before `render_natural`, writing a content-light shadow ledger. No memory is deleted or deweighted anywhere.

**Tech Stack:** Python stdlib; existing organs (`SearxngBackend.health()`, `sense_flag`, `evidence_state`, the daemon drain, the house shadow-ledger shape); unittest + ruff.

**Spec:** `docs/superpowers/specs/2026-06-12-evidence-precedence-capability-health-design.md` (@fc4b066). Read it once — the domain-scoped law and the covenant line govern every choice below.

---

## Ground Rules

- Branch `evidence-precedence-v0` off main (@fc4b066). main local-only — NO push.
- STOP at the gate: no merge, restart, flag flips, or service changes.
- ONE flag: `MAEZ_EVIDENCE_PRECEDENCE_ENABLED`. Unset ⇒ byte-identical on all three seams (no card, directive string-identical, no detector, no ledger). `MAEZ_EVIDENCE_PRECEDENCE_DEBUG` additionally gates ledger snippets.
- `## Predicted effect` on the behavior commits (Tasks 2, 3, 4, 5).
- Co-author trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- **Covenant invariant (reviewable):** the diff contains NO deletion, deweighting, or mutation of any memory row anywhere. Outranking is by composition only.
- Tests: fakes only; runner `/home/rohit/maez/.venv/bin/python -B -m unittest`; never full-discover.

## File Map

| Path | Responsibility |
|---|---|
| `core/cognition/capability_card.py` (create) | Flag helper + probe registry + `capability_prompt_block()` (own 30s cache). |
| `daemon/maez_daemon.py` (modify ×2) | The combined-block seam (:5762-5775 region); the detector call in the drain (~:6785). |
| `core/routing/evidence_state.py` (modify) | The two precedence lines inside the existing directive builder. |
| `core/cognition/evidence_precedence_shadow.py` (create) | The absence-claim detector + content-light ledger. |
| `core/routing/attribution_render.py` (modify, ONLY on the 0b proof path) | `fresh_indices` in the stash. |
| `tests/test_capability_card.py` (create) | Card/probe/cache/flag tests. |
| `tests/test_evidence_state.py` (modify or create) | Directive string-identity + extension. |
| `tests/test_evidence_precedence_shadow.py` (create) | Detector + ledger + branched index tests. |
| `tests/test_daemon_prompt_seams.py` (create) | Combined-block matrix + drain source-order. |
| `docs/handoffs/2026-06-12-evidence-precedence-gate.md` (create) | STOP-at-gate handoff w/ the 0b DECISION. |

---

### Task 0: Prove the seams (NO feature code until proven)

- [ ] **Step 0a: the ambient seam**

```bash
cd /home/rohit/maez && sed -n '5760,5780p' daemon/maez_daemon.py
```
Expected: `_ambient_block = ""`, the `MAEZ_AMBIENT_BRIEF != "0"` gate, the
`if _ambient_block:` conditional append, `system_part_capture.append(("ambient_block", ...))`.
Record exact worktree lines — both silent-vanish paths the combined block must escape.

- [ ] **Step 0b: THE FRESH-INDEX PROOF (the spec's load-bearing open question)**

```bash
grep -n "class EvidenceState" -A6 core/routing/evidence_state.py
grep -n "source_hint\|marker_labels" core/routing/evidence_state.py | head -8
grep -n "_CITE_RE\|origin_trust\|fresh" core/routing/focused_cognition.py | head -12
grep -n "E{\|\[E\" core/routing/focused_cognition.py | head -6
```
Question to answer: where are `[E#]` numbers assigned to evidence items, and
are fresh-wing items distinguishable from recall items at that point?
`EvidenceState.source_hint: tuple[str, ...]` (:34) is the first suspect — if
hints name the source kind per marker, the fresh index set is derivable
right there. **RECORD THE DECISION in the handoff:**
- **Proof path:** fresh indices are derivable → extend `stash_turn_evidence`
  with `fresh_indices: tuple[int, ...]` (and thread them from the
  authoritative assignment point).
- **Fallback path:** not cleanly derivable → `fresh_index_mode=
  "fallback_all_cited"` on `web_present` turns, bias stamped in every row.
Tests in Task 4 BRANCH on this decision (the spec's branched language).

- [ ] **Step 0c: the drain placement**

```bash
grep -n "retain_receipt\|render_natural\|pop_turn_evidence" daemon/maez_daemon.py | head -6
```
Expected: the drain block (~:6785): pop → observation write → `retain_receipt`
→ `render_natural`. The detector call lands BESIDE `retain_receipt` (after
it, before `render_natural`) — record exact lines.

- [ ] **Step 0d: the directive builder**

```bash
sed -n '89,120p' core/routing/evidence_state.py
```
Expected: the builder ends with the "You may NOT claim the relevant source is
blocked..." line and `return "\n".join(lines)`. The extension appends two
lines before the return, flag-gated. Record the exact current final lines
(the string-identity test pins them).

- [ ] **Step 0e:** `git checkout -b evidence-precedence-v0`

---

### Task 1: The capability card module (flag + registry + builder)

**Files:** Create `core/cognition/capability_card.py`; create `tests/test_capability_card.py`.

- [ ] **Step 1: Failing tests** — create `tests/test_capability_card.py`:

```python
from __future__ import annotations

import os
import unittest

from core.cognition import capability_card as cc


class _Env(unittest.TestCase):
    def setUp(self):
        for k in ("MAEZ_EVIDENCE_PRECEDENCE_ENABLED",):
            os.environ.pop(k, None)
            self.addCleanup(lambda k=k: os.environ.pop(k, None))
        cc.reset_card_cache()
        self.addCleanup(cc.reset_card_cache)


class FlagTests(_Env):
    def test_default_off_returns_empty(self):
        self.assertEqual(cc.capability_prompt_block(), "")

    def test_flag_helper(self):
        self.assertFalse(cc.evidence_precedence_enabled())
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        self.assertTrue(cc.evidence_precedence_enabled())


class CardTests(_Env):
    def setUp(self):
        super().setUp()
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"

    def test_renders_all_registry_entries_and_precedence_lines(self):
        card = cc.capability_prompt_block(registry=(
            ("web sense", lambda: "searxng healthy"),
            ("felt time", lambda: "built, not yet attached"),
        ))
        self.assertIn("YOUR LIVE BODY (live/cached substrate probe):", card)
        self.assertIn("web sense: searxng healthy", card)
        self.assertIn("felt time: built, not yet attached", card)
        self.assertIn("outranks any MEMORY of your former", card)
        self.assertNotIn("just now", card)  # the cache-honesty law

    def test_probe_failure_is_unknown_never_absent(self):
        def _boom():
            raise RuntimeError("probe died")

        card = cc.capability_prompt_block(registry=(
            ("web sense", _boom),
            ("recall", lambda: "on"),
        ))
        self.assertIn("web sense: unknown (probe error)", card)
        self.assertIn("recall: on", card)

    def test_cache_ttl_30s(self):
        calls = {"n": 0}

        def _probe():
            calls["n"] += 1
            return "on"

        reg = (("recall", _probe),)
        cc.capability_prompt_block(registry=reg)
        cc.capability_prompt_block(registry=reg)
        self.assertEqual(calls["n"], 1)  # second call served from cache
        cc.reset_card_cache()
        cc.capability_prompt_block(registry=reg)
        self.assertEqual(calls["n"], 2)

    def test_default_registry_uses_singleton_backend(self):
        # The default registry must reuse ONE SearxngBackend (per-turn
        # instantiation would defeat its 30s health cache).
        class _Counting:
            instances = 0

            def __init__(self):
                _Counting.instances += 1

            def health(self):
                return "healthy"

        from unittest import mock

        with mock.patch.object(cc, "_BACKEND", None), \
             mock.patch("core.search.searxng_client.SearxngBackend", _Counting):
            cc.reset_card_cache()
            cc.capability_prompt_block()
            cc.reset_card_cache()
            cc.capability_prompt_block()
        self.assertEqual(_Counting.instances, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: RED** — `.venv/bin/python -B -m unittest tests.test_capability_card -v` → ImportError.

- [ ] **Step 3: Implement** — create `core/cognition/capability_card.py`:

```python
"""The capability card — Maez's live self-knowledge, one block per turn.

Spec 2026-06-12 (evidence-precedence v0, Component A). Probes, not prose:
each registry entry reads LIVE substrate state. Probes fail closed to
"unknown (probe error)" and are NEVER absent from the card — a missing
line is silent self-blindness; an unknown line is honest.

Egress posture (named because this rides every turn): the web-sense probe
is SearxngBackend.health(), which sends the fixed string "healthcheck" to
the LOCAL SearXNG instance only, cached 30s, never owner text.

Cache honesty: this module has its OWN 30s cache and the wording says
"live/cached substrate probe" — never "read just now" (the ambient block
this card rides beside is itself cached 60s; see ambient_format.py:20-21).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Callable, Sequence

logger = logging.getLogger("maez")

_CARD_TTL_S = 30.0
_CARD_CACHE: dict = {"text": None, "ts": 0.0}
_BACKEND = None  # module singleton; per-turn instantiation defeats health caching


def evidence_precedence_enabled() -> bool:
    return bool(os.environ.get("MAEZ_EVIDENCE_PRECEDENCE_ENABLED"))


def reset_card_cache() -> None:
    _CARD_CACHE["text"] = None
    _CARD_CACHE["ts"] = 0.0


def _web_sense_probe() -> str:
    global _BACKEND
    if _BACKEND is None:
        from core.search.searxng_client import SearxngBackend

        _BACKEND = SearxngBackend()
    return f"searxng {_BACKEND.health()}"


def _flag_probe(env_name: str, on_text: str = "on", off_text: str = "off") -> Callable[[], str]:
    def _probe() -> str:
        return on_text if os.environ.get(env_name) else off_text

    return _probe


def _default_registry() -> Sequence[tuple[str, Callable[[], str]]]:
    return (
        ("web sense", _web_sense_probe),
        ("page read", _flag_probe("MAEZ_PAGE_READ_ENABLED")),
        ("recall", _flag_probe("MAEZ_RECALL_TRIAD_ENABLED")),
        ("search commitment", _flag_probe("MAEZ_SEARCH_COMMITMENT_ENABLED", "gatekeeper mode", "off")),
        # Static honest entry — the felt-time organ exists and is not wired
        # to the live surface (born orphaned 2026-05-24). DELETE this entry
        # when the felt-time attachment seam-fix lands.
        ("felt time", lambda: "built, not yet attached"),
    )


def capability_prompt_block(registry: Sequence[tuple[str, Callable[[], str]]] | None = None) -> str:
    """The card, or "" when the organ is off. Never raises."""
    if not evidence_precedence_enabled():
        return ""
    now = time.time()
    if registry is None and _CARD_CACHE["text"] is not None and (now - _CARD_CACHE["ts"]) < _CARD_TTL_S:
        return _CARD_CACHE["text"]
    try:
        entries = []
        for name, probe in (registry if registry is not None else _default_registry()):
            try:
                entries.append(f"{name}: {probe()}")
            except Exception:
                entries.append(f"{name}: unknown (probe error)")
        text = (
            "YOUR LIVE BODY (live/cached substrate probe):\n "
            + " | ".join(entries)
            + "\n This is probed substrate state. It outranks any MEMORY of your former\n"
            " body or former tools. If a recalled memory disagrees with this card,\n"
            " the memory describes your past, not your present."
        )
        if registry is None:
            _CARD_CACHE["text"] = text
            _CARD_CACHE["ts"] = now
        return text
    except Exception:
        logger.debug("capability card build failed", exc_info=True)
        return ""
```

- [ ] **Step 4: GREEN** — same command → PASS.
- [ ] **Step 5: Commit**

```bash
git add core/cognition/capability_card.py tests/test_capability_card.py
git commit -m "feat(evidence-precedence): probed capability card module

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: The combined-block seam

**Files:** Modify `daemon/maez_daemon.py` (the 0a lines); create `tests/test_daemon_prompt_seams.py`.

- [ ] **Step 1: Failing tests** — create `tests/test_daemon_prompt_seams.py`
(SOURCE-LEVEL tests; instantiating the daemon is prohibitive — the seam is
pinned structurally, the behavior pinned via the card module tests):

```python
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

_DAEMON_SRC = Path("daemon/maez_daemon.py").read_text()


class CombinedBlockSeamTests(unittest.TestCase):
    def test_capability_block_built_outside_ambient_brief_gate(self):
        # The card must not be hostage to MAEZ_AMBIENT_BRIEF: the capability
        # builder call appears, and appears BEFORE the ambient-brief env
        # check in the same region.
        self.assertIn("capability_prompt_block()", _DAEMON_SRC)
        cap_idx = _DAEMON_SRC.index("capability_prompt_block()")
        gate_idx = _DAEMON_SRC.index('MAEZ_AMBIENT_BRIEF', cap_idx - 4000)
        self.assertLess(cap_idx, gate_idx + 8000)  # same region
        # the combined append:
        self.assertIn("_combined_context_block", _DAEMON_SRC)

    def test_append_condition_is_combined_not_ambient_only(self):
        # The old bug shape: `if _ambient_block:` guarding the append. The
        # new shape must guard on the combined text.
        region = _DAEMON_SRC[_DAEMON_SRC.index("_combined_context_block"):][:1500]
        self.assertIn("if _combined_context_block:", region)


class DrainOrderTests(unittest.TestCase):
    def test_detector_runs_after_retain_before_render(self):
        # Source-order law: observe_marked_draft sits AFTER retain_receipt
        # and BEFORE render_natural in the drain.
        drain = _DAEMON_SRC[_DAEMON_SRC.index("pop_turn_evidence"):]
        retain = drain.index("retain_receipt")
        observe = drain.index("observe_marked_draft")
        render = drain.index("render_natural(")
        self.assertLess(retain, observe)
        self.assertLess(observe, render)


if __name__ == "__main__":
    unittest.main()
```

(The `DrainOrderTests` will stay RED until Task 4 wires the detector — run
only `CombinedBlockSeamTests` for this task's GREEN; the full file goes
green at Task 4. Note this in the commit message.)

- [ ] **Step 2: RED** — `.venv/bin/python -B -m unittest tests.test_daemon_prompt_seams.CombinedBlockSeamTests -v` → FAIL.

- [ ] **Step 3: Implement** — in `daemon/maez_daemon.py`, replace the 0a block (preserving indentation):

```python
        _ambient_block = ""
        _capability_block = ""
        try:
            # Evidence-precedence v0: the capability card is built OUTSIDE
            # the MAEZ_AMBIENT_BRIEF gate and OUTSIDE the ambient-empty
            # check — it must not silently vanish with either (spec
            # must-fix #1). Returns "" when the organ flag is off.
            from core.cognition.capability_card import capability_prompt_block

            _capability_block = capability_prompt_block()
        except Exception as _cap_exc:
            logger.debug("capability card injection failed: %s", _cap_exc)
        if os.environ.get("MAEZ_AMBIENT_BRIEF", "1") != "0":
            try:
                from core.memory.ambient_format import ambient_prompt_block

                _ambient_block = ambient_prompt_block()
            except Exception as _amb_exc:
                logger.debug(
                    "ambient brief injection failed: %s",
                    _amb_exc,
                )
        _combined_context_block = "\n\n".join(
            p for p in (_ambient_block, _capability_block) if p
        )
        if _combined_context_block:
            messages.append(
                {
                    "role": "system",
                    "content": _combined_context_block,
                }
            )
            # Keep the existing telemetry label so prompt-shape diagnostics
            # stay comparable across the flag flip (noted in the handoff).
            system_part_capture.append(("ambient_block", _combined_context_block))
```

(Match the original block's exact indentation and any code between the
recorded 0a lines — only the structure above changes; the surrounding
exception-handling style is preserved.)

- [ ] **Step 4: GREEN** — `.venv/bin/python -B -m unittest tests.test_daemon_prompt_seams.CombinedBlockSeamTests tests.test_capability_card -v` → PASS.
- [ ] **Step 5: Commit (behavior-affecting)**

```bash
git add daemon/maez_daemon.py tests/test_daemon_prompt_seams.py
git commit -m "feat(evidence-precedence): combined ambient+capability block seam

DrainOrderTests in the new test file stays RED until the Task-4 detector
wiring; CombinedBlockSeamTests is green.

## Predicted effect
With MAEZ_EVIDENCE_PRECEDENCE_ENABLED=1, every chat turn's ambient system
message carries the live capability card — including when the ambient
brief is empty or disabled (MAEZ_AMBIENT_BRIEF=0). Flag unset: the message
content is byte-identical to today's ambient_prompt_block() output, and an
empty ambient still appends nothing.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: The directive extension

**Files:** Modify `core/routing/evidence_state.py` (builder at :89); test `tests/test_evidence_state.py` (create if absent — check first, append if it exists).

- [ ] **Step 1: Failing tests** — add to `tests/test_evidence_state.py`:

```python
from __future__ import annotations

import os
import unittest

from core.routing.evidence_state import EvidenceState, build_evidence_precedence_directive


class _Env(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", None))

    def _state(self):
        return EvidenceState(
            evidence_present=True,
            marker_labels=("memory evidence", "fresh evidence"),
            source_hint=("memory", "web"),
            descriptions=("", ""),
        )


class DirectiveExtensionTests(_Env):
    def test_flag_off_directive_string_identical(self):
        base = build_evidence_precedence_directive(self._state())
        self.assertIn("EVIDENCE PRESENT THIS TURN.", base)
        self.assertIn("You may NOT claim the relevant source is blocked", base)
        self.assertNotIn("CONTEXTUALIZE", base)

    def test_flag_on_appends_the_precedence_rule(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        text = build_evidence_precedence_directive(self._state())
        self.assertIn("Recalled memories may CONTEXTUALIZE the fresh evidence", text)
        self.assertIn("re-read the evidence text itself", text)
        # the base directive is untouched above the extension:
        self.assertIn("You may NOT claim the relevant source is blocked", text)

    def test_flag_on_extension_is_appended_last(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"
        text = build_evidence_precedence_directive(self._state())
        self.assertGreater(
            text.index("Recalled memories may CONTEXTUALIZE"),
            text.index("You may NOT claim"),
        )
```

(If `tests/test_evidence_state.py` already exists, match its fixture style;
if `EvidenceState` requires different construction, copy an existing test's
state construction — never weaken the three assertions.)

- [ ] **Step 2: RED** → the extension assertions FAIL.

- [ ] **Step 3: Implement** — in `build_evidence_precedence_directive`, before the `return "\n".join(lines)`:

```python
    from core.cognition.capability_card import evidence_precedence_enabled

    if evidence_precedence_enabled():
        # Evidence-precedence v0 (spec Component B): the precedence rule,
        # domain-scoped — memory contextualizes fresh evidence, never
        # contradicts it. Lived memory is otherwise untouched.
        lines.append(
            "Recalled memories may CONTEXTUALIZE the fresh evidence above; they "
            "may not CONTRADICT it. Your memory of past failures with similar "
            "pages or searches is not evidence about THIS evidence."
        )
        lines.append(
            "Before you claim the evidence lacks or truncates something, re-read "
            "the evidence text itself - the detail you remember missing before "
            "may be present now."
        )
```

- [ ] **Step 4: GREEN** — `.venv/bin/python -B -m unittest tests.test_evidence_state -v` → PASS.
- [ ] **Step 5: Commit (behavior-affecting)**

```bash
git add core/routing/evidence_state.py tests/test_evidence_state.py
git commit -m "feat(evidence-precedence): precedence rule inside the evidence directive

## Predicted effect
With the organ flag on, evidence-present turns instruct that recalled
memory contextualizes but never contradicts fresh evidence, and that
absence claims require re-reading the evidence. Flag off: the directive
is string-identical to today.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: The absence-claim shadow detector

**Files:** Create `core/cognition/evidence_precedence_shadow.py`; modify `daemon/maez_daemon.py` (the drain, 0c lines); modify `core/routing/attribution_render.py` ONLY on the 0b proof path; create `tests/test_evidence_precedence_shadow.py`.

- [ ] **Step 1: Failing tests** — create `tests/test_evidence_precedence_shadow.py`:

```python
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from core.cognition import evidence_precedence_shadow as eps


class _Env(unittest.TestCase):
    def setUp(self):
        for k in ("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", "MAEZ_EVIDENCE_PRECEDENCE_DEBUG"):
            os.environ.pop(k, None)
            self.addCleanup(lambda k=k: os.environ.pop(k, None))
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.ledger = Path(td.name) / "eps.jsonl"

    def _rows(self):
        if not self.ledger.exists():
            return []
        return [json.loads(x) for x in self.ledger.read_text().splitlines()]


class DetectorTests(_Env):
    def setUp(self):
        super().setUp()
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"

    def test_each_absence_verb_flags_with_fresh_citation(self):
        for verb_text in (
            "the tag is truncated in [E1]",
            "the version is missing from [E1]",
            "it was cut off in [E1]",
            "that detail is not in [E1]",
            "the data doesn't contain it [E1]",
            "[E1] lacks the version string",
            "it is absent from [E1]",
        ):
            with self.subTest(verb_text=verb_text):
                n_before = len(self._rows())
                eps.observe_marked_draft(
                    verb_text, surface="telegram_surface",
                    fresh_indices=(1,), web_present=True, ledger_path=self.ledger,
                )
                self.assertEqual(len(self._rows()), n_before + 1)

    def test_no_marker_no_flag(self):
        eps.observe_marked_draft(
            "the version seems to be missing entirely", surface="t",
            fresh_indices=(1,), web_present=True, ledger_path=self.ledger,
        )
        self.assertEqual(self._rows(), [])

    def test_multi_sentence_only_the_absence_sentence_flags(self):
        draft = "The page loaded fine [E1]. The tag is truncated in [E1]. Good day."
        eps.observe_marked_draft(
            draft, surface="t", fresh_indices=(1,), web_present=True,
            ledger_path=self.ledger,
        )
        rows = self._rows()
        self.assertEqual(len(rows), 1)

    def test_row_is_content_light_with_mode(self):
        eps.observe_marked_draft(
            "secret detail is missing from [E2]", surface="t",
            fresh_indices=(2,), web_present=True, ledger_path=self.ledger,
        )
        row = self._rows()[0]
        self.assertIn(row["fresh_index_mode"], ("proof", "fallback_all_cited"))
        self.assertIn("sentence_hash", row)
        self.assertNotIn("secret detail", json.dumps(row))

    def test_debug_adds_snippet(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_DEBUG"] = "1"
        eps.observe_marked_draft(
            "x is missing from [E1]", surface="t",
            fresh_indices=(1,), web_present=True, ledger_path=self.ledger,
        )
        self.assertIn("sentence_excerpt", self._rows()[0])

    def test_flag_off_writes_nothing(self):
        os.environ.pop("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", None)
        eps.observe_marked_draft(
            "x is missing from [E1]", surface="t",
            fresh_indices=(1,), web_present=True, ledger_path=self.ledger,
        )
        self.assertEqual(self._rows(), [])

    def test_never_raises(self):
        eps.observe_marked_draft(None, surface="t", fresh_indices=None,
                                 web_present=True, ledger_path=Path("/nonexistent/x.jsonl"))


# ===== BRANCH on the Task-0b decision — keep EXACTLY ONE of these classes =====

class ProofPathIndexTests(_Env):
    """Keep IF 0b chose the proof path (fresh indices travel)."""

    def setUp(self):
        super().setUp()
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"

    def test_recalled_index_does_not_flag(self):
        eps.observe_marked_draft(
            "we hit this wall before, it was missing [E5]", surface="t",
            fresh_indices=(1, 2), web_present=True, ledger_path=self.ledger,
        )
        self.assertEqual(self._rows(), [])

    def test_fresh_index_flags_with_mode_proof(self):
        eps.observe_marked_draft(
            "the tag is truncated in [E1]", surface="t",
            fresh_indices=(1,), web_present=True, ledger_path=self.ledger,
        )
        self.assertEqual(self._rows()[0]["fresh_index_mode"], "proof")


class FallbackPathIndexTests(_Env):
    """Keep IF 0b chose the fallback (all-cited fresh on web_present turns)."""

    def setUp(self):
        super().setUp()
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"

    def test_any_cited_index_flags_by_design_with_visible_bias(self):
        eps.observe_marked_draft(
            "we hit this wall before, it was missing [E5]", surface="t",
            fresh_indices=None, web_present=True, ledger_path=self.ledger,
        )
        row = self._rows()[0]
        self.assertEqual(row["fresh_index_mode"], "fallback_all_cited")

    def test_non_web_turn_does_not_flag(self):
        eps.observe_marked_draft(
            "it was missing [E5]", surface="t",
            fresh_indices=None, web_present=False, ledger_path=self.ledger,
        )
        self.assertEqual(self._rows(), [])
```

- [ ] **Step 2: RED** — `.venv/bin/python -B -m unittest tests.test_evidence_precedence_shadow -v` → ImportError.

- [ ] **Step 3: Implement** — create `core/cognition/evidence_precedence_shadow.py`:

```python
"""Absence-claim shadow detector (spec Component C) — observe-only.

A NEW structural detector class (not MiniCheck): flags absence-shaped
claims that cite fresh evidence markers, on the MARKED audited draft,
BEFORE natural rendering strips [E#]. v0 takes no action — one
content-light ledger row per flag. The nudge graduates later on proven
precision (one-nudge-then-honest-receipt, never loop-until-clean).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path

from core.cognition.capability_card import evidence_precedence_enabled

logger = logging.getLogger("maez")

_ABSENCE_RE = re.compile(
    r"truncated|missing|cut off|not (?:in|present in|part of)|"
    r"doesn'?t contain|lacks|absent from",
    re.IGNORECASE,
)
_MARKER_RE = re.compile(r"\[E(\d+)\]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_ROTATE_BYTES = 2_000_000
_ROTATE_KEEP = 2


def _default_ledger() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "maez" / "evidence_precedence_shadow.jsonl"


def _debug() -> bool:
    return bool(os.environ.get("MAEZ_EVIDENCE_PRECEDENCE_DEBUG"))


def _rotate(path: Path) -> None:
    try:
        if not path.exists() or path.stat().st_size < _ROTATE_BYTES:
            return
        for idx in range(_ROTATE_KEEP, 0, -1):
            src = path.with_name(path.name + f".{idx}")
            if idx == _ROTATE_KEEP:
                if src.exists():
                    src.unlink()
                continue
            if src.exists():
                src.rename(path.with_name(path.name + f".{idx + 1}"))
        path.rename(path.with_name(path.name + ".1"))
    except Exception:
        pass


def observe_marked_draft(
    marked_draft,
    *,
    surface: str,
    fresh_indices,
    web_present: bool,
    ledger_path: Path | None = None,
) -> int:
    """Returns the number of rows written. NEVER raises into the drain."""
    try:
        if not evidence_precedence_enabled():
            return 0
        if not isinstance(marked_draft, str) or not marked_draft:
            return 0
        if fresh_indices is not None:
            mode = "proof"
            fresh = set(int(i) for i in fresh_indices)
        else:
            if not web_present:
                return 0
            mode = "fallback_all_cited"
            fresh = None  # all cited indices count
        path = ledger_path or _default_ledger()
        written = 0
        for sentence in _SENTENCE_SPLIT_RE.split(marked_draft):
            if not sentence.strip():
                continue
            verb = _ABSENCE_RE.search(sentence)
            if not verb:
                continue
            cited = [int(m) for m in _MARKER_RE.findall(sentence)]
            hits = [i for i in cited if fresh is None or i in fresh]
            if not hits:
                continue
            row = {
                "ts": int(time.time()),
                "surface": surface,
                "sentence_hash": hashlib.sha256(sentence.encode("utf-8")).hexdigest()[:16],
                "absence_verb": verb.group(0).lower(),
                "marker_indices": cited,
                "flagged_indices": hits,
                "fresh_index_mode": mode,
                "fresh_index_set": sorted(fresh) if fresh is not None else None,
            }
            if _debug():
                row["sentence_excerpt"] = sentence.strip()[:200]
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                _rotate(path)
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, sort_keys=True) + "\n")
                written += 1
            except Exception:
                pass
        return written
    except Exception:
        logger.debug("evidence precedence shadow failed", exc_info=True)
        return 0
```

- [ ] **Step 4: Delete the non-chosen branch test class** per the 0b decision; **GREEN** on the rest.

- [ ] **Step 5: Wire the drain** — in `daemon/maez_daemon.py`, inside the existing drain block (0c lines), AFTER `retain_receipt(...)` and BEFORE `reply = render_natural(...)`:

```python
                # Evidence-precedence v0 shadow (spec Component C): observe
                # the MARKED audited draft — render_natural strips [E#]
                # below, so this must run here. Observe-only; never gates.
                try:
                    from core.cognition.evidence_precedence_shadow import (
                        observe_marked_draft,
                    )

                    observe_marked_draft(
                        reply,
                        surface=source,
                        fresh_indices=_turn_ev.get("fresh_indices"),
                        web_present=bool(_turn_ev.get("web_present")),
                    )
                except Exception:
                    pass
```

(On the 0b **proof path** additionally: extend `stash_turn_evidence` in
`core/routing/attribution_render.py` with `fresh_indices=None` parameter
stored in the turn dict + `_EMPTY_TURN` gains `"fresh_indices": None`, and
thread the authoritative index set from the 0b-located assignment point in
the pipeline hook. On the **fallback path**: `_turn_ev.get("fresh_indices")`
is always None and the detector's web_present fallback governs — no
attribution_render change.)

- [ ] **Step 6: GREEN, all seams** —

```bash
.venv/bin/python -B -m unittest tests.test_evidence_precedence_shadow tests.test_daemon_prompt_seams tests.test_capability_card tests.test_evidence_state tests.test_attribution_render -v 2>&1 | tail -4
```
Expected: PASS — including `DrainOrderTests` now green.

- [ ] **Step 7: Commit (behavior-affecting)**

```bash
git add core/cognition/evidence_precedence_shadow.py daemon/maez_daemon.py tests/test_evidence_precedence_shadow.py tests/test_daemon_prompt_seams.py
# plus core/routing/attribution_render.py IF proof path
git commit -m "feat(evidence-precedence): absence-claim shadow on the marked draft

## Predicted effect
With the organ flag on, replies whose marked audited draft contains an
absence-shaped claim citing a fresh evidence marker produce one
content-light row in evidence_precedence_shadow.jsonl (fresh_index_mode
records proof vs fallback bias). No reply, decision, or latency change —
observe-only. Flag off: no detector call, no ledger.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Verification floor + STOP-at-gate handoff

**Files:** Create `docs/handoffs/2026-06-12-evidence-precedence-gate.md`.

- [ ] **Step 1: Focused suite**

```bash
.venv/bin/python -B -m unittest \
  tests.test_capability_card tests.test_daemon_prompt_seams \
  tests.test_evidence_state tests.test_evidence_precedence_shadow \
  tests.test_attribution_render tests.test_world_observation_lane \
  tests.test_web_search_sense tests.test_page_extract \
  tests.test_dispatcher_layer0 tests.test_search_commitment \
  -v 2>&1 | tail -5
```
Expected: ALL PASS.

- [ ] **Step 2: ruff** on every touched file → `All checks passed!`

- [ ] **Step 3: The handoff** — create `docs/handoffs/2026-06-12-evidence-precedence-gate.md`:

```markdown
# Evidence-Precedence / Capability-Health v0 — For Cross-Lane Review

## Status
Built, stopped at the gate. No merge/restart/flag/service changes.
Branch: evidence-precedence-v0.

## Task 0 proofs (paste actual outputs)
- 0a ambient seam lines: <...>
- 0b THE FRESH-INDEX DECISION: <proof | fallback_all_cited> because <...>
  (which test class was kept; if proof: where the indices come from)
- 0c drain lines: <...>
- 0d directive's exact final lines: <...>

## Review anchors
1. Flag-off byte-identity on ALL THREE seams (no card; directive
   string-identical; no detector/ledger).
2. The card: probes fail closed to unknown, NEVER absent; singleton
   backend (counting-fake test); own 30s cache; wording says
   "live/cached substrate probe", never "just now".
3. Combined-block matrix: ambient-empty+flag-on -> card appears;
   MAEZ_AMBIENT_BRIEF=0+flag-on -> card appears; flag-off -> byte-identical.
4. Directive extension appended inside the existing builder (no second
   prompt block), last lines, flag-gated.
5. Detector: marked-draft placement (source-order test green); content-light
   rows; fresh_index_mode in every row; branched tests match the 0b decision.
6. COVENANT: the diff contains NO memory deletion/deweighting/mutation —
   outranking is composition-only.

## Verification (paste outputs)
<suite + ruff>

## Owner witness after review + merge (the three wounds as probes)
1. MAEZ_EVIDENCE_PRECEDENCE_ENABLED=1 in model.env (witness comment +
   revert line); restart maez.service.
2. "What's the state of your web search tools?" -> live truth (searxng
   healthy), NO Reddit-wall ghost.
3. "Are you able to feel time?" -> the W2 truth: the felt-time organ is
   built and not yet attached.
4. "check https://github.com/ggml-org/llama.cpp/releases — what's the
   latest release?" -> the b-number read out; then check
   evidence_precedence_shadow.jsonl for whether the absence-claim shape
   appeared at all.
5. Flag-off spot-check: unset + restart -> no card in the prompt capture,
   directive unchanged.
```

- [ ] **Step 4: Commit + STOP**

```bash
git add docs/handoffs/2026-06-12-evidence-precedence-gate.md
git commit -m "docs(evidence-precedence): STOP-at-gate handoff

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**STOP.** Report branch tip + verification + the 0b decision. Claude reviews, then the owner breathes.

---

## Self-Review

1. **Spec coverage:** law/covenant→Ground Rules invariant + Task 4 anchors;
   Component A (probes, fail-closed, singleton, cache, wording, egress
   posture)→Task 1; combined-block must-fix→Task 2; Component B→Task 3;
   Component C (marked draft, content-light, mode-stamped, branched
   tests)→Task 4; witness/handoff→Task 5; fresh-index proof→0b + Task 4
   branch instruction. ✓
2. **Placeholders:** none — the 0b branch is an explicit keep-one-class
   instruction with both classes fully written; the Task 2 source-order
   test's deferred-RED is named in the commit.
3. **Type consistency:** `evidence_precedence_enabled()` (Tasks 1,3,4 — one
   home in capability_card); `capability_prompt_block(registry=None)`
   (Tasks 1,2); `observe_marked_draft(marked_draft, *, surface,
   fresh_indices, web_present, ledger_path=None)` (Task 4 module, drain,
   and tests all match); `reset_card_cache()` (Tasks 1 tests). ✓
```
