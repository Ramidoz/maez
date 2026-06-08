# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Uniform candidate adapters for the photo-contradiction bakeoff.

Each adapter exposes predict(premise, hypothesis) -> Verdict. The model-specific
load + raw prediction live in _load() / _raw_predict() (mocked in unit tests; the
exact model API is verified at obtain-time, execution step 1). Threshold mapping +
latency + the unavailable path are shared in CandidateAdapter.predict().
"""

from __future__ import annotations

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


class CandidateAdapter:
    name: str = "base"
    score_based: bool = True   # False → label-native (no threshold)

    def __init__(self, threshold: float | None = None):
        self.threshold = threshold
        self.unavailable_reason: str | None = None
        self._model = None
        self._load_failed = False
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
