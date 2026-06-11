"""Candidate verifier adapters for the grounding audition. CPU-only.

Each adapter: .support(evidence, claim) -> (label, latency_s).
Models load lazily so unit tests can mock the raw inference without downloading.
"""
from __future__ import annotations

import os
import time

import httpx

from adapter_prompt import (ENTAILMENT_SYSTEM_PROMPT, build_entailment_user_prompt,
                            parse_support_verdict)

# Option A: HHEM stays UNAVAILABLE unless an owner-approved pin is supplied via the
# HHEM_REVISION env var (post-gate). Inert by construction: no env var -> no download,
# no trust_remote_code. Owner-approved pin (2026-06-11, remote-code reviewed by owner
# + Claude — a benign T5 wrapper, no network/fs/exec): 8e4a2e6e96c708cc76c2344f7e4757df2515292c
HHEM_REPO = "vectara/hallucination_evaluation_model"
HHEM_REVISION = os.environ.get("HHEM_REVISION") or None
MINICHECK_REPO = "lytang/MiniCheck-DeBERTa-v3-Large"


class HhemRevisionUnconfigured(RuntimeError):
    """Raised when HhemVerifier is used before the owner-gated pin is set."""


class HhemVerifier:
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.last_score: float | None = None
        self._model = None

    def _load(self):
        if not HHEM_REVISION:
            raise HhemRevisionUnconfigured(
                "HHEM_REVISION unset — set the owner-approved pinned commit post-gate "
                "(no trust_remote_code download happens until then)")
        from transformers import AutoModelForSequenceClassification
        self._model = AutoModelForSequenceClassification.from_pretrained(
            HHEM_REPO, trust_remote_code=True, revision=HHEM_REVISION)

    def _score_raw(self, evidence: str, claim: str) -> float:
        if self._model is None:
            self._load()
        # HHEM predict takes (premise, hypothesis) pairs -> consistency score 0..1.
        return float(self._model.predict([(evidence, claim)])[0])

    def support(self, evidence: str, claim: str) -> tuple[str, float]:
        t0 = time.time()
        try:
            score = self._score_raw(evidence, claim)
        except Exception as e:
            return f"ERROR({type(e).__name__})", time.time() - t0
        self.last_score = score
        label = "SUPPORTED" if score >= self.threshold else "UNSUPPORTED"
        return label, time.time() - t0


class MinicheckVerifier:
    def __init__(self):
        self._model = None
        self._tok = None

    def _load(self):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self._tok = AutoTokenizer.from_pretrained(MINICHECK_REPO)
        self._model = AutoModelForSequenceClassification.from_pretrained(MINICHECK_REPO)

    def _predict_raw(self, evidence: str, claim: str) -> int:
        # CONFIRM in the post-gate smoke: MiniCheck takes (doc, claim) -> 2-class
        # logits, label 1 == supported. Adjust here if the real call differs.
        import torch
        if self._model is None:
            self._load()
        inputs = self._tok(evidence, claim, truncation=True, return_tensors="pt", max_length=2048)
        with torch.no_grad():
            logits = self._model(**inputs).logits
        return int(torch.argmax(logits, dim=-1).item())

    def support(self, evidence: str, claim: str) -> tuple[str, float]:
        t0 = time.time()
        try:
            raw = self._predict_raw(evidence, claim)
        except Exception as e:
            return f"ERROR({type(e).__name__})", time.time() - t0
        return ("SUPPORTED" if raw == 1 else "UNSUPPORTED"), time.time() - t0


class FourBAdapterVerifier:
    def __init__(self, url: str, model: str, timeout_s: float = 60.0):
        self.url = url
        self.model = model
        self.timeout_s = timeout_s

    def _chat_raw(self, evidence: str, claim: str) -> str:
        endpoint = self.url.rstrip("/") + "/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": ENTAILMENT_SYSTEM_PROMPT},
                {"role": "user", "content": build_entailment_user_prompt(evidence, claim)},
            ],
            "temperature": 0.0, "max_tokens": 80,
            "chat_template_kwargs": {"enable_thinking": False},
            "reasoning_effort": "none",
        }
        r = httpx.post(endpoint, json=payload, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    def support(self, evidence: str, claim: str) -> tuple[str, float]:
        t0 = time.time()
        try:
            content = self._chat_raw(evidence, claim)
        except Exception as e:
            return f"ERROR({type(e).__name__})", time.time() - t0
        return parse_support_verdict(content), time.time() - t0
