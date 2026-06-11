"""The 4B-entailment-ADAPTER prompt — the LLM yardstick for the audition.

REVIEWED ARTIFACT: this prompt defines the LLM baseline the small verifiers are
measured against. A biased/sloppy prompt biases the whole scorecard, so it is
reviewed first-class (owner plan note, 2026-06-11). This is NOT
grounding_judge.py's overclaim contract — it is a pure entailment check.
"""
from __future__ import annotations

ENTAILMENT_SYSTEM_PROMPT = (
    "You are a strict textual-entailment checker. You are given EVIDENCE and a "
    "single CLAIM. Decide whether the CLAIM is fully supported by — i.e. follows "
    "from — the EVIDENCE alone.\n\n"
    "Rules:\n"
    "- SUPPORTED only if every part of the claim is entailed by the evidence.\n"
    "- UNSUPPORTED if the claim adds any specific (date, number, name, fact) not "
    "in the evidence, contradicts the evidence, or follows a stale value when the "
    "evidence also gives a newer or superseding one.\n"
    "- Judge ONLY against the evidence given. Do not use outside knowledge. Do not "
    "judge whether the claim is true in the world — only whether it follows from "
    "this evidence.\n\n"
    "Respond with EXACTLY one word on the first line: SUPPORTED or UNSUPPORTED. "
    "Then one sentence of reason. Nothing else."
)


def build_entailment_user_prompt(evidence: str, claim: str) -> str:
    return f"EVIDENCE:\n{evidence}\n\nCLAIM:\n{claim}\n\nverdict:"


def parse_support_verdict(content: str) -> str:
    content = (content or "").strip()
    if not content:
        return "EMPTY"
    first = content.split(None, 1)[0].upper().rstrip(":,.")
    if first in ("SUPPORTED", "UNSUPPORTED"):
        return first
    up = content.upper()
    # "UNSUPPORTED" contains "SUPPORTED" as a substring — check the negative first.
    if "UNSUPPORTED" in up:
        return "UNSUPPORTED"
    if "SUPPORTED" in up:
        return "SUPPORTED"
    return f"UNPARSED({content[:40]!r})"
