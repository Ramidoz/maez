# Thin-Evidence Synthesis Honesty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a web search returns thin/sparse results, Maez acknowledges the limit ("I found limited information") instead of fabricating confident cited specifics — by switching the evidence-precedence directives from confidence-forcing to limited-evidence honesty on thin turns.

**Architecture:** The single shared renderer `format_for_context` computes a deterministic thin signal and prepends a body-authored `quality=…` line (flag-gated, no dict mutation). `EvidenceState` parses that line (anti-spoof, line-anchored) into `thin_evidence`. Both evidence-precedence directives (daemon `build_evidence_precedence_directive` and the focused `_focused_evidence_precedence_instruction`, wired through `WorkingSet`) read it and, when thin, suppress the confidence-forcing clause and emit a hedge directive. The live support gate stays the reliable per-claim net.

**Tech Stack:** Python, `unittest` (runner `/home/rohit/maez/.venv/bin/python -B -m unittest <module>`, NEVER full-discover), `skills/web_search.py`, `core/routing/evidence_state.py`, `core/routing/focused_cognition.py`, `daemon/maez_daemon.py`.

**Spec:** `docs/superpowers/specs/2026-06-16-thin-evidence-synthesis-honesty-design.md` (PASS, @3bf91a6).
**Branch:** `thin-evidence-honesty` (main local-only/unpushed — NO push).
**Discipline:** TDD per task. `## Predicted effect` on behavior commits. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. **STOP at the review gate** before ANY flag flip/restart (owner-sovereign). Cross-lane Codex at the gate (changes the synthesis prompt). This is upstream **reduction** (best-effort); the gate stays the net.

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `skills/web_search.py` | the single shared renderer | thin compute + body-authored `quality=` line (flag-gated, no dict mutation); named constants |
| `core/routing/evidence_state.py` | `EvidenceState`, `turn_evidence_state`, daemon directive | `thin_evidence` field; anchored parse; thin wording constant; directive switch+suppress |
| `core/routing/focused_cognition.py` | focused synthesis instruction | `WorkingSet.thin_evidence` wiring → `_citation_instruction` → `_focused_evidence_precedence_instruction` |
| `tests/test_thin_evidence_honesty.py` | tests | create |
| `docs/proof/2026-06-16-thin-evidence-task0.md` | Task-0 proofs | create |

**Branch setup:**
```bash
cd /home/rohit/maez
git checkout main && git checkout -b thin-evidence-honesty
git branch --show-current   # expect: thin-evidence-honesty
```

---

## Task 0: Proofs (HARD GATE — docs only, no behavior change)

**Files:** Create `docs/proof/2026-06-16-thin-evidence-task0.md`. STOP if a proof refutes the spec.

- [ ] **Step 1: Prove 0a — `format_for_context` consumer classification (owner-mandated)**

`format_for_context` is the single shared renderer; the body-authored line will appear in EVERY consumer's output. Classify each so the line is never an owner-facing artifact or a silent untreated signal:
```bash
cd /home/rohit/maez
grep -rn 'format_for_context\b' daemon/ core/ skills/ | grep -viE 'def format_for_context|git_awareness|screen_obs|quality_tracker|reflection|calendar_perception'
```
Known consumers to classify (read each call site):
| consumer | site | classify: (i) treated synthesis / (ii) owner-facing artifact / (iii) untreated prompt |
|---|---|---|
| dispatcher adapter | `core/dispatcher/external_sources.py:519` | (i) treated |
| legacy synthesis | `daemon/maez_daemon.py:5445` (`web_format`) | (i) treated |
| `daemon/maez_daemon.py:7548` (`web_format`) | read ~7520-7560 | ? |
| `daemon/maez_daemon.py:7740` (`web_fmt`, with `search_rss`) | read ~7720-7770 | ? |
| `core/actions/action_engine.py:1575,1583` | read ~1560-1590 | ? |
| `skills/web_search.py:435` (`print(...)`) | the module `__main__` CLI | (ii) CLI stdout — debug only |

For each `?`: does it FEED A PROMPT (treated if it gets the thin directive; untreated-but-harmless if not) or RENDER TO THE OWNER (the `quality=` line would leak)? **If any consumer renders `format_for_context` output directly to the owner (voice TTS, a briefing message body, a cockpit string), STOP** and scope the line so it cannot reach that surface (e.g., a `with_quality: bool` param defaulting False, set True only on the treated synthesis call sites — adjust the plan's Task 1 accordingly). Record the verdict per consumer.

- [ ] **Step 2: Prove 0b — focused-wiring reachability**
```bash
sed -n '353,360p' core/routing/focused_cognition.py   # WorkingSet — no thin field
sed -n '184,205p' core/routing/focused_cognition.py    # _citation_instruction(render_version) + _focused_evidence_precedence_instruction() argless
grep -n 'state = turn_evidence_state\|return WorkingSet\|WorkingSet(' core/routing/focused_cognition.py   # :796 computes state; :959/:1061/:1277 ctor sites
sed -n '996,1002p' core/routing/focused_cognition.py   # the _citation_instruction(working_set.citation_render_version) call (~:1000)
```
Confirm: `WorkingSet` has no thin field; `assemble_working_set` computes `state` but drops it; the three ctor sites need the `False` default. Record buildability.

- [ ] **Step 3: Write the proof doc + commit**

Record 0a (per-consumer verdict; whether the line must be scoped to treated call sites) and 0b (wiring buildable). State `## SEAM ASSUMPTIONS HELD: YES/NO`.
```bash
git add docs/proof/2026-06-16-thin-evidence-task0.md
git commit -m "$(cat <<'EOF'
docs(proof): Task-0 for thin-evidence honesty (consumers + focused wiring)

0a: format_for_context consumers classified — the body-authored quality line must
not reach an owner-facing surface (voice/briefing/CLI). 0b: focused wiring buildable
(WorkingSet has no thin field; assemble_working_set drops state). No behavior change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 1: Thin signal + body-authored line in `format_for_context`

**Files:** Modify `skills/web_search.py`. Test: `tests/test_thin_evidence_honesty.py` (create).

> If Task 0a found an owner-facing consumer, add a `with_quality: bool = False` param to `format_for_context` and emit the line only when True; the treated call sites (Tasks 3/4 context) pass True. The default-False keeps owner-facing consumers clean. The tests below assume the unconditional flag-gated form; adapt to `with_quality` if 0a required it.

- [ ] **Step 1: Write the failing tests**
```python
import unittest
from unittest import mock


def _res(query, results, count=None):
    return {"success": bool(results), "results": results,
            "result_count": count if count is not None else len(results),
            "query": query, "timestamp": "2026-06-16"}


class ThinSignalRenderTest(unittest.TestCase):
    def _render(self, result, flag="1"):
        from skills import web_search
        with mock.patch.dict("os.environ", {"MAEZ_THIN_EVIDENCE_HONESTY_ENABLED": flag}):
            return web_search.format_for_context(result)

    def test_thin_when_few_results(self):
        out = self._render(_res("q", [{"title": "T", "snippet": "x" * 100, "url": "u"}]))  # 1 result
        self.assertIn("quality=thin result_count=1", out.splitlines()[0])

    def test_thin_when_short_snippets(self):
        # 3 results but tiny snippets -> usable_snippet_chars < 450
        rs = [{"title": "T", "snippet": "short", "url": "u"} for _ in range(3)]
        out = self._render(_res("q", rs))
        self.assertIn("quality=thin", out.splitlines()[0])

    def test_adequate_when_enough(self):
        rs = [{"title": "T", "snippet": "y" * 200, "url": "u"} for _ in range(3)]  # 3 × 200 = 600 chars
        out = self._render(_res("q", rs))
        self.assertIn("quality=adequate result_count=3 snippet_chars=600", out.splitlines()[0])

    def test_flag_off_byte_identical_and_dict_unmutated(self):
        rs = [{"title": "T", "snippet": "x", "url": "u"}]
        r = _res("q", rs)
        off = self._render(dict(r), flag="0")
        self.assertNotIn("quality=", off)        # no body line
        self.assertNotIn("result_quality", r)    # dict never mutated
        # off output equals the pre-feature render (header + items, no quality line)
        self.assertTrue(off.startswith("[WEB SEARCH: 'q'] 1 results"))
```

- [ ] **Step 2: Run → RED.**

- [ ] **Step 3: Implement** in `skills/web_search.py` (named constants near the top; the compute + flag-gated prepend in `format_for_context`):
```python
_THIN_RESULT_COUNT = 3
_THIN_SNIPPET_CHARS = 450


def _compute_quality(result: dict) -> tuple[str, int, int]:
    rc = int(result.get("result_count", 0) or 0)
    snippet_chars = sum(len((r.get("snippet") or "")[:200]) for r in (result.get("results") or [])[:3])
    quality = "thin" if (rc < _THIN_RESULT_COUNT or snippet_chars < _THIN_SNIPPET_CHARS) else "adequate"
    return quality, rc, snippet_chars
```
In `format_for_context`, after building `rendered = '\n'.join(lines)` (do NOT mutate `result`):
```python
    rendered = '\n'.join(lines)
    try:
        from core.infra.env_flags import strict_env_flag
        if strict_env_flag("MAEZ_THIN_EVIDENCE_HONESTY_ENABLED"):
            quality, rc, sc = _compute_quality(result)
            q_line = (f"[WEB SEARCH: '{result['query']}'] "
                      f"quality={quality} result_count={rc} snippet_chars={sc}")
            return f"{q_line}\n{rendered}"
    except Exception:
        pass
    return rendered
```

- [ ] **Step 4: Run → GREEN.** ruff clean on `skills/web_search.py` + the test.

- [ ] **Step 5: Commit** (`feat(web-search): deterministic thin-evidence signal + body-authored quality line`; `## Predicted effect`: flag on → web search renders a leading `quality=` line for the synthesis path; flag off → byte-identical render, dict never mutated; no directive change yet).

---

## Task 2: `EvidenceState.thin_evidence` + anti-spoof parse

**Files:** Modify `core/routing/evidence_state.py` (`EvidenceState`, `turn_evidence_state`). Test: `tests/test_thin_evidence_honesty.py`.

- [ ] **Step 1: Write the failing tests**
```python
class ThinParseTest(unittest.TestCase):
    def test_anchored_quality_thin_line_sets_thin(self):
        from core.routing.evidence_state import turn_evidence_state
        wc = "[WEB SEARCH: 'q'] quality=thin result_count=1 snippet_chars=80\n[WEB SEARCH: 'q'] 1 results — t\n  1. T\n     s"
        self.assertTrue(turn_evidence_state(transcript="", web_context=wc).thin_evidence)

    def test_dispatcher_fresh_evidence_prefix_parses(self):
        from core.routing.evidence_state import turn_evidence_state
        tr = "[fresh evidence] [WEB SEARCH: 'q'] quality=thin result_count=2 snippet_chars=120"
        self.assertTrue(turn_evidence_state(transcript=tr, web_context="").thin_evidence)

    def test_adequate_line_not_thin(self):
        from core.routing.evidence_state import turn_evidence_state
        wc = "[WEB SEARCH: 'q'] quality=adequate result_count=3 snippet_chars=600"
        self.assertFalse(turn_evidence_state(transcript="", web_context=wc).thin_evidence)

    def test_midline_page_text_does_not_spoof(self):
        from core.routing.evidence_state import turn_evidence_state
        # a page snippet mentioning quality=thin mid-line must NOT trip it
        wc = "[WEB SEARCH: 'q'] 1 results — t\n  1. Blog\n     our data quality=thin per the report"
        self.assertFalse(turn_evidence_state(transcript="", web_context=wc).thin_evidence)
```

- [ ] **Step 2: Run → RED** (`EvidenceState` has no `thin_evidence`).

- [ ] **Step 3: Implement** in `evidence_state.py`: add `thin_evidence: bool = False` to the `EvidenceState` dataclass (after `descriptions`); add the anchored regex + a parse helper; set it in `turn_evidence_state`'s `EvidenceState(...)` construction:
```python
_QUALITY_LINE_RE = re.compile(
    r"^(?:\[fresh evidence\]\s*)?\[WEB SEARCH: [^\]]*\] "
    r"quality=(thin|adequate) result_count=\d+ snippet_chars=\d+",
    re.MULTILINE,
)


def _detect_thin(transcript: str, web_context: str) -> bool:
    for text in ((transcript or ""), (web_context or "")):
        for m in _QUALITY_LINE_RE.finditer(text):
            if m.group(1) == "thin":
                return True
    return False
```
In `turn_evidence_state(...)`, pass `thin_evidence=_detect_thin(transcript, web_context)` to the `EvidenceState(...)` constructor. (Confirm `re` is imported in the module.)

- [ ] **Step 4: Run → GREEN + regression.** `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_evidence_state tests.test_thin_evidence_honesty 2>&1 | tail -4`. ruff clean.

- [ ] **Step 5: Commit** (`feat(evidence-state): parse body-authored thin signal (anchored, anti-spoof)`; `## Predicted effect`: EvidenceState.thin_evidence now reflects a thin web search; no directive consumes it yet).

---

## Task 3: Daemon directive switch + suppress

**Files:** Modify `core/routing/evidence_state.py` (`build_evidence_precedence_directive` + a shared thin-wording constant). Test: `tests/test_thin_evidence_honesty.py`.

- [ ] **Step 1: Write the failing tests**
```python
class DaemonDirectiveTest(unittest.TestCase):
    def _state(self, thin):
        from core.routing.evidence_state import EvidenceState
        return EvidenceState(evidence_present=True, marker_labels=("web search results",),
                             descriptions=("…",), thin_evidence=thin)

    def test_thin_emits_hedge_and_suppresses_confidence_clause(self):
        from core.routing.evidence_state import build_evidence_precedence_directive
        out = build_evidence_precedence_directive(self._state(True))
        self.assertIn("THIN", out)
        self.assertIn("limited information", out)
        self.assertNotIn("You may NOT claim the relevant source", out)  # confidence-forcing clause suppressed
        self.assertNotIn("refuse", out.lower())  # covenant: no refusal language

    def test_adequate_keeps_normal_directive(self):
        from core.routing.evidence_state import build_evidence_precedence_directive
        out = build_evidence_precedence_directive(self._state(False))
        self.assertIn("You may NOT claim the relevant source", out)
        self.assertNotIn("THIN", out)
```

- [ ] **Step 2: Run → RED.**

- [ ] **Step 3: Implement** — add the shared constant + branch in `build_evidence_precedence_directive`:
```python
_THIN_EVIDENCE_DIRECTIVE = (
    "The fresh evidence this turn is THIN - few results, little detail. "
    "Answer only what it actually supports, and say plainly that the search "
    "returned limited information. Do not fabricate specifics the results do "
    "not contain. You may offer to search differently."
)
```
In `build_evidence_precedence_directive`, when `state.thin_evidence` is True: emit the evidence list as today, then append `_THIN_EVIDENCE_DIRECTIVE` and **do NOT append** the `"Answer from this evidence…"` / `"You may NOT claim the relevant source…"` confidence-forcing lines. When False: unchanged (append the normal lines). Concretely, wrap the two confidence-forcing `lines.append(...)` calls in `if not state.thin_evidence:` and add `else: lines.append(_THIN_EVIDENCE_DIRECTIVE)`.

- [ ] **Step 4: Run → GREEN + regression** (`tests.test_evidence_state`). ruff clean.

- [ ] **Step 5: Commit** (`feat(evidence-state): daemon directive hedges on thin evidence (suppress confidence-forcing)`; `## Predicted effect`: on the legacy/daemon path, a thin web turn (flag on) tells Maez to acknowledge limited info instead of being forbidden from saying so; adequate turns unchanged).

---

## Task 4: Focused-path wiring + prompt-shape test (the must-fix)

**Files:** Modify `core/routing/focused_cognition.py`. Test: `tests/test_thin_evidence_honesty.py`.

- [ ] **Step 1: Write the failing focused prompt-shape test**
```python
class FocusedThinWiringTest(unittest.TestCase):
    def _instruction(self, thin):
        from core.routing import focused_cognition as fc
        # _citation_instruction now takes thin_evidence; assert the focused wording
        return fc._citation_instruction(None, thin_evidence=thin)

    def test_thin_focused_instruction_hedges_and_suppresses(self):
        out = self._instruction(True)
        self.assertIn("THIN", out)
        self.assertIn("limited information", out)
        self.assertNotIn("Before you claim the evidence lacks", out)  # confidence-forcing clause absent
        self.assertNotIn("refuse", out.lower())

    def test_adequate_focused_instruction_normal(self):
        out = self._instruction(False)
        self.assertNotIn("THIN", out)

    def test_working_set_carries_thin_from_state(self):
        # assemble_working_set sets WorkingSet.thin_evidence from the parsed state
        from core.routing.focused_cognition import assemble_working_set
        wc = "[WEB SEARCH: 'q'] quality=thin result_count=1 snippet_chars=50\n[fresh evidence] x [E1]"
        ws = assemble_working_set(transcript="[fresh evidence] x [E1]", web_context=wc,
                                  owner_question="q", recall_items=None)
        self.assertTrue(getattr(ws, "thin_evidence", False))
```
(Adapt the `assemble_working_set` call to its real signature; the assertion `ws.thin_evidence is True` is the contract.)

- [ ] **Step 2: Run → RED** (`_citation_instruction` has no `thin_evidence`; `WorkingSet` has no field).

- [ ] **Step 3: Implement the wiring**

(a) Add `thin_evidence: bool = False` to the `WorkingSet` dataclass (`:353`). The other two ctor sites (`:1061`, `:1277`) inherit the default; no change needed there.

(b) In `assemble_working_set`, the `state = turn_evidence_state(...)` is already computed (`:796`); pass `thin_evidence=state.thin_evidence` into the `return WorkingSet(...)` (`:959`).

(c) Thread it through the instruction. `_focused_evidence_precedence_instruction` gains a param and reuses the shared constant:
```python
def _focused_evidence_precedence_instruction(thin_evidence: bool = False) -> str:
    if not _evidence_precedence_enabled():
        return ""
    if thin_evidence:
        from core.routing.evidence_state import _THIN_EVIDENCE_DIRECTIVE
        return _THIN_EVIDENCE_DIRECTIVE
    return (  # ... existing static text, including "Before you claim the evidence lacks something, re-read it" ...
    )
```
And `_citation_instruction`:
```python
def _citation_instruction(render_version: str | None = None, *, thin_evidence: bool = False) -> str:
    version = render_version or _citation_render_version()
    base = ...  # unchanged
    extension = _focused_evidence_precedence_instruction(thin_evidence)
    return f"{base}\n{extension}" if extension else base
```

(d) Update the call site (`~:1000`): `_citation_instruction(working_set.citation_render_version, thin_evidence=working_set.thin_evidence)`.

- [ ] **Step 4: Run → GREEN + regression.** `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_focused_cognition tests.test_thin_evidence_honesty 2>&1 | tail -5`. ruff clean.

- [ ] **Step 5: Commit** (`feat(focused): wire thin_evidence to the focused synthesis instruction`; `## Predicted effect`: on the focused path, a thin web turn (flag on) hedges instead of being told to re-read for missing detail; the previously-deaf room now hears the warning; adequate unchanged).

---

## Task 5: Receipt + flag-off byte-identical sweep

**Files:** Modify `daemon/maez_daemon.py` (emit the receipt near where `_evidence_state` is built ~6090). Test: `tests/test_thin_evidence_honesty.py`.

- [ ] **Step 1: Write the receipt + flag-off tests**
```python
class ReceiptAndFlagOffTest(unittest.TestCase):
    def test_flag_off_no_quality_line_and_dict_unmutated(self):
        from skills import web_search
        from unittest import mock
        r = {"success": True, "results": [{"title": "T", "snippet": "x", "url": "u"}],
             "result_count": 1, "query": "q", "timestamp": "t"}
        with mock.patch.dict("os.environ", {"MAEZ_THIN_EVIDENCE_HONESTY_ENABLED": "0"}):
            out = web_search.format_for_context(r)
        self.assertNotIn("quality=", out)
        self.assertNotIn("result_quality", r)

    def test_thin_directive_constant_has_no_refusal(self):
        from core.routing.evidence_state import _THIN_EVIDENCE_DIRECTIVE
        low = _THIN_EVIDENCE_DIRECTIVE.lower()
        for banned in ("i cannot answer", "i won't answer", "refuse", "i can't help"):
            self.assertNotIn(banned, low)
```

- [ ] **Step 2: Run → GREEN (mostly pass from Tasks 1-4); add the receipt.**

In `daemon/maez_daemon.py`, right after `_evidence_state = turn_evidence_state(...)` (~6090), behind the flag, log the greppable receipt (content-light — counts only; re-derive from the parsed line or `_evidence_state.thin_evidence` + a small parse of the quality line, surface=source):
```python
        try:
            if strict_env_flag("MAEZ_THIN_EVIDENCE_HONESTY_ENABLED"):
                logger.info(
                    "thin_evidence quality=%s thresholds=(3,450) directive=%s surface=%s",
                    "thin" if _evidence_state.thin_evidence else "adequate",
                    "thin" if _evidence_state.thin_evidence else "normal",
                    source,
                )
        except Exception:
            pass
```
(If the witness needs `result_count`/`snippet_chars` in the receipt, capture them when the search runs — the search result dict has `result_count`; thread the two ints to this log. Keep it best-effort.)

- [ ] **Step 3: Run feature suite + ruff.** `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_thin_evidence_honesty 2>&1 | tail -3`; `/home/rohit/maez/.venv/bin/python -B -c "import daemon.maez_daemon"`; ruff clean on all touched files.

- [ ] **Step 4: Commit** (`feat(daemon): thin_evidence receipt (greppable, flag-gated)`; `## Predicted effect`: flag on → each web turn logs a thin_evidence receipt for witnessing; flag off → no receipt, byte-identical).

---

## Task 6: STOP-at-gate handoff

**Files:** Create `docs/handoffs/2026-06-16-thin-evidence-honesty-gate.md`.

- [ ] **Step 1: Write the handoff** — branch + commits + green suites (paste) + ruff. Codex cross-lane ask (changes the synthesis prompt): anchors — single shared annotator (no dict mutation, flag-off byte-identical); anti-spoof anchored parse; BOTH directive sites switch+suppress; focused wiring reaches `_focused_evidence_precedence_instruction`; covenant (no refusal). **Owner breath:** `MAEZ_THIN_EVIDENCE_HONESTY_ENABLED=1` + restart (MiniCheck/gate already live from the prior slices). **Witness (measure first, then prove):** (1) FIRST measure the Anthropic baseline — re-run "latest news about Anthropic?" with the flag on and read the `thin_evidence … quality=…` receipt + the `result_count`/`snippet_chars`: **is it actually thin?** (`spec_match_score=0.000` was routing, NOT thinness). (2) If thin → Maez visibly hedges ("I found limited information") instead of asserting, AND the live gate's `caveated_unsupported` **drops** from the 4/4 baseline. (3) If NOT thin → record honestly: this slice helps sparse searches but does not explain that wound; the gate remains the net. **Forward-only / honest:** upstream reduction, best-effort; not a guarantee.

- [ ] **Step 2: Commit + STOP.** No flag flip, no restart, no model.env edit — owner-sovereign. Surface branch tip + green suites + the witness recipe.

---

## Notes for the implementer

- **Runner:** `/home/rohit/maez/.venv/bin/python -B -m unittest <module>` — NEVER `discover`.
- **Never mutate the result dict** — compute thin at render time in `format_for_context`; that's what keeps flag-off byte-identical and the dict shape stable.
- **Single shared annotator:** `format_for_context` is `web_format` (daemon) and the dispatcher renderer — one change covers searxng/DDG/RSS + both surfaces. Task 0a decides if it must be scoped away from an owner-facing consumer.
- **Two directive sites, one wording constant** (`_THIN_EVIDENCE_DIRECTIVE` in `evidence_state.py`, imported by focused) — keep them identical so "same wound, different prompt layer" can't recur.
- **Covenant:** the thin directive hedges, never refuses. Maez still answers what's supported + honest background knowledge.
- **No push. STOP at the gate.** Upstream reduction; the live support gate stays the per-claim net.
