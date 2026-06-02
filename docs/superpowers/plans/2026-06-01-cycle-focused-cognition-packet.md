# Cycle Focused-Cognition Packet — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the daydream cycle's ~23k-token dynamic dump with a bounded (~3k), provenance-tagged evidence packet built from the existing focused-cognition machinery — cutting cycle prefill ~16s → ~2-3s and sharpening reflection, without thinning Maez's inner life.

**Architecture:** Extend `core/routing/focused_cognition.py` (don't reinvent): reuse `EvidenceItem`, the working-set/budget assembler, citation rendering, provenance; add cycle-specific source types + authority labels, a salience selector (no query), and a reflection instruction. Wire into `_reason` behind a flag with the legacy megaprompt as fallback. Soul stays static-cached.

**Tech Stack:** Python 3.14, `unittest` (NO pytest), existing `core/routing/focused_cognition.py` + `daemon/maez_daemon.py` `_reason`.

**Spec:** `docs/superpowers/specs/2026-06-01-cycle-focused-cognition-packet-design.md`

**Lane:** Codex implements, Claude cross-verifies, Rohit owner-runs the live quality+prefill witness. **Flag off by default; legacy cycle path is the safe resting state.**

---

## File Structure

- `core/routing/focused_cognition.py` — extend source-type/authority-label maps with cycle types; add a cycle reflection instruction constant. (Read the existing `EvidenceItem`, the assembler entry point, `_AUTHORITY_LABEL`/source-type maps, and the faithful-instruction constants FIRST.)
- `core/cognition/cycle_packet.py` — NEW: the salience selector + packet builder (takes the cycle's candidate sources, ranks by salience, bounds to budget with per-source sub-budgets, returns `EvidenceItem`s incl. `signal_absence`; assembles via the focused-cognition assembler with the reflection instruction).
- `daemon/maez_daemon.py` — in `_reason` (~`:3200-3478`): behind `MAEZ_CYCLE_FOCUSED_ENABLED`, build the packet instead of the legacy dynamic `prompt`; legacy megaprompt retained as fallback (mirror the recall fallback at `:4744`); emit `cycle_packet_shape` telemetry.
- `tests/test_cycle_packet.py` — NEW: selector ranking/budget/inclusion/`signal_absence`/no-summaries; reflection faithful-empty; telemetry content-free; fallback-on-failure.

---

## Task 0: Branch + read the organ

- [ ] **Step 1:** Branch `cycle-focused-cognition-packet` off `main`.
- [ ] **Step 2 (read, no code):** In `core/routing/focused_cognition.py`, identify and note: the `EvidenceItem` fields; the public assembler entry (the function recall calls to turn `EvidenceItem`s + an instruction into the bounded working-set text + citation labels); the `_AUTHORITY_LABEL` map and source-type ordering maps; the faithful-instruction constants. The plan's code sketches below must be reconciled to these exact signatures.
- [ ] **Step 3 (read, no code):** In `daemon/maez_daemon.py` `_reason`, note exactly where the dynamic `prompt` string is assembled (the `f"Daemon cycle: …"` block and all the `prompt += …` appends) and which `self.*`/`self.memory.*` sources feed it — that source list IS the selector's candidate pool.

---

## Task 1: Cycle source types + authority labels

**Files:** `core/routing/focused_cognition.py`; Test `tests/test_cycle_packet.py`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_cycle_packet.py
import unittest
from core.routing.focused_cognition import _authority_label

class CycleVocabTest(unittest.TestCase):
    def test_cycle_source_types_have_distinct_authority_labels(self):
        for st in ("action_outcome", "signal_absence", "open_loop",
                   "builder_event", "quality_signal"):
            lbl = _authority_label(st)
            self.assertNotEqual(lbl, "unverified", f"{st} missing an authority label")
        # absence must read as absence, not as a (fabricable) observation
        self.assertIn("absence", _authority_label("signal_absence").lower())
```

- [ ] **Step 2:** Run → FAIL (labels default to `unverified`).
- [ ] **Step 3:** Extend `_AUTHORITY_LABEL` (and any source-type ordering/priority maps) with the five cycle types. Suggested labels (reconcile wording to the existing style):
  - `action_outcome` → "what Maez just did — outcome authority"
  - `signal_absence` → "signal ABSENT — do not infer presence"
  - `open_loop` → "unresolved want/wondering — open, not concluded"
  - `builder_event` → "self-modification activity"
  - `quality_signal` → "self-critique signal"
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(cycle): cycle-specific focused-cognition source types + labels`.

---

## Task 2: Salience selector + packet builder (the design-critical part)

**Files:** `core/cognition/cycle_packet.py` (create); Test `tests/test_cycle_packet.py`.

- [ ] **Step 1: Write failing tests — the selector's contract**

```python
    # --- budget + per-source sub-budget ---
    def test_packet_respects_token_budget(self):
        from core.cognition.cycle_packet import select_cycle_evidence
        cands = _many_candidates()  # far more than fits
        items = select_cycle_evidence(cands, budget_tokens=3000)
        self.assertLessEqual(_est_tokens(items), 3000)

    def test_no_single_source_crowds_out_others(self):
        # a huge memory dump must not evict action_outcome / signal_absence / open_loop
        from core.cognition.cycle_packet import select_cycle_evidence
        cands = _huge_memory_plus_one_failure_one_absence_one_open_loop()
        items = select_cycle_evidence(cands, budget_tokens=3000)
        kinds = {i.source_type for i in items}
        self.assertIn("action_outcome", kinds)
        self.assertIn("signal_absence", kinds)
        self.assertIn("open_loop", kinds)

    # --- absence is preserved (the load-bearing rail) ---
    def test_signal_absence_survives_selection(self):
        from core.cognition.cycle_packet import select_cycle_evidence
        cands = _candidates_with_screen_absent()
        items = select_cycle_evidence(cands, budget_tokens=500)  # tight
        self.assertTrue(any(i.source_type == "signal_absence" for i in items),
                        "absence rail dropped under tight budget — fabrication risk")

    # --- inclusion-on-uncertainty ---
    def test_errs_toward_inclusion_when_salience_uncertain(self):
        ...

    # --- evidence, not summary (covenant) ---
    def test_items_are_evidence_not_summaries(self):
        from core.cognition.cycle_packet import select_cycle_evidence, build_cycle_packet
        items = select_cycle_evidence(_candidates_with_screen_absent(), budget_tokens=3000)
        for i in items:
            self.assertTrue(i.source_type)          # typed evidence
            self.assertTrue(hasattr(i, "temporal_provenance") or i.source_type)
        text, n = build_cycle_packet(items)
        # the builder renders EvidenceItems with [E#] labels, not a free-text narration
        self.assertIn("[E", text)
```

- [ ] **Step 2:** Run → FAIL (module absent).
- [ ] **Step 3: Implement** `select_cycle_evidence(candidates, *, budget_tokens)` and `build_cycle_packet(items)`:
  - `candidates`: a list of typed raw signals (source_type + content + provenance) gathered from the `_reason` source pool (Task 0 Step 3).
  - **Per-source sub-budgets:** allocate the budget across source types so no single source (esp. the memory dump) can crowd out failures/absence/open-loops. Reserve a guaranteed slot for `signal_absence` and `action_outcome`-failures.
  - **Salience ranking** within each source type (recency, failure>success, unresolved>resolved, changed>static); err toward inclusion when uncertain.
  - Return `EvidenceItem`s (typed, provenance-carrying) — NOT summaries.
  - `build_cycle_packet` calls the existing focused-cognition assembler with the **cycle reflection instruction** to render the bounded working-set text + `[E#]` labels.
- [ ] **Step 4:** Run → PASS (iterate until budget/inclusion/absence/evidence-not-summary all green).
- [ ] **Step 5:** Commit `feat(cycle): salience selector + bounded evidence packet builder`.

---

## Task 3: Cycle reflection instruction (honest-silent preserved)

**Files:** `core/routing/focused_cognition.py` (add the constant) or `core/cognition/cycle_packet.py`; Test extends `tests/test_cycle_packet.py`.

- [ ] **Step 1: Test** the reflection instruction permits an honest-empty cycle and forbids out-of-evidence claims:

```python
    def test_reflection_instruction_allows_honest_silence(self):
        from core.cognition.cycle_packet import CYCLE_REFLECTION_INSTRUCTION as I
        low = I.lower()
        self.assertTrue("evidence" in low and ("nothing" in low or "say so" in low))
        # must not forbid silence; a silent cycle is a legitimate outcome
```

- [ ] **Step 2-3:** Add `CYCLE_REFLECTION_INSTRUCTION`: "Reflect over the evidence below. Notice what matters, connect, wonder. Ground what you say in the [E#] items and their authority labels; treat a `signal_absence` item as absent, never inferred present. If nothing here is worth a thought, say so plainly." Wire `build_cycle_packet` to use it.
- [ ] **Step 4-5:** Run → PASS; commit `feat(cycle): faithful reflection instruction`.

---

## Task 4: Wire into `_reason` behind the flag + telemetry

**Files:** `daemon/maez_daemon.py` (`_reason`); Test `tests/test_cycle_packet.py` (daemon-level seam test).

- [ ] **Step 1: Test** the flag branch + fallback (use a faithful seam test mirroring the recall focused/legacy pattern):
  - flag off → legacy dynamic `prompt` unchanged;
  - flag on → packet used; on packet-assembly exception → fall back to legacy + log (no cycle crash);
  - `cycle_packet_shape` telemetry emitted, content-free (no prompt/memory text — assert the field set: `packet_tokens_est`, `legacy_tokens_est`, `evidence_item_count`, `source_types`, `prefill_ms`, `cycle_outcome`).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** in `_reason`: read `MAEZ_CYCLE_FOCUSED_ENABLED`; when on, gather candidates from the existing source pool, `select_cycle_evidence(...)` + `build_cycle_packet(...)`, and use the packet as the user message (the `system_content` soul block stays byte-identical for KV reuse). Wrap in try/except → legacy `prompt` on failure (mirror `:4744`). Emit `cycle_packet_shape` (content-free helper modeled on `_log_focused_cognition_prompt_shape` at `:1467`).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(cycle): flag-gated packet path in _reason + content-free telemetry`.

---

## Task 5: Hermetic guards

- [ ] **Step 1:** Consolidate/confirm the full `tests/test_cycle_packet.py` covers: budget respected; per-source sub-budget (no crowd-out); `signal_absence` survives tight budget; inclusion-on-uncertainty; items-are-evidence-not-summaries (`[E#]`, typed, provenance); reflection allows honest-silence; flag-off no-op; fallback-on-failure; telemetry content-free.
- [ ] **Step 2:** Run the file + the focused-cognition suite (no regression to recall):
  `.venv/bin/python -m unittest tests.test_cycle_packet -v` and any `tests/test_focused_cognition*.py` → PASS.
- [ ] **Step 3:** Commit `test(cycle): hermetic guards for packet selection + fallback`.

---

## Task 6: Regression + owner-run acceptance note

- [ ] **Step 1:** Floor both directions on a clean checkout (NOT git stash); name the known-unrelated flaky trio (egress / web-slice / import-shim) explicitly; assert no NEW failures from this slice.
- [ ] **Step 2:** Run daemon-adjacent suites (cognition, perception, memory-format, grounding) → no regression.
- [ ] **Step 3: Acceptance note (owner-run, separate)** — `docs/slices/cycle-packet/acceptance.md`: with `MAEZ_CYCLE_FOCUSED_ENABLED=1` + restart, over a window of real cycles, read `cycle_packet_shape`: **dynamic packet ~2-4k tokens** (target ~3k), **prefill ~2-3s** (vs ~16s), **cycle quality holds/improves** (reflections coherent + in-voice; silent cycles stay honestly silent; absence never narrated as presence; no loss of action/want/quality awareness), no laundering (items provenance-tagged). Any miss → flag off (legacy is the resting state). **Owner-run; reversible by flag flip.**
- [ ] **Step 4:** Commit `test(cycle): regression sweep + acceptance note`.

---

## Self-Review

- **Spec coverage:** §2 selection/instruction/vocabulary → Tasks 1-3; salience criteria incl. absence rail → Task 2 (`signal_absence` survives tight budget); §3 covenant (evidence-not-summary) → Task 2 `[E#]` test; §4 no-thinning → inclusion-on-uncertainty + honest-silent tests; §5 flag/fallback/telemetry → Task 4; §6 budget arithmetic → Task 6 acceptance.
- **The design-critical risk** is the selector (Task 2): the load-bearing tests are `signal_absence`-survives-tight-budget and no-single-source-crowd-out — if those fail, the packet got smaller but less honest, which is the one outcome we must not ship.
- **Reconcile to the real API:** Task 0 Step 2/3 reads are mandatory before Task 1-4 code; the sketches here name intent, not exact signatures.
- **Resting state stays safe:** flag off = legacy cycle unchanged; every commit green.
