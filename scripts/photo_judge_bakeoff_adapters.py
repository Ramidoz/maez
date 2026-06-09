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
from dataclasses import dataclass, field
from urllib.parse import urlparse

ADAPTER_VERSION = "1"
THRESHOLD_GRID = (0.3, 0.4, 0.5, 0.6, 0.7)


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    kind: str
    repo_id: str | None = None
    revision: str | None = None
    base_url: str | None = None
    expected_alias: str | None = None
    params: dict = field(default_factory=dict)


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


def is_loopback_http_url(url: str | None) -> bool:
    parsed = urlparse(url or "")
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}


def require_loopback_http_url(url: str | None, *, label: str) -> None:
    if not is_loopback_http_url(url):
        raise ValueError(f"{label} must use loopback http")


class CandidateAdapter:
    name: str = "base"
    score_based: bool = True   # False → label-native (no threshold)
    requires_artifact: bool = False
    revision: str | None = None   # pinned download revision (read from manifest)
    sha256: str | None = None     # artifact sha256 (read from manifest)

    def __init__(self, threshold: float | None = None):
        self.threshold = threshold
        self.unavailable_reason: str | None = None
        self._model = None
        self._load_failed = False
        artifact_dir = os.path.join(_BAKEOFF_CACHE, self.name)
        if self.requires_artifact and not os.path.isdir(artifact_dir):
            self._load_failed = True
            self.unavailable_reason = (
                f"missing bakeoff artifact: {artifact_dir} "
                "(run photo_judge_bakeoff_fetch first)")
            return
        # Pick up the pinned revision + sha256 the fetch helper recorded, so the
        # report's fingerprint IS the actual downloaded artifact (not hand-edited).
        man = read_bakeoff_manifest(artifact_dir)
        if self.requires_artifact and not man:
            self._load_failed = True
            self.unavailable_reason = (
                f"incomplete bakeoff artifact: {artifact_dir} "
                "has no bakeoff_manifest.json")
            return
        if man:
            manifest_repo = man.get("repo_id")
            if manifest_repo and manifest_repo != getattr(self, "model_id", None):
                self._load_failed = True
                self.unavailable_reason = (
                    f"manifest repo_id {manifest_repo!r} != spec repo_id "
                    f"{getattr(self, 'model_id', None)!r}")
                return
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
    requires_artifact = True
    model_id = "vectara/hallucination_evaluation_model"

    def __init__(self, threshold=None, name=None, repo_id=None):
        if name:
            self.name = name
        if repo_id:
            self.model_id = repo_id
        super().__init__(threshold=threshold)

    def _load(self):
        from transformers import AutoModelForSequenceClassification
        from transformers.modeling_utils import PreTrainedModel
        if not hasattr(PreTrainedModel, "all_tied_weights_keys"):
            PreTrainedModel.all_tied_weights_keys = {}
        return AutoModelForSequenceClassification.from_pretrained(
            os.path.join(_BAKEOFF_CACHE, self.name), trust_remote_code=True)

    def _raw_predict(self, premise, hypothesis):
        # HHEM returns a 0..1 consistency score (higher = consistent = grounded)
        return float(self._model.predict([(premise, hypothesis)])[0])


class NLIAdapter(CandidateAdapter):
    name = "nli"
    score_based = True
    requires_artifact = True
    model_id = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"

    def __init__(self, threshold=None, name=None, repo_id=None):
        if name:
            self.name = name
        if repo_id:
            self.model_id = repo_id
        super().__init__(threshold=threshold)

    def _load(self):
        from transformers import pipeline
        return pipeline("text-classification",
                        model=os.path.join(_BAKEOFF_CACHE, self.name),
                        top_k=None)

    def _raw_predict(self, premise, hypothesis):
        from core.routing.photo_contradiction import nli_grounded_score_from_output

        out = self._model({"text": premise, "text_pair": hypothesis})
        return nli_grounded_score_from_output(out)


class RerankerAdapter(CandidateAdapter):
    name = "reranker"
    score_based = True
    requires_artifact = True
    model_id = "Qwen/Qwen3-Reranker-0.6B"

    def __init__(self, threshold=None, name=None, repo_id=None):
        if name:
            self.name = name
        if repo_id:
            self.model_id = repo_id
        super().__init__(threshold=threshold)

    def _load(self):
        from sentence_transformers import CrossEncoder
        return CrossEncoder(os.path.join(_BAKEOFF_CACHE, self.name))

    def _raw_predict(self, premise, hypothesis):
        # BASELINE-CAVEATED: relevance != entailment. Higher relevance treated
        # as "grounded" only as a baseline signal.
        return float(self._model.predict([(premise, hypothesis)])[0])


class MiniCheckAdapter(CandidateAdapter):
    name = "minicheck-roberta"
    score_based = False   # label-native 0/1
    requires_artifact = True
    model_id = "lytang/MiniCheck-RoBERTa-Large"
    model_name = "roberta-large"

    def __init__(self, threshold=None, name=None, repo_id=None, model_name=None):
        if name:
            self.name = name
        if repo_id:
            self.model_id = repo_id
        if model_name:
            self.model_name = model_name
        super().__init__(threshold=threshold)

    def _load(self):
        from transformers import pipeline
        return pipeline("text-classification",
                        model=os.path.join(_BAKEOFF_CACHE, self.name),
                        top_k=None)

    def _raw_predict(self, premise, hypothesis):
        out = self._model({"text": premise, "text_pair": hypothesis})
        if out and isinstance(out[0], list):
            out = out[0]
        scores = {
            str(d.get("label", "")).lower(): float(d.get("score", 0.0))
            for d in out
        }
        def _is_grounded_label(label: str) -> bool:
            if ("unsupported" in label or "not_supported" in label
                    or "not-supported" in label):
                return False
            return (label in {"1", "label_1", "entailment", "true", "supported",
                              "supports"}
                    or "support" in label
                    or "entail" in label)

        def _is_contradicts_label(label: str) -> bool:
            return (label in {"0", "label_0", "contradiction", "false",
                              "unsupported", "contradicts"}
                    or "contradict" in label
                    or "unsupport" in label
                    or "not_supported" in label
                    or "not-supported" in label)

        grounded = max(
            (score for label, score in scores.items()
             if _is_grounded_label(label)),
            default=0.0,
        )
        contradicts = max(
            (score for label, score in scores.items()
             if _is_contradicts_label(label)),
            default=0.0,
        )
        return "grounded" if grounded >= contradicts else "contradicts"


class ThinknCheckAdapter(CandidateAdapter):
    name = "thinkncheck"
    score_based = False   # reasoning verdict
    requires_artifact = True
    model_id = "thinkncheck/thinkncheck-1b-gemma3-q4"  # verify at obtain-time

    def __init__(self, threshold=None, name=None, repo_id=None):
        if name:
            self.name = name
        if repo_id:
            self.model_id = repo_id
        super().__init__(threshold=threshold)

    def _load(self):
        # 4-bit 1B Gemma3; served via llama.cpp OR transformers — pinned at
        # obtain-time. Returns a callable that yields a verdict string.
        from scripts.photo_judge_bakeoff_thinkncheck import load_thinkncheck
        return load_thinkncheck(os.path.join(_BAKEOFF_CACHE, self.name))

    def _raw_predict(self, premise, hypothesis):
        verdict = self._model.verify(premise=premise, claim=hypothesis)
        return "grounded" if verdict.get("supported") else "contradicts"


class ChatJudgeAdapter(CandidateAdapter):
    name = "chatjudge"
    score_based = False   # yes/no
    model_id = "chatjudge (unconfigured)"  # set to the served alias at load

    def __init__(self, threshold=None, name=None, base_url=None,
                 expected_alias="maez-judge"):
        # NO hardcoded port: a wrong endpoint could benchmark the vision server
        # under a judge label (e.g. :8082 serves maez-vision here). base_url must
        # be given explicitly, and the SERVED alias is verified at load.
        if name:
            self.name = name
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
        require_loopback_http_url(self.base_url, label=f"ChatJudge {self.name!r}")
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


CANDIDATES = (
    CandidateSpec(name="hhem", kind="hhem",
                  repo_id="vectara/hallucination_evaluation_model",
                  revision="8e4a2e6e96c708cc76c2344f7e4757df2515292c"),
    CandidateSpec(name="minicheck-roberta", kind="minicheck",
                  repo_id="lytang/MiniCheck-RoBERTa-Large",
                  revision="74c8919647e61ed0f71bc177d94f10930f090068",
                  params={"model_name": "roberta-large"}),
    CandidateSpec(name="minicheck-flan-t5", kind="minicheck",
                  repo_id="lytang/MiniCheck-Flan-T5-Large",
                  revision="96eafd01cee2d16cf81aaa2fb226b14f422a37b3",
                  params={"model_name": "flan-t5-large"}),
    CandidateSpec(name="minicheck-deberta", kind="minicheck",
                  repo_id="lytang/MiniCheck-DeBERTa-v3-Large",
                  revision="2f2d01a54fa022a7ffadb76260e1ea8bc88c82bb",
                  params={"model_name": "deberta-v3-large"}),
    CandidateSpec(name="thinkncheck", kind="thinkncheck",
                  repo_id="thinkncheck/thinkncheck-1b-gemma3-q4"),
    CandidateSpec(name="nli", kind="nli",
                  repo_id="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
                  revision="6f5cf0a2b59cabb106aca4c287eed12e357e90eb"),
    CandidateSpec(name="reranker", kind="reranker",
                  repo_id="Qwen/Qwen3-Reranker-0.6B",
                  revision="e61197ed45024b0ed8a2d74b80b4d909f1255473"),
    CandidateSpec(name="chatjudge-maez-judge", kind="chatjudge",
                  base_url="http://127.0.0.1:8081",
                  expected_alias="maez-judge"),
)


def validate_local_chat_specs(specs=CANDIDATES):
    for spec in specs:
        if spec.kind != "chatjudge":
            continue
        require_loopback_http_url(spec.base_url, label=f"chatjudge spec {spec.name!r}")


def build_candidates(specs=CANDIDATES):
    validate_local_chat_specs(specs)
    adapters = []
    for spec in specs:
        if spec.kind == "hhem":
            adapters.append(HHEMAdapter(name=spec.name, repo_id=spec.repo_id))
        elif spec.kind == "minicheck":
            adapters.append(MiniCheckAdapter(
                name=spec.name,
                repo_id=spec.repo_id,
                model_name=spec.params["model_name"],
            ))
        elif spec.kind == "thinkncheck":
            adapters.append(ThinknCheckAdapter(name=spec.name, repo_id=spec.repo_id))
        elif spec.kind == "nli":
            adapters.append(NLIAdapter(name=spec.name, repo_id=spec.repo_id))
        elif spec.kind == "reranker":
            adapters.append(RerankerAdapter(name=spec.name, repo_id=spec.repo_id))
        elif spec.kind == "chatjudge":
            adapters.append(ChatJudgeAdapter(
                name=spec.name,
                base_url=spec.base_url,
                expected_alias=spec.expected_alias or "maez-judge",
            ))
        else:
            raise ValueError(f"unknown candidate kind {spec.kind!r}")
    return adapters


ALL_ADAPTERS = CANDIDATES
