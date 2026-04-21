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
    """Extract the `ungrounded` list from judge output. Tolerates
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
    return [u for u in ungrounded if isinstance(u, dict) and u.get("text")]


def judge(
    *,
    text: str,
    signals_present: list[str],
    signals_absent: list[str],
    few_shots: list[dict] | None = None,
    model: str = _MODEL_DEFAULT,
) -> list[dict]:
    """Run the grounding judge. Returns a list of flag dicts
    {text, reason, rewrite}. Never raises — all failures return [].
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
