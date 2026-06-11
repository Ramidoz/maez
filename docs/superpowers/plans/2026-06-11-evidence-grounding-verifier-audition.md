# Evidence-Grounding Verifier Audition — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline scorecard answering whether a small CPU verifier (HHEM-2.1 / MiniCheck-DeBERTa) can perform the *claimable-entailment support check* — `(evidence, claim) → SUPPORTED/UNSUPPORTED` — that Maez currently lacks, measured on an obstacle course of dangerous grounding failures against a purpose-built 4B-entailment-adapter yardstick.

**Architecture:** A new `scripts/grounding_bench/` package: a hand-labeled `corpus.json` (claim-level, taxonomy-balanced, real-spine from longmemeval + flagged synthetic), three candidate adapters (HHEM local, MiniCheck local, 4B-adapter via the judge endpoint), a harness that mirrors `scripts/judge_bench/bench.py` with an **abstain precondition** and an HHEM **threshold sweep**, and a report whose **headline is per-mode false-negative rate**. v0 produces a scorecard only — **no live-daemon change**.

**Tech Stack:** Python 3.11+, `unittest`, `httpx` (already used by bench.py), `torch 2.12.0+cpu` + `transformers 5.10.2` (already installed). Runner: `/home/rohit/maez/.venv/bin/python -B -m unittest`. main local-only.

**Scope boundary (load-bearing):** entailment ONLY. The deterministic citation rail (`cited=0 ⇒ not grounded`) and the `forbidden`/`self_history` overclaim rail are UNTOUCHED; no-citation cases are EXCLUDED from the corpus. A winning verifier becomes a *new* layer in a **follow-on slice** — not in scope here.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `scripts/grounding_bench/corpus_schema.py` | Row schema constants (enums) + `validate_corpus(items)` |
| `scripts/grounding_bench/corpus.json` | The ~24–30 hand-labeled cases (data) |
| `scripts/grounding_bench/adapter_prompt.py` | The **reviewed** 4B-entailment-adapter system prompt (const) + `build_entailment_user_prompt` |
| `scripts/grounding_bench/verifiers.py` | `HhemVerifier`, `MinicheckVerifier`, `FourBAdapterVerifier` — each `.support(evidence, claim) → ("SUPPORTED"|"UNSUPPORTED", latency_s)` (HHEM also returns the raw score) |
| `scripts/grounding_bench/bench_grounding.py` | The harness: abstain precondition, candidate loop, HHEM threshold sweep, per-mode tally, CSV/MD report |
| `tests/test_grounding_bench.py` | All harness/adapter unit tests (mocked models) |
| `docs/handoffs/2026-06-11-grounding-audition-gate.md` | The STOP-at-gate handoff (label + prompt review + HHEM owner-download) |

**HHEM revision pin (used in Task 4):** before writing the adapter, resolve the current main-branch commit of `vectara/hallucination_evaluation_model` and pin it:
`HHEM_REVISION = "<full 40-char commit sha from https://huggingface.co/vectara/hallucination_evaluation_model/commits/main>"` — never load `trust_remote_code` off a moving `main`.

---

## Task 1: Corpus schema + validator

**Files:** Create `scripts/grounding_bench/corpus_schema.py`; Create `scripts/grounding_bench/corpus.json` (seed); Test `tests/test_grounding_bench.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_grounding_bench.py`:
```python
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(REPO / "scripts" / "grounding_bench"))

from corpus_schema import validate_corpus, MODES, EVIDENCE_KINDS, LABELS


class CorpusSchemaTests(unittest.TestCase):
    def _row(self, **over):
        base = dict(id="x-1", mode="grounded_positive", source="synthetic",
                    evidence_kind="claimable_present", evidence="E", claim="C",
                    expected="SUPPORTED", strict_rule=False, rationale="r")
        base.update(over)
        return base

    def test_valid_row_passes(self):
        validate_corpus([self._row()])  # should not raise

    def test_missing_field_raises(self):
        bad = self._row()
        del bad["rationale"]
        with self.assertRaises(ValueError):
            validate_corpus([bad])

    def test_bad_enum_raises(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(expected="MAYBE")])

    def test_claimable_absent_must_be_abstain(self):
        # an absent-evidence row that doesn't expect abstain is a labeling bug
        with self.assertRaises(ValueError):
            validate_corpus([self._row(evidence_kind="claimable_absent", expected="SUPPORTED")])

    def test_duplicate_ids_raise(self):
        with self.assertRaises(ValueError):
            validate_corpus([self._row(id="dup"), self._row(id="dup")])
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_bench -v`
Expected: FAIL — `ModuleNotFoundError: corpus_schema`.

- [ ] **Step 3: Implement the schema**

Create `scripts/grounding_bench/corpus_schema.py`:
```python
"""Schema + validator for the grounding audition corpus.

The corpus is DATA whose labels are covenant-critical; this validator
catches structural mistakes, the human label-review gate catches semantic ones.
"""
from __future__ import annotations

MODES = frozenset({
    "grounded_positive", "cited_but_unsupported", "fabricated_false_specific",
    "stale_over_current", "no_evidence_abstain", "multi_claim",
})
SOURCES = frozenset({"real-longmemeval", "synthetic"})
EVIDENCE_KINDS = frozenset({"claimable_present", "claimable_absent", "stale_vs_current"})
LABELS = frozenset({"SUPPORTED", "UNSUPPORTED", "ABSTAIN_EXPECTED"})
_REQUIRED = ("id", "mode", "source", "evidence_kind", "evidence", "claim",
             "expected", "strict_rule", "rationale")


def validate_corpus(items: list[dict]) -> None:
    """Raise ValueError on the first structural problem; return None if clean."""
    seen_ids: set[str] = set()
    for i, row in enumerate(items):
        for key in _REQUIRED:
            if key not in row:
                raise ValueError(f"row {i}: missing required field {key!r}")
        if row["mode"] not in MODES:
            raise ValueError(f"row {row['id']}: bad mode {row['mode']!r}")
        if row["source"] not in SOURCES:
            raise ValueError(f"row {row['id']}: bad source {row['source']!r}")
        if row["evidence_kind"] not in EVIDENCE_KINDS:
            raise ValueError(f"row {row['id']}: bad evidence_kind {row['evidence_kind']!r}")
        if row["expected"] not in LABELS:
            raise ValueError(f"row {row['id']}: bad expected {row['expected']!r}")
        if not isinstance(row["strict_rule"], bool):
            raise ValueError(f"row {row['id']}: strict_rule must be bool")
        # the load-bearing invariant: absent evidence <-> abstain expected
        if row["evidence_kind"] == "claimable_absent" and row["expected"] != "ABSTAIN_EXPECTED":
            raise ValueError(
                f"row {row['id']}: claimable_absent must expect ABSTAIN_EXPECTED")
        if row["evidence_kind"] != "claimable_absent" and row["expected"] == "ABSTAIN_EXPECTED":
            raise ValueError(
                f"row {row['id']}: ABSTAIN_EXPECTED only valid with claimable_absent")
        if not str(row["rationale"]).strip():
            raise ValueError(f"row {row['id']}: empty rationale (label must be reasoned)")
        if row["id"] in seen_ids:
            raise ValueError(f"duplicate id {row['id']!r}")
        seen_ids.add(row["id"])
```

Create a seed `scripts/grounding_bench/corpus.json` (Task 2 fills it out):
```json
{ "_notes": "Evidence-grounding audition corpus. Hand-labeled for GROUNDING (does the claim follow from the evidence?), NOT correctness. Claim-level unit. See 2026-06-11 spec.",
  "items": [
    { "id": "pos-1", "mode": "grounded_positive", "source": "synthetic",
      "evidence_kind": "claimable_present",
      "evidence": "The recall flip failed the latency gate at 5.8 to 12.3 seconds versus a 4.3 second ceiling.",
      "claim": "The recall flip was a No-Go because its latency exceeded the 4.3s ceiling.",
      "expected": "SUPPORTED", "strict_rule": false,
      "rationale": "Every part of the claim (No-Go, latency, the 4.3s ceiling) is stated in the evidence." }
  ] }
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_bench -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**
```bash
git add scripts/grounding_bench/corpus_schema.py scripts/grounding_bench/corpus.json tests/test_grounding_bench.py
git commit -m "feat(grounding-bench): corpus schema + validator + seed

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Author the full taxonomy-balanced corpus (DATA)

**Files:** Modify `scripts/grounding_bench/corpus.json`

This is a careful authoring task, not code. Fill `items` to ~24–30 rows, **balanced by failure mode** (not natural frequency):

| mode | expected | evidence_kind | n |
|------|----------|---------------|---|
| `grounded_positive` | SUPPORTED | claimable_present | 6–8 |
| `cited_but_unsupported` | UNSUPPORTED | claimable_present | 4–5 |
| `fabricated_false_specific` | UNSUPPORTED | claimable_present | 4–5 |
| `stale_over_current` | UNSUPPORTED | stale_vs_current | 4–5 |
| `no_evidence_abstain` | ABSTAIN_EXPECTED | claimable_absent | 3–4 |
| `multi_claim` | SUPPORTED or UNSUPPORTED | claimable_present | 2–3 (split into subclaims, or `strict_rule:true`) |

- [ ] **Step 1: Mine real evidence from longmemeval**

Read real `surfaced` evidence to use as the spine where it fits a mode:
```bash
/home/rohit/maez/.venv/bin/python -B -c "
import json
d=json.load(open('docs/eval/runs/longmemeval_judge30_2026-04-30.json'))
for c in d[:6]:
    print('---', c['question_id'], c['question_type'])
    print('EVIDENCE:', c['surfaced'][:300].replace(chr(10),' '))
    print('ANSWER  :', c['answer'])
"
```
Use these `surfaced` snippets as `evidence` and the `answer` (or a derived single claim) as `claim` for `source: "real-longmemeval"` rows. For a `cited_but_unsupported` or `stale_over_current` row, take real evidence and pair it with a claim that does NOT follow (mark `synthetic` if you altered the claim).

- [ ] **Step 2: Author the rows**

Compose each row per the schema. Authoring rules (hold these — they are the covenant of this corpus):
- **Claim is a single material claim.** For a multi-claim answer either split it into subclaim rows, or keep it whole with `strict_rule: true` and label UNSUPPORTED iff any material subclaim is unsupported.
- **`stale_over_current`:** `evidence` contains BOTH a stale value and the current/superseding value; the `claim` follows the stale one → UNSUPPORTED; `rationale` names which line supersedes.
- **`fabricated_false_specific`:** evidence is general/absent on a specific; the claim invents a precise specific (a date/number/name) not in the evidence → UNSUPPORTED (the WWDC pattern).
- **`no_evidence_abstain`:** `evidence` empty/whitespace, `evidence_kind: claimable_absent`, `expected: ABSTAIN_EXPECTED`.
- **Every row has a `rationale`** that an independent reviewer can check.
- **Flag `synthetic`** on every non-real-longmemeval row. Do NOT pad the real count by relabeling synthetic rows as real.

- [ ] **Step 3: Validate structurally**
```bash
/home/rohit/maez/.venv/bin/python -B -c "
import json,sys; sys.path.insert(0,'scripts/grounding_bench')
from corpus_schema import validate_corpus
items=json.load(open('scripts/grounding_bench/corpus.json'))['items']
validate_corpus(items)
from collections import Counter
print('n=',len(items),'modes=',dict(Counter(r['mode'] for r in items)))
print('labels=',dict(Counter(r['expected'] for r in items)))
print('sources=',dict(Counter(r['source'] for r in items)))
"
```
Expected: no ValueError; n in 24–30; each mode within its band; ABSTAIN rows present.

- [ ] **Step 4: Commit**
```bash
git add scripts/grounding_bench/corpus.json
git commit -m "feat(grounding-bench): full taxonomy-balanced corpus (real spine + flagged synthetic)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: The reviewed 4B-entailment-adapter prompt + call

**Files:** Create `scripts/grounding_bench/adapter_prompt.py`; Test `tests/test_grounding_bench.py`

The prompt is a **reviewed artifact** (it is the yardstick). Keep it isolated and named so review is easy.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_grounding_bench.py`:
```python
from adapter_prompt import ENTAILMENT_SYSTEM_PROMPT, build_entailment_user_prompt, parse_support_verdict


class AdapterPromptTests(unittest.TestCase):
    def test_user_prompt_has_evidence_and_claim(self):
        p = build_entailment_user_prompt("EV-TEXT", "CL-TEXT")
        self.assertIn("EV-TEXT", p)
        self.assertIn("CL-TEXT", p)

    def test_system_prompt_is_entailment_not_overclaim(self):
        sp = ENTAILMENT_SYSTEM_PROMPT.lower()
        self.assertIn("evidence", sp)
        self.assertIn("supported", sp)
        # must NOT be the overclaim contract
        self.assertNotIn("signals available", sp)
        self.assertNotIn("self-history", sp)

    def test_parse_verdict(self):
        self.assertEqual(parse_support_verdict("SUPPORTED\nbecause..."), "SUPPORTED")
        self.assertEqual(parse_support_verdict("unsupported: the claim..."), "UNSUPPORTED")
        self.assertEqual(parse_support_verdict(""), "EMPTY")
        self.assertTrue(parse_support_verdict("maybe idk").startswith("UNPARSED"))
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_bench.AdapterPromptTests -v`
Expected: FAIL — `ModuleNotFoundError: adapter_prompt`.

- [ ] **Step 3: Implement the prompt + parser**

Create `scripts/grounding_bench/adapter_prompt.py`:
```python
"""The 4B-entailment-ADAPTER prompt — the LLM yardstick for the audition.

REVIEWED ARTIFACT: this prompt defines the LLM baseline the small verifiers
are measured against. A biased/sloppy prompt biases the whole scorecard, so it
is reviewed first-class (owner plan note, 2026-06-11). This is NOT
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
    "evidence also gives a newer/superseding one.\n"
    "- Judge ONLY against the evidence given. Do not use outside knowledge. Do not "
    "judge whether the claim is true in the world — only whether it follows from "
    "this evidence.\n\n"
    "Respond with EXACTLY one word on the first line: SUPPORTED or UNSUPPORTED. "
    "Then one sentence of reason. Nothing else."
)


def build_entailment_user_prompt(evidence: str, claim: str) -> str:
    return (
        f"EVIDENCE:\n{evidence}\n\n"
        f"CLAIM:\n{claim}\n\n"
        f"verdict:"
    )


def parse_support_verdict(content: str) -> str:
    content = (content or "").strip()
    if not content:
        return "EMPTY"
    first = content.split(None, 1)[0].upper().rstrip(":,.")
    if first in ("SUPPORTED", "UNSUPPORTED"):
        return first
    up = content.upper()
    if "UNSUPPORTED" in up and "SUPPORTED" not in up.replace("UNSUPPORTED", ""):
        return "UNSUPPORTED"
    if "SUPPORTED" in up and "UNSUPPORTED" not in up:
        return "SUPPORTED"
    return f"UNPARSED({content[:40]!r})"
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_bench.AdapterPromptTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add scripts/grounding_bench/adapter_prompt.py tests/test_grounding_bench.py
git commit -m "feat(grounding-bench): reviewed 4B-entailment-adapter prompt + verdict parser

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Verifier adapters (HHEM + MiniCheck + 4B-adapter)

**Files:** Create `scripts/grounding_bench/verifiers.py`; Test `tests/test_grounding_bench.py`

All three expose the same interface: `.support(evidence, claim) -> (label, latency_s)` where `label ∈ {SUPPORTED, UNSUPPORTED, EMPTY, ERROR(...), UNPARSED(...)}`. HHEM also stores its last raw score for the sweep. **Models load lazily on first `.support()`** (so tests can mock without loading).

> **Option A — HHEM is unavailable by construction until the gate clears.** `HHEM_REVISION` ships **unset (`None`)**; `HhemVerifier` raises `HhemRevisionUnconfigured` on load → `.support()` returns `ERROR(HhemRevisionUnconfigured)` rather than download anything. **No model downloads, and no `trust_remote_code` executes, anywhere in this build** — every verifier test mocks the raw inference, and MiniCheck also loads lazily (nothing downloads until the scorecard run). Resolving the HHEM pin, the owner-approved download, and the **API-confirmation smoke** (HHEM `.predict` shape + MiniCheck `(doc,claim)` shape — confirm and adjust the adapters if the real call differs from the snippets below) all happen **post-gate in Task 7**. This preserves the safety boundary: build everything offline, stop before any remote-code/download.

- [ ] **Step 1: Write the failing test (mocked models — no real load)**

Append to `tests/test_grounding_bench.py`:
```python
from unittest import mock
import verifiers as V


class VerifierTests(unittest.TestCase):
    def test_minicheck_binary_maps_to_label(self):
        v = V.MinicheckVerifier()
        with mock.patch.object(v, "_predict_raw", return_value=1):
            label, _ = v.support("E", "C")
        self.assertEqual(label, "SUPPORTED")
        with mock.patch.object(v, "_predict_raw", return_value=0):
            label, _ = v.support("E", "C")
        self.assertEqual(label, "UNSUPPORTED")

    def test_hhem_threshold_mapping(self):
        v = V.HhemVerifier(threshold=0.5)
        with mock.patch.object(v, "_score_raw", return_value=0.8):
            self.assertEqual(v.support("E", "C")[0], "SUPPORTED")
        with mock.patch.object(v, "_score_raw", return_value=0.2):
            self.assertEqual(v.support("E", "C")[0], "UNSUPPORTED")
        self.assertEqual(v.last_score, 0.2)

    def test_hhem_unconfigured_revision_errors_without_download(self):
        # Option A: with HHEM_REVISION unset (the default), HHEM refuses to load —
        # it returns a clear ERROR and never touches the network / remote code.
        self.assertIsNone(V.HHEM_REVISION)         # ships unset
        v = V.HhemVerifier(threshold=0.5)          # NOT mocked
        label, _ = v.support("E", "C")
        self.assertEqual(label, "ERROR(HhemRevisionUnconfigured)")

    def test_4b_adapter_parses_endpoint(self):
        v = V.FourBAdapterVerifier(url="http://x", model="m")
        with mock.patch.object(v, "_chat_raw", return_value="SUPPORTED\nreason"):
            self.assertEqual(v.support("E", "C")[0], "SUPPORTED")
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_bench.VerifierTests -v`
Expected: FAIL — `ModuleNotFoundError: verifiers`.

- [ ] **Step 3: Implement the adapters**

Create `scripts/grounding_bench/verifiers.py`:
```python
"""Candidate verifier adapters for the grounding audition. CPU-only.

Each adapter: .support(evidence, claim) -> (label, latency_s).
Models load lazily so unit tests can mock the raw inference.
"""
from __future__ import annotations

import time

import httpx

from adapter_prompt import (ENTAILMENT_SYSTEM_PROMPT, build_entailment_user_prompt,
                            parse_support_verdict)

# Option A: HHEM ships UNAVAILABLE until the owner-gated pin is supplied post-gate.
# Nothing downloads and no trust_remote_code runs during the build.
HHEM_REPO = "vectara/hallucination_evaluation_model"
HHEM_REVISION = None  # set post-gate to a full 40-char commit sha (owner-approved download)
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
        # HHEM predict takes (premise, hypothesis) pairs -> consistency score 0..1
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
        # CONFIRM in the smoke step: MiniCheck takes (doc, claim) -> 2-class logits,
        # label 1 == supported. Adjust to the confirmed call if it differs.
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_bench.VerifierTests -v`
Expected: PASS (mocked — no real model load).

- [ ] **Step 5: Commit**
```bash
git add scripts/grounding_bench/verifiers.py tests/test_grounding_bench.py
git commit -m "feat(grounding-bench): HHEM/MiniCheck/4B-adapter verifiers (lazy load, pinned HHEM)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: The harness — abstain precondition + per-mode tally

**Files:** Create `scripts/grounding_bench/bench_grounding.py`; Test `tests/test_grounding_bench.py`

- [ ] **Step 1: Write the failing tests (the abstain precondition is the load-bearing one)**

Append to `tests/test_grounding_bench.py`:
```python
import bench_grounding as B


class HarnessTests(unittest.TestCase):
    def test_abstain_precondition_calls_no_model(self):
        # claimable_absent -> ABSTAIN, verifier MUST NOT be called
        verifier = mock.MagicMock()
        case = {"id": "abs-1", "mode": "no_evidence_abstain", "evidence_kind": "claimable_absent",
                "evidence": "", "claim": "C", "expected": "ABSTAIN_EXPECTED"}
        label, _ = B.judge_case(verifier, case)
        self.assertEqual(label, "ABSTAIN")
        verifier.support.assert_not_called()      # the box was never weighed

    def test_present_evidence_calls_model(self):
        verifier = mock.MagicMock()
        verifier.support.return_value = ("UNSUPPORTED", 0.01)
        case = {"id": "x", "mode": "cited_but_unsupported", "evidence_kind": "claimable_present",
                "evidence": "E", "claim": "C", "expected": "UNSUPPORTED"}
        label, _ = B.judge_case(verifier, case)
        self.assertEqual(label, "UNSUPPORTED")
        verifier.support.assert_called_once()

    def test_false_negative_tally_per_mode(self):
        # an UNSUPPORTED case wrongly labeled SUPPORTED is a false-negative for its mode
        per_item = [
            {"mode": "stale_over_current", "expected": "UNSUPPORTED", "got": "SUPPORTED"},
            {"mode": "stale_over_current", "expected": "UNSUPPORTED", "got": "UNSUPPORTED"},
            {"mode": "grounded_positive", "expected": "SUPPORTED", "got": "UNSUPPORTED"},
        ]
        fn = B.false_negatives_by_mode(per_item)
        self.assertEqual(fn["stale_over_current"], {"false_neg": 1, "total_unsupported": 2})
        self.assertNotIn("grounded_positive", fn)  # no UNSUPPORTED cases -> not a FN mode
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_bench.HarnessTests -v`
Expected: FAIL — `ModuleNotFoundError: bench_grounding`.

- [ ] **Step 3: Implement the harness**

Create `scripts/grounding_bench/bench_grounding.py`:
```python
"""Grounding-verifier audition harness. Offline scorecard; no live-daemon change.

Mirrors scripts/judge_bench/bench.py, with two differences that matter:
  - an ABSTAIN precondition (no model is called on claimable_absent), and
  - a per-mode FALSE-NEGATIVE headline (the dangerous error: an UNSUPPORTED
    claim wrongly blessed SUPPORTED).
"""
from __future__ import annotations

import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus.json"
RESULTS_CSV = HERE / "results_grounding.csv"
RESULTS_MD = HERE / "results_grounding.md"


def judge_case(verifier, case: dict) -> tuple[str, float]:
    """ABSTAIN precondition: claimable_absent -> ABSTAIN without calling any model."""
    if case["evidence_kind"] == "claimable_absent":
        return "ABSTAIN", 0.0
    return verifier.support(case["evidence"], case["claim"])


def _scored(expected: str, got: str) -> str:
    if got == "ABSTAIN":
        return "abstain_ok" if expected == "ABSTAIN_EXPECTED" else "abstain_wrong"
    if got == expected:
        return "match"
    if expected == "UNSUPPORTED" and got == "SUPPORTED":
        return "false_negative"   # the dangerous one
    if expected == "SUPPORTED" and got == "UNSUPPORTED":
        return "false_positive"
    return "error"                # EMPTY/ERROR/UNPARSED


def false_negatives_by_mode(per_item: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for r in per_item:
        if r["expected"] != "UNSUPPORTED":
            continue
        m = out.setdefault(r["mode"], {"false_neg": 0, "total_unsupported": 0})
        m["total_unsupported"] += 1
        if r["got"] == "SUPPORTED":
            m["false_neg"] += 1
    return out


def run_candidate(verifier, label: str, items: list[dict]) -> dict:
    per_item, latencies = [], []
    tally = defaultdict(int)
    print(f"\n=== {label} ===", flush=True)
    for case in items:
        got, lat = judge_case(verifier, case)
        latencies.append(lat)
        outcome = _scored(case["expected"], got)
        tally[outcome] += 1
        per_item.append({"id": case["id"], "mode": case["mode"],
                         "expected": case["expected"], "got": got, "outcome": outcome,
                         "latency_s": round(lat, 3)})
        mark = {"match": "OK", "abstain_ok": "OK", "false_negative": "!!FN",
                "false_positive": "fp", "abstain_wrong": "!abs", "error": "err"}.get(outcome, "?")
        print(f"  {mark:<4} {case['id']:<10} exp={case['expected']:<16} got={got:<20} ({lat:.2f}s)", flush=True)
    return {
        "label": label,
        "n": len(items),
        "false_neg_by_mode": false_negatives_by_mode(per_item),
        "false_positives": tally["false_positive"],
        "abstain_ok": tally["abstain_ok"],
        "abstain_wrong": tally["abstain_wrong"],
        "errors": tally["error"],
        "matches": tally["match"] + tally["abstain_ok"],
        "latency_p50": round(statistics.median(latencies), 3) if latencies else 0.0,
        "latency_p95": round(sorted(latencies)[max(0, int(0.95 * len(latencies)) - 1)], 3) if latencies else 0.0,
        "per_item": per_item,
    }


def load_corpus() -> list[dict]:
    import sys
    sys.path.insert(0, str(HERE))
    from corpus_schema import validate_corpus
    items = json.loads(CORPUS.read_text())["items"]
    validate_corpus(items)
    return items
```
(The CLI `main()` that wires the three verifiers + the HHEM sweep + writes the report is Task 6.)

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_bench.HarnessTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add scripts/grounding_bench/bench_grounding.py tests/test_grounding_bench.py
git commit -m "feat(grounding-bench): harness with abstain precondition + per-mode false-negative tally

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Report renderer (per-mode false-negative headline) + CLI

**Files:** Modify `scripts/grounding_bench/bench_grounding.py`; Test `tests/test_grounding_bench.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_grounding_bench.py`:
```python
class ReportTests(unittest.TestCase):
    def test_markdown_foregrounds_false_negatives(self):
        summaries = [{
            "label": "hhem@0.5", "n": 26,
            "false_neg_by_mode": {"stale_over_current": {"false_neg": 2, "total_unsupported": 4},
                                  "fabricated_false_specific": {"false_neg": 0, "total_unsupported": 5}},
            "false_positives": 1, "abstain_ok": 3, "abstain_wrong": 0, "errors": 0,
            "matches": 22, "latency_p50": 0.05, "latency_p95": 0.09, "per_item": [],
        }]
        md = B.render_markdown(summaries)
        self.assertIn("False-negatives by mode", md)
        self.assertIn("stale_over_current", md)
        self.assertIn("2/4", md)          # the dangerous miss, shown as a fraction
        self.assertIn("hhem@0.5", md)
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_bench.ReportTests -v`
Expected: FAIL — `render_markdown` not defined.

- [ ] **Step 3: Implement render + CLI**

Append to `scripts/grounding_bench/bench_grounding.py`:
```python
def render_markdown(summaries: list[dict]) -> str:
    lines = ["# Evidence-grounding verifier audition", "",
             "Headline metric: **per-mode false-negative rate** (an UNSUPPORTED claim "
             "wrongly blessed SUPPORTED — the dangerous miss).", ""]
    lines += ["## False-negatives by mode (lower is safer)", "",
              "| candidate | cited_but_unsupported | fabricated_false_specific | stale_over_current |",
              "|---|---|---|---|"]
    modes = ["cited_but_unsupported", "fabricated_false_specific", "stale_over_current"]
    for s in summaries:
        cells = []
        for m in modes:
            d = s["false_neg_by_mode"].get(m)
            cells.append(f"{d['false_neg']}/{d['total_unsupported']}" if d else "—")
        lines.append(f"| {s['label']} | " + " | ".join(cells) + " |")
    lines += ["", "## Side metrics", "",
              "| candidate | n | false_pos | abstain_ok | abstain_wrong | errors | p50 s | p95 s |",
              "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for s in summaries:
        lines.append(f"| {s['label']} | {s['n']} | {s['false_positives']} | {s['abstain_ok']} | "
                     f"{s['abstain_wrong']} | {s['errors']} | {s['latency_p50']} | {s['latency_p95']} |")
    return "\n".join(lines) + "\n"


def append_to_csv(summary: dict) -> None:
    is_new = not RESULTS_CSV.exists()
    with RESULTS_CSV.open("a") as f:
        if is_new:
            f.write("timestamp,label,n,false_pos,abstain_ok,abstain_wrong,errors,matches,p50,p95\n")
        f.write(f"{int(time.time())},{summary['label']},{summary['n']},{summary['false_positives']},"
                f"{summary['abstain_ok']},{summary['abstain_wrong']},{summary['errors']},"
                f"{summary['matches']},{summary['latency_p50']},{summary['latency_p95']}\n")


def main() -> int:
    import argparse
    from verifiers import HhemVerifier, MinicheckVerifier, FourBAdapterVerifier
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-url", default="http://127.0.0.1:8081")
    ap.add_argument("--judge-model", default="maez-judge")
    ap.add_argument("--only", default="", help="comma list: hhem,minicheck,4b")
    args = ap.parse_args()

    items = load_corpus()
    want = set(args.only.split(",")) if args.only else {"hhem", "minicheck", "4b"}
    summaries = []
    if "minicheck" in want:
        summaries.append(run_candidate(MinicheckVerifier(), "minicheck-deberta", items))
    if "hhem" in want:
        for thr in (0.3, 0.5, 0.7):
            summaries.append(run_candidate(HhemVerifier(threshold=thr), f"hhem@{thr}", items))
    if "4b" in want:
        summaries.append(run_candidate(
            FourBAdapterVerifier(args.judge_url, args.judge_model), "4b-entailment-adapter", items))

    for s in summaries:
        append_to_csv(s)
    RESULTS_MD.write_text(render_markdown(summaries))
    print(f"\nWrote {RESULTS_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify it passes + a mocked smoke**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_bench -v`
Expected: PASS (all classes). Then a mocked end-to-end smoke (no real models):
```bash
/home/rohit/maez/.venv/bin/python -B -c "
import sys; sys.path.insert(0,'scripts/grounding_bench')
import bench_grounding as B
class Fake:
    def support(self,e,c): return ('UNSUPPORTED',0.01)
items=B.load_corpus()
s=B.run_candidate(Fake(),'fake',items)
print('modes with FN tracking:', list(s['false_neg_by_mode']))
print(B.render_markdown([s])[:400])
"
```
Expected: runs over the real corpus with a fake verifier, prints the FN-by-mode table.

- [ ] **Step 5: Commit**
```bash
git add scripts/grounding_bench/bench_grounding.py tests/test_grounding_bench.py
git commit -m "feat(grounding-bench): report renderer (per-mode FN headline) + CLI

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: STOP at the gate — handoff for review + owner-download

**Files:** Create `docs/handoffs/2026-06-11-grounding-audition-gate.md`

The code + corpus are built and unit-tested with mocked models. **The meaningful scorecard run is POST-GATE.** Do not run real models yet.

- [ ] **Step 1: Full floor (mocked tests only)**
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_bench
cd /home/rohit/maez && .venv/bin/ruff check scripts/grounding_bench/ tests/test_grounding_bench.py
```
Expected: OK / clean.

- [ ] **Step 2: Write the gate handoff**

Create `docs/handoffs/2026-06-11-grounding-audition-gate.md` documenting:
- What's built (corpus, schema, adapter prompt, verifiers, harness, report) + the mocked-test floor green.
- **The three hard gates that must clear before the scorecard run:**
  1. **Corpus label review** — Codex/owner reads each case's `(evidence, claim, expected, rationale)` and confirms the grounding label, case-by-case.
  2. **4B-adapter prompt review** — `adapter_prompt.py:ENTAILMENT_SYSTEM_PROMPT` reviewed (it's the yardstick).
  3. **HHEM download owner-approval + pin** — `HhemVerifier` ships inert (`ERROR(HhemRevisionUnconfigured)`) until `HHEM_REVISION` is set; nothing downloaded so far. Owner approves the ~440MB download + `trust_remote_code` execution.
- **Post-gate sequence (only after all three clear):**
  1. Resolve the current commit sha of `vectara/hallucination_evaluation_model` and set `HHEM_REVISION` in `verifiers.py` to it (full 40-char sha).
  2. **API-confirmation smoke** — load HHEM (now permitted) + MiniCheck on ONE pair each; confirm the `.predict` / `(doc,claim)` call shapes match the adapters; **adjust the adapters if the real call differs — do not force the snippet.**
  3. **Run the scorecard:** `/home/rohit/maez/.venv/bin/python -B scripts/grounding_bench/bench_grounding.py` (judge endpoint up on 8081 for the 4B-adapter row). Optionally add the production-`grounding_judge` diagnostic row.

- [ ] **Step 3: Commit + STOP**
```bash
git add docs/handoffs/2026-06-11-grounding-audition-gate.md
git commit -m "docs(grounding-bench): gate handoff — STOP before scorecard run

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**STOP.** No real-model run, no merge. Report branch tip + the floor. The three gates clear before the scorecard.

---

## Self-Review (against the spec)

- Corpus: claim-level unit, `evidence_kind` explicit, 3 labels, taxonomy-balanced modes, real-spine + flagged synthetic, rationale per row, validator enforces absent↔abstain: Tasks 1–2. ✓
- 4B = entailment *adapter* (reviewed prompt), NOT grounding_judge's overclaim contract; test forbids the overclaim phrasing: Task 3. ✓
- Abstain precondition calls no model (mock asserts not-called): Task 5. ✓
- HHEM threshold sweep {0.3,0.5,0.7}; MiniCheck binary; per-mode false-negative headline: Tasks 4/6. ✓
- HHEM `trust_remote_code` unavailable-by-construction (`HHEM_REVISION=None` → `ERROR(HhemRevisionUnconfigured)`); pin + owner-approved download + smoke are all post-gate (Option A — resolves the Task-4-smoke vs Task-7-gate contradiction): Task 4 guard + Task 7 post-gate sequence. ✓
- Scope: no live-daemon change; no-citation excluded; citation/overclaim rails untouched: throughout. ✓
- STOP at the gate before the meaningful run (label + prompt + download review): Task 7. ✓
- Optional production-`grounding_judge` diagnostic row: deferred to the post-gate run (notable: not blocking v0; can be added as a `--only` candidate later).

Placeholder scan: **no placeholder SHA is committed** — `HHEM_REVISION = None` ships HHEM unavailable-by-construction; the real pin is set post-gate (Task 7) and the MiniCheck call-shape is confirmed in the post-gate smoke. No `<PLACEHOLDER>` strings in committed code. No other placeholders. Signatures consistent: `.support(evidence, claim) -> (label, latency)` across all three verifiers; `judge_case`, `false_negatives_by_mode`, `render_markdown` consistent across Tasks 5–6.
