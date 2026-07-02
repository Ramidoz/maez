# Scar Tissue (A1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Deterministic correction-events (fabrication catches, claim-receipt redos, dream rejections, proven-wrong vetoes, card rejections) become receipt-grade scar episodes in Maez's autobiography — neutral, deduplicated, fading via ordinary salience — plus consequence rows for the planner, with scar classes excluded from the `[LEARNED FROM PAST MISTAKES]` block.

**Architecture:** One pure module `core/learning/scar_tissue.py` (validation + dedup sidecar + substrate-composed episode text), four thin hooks at seams that already detect the events, one widened existing write (`card_rejected`), one small backfill script for the 4 exhibits. All writers behind `MAEZ_SCAR_TISSUE` (default-off, flag-off byte-identical).

**Tech Stack:** Python 3.12; host tests `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest).

**Spec:** `docs/superpowers/specs/2026-07-02-scar-tissue-a1-design.md` (@be8fa1c).

**Task 0 (DONE 2026-07-02 — plan written on this ground):** episode `add()` fields are open strings (no closed enums) → `source_kind="scar"`/`authorship="scar_detector"` write-safe. `memory_voice` has ONE reader (memory_manager:683, telemetry/parked-damp) → **pin `memory_voice="external_to_maez"`** (semantically right — the correction came from outside; avoids the `maez_self` parked-promotion damp; proven ordinary recall candidate). `lived_recall`'s only source_kind special case is `"reflection"` (:877) → scars content-blind. Receipts: `fabrication_memory.record_event` returns None today (add lastrowid return); the redo class's durable receipt is minted by **Landing 1's own consequence row id**; `dream_state.reject_proposal(prop_id, reason)` and `veto_ledger.attach_reask_outcome(...)→"likely_wrong"` are single-seam hooks; `card_rejected` write to widen at decision_pipeline ~2117 (id currently discarded). Both rail classes therefore stay **INCLUDED**.

## Hard Invariants
- Flag-off (`MAEZ_SCAR_TISSUE` unset): byte-identical behavior everywhere (incl. the card_rejected path).
- **Receipt-grade or nothing:** `record_scar` with zero resolvable receipt refs raises; never degrades to a log-line citation.
- Scar classes NEVER render inside `[LEARNED FROM PAST MISTAKES]`; the neutral formatter exists but is NOT wired to the planner in v0. `tool_failure` block behavior unchanged (regression check, not a scar path — per Codex note).
- Scar text is substrate-composed (zero LLM) and passes the no-shame/no-directive vocabulary guard.
- Dedup is append-preserving: sidecar accumulates receipts; episodes only ever add/supersede.
- `tool_failure` produces NO scar episode.

---

## Task 1: `fabrication_memory.record_event` returns its row id

**Files:** Modify `core/learning/fabrication_memory.py`; Test `tests/test_scar_receipts.py` (create)

- [ ] **Step 1: Failing test**
```python
# tests/test_scar_receipts.py
import unittest
from unittest import mock


class FabricationReceiptIdTests(unittest.TestCase):
    def test_record_event_returns_row_id(self):
        from core.learning import fabrication_memory as fm
        with mock.patch.object(fm, "_db_path_for_test", create=True):
            pass  # implementer: use the module's existing test seam / tmp db pattern
        # Build-time: follow the module's existing test fixture pattern (tmp sqlite);
        # assert record_event(...) returns an int > 0, and two calls return distinct ids.
```
The implementer writes this against the module's existing test fixtures (it has a tmp-db pattern in its current tests) — assert: returns `int > 0`; distinct ids on distinct calls; early-return paths (disabled/dup) return `None`.
- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** — `INSERT` → `return cur.lastrowid`; early returns → `return None`; update the docstring contract. — [ ] **Step 4: GREEN + existing fabrication tests still pass.** — [ ] **Step 5: Commit** `feat(scar): fabrication_memory.record_event returns receipt id`

---

## Task 2: `core/learning/scar_tissue.py` — the organ (pure core)

**Files:** Create `core/learning/scar_tissue.py`; Test `tests/test_scar_tissue.py` (create)

- [ ] **Step 1: Failing tests**
```python
# tests/test_scar_tissue.py
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class ScarValidationTests(unittest.TestCase):
    def test_no_receipt_raises(self):
        from core.learning.scar_tissue import ScarEvent, validate_scar
        e = ScarEvent(scar_class="dream_rejected", surface="telegram", context="proposal 7",
                      correction="rejected: too grand", receipt_refs=[], dedup_key="dream:7")
        with self.assertRaises(ValueError):
            validate_scar(e)

    def test_tool_failure_is_not_scar_grade(self):
        from core.learning.scar_tissue import SCAR_CLASSES
        self.assertNotIn("tool_failure", SCAR_CLASSES)
        for c in ("fabrication_catch", "claim_receipt_redo", "dream_rejected",
                  "veto_proven_wrong", "card_rejected"):
            self.assertIn(c, SCAR_CLASSES)

    def test_episode_text_is_neutral(self):
        from core.learning.scar_tissue import compose_scar_text
        text = compose_scar_text(
            scar_class="card_rejected", surface="decision_pipeline",
            context="action=run_shell cmd='rm -rf tmp'", correction="denied: too broad",
            receipt_refs=["consequence:42", "card:abc"], occurred_at="2026-07-02T12:00:00Z",
        )
        for banned in ("mistake", "never ", "should not", "avoid ", "failed to",
                       "sorry", "apolog", "shame", "must not"):
            self.assertNotIn(banned, text.lower())
        self.assertIn("denied: too broad", text)       # the correction, restated
        self.assertIn("consequence:42", text)          # receipts visible


class ScarSidecarTests(unittest.TestCase):
    def _sidecar(self, td):
        from core.learning.scar_tissue import ScarSidecar
        return ScarSidecar(Path(td) / "scars.db")

    def test_first_occurrence_needs_episode(self):
        with tempfile.TemporaryDirectory() as td:
            s = self._sidecar(td)
            self.assertIsNone(s.active_episode("fab:tok1"))
            s.register("fab:tok1", episode_id="ep-1", receipt_ref="fabrication:9")
            self.assertEqual(s.active_episode("fab:tok1"), "ep-1")

    def test_repeat_appends_evidence_without_new_episode(self):
        with tempfile.TemporaryDirectory() as td:
            s = self._sidecar(td)
            s.register("fab:tok1", episode_id="ep-1", receipt_ref="fabrication:9")
            s.append_evidence("fab:tok1", receipt_ref="fabrication:10")
            row = s.get("fab:tok1")
            self.assertEqual(row["active_episode_id"], "ep-1")
            self.assertEqual(row["occurrence_count"], 2)
            self.assertIn("fabrication:10", row["receipt_refs"])

    def test_supersede_updates_active_pointer_preserving_history(self):
        with tempfile.TemporaryDirectory() as td:
            s = self._sidecar(td)
            s.register("fab:tok1", episode_id="ep-1", receipt_ref="r1")
            s.supersede_active("fab:tok1", new_episode_id="ep-2")
            row = s.get("fab:tok1")
            self.assertEqual(row["active_episode_id"], "ep-2")
            self.assertIn("ep-1", row["prior_episode_ids"])
```
- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement** — the module holds:
```python
SCAR_CLASSES = frozenset({
    "fabrication_catch", "claim_receipt_redo", "dream_rejected",
    "veto_proven_wrong", "card_rejected",
})

@dataclass(frozen=True)
class ScarEvent:
    scar_class: str
    surface: str
    context: str          # what was happening (content-light, capped)
    correction: str       # the correction, RESTATED verbatim-derived — never synthesized
    receipt_refs: list    # ["consequence:<id>", "fabrication:<id>", "dream:<id>", ...]
    dedup_key: str

def validate_scar(e) -> None: ...   # class in SCAR_CLASSES; receipt_refs non-empty + well-formed; caps

def compose_scar_text(...) -> str:
    # substrate-composed, zero LLM. Shape:
    # "Correction received (<scar_class>, <surface>, <occurred_at>). Context: <context>.
    #  The correction: <correction>. Receipts: <refs>."
    # No advice. No shame vocabulary. The guard test pins this.

class ScarSidecar: ...  # sqlite: dedup_key PK, active_episode_id, prior_episode_ids_json,
                        # receipt_refs_json, occurrence_count, first_ts, last_ts
                        # register / append_evidence / supersede_active / get / active_episode

def record_scar(event, *, episode_store, sidecar, consequence_id=None,
                now_iso=None) -> dict:
    # validate -> (reuse consequence_id or write consequence row; its id joins receipt_refs)
    # -> sidecar: new dedup_key? add episode (source_kind="scar", authorship="scar_detector",
    #    memory_voice="external_to_maez", importance=4, source_memory_ids=receipt refs,
    #    title/summary from compose_scar_text) + register
    #    else append_evidence (no new episode)
    # returns {"episode_id", "consequence_id", "new_episode": bool}
```
Consequence-row write uses the existing `record_event` API with the scar class; for scar classes the `feedback` param is the restated correction (spec pin).
- [ ] **Step 4: GREEN.** — [ ] **Step 5: Commit** `feat(scar): scar_tissue core — validation, neutral composition, append-preserving dedup`

---

## Task 3: the four hooks + the widened card path (flag-gated)

**Files:** Modify `daemon/maez_daemon.py` (redo outcomes ~8204-8250 + fabrication/audit seam), `core/evolution/dream_state.py` (`reject_proposal`), `core/routing/veto_ledger.py` caller (where `attach_reask_outcome` returns), `core/decision/decision_pipeline.py` (~2117); Test `tests/test_scar_hooks.py` (create)

Each hook is the same 6-line shape, behind `MAEZ_SCAR_TISSUE`:
```python
if strict_env_flag("MAEZ_SCAR_TISSUE"):
    try:
        record_scar(ScarEvent(scar_class=..., surface=..., context=...[:400],
                              correction=...[:300], receipt_refs=[...], dedup_key=...),
                    episode_store=..., sidecar=..., consequence_id=<existing id if any>)
    except Exception as exc:
        logger.debug("scar record skipped: %s", exc)   # fail-safe: scars never break the host path
```
Per hook: **fabrication_catch** — at the self_claim_audit caller where a rewrite/action-claim flag lands; receipt = `fabrication:<id>` (Task 1) + consequence id; dedup = fabrication token. **claim_receipt_redo** — both `accepted` and `floor` branches; receipt = consequence id (this row IS the durable redo receipt); dedup = `redo:<action_type>:<pattern_id>`. **dream_rejected** — inside `reject_proposal` on success; receipt = `dream:<prop_id>` + consequence id; dedup = `dream:<prop_id>`. **veto_proven_wrong** — where classification returns `"likely_wrong"`; receipt = `veto:<event_id>` + consequence id; dedup = `veto:<event_id>`. **card_rejected** — WIDEN the existing `record_event` call: capture its return id, pass as `consequence_id` (assert exactly one consequence row per rejection), receipt = `card:<action_id>` + that id; dedup = `card:<action_id>`.

- [ ] **Step 1: Failing tests** — per hook, with mocked stores: flag-off → zero scar calls AND (card path) the existing single record_event still fires identically; flag-on → one `record_scar` with correct class/receipts/dedup; hook exception → host path unaffected (fail-safe test).
- [ ] **Step 2: RED. Step 3: implement. Step 4: GREEN + flag-off byte-identical suite.** — [ ] **Step 5: Commit** `feat(scar): wire the five deterministic scar sources (flag-gated, fail-safe)`

---

## Task 4: planner-block exclusion + neutral formatter

**Files:** Modify `core/learning/consequence_memory.py` (`format_for_prompt`, `relevant`); Test additions to `tests/test_scar_tissue.py`

- [ ] **Step 1: Failing tests** — (a) `format_for_prompt` given a mixed event list renders `tool_failure` rows under `[LEARNED FROM PAST MISTAKES]` **and silently omits scar-class rows** (assert none of the scar contexts appear); (b) `format_scars_neutral(events)` exists, renders event+correction+receipts with a neutral header (`[PRIOR CORRECTIONS — receipts]` or plainer), and passes the same no-shame-vocabulary guard; (c) **it is not called anywhere in production** (AST/grep structural test — v0 does not wire it; the planner keeps getting tool_failure only). (d) Regression: existing block formatting for tool_failure byte-identical.
- [ ] **Step 2-4: RED → implement (class-filter in format_for_prompt + the standalone neutral formatter) → GREEN.** — [ ] **Step 5: Commit** `feat(scar): exclude scar classes from the past-mistakes block; neutral formatter (unwired)`

---

## Task 5: backfill the four exhibits (witnessed)

**Files:** Create `scripts/scar_backfill_exhibits.py`; Test `tests/test_scar_backfill.py` (create)

- [ ] **Step 1:** Script with two modes: `list` (prints the 4 rows — ids, previews, the scar episode each would become; **no mutation**) and `apply --owner-approved` (for each: compose scar episode citing the original row id as receipt + `exhibit:<original_id>` dedup key; register in sidecar; the original hot rows then follow the ordinary archive path — same collections the ceremony used). Test with a tmp episode store + tmp sidecar: list mutates nothing; apply creates exactly 4 scar episodes with correct citations; idempotent (second apply refuses — dedup keys exist).
- [ ] **Step 2: Commit** `feat(scar): 4-exhibit backfill tooling (list/apply, owner-gated, idempotent)`

---

## Task 6: regression + STOP at review gate

- [ ] **Step 1:**
```bash
/home/rohit/maez/.venv/bin/python -B -W ignore::ResourceWarning -m unittest \
  tests.test_scar_receipts tests.test_scar_tissue tests.test_scar_hooks tests.test_scar_backfill \
  tests.test_metabolic_trust_tier tests.test_metabolic_store_seam \
  tests.test_recall_floor tests.test_living_recall -v
```
- [ ] **Step 2:** ruff on touched files; `git diff --check`; flag-off byte-identical re-run.
- [ ] **Step 3: STOP.** No merge, no flag flip, no backfill apply. Codex cross-lane → then the owner sequence: merge dormant → `MAEZ_SCAR_TISSUE=1` + restart → live witness (trigger a real rail catch → scar episode with receipts appears; a related later conversation surfaces it naturally via ordinary recall; no shame language; `[LEARNED FROM PAST MISTAKES]` still serves tool_failure only) → backfill: `list` shown to Rohit → `apply --owner-approved`.

## Self-Review
**Spec coverage:** receipt-grade enforced (Task 2 validation + Task 1 id + consequence-row-as-receipt); both rail classes INCLUDED via minted receipts; shame-block exclusion + unwired neutral formatter + regression on tool_failure block (Task 4, per Codex's note); append-preserving dedup sidecar + supersede path (Task 2); card widening with exactly-one-row (Task 3); memory_voice=external_to_maez pinned from Task 0 (single-reader proof); backfill witnessed + idempotent (Task 5); flag-off byte-identical (invariant + tests).
**Placeholder scan:** Task 1's test defers to the module's existing tmp-db fixture pattern by name — a build-time adaptation, not a TODO. No other deferrals.
**Type consistency:** `ScarEvent(scar_class, surface, context, correction, receipt_refs, dedup_key)`; `record_scar(event, *, episode_store, sidecar, consequence_id) -> dict`; `ScarSidecar.register/append_evidence/supersede_active/get/active_episode`; `compose_scar_text(...) -> str`; `format_scars_neutral(events)` — consistent across tasks.
**Known risk named:** the fabrication hook's placement (audit caller vs judge caller) is the one seam the implementer locates at build; the flag-gate + fail-safe wrapper makes a wrong-but-safe placement recoverable without host breakage.
