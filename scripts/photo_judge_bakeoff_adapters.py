# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Uniform candidate adapters for the photo-contradiction bakeoff.

Each adapter exposes predict(premise, hypothesis) -> Verdict. The model-specific
load + raw prediction live in _load() / _raw_predict() (mocked in unit tests; the
exact model API is verified at obtain-time, execution step 1). Threshold mapping +
latency + the unavailable path are shared in CandidateAdapter.predict().
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

ADAPTER_VERSION = "1"
THRESHOLD_GRID = (0.3, 0.4, 0.5, 0.6, 0.7)


@dataclass
class Verdict:
    label: str          # "grounded" | "contradicts" | "unavailable"
    score: float | None
    latency_s: float


def score_to_label(score: float, threshold: float) -> str:
    """HIGHER score = more grounded. score >= threshold → grounded."""
    return "grounded" if score >= threshold else "contradicts"


def read_bakeoff_manifest(cache_dir: str) -> dict | None:
    """Read <cache_dir>/bakeoff_manifest.json (written by the fetch helper at
    download time) → {revision, sha256, ...}, or None if absent/unreadable. This
    is how a pinned revision + sha256 reach the report after a real download."""
    path = os.path.join(cache_dir, "bakeoff_manifest.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


class CandidateAdapter:
    name: str = "base"
    score_based: bool = True   # False → label-native (no threshold)
    revision: str | None = None   # pinned download revision (read from manifest)
    sha256: str | None = None     # artifact sha256 (read from manifest)

    def __init__(self, threshold: float | None = None):
        self.threshold = threshold
        self.unavailable_reason: str | None = None
        self._model = None
        self._load_failed = False
        # Pick up the pinned revision + sha256 the fetch helper recorded, so the
        # report's fingerprint IS the actual downloaded artifact (not hand-edited).
        man = read_bakeoff_manifest(os.path.join(_BAKEOFF_CACHE, self.name))
        if man:
            self.revision = man.get("revision")
            self.sha256 = man.get("sha256")
        try:
            self._model = self._load()
        except Exception as e:  # unavailable, never crash the bakeoff
            self._load_failed = True
            self.unavailable_reason = f"{type(e).__name__}: {e}"

    # ---- subclasses implement these two ----
    def _load(self):
        raise NotImplementedError

    def _raw_predict(self, premise: str, hypothesis: str):
        """Score-based → return float (higher=grounded). Label-native →
        return 'grounded' or 'contradicts'."""
        raise NotImplementedError

    # ---- shared ----
    def predict(self, premise: str, hypothesis: str) -> Verdict:
        if self._load_failed:
            return Verdict(label="unavailable", score=None, latency_s=0.0)
        t0 = time.perf_counter()
        try:
            raw = self._raw_predict(premise, hypothesis)
        except Exception as e:
            self.unavailable_reason = f"predict: {type(e).__name__}: {e}"
            return Verdict(label="unavailable", score=None,
                           latency_s=time.perf_counter() - t0)
        latency = time.perf_counter() - t0
        if self.score_based:
            thr = self.threshold if self.threshold is not None else 0.5
            return Verdict(label=score_to_label(float(raw), thr),
                           score=float(raw), latency_s=latency)
        # label-native
        return Verdict(label=str(raw), score=None, latency_s=latency)



_BAKEOFF_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "bakeoff",
)


class HHEMAdapter(CandidateAdapter):
    name = "hhem"
    score_based = True
    model_id = "vectara/hallucination_evaluation_model"

    def _load(self):
        from transformers import AutoModelForSequenceClassification
        return AutoModelForSequenceClassification.from_pretrained(
            os.path.join(_BAKEOFF_CACHE, "hhem"), trust_remote_code=True)

    def _raw_predict(self, premise, hypothesis):
        # HHEM returns a 0..1 consistency score (higher = consistent = grounded)
        return float(self._model.predict([(premise, hypothesis)])[0])


class NLIAdapter(CandidateAdapter):
    name = "nli"
    score_based = True
    model_id = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"

    def _load(self):
        from transformers import pipeline
        return pipeline("text-classification",
                        model=os.path.join(_BAKEOFF_CACHE, "nli"),
                        top_k=None)

    def _raw_predict(self, premise, hypothesis):
        # grounded-score = 1 - P(contradiction); lower = contradiction
        out = self._model({"text": premise, "text_pair": hypothesis})
        probs = {d["label"].lower(): d["score"] for d in out}
        contra = probs.get("contradiction", 0.0)
        return 1.0 - float(contra)


class RerankerAdapter(CandidateAdapter):
    name = "reranker"
    score_based = True
    model_id = "Qwen/Qwen3-Reranker-0.6B"

    def _load(self):
        from sentence_transformers import CrossEncoder
        return CrossEncoder(os.path.join(_BAKEOFF_CACHE, "reranker"))

    def _raw_predict(self, premise, hypothesis):
        # BASELINE-CAVEATED: relevance != entailment. Higher relevance treated
        # as "grounded" only as a baseline signal.
        return float(self._model.predict([(premise, hypothesis)])[0])


class MiniCheckAdapter(CandidateAdapter):
    name = "minicheck"
    score_based = False   # label-native 0/1
    model_id = "bespokelabs/Bespoke-MiniCheck-RoBERTa-Large"

    def _load(self):
        from minicheck.minicheck import MiniCheck
        return MiniCheck(model_name="roberta-large",
                         cache_dir=os.path.join(_BAKEOFF_CACHE, "minicheck"))

    def _raw_predict(self, premise, hypothesis):
        pred, _ = self._model.score(docs=[premise], claims=[hypothesis])[:2]
        return "grounded" if int(pred[0]) == 1 else "contradicts"


class ThinknCheckAdapter(CandidateAdapter):
    name = "thinkncheck"
    score_based = False   # reasoning verdict
    model_id = "thinkncheck/thinkncheck-1b-gemma3-q4"  # verify at obtain-time

    def _load(self):
        # 4-bit 1B Gemma3; served via llama.cpp OR transformers — pinned at
        # obtain-time. Returns a callable that yields a verdict string.
        from scripts.photo_judge_bakeoff_thinkncheck import load_thinkncheck
        return load_thinkncheck(os.path.join(_BAKEOFF_CACHE, "thinkncheck"))

    def _raw_predict(self, premise, hypothesis):
        verdict = self._model.verify(premise=premise, claim=hypothesis)
        return "grounded" if verdict.get("supported") else "contradicts"


class ChatJudgeAdapter(CandidateAdapter):
    name = "chatjudge"
    score_based = False   # yes/no
    model_id = "chatjudge (unconfigured)"  # set to the served alias at load

    def __init__(self, threshold=None, base_url=None, expected_alias="maez-judge"):
        # NO hardcoded port: a wrong endpoint could benchmark the vision server
        # under a judge label (e.g. :8082 serves maez-vision here). base_url must
        # be given explicitly, and the SERVED alias is verified at load.
        self.base_url = base_url
        self.expected_alias = expected_alias
        self.served_alias = None
        super().__init__(threshold=threshold)

    @staticmethod
    def _list_models(base_url):
        import json as _json
        import urllib.request
        req = urllib.request.Request(base_url.rstrip("/") + "/v1/models")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = _json.loads(r.read())
        return [m.get("id") for m in data.get("data", [])]

    def _load(self):
        if not self.base_url:
            raise RuntimeError(
                "ChatJudge requires an explicit base_url (a bakeoff judge "
                "endpoint); refusing to guess a port")
        served = self._list_models(self.base_url)
        if self.expected_alias not in served:
            raise RuntimeError(
                f"served models {served} at {self.base_url} do not include "
                f"expected alias '{self.expected_alias}' — refusing to benchmark "
                f"the wrong model")
        self.served_alias = self.expected_alias
        self.model_id = f"chatjudge:{self.expected_alias}@{self.base_url}"
        return self.base_url

    def _raw_predict(self, premise, hypothesis):
        import json as _json
        import urllib.request
        prompt = (
            "Evidence:\n" + premise + "\n\nClaim: " + hypothesis + "\n\n"
            "Does the claim CONTRADICT the evidence? Answer exactly "
            "'contradicts' or 'grounded'.")
        body = _json.dumps({
            "model": self.expected_alias,   # the VERIFIED served alias
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }).encode()
        req = urllib.request.Request(
            self.base_url.rstrip("/") + "/v1/chat/completions",
            data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = _json.loads(r.read())["choices"][0]["message"]["content"]
        return "contradicts" if "contradict" in txt.lower() else "grounded"


ALL_ADAPTERS = [
    HHEMAdapter, MiniCheckAdapter, ThinknCheckAdapter,
    NLIAdapter, RerankerAdapter, ChatJudgeAdapter,
]
