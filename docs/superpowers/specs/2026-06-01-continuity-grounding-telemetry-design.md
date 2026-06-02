# Continuity-Grounding Telemetry Fix — Design

**Date:** 2026-06-01
**Status:** Design approved (Rohit, 2026-06-01). Pre-registration. Spec-first.
**Predecessors:** The owner-run mini re-witness (2026-06-01, recall-triad posture) proved the original No-Go #5/#6 continuity blocker is **cleared** — "what were we just talking about, the 3 may bugs?" now recaps the real seed from the `dialogue_anchor` with no archival derail. But it surfaced a telemetry mis-score: faithful continuity recaps logged `outcome_class=answered_ungrounded` because the grounding check counts only `memory_context` as grounded. This is the same family as the [recall-outcome classification slice](2026-05-31-recall-outcome-classification-correctness-design.md) ([[feedback_labels_prove_shape_not_support.md]]): the scoreboard libeling honest behavior.

---

## 1. Why this exists (witnessed)

Mini re-witness, 2026-06-01, recall-triad on:
- Probe (a) "What were we just talking about?" → **faithful recap**, `turn_kind=continuity`, `source_types=dialogue_anchor` → logged **`answered_ungrounded`**.
- Probe (b) "…the 3 may bugs?" → **faithful, no derail**, `continuity` / `dialogue_anchor` → logged **`answered_ungrounded`**.

Cause: `citation_support` returns `"grounded"` only via `cites_confirmed_memory_context` (every cited label a confirmed `memory_context`). A continuity turn's authoritative source is the `dialogue_anchor`, not dated memory — so a correct continuity recap is structurally scored `ungrounded`. If we re-run the six-prompt smoke against this, every faithful continuity turn produces a **false red** exactly where live behavior is good, wasting the gate and muddying the verdict.

## 2. Goal & non-goals

**Goal:** a continuity turn that grounds in its authoritative source (the `dialogue_anchor`) scores `answered_grounded`; a continuity turn that reaches into memory / cites invalid or contaminated support scores `answered_ungrounded` — so the smoke reads honestly.

**Non-goals (explicit):**
- **NO behavior/cognition change.** Classification only; synthesis/model/anchor-selection untouched. Recall stays **off**.
- **`cites_confirmed_memory_context` stays byte-identical** (the strict dated primitive).
- **Dated, both-shaped, and `answered_mixed_support` semantics byte-stable.**
- **NOT the grammar gap** ("covered"/"chatting" classifier misses) — optional polish, out of scope, not in the smoke set.
- **Does NOT widen `answered_mixed_support`** — mixed stays a both-shaped-only concept.

## 3. The fix — a continuity branch in `citation_support`, ordered FIRST

The current `cites_confirmed_memory_context → "grounded"` check is **turn-kind-agnostic**, so a continuity turn that cited a `memory_context` row would wrongly pass as grounded — the exact stale-memory failure we must catch. The continuity branch therefore comes **before** the memory check:

```python
def citation_support(result, working_set, turn_kind: str = "dated") -> str:
    if turn_kind == "continuity":
        return _continuity_support(result, working_set)
    if cites_confirmed_memory_context(result, working_set):
        return "grounded"
    if turn_kind != "both":
        return "ungrounded"
    # ... existing both-shaped logic, unchanged ...
```

`_continuity_support` (new helper; parallel in shape to the both-branch, but keyed on `dialogue_anchor`):
- cited non-empty, all cited labels valid (subset of the working set) — else `"ungrounded"`,
- **≥1 cited item is a `dialogue_anchor`** AND **every cited item is a `dialogue_anchor`** → `"grounded"`,
- any cited item that is not a `dialogue_anchor` (memory_context, memory_evidence, temporal_recall_status, etc.) → `"ungrounded"` (contaminated / stale path).

A `dialogue_anchor` is authoritative-by-construction for "what did we just say" (it is the literal recent exchange), so grounding a continuity recap in it is honest grounding. Memory on a continuity turn is not a legitimate supplement (unlike the both-shaped case) — it is the stale rail this fix exists to flag. `cites_confirmed_memory_context` is **not modified**; continuity simply never routes through it.

## 4. The honest ladder (now complete)

- **`answered_grounded`** — the turn cited the *authoritative* substrate for its kind: dated → confirmed `memory_context`; continuity → valid `dialogue_anchor` (all citations of that kind).
- **`answered_mixed_support`** — both-shaped (dated+continuity) only: confirmed memory present and carrying the dated fact, with `dialogue_anchor` a legitimate supplement.
- **`answered_ungrounded`** — wrong-kind support, invalid support, or contaminated support (incl. a continuity turn that cited memory).

## 5. Consumer wiring + the A5 invariant (corrected — there IS an eval wiring change)

**Daemon — no change.** It already derives `_rk_cited_grounded = (_rk_support == "grounded")` ([daemon/maez_daemon.py:4693-4696](../../../daemon/maez_daemon.py)) and passes that to `classify_outcome`, so it picks up the continuity branch automatically.

**Eval scripts — DO need a one-line change each.** [probe_runner.py:262](../../../scripts/brain_bench/probe_runner.py) and [harness.py:167](../../../scripts/recall_flip_eval/harness.py) currently pass `cited_grounded_context=grounded` where `grounded = cites_confirmed_memory_context(...)` (strict) — they compute `support` but only use it for `cited_mixed_support`. Today `support=="grounded"` ⟺ `cites_confirmed`, so it was invisible; the continuity branch makes them diverge for continuity turns. Change both to:
- `cited_grounded_context=(support == "grounded")` — so eval matches the daemon and reflects continuity-grounded.
- **Keep the emitted `cited_confirmed_memory_context=grounded` field strict** (the field `assert_probe_result` reads at `probes.py:112`) — so benchmark categorical grounding still cannot be cleared by mixed/continuity support.
- Byte-stable for dated/both probes (the continuity branch only fires for `turn_kind="continuity"`).

**A5 dated-rescue must stay dated/both-scoped — and make it STRUCTURAL.** Today `derive_shadow_outcome` ([core/routing/recall_shadow.py:121-135](../../../core/routing/recall_shadow.py)) date-gates `false_absence` but NOT `rescuable_candidate` / `legacy_false_absence_rescuable` (those are `grounded`-only). The live path is date-gated via `_shadow_should_attempt`, but the function itself is not. Harden it:
- `rescuable_candidate = bool(date_addressed and legacy_rec.outcome_class in _LEGACY_RESCUABLE_FROM and grounded)`
- `legacy_false_absence_rescuable = bool(date_addressed and is_false_absence(legacy_rec) and grounded)`
- Direct unit test: non-dated turn + `ShadowReach.GROUNDED_MATERIAL_AVAILABLE` → `rescuable_candidate=False`, `legacy_false_absence_rescuable=False`.

This is hardening, not behavior expansion (the live path already never feeds non-dated turns here). The flip-spec / runbook A5 benefit definition stays dated-only.

## 6. Tests (pre-registered)

- continuity + `dialogue_anchor` only → `grounded`
- continuity + `memory_context` only → `ungrounded` (the structural trap — must come before the memory check)
- continuity + `dialogue_anchor` + `memory_context` → `ungrounded` (contaminated)
- continuity + invalid/unmatched label → `ungrounded`
- continuity + empty citations → `ungrounded`
- **dated path byte-stable** (existing `citation_support`/`classify_outcome` dated tests unchanged)
- **both / `answered_mixed_support` path byte-stable**
- **A5 structural invariant (direct shadow unit test):** `derive_shadow_outcome(date_addressed=False, shadow_reach=GROUNDED_MATERIAL_AVAILABLE, …)` → `rescuable_candidate=False` AND `legacy_false_absence_rescuable=False`; and the dated case stays unchanged (`date_addressed=True` + rescuable-legacy + grounded → `rescuable_candidate=True`).
- **Daemon-shaped (REQUIRED — the witnessed bug was a daemon log mis-score):** a `handle_message` continuity turn whose focused answer cites a `dialogue_anchor` logs `turn_kind=continuity` + `outcome_class=answered_grounded` end-to-end (model on the same `test_memory_integrity_invariant.py` harness used for the mixed-support test). A continuity turn that cites memory logs `answered_ungrounded`.
- **Eval consistency:** a continuity probe with a `dialogue_anchor` citation now classifies `answered_grounded` via `cited_grounded_context=(support=="grounded")`, while its emitted `cited_confirmed_memory_context` field stays `False` (strict) so `grounded_categorical` is unmoved.

## 7. Covenant / honesty invariants

- **Labels prove shape, not semantic support** ([[feedback_labels_prove_shape_not_support.md]]): continuity is grounded only via its authoritative source; contamination fails rather than launders. The strict primitive and the closed-state meanings stay one-thing-each.
- **No behavior/cognition change; recall stays off; `cites_confirmed_memory_context` byte-identical; dated/both/mixed byte-stable.**
- Makes the scoreboard stop calling a good continuity answer bad — so the six-prompt smoke measures the real thing, not a crooked instrument.

## 8. Process & sequence

Codex switchboard (six-agent + 7+3); Claude cross-verifies every diff, runs suites independently, fires the coverage panel; merge on the legacy baseline (recall off). **Lands BEFORE the six-prompt re-smoke** so continuity turns score honestly. After it merges: owner-run six-prompt smoke on the now-honest scoreboard → read latency honestly (the likely true remaining gate). The grammar gap (covered/chatting) and any latency work are separate, later.
