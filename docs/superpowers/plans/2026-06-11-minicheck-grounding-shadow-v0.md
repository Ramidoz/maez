# MiniCheck Grounding Shadow v0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Watch a sentence-level claimable-entailment verifier (MiniCheck) on *live* Maez replies — logging content-light divergence telemetry — while changing, blocking, and delaying nothing Maez says.

**Architecture:** An out-of-process MiniCheck HTTP service owns the model. A default-OFF shadow hook in the daemon's reply path, *after* the reply is served, does one non-blocking enqueue onto a **bounded** queue; a background worker drains it, splits the final audited text into sentences, calls the service per-sentence under a two-layer budget, and appends one content-light JSONL telemetry record. The daemon never imports `transformers`.

**Tech Stack:** Python 3 (stdlib `http.server`, `queue`, `threading`, `hashlib`, `json`, `re`), `httpx` (already used by `scripts/judge_bench/bench.py`), `torch`+`transformers` **only inside the service**. Spec: `docs/superpowers/specs/2026-06-11-minicheck-grounding-shadow-v0-design.md` @ `ca61e03`.

**Test runner:** `/home/rohit/maez/.venv/bin/python -B -m unittest <module>` (NOT pytest). Run a single test: `... -m unittest tests.test_support_verifier.SupportVerifierTests.test_x`.

---

## Standing constraints (read before Task 1)
- **Lane:** Codex builds / Claude reviews (covenant axis). main is local-only/unpushed @ `ca61e03` — **never `git push`**.
- **Daemon never imports `transformers`.** Only `scripts/minicheck_verifier_service.py` (Task 7) imports `torch`/`transformers`. All daemon-side tests use `FakeSupportVerifier`. Task 6 includes a test asserting `core.cognition.grounding_shadow`'s import graph does not pull `transformers`.
- **The shadow is observation-only:** gates nothing, rewrites nothing, blocks nothing, delays nothing. The serve path's only action is one non-blocking enqueue.
- **`## Predicted effect`** goes on exactly ONE commit — the Task 6 hook wiring (the only behavior-touching change, and it's default-OFF). Every other commit is additive/inert and omits it.
- **Co-author trailer on every commit:** `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **STOP-AT-GATE (Task 8):** build everything green-with-Fake, then STOP. The owner breath (install+start the service, the real-model smoke, flipping `MAEZ_GROUNDING_SHADOW_ENABLED=1`) is NOT taken by the implementer.
- **Port:** the service binds `127.0.0.1:8083` (brain 8080, judge 8081, vision 8082, minicheck 8083).

## File structure
| File | Responsibility |
|---|---|
| `core/cognition/support_verifier.py` (create) | `SupportVerifier` interface + `HttpSupportVerifier` (live) + `FakeSupportVerifier` (tests). |
| `core/cognition/grounding_shadow.py` (create) | sentence split, per-job compute + two-layer budget, content-light telemetry, bounded queue + worker, the `shadow_observe` hook + default-off gate. |
| `scripts/minicheck_verifier_service.py` (create) | the out-of-process HTTP service; the ONLY place `torch`/`transformers` loads. |
| `scripts/maez-minicheck-verifier.template.service` (create) | the systemd user unit template (installed-but-inert). |
| `core/safety/audited_output.py` (modify) | the post-dispatch hook call site (Task 6). |
| `tests/test_support_verifier.py`, `tests/test_grounding_shadow.py`, `tests/test_minicheck_verifier_service.py` (create) | unit tests. |
| `docs/handoffs/2026-06-11-minicheck-grounding-shadow-gate.md` (create) | the STOP-AT-GATE handoff (Task 8). |

---

### Task 1: `SupportVerifier` interface + `FakeSupportVerifier`

**Files:**
- Create: `core/cognition/support_verifier.py`
- Test: `tests/test_support_verifier.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_support_verifier.py
import unittest
from core.cognition.support_verifier import (
    SupportVerifier, FakeSupportVerifier, SUPPORTED, UNSUPPORTED, UNAVAILABLE,
)


class FakeSupportVerifierTests(unittest.TestCase):
    def test_interface_is_abstract(self):
        with self.assertRaises(TypeError):
            SupportVerifier()  # abstract — cannot instantiate

    def test_scripted_verdict(self):
        v = FakeSupportVerifier(scripted={"the sky is green": (UNSUPPORTED, 0.1)})
        label, score, latency = v.support("ev", "the sky is green", 0.25)
        self.assertEqual(label, UNSUPPORTED)
        self.assertEqual(score, 0.1)
        self.assertGreaterEqual(latency, 0.0)

    def test_default_verdict(self):
        v = FakeSupportVerifier(default=(SUPPORTED, 0.99))
        self.assertEqual(v.support("ev", "anything", 0.25)[0], SUPPORTED)

    def test_records_calls(self):
        v = FakeSupportVerifier()
        v.support("ev1", "claim1", 0.25)
        self.assertEqual(v.calls, [("ev1", "claim1")])

    def test_can_raise(self):
        v = FakeSupportVerifier(raises=RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            v.support("ev", "claim", 0.25)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_support_verifier -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.cognition.support_verifier'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/cognition/support_verifier.py
"""The claimable-entailment support verifier seam.

`SupportVerifier` is the swappable instrument contract. `HttpSupportVerifier`
(Task 2) talks to the out-of-process MiniCheck service; `FakeSupportVerifier`
is for tests. The real model is NEVER loaded in this module — it lives only in
`scripts/minicheck_verifier_service.py`.
"""
from __future__ import annotations

import abc
import time
from typing import Optional

SUPPORTED = "SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
UNAVAILABLE = "UNAVAILABLE"


class SupportVerifier(abc.ABC):
    @abc.abstractmethod
    def support(self, evidence: str, claim: str, timeout_s: float) -> tuple[str, Optional[float], float]:
        """Return (label, score, latency_s). label ∈ {SUPPORTED, UNSUPPORTED, UNAVAILABLE}."""
        raise NotImplementedError


class FakeSupportVerifier(SupportVerifier):
    """Tests only. Scripted verdicts; never loads a real model."""

    def __init__(self, scripted=None, default=(SUPPORTED, 0.99), raises=None, sleep_s=0.0):
        self._scripted = dict(scripted or {})
        self._default = default
        self._raises = raises
        self._sleep_s = sleep_s
        self.calls: list[tuple[str, str]] = []

    def support(self, evidence, claim, timeout_s):
        t0 = time.monotonic()
        self.calls.append((evidence, claim))
        if self._raises is not None:
            raise self._raises
        if self._sleep_s:
            time.sleep(self._sleep_s)
        label, score = self._scripted.get(claim, self._default)
        return label, score, time.monotonic() - t0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_support_verifier -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add core/cognition/support_verifier.py tests/test_support_verifier.py
git commit -m "feat(grounding-shadow): SupportVerifier interface + FakeSupportVerifier

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `HttpSupportVerifier` (transport errors → UNAVAILABLE, never raises)

**Files:**
- Modify: `core/cognition/support_verifier.py`
- Test: `tests/test_support_verifier.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_support_verifier.py`, above `if __name__`)

```python
from unittest import mock
from core.cognition.support_verifier import HttpSupportVerifier


class HttpSupportVerifierTests(unittest.TestCase):
    def _resp(self, payload):
        r = mock.Mock()
        r.json.return_value = payload
        r.raise_for_status.return_value = None
        return r

    def test_supported(self):
        v = HttpSupportVerifier(url="http://127.0.0.1:8083")
        with mock.patch("core.cognition.support_verifier.httpx.post",
                        return_value=self._resp({"verdict": "SUPPORTED", "score": 0.9})) as p:
            label, score, _ = v.support("ev", "claim", 0.25)
        self.assertEqual(label, SUPPORTED)
        self.assertEqual(score, 0.9)
        # the per-sentence timeout is passed through to httpx
        self.assertEqual(p.call_args.kwargs["timeout"], 0.25)

    def test_unsupported(self):
        v = HttpSupportVerifier()
        with mock.patch("core.cognition.support_verifier.httpx.post",
                        return_value=self._resp({"verdict": "UNSUPPORTED", "score": 0.2})):
            self.assertEqual(v.support("ev", "claim", 0.25)[0], UNSUPPORTED)

    def test_transport_error_returns_unavailable(self):
        v = HttpSupportVerifier()
        with mock.patch("core.cognition.support_verifier.httpx.post",
                        side_effect=Exception("connection refused")):
            label, score, _ = v.support("ev", "claim", 0.25)
        self.assertEqual(label, UNAVAILABLE)
        self.assertIsNone(score)

    def test_never_raises(self):
        v = HttpSupportVerifier()
        with mock.patch("core.cognition.support_verifier.httpx.post",
                        side_effect=Exception("boom")):
            try:
                v.support("ev", "claim", 0.25)
            except Exception:  # noqa
                self.fail("HttpSupportVerifier.support must never raise")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_support_verifier.HttpSupportVerifierTests -v`
Expected: FAIL — `ImportError: cannot import name 'HttpSupportVerifier'`.

- [ ] **Step 3: Write minimal implementation** (append to `core/cognition/support_verifier.py`)

```python
import httpx


class HttpSupportVerifier(SupportVerifier):
    """Live verifier — POSTs to the out-of-process MiniCheck service.
    Any transport failure (down, timeout, 5xx, bad JSON) → ("UNAVAILABLE", None).
    NEVER raises: the shadow must never perturb the reply path.
    """

    def __init__(self, url: str = "http://127.0.0.1:8083", default_timeout_s: float = 0.25):
        self._endpoint = url.rstrip("/") + "/support"
        self._default_timeout_s = default_timeout_s

    def support(self, evidence, claim, timeout_s=None):
        t0 = time.monotonic()
        to = self._default_timeout_s if timeout_s is None else timeout_s
        try:
            r = httpx.post(self._endpoint, json={"evidence": evidence, "claim": claim}, timeout=to)
            r.raise_for_status()
            data = r.json()
            label = SUPPORTED if data.get("verdict") == SUPPORTED else UNSUPPORTED
            return label, data.get("score"), time.monotonic() - t0
        except Exception:
            return UNAVAILABLE, None, time.monotonic() - t0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_support_verifier -v`
Expected: PASS (9 tests total).

- [ ] **Step 5: Commit**

```bash
git add core/cognition/support_verifier.py tests/test_support_verifier.py
git commit -m "feat(grounding-shadow): HttpSupportVerifier (transport-error -> UNAVAILABLE, never raises)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: sentence split + per-job compute + two-layer budget

**Files:**
- Create: `core/cognition/grounding_shadow.py`
- Test: `tests/test_grounding_shadow.py`

The per-job compute splits the final text, concatenates the claimable items' evidence as the MiniCheck document, and runs one verifier call per sentence under a per-sentence timeout + a per-job wall-clock budget. Claimable item shape (from `envelope_builder.py:132-148`): `c.get("evidence") or c.get("evidence_refs") or c.get("text") or c.get("fact")`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_grounding_shadow.py
import time
import unittest
from core.cognition.support_verifier import FakeSupportVerifier, SUPPORTED, UNSUPPORTED
from core.cognition import grounding_shadow as gs


CLAIMABLE = [{"text": "f", "provenance": "memory", "evidence": "The recall flip was a No-Go on latency."}]


class SplitTests(unittest.TestCase):
    def test_split_sentences(self):
        self.assertEqual(gs.split_sentences("A b. C d! E f?"), ["A b.", "C d!", "E f?"])

    def test_split_empty(self):
        self.assertEqual(gs.split_sentences("   "), [])


class ComputeTests(unittest.TestCase):
    def test_no_claimable_calls_no_verifier(self):
        v = FakeSupportVerifier()
        out = gs.compute_shadow("A sentence.", [], v)
        self.assertEqual(out["status"], "no_claimable")
        self.assertEqual(v.calls, [])  # the abstain rule — no model touched

    def test_no_sentences(self):
        out = gs.compute_shadow("   ", CLAIMABLE, FakeSupportVerifier())
        self.assertEqual(out["status"], "no_sentences")

    def test_ok_runs_per_sentence(self):
        v = FakeSupportVerifier(default=(SUPPORTED, 0.9))
        out = gs.compute_shadow("One. Two.", CLAIMABLE, v)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(len(out["sentences"]), 2)
        self.assertEqual(out["sentences"][0]["verdict"], SUPPORTED)

    def test_budget_exceeded_stops_and_counts(self):
        # each call sleeps 0.2s; per-job budget 0.25s → 2nd sentence trips the budget
        v = FakeSupportVerifier(sleep_s=0.2)
        out = gs.compute_shadow("One. Two. Three.", CLAIMABLE, v, per_job_budget_s=0.25)
        self.assertEqual(out["status"], "budget_exceeded")
        self.assertGreaterEqual(out["remaining_count"], 1)
        self.assertLess(out["shadowed_count"], 3)

    def test_verifier_error_marks_unavailable(self):
        v = FakeSupportVerifier(raises=RuntimeError("boom"))
        out = gs.compute_shadow("One.", CLAIMABLE, v)
        self.assertEqual(out["status"], "verifier_unavailable")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.cognition.grounding_shadow'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/cognition/grounding_shadow.py
"""The MiniCheck grounding SHADOW — observation only.

Splits the FINAL audited reply into sentences and asks an out-of-process
verifier whether each follows from the claimable evidence, writing content-light
divergence telemetry. Gates nothing, rewrites nothing, blocks nothing, delays
nothing. Mirrors the in-tree shadow precedent (core/routing/recall_shadow.py).
"""
from __future__ import annotations

import re
import time

from core.cognition.support_verifier import SUPPORTED, UNSUPPORTED, UNAVAILABLE

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


def claimable_evidence(claimable_items) -> str:
    parts = []
    for c in (claimable_items or []):
        ev = c.get("evidence") or c.get("evidence_refs") or c.get("text") or c.get("fact") or ""
        if ev:
            parts.append(str(ev))
    return "\n".join(parts)


def compute_shadow(final_text, claimable_items, verifier, *,
                   per_sentence_timeout_s: float = 0.25, per_job_budget_s: float = 1.5) -> dict:
    """Run the per-sentence entailment shadow under a two-layer budget.

    NOTE: the per-sentence HTTP timeout and an UNAVAILABLE result both surface as
    the job status `verifier_unavailable` in v0 — the HTTP client does not
    distinguish a timeout from a refused connection (spec status `timeout` is
    subsumed here; revisit if v0.1 needs the split).
    """
    evidence = claimable_evidence(claimable_items)
    if not evidence.strip():
        return {"status": "no_claimable", "sentences": [], "shadowed_count": 0, "remaining_count": 0}
    sentences = split_sentences(final_text)
    if not sentences:
        return {"status": "no_sentences", "sentences": [], "shadowed_count": 0, "remaining_count": 0}

    results, t_start, shadowed = [], time.monotonic(), 0
    for i, sent in enumerate(sentences):
        if time.monotonic() - t_start >= per_job_budget_s:
            return {"status": "budget_exceeded", "sentences": results,
                    "shadowed_count": shadowed, "remaining_count": len(sentences) - i}
        try:
            label, score, latency = verifier.support(evidence, sent, per_sentence_timeout_s)
        except Exception:
            label, score, latency = UNAVAILABLE, None, 0.0
        results.append({"sentence": sent, "verdict": label, "score": score, "latency_s": latency})
        shadowed += 1

    status = "verifier_unavailable" if any(r["verdict"] == UNAVAILABLE for r in results) else "ok"
    return {"status": status, "sentences": results, "shadowed_count": shadowed, "remaining_count": 0}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add core/cognition/grounding_shadow.py tests/test_grounding_shadow.py
git commit -m "feat(grounding-shadow): sentence split + per-job compute + two-layer budget

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: content-light telemetry record + audit-summary derivation

**Files:**
- Modify: `core/cognition/grounding_shadow.py`
- Test: `tests/test_grounding_shadow.py`

Content-light by default: hashes, counts, scores, provenance fingerprints — **no owner text** unless `debug=True`. `audit_summary_from_result` reads only real `AuditResult` fields (`mode`, `rewritten`, `flags`) and derives `audit_available` from `mode != "judge_unavailable"`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_grounding_shadow.py`)

```python
from dataclasses import dataclass, field


@dataclass
class _FakeAudit:  # mirrors core.safety.self_claim_audit.AuditResult fields
    text: str = "Final served text."
    rewritten: bool = False
    mode: str = "sentence"
    flags: list = field(default_factory=list)
    skipped_reason: object = None


class TelemetryTests(unittest.TestCase):
    def _compute(self):
        return gs.compute_shadow("Sky is blue. Sky is green.", CLAIMABLE,
                                 FakeSupportVerifier(scripted={"Sky is green.": (UNSUPPORTED, 0.1)}))

    def test_content_light_by_default(self):
        rec = gs.build_telemetry("sid", 123, "telegram", "boot1",
                                 gs.audit_summary_from_result(_FakeAudit()), CLAIMABLE, self._compute())
        blob = repr(rec)
        self.assertNotIn("Sky is blue", blob)          # no owner reply text
        self.assertNotIn("recall flip", blob)           # no owner evidence text
        self.assertIn("sentence_hash", rec["sentences"][0])
        self.assertNotIn("snippet", rec["sentences"][0])

    def test_debug_includes_bounded_snippet(self):
        rec = gs.build_telemetry("sid", 123, "telegram", "boot1",
                                 gs.audit_summary_from_result(_FakeAudit()), CLAIMABLE, self._compute(), debug=True)
        self.assertIn("snippet", rec["sentences"][0])
        self.assertLessEqual(len(rec["sentences"][0]["snippet"]), 120)

    def test_counts(self):
        rec = gs.build_telemetry("sid", 123, "telegram", "boot1",
                                 gs.audit_summary_from_result(_FakeAudit()), CLAIMABLE, self._compute())
        self.assertEqual(rec["sentence_count"], 2)
        self.assertEqual(rec["unsupported_count"], 1)
        self.assertEqual(rec["supported_count"], 1)
        self.assertEqual(rec["status"], "ok")

    def test_audit_summary_derives_available(self):
        self.assertTrue(gs.audit_summary_from_result(_FakeAudit(mode="sentence"))["audit_available"])
        self.assertFalse(gs.audit_summary_from_result(_FakeAudit(mode="judge_unavailable"))["audit_available"])

    def test_audit_summary_has_no_owner_text(self):
        s = gs.audit_summary_from_result(_FakeAudit(text="secret reply"))
        self.assertNotIn("secret reply", repr(s))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow.TelemetryTests -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'build_telemetry'`.

- [ ] **Step 3: Write minimal implementation** (append to `core/cognition/grounding_shadow.py`)

```python
import hashlib


def _hash(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]


def audit_summary_from_result(audit_result) -> dict:
    """Content-light summary from a self_claim_audit AuditResult — real fields only."""
    flags = getattr(audit_result, "flags", None) or []
    mode = getattr(audit_result, "mode", "noop")
    return {
        "audit_available": mode != "judge_unavailable",
        "flag_count": len(flags),
        "flag_kinds": sorted({getattr(f, "kind", "unknown") for f in flags}),
        "rewritten": bool(getattr(audit_result, "rewritten", False)),
        "mode": mode,
    }


def build_telemetry(shadow_id, ts, surface, boot_id, audit_summary, claimable_items, compute_result,
                    *, debug: bool = False) -> dict:
    sentences = []
    for r in compute_result.get("sentences", []):
        rec = {"sentence_hash": _hash(r["sentence"]), "verdict": r["verdict"],
               "score": r.get("score"), "latency_ms": round((r.get("latency_s") or 0.0) * 1000, 1)}
        if debug:
            rec["snippet"] = r["sentence"][:120]
        sentences.append(rec)
    verdicts = [r["verdict"] for r in compute_result.get("sentences", [])]
    return {
        "shadow_id": shadow_id, "ts": ts, "surface": surface, "boot_id": boot_id,
        "audit_available": audit_summary.get("audit_available"),
        "flag_count": audit_summary.get("flag_count"),
        "flag_kinds": audit_summary.get("flag_kinds"),
        "rewritten": audit_summary.get("rewritten"),
        "mode": audit_summary.get("mode"),
        "claimable_count": len(claimable_items or []),
        "claimable_chars": sum(len(str(c.get("evidence") or c.get("text") or "")) for c in (claimable_items or [])),
        "provenance_refs": [_hash(str(c.get("provenance") or "")) for c in (claimable_items or [])],
        "sentence_count": len(verdicts),
        "unsupported_count": sum(1 for v in verdicts if v == UNSUPPORTED),
        "supported_count": sum(1 for v in verdicts if v == SUPPORTED),
        "skipped_count": compute_result.get("remaining_count", 0),
        "status": compute_result["status"],
        "sentences": sentences,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow -v`
Expected: PASS (12 tests).

- [ ] **Step 5: Commit**

```bash
git add core/cognition/grounding_shadow.py tests/test_grounding_shadow.py
git commit -m "feat(grounding-shadow): content-light telemetry record + audit-summary derivation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: bounded queue + background worker + `shadow_enqueue_failed`

**Files:**
- Modify: `core/cognition/grounding_shadow.py`
- Test: `tests/test_grounding_shadow.py`

The owner's explicit note: the queue is **bounded**, and the **full-queue path is tested** — that's where `shadow_enqueue_failed` becomes real. `enqueue` is non-blocking and never raises; the worker never dies on a bad job.

- [ ] **Step 1: Write the failing test** (append to `tests/test_grounding_shadow.py`)

```python
import json
import os
import tempfile


class GroundingShadowQueueTests(unittest.TestCase):
    def _shadow(self, **kw):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return gs.GroundingShadow(FakeSupportVerifier(), path, **kw), path

    def _job(self, sid="s1"):
        return {"final_text": "One. Two.", "claimable_items": CLAIMABLE,
                "audit_summary": {"mode": "sentence", "audit_available": True},
                "surface": "telegram", "boot_id": "b", "shadow_id": sid, "ts": 1}

    def test_enqueue_returns_enqueued(self):
        shadow, _ = self._shadow(maxsize=4)
        self.assertEqual(shadow.enqueue(self._job()), "enqueued")

    def test_full_queue_returns_shadow_enqueue_failed(self):
        # worker NOT started → the bounded queue fills and the next enqueue fails
        shadow, path = self._shadow(maxsize=1)
        self.assertEqual(shadow.enqueue(self._job("s1")), "enqueued")
        self.assertEqual(shadow.enqueue(self._job("s2")), "shadow_enqueue_failed")
        with open(path) as f:
            recs = [json.loads(line) for line in f if line.strip()]
        self.assertTrue(any(r["status"] == "shadow_enqueue_failed" for r in recs))

    def test_enqueue_never_raises(self):
        shadow, _ = self._shadow(maxsize=1)
        try:
            shadow.enqueue(self._job())
            shadow.enqueue(self._job())  # full
        except Exception:  # noqa
            self.fail("enqueue must never raise")

    def test_worker_processes_and_writes_telemetry(self):
        shadow, path = self._shadow(maxsize=8)
        shadow.start()
        self.addCleanup(shadow.stop)
        shadow.enqueue(self._job("done"))
        deadline = time.monotonic() + 3.0
        recs = []
        while time.monotonic() < deadline:
            if os.path.getsize(path) > 0:
                with open(path) as f:
                    recs = [json.loads(line) for line in f if line.strip()]
                if any(r.get("shadow_id") == "done" for r in recs):
                    break
            time.sleep(0.02)
        self.assertTrue(any(r.get("shadow_id") == "done" and r["status"] == "ok" for r in recs))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow.GroundingShadowQueueTests -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'GroundingShadow'`.

- [ ] **Step 3: Write minimal implementation** (append to `core/cognition/grounding_shadow.py`)

```python
import json
import queue
import threading


class GroundingShadow:
    """Bounded queue + background worker. enqueue() is non-blocking and never
    raises; a full queue yields `shadow_enqueue_failed`. The worker never dies
    on a bad job. Nothing here ever touches the serve path's return value.
    """

    def __init__(self, verifier, telemetry_path, *, maxsize: int = 64,
                 per_sentence_timeout_s: float = 0.25, per_job_budget_s: float = 1.5, debug: bool = False):
        self._verifier = verifier
        self._telemetry_path = telemetry_path
        self._q: "queue.Queue" = queue.Queue(maxsize=maxsize)
        self._per_sentence_timeout_s = per_sentence_timeout_s
        self._per_job_budget_s = per_job_budget_s
        self._debug = debug
        self._worker = None
        self._stop = threading.Event()

    def enqueue(self, job: dict) -> str:
        try:
            self._q.put_nowait(job)
            return "enqueued"
        except queue.Full:
            self._emit({"shadow_id": job.get("shadow_id"), "ts": job.get("ts"),
                        "surface": job.get("surface"), "boot_id": job.get("boot_id"),
                        "status": "shadow_enqueue_failed"})
            return "shadow_enqueue_failed"
        except Exception:
            return "shadow_enqueue_failed"

    def start(self):
        if self._worker is None:
            self._worker = threading.Thread(target=self._run, name="grounding-shadow", daemon=True)
            self._worker.start()

    def stop(self):
        self._stop.set()
        try:
            self._q.put_nowait(None)
        except Exception:
            pass

    def _run(self):
        while not self._stop.is_set():
            try:
                job = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if job is None:
                break
            try:
                self._process(job)
            except Exception:
                pass  # the worker NEVER dies on a single job

    def _process(self, job):
        compute = compute_shadow(job["final_text"], job["claimable_items"], self._verifier,
                                 per_sentence_timeout_s=self._per_sentence_timeout_s,
                                 per_job_budget_s=self._per_job_budget_s)
        rec = build_telemetry(job.get("shadow_id"), job.get("ts"), job.get("surface"),
                              job.get("boot_id"), job.get("audit_summary", {}),
                              job.get("claimable_items"), compute, debug=self._debug)
        self._emit(rec)

    def _emit(self, rec):
        try:
            with open(self._telemetry_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow -v`
Expected: PASS (16 tests).

- [ ] **Step 5: Commit**

```bash
git add core/cognition/grounding_shadow.py tests/test_grounding_shadow.py
git commit -m "feat(grounding-shadow): bounded queue + background worker + shadow_enqueue_failed

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: the post-dispatch shadow hook (default-OFF) — the ONE behavior commit

**Files:**
- Modify: `core/cognition/grounding_shadow.py` (add the `shadow_observe` hook + default-off gate)
- Modify: `core/safety/audited_output.py` (the call site — wire AFTER the audited reply is dispatched)
- Test: `tests/test_grounding_shadow.py`

**Read first:** `core/safety/audited_output.py` — it wraps `audit()` to produce the displayed reply. Find the point where the audited text has been produced and is being returned/dispatched to the surface. The hook is added there: after the reply is handed off, call `shadow_observe(...)` with the `AuditResult`. If the flag is off, `shadow_observe` returns `"disabled"` immediately (zero overhead, no shadow object built). The call must not change the returned reply.

- [ ] **Step 1: Write the failing test** (append to `tests/test_grounding_shadow.py`)

```python
class HookTests(unittest.TestCase):
    def setUp(self):
        gs.reset_shadow_singleton()           # test hook — clears the module singleton
        self.addCleanup(gs.reset_shadow_singleton)
        for k in ("MAEZ_GROUNDING_SHADOW_ENABLED", "MAEZ_GROUNDING_SHADOW_DEBUG"):
            os.environ.pop(k, None)

    def test_disabled_by_default(self):
        out = gs.shadow_observe(_FakeAudit(), CLAIMABLE, surface="telegram",
                                boot_id="b", shadow_id="s", ts=1)
        self.assertEqual(out, "disabled")

    def test_enabled_enqueues(self):
        os.environ["MAEZ_GROUNDING_SHADOW_ENABLED"] = "1"
        shadow = gs.GroundingShadow(FakeSupportVerifier(), tempfile.mkstemp(suffix=".jsonl")[1], maxsize=4)
        gs.set_shadow_singleton(shadow)        # test hook — inject a Fake-backed shadow
        out = gs.shadow_observe(_FakeAudit(), CLAIMABLE, surface="telegram",
                                boot_id="b", shadow_id="s", ts=1)
        self.assertEqual(out, "enqueued")

    def test_observe_never_raises_and_returns_promptly(self):
        os.environ["MAEZ_GROUNDING_SHADOW_ENABLED"] = "1"
        # a shadow whose verifier would sleep — but enqueue must return immediately,
        # proving the serve path does not await the worker.
        shadow = gs.GroundingShadow(FakeSupportVerifier(sleep_s=5.0),
                                    tempfile.mkstemp(suffix=".jsonl")[1], maxsize=4)
        gs.set_shadow_singleton(shadow)
        t0 = time.monotonic()
        out = gs.shadow_observe(_FakeAudit(), CLAIMABLE, surface="telegram",
                                boot_id="b", shadow_id="s", ts=1)
        self.assertLess(time.monotonic() - t0, 0.5)   # did NOT wait on the 5s verifier
        self.assertEqual(out, "enqueued")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow.HookTests -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'shadow_observe'`.

- [ ] **Step 3: Write minimal implementation** (append to `core/cognition/grounding_shadow.py`)

```python
import os

_SHADOW_SINGLETON = None


def _default_telemetry_path() -> str:
    # follow the repo's state/log dir convention; XDG_STATE_HOME or ~/.local/state/maez
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    d = os.path.join(base, "maez")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "grounding_shadow.jsonl")


def _get_shadow():
    """Lazily build the singleton ONLY when enabled. Returns None when disabled."""
    global _SHADOW_SINGLETON
    if not os.environ.get("MAEZ_GROUNDING_SHADOW_ENABLED"):
        return None
    if _SHADOW_SINGLETON is None:
        verifier = HttpSupportVerifier()  # 127.0.0.1:8083
        _SHADOW_SINGLETON = GroundingShadow(
            verifier, _default_telemetry_path(),
            debug=bool(os.environ.get("MAEZ_GROUNDING_SHADOW_DEBUG")))
        _SHADOW_SINGLETON.start()
    return _SHADOW_SINGLETON


def set_shadow_singleton(shadow):      # test hook
    global _SHADOW_SINGLETON
    _SHADOW_SINGLETON = shadow


def reset_shadow_singleton():          # test hook
    global _SHADOW_SINGLETON
    _SHADOW_SINGLETON = None


def shadow_observe(audit_result, claimable_items, *, surface, boot_id, shadow_id, ts) -> str:
    """Post-dispatch, non-blocking. Returns 'disabled' | 'enqueued' | 'shadow_enqueue_failed'.
    NEVER raises, NEVER blocks, NEVER changes the reply. Call AFTER the reply is served.
    """
    try:
        shadow = _get_shadow()
        if shadow is None:
            return "disabled"
        job = {
            "final_text": getattr(audit_result, "text", "") or "",
            "claimable_items": claimable_items,
            "audit_summary": audit_summary_from_result(audit_result),
            "surface": surface, "boot_id": boot_id, "shadow_id": shadow_id, "ts": ts,
        }
        return shadow.enqueue(job)
    except Exception:
        return "disabled"
```

We also need the import for `HttpSupportVerifier` at the top of `grounding_shadow.py`. Update the existing import line:

```python
from core.cognition.support_verifier import (
    SUPPORTED, UNSUPPORTED, UNAVAILABLE, HttpSupportVerifier,
)
```

- [ ] **Step 4: Write the no-transformers import-graph test** (append to `HookTests`)

```python
    def test_daemon_module_does_not_import_transformers(self):
        import sys
        # fresh import of the shadow module must not pull transformers/torch
        for m in [k for k in sys.modules if k.startswith(("transformers", "torch"))]:
            del sys.modules[m]
        import importlib
        importlib.reload(gs)
        self.assertNotIn("transformers", sys.modules)
        self.assertNotIn("torch", sys.modules)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow -v`
Expected: PASS (all, incl. the 4 new HookTests).

- [ ] **Step 6: Wire the call site in `audited_output.py`**

The display entry point is `audit_assistant_text(text, *, surface, evidence_envelope=None, ...) -> str` (`core/safety/audited_output.py:67`). On its MAIN path it computes `result = _audit(text, surface=surface, ..., evidence_envelope=evidence_envelope)` (`:205`, an `AuditResult`) and returns `result.text`. Add the non-blocking observe on that main path, immediately before `return result.text`. The claimable items live in `evidence_envelope["claimable"]`.

```python
import os
import time
import uuid
from core.cognition.grounding_shadow import shadow_observe

# ... existing main path: result = _audit(text, surface=surface, ..., evidence_envelope=evidence_envelope)
# immediately before `return result.text`, fire-and-forget (never blocks, never alters result):
try:
    shadow_observe(
        result,
        (evidence_envelope or {}).get("claimable"),
        surface=surface,
        boot_id=os.environ.get("MAEZ_BOOT_ID"),
        shadow_id=uuid.uuid4().hex,
        ts=int(time.time()),
    )
except Exception:
    pass
return result.text
```

The early-return/degraded paths (judge unavailable, audit raised → raw `text` returned) are OUT of v0 scope — no `AuditResult` exists there, so the shadow does not run on them. Only the normal-audit path is shadowed in v0. `shadow_observe` itself is a no-op when the flag is unset, so this line is inert by default.

- [ ] **Step 7: Write the reply-unchanged test** (append to `HookTests`)

The prime-directive guarantee: wiring the shadow in must not change the served reply, even when the verifier raises. Mock `_audit` so the test is deterministic (no live judge), then compare the returned text with the shadow OFF vs ON+erroring.

```python
    def test_call_site_keeps_reply_unchanged(self):
        from unittest import mock
        from core.safety import audited_output
        from core.safety.self_claim_audit import AuditResult
        fixed = AuditResult(text="The corrected reply.", rewritten=True, mode="sentence", flags=[])
        env = {"claimable": CLAIMABLE}
        with mock.patch.object(audited_output, "_audit", return_value=fixed):
            out_off = audited_output.audit_assistant_text("raw", surface="telegram", evidence_envelope=env)
            os.environ["MAEZ_GROUNDING_SHADOW_ENABLED"] = "1"
            gs.set_shadow_singleton(gs.GroundingShadow(
                FakeSupportVerifier(raises=RuntimeError("boom")),
                tempfile.mkstemp(suffix=".jsonl")[1], maxsize=4))
            out_on = audited_output.audit_assistant_text("raw", surface="telegram", evidence_envelope=env)
        self.assertEqual(out_off, out_on)            # byte-identical — the prime directive
        self.assertEqual(out_on, "The corrected reply.")
```

NOTE: if `audit_assistant_text`'s real signature needs extra kwargs, or earlier guards (`scrub_canary_leakage`, signal assembly) interfere, adapt the call — but keep the `out_off == out_on` assertion. If it cannot pass honestly, STOP and escalate (do not weaken the assertion).

- [ ] **Step 8: Run the focused suites + the touched-module floor**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow tests.test_self_claim_audit -v`
Expected: PASS. Then run `ruff check core/cognition/grounding_shadow.py core/cognition/support_verifier.py core/safety/audited_output.py` — clean.

- [ ] **Step 9: Commit (the ONE behavior commit — carries `## Predicted effect`)**

```bash
git add core/cognition/grounding_shadow.py core/safety/audited_output.py tests/test_grounding_shadow.py
git commit -m "feat(grounding-shadow): post-dispatch shadow hook (default-OFF, observation-only)

## Predicted effect
With MAEZ_GROUNDING_SHADOW_ENABLED unset (default), zero behavior change — shadow_observe
returns 'disabled' before building anything. When enabled, after a reply is served the path
makes one non-blocking enqueue onto a bounded queue; a background worker writes content-light
divergence telemetry. The served reply is byte-identical and undelayed in all cases. No gating.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: the out-of-process MiniCheck service + systemd unit (owner-gated; NOT started)

**Files:**
- Create: `scripts/minicheck_verifier_service.py`
- Create: `scripts/maez-minicheck-verifier.template.service`
- Test: `tests/test_minicheck_verifier_service.py`

**Read first:** `scripts/fast_reply_service.py` for the repo's HTTP-service + service-unit conventions; follow them. This is the ONLY module that imports `torch`/`transformers`. The MiniCheck call shape is the one confirmed in the audition (`scripts/grounding_bench/verifiers.py:MinicheckVerifier`): `tokenizer(evidence, claim, truncation=True, max_length=2048, return_tensors="pt")` → `argmax(logits)`, label `1` == SUPPORTED. **The real-model load + first inference is the OWNER's smoke (Task 8) — do NOT run it here.** The test mocks `_predict` so the HTTP shape is covered without the model.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_minicheck_verifier_service.py
import json
import unittest
from unittest import mock
import importlib.util
import pathlib

_SPEC = importlib.util.spec_from_file_location(
    "minicheck_verifier_service",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "minicheck_verifier_service.py")


class ServiceShapeTests(unittest.TestCase):
    def _load(self):
        mod = importlib.util.module_from_spec(_SPEC)
        _SPEC.loader.exec_module(mod)
        return mod

    def test_handle_support_maps_predict_to_json(self):
        mod = self._load()
        with mock.patch.object(mod, "_predict", return_value=("SUPPORTED", 0.91)):
            body = mod.handle_support({"evidence": "ev", "claim": "cl"})
        self.assertEqual(body, {"verdict": "SUPPORTED", "score": 0.91})

    def test_handle_support_missing_fields(self):
        mod = self._load()
        body = mod.handle_support({})
        self.assertIn("error", body)

    def test_module_loads_without_touching_model(self):
        # importing the service module must NOT load torch/transformers (lazy in _predict)
        self._load()  # no exception, no eager model load
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_minicheck_verifier_service -v`
Expected: FAIL — file does not exist.

- [ ] **Step 3: Write the service**

```python
# scripts/minicheck_verifier_service.py
"""Out-of-process MiniCheck verifier service (claimable-entailment).

The ONLY place torch/transformers loads. The daemon speaks HTTP to it on
127.0.0.1:8083 and never imports this. Owner-gated: the owner starts the
systemd unit; the first request lazily loads the model.

  POST /support  {"evidence": "...", "claim": "..."}  ->  {"verdict": "...", "score": 0.x}
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

_REPO = "lytang/MiniCheck-DeBERTa-v3-Large"
_MODEL = None
_TOK = None


def _load():
    global _MODEL, _TOK
    if _MODEL is None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        _TOK = AutoTokenizer.from_pretrained(_REPO)
        _MODEL = AutoModelForSequenceClassification.from_pretrained(_REPO)
    return _MODEL, _TOK


def _predict(evidence: str, claim: str):
    import torch
    model, tok = _load()
    inputs = tok(evidence, claim, truncation=True, max_length=2048, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    label = int(torch.argmax(logits, dim=-1).item())
    score = float(torch.softmax(logits, dim=-1)[0, 1].item())
    return ("SUPPORTED" if label == 1 else "UNSUPPORTED"), score


def handle_support(payload: dict) -> dict:
    evidence, claim = payload.get("evidence"), payload.get("claim")
    if not evidence or not claim:
        return {"error": "evidence and claim are required"}
    verdict, score = _predict(evidence, claim)
    return {"verdict": verdict, "score": score}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.rstrip("/") != "/support":
            self.send_error(404)
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            body = handle_support(payload)
            code = 400 if "error" in body else 200
        except Exception as e:  # noqa
            body, code = {"error": str(e)}, 500
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def main():
    HTTPServer(("127.0.0.1", 8083), Handler).serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_minicheck_verifier_service -v`
Expected: PASS (3 tests; no model loaded).

- [ ] **Step 5: Write the systemd unit template** (mirror `scripts/maez.template.service` conventions)

```ini
# scripts/maez-minicheck-verifier.template.service
# Owner installs to ~/.config/systemd/user/minicheck-verifier.service and starts it
# as the witness breath. NOT started by the merge.
[Unit]
Description=Maez MiniCheck claimable-entailment verifier (out-of-process)
After=default.target

[Service]
Type=simple
ExecStart=/home/rohit/maez/.venv/bin/python -B /home/rohit/maez/scripts/minicheck_verifier_service.py
Restart=on-failure
# CPU only — no GPU; the daemon never loads this model.
Environment=CUDA_VISIBLE_DEVICES=

[Install]
WantedBy=default.target
```

- [ ] **Step 6: Commit**

```bash
git add scripts/minicheck_verifier_service.py scripts/maez-minicheck-verifier.template.service tests/test_minicheck_verifier_service.py
git commit -m "feat(grounding-shadow): out-of-process MiniCheck verifier service + systemd unit (inert)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: STOP-AT-GATE handoff doc

**Files:**
- Create: `docs/handoffs/2026-06-11-minicheck-grounding-shadow-gate.md`

- [ ] **Step 1: Run the full touched-module floor and record it**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_support_verifier tests.test_grounding_shadow tests.test_minicheck_verifier_service tests.test_self_claim_audit -v`
Record the pass count. Run `ruff check core/cognition/ scripts/minicheck_verifier_service.py` — clean.

- [ ] **Step 2: Write the handoff doc**

Content must state: what's built (the 4 modules + tests, all green with the Fake); that the daemon imports no `transformers` (the import-graph test); that the shadow is default-OFF and observation-only; and the **owner witness-breath sequence** (the only remaining steps, none taken by the implementer):
1. Cross-lane covenant review (Codex/owner) — focus: reply-unchanged guarantee, the post-dispatch placement on `AuditResult.text`, content-light telemetry, bounded-queue/`shadow_enqueue_failed`.
2. Owner installs + starts `minicheck-verifier.service` (the model is already downloaded from the audition; first load is the owner's breath).
3. Owner-gated smoke: `POST 127.0.0.1:8083/support` a sanity pair ("The sky is blue." / "The sky is blue." → SUPPORTED; / "The sky is green." → UNSUPPORTED) to **confirm the call shape**; adapt the service if it differs — do NOT force it.
4. Owner flips `MAEZ_GROUNDING_SHADOW_ENABLED=1` (+ optional `MAEZ_GROUNDING_SHADOW_DEBUG=1`) and restarts the daemon.
5. Read `~/.local/state/maez/grounding_shadow.jsonl` — the divergence telemetry. Decide (v0.1) whether MiniCheck's live false-positive behavior justifies a gating rail (with the two-sided-pressure discipline) and recency handling.

- [ ] **Step 3: Commit**

```bash
git add docs/handoffs/2026-06-11-minicheck-grounding-shadow-gate.md
git commit -m "docs(grounding-shadow): STOP-AT-GATE handoff — cross-lane review + owner witness breath

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review notes (for the implementer)
- **Reply-unchanged is the prime directive.** Tasks 5 (enqueue non-blocking/never-raises), 6 (disabled-by-default, returns-promptly, call-site-keeps-reply-unchanged) are the load-bearing tests. If any cannot be made to pass honestly against the real `audited_output` seam, STOP and escalate — do not weaken the test.
- **Never import `transformers` outside `scripts/minicheck_verifier_service.py`.** The Task 6 import-graph test guards this.
- **Do not start the service, flip the flag, restart the daemon, or download anything.** Those are owner breaths (Task 8 documents them).
- **Status enum** (`grounding_shadow`): `ok` | `verifier_unavailable` | `no_claimable` | `no_sentences` | `budget_exceeded` | `shadow_enqueue_failed`. (Spec's `timeout` is subsumed into `verifier_unavailable` in v0 — noted in `compute_shadow`'s docstring.)
- **Method/field names** used across tasks: `support(evidence, claim, timeout_s)`, `compute_shadow(...)`, `build_telemetry(...)`, `audit_summary_from_result(...)`, `GroundingShadow(verifier, telemetry_path, maxsize=, ...)`, `enqueue/start/stop`, `shadow_observe(audit_result, claimable_items, surface=, boot_id=, shadow_id=, ts=)`, `set_shadow_singleton/reset_shadow_singleton`. Keep them identical.
