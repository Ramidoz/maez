# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""LLM-as-judge for LongMemEval (Slice 9 Session 2).

The published benchmark uses GPT-4o as the correctness judge. Maez's
local stack already runs Qwen3-27B on llama-server, so we reuse that:
the judge is just another single-prompt completion via
``core.routing.llm_client.generate``.

Decisions:

* Output shape is **binary** (0 or 1) — matches LongMemEval's
  autoeval_label semantics and makes per-type aggregates immediately
  comparable to the published table.
* The judge **fails closed**: an unparseable verdict counts as 0,
  not 1. A model hedging ("not sure") doesn't get to inflate the
  score.
* Backend errors return ``None`` (not 0) so the driver can
  distinguish "judge failed" from "judge said incorrect" in the
  per-question record.
* Empty predictions short-circuit to 0 with no generate call.

Cite: Wu et al. 2024, LongMemEval (arxiv 2410.10813), §3.4 for the
binary-judge methodology.
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Single, deterministic verdict template. Asks for the verdict on the
# first line so a regex can pull it out without parsing free-form
# rationale.
_JUDGE_PROMPT = """You are an evaluator scoring an AI assistant's recall of a user's chat history.

Question the assistant was asked:
{question}

Reference answer (ground truth):
{reference}

Assistant's surfaced evidence / answer:
{prediction}

Decide whether the surfaced evidence supports the reference answer.
Begin your reply with EXACTLY one of these two words on the first line:
CORRECT
INCORRECT

Then optionally one short sentence explaining the call.""".strip()


# Match the FIRST verdict word anywhere in the reply — handles
# markdown bolds (``**CORRECT**``), prefixes ("Verdict: CORRECT"),
# code fences, and quote markers. INCORRECT must be matched as a
# whole word so it doesn't get swallowed by a "CORRECT" inside it.
_VERDICT_RE = re.compile(r"\b(INCORRECT|CORRECT)\b", re.IGNORECASE)


def judge_answer(
    *,
    question: str,
    reference: str,
    prediction: str,
    generate_fn: Optional[Callable[..., str]] = None,
    model: str | None = None,
    timeout_s: float = 60.0,
) -> Optional[int]:
    """Return 1 (correct), 0 (incorrect / unparseable / empty),
    or None (backend error).

    ``generate_fn`` is injectable for tests; production callers leave
    it None and get the local llama-server route through
    ``core.routing.llm_client.generate``.

    Note: ``timeout_s`` is forwarded through
    ``core.routing.llm_client.generate`` to supported backends (Ollama
    via ``ollama.Client(timeout=...)`` and llama.cpp via the
    OpenAI-compatible client timeout). Backend behavior still depends
    on the client/server honoring transport timeouts.
    """
    pred_s = str(prediction) if prediction is not None else ""
    if not pred_s.strip():
        return 0
    if generate_fn is None:
        from core.routing.llm_client import generate as _gen

        generate_fn = _gen
    # LongMemEval reference answers are sometimes numeric (e.g.
    # "How many sessions ago…"), so coerce defensively before strip.
    prompt = _JUDGE_PROMPT.format(
        question=str(question or "").strip(),
        reference=str(reference or "").strip(),
        # Bounded to keep judge prompts under the local model's
        # comfortable single-turn budget. Surfaced text >4000 chars
        # is truncated from the END — earlier evidence usually wins
        # because ``recall_for_cycle`` returns core/daily before raw.
        # If the multi-session category looks suspicious in a future
        # report, revisit this and prefer chunks containing reference
        # tokens.
        prediction=pred_s.strip()[:4000],
    )
    try:
        raw = generate_fn(
            prompt,
            model=model,
            temperature=0.0,
            max_tokens=80,
            timeout_s=timeout_s,
        )
    except Exception as exc:
        logger.warning("longmemeval judge failed: %s", exc)
        return None
    text = (raw or "").strip()
    # search, not match — the verdict can be wrapped in markdown
    # bolds, prefixed ("Verdict:"), or quoted; the audit caught
    # match-anchored false negatives.
    m = _VERDICT_RE.search(text)
    if not m:
        return 0
    return 0 if m.group(1).upper() == "INCORRECT" else 1


def build_sonnet_generate_fn(
    *, call_fn=None, model: str = "sonnet",
    caller: str = "longmemeval-judge",
):
    """Return a generate-shaped callable that delegates to
    ``core.routing.claude_tier.call`` so the LongMemEval judge can
    cross-check its local Qwen verdicts against Sonnet/Opus.

    The returned function matches the contract
    ``judge_answer.generate_fn`` expects:
    ``(prompt: str, *, model=None, temperature=0.0, max_tokens=80,
    timeout_s=60.0) -> str``.

    ``call_fn`` is injectable for tests; production callers leave it
    None and get the real ``claude_tier.call``.
    """
    if call_fn is None:
        from core.routing.claude_tier import call as _claude_call

        call_fn = _claude_call

    def _generate(
        prompt,
        *,
        model: str | None = None,  # noqa: ARG001 — fixed at closure time
        temperature: float = 0.0,  # noqa: ARG001 — proxy decides
        max_tokens: int = 80,  # noqa: ARG001 — proxy decides
        timeout_s: float = 60.0,
    ) -> str:
        from core.egress.provenance import ProvenancedText

        tagged_prompt = ProvenancedText.system_bounded_query(
            str(prompt),
            source_ref="core.eval.judge:sonnet_generate_prompt",
        )
        reply = call_fn(
            prompt=tagged_prompt,
            model=model_at_close,
            caller=caller,
            timeout_s=timeout_s,
        )
        return getattr(reply, "reply", "") or ""

    model_at_close = model
    return _generate


__all__ = ["build_sonnet_generate_fn", "judge_answer"]
