# Continuity Classifier + Trust-Tier Evidence Lines — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Maez (1) recognize natural continuity phrasings ("what were we *just* talking about?") so continuity asks anchor to the recent thread, and (2) render each `[E#]`'s trust/authority kind so the brain can't treat past/context/external items as current fact.

**Architecture:** Two independently-RED-first changes in ONE file, `core/routing/focused_cognition.py`, both substrate-side and brain-swap-safe. Task 1 replaces brittle substring matching in `dialogue_continuity_state` with light normalization + a deterministic dialogue-meta regex grammar that allows filler words *in place* (no global word deletion). Task 2 adds a `source_type → authority_label` map used when rendering evidence lines, plus a trust-aware faithful instruction that preserves citation (cite-with-caveat, never forbid). Output shape `DialogueContinuityState` is unchanged; `[E#]` tokens are preserved byte-for-byte so `check_groundedness` and the merged living-recall path are untouched.

**Tech Stack:** Python 3, `unittest` (pytest is NOT installed — run `.venv/bin/python -m unittest`), `ruff`.

**Process (project switchboard):** Codex implements RED-first; Claude cross-verifies the diff + runs the live Telegram witness before any merge. Flag posture: focused cognition stays behind `MAEZ_FOCUSED_COGNITION_ENABLED`; this slice does not change the flag.

---

## File map

- **Modify** `core/routing/focused_cognition.py`:
  - Task 1: add `_normalize_continuity()` + `_DIRECT_GRAMMAR`; rewrite `dialogue_continuity_state()` body (lines ~232–274) to use them; keep `_DIRECT_CONTINUITY_PATTERNS` as a fallback.
  - Task 2: add `_AUTHORITY_LABEL` + `_authority_label()`; extract `_render_evidence_lines()` from the inline render at line ~441 and label by authority; add `_TRUST_TIER_INSTRUCTION` and inject it into `focused_synthesize`'s system block (after `_FAITHFUL_INSTRUCTION`, line ~479).
- **Modify (tests)** `tests/test_focused_cognition.py`: extend `DialogueContinuityStateTests` (line ~246) and `AssembleWorkingSetTests` (line ~20); add a small `TrustTierRenderingTests` class.

---

## Task 1: Continuity classifier — dialogue-meta grammar

**Files:**
- Modify: `core/routing/focused_cognition.py` (`dialogue_continuity_state` ~232–274; add helpers near the pattern constants ~161–186)
- Test: `tests/test_focused_cognition.py` (`DialogueContinuityStateTests`)

- [ ] **Step 1: Write the failing tests**

Add to `DialogueContinuityStateTests` in `tests/test_focused_cognition.py`:

```python
    def test_natural_phrasings_with_filler_are_direct(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        examples = [
            "What were we just talking about?",
            "What were we actually discussing?",
            "What were we just discussing?",
            "Remind me what we were covering.",
            "Where did we leave off?",
            "What were we working on?",
        ]
        for text in examples:
            with self.subTest(text=text):
                state = dialogue_continuity_state(text)
                self.assertEqual(state.kind, ContinuityKind.DIRECT)
                self.assertTrue(state.needs_dialogue)
                self.assertFalse(state.fail_safe_legacy)

    def test_content_recall_is_not_continuity(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        # Hard false-positive boundary: content-recall asks must NOT anchor.
        for text in [
            "What's the infrastructure ground-truth you noted earlier?",
            "What did you find about the GPU?",
        ]:
            with self.subTest(text=text):
                state = dialogue_continuity_state(text)
                self.assertNotEqual(state.kind, ContinuityKind.DIRECT)
                self.assertNotEqual(state.kind, ContinuityKind.ANAPHORIC)

    def test_filler_does_not_manufacture_direct_continuity(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        # "still" must not be deleted into a continuity match (no global
        # filler deletion). This stays out of DIRECT.
        state = dialogue_continuity_state("Is it still running?")
        self.assertNotEqual(state.kind, ContinuityKind.DIRECT)
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.DialogueContinuityStateTests.test_natural_phrasings_with_filler_are_direct -v`
Expected: FAIL — `"What were we just talking about?"` currently returns `kind=NONE` (the `"just"` breaks the literal substring `"what were we talking about"`).

- [ ] **Step 3: Add the normalizer + grammar**

In `core/routing/focused_cognition.py`, near the continuity pattern constants (after `_UNCERTAIN_CONTINUITY_PATTERNS`, ~line 192), add:

```python
def _normalize_continuity(text: str) -> str:
    """Lowercase, strip punctuation to spaces, collapse whitespace.

    Light normalization only — we do NOT delete filler words globally
    (that can manufacture accidental matches, e.g. removing 'still' from
    'is it still running'). Filler is absorbed by the [\\w\\s]* slots in
    the dialogue-meta grammar instead.
    """
    lowered = (text or "").lower()
    spaced = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", spaced).strip()


# Deterministic dialogue-meta grammar. DIRECT requires the dialogue-meta
# STRUCTURE: a question lead-in + a first/second person dialogue subject
# (we/us/i/you) + a conversation verb. The [\\w\\s]* gaps allow filler
# words ("just", "actually", "really") IN PLACE without global deletion.
# Content-recall asks ("what's the X you noted earlier?") lack the
# conversation verb and so do not match.
_DIRECT_GRAMMAR: tuple = (
    re.compile(
        r"\b(?:what|which|remind me)\b[\w\s]*"
        r"\b(?:we|us|i|you)\b[\w\s]*"
        r"\b(?:talk|talking|discuss|discussing|cover|covering|"
        r"doing|working|going over|say|saying|said)\b"
    ),
    re.compile(
        r"\bwhere\b[\w\s]*\b(?:we|us)\b[\w\s]*"
        r"\b(?:leave off|left off|get to|got to|were)\b"
    ),
)
```

- [ ] **Step 4: Rewrite `dialogue_continuity_state` to use them**

Replace the body of `dialogue_continuity_state` (currently lines ~232–274) with:

```python
def dialogue_continuity_state(owner_question: str) -> DialogueContinuityState:
    text = _normalize_continuity(owner_question)

    # 1. Deterministic dialogue-meta grammar (natural phrasings + filler).
    for pattern in _DIRECT_GRAMMAR:
        match = pattern.search(text)
        if match:
            return DialogueContinuityState(
                kind=ContinuityKind.DIRECT,
                needs_dialogue=True,
                fail_safe_legacy=False,
                matched_reason=match.group(0)[:60],
            )

    # 2. Legacy literal DIRECT forms the grammar doesn't cover
    #    (e.g. "before this", "before that").
    for pattern in _DIRECT_CONTINUITY_PATTERNS:
        if pattern in text:
            return DialogueContinuityState(
                kind=ContinuityKind.DIRECT,
                needs_dialogue=True,
                fail_safe_legacy=False,
                matched_reason=pattern,
            )

    # 3. Anaphoric multi-word phrases.
    for pattern in _ANAPHORIC_PHRASES:
        if pattern in text:
            return DialogueContinuityState(
                kind=ContinuityKind.ANAPHORIC,
                needs_dialogue=True,
                fail_safe_legacy=False,
                matched_reason=pattern,
            )

    # 4. Intra-turn echo instruction ("say that back") — handled elsewhere,
    #    not a continuity recall.
    if _is_intra_turn_echo_instruction(text):
        return DialogueContinuityState(
            kind=ContinuityKind.NONE,
            needs_dialogue=False,
            fail_safe_legacy=False,
            matched_reason=None,
        )

    # 5. Bare anaphoric words ("that", "this", "those", "it").
    for pattern in _ANAPHORIC_WORDS:
        if re.search(rf"\b{re.escape(pattern)}\b", text):
            return DialogueContinuityState(
                kind=ContinuityKind.ANAPHORIC,
                needs_dialogue=True,
                fail_safe_legacy=False,
                matched_reason=pattern,
            )

    # 6. Conservative uncertain markers -> legacy fail-safe (not authoritative).
    for pattern in _UNCERTAIN_CONTINUITY_PATTERNS:
        if pattern in text:
            return DialogueContinuityState(
                kind=ContinuityKind.NONE,
                needs_dialogue=False,
                fail_safe_legacy=True,
                matched_reason=pattern,
            )

    return DialogueContinuityState(
        kind=ContinuityKind.NONE,
        needs_dialogue=False,
        fail_safe_legacy=False,
        matched_reason=None,
    )
```

(This preserves the original ordering and the `DialogueContinuityState` shape; it only adds the grammar at step 1 and runs all matching over `_normalize_continuity(...)` instead of a bare `.lower()`. Confirm `_DIRECT_CONTINUITY_PATTERNS`, `_ANAPHORIC_PHRASES`, `_ANAPHORIC_WORDS`, `_UNCERTAIN_CONTINUITY_PATTERNS`, `_is_intra_turn_echo_instruction` already exist above this function — they do, at lines ~161–214.)

- [ ] **Step 5: Run to verify they pass + no regressions**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.DialogueContinuityStateTests -v`
Expected: PASS — the new tests pass AND the existing `test_direct_continuity_state`, `test_anaphoric_continuity_state`, `test_conservative_uncertain_continuity_state`, `test_bare_temporal_freshness_queries_are_not_continuity` stay green.

- [ ] **Step 6: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "fix(focused): continuity classifier — dialogue-meta grammar with in-place filler (natural phrasings now DIRECT)"
```

---

## Task 2: Trust-tier evidence rendering

**Files:**
- Modify: `core/routing/focused_cognition.py` (constants ~40–56; `assemble_working_set` render ~441; `focused_synthesize` system block ~477–482)
- Test: `tests/test_focused_cognition.py` (new `TrustTierRenderingTests`; extend `AssembleWorkingSetTests`)

- [ ] **Step 1: Write the failing tests**

Add a new class to `tests/test_focused_cognition.py`:

```python
class TrustTierRenderingTests(unittest.TestCase):
    def test_authority_label_per_source_type(self):
        from core.routing.focused_cognition import _authority_label

        self.assertEqual(
            _authority_label("web_context"),
            "external web — UNTRUSTED, informational only",
        )
        self.assertEqual(
            _authority_label("memory_context"),
            "recalled context — past background, not current state",
        )
        self.assertEqual(
            _authority_label("dialogue_anchor"),
            "recent dialogue — authoritative for continuity",
        )
        self.assertEqual(_authority_label("something_new"), "unverified")

    def test_render_uses_authority_label_and_preserves_labels(self):
        from core.routing.focused_cognition import (
            EvidenceItem,
            _render_evidence_lines,
        )

        items = [
            EvidenceItem("E1", "web_context", "rain tomorrow", "h1"),
            EvidenceItem("E2", "fresh_evidence", "cpu at 6%", "h2"),
        ]
        text = "\n".join(_render_evidence_lines(items))
        self.assertIn("external web — UNTRUSTED", text)
        self.assertIn("observed (fresh)", text)
        # [E#] tokens preserved exactly (groundedness keys on these).
        self.assertIn("[E1]", text)
        self.assertIn("[E2]", text)

    def test_trust_instruction_in_synthesize_system_block(self):
        from core.routing.focused_cognition import (
            EvidenceItem,
            WorkingSet,
            focused_synthesize,
        )

        captured = {}

        def fake_chat(*, model, messages, think, options):
            captured["system"] = messages[0]["content"]

            class _Msg:
                content = "ok [E1]"

            class _Resp:
                message = _Msg()

            return _Resp()

        ws = WorkingSet(
            items=[EvidenceItem("E1", "memory_context", "old note", "h")],
            ordered_evidence_text="[E1] (recalled context — past background, not current state) old note",
            owner_question="q",
            working_set_chars=10,
            working_set_tokens_est=2,
        )
        focused_synthesize(ws, surface="telegram_surface", chat_fn=fake_chat)
        self.assertIn("carry their caveat", captured["system"])
        self.assertIn("UNTRUSTED", captured["system"])

    def test_citation_coverage_not_reduced_by_trust_render(self):
        # Trust labels change only the rendered parenthetical, never
        # local_labels, so groundedness coverage is unchanged.
        from core.routing.focused_cognition import (
            EvidenceItem,
            FocusedResult,
            WorkingSet,
            check_groundedness,
        )

        ws = WorkingSet(
            items=[
                EvidenceItem("E1", "memory_context", "old note", "h1"),
                EvidenceItem("E2", "fresh_evidence", "live", "h2"),
            ],
            ordered_evidence_text="(unused here)",
            owner_question="q",
            working_set_chars=1,
            working_set_tokens_est=1,
        )
        result = FocusedResult(
            reply="Background per [E1].", cited_ids=["E1"], working_set_chars=1
        )
        verdict = check_groundedness(result, ws)
        self.assertEqual(verdict.verdict, "grounded")
        self.assertEqual(verdict.citation_coverage, 0.5)
        self.assertEqual(verdict.unmatched, [])
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.TrustTierRenderingTests -v`
Expected: FAIL — `_authority_label`, `_render_evidence_lines` don't exist yet; the synthesize system block lacks the trust instruction.

- [ ] **Step 3: Add the authority map + render helper**

In `core/routing/focused_cognition.py`, after `_SOURCE_TYPE`/`_PRIORITY` (~line 50), add:

```python
_AUTHORITY_LABEL: dict[str, str] = {
    "fresh_evidence": "observed (fresh) — current-state authority",
    "memory_evidence": "recalled memory — past authority, not current state",
    "memory_context": "recalled context — past background, not current state",
    "dialogue_anchor": "recent dialogue — authoritative for continuity",
    "web_context": "external web — UNTRUSTED, informational only",
    "empty_result": "no evidence",
}


def _authority_label(source_type: str) -> str:
    return _AUTHORITY_LABEL.get(source_type, "unverified")


def _render_evidence_lines(items) -> list:
    """Render each evidence item as '[E#] (authority) text'.

    The parenthetical carries the trust/authority KIND (not the internal
    source_type), so the brain can tell a witnessed fact from past context
    or an UNTRUSTED web result. The [E#] token is preserved exactly so
    check_groundedness (which keys on local_label) is unaffected.
    """
    lines = [
        f"[{item.local_label}] ({_authority_label(item.source_type)}) {item.text}"
        for item in items
    ]
    if items:
        top = items[0]
        lines.append(f"(most important, repeated) [{top.local_label}] {top.text}")
    return lines
```

- [ ] **Step 4: Use the helper in `assemble_working_set`**

Replace the inline render (currently lines ~441–444):

```python
    lines = [f"[{item.local_label}] ({item.source_type}) {item.text}" for item in items]
    top = items[0]
    lines.append(f"(most important, repeated) [{top.local_label}] {top.text}")
    ordered = "\n".join(lines)
```

with:

```python
    ordered = "\n".join(_render_evidence_lines(items))
```

(`items` is non-empty here — the function already returned `None` at the `if not raw_items` guard above, and `items` is built from `raw_items`.)

- [ ] **Step 5: Add the trust instruction + inject it into `focused_synthesize`**

After `_FAITHFUL_INSTRUCTION` (~line 56), add:

```python
_TRUST_TIER_INSTRUCTION = (
    "Each [E#] is tagged with its authority. Cite the [E#] you use — including "
    "context, external-web, or recent-dialogue items — but carry their caveat: "
    "do not upgrade them into witnessed or current fact. Only 'observed (fresh)' "
    "or tool-verified data is current-state authority; 'recalled memory' is "
    "authority about the past, not the present; 'recalled context' is background; "
    "'recent dialogue' is authoritative for continuity (what we were discussing), "
    "not for general facts; 'external web — UNTRUSTED' must be hedged."
)
```

In `focused_synthesize`, change the system assembly (lines ~477–482) from:

```python
    system = (
        f"{_voice_card(surface)}\n\n"
        f"{_FAITHFUL_INSTRUCTION}\n\n"
        f"=== EVIDENCE (cite [E#]) ===\n"
        f"{working_set.ordered_evidence_text}"
    )
```

to:

```python
    system = (
        f"{_voice_card(surface)}\n\n"
        f"{_FAITHFUL_INSTRUCTION}\n\n"
        f"{_TRUST_TIER_INSTRUCTION}\n\n"
        f"=== EVIDENCE (cite [E#]) ===\n"
        f"{working_set.ordered_evidence_text}"
    )
```

- [ ] **Step 6: Run to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition.TrustTierRenderingTests -v`
Expected: PASS (all four).

- [ ] **Step 7: Run the full focused-cognition suite + lint**

Run: `.venv/bin/python -m unittest tests.test_focused_cognition -v`
Expected: PASS (no regression in `AssembleWorkingSetTests`, `DialogueContinuityStateTests`, honest-empty tests).
Run: `.venv/bin/ruff check core/routing/focused_cognition.py tests/test_focused_cognition.py`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_focused_cognition.py
git commit -m "fix(focused): trust-tier authority labels on evidence lines + cite-with-caveat instruction"
```

---

## Task 3: Cross-suite regression check (no living-recall / dispatcher breakage)

**Files:** none (verification only)

- [ ] **Step 1: Run the adjacent suites that exercise the same path**

Run: `.venv/bin/python -m unittest tests.test_living_recall tests.test_focused_cognition -v`
Expected: PASS. (Living recall builds rendered transcripts that flow through `assemble_working_set`; the `[E#]`-preserving render guarantees no break. If `test_living_recall` references the exact `(source_type)` parenthetical anywhere, update that assertion to the authority label — but it keys on `[memory context]`/`[E#]`, not the working-set parenthetical.)

- [ ] **Step 2: Confirm `dialogue_anchor` authority renders in the in-process continuity path**

Run: `.venv/bin/python -m unittest tests.test_living_recall -v` and confirm any continuity/anchor test still passes; the anchor now renders as `recent dialogue — authoritative for continuity`.

---

## Live witness (Claude, after Task 1–3 green in-process)

Path-b transplant onto `main` working tree (uncommitted), flag-on Telegram daemon (`MAEZ_DISPATCHER_ENABLED=1 MAEZ_FOCUSED_COGNITION_ENABLED=1 MAEZ_LIVING_RECALL_ENABLED=1`, launch-env only, `config/.env` untouched), the privacy-clean `continuity_witness`-style trace. Probe battery:

1. `"What were we just talking about?"` → `kind=direct`, working set = `dialogue_anchor`, reply recaps the recent thread.
2. `"What's the infrastructure ground-truth you noted earlier?"` → content recall (NOT mis-anchored); rendered evidence lines carry authority labels; reply cites past-memory/context rows **with their caveat**, not as current state.
3. (Only if the live web path is available) a web turn → reply hedges the `external web — UNTRUSTED` item.

**Web is proven in-process (Task 2 Step 1), not gated on the live web surface.**

Gate: continuity recaps correctly; no content-recall regression; citation coverage not reduced; `check_groundedness` still passes. Green → branch-first commit + merge (flag posture unchanged). Red → split per the "no sixth fixture pass" rule.

---

## Self-Review

**Spec coverage:** Task 1 = continuity grammar + filler-in-place + false-positive boundary (spec Task 1) ✓. Task 2 = authority map (exact label table from spec), `[E#]` preserved, cite-with-caveat instruction, citation-coverage guard, web proven in-process (spec Task 2, all 5 refinements) ✓. Witness battery = spec's shared witness ✓.

**Placeholder scan:** none — every code step shows full code; commands are exact `.venv/bin/python -m unittest` invocations.

**Type consistency:** `_authority_label(source_type:str)->str`, `_render_evidence_lines(items)->list`, `DialogueContinuityState(kind,needs_dialogue,fail_safe_legacy,matched_reason)` unchanged, `EvidenceItem(local_label,source_type,text,durable_id)` and `GroundednessVerdict(verdict,citation_coverage,unmatched)` match the live dataclasses. The render helper reproduces the existing tail-repeat line exactly.
