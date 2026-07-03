# Scar Tissue (A1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Deterministic correction-events (fabrication catches, claim-receipt redos, dream rejections, proven-wrong vetoes, card rejections) become receipt-grade scar episodes in Maez's autobiography — neutral, deduplicated, fading via ordinary salience — plus consequence rows for the planner, with scar classes excluded from the `[LEARNED FROM PAST MISTAKES]` block.

**Architecture:** One pure module `core/learning/scar_tissue.py` (validation + dedup sidecar + substrate-composed episode text), four thin hooks at seams that already detect the events, one widened existing write (`card_rejected`), one small backfill script for the 4 exhibits. All writers behind `MAEZ_SCAR_TISSUE` (default-off, flag-off byte-identical).

**Tech Stack:** Python 3.12; host tests `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest).

**Spec:** `docs/superpowers/specs/2026-07-02-scar-tissue-a1-design.md` (@be8fa1c).

**Task 0 (DONE 2026-07-02 — plan written on this ground):** episode `add()` fields are open strings (no closed enums) → `source_kind="scar"`/`authorship="scar_detector"` write-safe. `memory_voice` has ONE reader (memory_manager:683, telemetry/parked-damp) → **pin `memory_voice="external_to_maez"`** (semantically right — the correction came from outside; avoids the `maez_self` parked-promotion damp; proven ordinary recall candidate). `lived_recall`'s only source_kind special case is `"reflection"` (:877) → scars content-blind. Receipts: `fabrication_memory.record_event` returns None today (add lastrowid return); the redo class's durable receipt is minted by **Landing 1's own consequence row id**; `dream_state.reject_proposal(prop_id, reason)` and `veto_ledger.attach_reask_outcome(...)→"likely_wrong"` are single-seam hooks; `card_rejected` write to widen at decision_pipeline ~2117 (id currently discarded). Both rail classes therefore stay **INCLUDED**.

## Hard Invariants
- Flag-off (`MAEZ_SCAR_TISSUE` unset): byte-identical behavior everywhere (incl. the card_rejected WRITE path). **One NAMED reader-side change ships with this slice regardless of flag** (spec-sanctioned, Landing 1): scar classes leave the `[LEARNED FROM PAST MISTAKES]` retrieval+render path — which moves the 6 existing `card_rejected` rows out of planner hints. This is called out in the commit's `## Predicted effect` and the handoff artifact; it is never silent.
- **Receipt-grade or nothing, with pinned ORDER (Codex plan-HOLD fix #2):** `record_scar` first mints/reuses the consequence row (that id is itself a durable receipt), THEN validates the combined receipt set; zero resolvable refs after minting raises. Never degrades to a log-line citation.
- Scar classes NEVER render inside `[LEARNED FROM PAST MISTAKES]` — enforced at BOTH retrieval (`relevant(exclude_classes=...)`) and formatter, so scar rows can't starve `limit=3` slots (Codex plan-HOLD fix #4). The neutral formatter exists but is NOT wired to the planner in v0. `tool_failure` block behavior unchanged (regression check, not a scar path — per Codex note).
- Scar SCAFFOLD text is substrate-composed (zero LLM) and passes the no-shame/no-directive vocabulary guard; the verbatim correction content is exempt but clearly labeled as the quoted correction (Codex plan-HOLD fix #3 — Rohit saying "never do X" must not make the scar unwritable).
- Dedup is append-preserving: sidecar accumulates receipts; episodes only ever add/supersede.
- `tool_failure` produces NO scar episode.
- **Class boundary (Codex plan-HOLD fix #1):** `fabrication_catch` = judge-flag rewrites ONLY (the path that persists fabrication_events). Action-narration mismatches return at self_claim_audit:1002 BEFORE fabrication persistence — they scar via `claim_receipt_redo` (the daemon redo-outcome hook, enforce mode). Shadow-mode mismatches do NOT scar in v0: nothing corrected Maez's output, so there is no correction to remember.

---

## Task 1: fabrication receipt ids — minted AND plumbed to the caller

**Files:** Modify `core/learning/fabrication_memory.py`, `core/safety/self_claim_audit.py` (`_emit` ~1090-1153, `AuditResult` dataclass, `audit()` return sites); Test `tests/test_scar_receipts.py` (create)

Codex plan-HOLD fix #1: returning the id from `record_event` is not enough — `_emit` (self_claim_audit:1134) discards it and `AuditResult` has nowhere to carry it, so Task 3's hook could never cite `fabrication:<id>`. This task plumbs the full path: `record_event` returns lastrowid → `_emit` collects the ids and returns them → `audit()` threads them into a new `AuditResult.fabrication_receipt_ids: list[int] | None = None` field (additive, default None — every existing constructor call site unchanged).

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

Plus the plumbing tests (same file):
```python
class AuditResultReceiptPlumbingTests(unittest.TestCase):
    def test_audit_result_carries_fabrication_receipt_ids(self):
        from core.safety.self_claim_audit import AuditResult
        r = AuditResult(text="x", rewritten=False, mode="noop")
        self.assertIsNone(r.fabrication_receipt_ids)  # additive default — no call site breaks

    def test_emit_returns_collected_ids(self):
        # mock fabrication_memory.record_event -> 7 then 8; call _emit with two flags;
        # assert it returns [7, 8]; with flags=[] it returns [] (or None) without importing fabrication_memory
        ...

    def test_action_claim_mismatch_result_has_no_fabrication_ids(self):
        # the :981-1008 mismatch path returns BEFORE fabrication persistence —
        # assert its AuditResult.fabrication_receipt_ids is None (this pins the
        # class boundary: mismatches are claim_receipt_redo material, never fabrication_catch)
        ...
```
- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** — `record_event`: `INSERT` → `return cur.lastrowid`; early returns → `return None`; docstring contract. `_emit`: collect non-None ids into a list, `return ids`. `audit()`: at the judge-rewrite return sites that called `_emit` with flags, pass the returned ids into `AuditResult(..., fabrication_receipt_ids=ids or None)`; all other return sites untouched (field defaults None). — [ ] **Step 4: GREEN + existing fabrication AND self_claim_audit tests still pass.** — [ ] **Step 5: Commit** `feat(scar): fabrication receipt ids minted and plumbed through AuditResult`

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

    def test_redo_scar_succeeds_via_minted_consequence_receipt(self):
        # Codex plan-HOLD fix #2: claim_receipt_redo arrives with NO external receipt —
        # record_scar mints the consequence row FIRST, and validation then passes on
        # that minted id alone. (Mock consequence record_event -> 42, tmp sidecar +
        # fake episode store; assert episode written with "consequence:42" in refs.)
        from core.learning.scar_tissue import ScarEvent, record_scar
        e = ScarEvent(scar_class="claim_receipt_redo", surface="daemon",
                      context="action=web_search outcome=floor",
                      correction="claim lacked receipt; reply held to facts",
                      receipt_refs=[], dedup_key="redo:web_search:p1")
        # ... record_scar(e, episode_store=fake, sidecar=s) -> refs contain "consequence:42",
        # no ValueError. A second event with receipt_refs=[] and a FAILING consequence
        # write (mock returns None) DOES raise — minting is the only thing that saved it.

    def test_tool_failure_is_not_scar_grade(self):
        from core.learning.scar_tissue import SCAR_CLASSES
        self.assertNotIn("tool_failure", SCAR_CLASSES)
        for c in ("fabrication_catch", "claim_receipt_redo", "dream_rejected",
                  "veto_proven_wrong", "card_rejected"):
            self.assertIn(c, SCAR_CLASSES)

    def test_scaffold_text_is_neutral(self):
        # Codex plan-HOLD fix #3: the guard applies to the SCAFFOLD (generated text),
        # not the verbatim correction — compose with an empty-marker correction and
        # scan everything that remains.
        from core.learning.scar_tissue import compose_scar_text, CORRECTION_MARKER
        text = compose_scar_text(
            scar_class="card_rejected", surface="decision_pipeline",
            context="action=run_shell cmd='rm -rf tmp'", correction=CORRECTION_MARKER,
            receipt_refs=["consequence:42", "card:abc"], occurred_at="2026-07-02T12:00:00Z",
        )
        scaffold = text.replace(CORRECTION_MARKER, "")
        for banned in ("mistake", "never ", "should not", "avoid ", "failed to",
                       "sorry", "apolog", "shame", "must not"):
            self.assertNotIn(banned, scaffold.lower())
        self.assertIn("consequence:42", text)          # receipts visible

    def test_verbatim_correction_with_hot_words_still_composes_and_is_labeled(self):
        # Rohit's real rejection reason may say "never do X" — that must not make
        # the scar unwritable, and it must read as the QUOTED correction, not scaffold voice.
        from core.learning.scar_tissue import compose_scar_text
        text = compose_scar_text(
            scar_class="dream_rejected", surface="telegram",
            context="proposal 7", correction="never do this again, you failed to check",
            receipt_refs=["consequence:9", "dream:7"], occurred_at="2026-07-02T12:00:00Z",
        )
        self.assertIn("never do this again, you failed to check", text)  # verbatim preserved
        self.assertIn('The correction: "', text)  # quoted/labeled as the correction receipt


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

CORRECTION_MARKER = "\x00CORRECTION\x00"  # test seam for scaffold-only vocabulary scan

def compose_scar_text(...) -> str:
    # substrate-composed, zero LLM. Shape:
    # 'Correction received (<scar_class>, <surface>, <occurred_at>). Context: <context>.
    #  The correction: "<correction verbatim>". Receipts: <refs>.'
    # Scaffold carries no advice and no shame vocabulary (guard test); the correction
    # is embedded VERBATIM inside quotes labeled "The correction:" — hot words in
    # Rohit's own phrasing are the receipt, not scaffold voice.

class ScarSidecar: ...  # sqlite: dedup_key PK, active_episode_id, prior_episode_ids_json,
                        # receipt_refs_json, occurrence_count, first_ts, last_ts
                        # register / append_evidence / supersede_active / get / active_episode

def record_scar(event, *, episode_store, sidecar, consequence_id=None,
                now_iso=None) -> dict:
    # PINNED ORDER (Codex plan-HOLD fix #2):
    # 1. mint/reuse the consequence row FIRST (reuse consequence_id if given, else
    #    record_event); its id joins receipt_refs as "consequence:<id>"
    # 2. THEN validate_scar on the combined receipt set (a redo event that arrived
    #    with refs=[] passes here solely because step 1 minted; a failed mint raises)
    # 3. sidecar: new dedup_key? add episode (source_kind="scar", authorship="scar_detector",
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
Per hook: **fabrication_catch** — at the daemon caller of `audit()`, fires ONLY when `result.fabrication_receipt_ids` is non-empty (judge-rewrite path — the one that persists fabrication_events; Task 1 plumbing). Action-claim mismatches are NOT this class (their `fabrication_receipt_ids` is None — pinned by Task 1's test); receipt = `fabrication:<id>` per id + consequence id; dedup = fabrication token. **claim_receipt_redo** — both `accepted` and `floor` branches of the daemon redo-outcome seam (~8204-8250); this is also where enforce-mode action-claim mismatches earn their scar (the redo IS the correction); shadow-mode mismatches do not scar in v0 (nothing was corrected); receipt = consequence id (minted by record_scar step 1 — this row IS the durable redo receipt); dedup = `redo:<action_type>:<pattern_id>`. **dream_rejected** — Codex plan-pin: NOT inlined in `DreamState.reject_proposal` (multi-surface caller, no episode store in scope). Instead `DreamState` gains `scar_hook: Callable | None = None` (attribute, default None = flag-off byte-identical); the daemon wires it at startup when the flag is on (closure over its own episode store + sidecar); `reject_proposal` invokes it fail-safe on success only. All surfaces (telegram `_handle_reject_dream`:4591, cockpit, CLI) are covered through the one method without the store leaking into `dream_state`; receipt = `dream:<prop_id>` + consequence id; dedup = `dream:<prop_id>`. **veto_proven_wrong** — where `attach_reask_outcome` returns `"likely_wrong"` (veto_ledger:93 caller); receipt = `veto:<event_id>` + consequence id; dedup = `veto:<event_id>`. **card_rejected** — WIDEN the existing `record_event` call at decision_pipeline ~2117: capture its return id, pass as `consequence_id` (assert exactly one consequence row per rejection), receipt = `card:<action_id>` + that id; dedup = `card:<action_id>`.

- [ ] **Step 1: Failing tests** — per hook, with mocked stores: flag-off → zero scar calls AND (card path) the existing single record_event still fires identically; flag-on → one `record_scar` with correct class/receipts/dedup; hook exception → host path unaffected (fail-safe test). Dream-specific: `scar_hook=None` (default) → `reject_proposal` behavior byte-identical; hook wired → invoked exactly once on a successful rejection, NOT invoked on not-found or already-resolved proposals, and a raising hook doesn't break the rejection. Fabrication-specific: an `AuditResult` with `fabrication_receipt_ids=None` (mismatch path) triggers NO fabrication_catch scar.
- [ ] **Step 2: RED. Step 3: implement. Step 4: GREEN + flag-off byte-identical suite.** — [ ] **Step 5: Commit** `feat(scar): wire the five deterministic scar sources (flag-gated, fail-safe)`

---

## Task 4: planner-block exclusion + neutral formatter

**Files:** Modify `core/learning/consequence_memory.py` (`format_for_prompt`, `relevant`), `core/brain/brain_loop.py` (~2238 call site); Test additions to `tests/test_scar_tissue.py`

Codex plan-HOLD fix #4: formatter-only filtering still lets scar rows occupy all of `relevant(limit=3)`'s slots before the formatter drops them — the tool_failure block would silently starve. Exclusion happens at BOTH layers: `relevant()` gains `exclude_classes: tuple[str, ...] = ()` (default empty — no behavior change for other callers), the brain_loop call site passes `exclude_classes=SCAR_CLASSES`, and `format_for_prompt` also skips scar classes (defense for callers that don't pass the param). **Named behavior change:** the 6 existing `card_rejected` rows leave planner hints (spec reassigns card_rejected to the scar landing); called out in the commit's `## Predicted effect` — never silent.

- [ ] **Step 1: Failing tests** — (a) `format_for_prompt` given a mixed event list renders `tool_failure` rows under `[LEARNED FROM PAST MISTAKES]` **and silently omits scar-class rows** (assert none of the scar contexts appear); (b) **starvation regression:** seed a tmp store with 5 scar-class rows + 2 `tool_failure` rows all sharing query tokens; `relevant(context_snippet=..., limit=3, exclude_classes=SCAR_CLASSES)` returns the 2 tool_failure rows (scars can't eat the slots); with `exclude_classes=()` behavior is unchanged from today; (c) `format_scars_neutral(events)` exists, renders event+correction+receipts with a neutral header, scaffold passes the no-shame guard; (d) **it is not called anywhere in production** (AST/grep structural test — v0 does not wire it; the planner keeps getting tool_failure only); (e) Regression: existing block formatting for tool_failure byte-identical.
- [ ] **Step 2-4: RED → implement (`relevant(exclude_classes)` + brain_loop passes SCAR_CLASSES + class-filter in format_for_prompt + the standalone neutral formatter) → GREEN.** — [ ] **Step 5: Commit** `feat(scar): scar classes excluded from past-mistakes retrieval+render; neutral formatter (unwired)` — with `## Predicted effect: existing card_rejected rows (6) stop appearing in planner hints; tool_failure hints unchanged and no longer starvable by scar rows.`

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
**Codex plan-HOLD (2026-07-02) folded, all four verified in code first:** (1) fabrication receipt ids fully plumbed (`record_event` lastrowid → `_emit` returns ids → `AuditResult.fabrication_receipt_ids`), and the class boundary pinned — action-claim mismatches return at self_claim_audit:1002 before fabrication persistence, so they scar via `claim_receipt_redo` (enforce mode) and never as `fabrication_catch`; (2) `record_scar` order pinned mint-then-validate with the refs=[]-redo test; (3) no-shame guard scoped to scaffold via `CORRECTION_MARKER`, verbatim corrections quoted + labeled; (4) scar exclusion at retrieval (`relevant(exclude_classes)`) AND formatter, with a starvation regression test; plus the dream hook moved from inlining in `reject_proposal` to a daemon-wired `scar_hook` callback (default None = byte-identical, all surfaces covered, no store leak into dream_state).
**Known risk resolved:** the fabrication hook placement question is closed by the AuditResult plumbing — the hook keys on `fabrication_receipt_ids` at the daemon caller, not on locating a seam inside the audit module. Remaining named change: the 6 existing card_rejected rows leaving planner hints is deliberate and carried in the Task 4 `## Predicted effect`.
