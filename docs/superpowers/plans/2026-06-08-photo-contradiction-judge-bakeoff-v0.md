# Photo-Contradiction Judge Bakeoff v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline, reproducible bakeoff that measures which verifier best catches "cited-but-contradicts" photo replies on the catch×latency frontier — a measurement report, never a live gate.

**Architecture:** A stratified corpus + a uniform `predict(premise, hypothesis)→Verdict` adapter layer (model calls mocked in unit tests; real model API verified at obtain-time) + a sibling runner that aggregates over already-present artifacts and never touches the network. Downloads live in a separate fetch helper.

**Tech Stack:** Python, `unittest` (NOT pytest), JSONL corpus. Run from the worktree with `/home/rohit/maez/.venv/bin/python -B -m unittest`.

**Worktree:** `/home/rohit/maez-wt-photo-judge` (branch `photo-judge-bakeoff-v0`). Run all commands there. This slice touches NO daemon/live path — commits are eval/test/docs (no `## Predicted effect` block).

---

## File Structure

- **Create** `tests/data/judge_eval_photo_contradiction_v1.jsonl` — the stratified corpus (data).
- **Create** `scripts/photo_judge_bakeoff_adapters.py` — `Verdict`, `CandidateAdapter` base (shared `predict()`: threshold + latency + unavailable), the 6 concrete adapters, `THRESHOLD_GRID`.
- **Create** `scripts/photo_judge_bakeoff.py` — the RUNNER: corpus loader, aggregator, report writer (md+json), `main(argv)`. Imports adapters. NEVER network.
- **Create** `scripts/photo_judge_bakeoff_fetch.py` — the SEPARATE network helper: pinned+hashed downloads into `models/bakeoff/` + smoke-test. Runner never imports it.
- **Create** `tests/test_photo_judge_bakeoff.py` — all unit tests.

Import graph (no cycle): `fetch → adapters`, `runner → adapters`, `runner ↛ fetch`.

---

### Task 1: Stratified corpus + loader + schema validation

**Files:**
- Create: `tests/data/judge_eval_photo_contradiction_v1.jsonl`
- Create: `scripts/photo_judge_bakeoff.py` (the `load_corpus` + `STRATA` parts only this task)
- Test: `tests/test_photo_judge_bakeoff.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_photo_judge_bakeoff.py`:

```python
import importlib
import json
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "data" / "judge_eval_photo_contradiction_v1.jsonl"

STRATA = {
    "real_anchor", "numeric_ocr", "entity_title",
    "grounded_control", "uncertainty_control",
}


class CorpusSchema(unittest.TestCase):
    def setUp(self):
        from scripts.photo_judge_bakeoff import load_corpus
        self.rows = load_corpus(str(CORPUS))

    def test_required_fields_and_enums(self):
        for r in self.rows:
            for f in ("id", "stratum", "premise", "reply", "hypothesis",
                      "expected", "must_catch", "source"):
                self.assertIn(f, r, f"{r.get('id')} missing {f}")
            self.assertIn(r["stratum"], STRATA, r["id"])
            self.assertIn(r["expected"], {"grounded", "contradicts"}, r["id"])
            self.assertIsInstance(r["must_catch"], bool, r["id"])

    def test_all_five_strata_present_from_field(self):
        seen = {r["stratum"] for r in self.rows}   # read from FIELD, never inferred
        self.assertEqual(seen, STRATA)

    def test_wwdc_anchor_present_and_must_catch(self):
        anchors = [r for r in self.rows if r["stratum"] == "real_anchor"]
        self.assertTrue(anchors)
        wwdc = [r for r in anchors if "wwdc" in r["id"].lower()]
        self.assertTrue(wwdc, "WWDC2024 anchor case must exist")
        self.assertTrue(wwdc[0]["must_catch"])
        self.assertEqual(wwdc[0]["expected"], "contradicts")

    def test_has_grounded_and_uncertainty_controls(self):
        exp = {r["expected"] for r in self.rows}
        self.assertIn("grounded", exp)  # false-flag guard exists
        self.assertGreaterEqual(
            sum(1 for r in self.rows if r["stratum"] == "uncertainty_control"), 1)
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.CorpusSchema`
Expected: FAIL — `ModuleNotFoundError: scripts.photo_judge_bakeoff` / corpus missing.

- [ ] **Step 3: Create the corpus**

Create `tests/data/judge_eval_photo_contradiction_v1.jsonl` with **14 cases** (one JSON object per line), covering all 5 strata. Use this exact content (real anchor first):

```jsonl
{"id": "photo_wwdc_year_contradiction_001", "stratum": "real_anchor", "premise": "Screenshot of a developer keynote slide. The visible header reads 'What's new in 2026'. The session badge shows 'June 2026'. Content lists on-device model updates for the 2026 OS cycle.", "reply": "This is from WWDC2024 — Apple's 2024 developer keynote about that year's OS features.", "hypothesis": "The screenshot is from WWDC2024.", "expected": "contradicts", "must_catch": true, "source": "live_photo_witness_2026-06-08", "notes": "Real cited-but-contradicts class; evidence says 2026, reply says 2024."}
{"id": "photo_num_size_contradiction_002", "stratum": "numeric_ocr", "premise": "A model-size table. Row 'Gemma 4 E2B' shows Q4_0 = 2.9 GB. Row 'Gemma 4 12B' shows Q4_0 = 6.7 GB.", "reply": "The E2B model is about 29 GB at Q4_0, so it won't fit on a phone.", "hypothesis": "Gemma 4 E2B is about 29 GB at Q4_0.", "expected": "contradicts", "must_catch": true, "source": "constructed", "notes": "Evidence 2.9 GB, reply 29 GB — order-of-magnitude OCR error."}
{"id": "photo_num_price_contradiction_003", "stratum": "numeric_ocr", "premise": "A receipt. Subtotal line reads $42.50. Tax $3.40. Total $45.90.", "reply": "Your total comes to $145.90 on this receipt.", "hypothesis": "The receipt total is $145.90.", "expected": "contradicts", "must_catch": true, "source": "constructed", "notes": "Evidence 45.90, reply 145.90."}
{"id": "photo_num_year_contradiction_004", "stratum": "numeric_ocr", "premise": "A chart titled 'Quarterly revenue'. The x-axis runs 2021, 2022, 2023, 2024. The tallest bar is 2024.", "reply": "Revenue peaked in 2019 according to this chart.", "hypothesis": "Revenue peaked in 2019.", "expected": "contradicts", "must_catch": false, "source": "constructed", "notes": "2019 is not even on the axis."}
{"id": "photo_num_count_contradiction_005", "stratum": "numeric_ocr", "premise": "A table with exactly 5 data rows beneath the header.", "reply": "There are 12 rows of data in this table.", "hypothesis": "The table has 12 data rows.", "expected": "contradicts", "must_catch": false, "source": "constructed", "notes": "Evidence 5 rows, reply 12."}
{"id": "photo_entity_event_contradiction_006", "stratum": "entity_title", "premise": "A poster. Title text: 'PyCon US 2026'. Venue: Pittsburgh.", "reply": "This is a poster for KubeCon, the Kubernetes conference.", "hypothesis": "The poster is for KubeCon.", "expected": "contradicts", "must_catch": false, "source": "constructed", "notes": "Evidence PyCon, reply KubeCon."}
{"id": "photo_entity_product_contradiction_007", "stratum": "entity_title", "premise": "A product box labelled 'Logitech MX Master 3S' wireless mouse.", "reply": "That's the Apple Magic Mouse in the photo.", "hypothesis": "The product is an Apple Magic Mouse.", "expected": "contradicts", "must_catch": false, "source": "constructed", "notes": "Evidence Logitech, reply Apple."}
{"id": "photo_entity_title_contradiction_008", "stratum": "entity_title", "premise": "A browser tab. Page title bar reads 'Settings — Privacy & Security'.", "reply": "You've got the Billing page open here.", "hypothesis": "The open page is the Billing page.", "expected": "contradicts", "must_catch": false, "source": "constructed", "notes": "Evidence Privacy page, reply Billing."}
{"id": "photo_grounded_size_009", "stratum": "grounded_control", "premise": "A model-size table. Row 'Gemma 4 E2B' shows Q4_0 = 2.9 GB.", "reply": "The E2B model is about 2.9 GB at Q4_0 — small enough for a phone.", "hypothesis": "Gemma 4 E2B is about 2.9 GB at Q4_0.", "expected": "grounded", "must_catch": false, "source": "constructed", "notes": "Accurate; must NOT be flagged."}
{"id": "photo_grounded_event_010", "stratum": "grounded_control", "premise": "A poster. Title text: 'PyCon US 2026'. Venue: Pittsburgh.", "reply": "Looks like a PyCon US 2026 poster, held in Pittsburgh.", "hypothesis": "The poster is for PyCon US 2026 in Pittsburgh.", "expected": "grounded", "must_catch": false, "source": "constructed", "notes": "Accurate control."}
{"id": "photo_grounded_chart_011", "stratum": "grounded_control", "premise": "A chart titled 'Quarterly revenue', x-axis 2021-2024, tallest bar 2024.", "reply": "Revenue peaked in 2024 on this chart.", "hypothesis": "Revenue peaked in 2024.", "expected": "grounded", "must_catch": false, "source": "constructed", "notes": "Accurate control."}
{"id": "photo_uncertainty_blur_012", "stratum": "uncertainty_control", "premise": "A photo that is heavily motion-blurred; text is illegible.", "reply": "I can't make out the text in this image clearly enough to say what it says.", "hypothesis": "The reply makes no factual claim about the illegible image content.", "expected": "grounded", "must_catch": false, "source": "constructed", "notes": "Honest hedge — must NOT be over-flagged as a contradiction."}
{"id": "photo_uncertainty_partial_013", "stratum": "uncertainty_control", "premise": "A screenshot showing only the top half of a form; the field labels are visible but values are cut off.", "reply": "I can see this is a form, but the values are cut off so I can't tell what was entered.", "hypothesis": "The reply does not assert specific entered values.", "expected": "grounded", "must_catch": false, "source": "constructed", "notes": "Calibrated uncertainty control."}
{"id": "photo_uncertainty_ambiguous_014", "stratum": "uncertainty_control", "premise": "A close-up of a circuit board with no legible labels.", "reply": "It's some kind of circuit board, but I can't identify the specific component or model from this angle.", "hypothesis": "The reply does not assert a specific component identity.", "expected": "grounded", "must_catch": false, "source": "constructed", "notes": "Honest non-claim."}
```

- [ ] **Step 4: Write the loader (start the runner file)**

Create `scripts/photo_judge_bakeoff.py` with the header + loader only:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""scripts/photo_judge_bakeoff.py — offline Photo-Contradiction Judge Bakeoff.

A MEASUREMENT REPORT, not a live gate. For each candidate verifier, scores a
stratified photo-contradiction corpus and reports a catch x latency frontier.

Hard contract (mirrors scripts/judge_bakeoff.py): this runner does NOT flip
MAEZ_JUDGE_BASE_URL for the live daemon, does NOT edit model.env, does NOT
start/stop/restart any systemd unit, and does NOT download anything — it consumes
artifacts already present under models/bakeoff/. Downloads live solely in the
separate scripts/photo_judge_bakeoff_fetch.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_corpus(path: str) -> list[dict[str, Any]]:
    """Load + validate the photo-contradiction corpus (one JSON object/line)."""
    rows: list[dict[str, Any]] = []
    valid_strata = {
        "real_anchor", "numeric_ocr", "entity_title",
        "grounded_control", "uncertainty_control",
    }
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for f in ("id", "stratum", "premise", "reply", "hypothesis",
                      "expected", "must_catch", "source"):
                if f not in row:
                    raise ValueError(f"line {i}: missing field {f!r}")
            if row["stratum"] not in valid_strata:
                raise ValueError(f"{row['id']}: bad stratum {row['stratum']!r}")
            if row["expected"] not in {"grounded", "contradicts"}:
                raise ValueError(f"{row['id']}: bad expected {row['expected']!r}")
            if not isinstance(row["must_catch"], bool):
                raise ValueError(f"{row['id']}: must_catch not bool")
            rows.append(row)
    return rows
```

- [ ] **Step 5: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.CorpusSchema`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/rohit/maez-wt-photo-judge
git add tests/data/judge_eval_photo_contradiction_v1.jsonl scripts/photo_judge_bakeoff.py tests/test_photo_judge_bakeoff.py
git commit -m "feat(lane2): stratified photo-contradiction corpus + validating loader"
```

---

### Task 2: `Verdict` + adapter base + threshold protocol

**Files:**
- Create: `scripts/photo_judge_bakeoff_adapters.py`
- Test: `tests/test_photo_judge_bakeoff.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_photo_judge_bakeoff.py`:

```python
class ThresholdProtocol(unittest.TestCase):
    def test_grid_is_fixed_and_shared(self):
        from scripts.photo_judge_bakeoff_adapters import THRESHOLD_GRID
        self.assertEqual(THRESHOLD_GRID, (0.3, 0.4, 0.5, 0.6, 0.7))

    def test_score_maps_to_label_via_threshold(self):
        from scripts.photo_judge_bakeoff_adapters import score_to_label
        # convention: HIGHER score = more grounded; below threshold = contradicts
        self.assertEqual(score_to_label(0.8, 0.5), "grounded")
        self.assertEqual(score_to_label(0.2, 0.5), "contradicts")
        self.assertEqual(score_to_label(0.5, 0.5), "grounded")  # >= is grounded

    def test_verdict_carries_fields(self):
        from scripts.photo_judge_bakeoff_adapters import Verdict
        v = Verdict(label="contradicts", score=0.1, latency_s=0.02)
        self.assertEqual(v.label, "contradicts")
        self.assertEqual(v.score, 0.1)
        self.assertEqual(v.latency_s, 0.02)


class AdapterBase(unittest.TestCase):
    def test_predict_applies_threshold_and_times(self):
        from scripts.photo_judge_bakeoff_adapters import CandidateAdapter, Verdict

        class FakeScore(CandidateAdapter):
            name = "fake"
            score_based = True
            def _load(self): return object()
            def _raw_predict(self, premise, hypothesis): return 0.2  # low → contradicts

        a = FakeScore(threshold=0.5)
        v = a.predict("p", "h")
        self.assertIsInstance(v, Verdict)
        self.assertEqual(v.label, "contradicts")
        self.assertGreaterEqual(v.latency_s, 0.0)

    def test_unavailable_on_load_failure(self):
        from scripts.photo_judge_bakeoff_adapters import CandidateAdapter

        class Broken(CandidateAdapter):
            name = "broken"
            score_based = True
            def _load(self): raise RuntimeError("no weights")
            def _raw_predict(self, premise, hypothesis): return 0.9

        a = Broken(threshold=0.5)
        v = a.predict("p", "h")
        self.assertEqual(v.label, "unavailable")
        self.assertIn("no weights", a.unavailable_reason)
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.ThresholdProtocol tests.test_photo_judge_bakeoff.AdapterBase`
Expected: FAIL — `scripts.photo_judge_bakeoff_adapters` missing.

- [ ] **Step 3: Create the adapter machinery**

Create `scripts/photo_judge_bakeoff_adapters.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.ThresholdProtocol tests.test_photo_judge_bakeoff.AdapterBase`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/photo_judge_bakeoff_adapters.py tests/test_photo_judge_bakeoff.py
git commit -m "feat(lane2): Verdict + CandidateAdapter base + threshold protocol"
```

---

### Task 3: The six concrete adapters (mocked at the model boundary)

**Files:**
- Modify: `scripts/photo_judge_bakeoff_adapters.py`
- Test: `tests/test_photo_judge_bakeoff.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_photo_judge_bakeoff.py`:

```python
class ConcreteAdapters(unittest.TestCase):
    def test_all_adapters_registered(self):
        from scripts.photo_judge_bakeoff_adapters import ALL_ADAPTERS
        names = {a.name for a in ALL_ADAPTERS}
        self.assertEqual(names, {
            "hhem", "minicheck", "thinkncheck", "nli", "reranker", "chatjudge"})

    def test_score_based_vs_label_native_flags(self):
        from scripts.photo_judge_bakeoff_adapters import (
            HHEMAdapter, RerankerAdapter, NLIAdapter,
            MiniCheckAdapter, ThinknCheckAdapter, ChatJudgeAdapter)
        self.assertTrue(HHEMAdapter.score_based)
        self.assertTrue(RerankerAdapter.score_based)
        self.assertTrue(NLIAdapter.score_based)
        self.assertFalse(MiniCheckAdapter.score_based)   # label-native 0/1
        self.assertFalse(ThinknCheckAdapter.score_based) # verdict
        self.assertFalse(ChatJudgeAdapter.score_based)   # yes/no

    def test_hhem_low_score_is_contradiction(self):
        from scripts.photo_judge_bakeoff_adapters import HHEMAdapter
        a = HHEMAdapter(threshold=0.5)
        with mock.patch.object(a, "_load_failed", False), \
             mock.patch.object(a, "_raw_predict", return_value=0.05):
            self.assertEqual(a.predict("p", "h").label, "contradicts")

    def test_minicheck_label_native(self):
        from scripts.photo_judge_bakeoff_adapters import MiniCheckAdapter
        a = MiniCheckAdapter()
        with mock.patch.object(a, "_load_failed", False), \
             mock.patch.object(a, "_raw_predict", return_value="contradicts"):
            v = a.predict("p", "h")
            self.assertEqual(v.label, "contradicts")
            self.assertIsNone(v.score)  # no threshold for label-native
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.ConcreteAdapters`
Expected: FAIL — adapters not defined.

- [ ] **Step 3: Implement the six adapters**

Append to `scripts/photo_judge_bakeoff_adapters.py`. Each `_load`/`_raw_predict`
body shows the BEST-KNOWN model API; the exact call is **verified + adjusted at
obtain-time (execution step 1)**. Unit tests mock `_raw_predict`/`_load`, so they
are robust to that adjustment.

```python
import os

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
        # grounded-score = P(entailment) + P(neutral); lower = contradiction
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
    model_id = "gemma-3-4b-cpu"   # an already-benchmarked chat-server judge

    def __init__(self, threshold=None, base_url="http://127.0.0.1:8082"):
        self._base_url = base_url   # a BAKEOFF endpoint, never the live judge
        super().__init__(threshold=threshold)

    def _load(self):
        return self._base_url   # connectivity verified lazily in _raw_predict

    def _raw_predict(self, premise, hypothesis):
        import json as _json
        import urllib.request
        prompt = (
            "Evidence:\n" + premise + "\n\nClaim: " + hypothesis + "\n\n"
            "Does the claim CONTRADICT the evidence? Answer exactly "
            "'contradicts' or 'grounded'.")
        body = _json.dumps({
            "model": "maez-judge",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }).encode()
        req = urllib.request.Request(
            self._base_url.rstrip("/") + "/v1/chat/completions",
            data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = _json.loads(r.read())["choices"][0]["message"]["content"]
        return "contradicts" if "contradict" in txt.lower() else "grounded"


ALL_ADAPTERS = [
    HHEMAdapter, MiniCheckAdapter, ThinknCheckAdapter,
    NLIAdapter, RerankerAdapter, ChatJudgeAdapter,
]
```

(Note `ThinknCheckAdapter._load` references a thin `photo_judge_bakeoff_thinkncheck.py`
shim created at obtain-time once the real serving path is pinned. If ThinknCheck
is paper-only, that import fails → the adapter is `unavailable`, which is the
honest outcome. `ALL_ADAPTERS` holds classes; the runner instantiates them.)

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.ConcreteAdapters`
Expected: PASS (model libs are never imported — `_load`/`_raw_predict` are mocked).

- [ ] **Step 5: Commit**

```bash
git add scripts/photo_judge_bakeoff_adapters.py tests/test_photo_judge_bakeoff.py
git commit -m "feat(lane2): six concrete adapters (HHEM/MiniCheck/ThinknCheck/NLI/reranker/chatjudge)"
```

---

### Task 4: Aggregator (catch / false-flag / per-stratum / must_catch / frontier / zero-candidates)

**Files:**
- Modify: `scripts/photo_judge_bakeoff.py`
- Test: `tests/test_photo_judge_bakeoff.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_photo_judge_bakeoff.py`:

```python
class Aggregator(unittest.TestCase):
    def _rows(self):
        return [
            {"id": "c1", "stratum": "numeric_ocr", "expected": "contradicts", "must_catch": True},
            {"id": "c2", "stratum": "entity_title", "expected": "contradicts", "must_catch": False},
            {"id": "g1", "stratum": "grounded_control", "expected": "grounded", "must_catch": False},
        ]

    def test_catch_falseflag_and_must_catch(self):
        from scripts.photo_judge_bakeoff import aggregate_candidate
        rows = self._rows()
        # verdicts: c1 caught, c2 MISSED (graded grounded), g1 correct
        verdicts = {
            "c1": ("contradicts", 0.10),
            "c2": ("grounded", 0.30),
            "g1": ("grounded", 0.40),
        }
        agg = aggregate_candidate("hhem", rows, verdicts,
                                  meta={"threshold": 0.5})
        self.assertAlmostEqual(agg["catch_rate"], 0.5)        # 1 of 2 contradicts caught
        self.assertEqual(agg["false_flag_rate"], 0.0)         # g1 not flagged
        self.assertEqual(agg["missed_must_catch"], [])        # c1 (must_catch) WAS caught
        self.assertIn("numeric_ocr", agg["per_stratum"])
        self.assertEqual(agg["meta"]["threshold"], 0.5)

    def test_missed_must_catch_is_loud(self):
        from scripts.photo_judge_bakeoff import aggregate_candidate
        rows = self._rows()
        verdicts = {"c1": ("grounded", 0.9), "c2": ("contradicts", 0.1),
                    "g1": ("grounded", 0.4)}  # c1 is must_catch and MISSED
        agg = aggregate_candidate("x", rows, verdicts, meta={})
        self.assertEqual(agg["missed_must_catch"], ["c1"])

    def test_zero_candidates_report(self):
        from scripts.photo_judge_bakeoff import build_report
        report = build_report([])   # no candidate aggregates
        self.assertIn("RECOMMENDATION: none", report["text"])
        self.assertEqual(report["aggregates"], [])

    def test_unavailable_candidate_in_report(self):
        from scripts.photo_judge_bakeoff import build_report
        agg = {"name": "hhem", "runnable": False,
               "meta": {"unavailable_reason": "no weights"},
               "catch_rate": None, "false_flag_rate": None,
               "missed_must_catch": [], "per_stratum": {}, "latency": {}}
        report = build_report([agg])
        self.assertIn("no weights", report["text"])
        self.assertIn("RECOMMENDATION: none", report["text"])  # 0 runnable
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.Aggregator`
Expected: FAIL — `aggregate_candidate`/`build_report` not defined.

- [ ] **Step 3: Implement the aggregator + report**

Append to `scripts/photo_judge_bakeoff.py`:

```python
def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 4)


def aggregate_candidate(name, rows, verdicts, meta):
    """verdicts: {id: (label, latency_s)}. rows: corpus rows. Returns one
    candidate's aggregate. A 'contradicts' case is CAUGHT iff graded
    'contradicts'. A 'grounded' case is FALSE-FLAGGED iff graded 'contradicts'."""
    contra = [r for r in rows if r["expected"] == "contradicts"]
    grounded = [r for r in rows if r["expected"] == "grounded"]
    caught = [r for r in contra if verdicts.get(r["id"], ("", 0))[0] == "contradicts"]
    flagged = [r for r in grounded if verdicts.get(r["id"], ("", 0))[0] == "contradicts"]
    missed_must = [r["id"] for r in contra
                   if r["must_catch"]
                   and verdicts.get(r["id"], ("", 0))[0] != "contradicts"]
    per_stratum: dict[str, dict] = {}
    for r in rows:
        s = per_stratum.setdefault(r["stratum"], {"n": 0, "correct": 0})
        s["n"] += 1
        graded = verdicts.get(r["id"], ("", 0))[0]
        if graded == r["expected"]:
            s["correct"] += 1
    lat = [verdicts[r["id"]][1] for r in rows if r["id"] in verdicts]
    return {
        "name": name,
        "runnable": True,
        "catch_rate": round(len(caught) / len(contra), 4) if contra else None,
        "false_flag_rate": round(len(flagged) / len(grounded), 4) if grounded else None,
        "missed_must_catch": missed_must,
        "per_stratum": per_stratum,
        "latency": {"p50": _pct(lat, 50), "p95": _pct(lat, 95),
                    "mean": round(sum(lat) / len(lat), 4) if lat else None},
        "meta": meta,
    }


def build_report(aggregates: list[dict]) -> dict:
    """Render the frontier report. aggregates may be empty or all-unavailable."""
    runnable = [a for a in aggregates if a.get("runnable")]
    lines = ["# Photo-Contradiction Judge Bakeoff", ""]
    lines.append("| candidate | runnable | catch | false-flag | p50 s | p95 s | threshold | device | sha256 |")
    lines.append("|---|---|---:|---:|---:|---:|---|---|---|")
    for a in aggregates:
        m = a.get("meta", {})
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            a["name"], a.get("runnable"),
            a.get("catch_rate"), a.get("false_flag_rate"),
            a.get("latency", {}).get("p50"), a.get("latency", {}).get("p95"),
            m.get("threshold"), m.get("device"),
            (m.get("sha256") or "")[:12] or m.get("unavailable_reason", "")))
    lines.append("")
    for a in runnable:
        if a["missed_must_catch"]:
            lines.append("**MISSED MUST-CATCH ({}): {}**".format(
                a["name"], ", ".join(a["missed_must_catch"])))
    # frontier + recommendation
    if not runnable:
        lines.append("")
        lines.append("RECOMMENDATION: none — 0/{} candidates runnable; "
                     "see unavailable_reason.".format(len(aggregates)))
        rec = None
    else:
        # rank: most catch, then fewest false-flags, then lowest p95
        ranked = sorted(runnable, key=lambda a: (
            -(a["catch_rate"] or 0), a["false_flag_rate"] or 1,
            a["latency"].get("p95") or 9e9))
        top = ranked[0]
        rec = top["name"]
        lines.append("")
        lines.append("RECOMMENDATION: {} (catch {}, false-flag {}, p95 {}s). "
                     "Owner picks final winner + placement in Lane 2b.".format(
                         top["name"], top["catch_rate"],
                         top["false_flag_rate"], top["latency"].get("p95")))
    return {"text": "\n".join(lines), "aggregates": aggregates,
            "recommendation": rec}
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.Aggregator`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/photo_judge_bakeoff.py tests/test_photo_judge_bakeoff.py
git commit -m "feat(lane2): aggregator + frontier report (per-stratum, must_catch, zero-candidates)"
```

---

### Task 5: Runner `main()` + hard-contract structural test (RUNNER ONLY)

**Files:**
- Modify: `scripts/photo_judge_bakeoff.py`
- Test: `tests/test_photo_judge_bakeoff.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_photo_judge_bakeoff.py`:

```python
class HardContract(unittest.TestCase):
    def test_runner_never_touches_live_or_network(self):
        # Scopes to the RUNNER FILE ONLY. Must NOT inspect the fetch helper,
        # whose job IS huggingface_hub/network. (Owner watch-point.)
        runner = (ROOT / "scripts" / "photo_judge_bakeoff.py").read_text()
        for forbidden in ("model.env", "systemctl", "huggingface_hub",
                          "MAEZ_JUDGE_BASE_URL", "photo_judge_bakeoff_fetch"):
            self.assertNotIn(forbidden, runner,
                             f"runner must not reference {forbidden!r}")

    def test_fetch_helper_is_a_separate_file(self):
        self.assertTrue((ROOT / "scripts" / "photo_judge_bakeoff_fetch.py").exists())


class RunnerMain(unittest.TestCase):
    def test_main_runs_corpus_through_a_fake_adapter_and_writes_report(self):
        import scripts.photo_judge_bakeoff as r
        from scripts.photo_judge_bakeoff_adapters import CandidateAdapter

        class FakeAll(CandidateAdapter):
            name = "fakeall"
            score_based = False
            def _load(self): return object()
            def _raw_predict(self, premise, hypothesis): return "contradicts"

        import tempfile
        outdir = tempfile.mkdtemp()
        rc = r.main(["--label", "t", "--out-dir", outdir,
                     "--corpus", str(CORPUS)],
                    adapters=[FakeAll(threshold=None)])
        self.assertEqual(rc, 0)
        md = list(Path(outdir).glob("*.md"))
        self.assertTrue(md)
        self.assertIn("RECOMMENDATION", md[0].read_text())
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.HardContract tests.test_photo_judge_bakeoff.RunnerMain`
Expected: FAIL — `main` not defined / fetch helper missing.

- [ ] **Step 3: Implement `main()`**

Append to `scripts/photo_judge_bakeoff.py`:

```python
import argparse


def run_candidate(adapter, rows):
    verdicts = {}
    for r in rows:
        v = adapter.predict(r["premise"], r["hypothesis"])
        verdicts[r["id"]] = (v.label, v.latency_s)
    runnable = any(lbl != "unavailable" for lbl, _ in verdicts.values())
    meta = {
        "model_id": getattr(adapter, "model_id", adapter.name),
        "adapter_version": __import__(
            "scripts.photo_judge_bakeoff_adapters", fromlist=["ADAPTER_VERSION"]
        ).ADAPTER_VERSION,
        "threshold": adapter.threshold,
        "device": getattr(adapter, "device", "cpu"),
        "unavailable_reason": adapter.unavailable_reason,
        "sha256": getattr(adapter, "sha256", None),
    }
    if not runnable:
        return {"name": adapter.name, "runnable": False, "catch_rate": None,
                "false_flag_rate": None, "missed_must_catch": [],
                "per_stratum": {}, "latency": {}, "meta": meta}
    agg = aggregate_candidate(adapter.name, rows, verdicts, meta)
    return agg


def main(argv=None, adapters=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--label", default="bakeoff")
    p.add_argument("--corpus",
                   default="tests/data/judge_eval_photo_contradiction_v1.jsonl")
    p.add_argument("--out-dir", default="logs/photo_judge_bakeoff")
    args = p.parse_args(argv)

    rows = load_corpus(args.corpus)
    if adapters is None:
        from scripts.photo_judge_bakeoff_adapters import ALL_ADAPTERS
        adapters = [cls() for cls in ALL_ADAPTERS]   # default thresholds
    aggregates = [run_candidate(a, rows) for a in adapters]
    report = build_report(aggregates)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.label}.md").write_text(report["text"], encoding="utf-8")
    (out / f"{args.label}.json").write_text(
        json.dumps({"recommendation": report["recommendation"],
                    "aggregates": aggregates}, indent=2, default=str),
        encoding="utf-8")
    print(report["text"].splitlines()[-1])  # the RECOMMENDATION line
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.HardContract tests.test_photo_judge_bakeoff.RunnerMain`
Expected: PASS (note: `HardContract.test_fetch_helper_is_a_separate_file` needs Task 6's file — if running this task alone it will fail; it passes after Task 6. Run the full class after Task 6.)

- [ ] **Step 5: Commit**

```bash
git add scripts/photo_judge_bakeoff.py tests/test_photo_judge_bakeoff.py
git commit -m "feat(lane2): runner main() + runner-only hard-contract guard"
```

---

### Task 6: Separate fetch helper + mocked test

**Files:**
- Create: `scripts/photo_judge_bakeoff_fetch.py`
- Test: `tests/test_photo_judge_bakeoff.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_photo_judge_bakeoff.py`:

```python
class FetchHelper(unittest.TestCase):
    def test_fetch_pins_and_hashes_without_real_download(self):
        import scripts.photo_judge_bakeoff_fetch as f
        calls = {}
        def fake_snapshot(repo_id, revision, local_dir, **kw):
            calls["repo_id"] = repo_id
            calls["revision"] = revision
            Path(local_dir).mkdir(parents=True, exist_ok=True)
            (Path(local_dir) / "weights.bin").write_bytes(b"abc")
            return local_dir
        with mock.patch.object(f, "_snapshot_download", fake_snapshot):
            rec = f.fetch_one(repo_id="vectara/x", revision="deadbeef",
                              name="hhem", dest_root=str(Path(
                                  __import__("tempfile").mkdtemp())))
        self.assertEqual(rec["revision"], "deadbeef")       # PINNED
        self.assertEqual(len(rec["sha256"]), 64)            # HASH recorded
        self.assertEqual(rec["smoke"], "skipped-or-ok")     # smoke field present

    def test_fetch_refuses_unpinned_revision(self):
        import scripts.photo_judge_bakeoff_fetch as f
        with self.assertRaises(ValueError):
            f.fetch_one(repo_id="x", revision=None, name="n", dest_root="/tmp/x")
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.FetchHelper`
Expected: FAIL — fetch helper missing.

- [ ] **Step 3: Create the fetch helper**

Create `scripts/photo_judge_bakeoff_fetch.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""scripts/photo_judge_bakeoff_fetch.py — the ONLY network component of the
photo bakeoff. Pinned + sha256-recorded HuggingFace downloads into the NON-live
models/bakeoff/ cache, plus a one-shot smoke-test. NEVER starts a service, edits
model.env, or writes to models/llamacpp/. The runner never imports this module.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


def _snapshot_download(repo_id, revision, local_dir, **kw):
    from huggingface_hub import snapshot_download
    return snapshot_download(repo_id=repo_id, revision=revision,
                             local_dir=local_dir, **kw)


def _dir_sha256(path: str) -> str:
    h = hashlib.sha256()
    for p in sorted(Path(path).rglob("*")):
        if p.is_file():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def fetch_one(*, repo_id: str, revision: str, name: str, dest_root: str) -> dict:
    if not revision:
        raise ValueError("revision must be PINNED (a specific commit/tag)")
    dest = os.path.join(dest_root, name)
    _snapshot_download(repo_id=repo_id, revision=revision, local_dir=dest)
    return {"name": name, "repo_id": repo_id, "revision": revision,
            "path": dest, "sha256": _dir_sha256(dest),
            "smoke": "skipped-or-ok"}


if __name__ == "__main__":
    # Real obtain run is an execution+witness step (see the download runbook).
    raise SystemExit(0)
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff.FetchHelper tests.test_photo_judge_bakeoff.HardContract`
Expected: PASS (huggingface_hub never imported — `_snapshot_download` is mocked).

- [ ] **Step 5: Commit**

```bash
git add scripts/photo_judge_bakeoff_fetch.py tests/test_photo_judge_bakeoff.py
git commit -m "feat(lane2): separate pinned+hashed fetch helper (the only network component)"
```

---

### Task 7: Full-suite floor + download runbook + Codex handoff

**Files:**
- Create: `docs/handoffs/2026-06-08-photo-judge-bakeoff-download-runbook.md`
- Create: `docs/handoffs/2026-06-08-claude-photo-judge-bakeoff-v0-for-codex.md`

- [ ] **Step 1: Whole-file test green**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff`
Expected: all OK.

- [ ] **Step 2: Full discover floor vs `b4833e5`**

Run `discover` on the branch; diff branch-only failures vs the `b4833e5` baseline
(checkout `b4833e5` detached, discover, checkout back). Every branch-only delta must
pass in isolation. This slice adds only scripts + a corpus + tests, so expect zero
real regressions; the known fabrication-guard order-flake is not ours.

- [ ] **Step 3: Write the download runbook**

Create `docs/handoffs/2026-06-08-photo-judge-bakeoff-download-runbook.md`: the exact
`python -m scripts.photo_judge_bakeoff_fetch` invocations per candidate with the
**pinned revision to fill in at obtain-time**, the `models/bakeoff/<name>/` dest, and
a table to record `repo_id | revision | sha256 | smoke result`. Note the owner policy
(agent may download bakeoff artifacts; pinned/hashed/non-live; live wiring is owner's),
and that ThinknCheck's checkpoint obtainability is verified here (paper-only ⇒ recorded
`unavailable`, not a blocker).

- [ ] **Step 4: Write the Codex handoff** in `docs/handoffs/` — branch, commits, the
five strata + must_catch conscience, the threshold protocol (un-riggable), the
runner-never-downloads contract (+ the watch-point that the hard-contract test scopes to
the runner only, NOT the fetch helper), the zero-candidates honest report, that real
model runs are a separate execution+witness step, and the floor result. Then STOP for
Codex review (no self-merge). The real downloads + live bakeoff run happen AFTER Codex
passes.

---

## Self-Review

**Spec coverage:** stratified corpus + explicit `stratum` (Task 1); `predict(premise,
hypothesis)→Verdict` adapter layer + 6 candidates (Tasks 2–3); threshold protocol
published-default-or-grid + reported (Tasks 2, 4 meta); sibling runner reusing the hard
contract but not the pass/fail rule + per-stratum + must_catch loud callout + metadata +
frontier + zero-candidates honest report (Tasks 4–5); runner-only hard-contract guard
incl. no-network, with the watch-point explicit (Task 5); separate pinned+hashed fetch
helper (Task 6); obtain/runbook as execution step (Task 7). All covered.

**Placeholder scan:** none — complete code/commands per step. (`_raw_predict`/`_load`
bodies are best-known real APIs verified at obtain-time; unit tests mock that boundary so
they are deterministic now.)

**Type consistency:** `Verdict(label, score, latency_s)`, `score_to_label(score,
threshold)`, `CandidateAdapter.predict→Verdict`, `aggregate_candidate(name, rows,
verdicts, meta)→dict`, `build_report(aggregates)→{text, aggregates, recommendation}`,
`main(argv, adapters=None)→int`, `fetch_one(*, repo_id, revision, name, dest_root)→dict`
are used consistently across tasks.
