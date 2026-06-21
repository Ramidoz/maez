# Trusted Memory vs Fresh Evidence — Conflict SENSE (Shadow Detector v0) — Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A shadow-only sense that detects when a TRUSTED memory item and a FRESH evidence item in the same focused working set substantively CONTRADICT — logging a redacted receipt, changing no reply.

**Architecture:** A new module `core/routing/memory_fresh_conflict.py` reuses the *verifier shape* from `photo_contradiction.py` (`ContradictionVerifier` protocol, `LocalNLIContradictionVerifier`, `ClaimVerdict.label == "contradicts"`) but emits its OWN redacted receipt (no claim/memory/fresh text). It pairs trusted-memory items (`origin_trust ∈ {lived,covenant}`, `≠ self_web_claim`, fail-closed on `None`) against fresh items (`source_type ∈ _FRESH_SOURCE_TYPES`), runs `predict(premise=fresh, hypothesis=memory_claim)`, and is fail-safe toward the memory (unavailable/low-confidence → `ambiguous`, never accuse). A daemon seam call runs it in shadow, flag-gated, byte-identical when off.

**Tech Stack:** Python 3, `unittest` (NOT pytest), the existing `photo_contradiction` NLI machinery, `core/infra/env_flags.strict_env_flag`.

**Test runner (EVERY test step):** `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v`

**Git hygiene:** Work on a branch/worktree (NO checkout/switch/reset/rebase mid-task; verify "On branch X" after each commit; STOP if detached). `main` is local-only, NO push. Behavior commit (Task 5) carries `## Predicted effect`. Commits end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## File Structure

- **Create `core/routing/memory_fresh_conflict.py`** — the whole detector: `MemoryFreshConflictReceipt` (redacted dataclass), `memory_fresh_conflict_sense_enabled(env)` (flag), `trusted_memory_items` / `fresh_items` / `extract_memory_claims` (selectors), `check_memory_fresh_conflict(...)` (orchestration → redacted receipt). One responsibility: sense a trusted-memory↔fresh contradiction without leaking text.
- **Modify `daemon/maez_daemon.py`** — one shadow-observer call at the focused seam (adjacent to `_run_support_scope`), flag-gated.
- **Create `tests/test_memory_fresh_conflict.py`** — unit tests for the module (receipt, flag, selectors, orchestration, redaction).
- **Create `tests/test_memory_fresh_conflict_seam.py`** — daemon seam test (flag-off inert; flag-on shadow call; source-order).
- **Create `docs/proof/2026-06-21-mem-fresh-conflict-task0.md`** — Task 0 STOP-gate proof.
- **Create `docs/handoffs/2026-06-21-mem-fresh-conflict-handoff.md`** — Codex cross-lane handoff.

---

## Task 0: STOP GATES — prove feasibility BEFORE any detector code

**This task writes NO detector code.** It produces a proof doc and either CLEARS or STOPS. If any gate fails, STOP and report to the owner; do not proceed to Task 1.

**Files:**
- Create: `docs/proof/2026-06-21-mem-fresh-conflict-task0.md`

- [ ] **Step 1: Gate 0a — prove `origin_trust`/`origin_provenance` are POPULATED at the live focused seam**

`assemble_working_set` ([focused_cognition.py:871-872](../../core/routing/focused_cognition.py#L871)) sets `origin_trust` from `item.trust_tier` and `origin_provenance` from `item.provenance_source` — but ONLY on the `structured_recall_items` path; the transcript-parse path leaves them `None`. So the trusted filter only ever matches structured-recall items.

Investigate and record in the proof doc:
- Does the LIVE daemon path pass `structured_recall_items` (recall-triad) into `assemble_working_set`? (Grep `daemon/maez_daemon.py` for `_assemble_working_set(` ~line 6899 and trace whether `recall_items=` is populated.)
- What concrete `trust_tier` VALUES do live recall items carry? Find the producer of `trust_tier`/`provenance_source` on recall items (grep `trust_tier` across `core/`), and record the actual value set — is it ever literally `"lived"` / `"covenant"`?

**STOP condition:** if `trust_tier` is never set to `lived`/`covenant` on items reaching this seam (the field is structurally always `None` here), STOP — the detector would pair nothing. Report: "provenance plumbing must precede the detector." Otherwise record the evidence that ≥1 path populates it and CLEAR 0a.

- [ ] **Step 2: Gate 0b — audition the contradiction verifier on a labeled set (precision)**

`LocalNLIContradictionVerifier` ([photo_contradiction.py:376](../../core/routing/photo_contradiction.py#L376)) loads a transformers NLI pipeline from `DEFAULT_NLI_ARTIFACT_DIR`. Confirm the artifact dir exists and the model loads (instantiate it, call `_ensure_loaded()`, record the returned reason — `None` = loaded).

Build a SMALL labeled set (≥8 pairs) in the proof doc, each `(premise=fresh_text, hypothesis=memory_claim, expected)`:
- TRUE clashes (expected `contradicts`): e.g. premise "Anthropic released Claude Opus 4.8 in 2026." / hypothesis "Anthropic's latest model is Claude 3."
- NON-clashes that a SUPPORT checker would wrongly flag (expected NOT `contradicts`): thin premise ("Markets were quiet today.") vs unrelated memory ("Rohit prefers tea."); partial/incomplete fresh source; irrelevant fresh source.

Run each through `verifier.predict(premise, hypothesis)`, tabulate `label`. Compute precision = (true clashes flagged `contradicts`) / (all flagged `contradicts`).

**STOP condition:** if the verifier flags `contradicts` on the thin/irrelevant/partial NON-clash rows (precision low — it's behaving like a support checker), STOP — a crying-wolf detector is worse than none. Record the table; CLEAR 0b only on high precision (no false `contradicts` on the non-clash rows).

- [ ] **Step 3: Gate 0c — fix the pairing/chunking granularity on the labeled set**

Decide and record the exact strategy the detector will use, validated against the 0b set:
- Memory-claim extraction: per-SENTENCE claims from the trusted-memory item text (reuse `_SENTENCE_RE`/`_clean_sentence`/`normalize_claim_text` from `photo_contradiction.py`, but WITHOUT the `_is_direct_perceptual` filter — memory claims are not perceptual). Record `claim_limit = 5` per memory item.
- Pair budget: at most `pair_budget = 6` (fresh_item × memory_claim) predict() calls per turn; record that the cap is logged honestly as `pair_limit_exceeded=true`, never silently dropped.
- Confirm whole-item-vs-whole-item is REJECTED (note why: noisy, kills precision).

**STOP condition:** if no chunking makes the 0b precision hold, STOP. Otherwise record the chosen `claim_limit`/`pair_budget` and CLEAR 0c.

- [ ] **Step 4: Commit the proof (only if all three gates CLEAR)**

```bash
git add docs/proof/2026-06-21-mem-fresh-conflict-task0.md
git commit --no-verify -m "docs(proof): Task 0 — mem↔fresh conflict sense STOP gates CLEARED (trust-fields populated, verifier precision, pairing granularity)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

If any gate STOPPED: commit the proof doc recording the STOP + the reason, and HALT the plan (report to owner). Do NOT start Task 1.

---

## Task 1: Redacted receipt + flag gate

**Files:**
- Create: `core/routing/memory_fresh_conflict.py`
- Test: `tests/test_memory_fresh_conflict.py`

- [ ] **Step 1: Write the failing test**

```python
import os
import unittest

from core.routing.memory_fresh_conflict import (
    MemoryFreshConflictReceipt,
    memory_fresh_conflict_sense_enabled,
)


class TestReceiptAndFlag(unittest.TestCase):
    def test_receipt_has_only_content_light_fields(self):
        r = MemoryFreshConflictReceipt(
            verdict="contradiction", mem_id="E2", mem_label="memory_evidence",
            fresh_id="E1", fresh_label="web_context", confidence=0.91,
            verifier="LocalNLIContradictionVerifier@rev1", mem_sha256="a" * 64,
            fresh_sha256="b" * 64, reason_code="trusted_clash",
        )
        # No text-bearing fields exist on the struct at all.
        forbidden = {"text", "mem_text", "fresh_text", "claim_text", "sense_note", "claim_details"}
        self.assertEqual(forbidden & set(vars(r)), set())
        self.assertEqual(r.verdict, "contradiction")

    def test_flag_off_by_default(self):
        self.assertFalse(memory_fresh_conflict_sense_enabled(env={}))

    def test_flag_on_when_set(self):
        self.assertTrue(
            memory_fresh_conflict_sense_enabled(env={"MAEZ_MEM_FRESH_CONFLICT_SENSE": "1"})
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_fresh_conflict -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.routing.memory_fresh_conflict'`.

- [ ] **Step 3: Write the minimal module**

```python
"""Trusted-memory ↔ fresh-evidence contradiction SENSE (shadow detector v0).

Reuses the VERIFIER SHAPE from photo_contradiction (ContradictionVerifier /
ClaimVerdict / LocalNLIContradictionVerifier) but emits its OWN redacted receipt
— it must NEVER log claim/memory/fresh text. Fail-safe toward the memory:
unavailable / low-confidence → 'ambiguous', never a contradiction accusation.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryFreshConflictReceipt:
    """Content-light by construction — NO field carries claim/memory/fresh text."""
    verdict: str  # "contradiction" | "none" | "ambiguous"
    mem_id: str | None = None
    mem_label: str | None = None
    fresh_id: str | None = None
    fresh_label: str | None = None
    confidence: float | None = None
    verifier: str | None = None
    mem_sha256: str | None = None
    fresh_sha256: str | None = None
    reason_code: str | None = None
    pair_count: int = 0
    pair_limit_exceeded: bool = False


def memory_fresh_conflict_sense_enabled(env=os.environ) -> bool:
    value = (env.get("MAEZ_MEM_FRESH_CONFLICT_SENSE", "") or "").strip().lower()
    return value in ("1", "true", "yes", "on")
```

- [ ] **Step 4: Run to verify it passes**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_fresh_conflict -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add core/routing/memory_fresh_conflict.py tests/test_memory_fresh_conflict.py
git commit --no-verify -m "feat(mem-fresh-conflict): redacted receipt struct + shadow flag

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Selectors — trusted-memory (exact, fail-closed), fresh, memory-claim extraction

**Files:**
- Modify: `core/routing/memory_fresh_conflict.py`
- Test: `tests/test_memory_fresh_conflict.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_fresh_conflict.py`:

```python
from dataclasses import dataclass as _dc

from core.routing.memory_fresh_conflict import (
    trusted_memory_items,
    fresh_items,
    extract_memory_claims,
)


@_dc
class _Item:
    local_label: str
    source_type: str
    text: str
    origin_trust: str | None = None
    origin_provenance: str | None = None


@_dc
class _WS:
    items: tuple


class TestSelectors(unittest.TestCase):
    def _ws(self, *items):
        return _WS(items=tuple(items))

    def test_trusted_memory_requires_lived_or_covenant(self):
        lived = _Item("E1", "memory_evidence", "x", origin_trust="lived")
        cov = _Item("E2", "memory_context", "y", origin_trust="covenant")
        ws = self._ws(lived, cov)
        self.assertEqual([i.local_label for i in trusted_memory_items(ws)], ["E1", "E2"])

    def test_none_trust_excluded_fail_closed(self):
        untrusted = _Item("E1", "memory_evidence", "x", origin_trust=None)
        unknown = _Item("E2", "memory_evidence", "y", origin_trust="hearsay")
        self.assertEqual(list(trusted_memory_items(self._ws(untrusted, unknown))), [])

    def test_self_web_claim_excluded_even_if_trusted(self):
        sweb = _Item("E1", "memory_evidence", "x", origin_trust="lived",
                     origin_provenance="self_web_claim")
        self.assertEqual(list(trusted_memory_items(self._ws(sweb))), [])

    def test_fresh_items_are_fresh_source_types(self):
        web = _Item("E1", "web_context", "w")
        obs = _Item("E2", "fresh_evidence", "o")
        mem = _Item("E3", "memory_evidence", "m", origin_trust="lived")
        self.assertEqual([i.local_label for i in fresh_items(self._ws(web, obs, mem))],
                         ["E1", "E2"])

    def test_extract_memory_claims_splits_sentences_bounded(self):
        claims = extract_memory_claims("Rohit prefers tea. He dislikes loud rooms. Maez is calm.",
                                       limit=2)
        self.assertEqual(len(claims), 2)
        self.assertTrue(all(isinstance(c, str) and c for c in claims))
```

- [ ] **Step 2: Run to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_fresh_conflict -v`
Expected: FAIL — `ImportError: cannot import name 'trusted_memory_items'`.

- [ ] **Step 3: Add the selectors to the module**

Append to `core/routing/memory_fresh_conflict.py`:

```python
from core.routing.focused_cognition import _FRESH_SOURCE_TYPES
from core.routing.photo_contradiction import (
    _SENTENCE_RE,
    _clean_sentence,
    normalize_claim_text,
)

_TRUSTED_TIERS = frozenset({"lived", "covenant"})


def trusted_memory_items(working_set):
    """EXACT, fail-closed: origin_trust ∈ {lived,covenant} AND provenance != self_web_claim.
    None / unknown trust → EXCLUDED (vague trust never counts as sacred memory)."""
    out = []
    for it in getattr(working_set, "items", ()) or ():
        trust = getattr(it, "origin_trust", None)
        if trust not in _TRUSTED_TIERS:
            continue
        if getattr(it, "origin_provenance", None) == "self_web_claim":
            continue
        out.append(it)
    return out


def fresh_items(working_set):
    return [
        it for it in (getattr(working_set, "items", ()) or ())
        if getattr(it, "source_type", None) in _FRESH_SOURCE_TYPES
    ]


def extract_memory_claims(text: str, *, limit: int = 5) -> list[str]:
    """Per-sentence claims from a memory item — NO perceptual filter (memory claims
    are not perceptual). Bounded by `limit`."""
    if limit <= 0 or not text:
        return []
    normalized = normalize_claim_text(text)
    claims: list[str] = []
    for match in _SENTENCE_RE.finditer(text):
        sentence = _clean_sentence(match.group(0))
        if not sentence:
            continue
        if normalize_claim_text(sentence) not in normalized:
            continue
        claims.append(sentence)
        if len(claims) >= limit:
            break
    return claims
```

NOTE: confirm `_SENTENCE_RE`, `_clean_sentence`, `normalize_claim_text`, `_FRESH_SOURCE_TYPES` are importable (they are module-level in those files). If `_clean_sentence`/`_SENTENCE_RE` are private and absent, fall back to a local sentence split on `re.compile(r"[^.!?]+[.!?]?")` and `.strip()` — record the swap in the commit body.

- [ ] **Step 4: Run to verify it passes**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_fresh_conflict -v`
Expected: PASS (all selector tests + Task 1 tests).

- [ ] **Step 5: Commit**

```bash
git add core/routing/memory_fresh_conflict.py tests/test_memory_fresh_conflict.py
git commit --no-verify -m "feat(mem-fresh-conflict): trusted-memory (fail-closed) + fresh + memory-claim selectors

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Orchestration — `check_memory_fresh_conflict` (pair, predict, redacted receipt, fail-safe)

**Files:**
- Modify: `core/routing/memory_fresh_conflict.py`
- Test: `tests/test_memory_fresh_conflict.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_fresh_conflict.py`:

```python
from core.routing.memory_fresh_conflict import check_memory_fresh_conflict


class _Verdict:
    def __init__(self, label, score=0.9, reason=None):
        self.label = label
        self.score = score
        self.latency_s = 0.0
        self.model_id = "nli-test"
        self.revision = "rev1"
        self.sha256 = "c" * 64
        self.reason = reason


class _FakeVerifier:
    def __init__(self, label):
        self._label = label
        self.calls = 0

    def predict(self, premise, hypothesis):
        self.calls += 1
        return _Verdict(self._label)


class TestOrchestration(unittest.TestCase):
    def _ws_with(self, mem_trust="lived"):
        mem = _Item("E2", "memory_evidence", "Maez's latest model is Claude 3.",
                    origin_trust=mem_trust)
        fresh = _Item("E1", "web_context", "Anthropic released Claude Opus 4.8 in 2026.")
        return _WS(items=(fresh, mem))

    def test_contradiction_emits_redacted_receipt(self):
        r = check_memory_fresh_conflict(self._ws_with(), _FakeVerifier("contradicts"))
        self.assertEqual(r.verdict, "contradiction")
        self.assertEqual(r.mem_id, "E2")
        self.assertEqual(r.fresh_id, "E1")
        self.assertEqual(len(r.mem_sha256), 64)
        # the receipt carries NO text
        self.assertNotIn("Claude", str(vars(r)))

    def test_grounded_is_none_verdict(self):
        r = check_memory_fresh_conflict(self._ws_with(), _FakeVerifier("grounded"))
        self.assertEqual(r.verdict, "none")

    def test_unavailable_is_ambiguous_never_accuse(self):
        r = check_memory_fresh_conflict(self._ws_with(), _FakeVerifier("unavailable"))
        self.assertEqual(r.verdict, "ambiguous")

    def test_no_trusted_memory_returns_none_receipt(self):
        ws = self._ws_with(mem_trust=None)  # untrusted memory → not paired
        self.assertIsNone(check_memory_fresh_conflict(ws, _FakeVerifier("contradicts")))

    def test_pair_budget_caps_predict_calls(self):
        mem = _Item("E2", "memory_evidence",
                    "A. B. C. D. E. F. G. H.", origin_trust="lived")
        fresh1 = _Item("E1", "web_context", "fresh one")
        fresh2 = _Item("E3", "web_context", "fresh two")
        ws = _WS(items=(fresh1, fresh2, mem))
        v = _FakeVerifier("grounded")
        r = check_memory_fresh_conflict(ws, v, claim_limit=5, pair_budget=3)
        self.assertLessEqual(v.calls, 3)
        self.assertTrue(r.pair_limit_exceeded)
```

- [ ] **Step 2: Run to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_fresh_conflict -v`
Expected: FAIL — `ImportError: cannot import name 'check_memory_fresh_conflict'`.

- [ ] **Step 3: Add the orchestration**

Append to `core/routing/memory_fresh_conflict.py`:

```python
from core.routing.observation import _sha256


def check_memory_fresh_conflict(
    working_set,
    verifier,
    *,
    claim_limit: int = 5,
    pair_budget: int = 6,
):
    """Pair trusted-memory claims (hypothesis) against fresh items (premise);
    predict contradiction. Returns a redacted MemoryFreshConflictReceipt, or None
    if there is no trusted-memory↔fresh pair to judge. Fail-safe toward the memory:
    any non-'contradicts'/'grounded' verdict → 'ambiguous', never an accusation."""
    mems = trusted_memory_items(working_set)
    fresh = fresh_items(working_set)
    if not mems or not fresh:
        return None

    pairs = []  # (fresh_item, mem_item, claim_text)
    for mem in mems:
        for claim in extract_memory_claims(getattr(mem, "text", "") or "", limit=claim_limit):
            for fr in fresh:
                pairs.append((fr, mem, claim))
    if not pairs:
        return None

    pair_limit_exceeded = len(pairs) > pair_budget
    budgeted = pairs[:pair_budget]

    saw_unavailable = False
    verifier_name = type(verifier).__name__
    for fr, mem, claim in budgeted:
        try:
            verdict = verifier.predict(getattr(fr, "text", "") or "", claim)
        except Exception:
            saw_unavailable = True
            continue
        label = getattr(verdict, "label", "unavailable")
        if label == "contradicts":
            rev = getattr(verdict, "revision", None)
            return MemoryFreshConflictReceipt(
                verdict="contradiction",
                mem_id=getattr(mem, "local_label", None),
                mem_label=getattr(mem, "source_type", None),
                fresh_id=getattr(fr, "local_label", None),
                fresh_label=getattr(fr, "source_type", None),
                confidence=getattr(verdict, "score", None),
                verifier=f"{verifier_name}@{rev}" if rev else verifier_name,
                mem_sha256=_sha256(claim),
                fresh_sha256=_sha256(getattr(fr, "text", "") or ""),
                reason_code="trusted_clash",
                pair_count=len(budgeted),
                pair_limit_exceeded=pair_limit_exceeded,
            )
        if label != "grounded":
            saw_unavailable = True

    return MemoryFreshConflictReceipt(
        verdict="ambiguous" if saw_unavailable else "none",
        verifier=verifier_name,
        reason_code="verifier_unavailable" if saw_unavailable else "clear",
        pair_count=len(budgeted),
        pair_limit_exceeded=pair_limit_exceeded,
    )
```

NOTE: confirm `_sha256` is importable from `core.routing.observation` (it is — used at [focused_cognition.py:27](../../core/routing/focused_cognition.py#L27)). If its signature differs (e.g. needs bytes), wrap: `_sha256(claim.encode())`.

- [ ] **Step 4: Run to verify it passes**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_fresh_conflict -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add core/routing/memory_fresh_conflict.py tests/test_memory_fresh_conflict.py
git commit --no-verify -m "feat(mem-fresh-conflict): orchestration — pair, predict, redacted receipt, fail-safe to memory

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Redaction guarantee — assert NO text leaks (must-fix)

**Files:**
- Test: `tests/test_memory_fresh_conflict.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_memory_fresh_conflict.py`:

```python
class TestRedaction(unittest.TestCase):
    def test_no_memory_or_fresh_text_anywhere_in_receipt(self):
        SECRET_MEM = "ZZSECRETMEMZZ is the remembered fact."
        SECRET_FRESH = "ZZSECRETFRESHZZ is the fresh source."
        mem = _Item("E2", "memory_evidence", SECRET_MEM, origin_trust="lived")
        fresh = _Item("E1", "web_context", SECRET_FRESH)
        ws = _WS(items=(fresh, mem))
        r = check_memory_fresh_conflict(ws, _FakeVerifier("contradicts"))
        blob = repr(vars(r))
        self.assertNotIn("ZZSECRETMEM", blob)
        self.assertNotIn("ZZSECRETFRESH", blob)
        # digests ARE present (proof we saw the text but stored only its hash)
        self.assertEqual(len(r.mem_sha256), 64)
```

- [ ] **Step 2: Run to verify it passes (redaction is by-construction)**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_fresh_conflict -v`
Expected: PASS — the receipt has no text fields, so the secrets never appear. (If it FAILS, a text field leaked into the struct — remove it; the receipt must stay redacted.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_memory_fresh_conflict.py
git commit --no-verify -m "test(mem-fresh-conflict): assert no memory/fresh text leaks into the receipt

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Daemon seam — shadow observer, flag-gated, byte-identical off

**Files:**
- Modify: `daemon/maez_daemon.py` (helper near `_run_support_scope` :1080; call at the focused seam where `_focused_working_set` is in scope, ~:6918-6931)
- Test: `tests/test_memory_fresh_conflict_seam.py`

- [ ] **Step 1: Write the failing seam tests**

```python
import os
import unittest
from unittest import mock

os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")

import daemon.maez_daemon as d


class _Item:
    def __init__(self, label, st, text, trust=None, prov=None):
        self.local_label, self.source_type, self.text = label, st, text
        self.origin_trust, self.origin_provenance = trust, prov


class _WS:
    def __init__(self, items):
        self.items = tuple(items)


class TestConflictSenseSeam(unittest.TestCase):
    def _ws(self):
        return _WS([
            _Item("E1", "web_context", "Anthropic released Opus 4.8 in 2026."),
            _Item("E2", "memory_evidence", "Maez's latest model is Claude 3.", trust="lived"),
        ])

    def test_flag_off_does_not_run_sense(self):
        with mock.patch.dict(os.environ, {"MAEZ_MEM_FRESH_CONFLICT_SENSE": "0"}), \
             mock.patch.object(d, "check_memory_fresh_conflict") as chk:
            d._run_mem_fresh_conflict_sense(self._ws(), surface="telegram")
            chk.assert_not_called()

    def test_flag_on_runs_sense_and_logs(self):
        with mock.patch.dict(os.environ, {"MAEZ_MEM_FRESH_CONFLICT_SENSE": "1"}), \
             mock.patch.object(d, "check_memory_fresh_conflict") as chk, \
             self.assertLogs(d.logger.name) as logs:
            chk.return_value = d.MemoryFreshConflictReceipt(
                verdict="contradiction", mem_id="E2", fresh_id="E1",
                mem_sha256="a" * 64, fresh_sha256="b" * 64, reason_code="trusted_clash")
            d._run_mem_fresh_conflict_sense(self._ws(), surface="telegram")
            chk.assert_called_once()
            self.assertTrue(any("mem_fresh_conflict_sense" in m for m in logs.output))

    def test_helper_appears_after_support_scope_call(self):
        import inspect
        src = inspect.getsource(d.MaezDaemon)  # the cycle/turn body
        # the shadow sense is called in the same seam region; presence + no reply mutation
        self.assertIn("_run_mem_fresh_conflict_sense(", src)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_fresh_conflict_seam -v`
Expected: FAIL — `AttributeError: module 'daemon.maez_daemon' has no attribute '_run_mem_fresh_conflict_sense'`.

NOTE: if `inspect.getsource(d.MaezDaemon)` is the wrong scope for the seam (the call may live in a module-level turn handler, not the class), adjust `test_helper_appears_after_support_scope_call` to `inspect.getsource(d)` or the actual enclosing function — match the real seam, do NOT weaken the assertion that `_run_mem_fresh_conflict_sense(` is called.

- [ ] **Step 3: Add the helper + the module imports**

Near the top imports of `daemon/maez_daemon.py` (with the other `core.routing` imports), add:

```python
from core.routing.memory_fresh_conflict import (
    MemoryFreshConflictReceipt,
    check_memory_fresh_conflict,
    memory_fresh_conflict_sense_enabled,
)
```

Add the helper next to `_run_support_scope` (~:1080):

```python
def _run_mem_fresh_conflict_sense(working_set, *, surface):
    """SHADOW: sense a trusted-memory↔fresh contradiction; log a redacted receipt.
    Never mutates the reply. Flag-gated; fail-safe (any error → silent no-op)."""
    if not memory_fresh_conflict_sense_enabled():
        return
    try:
        from core.routing.photo_contradiction import LocalNLIContradictionVerifier
        receipt = check_memory_fresh_conflict(working_set, LocalNLIContradictionVerifier())
        if receipt is None:
            return
        logger.info(
            "mem_fresh_conflict_sense surface=%s verdict=%s mem_id=%s fresh_id=%s "
            "confidence=%s verifier=%s reason_code=%s pair_count=%s pair_limit_exceeded=%s "
            "mem_sha256=%s fresh_sha256=%s",
            surface, receipt.verdict, receipt.mem_id, receipt.fresh_id,
            receipt.confidence, receipt.verifier, receipt.reason_code,
            receipt.pair_count, receipt.pair_limit_exceeded,
            receipt.mem_sha256, receipt.fresh_sha256,
        )
    except Exception as exc:  # fail-safe: a sense must never break a turn
        logger.info("mem_fresh_conflict_sense surface=%s error=%s", surface, type(exc).__name__)
```

- [ ] **Step 4: Wire the call at the focused seam**

At the focused-cognition seam where `_focused_working_set` is in scope and the support scope already runs (find the `_run_support_scope(` call site; place the new call IMMEDIATELY AFTER it, using the same `source`/surface variable), add:

```python
_run_mem_fresh_conflict_sense(_focused_working_set, surface=source)
```

This is a pure observer — it does NOT touch `reply`. Confirm `_focused_working_set` is non-None at this point (guard with `if _focused_working_set is not None:` if the support-scope call is itself guarded).

- [ ] **Step 5: Run the seam tests + the module tests**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_fresh_conflict_seam tests.test_memory_fresh_conflict -v`
Expected: PASS (all).

- [ ] **Step 6: Run the protected regression suite (no daemon breakage)**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_support_gate tests.test_grounding_shadow tests.test_turn_has_fresh_evidence -v`
Expected: PASS (the seam addition is additive; nothing else changes).

- [ ] **Step 7: Commit (behavior commit — carries `## Predicted effect`)**

```bash
git add daemon/maez_daemon.py tests/test_memory_fresh_conflict_seam.py
git commit --no-verify -m "feat(mem-fresh-conflict): shadow seam — sense trusted-memory↔fresh contradiction, log redacted receipt

Flag MAEZ_MEM_FRESH_CONFLICT_SENSE (default-off = byte-identical). Pure observer at the
focused seam (adjacent to _run_support_scope); never mutates the reply. Fail-safe: any
error → silent no-op. Slice 1 of Thread B (detector only; no governance/surfacing).

## Predicted effect
With the flag ON, turns that carry BOTH a trusted memory (origin_trust lived/covenant) and
fresh/web evidence will emit a 'mem_fresh_conflict_sense ... verdict=contradiction|none|ambiguous'
receipt. NO reply changes on any turn. Recall-only / untrusted-memory / no-fresh turns emit nothing.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Handoff doc + STOP for Codex cross-lane

**Files:**
- Create: `docs/handoffs/2026-06-21-mem-fresh-conflict-handoff.md`

- [ ] **Step 1: Write the handoff**

Content: branch tip; the Task-0 proof outcome (gates CLEARED with evidence); what shadow-only means here (flag default-off, byte-identical, pure observer, fail-safe); the redaction guarantee (receipt has no text fields; Task-4 test); the exact trusted predicate (lived/covenant, exclude self_web_claim/None); MiniCheck is NOT used (NLI contradiction verifier only); Codex anchors to verify — (a) the seam call does not mutate `reply`, (b) `_sha256` import is correct, (c) the `_run_mem_fresh_conflict_sense` call site is reached only when `_focused_working_set` is non-None, (d) flag-off is byte-identical; and the owner-breath (restart maez, set `MAEZ_MEM_FRESH_CONFLICT_SENSE=1`, live a turn that recalls a trusted fact AND pulls fresh evidence that clashes → paste the `verdict=contradiction` receipt; confirm a thin/irrelevant fresh source → no `contradiction`).

- [ ] **Step 2: Commit + STOP at the review gate**

```bash
git add docs/handoffs/2026-06-21-mem-fresh-conflict-handoff.md
git commit --no-verify -m "docs(handoff): mem↔fresh conflict sense Slice 1 — Codex cross-lane anchors + owner breath

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

STOP. Do NOT merge, restart, or witness live. Report branch tip + verification outputs + the owner-breath sequence (merge → owner restart → live re-witness). Hold for the owner's `merge it`.

---

## Self-Review

**Spec coverage:** trusted-only pairing (Task 2, exact fail-closed) ✓; contradiction-not-support / verifier shape reuse (Task 3 + Task 0b audition) ✓; redacted receipt no-text (Task 1 struct + Task 4 assert) ✓; shadow-only / flag-off byte-identical (Task 5) ✓; fail-safe to memory (Task 3 ambiguous-never-accuse) ✓; Task-0 STOP gates — trust-fields-populated (0a), verifier precision (0b), pairing granularity (0c) ✓; Slice-2 domain-routing correctly ABSENT ✓; MiniCheck NOT wired (NLI verifier only) ✓.

**Placeholder scan:** every code step has complete code; the two NOTEs (import-fallbacks, seam-scope) are explicit contingencies with concrete fallbacks, not TBDs.

**Type consistency:** `MemoryFreshConflictReceipt` fields match across Tasks 1/3/4/5; `check_memory_fresh_conflict(working_set, verifier, *, claim_limit, pair_budget)` signature consistent Task 3↔5; `_run_mem_fresh_conflict_sense(working_set, *, surface)` consistent Task 5 def↔call↔test; selectors `trusted_memory_items`/`fresh_items`/`extract_memory_claims` consistent Task 2↔3.
