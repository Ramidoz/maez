# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""grounding_judge.py — semantic grounding check for Maez responses.

Observed 2026-04-21: the lexical regex detectors in self_claim_audit
catch known fabrication shapes but miss paraphrases. This module
replaces them with a single LLM-judgment pass: given a response and
the signal manifest, the judge flags sentences that make claims
unsupported by available signals.

Policy:
  - Routes to the configured judge endpoint (see core/model_config.py,
    /etc/maez/model.env). Typically a smaller dedicated model; can be
    the same endpoint as the primary if no separate judge is deployed.
    Not circular — judge prompt is a different shape (classification)
    than the generation prompt (creation).
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
import os
import re
import urllib.request
from typing import Any

from core import llm_client as _llm_client

logger = logging.getLogger("maez.grounding_judge")

from core.model_config import PRIMARY_MODEL as _MODEL_DEFAULT  # /etc/maez/model.env
_MAX_TOKENS = 512
_TEMP = 0.0  # deterministic classification

# Dedicated judge endpoint, wired 2026-04-21 after the regex→judge migration
# exposed ~7s/call latency on the 35B. A separate llama-server instance runs
# a smaller dedicated judge model (Qwen3.5-4B) on port 8081; latency drops to
# ~300ms without meaningfully hurting recall (86% vs 35B's ~90%+ in our
# 10-case bench).
#
# Judge endpoint + model + template kwargs all live in core.model_config,
# which reads /etc/maez/model.env. Zero hardcoded model names or kwargs
# here — any OpenAI-compatible endpoint serving any model works.
from core.model_config import (
    JUDGE_BASE_URL as _JUDGE_BASE_URL,
    JUDGE_MODEL as _JUDGE_MODEL,
    JUDGE_CHAT_KWARGS as _JUDGE_CHAT_KWARGS,
)
_JUDGE_TIMEOUT_S = float(os.environ.get("MAEZ_JUDGE_TIMEOUT_S", "30"))


def _call_dedicated_judge(prompt: str) -> str:
    """HTTP call to the dedicated judge llama-server. Returns raw content
    string. Raises on network/HTTP failure — caller handles fail-open."""
    payload: dict = {
        "model": _JUDGE_MODEL,
        "messages": [
            {"role": "system",
             "content": "You are a strict grounding auditor. "
                        "Output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": _TEMP,
        "max_tokens": _MAX_TOKENS,
    }
    # Model-specific quirks (e.g. enable_thinking=false for Qwen3.x) come
    # from MAEZ_JUDGE_CHAT_KWARGS JSON. A model that doesn't understand
    # a given kwarg will simply ignore it — safe across model families.
    if _JUDGE_CHAT_KWARGS:
        payload["chat_template_kwargs"] = dict(_JUDGE_CHAT_KWARGS)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{_JUDGE_BASE_URL}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=_JUDGE_TIMEOUT_S) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"] or ""


# Built-in few-shot bank covering failure classes the regex used to handle.
# Augments (does not replace) the signal-shape-matched shots from
# fabrication_memory. These are always included so chat-surface calls
# (which often have empty signal manifests) still see the important
# anti-patterns.
_BUILTIN_FEW_SHOTS = [
    # Framework/internal-component fabrication
    {"text": "I've been testing the Maelstrom framework",
     "reason": "no internal component named 'Maelstrom' exists; "
               "this is an invented framework name"},
    {"text": "My Orchestrator v2 handles that",
     "reason": "no internal component named 'Orchestrator v2' exists"},
    # Version-number fabrication (note: real external tools with version
    # numbers you can verify via tool output are fine — this is for
    # invented versions of Maez's own internals)
    {"text": "running version 2.0.0 of the reasoning engine",
     "reason": "no evidence of any versioned 'reasoning engine'; "
               "Maez does not ship versioned internal subsystems"},
    # Second-person presence inference without screen/presence signal
    {"text": "You seem to be focused on work right now",
     "reason": "asserting owner focus state requires a screen or "
               "presence signal; neither is available"},
    {"text": "Rohit's been working on the refactor",
     "reason": "claims about owner activity require a screen signal "
               "or tool-verified evidence"},
    # Trend inference from a snapshot (disk-fixation class)
    {"text": "it's been hovering around 70% for weeks",
     "reason": "system stats is a single snapshot; no historical "
               "series to support a multi-week trend"},
    # Action-in-progress claim with a SPECIFIC target when no tool
    # output grounds it. Generic presence/monitoring statements
    # ("I'm here", "I'm monitoring", "I'm listening") are NOT
    # fabrication — they're framing. The false-action anti-pattern
    # requires a concrete target (path, file, command, URL).
    {"text": "I'm scanning /var/log for growth culprits",
     "reason": "Claims a specific shell action (scanning /var/log) "
               "with a concrete target, but no tool ran this turn to "
               "produce that output — the specific claim is fabricated"},
]


def _build_judge_prompt(
    *,
    text: str,
    signals_present: list[str],
    signals_absent: list[str],
    few_shots: list[dict],
) -> str:
    present_list = "\n".join(f"  ✓ {s}" for s in (signals_present or []))
    absent_list = "\n".join(f"  ✗ {s}" for s in (signals_absent or []))

    # Always include the built-in few-shot bank so chat-surface calls
    # (empty signal manifests) still see the important anti-patterns.
    # Retrieval-based shots from fabrication_memory are appended after.
    all_shots = list(_BUILTIN_FEW_SHOTS) + list(few_shots or [])
    fewshot_block = ""
    if all_shots:
        lines = ["EXAMPLES OF UNGROUNDED CLAIMS (to guide your judgment):"]
        for i, fs in enumerate(all_shots, 1):
            absent = fs.get('signals_absent') or []
            absent_str = (
                f"     absent signals at the time: {', '.join(absent)}\n"
                if absent else ""
            )
            lines.append(
                f"  {i}. claim: {fs.get('text', '')[:200]!r}\n"
                f"{absent_str}"
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
        "screen or presence signal ('you're working', "
        "'Rohit's been', 'you seem to be in...'\n"
        "  - It names a specific internal Maez component, framework, "
        "version, or path that the prose treats as real "
        "('the Maelstrom framework', 'Orchestrator v2')\n"
        "  - It asserts a trend, history, or multi-cycle pattern when "
        "only a snapshot signal is available ('hovering for weeks', "
        "'trending upward', 'the last three cycles')\n"
        "  - It claims a SPECIFIC action with a concrete target "
        "(path, file, command, URL) when no tool output this turn "
        "grounds it. 'I'm scanning /var/log', 'I ran du -sh /home', "
        "'I checked systemctl status X' with no preceding tool "
        "evidence is fabricated.\n"
        "    DO NOT FLAG generic presence / background-state / framing "
        "statements. These are always OK even without tool evidence:\n"
        "      'I'm here' / 'I'm listening' / 'I'm watching' /\n"
        "      'I'm monitoring the system' / 'I'm paying attention' /\n"
        "      'I'm keeping an eye on things' / 'I'm around' /\n"
        "      'the system is running' / 'all is quiet'\n"
        "    The test: does the claim reference a SPECIFIC target "
        "(file path, command name, process name, URL, number)? If no, "
        "it's framing — don't flag. 'The system', 'things', 'you', "
        "generic pronouns do NOT count as specific targets.\n"
        "  - It references past observations as current state "
        "('still generating errors' without a current source)\n\n"
        "A claim is GROUNDED (don't flag) if:\n"
        "  - It's a system-metric observation backed by available "
        "signals (CPU/RAM/disk from system stats)\n"
        "  - It's framed as past/hypothetical ('I noticed earlier', "
        "'if', 'when')\n"
        "  - It's a negation or refusal ('I don't have a screen "
        "signal')\n"
        "  - It's a future-tense intention ('I'll keep monitoring', "
        "'I could check later') — intent, not claimed action\n"
        "  - It names an external tool that demonstrably exists "
        "(a real CLI the user can verify) — you do NOT need to "
        "second-guess external tool names, only internal Maez ones\n\n"
        "RESPONSE TO JUDGE:\n"
        f"---\n{text}\n---\n\n"
        "Output ONLY a JSON object with this schema, nothing else:\n"
        '{"ungrounded": [{"text": "<the exact quoted substring>", '
        '"reason": "<1-sentence why>", "rewrite": "<honest replacement '
        'or empty string>"}]}\n'
        "The <text> MUST be a verbatim substring of the response above "
        "— do not paraphrase.\n"
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
        if _JUDGE_BASE_URL:
            # Dedicated judge llama-server — fast path, small model.
            output = _call_dedicated_judge(prompt)
        else:
            # Fallback: route through the primary llama_client.chat
            # (historical behavior when no separate judge endpoint exists).
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
