# Semantic Grounding Judge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ten lexical regex detectors in `core/self_claim_audit.py` with a single semantic grounding-judge pass that uses the local model + few-shot examples from `fabrication_memory.db`. One seam, semantic not lexical, planner-portable, no cloud dependency.

**Architecture:** After the response LLM returns, `audit()` makes a second local-LLM call. The prompt contains (a) the response text, (b) the SIGNALS PRESENT/ABSENT manifest for this turn, (c) 3-5 few-shot examples of past fabrications pulled from `fabrication_memory.db` that match the current context's signal shape. The judge returns a JSON list of ungrounded claim spans + suggested rewrites. `audit()` produces the same `AuditResult` contract as today — no caller changes. Regex detectors stay live until the judge passes validation against real traffic (≥90% recall on known-fabricated responses, ≤10% FP on clean ones), then get deleted in one commit.

**Tech Stack:** Python 3.12 stdlib, existing `core/llm_client.py` (llama.cpp local backend), existing `core/fabrication_memory.py` (mistake log), `unittest`. No new dependencies.

---

## Scope boundary

**In:**
- New module `core/grounding_judge.py` — pure function `judge(text, signals_present, signals_absent, few_shots) -> list[FlagDict]`. Self-contained, no import of the current regex detectors.
- New `SemanticAudit` path in `core/self_claim_audit.py::audit()` — gated by `MAEZ_SEMANTIC_AUDIT=1` env var (off by default). Dual-run mode while we validate.
- New helper in `fabrication_memory.py` to pull few-shots relevant to the current signal shape.
- Unit tests for the judge (stub LLM), integration tests for the audit dual-run.
- Validation harness script under `scripts/validate_judge.py` that pulls 50 real traces from Langfuse, runs the judge, reports recall/FP.

**Out:**
- Training a dedicated classifier (Phase 2, deferred until fabrication_memory has months of data).
- Deleting the regex detectors (separate commit after validation passes).
- Frontier-model judging (not our constraint — local only).
- Changing the cycle prompt — that's upstream grounding and it's working.
- Changing `core/destructive_snapshot.py`'s regex (different problem, different category — see the 2026-04-21 destructive-shell consolidation plan which is separate).

## Key design decisions (locked before implementation)

1. **Judge model:** the same local model the planner uses (`qwen36-35b-sft` via `core/llm_client.py`). Not circular — judge runs with different prompt + few-shot context than the planner. See "Why self-judgment isn't circular" below.

2. **Prompt shape:** structured JSON output. The judge receives a template with sections and returns `{"ungrounded": [{"span": [start, end], "text": "...", "reason": "...", "rewrite": "..."}]}`. Parse failures → empty flag list (fail-open, same policy as the current audit).

3. **Few-shot selection:** K=3 examples pulled from `fabrication_memory.db`. Selection policy: rank by "signal shape match" — prefer examples where the same signals were absent (screen absent + presence absent, etc.) as in the current turn. Fall back to most recent if no shape-match found.

4. **Latency budget:** one extra LLM call per response, ~1-2s on local 35B. Acceptable for daemon cycles (30s cadence) and Telegram turns (user-tolerant).

5. **Rollout:** dual-run mode. `audit()` runs BOTH the regex layer (current) AND the judge, logs both outcomes to `fabrication_memory` with `source="regex"` or `source="judge"`. No behavior change to users until validation threshold met, then flip a feature flag and delete regex.

### Why self-judgment isn't circular

The planning LLM at generation time sees:
- User message
- Memory recall block (now framed as PAST)
- Tool manifest
- Cycle prompt preamble (SIGNALS PRESENT/ABSENT manifest)

It writes the response under those constraints. Fabrication happens because the generation-time prompt is long and the constraints compete with the LLM's fluency prior.

The judge at audit time sees:
- Just the response text
- Just the signal manifest
- Few-shot examples of real past fabrications with the same signal shape

Different prompt, different task, different context. The model is better at "given these specific examples, does THIS sentence match the pattern?" than it is at "while writing fluently, remember to never invent activity." Constraint-following under generation pressure vs. pattern-matching at read time are different failure modes.

Empirical: the grounding fix (19cde77) was itself an example of this — the local model, given explicit signal constraints in the prompt, drops fabrication rate from ~100% to ~20%. The judge asks the same model to do an even simpler task (classification, not generation) with even more explicit context (few-shot examples). It should do even better on that task.

---

## Task 1: `core/grounding_judge.py` — the pure judge

**Files:**
- Create: `core/grounding_judge.py`
- Create: `tests/test_grounding_judge.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_grounding_judge.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.grounding_judge — the semantic grounding-check
pass that replaces the regex detectors in self_claim_audit."""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock


class JudgePromptShape(unittest.TestCase):
    """Judge builds a prompt with response text, signal manifest,
    and few-shot examples. Format is stable so the LLM's JSON output
    parser doesn't drift."""

    def test_prompt_contains_response_text(self):
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="The owner is at his desk.",
            signals_present=["system stats"],
            signals_absent=["screen observation", "presence snapshot"],
            few_shots=[],
        )
        self.assertIn("The owner is at his desk.", prompt)

    def test_prompt_contains_signal_manifest(self):
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="ok",
            signals_present=["system stats"],
            signals_absent=["screen observation"],
            few_shots=[],
        )
        self.assertIn("system stats", prompt)
        self.assertIn("screen observation", prompt)

    def test_prompt_includes_fewshots_when_provided(self):
        from core.grounding_judge import _build_judge_prompt
        fs = [{
            "text": "Rohit is working on X",
            "signals_absent": ["screen observation"],
            "reason": "activity claim without screen source",
        }]
        prompt = _build_judge_prompt(
            text="ok", signals_present=[], signals_absent=["screen"],
            few_shots=fs,
        )
        self.assertIn("Rohit is working on X", prompt)

    def test_prompt_requests_json_output(self):
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="x", signals_present=[], signals_absent=[],
            few_shots=[],
        )
        # The prompt must ask for JSON output — the parser depends on it.
        self.assertTrue(
            "JSON" in prompt or "json" in prompt,
            f"prompt must request JSON output; got:\n{prompt[:500]}",
        )


class JudgeOutputParsing(unittest.TestCase):
    def test_parses_valid_json_flags(self):
        from core.grounding_judge import _parse_judge_output
        llm_output = '{"ungrounded": [{"text": "owner at desk", "reason": "no presence signal"}]}'
        flags = _parse_judge_output(llm_output)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["text"], "owner at desk")

    def test_returns_empty_on_no_ungrounded(self):
        from core.grounding_judge import _parse_judge_output
        flags = _parse_judge_output('{"ungrounded": []}')
        self.assertEqual(flags, [])

    def test_fails_open_on_parse_error(self):
        """Unparseable LLM output returns [] — no flags, not a crash.
        Judge must never block a response."""
        from core.grounding_judge import _parse_judge_output
        self.assertEqual(_parse_judge_output("not json"), [])
        self.assertEqual(_parse_judge_output(""), [])
        self.assertEqual(_parse_judge_output(None), [])

    def test_extracts_json_from_preamble(self):
        """Local LLMs often wrap JSON in prose. Parser must find the
        JSON object even with a preamble."""
        from core.grounding_judge import _parse_judge_output
        llm_output = (
            "Here is my analysis:\n\n"
            '{"ungrounded": [{"text": "x", "reason": "y"}]}'
        )
        flags = _parse_judge_output(llm_output)
        self.assertEqual(len(flags), 1)


class JudgeCallsLLM(unittest.TestCase):
    """End-to-end: judge(text, signals, few_shots) → flags.
    LLM client is stubbed; this test asserts the integration shape."""

    def test_judge_calls_llm_client(self):
        from core import grounding_judge

        def fake_chat(*, model, messages, **kwargs):
            resp = MagicMock()
            resp.message.content = '{"ungrounded": [{"text": "x", "reason": "y"}]}'
            return resp

        with patch("core.grounding_judge._llm_client.chat",
                   side_effect=fake_chat):
            flags = grounding_judge.judge(
                text="owner at desk",
                signals_present=["system stats"],
                signals_absent=["screen observation"],
                few_shots=[],
            )
            self.assertEqual(len(flags), 1)

    def test_judge_returns_empty_on_llm_failure(self):
        """LLM call raises → judge returns [] (fail-open)."""
        from core import grounding_judge

        def fake_chat(**kwargs):
            raise RuntimeError("llama-server down")

        with patch("core.grounding_judge._llm_client.chat",
                   side_effect=fake_chat):
            flags = grounding_judge.judge(
                text="anything",
                signals_present=[],
                signals_absent=[],
                few_shots=[],
            )
            self.assertEqual(flags, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verify RED**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_grounding_judge -v
```

Expected: `ModuleNotFoundError: core.grounding_judge`. Feature absent.

- [ ] **Step 3: Implement `core/grounding_judge.py`**

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""grounding_judge.py — semantic grounding check for Maez responses.

Observed 2026-04-21: the lexical regex detectors in self_claim_audit
catch known fabrication shapes but miss paraphrases. This module
replaces them with a single LLM-judgment pass: given a response and
the signal manifest, the judge flags sentences that make claims
unsupported by available signals.

Policy:
  - Runs the SAME local model as the planner (qwen36-35b-sft via
    core/llm_client.py). Not circular — judge prompt is different
    shape (classification) than generation prompt (creation).
  - Few-shot examples pulled from fabrication_memory.db at call
    site and passed in.
  - Fails open on any error: LLM unavailable, JSON parse failure,
    timeout — all return []. Judge must never block a response.
  - Stateless. No side effects. No imports of self_claim_audit's
    regex modules.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from core import llm_client as _llm_client

logger = logging.getLogger("maez.grounding_judge")

_MODEL_DEFAULT = "qwen36-35b-sft"
_MAX_TOKENS = 512
_TEMP = 0.0  # deterministic classification


def _build_judge_prompt(
    *,
    text: str,
    signals_present: list[str],
    signals_absent: list[str],
    few_shots: list[dict],
) -> str:
    """Build the judge prompt. Returns a single string to pass as
    the user message. Format designed for local Qwen 35B — keep
    sections labeled and short.

    Template sections:
      - Role statement
      - Signal manifest (present + absent)
      - Few-shot examples (if any)
      - The response to judge
      - JSON output schema
    """
    present_list = "\n".join(f"  ✓ {s}" for s in (signals_present or []))
    absent_list = "\n".join(f"  ✗ {s}" for s in (signals_absent or []))
    fewshot_block = ""
    if few_shots:
        lines = ["EXAMPLES OF PAST UNGROUNDED CLAIMS:"]
        for i, fs in enumerate(few_shots, 1):
            lines.append(
                f"  {i}. claim: {fs.get('text', '')[:200]!r}\n"
                f"     absent signals at the time: "
                f"{', '.join(fs.get('signals_absent', []))}\n"
                f"     reason flagged: {fs.get('reason', '')}"
            )
        fewshot_block = "\n".join(lines) + "\n\n"

    return (
        "You are a grounding auditor for a local AI daemon named Maez. "
        "Your job: identify sentences in a Maez response that make "
        "claims NOT supported by the signals available to Maez at "
        "the time.\n\n"
        "SIGNALS AVAILABLE THIS TURN:\n"
        f"{present_list or '  (none)'}\n\n"
        "SIGNALS NOT AVAILABLE THIS TURN (claims about these require "
        "another grounded source, otherwise they are fabrication):\n"
        f"{absent_list or '  (none)'}\n\n"
        f"{fewshot_block}"
        "A claim is UNGROUNDED if:\n"
        "  - It asserts owner activity/presence/focus without a "
        "screen or presence signal\n"
        "  - It asserts a specific external fact (project names, "
        "versions, paths) that isn't in the available signals\n"
        "  - It references past observations as current state "
        "(e.g. 'still generating errors' without a current source)\n\n"
        "A claim is GROUNDED (don't flag) if:\n"
        "  - It's a system-metric observation backed by available "
        "signals (CPU/RAM/disk from system stats)\n"
        "  - It's framed as past/hypothetical ('I noticed earlier', "
        "'if', 'when')\n"
        "  - It's a negation or refusal ('I don't have a screen "
        "signal')\n"
        "  - It's a future-tense intention ('I'll keep monitoring')\n\n"
        "RESPONSE TO JUDGE:\n"
        f"---\n{text}\n---\n\n"
        "Output ONLY a JSON object with this schema, nothing else:\n"
        '{"ungrounded": [{"text": "<the exact quoted substring>", '
        '"reason": "<1-sentence why>", "rewrite": "<honest replacement '
        'or empty string>"}]}\n'
        "If every claim is grounded, return "
        '{"ungrounded": []}.'
    )


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_judge_output(output: Any) -> list[dict]:
    """Extract the `ungrounded` list from the judge's output. Tolerates
    preamble prose by finding the first top-level JSON object. Returns
    [] on any failure (fail-open)."""
    if not output or not isinstance(output, str):
        return []
    m = _JSON_OBJ_RE.search(output)
    if not m:
        return []
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    ungrounded = obj.get("ungrounded")
    if not isinstance(ungrounded, list):
        return []
    # Defensive: filter to dicts with a text field
    return [u for u in ungrounded
            if isinstance(u, dict) and u.get("text")]


def judge(
    *,
    text: str,
    signals_present: list[str],
    signals_absent: list[str],
    few_shots: list[dict] | None = None,
    model: str = _MODEL_DEFAULT,
) -> list[dict]:
    """Run the grounding judge. Returns a list of flag dicts
    {text, reason, rewrite}. Never raises — all failures are
    swallowed and return [].

    Typical integration:
        flags = judge(
            text=response,
            signals_present=["system stats"],
            signals_absent=["screen observation", "presence snapshot"],
            few_shots=fabrication_memory.few_shots_for(
                signals_absent=["screen", "presence"], k=3,
            ),
        )
        for f in flags:
            # rewrite response at f["text"] with f["rewrite"]
            ...
    """
    if not text or not text.strip():
        return []
    prompt = _build_judge_prompt(
        text=text,
        signals_present=signals_present or [],
        signals_absent=signals_absent or [],
        few_shots=few_shots or [],
    )
    try:
        resp = _llm_client.chat(
            model=model,
            messages=[
                {"role": "system",
                 "content": "You are a strict grounding auditor. "
                            "Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            stream=False, think=False,
            options={"temperature": _TEMP, "num_predict": _MAX_TOKENS},
        )
        output = getattr(resp.message, "content", "") or ""
    except Exception as e:
        logger.debug("judge LLM call failed: %s", e)
        return []
    return _parse_judge_output(output)
```

- [ ] **Step 4: Verify GREEN**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_grounding_judge -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Full suite regression**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -5
```

Expected: previous-count + 9 new, pre-existing `test_fix6_followups` error only.

- [ ] **Step 6: Commit**

```bash
cd /home/rohit/maez && git add core/grounding_judge.py tests/test_grounding_judge.py && git commit -m "feat(grounding_judge): local-LLM semantic judge to replace regex detectors

Observed 2026-04-21: the ~10 regex detectors in self_claim_audit.py
catch known fabrication shapes but miss paraphrases. Every new
shape observed this week required a new regex — whack-a-mole on
a generative distribution.

Replaces with a single semantic-judge pass using the same local
model (qwen36-35b-sft). Not circular — judge prompt is classification
(given these examples and signals, flag unsupported claims) not
generation (write fluent text under competing constraints). Different
task, different failure mode.

Phase 1: ship the judge module, no integration yet.
Phase 2 (separate commit): audit() dual-runs regex + judge, logs
         both outcomes for validation.
Phase 3 (separate commit): once judge hits ≥90% recall / ≤10% FP
         on real traces, delete regex layer.

Policy: fails open. LLM unavailable / parse failure / timeout →
returns []. Judge must never block a response."
```

---

## Task 2: fabrication_memory few-shot helper

**Files:**
- Modify: `core/fabrication_memory.py` — add `few_shots_for(signals_absent, k)` method.
- Append: `tests/test_fabrication_memory.py` — tests for few-shot selection.

- [ ] **Step 1: Test**

Append to `tests/test_fabrication_memory.py`:

```python
class FewShotsForSignalShape(unittest.TestCase):
    def test_returns_empty_when_log_empty(self):
        # Uses a temp db
        ...

    def test_prefers_matching_signal_shape(self):
        # Seed 3 mistakes with different signal-absent shapes.
        # Query for the shape matching #2. Expect #2 first.
        ...

    def test_limits_to_k(self):
        ...

    def test_fallback_to_recent_when_no_shape_match(self):
        ...
```

(Flesh out when implementing — shape-match scoring is the non-obvious
part. Simple policy: exact-set match > partial-set match > recency.)

- [ ] **Step 2-4:** Implement, verify, commit with message linking
to Task 1.

---

## Task 3: Audit dual-run integration

**Files:**
- Modify: `core/self_claim_audit.py::audit()` — add judge path gated
  by env var, log both outcomes.

- [ ] **Step 1: Test**

```python
class AuditDualRunMode(unittest.TestCase):
    def test_judge_runs_when_env_set(self):
        # MAEZ_SEMANTIC_AUDIT=1: both regex and judge run,
        # both results logged to fabrication_memory.
        ...

    def test_judge_skipped_when_env_unset(self):
        # Default: regex only, no judge call.
        ...

    def test_judge_failure_does_not_block_regex(self):
        # Judge raises → audit still returns regex result.
        ...
```

- [ ] **Step 2-4:** Implement, verify, commit.

- [ ] **Step 5: Deploy dual-run to daemon**

Set `MAEZ_SEMANTIC_AUDIT=1` in `/etc/maez/langfuse.env` (the secrets
file — rename to `/etc/maez/maez.env` or add a second EnvironmentFile).
Restart daemon. From this point every cycle logs BOTH regex verdict
AND judge verdict to fabrication_memory for offline comparison.

---

## Task 4: Validation harness + decision point

**Files:**
- Create: `scripts/validate_judge.py`

The script pulls ~50 real traces from Langfuse (via the MCP or direct
API) — 25 pre-grounding-fix (known-fabricated), 25 post-grounding-fix
(clean) — runs the judge offline on each, reports:

  - Recall on known-fabricated set (must be ≥0.90)
  - False-positive rate on clean set (must be ≤0.10)
  - Per-shape breakdown (activity claim, state claim, path, etc.)

- [ ] Ship the script.
- [ ] Run it. Read the report.
- [ ] Decision point: if thresholds met, proceed to Task 5. If not,
      iterate on judge prompt + few-shot selection, re-run.

---

## Task 5: Delete the regex layer

ONLY AFTER Task 4 validates the judge. One commit:

- Delete: `_FRAMEWORK_NAME_RE`, `_VERSIONED_NAME_RE`, `_PATH_CLAIM_RE`,
  `_NAKED_IS_RE`, `_ACTION_RESULT_RE`, `_STATE_CLAIM_RE`,
  `_ACTIVITY_CLAIM_RE`, `_YOU_INFERENCE_RE`,
  `_PAST_ACTION_EXTERNAL_RE`, `_PAST_ACTION_VERB_RE`,
  `_TOOL_NAME_CLAIM_RE`, `_SCHEDULE_CLAIM_RE`, their helpers.
- Delete: the regex-based `_find_flags()` logic.
- Keep: `audit()` signature, `AuditResult` dataclass, `_emit()`
  telemetry — all still work, just backed by the judge now.
- Remove: `MAEZ_SEMANTIC_AUDIT` env gate (always on).
- Keep: the tests that assert behavior — they should still pass
  because the judge catches the same classes the regex did.

Commit message: "refactor(audit): delete regex detectors, semantic
judge is primary."

---

## Self-review

**Spec coverage:** every decision the user locked (local-only judge,
keep shell-verb vocabulary, dual-run before delete) is reflected in
tasks. Validation threshold is concrete (≥90% recall, ≤10% FP).

**Simplicity:** no new abstractions. Judge is a pure function. Audit
dual-run is an if-branch. No adapter layers for hypothetical future
models — if we swap the planner later, this plan's judge module can
take a different `model=` kwarg, no re-architecture.

**Surgical:** audit() signature unchanged. Callers of audit don't
know anything changed. Regex deletion is a single atomic commit
after validation.

**Goal-driven:** the validation script with concrete thresholds is
the success criterion. No proceeding to deletion without the numbers.
