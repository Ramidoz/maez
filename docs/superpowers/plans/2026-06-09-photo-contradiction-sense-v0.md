# Photo Contradiction Sense v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Maez a local, claim-level contradiction sense for owner-sent photo replies, folded into focused synthesis as proprioceptive pressure rather than a censor.

**Architecture:** Add a small core organ, `core.routing.photo_contradiction`, that owns deterministic claim extraction, the swappable verifier contract, lazy local NLI loading, claim-level checking, and contradiction receipts. Wire it into `core.routing.focused_cognition.synthesize_photo_turn` behind `MAEZ_PHOTO_CONTRADICTION_SENSE=1`; flag-off behavior stays byte-equivalent. Extend the daemon's existing `photo_focused_synthesis` telemetry with the new contradiction receipt fields.

**Tech Stack:** Python stdlib dataclasses/re/unittest, existing focused-cognition path, optional lazy `transformers.pipeline` only inside the enabled local NLI verifier, local `models/bakeoff/nli/bakeoff_manifest.json`.

---

## File Structure

- Create `core/routing/photo_contradiction.py`
  - Deterministic claim extractor.
  - `PhotoClaim`, `ClaimVerdict`, `ContradictionReceipt` dataclasses.
  - `ContradictionVerifier` protocol-shaped base.
  - `LocalNLIContradictionVerifier` lazy local artifact wrapper.
  - `check_photo_contradictions(...)` orchestration helper.
  - Feature flag helper and single-photo detector.
- Modify `core/routing/focused_cognition.py`
  - Add contradiction receipt fields to `FocusedResult`.
  - Call the contradiction organ from `synthesize_photo_turn` only when enabled.
  - Add one revision pass plus one mandatory re-check.
  - Skip when Lane 1 deterministic fallback is already used.
- Modify `daemon/maez_daemon.py`
  - Extend the existing `photo_focused_synthesis` log with content-free contradiction telemetry.
- Add tests:
  - `tests/test_photo_contradiction.py` for extractor, verifier contract, receipt aggregation, lazy/local-only behavior.
  - Extend `tests/test_photo_focused_synthesis.py` for integration and revision/re-check behavior.
  - Extend `tests/test_photo_focused_routing.py` for telemetry field presence.

## Implementation Notes

- v0 is single-photo only. If the photo analysis contains multiple image sections, skip the sense and log `multi_photo_unsupported`.
- The claim extractor is deterministic and draft-bound. No model call. Extracted claim text must be a normalized substring of the draft reply.
- Good path overhead is deterministic extraction plus at most 5 NLI calls. If more direct perceptual claims are present, check only the first 5 and set `claim_limit_exceeded=True`.
- `revised_clear` is impossible unless the revised reply is re-extracted and re-checked clear.
- The local NLI artifact must lazy-load only after the feature flag is on and a check is requested. Importing `core.routing.photo_contradiction` must not import `transformers`.
- Before editing `synthesize_photo_turn`, re-open the live function and adapt to its actual local helper names. At plan time those names are verified as `_run`, `base_system`, and `_valid_photo_citation`; the executor must not assume they stayed unchanged.
- Current Lane 1 behavior is verified: if the first photo-focused brain call returns empty, it goes straight to `deterministic_fallback` without a citation retry.

---

### Task 1: Deterministic Claim Extractor

**Files:**
- Create: `core/routing/photo_contradiction.py`
- Test: `tests/test_photo_contradiction.py`

- [ ] **Step 1: Write failing extractor tests**

Create `tests/test_photo_contradiction.py` with:

```python
import unittest

from core.routing.photo_contradiction import (
    PhotoClaim,
    extract_photo_claims,
    normalize_claim_text,
)


class PhotoClaimExtraction(unittest.TestCase):
    def test_extracts_direct_perceptual_sentences(self):
        reply = (
            "The screenshot title says WWDC 2026 [E1]. "
            "The chart lists Q4_0 as 2.9 GB [E1]. "
            "This matters for what we are building."
        )
        claims = extract_photo_claims(reply)
        self.assertEqual(
            [c.text for c in claims],
            [
                "The screenshot title says WWDC 2026.",
                "The chart lists Q4_0 as 2.9 GB.",
            ],
        )
        self.assertTrue(all(c.direct_perceptual for c in claims))
        self.assertEqual([c.claim_id for c in claims], ["C1", "C2"])
        self.assertEqual([c.evidence_label for c in claims], ["E1", "E1"])

    def test_excludes_interpretive_advice_and_project_meaning(self):
        reply = (
            "This matters for Maez's roadmap [E1]. "
            "You may want to test it later. "
            "I would treat this as promising."
        )
        self.assertEqual(extract_photo_claims(reply), [])

    def test_claims_are_draft_bound_no_generated_paraphrase(self):
        reply = "The image shows a Reddit screenshot [E1]."
        claims = extract_photo_claims(reply)
        self.assertEqual(len(claims), 1)
        normalized_reply = normalize_claim_text(reply)
        self.assertIn(normalize_claim_text(claims[0].text), normalized_reply)

    def test_mixed_claim_keeps_sentence_or_skips_never_invents_smaller_claim(self):
        reply = "The image shows WWDC 2026, which is a developer conference [E1]."
        claims = extract_photo_claims(reply)
        self.assertEqual(len(claims), 1)
        self.assertEqual(
            claims[0].text,
            "The image shows WWDC 2026, which is a developer conference.",
        )

    def test_ambiguous_sentence_is_omitted_not_false_demoted(self):
        reply = "It seems important and probably relates to the current work [E1]."
        self.assertEqual(extract_photo_claims(reply), [])

    def test_claim_cap_returns_first_five_and_reports_limit(self):
        reply = " ".join(
            f"The screenshot lists item {i} [E1]." for i in range(1, 8)
        )
        claims = extract_photo_claims(reply, limit=5)
        self.assertEqual(len(claims), 5)
        self.assertEqual(claims[-1].text, "The screenshot lists item 5.")
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_contradiction
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.routing.photo_contradiction'`.

- [ ] **Step 3: Implement extractor**

Create `core/routing/photo_contradiction.py`:

```python
"""Local photo-contradiction sense helpers.

This module is intentionally light at import time. Heavy model libraries are
imported only inside the enabled verifier load path.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import time
from pathlib import Path
from typing import Protocol


_CITE_RE = re.compile(r"\[E\d+\]")
_SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")
_SPACE_RE = re.compile(r"\s+")
_PHOTO_VERBS_RE = re.compile(
    r"\b("
    r"(?:image|photo|picture|screenshot|chart|table|text|title|page|screen)"
    r"\s+(?:shows|says|contains|depicts|lists|names|displays|reads|includes)"
    r"|(?:shows|says|contains|depicts|lists|names|displays|reads|includes)"
    r")\b",
    re.IGNORECASE,
)
_NON_PERCEPTUAL_RE = re.compile(
    r"\b("
    r"matters|roadmap|promising|should|could|would|may want|recommend|"
    r"probably|seems|appears important|means for|suggests we|test later"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PhotoClaim:
    claim_id: str
    text: str
    direct_perceptual: bool
    evidence_label: str = "E1"


def normalize_claim_text(text: str) -> str:
    text = _CITE_RE.sub("", text or "")
    text = _SPACE_RE.sub(" ", text).strip()
    text = re.sub(r"\s+([.!?]+)", r"\1", text)
    return text


def _clean_sentence(text: str) -> str:
    cleaned = normalize_claim_text(text)
    return cleaned.strip(" \t\r\n")


def _is_direct_perceptual(sentence: str) -> bool:
    if not sentence:
        return False
    if _NON_PERCEPTUAL_RE.search(sentence):
        return False
    return bool(_PHOTO_VERBS_RE.search(sentence))


def extract_photo_claims(
    reply: str,
    *,
    evidence_label: str = "E1",
    limit: int = 5,
) -> list[PhotoClaim]:
    claims: list[PhotoClaim] = []
    normalized_reply = normalize_claim_text(reply)
    for match in _SENTENCE_RE.finditer(reply or ""):
        sentence = _clean_sentence(match.group(0))
        if not sentence:
            continue
        # Draft-bound anti-fabrication guard: the extracted claim must still be
        # present in the draft after normalization. No generated paraphrases.
        if normalize_claim_text(sentence) not in normalized_reply:
            continue
        if not _is_direct_perceptual(sentence):
            continue
        claims.append(
            PhotoClaim(
                claim_id=f"C{len(claims) + 1}",
                text=sentence,
                direct_perceptual=True,
                evidence_label=evidence_label,
            )
        )
        if len(claims) >= limit:
            break
    return claims
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_contradiction
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/routing/photo_contradiction.py tests/test_photo_contradiction.py
git commit -m "feat(photo): add deterministic contradiction claim extractor"
```

---

### Task 2: Local Verifier Contract And Lazy NLI Wrapper

**Files:**
- Modify: `core/routing/photo_contradiction.py`
- Modify: `scripts/photo_judge_bakeoff_adapters.py`
- Test: `tests/test_photo_contradiction.py`
- Test: `tests/test_photo_judge_bakeoff.py`

- [ ] **Step 1: Add failing verifier tests**

Append to `tests/test_photo_contradiction.py`:

```python
import subprocess
import sys
from unittest import mock


class LocalVerifierContract(unittest.TestCase):
    def test_importing_module_in_clean_process_does_not_import_transformers(self):
        code = (
            "import sys; "
            "import core.routing.photo_contradiction; "
            "print('transformers' in sys.modules)"
        )
        out = subprocess.check_output([sys.executable, "-c", code], text=True).strip()
        self.assertEqual(out, "False")

    def test_module_contains_no_network_client_imports(self):
        from pathlib import Path
        src = Path("core/routing/photo_contradiction.py").read_text(encoding="utf-8")
        for forbidden in ("requests", "huggingface_hub", "urllib.request"):
            self.assertNotIn(forbidden, src)

    def test_missing_nli_artifact_is_unavailable_without_model_import(self):
        from core.routing.photo_contradiction import LocalNLIContradictionVerifier

        with mock.patch(
            "core.routing.photo_contradiction._load_transformers_pipeline",
            side_effect=AssertionError("must not import"),
        ):
            verifier = LocalNLIContradictionVerifier(
                artifact_dir="/tmp/definitely-missing-maez-nli"
            )
            verdict = verifier.predict("premise", "hypothesis")
        self.assertEqual(verdict.label, "unavailable")
        self.assertIn("missing", verdict.reason)

    def test_manifest_repo_mismatch_is_unavailable(self):
        import json
        import tempfile
        from pathlib import Path
        from core.routing.photo_contradiction import LocalNLIContradictionVerifier

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "bakeoff_manifest.json").write_text(
                json.dumps({
                    "repo_id": "owner/wrong",
                    "revision": "abc",
                    "sha256": "f00",
                }),
                encoding="utf-8",
            )
            verifier = LocalNLIContradictionVerifier(artifact_dir=str(d))
            verdict = verifier.predict("premise", "hypothesis")
        self.assertEqual(verdict.label, "unavailable")
        self.assertIn("repo_id", verdict.reason)

    def test_nli_maps_contradiction_probability_to_label(self):
        from core.routing.photo_contradiction import LocalNLIContradictionVerifier

        class FakePipeline:
            def __call__(self, pair):
                self.pair = pair
                return [[
                    {"label": "contradiction", "score": 0.91},
                    {"label": "neutral", "score": 0.05},
                    {"label": "entailment", "score": 0.04},
                ]]

        with mock.patch(
            "core.routing.photo_contradiction._load_transformers_pipeline",
            return_value=FakePipeline(),
        ), mock.patch(
            "core.routing.photo_contradiction._read_manifest",
            return_value={
                "repo_id": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
                "revision": "abc",
                "sha256": "deadbeef",
            },
        ), mock.patch(
            "core.routing.photo_contradiction.Path.is_dir",
            return_value=True,
        ):
            verifier = LocalNLIContradictionVerifier(
                artifact_dir="/tmp/pretend-nli",
                threshold=0.5,
            )
            verdict = verifier.predict("The image says 2026.", "The image says 2024.")
        self.assertEqual(verdict.label, "contradicts")
        self.assertLess(verdict.score, 0.5)
        self.assertEqual(verdict.model_id, "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
        self.assertEqual(verdict.revision, "abc")
        self.assertEqual(verdict.sha256, "deadbeef")
        self.assertGreaterEqual(verdict.latency_s, 0.0)

    def test_nli_score_helper_handles_label_aliases(self):
        from core.routing.photo_contradiction import nli_grounded_score_from_output

        self.assertAlmostEqual(
            nli_grounded_score_from_output([
                {"label": "LABEL_0", "score": 0.91},
                {"label": "LABEL_1", "score": 0.04},
                {"label": "LABEL_2", "score": 0.05},
            ]),
            0.09,
        )
        self.assertAlmostEqual(
            nli_grounded_score_from_output([
                {"label": "contradiction", "score": 0.7},
                {"label": "neutral", "score": 0.2},
                {"label": "entailment", "score": 0.1},
            ]),
            0.3,
        )

    def test_nli_score_helper_fails_closed_on_unknown_labels(self):
        from core.routing.photo_contradiction import nli_grounded_score_from_output

        with self.assertRaises(ValueError):
            nli_grounded_score_from_output([
                {"label": "mystery", "score": 0.9},
            ])


class BakeoffNLIReusesCoreMapping(unittest.TestCase):
    def test_bakeoff_nli_adapter_imports_core_score_helper(self):
        from pathlib import Path
        src = Path("scripts/photo_judge_bakeoff_adapters.py").read_text(encoding="utf-8")
        self.assertIn("nli_grounded_score_from_output", src)
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_contradiction
```

Expected: FAIL with missing `LocalNLIContradictionVerifier`, `ClaimVerdict`, and `nli_grounded_score_from_output`.

- [ ] **Step 3: Implement verifier types and lazy loader**

Extend `core/routing/photo_contradiction.py`:

```python
import json


NLI_MODEL_ID = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
DEFAULT_NLI_ARTIFACT_DIR = (
    Path(__file__).resolve().parents[2] / "models" / "bakeoff" / "nli"
)


@dataclass(frozen=True)
class ClaimVerdict:
    label: str  # "grounded" | "contradicts" | "unavailable"
    score: float | None
    latency_s: float
    model_id: str | None = None
    revision: str | None = None
    sha256: str | None = None
    reason: str | None = None


class ContradictionVerifier(Protocol):
    def predict(self, premise: str, hypothesis: str) -> ClaimVerdict:
        ...


def _flatten_pipeline_output(output):
    if output and isinstance(output[0], list):
        return output[0]
    return output


def nli_grounded_score_from_output(output) -> float:
    rows = _flatten_pipeline_output(output)
    probs = {str(d["label"]).lower(): float(d["score"]) for d in rows}
    contradiction = None
    for label in ("contradiction", "contradictory", "label_0"):
        if label in probs:
            contradiction = probs[label]
            break
    if contradiction is None:
        raise ValueError(f"NLI output lacks contradiction label: {sorted(probs)}")
    return 1.0 - float(contradiction)


def _read_manifest(artifact_dir: Path) -> dict | None:
    try:
        with (artifact_dir / "bakeoff_manifest.json").open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _load_transformers_pipeline(artifact_dir: Path):
    from transformers import pipeline

    previous = os.environ.get("TRANSFORMERS_OFFLINE")
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        return pipeline(
            "text-classification",
            model=str(artifact_dir),
            tokenizer=str(artifact_dir),
            top_k=None,
            model_kwargs={"local_files_only": True},
        )
    finally:
        if previous is None:
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
        else:
            os.environ["TRANSFORMERS_OFFLINE"] = previous


class LocalNLIContradictionVerifier:
    def __init__(
        self,
        *,
        artifact_dir: str | os.PathLike[str] | None = None,
        threshold: float = 0.5,
    ) -> None:
        self.artifact_dir = Path(artifact_dir) if artifact_dir else DEFAULT_NLI_ARTIFACT_DIR
        self.threshold = threshold
        self._model = None
        self._load_failed_reason: str | None = None
        self.model_id = NLI_MODEL_ID
        self.revision: str | None = None
        self.sha256: str | None = None

    def _unavailable(self, reason: str, latency_s: float = 0.0) -> ClaimVerdict:
        return ClaimVerdict(
            label="unavailable",
            score=None,
            latency_s=latency_s,
            model_id=self.model_id,
            revision=self.revision,
            sha256=self.sha256,
            reason=reason,
        )

    def _ensure_loaded(self) -> str | None:
        if self._model is not None:
            return None
        if self._load_failed_reason:
            return self._load_failed_reason
        if not self.artifact_dir.is_dir():
            self._load_failed_reason = f"missing artifact: {self.artifact_dir}"
            return self._load_failed_reason
        manifest = _read_manifest(self.artifact_dir)
        if not manifest:
            self._load_failed_reason = (
                f"incomplete artifact: {self.artifact_dir} has no bakeoff_manifest.json"
            )
            return self._load_failed_reason
        manifest_repo = manifest.get("repo_id")
        if manifest_repo != self.model_id:
            self._load_failed_reason = (
                f"manifest repo_id {manifest_repo!r} != expected {self.model_id!r}"
            )
            return self._load_failed_reason
        self.revision = manifest.get("revision")
        self.sha256 = manifest.get("sha256")
        try:
            self._model = _load_transformers_pipeline(self.artifact_dir)
        except Exception as exc:
            self._load_failed_reason = f"{type(exc).__name__}: {exc}"
            return self._load_failed_reason
        return None

    def predict(self, premise: str, hypothesis: str) -> ClaimVerdict:
        t0 = time.perf_counter()
        unavailable = self._ensure_loaded()
        if unavailable:
            return self._unavailable(unavailable, time.perf_counter() - t0)
        try:
            out = self._model({"text": premise, "text_pair": hypothesis})
            grounded_score = nli_grounded_score_from_output(out)
            label = "grounded" if grounded_score >= self.threshold else "contradicts"
            return ClaimVerdict(
                label=label,
                score=grounded_score,
                latency_s=time.perf_counter() - t0,
                model_id=self.model_id,
                revision=self.revision,
                sha256=self.sha256,
            )
        except Exception as exc:
            return self._unavailable(
                f"predict: {type(exc).__name__}: {exc}",
                time.perf_counter() - t0,
            )
```

Modify `scripts/photo_judge_bakeoff_adapters.py:NLIAdapter._raw_predict` so the bakeoff reuses the same score helper:

```python
    def _raw_predict(self, premise, hypothesis):
        from core.routing.photo_contradiction import nli_grounded_score_from_output

        out = self._model({"text": premise, "text_pair": hypothesis})
        return nli_grounded_score_from_output(out)
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_contradiction tests.test_photo_judge_bakeoff
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/routing/photo_contradiction.py scripts/photo_judge_bakeoff_adapters.py tests/test_photo_contradiction.py tests/test_photo_judge_bakeoff.py
git commit -m "feat(photo): add lazy local contradiction verifier"
```

---

### Task 3: Receipt Aggregation, Single-Photo Scope, And Feature Flag

**Files:**
- Modify: `core/routing/photo_contradiction.py`
- Test: `tests/test_photo_contradiction.py`

- [ ] **Step 1: Add failing receipt orchestration tests**

Append to `tests/test_photo_contradiction.py`:

```python
from core.routing.photo_contradiction import ClaimVerdict


class FakeVerifier:
    def __init__(self, labels):
        self.labels = list(labels)
        self.calls = []

    def predict(self, premise, hypothesis):
        self.calls.append((premise, hypothesis))
        label = self.labels.pop(0)
        return ClaimVerdict(
            label=label,
            score=0.1 if label == "contradicts" else 0.9,
            latency_s=0.01,
            model_id="fake-nli",
            revision="rev",
            sha256="sha",
        )


class ContradictionReceiptAggregation(unittest.TestCase):
    PREMISE = "The screenshot title says WWDC 2026."

    def test_clear_receipt_for_grounded_claims(self):
        from core.routing.photo_contradiction import check_photo_contradictions
        verifier = FakeVerifier(["grounded"])
        receipt = check_photo_contradictions(
            premise=self.PREMISE,
            reply="The screenshot title says WWDC 2026 [E1].",
            verifier=verifier,
        )
        self.assertEqual(receipt.reason, "clear")
        self.assertEqual(receipt.claim_count, 1)
        self.assertEqual(receipt.contradiction_count, 0)
        self.assertEqual(verifier.calls[0][1], "The screenshot title says WWDC 2026.")

    def test_trust_demoted_for_direct_photo_contradiction(self):
        from core.routing.photo_contradiction import check_photo_contradictions
        receipt = check_photo_contradictions(
            premise=self.PREMISE,
            reply="The screenshot title says WWDC 2024 [E1].",
            verifier=FakeVerifier(["contradicts"]),
        )
        self.assertEqual(receipt.reason, "trust_demoted")
        self.assertEqual(receipt.contradiction_count, 1)
        self.assertIn("C1", receipt.contradicted_claim_ids)
        self.assertIn("Contradiction sense fired", receipt.sense_note)
        self.assertIn("WWDC 2024", receipt.sense_note)

    def test_non_perceptual_reply_is_claim_extraction_unavailable(self):
        from core.routing.photo_contradiction import check_photo_contradictions
        verifier = FakeVerifier(["contradicts"])
        receipt = check_photo_contradictions(
            premise=self.PREMISE,
            reply="This matters for the roadmap [E1].",
            verifier=verifier,
        )
        self.assertEqual(receipt.reason, "claim_extraction_unavailable")
        self.assertEqual(verifier.calls, [])

    def test_multi_photo_analysis_is_unsupported(self):
        from core.routing.photo_contradiction import check_photo_contradictions
        premise = "Image 1: a chart. Image 2: a screenshot."
        receipt = check_photo_contradictions(
            premise=premise,
            reply="The screenshot shows a chart [E1].",
            verifier=FakeVerifier(["grounded"]),
        )
        self.assertEqual(receipt.reason, "multi_photo_unsupported")

    def test_claim_limit_is_honestly_reported(self):
        from core.routing.photo_contradiction import check_photo_contradictions
        reply = " ".join(
            f"The screenshot lists item {i} [E1]." for i in range(1, 8)
        )
        verifier = FakeVerifier(["grounded"] * 5)
        receipt = check_photo_contradictions(
            premise="The screenshot lists items 1 through 7.",
            reply=reply,
            verifier=verifier,
            claim_limit=5,
        )
        self.assertEqual(receipt.reason, "clear")
        self.assertEqual(receipt.claim_count, 5)
        self.assertTrue(receipt.claim_limit_exceeded)
        self.assertEqual(len(verifier.calls), 5)

    def test_feature_flag_defaults_off(self):
        from core.routing.photo_contradiction import photo_contradiction_sense_enabled
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(photo_contradiction_sense_enabled())
        with mock.patch.dict("os.environ", {"MAEZ_PHOTO_CONTRADICTION_SENSE": "1"}):
            self.assertTrue(photo_contradiction_sense_enabled())
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_contradiction
```

Expected: FAIL with missing `check_photo_contradictions`, `ContradictionReceipt`, and `photo_contradiction_sense_enabled`.

- [ ] **Step 3: Implement receipt aggregation**

Extend `core/routing/photo_contradiction.py`:

```python
@dataclass(frozen=True)
class ContradictionReceipt:
    reason: str
    claim_count: int = 0
    contradiction_count: int = 0
    contradicted_claim_ids: tuple[str, ...] = ()
    sense_note: str | None = None
    verifier_name: str | None = None
    model_id: str | None = None
    revision: str | None = None
    sha256: str | None = None
    latency_ms: int = 0
    claim_limit_exceeded: bool = False


def photo_contradiction_sense_enabled() -> bool:
    value = os.environ.get("MAEZ_PHOTO_CONTRADICTION_SENSE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _looks_multi_photo(premise: str) -> bool:
    return len(re.findall(r"\bImage\s+\d+\s*:", premise or "", re.IGNORECASE)) > 1


def _count_potential_claims(reply: str) -> int:
    return len(extract_photo_claims(reply, limit=10_000))


def _build_sense_note(premise: str, contradictions: list[tuple[PhotoClaim, ClaimVerdict]]) -> str:
    lines = ["Contradiction sense fired:"]
    for claim, _verdict in contradictions:
        lines.append(f'- Claim {claim.claim_id}: "{claim.text}"')
    clipped = normalize_claim_text(premise)
    if len(clipped) > 500:
        clipped = clipped[:497].rstrip() + "..."
    lines.append(f"- Conflicts with E1: {clipped}")
    lines.append(
        "Revise the answer with this signal in view. Do not claim certainty "
        "where the photo evidence and draft conflict."
    )
    return "\n".join(lines)


def check_photo_contradictions(
    *,
    premise: str,
    reply: str,
    verifier: ContradictionVerifier,
    claim_limit: int = 5,
) -> ContradictionReceipt:
    t0 = time.perf_counter()
    if _looks_multi_photo(premise):
        return ContradictionReceipt(reason="multi_photo_unsupported")

    total_possible = _count_potential_claims(reply)
    claims = extract_photo_claims(reply, limit=claim_limit)
    if not claims:
        return ContradictionReceipt(reason="claim_extraction_unavailable")

    contradictions: list[tuple[PhotoClaim, ClaimVerdict]] = []
    first_verdict: ClaimVerdict | None = None
    unavailable = False
    for claim in claims:
        verdict = verifier.predict(premise, claim.text)
        if first_verdict is None:
            first_verdict = verdict
        if verdict.label == "contradicts":
            contradictions.append((claim, verdict))
        elif verdict.label == "unavailable":
            unavailable = True

    latency_ms = int((time.perf_counter() - t0) * 1000)
    claim_limit_exceeded = total_possible > len(claims)
    if contradictions:
        return ContradictionReceipt(
            reason="trust_demoted",
            claim_count=len(claims),
            contradiction_count=len(contradictions),
            contradicted_claim_ids=tuple(c.claim_id for c, _v in contradictions),
            sense_note=_build_sense_note(premise, contradictions),
            verifier_name=type(verifier).__name__,
            model_id=getattr(first_verdict, "model_id", None),
            revision=getattr(first_verdict, "revision", None),
            sha256=getattr(first_verdict, "sha256", None),
            latency_ms=latency_ms,
            claim_limit_exceeded=claim_limit_exceeded,
        )
    if unavailable:
        return ContradictionReceipt(
            reason="verifier_unavailable",
            claim_count=len(claims),
            verifier_name=type(verifier).__name__,
            model_id=getattr(first_verdict, "model_id", None),
            revision=getattr(first_verdict, "revision", None),
            sha256=getattr(first_verdict, "sha256", None),
            latency_ms=latency_ms,
            claim_limit_exceeded=claim_limit_exceeded,
        )
    return ContradictionReceipt(
        reason="clear",
        claim_count=len(claims),
        verifier_name=type(verifier).__name__,
        model_id=getattr(first_verdict, "model_id", None),
        revision=getattr(first_verdict, "revision", None),
        sha256=getattr(first_verdict, "sha256", None),
        latency_ms=latency_ms,
        claim_limit_exceeded=claim_limit_exceeded,
    )
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_contradiction
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/routing/photo_contradiction.py tests/test_photo_contradiction.py
git commit -m "feat(photo): aggregate contradiction receipts"
```

---

### Task 4: FocusedResult Fields And Flag-Off Invariance

**Files:**
- Modify: `core/routing/focused_cognition.py`
- Test: `tests/test_photo_focused_synthesis.py`

- [ ] **Step 1: Write failing field and flag-off tests**

Append to `tests/test_photo_focused_synthesis.py`:

```python
class PhotoContradictionSenseFields(unittest.TestCase):
    def test_focused_result_has_contradiction_receipt_defaults(self):
        r = FocusedResult(reply="x", cited_ids=["E1"], working_set_chars=1)
        self.assertIsNone(r.contradiction_receipt)
        self.assertEqual(r.contradiction_claim_count, 0)
        self.assertEqual(r.contradiction_count, 0)
        self.assertFalse(r.contradiction_claim_limit_exceeded)

    def test_flag_off_does_not_import_or_call_contradiction_checker(self):
        chat, box = _scripted_chat(["The screenshot shows Reddit [E1]."])
        with mock.patch.dict("os.environ", {}, clear=True), mock.patch(
            "core.routing.photo_contradiction.check_photo_contradictions",
            side_effect=AssertionError("must not run when flag off"),
        ):
            r = synthesize_photo_turn(
                analysis_text=ANALYSIS,
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat,
                model="m",
            )
        self.assertEqual(r.receipt_reason, "cited_ok")
        self.assertIsNone(r.contradiction_receipt)
        self.assertEqual(box["i"], 1)
```

Add `from unittest import mock` near the imports if not already present.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_focused_synthesis
```

Expected: FAIL because `FocusedResult` lacks contradiction fields.

- [ ] **Step 3: Add FocusedResult fields and lazy flag check**

Modify `core/routing/focused_cognition.py`:

```python
@dataclass(frozen=True)
class FocusedResult:
    reply: str
    cited_ids: list[str]
    working_set_chars: int
    prompt_build_ms: int | None = None
    chat_total_ms: int | None = None
    reply_token_est: int | None = None
    receipt_reason: str | None = None
    contradiction_receipt: str | None = None
    contradiction_claim_count: int = 0
    contradiction_count: int = 0
    contradiction_latency_ms: int | None = None
    contradiction_model_id: str | None = None
    contradiction_revision: str | None = None
    contradiction_sha256: str | None = None
    contradiction_claim_limit_exceeded: bool = False
```

Inside `synthesize_photo_turn`, after `cited_ids = ...` and before returning, add local defaults:

```python
    contradiction_receipt = None
    contradiction_claim_count = 0
    contradiction_count = 0
    contradiction_latency_ms = None
    contradiction_model_id = None
    contradiction_revision = None
    contradiction_sha256 = None
    contradiction_claim_limit_exceeded = False
```

Return those fields in `FocusedResult`. Do not run the checker yet; this task only makes the defaults and proves flag-off stays inert.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_focused_synthesis
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_photo_focused_synthesis.py
git commit -m "feat(photo): add contradiction receipt fields"
```

---

### Task 5: Integrate Contradiction Sense, Revision, And Mandatory Re-check

**Files:**
- Modify: `core/routing/focused_cognition.py`
- Modify: `core/routing/photo_contradiction.py` if a helper is needed
- Test: `tests/test_photo_focused_synthesis.py`

- [ ] **Step 1: Add failing integration tests**

Append to `tests/test_photo_focused_synthesis.py`:

```python
class FakeContradictionReceipt:
    def __init__(
        self,
        reason,
        *,
        sense_note=None,
        claim_count=1,
        contradiction_count=0,
        latency_ms=11,
        claim_limit_exceeded=False,
    ):
        self.reason = reason
        self.sense_note = sense_note
        self.claim_count = claim_count
        self.contradiction_count = contradiction_count
        self.latency_ms = latency_ms
        self.model_id = "fake-nli"
        self.revision = "rev"
        self.sha256 = "sha"
        self.claim_limit_exceeded = claim_limit_exceeded


class PhotoContradictionSenseIntegration(unittest.TestCase):
    def test_clear_receipt_no_revision(self):
        chat, box = _scripted_chat(["The screenshot shows Reddit [E1]."])
        with mock.patch.dict("os.environ", {"MAEZ_PHOTO_CONTRADICTION_SENSE": "1"}), \
             mock.patch(
                 "core.routing.photo_contradiction.check_photo_contradictions",
                 return_value=FakeContradictionReceipt("clear", claim_count=1),
             ) as check:
            r = synthesize_photo_turn(
                analysis_text=ANALYSIS,
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat,
                model="m",
            )
        self.assertEqual(r.contradiction_receipt, "clear")
        self.assertEqual(r.contradiction_claim_count, 1)
        self.assertEqual(r.contradiction_count, 0)
        self.assertEqual(box["i"], 1)
        self.assertEqual(check.call_count, 1)

    def test_contradiction_adds_sense_note_revision_and_recheck(self):
        chat, box = _scripted_chat([
            "The screenshot title says WWDC2024 [E1].",
            "The screenshot title says WWDC 2026 [E1].",
        ])
        receipts = [
            FakeContradictionReceipt(
                "trust_demoted",
                sense_note="Contradiction sense fired:\n- Claim C1",
                contradiction_count=1,
            ),
            FakeContradictionReceipt("clear", claim_count=1),
        ]

        def fake_check(**_kwargs):
            return receipts.pop(0)

        with mock.patch.dict("os.environ", {"MAEZ_PHOTO_CONTRADICTION_SENSE": "1"}), \
             mock.patch("core.routing.photo_contradiction.check_photo_contradictions",
                        side_effect=fake_check):
            r = synthesize_photo_turn(
                analysis_text="The screenshot title says WWDC 2026.",
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat,
                model="m",
            )
        self.assertEqual(r.reply, "The screenshot title says WWDC 2026 [E1].")
        self.assertEqual(r.contradiction_receipt, "revised_clear")
        self.assertEqual(box["i"], 2)

    def test_revision_still_contradicts_is_not_laundered_clear(self):
        chat, box = _scripted_chat([
            "The screenshot title says WWDC2024 [E1].",
            "It still says WWDC2024 [E1].",
        ])
        receipts = [
            FakeContradictionReceipt(
                "trust_demoted",
                sense_note="Contradiction sense fired:\n- Claim C1",
                contradiction_count=1,
            ),
            FakeContradictionReceipt(
                "trust_demoted",
                sense_note="Contradiction sense fired:\n- Claim C1",
                contradiction_count=1,
            ),
        ]
        with mock.patch.dict("os.environ", {"MAEZ_PHOTO_CONTRADICTION_SENSE": "1"}), \
             mock.patch("core.routing.photo_contradiction.check_photo_contradictions",
                        side_effect=lambda **_k: receipts.pop(0)):
            r = synthesize_photo_turn(
                analysis_text="The screenshot title says WWDC 2026.",
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat,
                model="m",
            )
        self.assertEqual(r.reply, "It still says WWDC2024 [E1].")
        self.assertEqual(r.contradiction_receipt, "trust_demoted")
        self.assertEqual(box["i"], 2)

    def test_deterministic_fallback_skips_contradiction_nli(self):
        chat, box = _scripted_chat(["", "unused"])
        with mock.patch.dict("os.environ", {"MAEZ_PHOTO_CONTRADICTION_SENSE": "1"}), \
             mock.patch(
                 "core.routing.photo_contradiction.check_photo_contradictions",
                 side_effect=AssertionError("deterministic fallback should skip"),
             ):
            r = synthesize_photo_turn(
                analysis_text=ANALYSIS,
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat,
                model="m",
            )
        self.assertEqual(r.receipt_reason, "deterministic_fallback")
        self.assertIsNone(r.contradiction_receipt)
        self.assertEqual(box["i"], 1)

    def test_revision_failure_keeps_original_reply_trust_demoted(self):
        calls = {"i": 0}
        def chat_fn(**_kwargs):
            calls["i"] += 1
            if calls["i"] == 1:
                return SimpleNamespace(
                    message=SimpleNamespace(
                        content="The screenshot title says WWDC2024 [E1]."
                    )
                )
            raise RuntimeError("revision down")

        with mock.patch.dict("os.environ", {"MAEZ_PHOTO_CONTRADICTION_SENSE": "1"}), \
             mock.patch(
                 "core.routing.photo_contradiction.check_photo_contradictions",
                 return_value=FakeContradictionReceipt(
                     "trust_demoted",
                     sense_note="Contradiction sense fired:\n- Claim C1",
                     contradiction_count=1,
                 ),
             ):
            r = synthesize_photo_turn(
                analysis_text="The screenshot title says WWDC 2026.",
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat_fn,
                model="m",
            )
        self.assertEqual(r.reply, "The screenshot title says WWDC2024 [E1].")
        self.assertEqual(r.contradiction_receipt, "retry_failed")
        self.assertEqual(calls["i"], 2)
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_focused_synthesis
```

Expected: FAIL because `synthesize_photo_turn` does not call the contradiction organ.

- [ ] **Step 3: Implement integration in `synthesize_photo_turn`**

In `core/routing/focused_cognition.py`, add the contradiction pass after Lane 1 citation rail sets `reply, receipt_reason`, and before `cited_ids` / return:

```python
    contradiction = None
    if receipt_reason != "deterministic_fallback":
        try:
            from core.routing import photo_contradiction as _photo_contradiction

            if _photo_contradiction.photo_contradiction_sense_enabled():
                verifier = _photo_contradiction.LocalNLIContradictionVerifier()
                contradiction = _photo_contradiction.check_photo_contradictions(
                    premise=analysis_text,
                    reply=reply,
                    verifier=verifier,
                )
                if contradiction.reason == "trust_demoted" and contradiction.sense_note:
                    try:
                        revision_raw = _run(
                            base_system
                            + "\n\n"
                            + contradiction.sense_note
                            + "\n\nRevise once. Keep every direct claim about the photo grounded in [E1]."
                        )
                    except Exception:
                        revision_raw = ""
                    if revision_raw and _valid_photo_citation(revision_raw):
                        revision_check = _photo_contradiction.check_photo_contradictions(
                            premise=analysis_text,
                            reply=revision_raw,
                            verifier=verifier,
                        )
                        reply = revision_raw
                        contradiction = revision_check
                        if revision_check.reason == "clear":
                            contradiction = replace(revision_check, reason="revised_clear")
                    else:
                        contradiction = replace(contradiction, reason="retry_failed")
        except Exception as exc:
            logger.warning(
                "photo contradiction sense failed: %s",
                type(exc).__name__,
            )
```

Add `replace` import if not already present; `focused_cognition.py` already imports `replace` from `dataclasses`, so reuse it.

After this block, copy the receipt values into the local return fields:

```python
    if contradiction is not None:
        contradiction_receipt = contradiction.reason
        contradiction_claim_count = contradiction.claim_count
        contradiction_count = contradiction.contradiction_count
        contradiction_latency_ms = contradiction.latency_ms
        contradiction_model_id = contradiction.model_id
        contradiction_revision = contradiction.revision
        contradiction_sha256 = contradiction.sha256
        contradiction_claim_limit_exceeded = contradiction.claim_limit_exceeded
```

Then include those values in the returned `FocusedResult`.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_focused_synthesis
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_photo_focused_synthesis.py
git commit -m "feat(photo): fold contradiction sense into synthesis" \
  -m "## Predicted effect

With MAEZ_PHOTO_CONTRADICTION_SENSE unset, owner-sent photo replies remain byte-equivalent to the current Lane 1 path. With the flag enabled and a local NLI artifact available, direct photo-perceptual contradictions trigger one proprioceptive revision and a contradiction receipt; revised_clear is emitted only after a re-check."
```

---

### Task 6: Daemon Telemetry

**Files:**
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_photo_focused_routing.py`

- [ ] **Step 1: Write failing structural telemetry test**

Append to `PhotoSynthesisLivesInsideThePipeline` in `tests/test_photo_focused_routing.py`:

```python
    def test_photo_log_carries_contradiction_receipt_fields(self):
        body = _handle_message_body()
        self.assertIn("contradiction_receipt=", body)
        self.assertIn("contradiction_claim_count=", body)
        self.assertIn("contradictions=", body)
        self.assertIn("contradiction_latency_ms=", body)
        self.assertIn("claim_limit_exceeded=", body)
        self.assertIn("contradiction_receipt", body)
        self.assertIn("contradiction_claim_count", body)
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_focused_routing.PhotoSynthesisLivesInsideThePipeline.test_photo_log_carries_contradiction_receipt_fields
```

Expected: FAIL because the log line does not include the new fields.

- [ ] **Step 3: Extend log line**

Modify the `photo_focused_synthesis` logger in `daemon/maez_daemon.py`:

```python
                    logger.info(
                        "photo_focused_synthesis surface=%s working_set_chars=%s "
                        "cited=%s reply_chars=%d receipt=%s turn_id=%s "
                        "contradiction_receipt=%s contradiction_claim_count=%s "
                        "contradictions=%s contradiction_latency_ms=%s "
                        "claim_limit_exceeded=%s",
                        source,
                        getattr(_photo_result, "working_set_chars", "?"),
                        len(getattr(_photo_result, "cited_ids", []) or []),
                        len(reply),
                        getattr(_photo_result, "receipt_reason", None),
                        _user_msg_turn_id,
                        getattr(_photo_result, "contradiction_receipt", None),
                        getattr(_photo_result, "contradiction_claim_count", 0),
                        getattr(_photo_result, "contradiction_count", 0),
                        getattr(_photo_result, "contradiction_latency_ms", None),
                        getattr(_photo_result, "contradiction_claim_limit_exceeded", False),
                    )
```

Do not log claim text, premise text, or raw photo pixels.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_photo_focused_routing
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_photo_focused_routing.py
git commit -m "feat(photo): log contradiction sense receipts" \
  -m "## Predicted effect

Photo-focused turns log contradiction_receipt, claim count, contradiction count, verifier latency, and claim-limit status without logging claim text or photo pixels. Non-photo turns and flag-off photo behavior are unchanged."
```

---

### Task 7: Protected Regression Sweep And Handoff

**Files:**
- Create: `docs/handoffs/2026-06-09-codex-photo-contradiction-sense-v0-for-review.md`
- No runtime code changes except fixes required by failing tests.

- [ ] **Step 1: Run focused suites**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_photo_contradiction \
  tests.test_photo_focused_synthesis \
  tests.test_photo_focused_routing \
  tests.test_chat_photo_wiring \
  tests.test_photo_judge_bakeoff
```

Expected: PASS.

- [ ] **Step 2: Run import/lazy-load guard**

Run:

```bash
/home/rohit/maez/.venv/bin/python - <<'PY'
import sys
import core.routing.photo_contradiction as pc
print("transformers_loaded", "transformers" in sys.modules)
print("flag_default", pc.photo_contradiction_sense_enabled())
PY
```

Expected:

```text
transformers_loaded False
flag_default False
```

- [ ] **Step 3: Run full discover floor**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Expected: no branch-only failures. If ambient failures appear, run the same command on clean main or compare against the current documented baseline before claiming zero regressions.

- [ ] **Step 4: Write Codex/Claude review handoff**

Create `docs/handoffs/2026-06-09-codex-photo-contradiction-sense-v0-for-review.md`:

```markdown
# Photo Contradiction Sense v0 - Review Handoff

Branch: `photo-contradiction-sense-v0`
Spec: `docs/superpowers/specs/2026-06-09-photo-contradiction-sense-v0-design.md`

## Boundary

This slice adds a dormant local contradiction sense for owner-sent photo replies.
It is gated by `MAEZ_PHOTO_CONTRADICTION_SENSE=1`. With the flag absent, photo
synthesis behavior should be unchanged and the local NLI artifact should not
load. No live daemon restart, service edit, model fetch, ledger write, or external
egress is part of this branch.

## Review Anchors

1. Claim extractor is deterministic, draft-bound, and conservative. No model
   extraction and no generated/paraphrased claims.
2. Verifier is claim-level only. Whole-reply NLI must not be called.
3. Live NLI and bakeoff NLI share the same score-mapping helper, including label
   aliases such as `LABEL_0`; no forked live-vs-witness mapping.
4. NLI is lazy and local-only. Importing the module must not import transformers;
   missing artifact means unavailable, never network.
5. Revision laundering is blocked. `revised_clear` requires one actual
   re-extract + re-check; no revision attempt can self-certify.
6. The floor is narrow. It fires only for direct photo-perceptual claims against
   the `E1` photo premise; multi-photo and deterministic fallback skip honestly.
7. No hard substitution in v0. Maez's voice revises with a contradiction sense
   note; the branch does not replace a whole cited-but-contradicts reply with a
   deterministic fallback.
8. Telemetry is content-free: receipt, counts, latency, fingerprint, turn id;
   no raw photo pixels or claim text in daemon logs.
9. No memory schema or ledger schema change.

## Verification

Paste the focused-suite output, lazy-load guard output, and full-discover floor
summary here before review.
```

- [ ] **Step 5: Commit**

```bash
git add docs/handoffs/2026-06-09-codex-photo-contradiction-sense-v0-for-review.md
git commit -m "docs(photo): hand off contradiction sense review"
```

- [ ] **Step 6: Stop for review**

Do not merge. Do not enable `MAEZ_PHOTO_CONTRADICTION_SENSE`. Do not fetch or wire model artifacts. Hand the branch to the full covenant review gate.

---

## Execution Recommendation

Use **Subagent-Driven** execution for this slice. It touches Maez's live speech path, model loading, and trust labeling; fresh task agents plus review checkpoints are worth the extra ceremony.

If executed inline, enforce the same boundaries manually:

- RED before GREEN for every task.
- Commit after each task.
- Stop at the handoff.
- Full 6-agent covenant review before merge.
- Owner-enabled witness after merge, artifact confirmation, flag enable, and restart.
