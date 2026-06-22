# Grounding-Meter Task 0 — Constructor Inventory (Trailing Defaults Safety Proof)

**Date:** 2026-06-22
**Branch:** grounding-meter-slice1
**Investigator:** Task 0 STOP-gate agent
**Purpose:** Prove that adding 3 trailing defaulted fields to `GroundednessVerdict` and 1
trailing defaulted field to `RecallOutcome` breaks no existing constructor call.

---

## Dataclass definitions (current, pre-change)

### `GroundednessVerdict` — `core/routing/focused_cognition.py:432`

```python
@dataclass(frozen=True)
class GroundednessVerdict:
    verdict: str                # field 1 (positional slot 0)
    citation_coverage: float    # field 2 (positional slot 1)
    unmatched: list[str]        # field 3 (positional slot 2) — LAST non-default
```

Proposed new trailing fields (all defaulted, appended after `unmatched`):
- `reply_grounding: float = 0.0`       (slot 3)
- `grounded_sentences: int = 0`        (slot 4)
- `total_sentences: int = 0`           (slot 5)

### `RecallOutcome` — `core/routing/recall_outcome.py:56`

Non-default fields (slots 0–9): `mode`, `turn_kind`, `outcome_class`, `denial_kind`,
`had_confirmed`, `citation_coverage`, `receipt_or_na`, `latency_ms`,
`focused_elapsed_ms`, `reply_path`

Existing defaulted tail (slots 10–15): `shadow_pair_id="na"`, `receipt_eligible=False`,
`receipt_after_ms=None`, `ack_required=False`, `ack_status="not_eligible"`,
`ack_emit_ms=None`

Proposed new trailing field (appended after `ack_emit_ms`):
- `reply_grounding: float | None = None`  (slot 16)

---

## GroundednessVerdict constructor sites

| # | File:line | Style | Args | Positional count | Safe under trailing defaults? |
|---|-----------|-------|------|-----------------|-------------------------------|
| 1 | `core/routing/focused_cognition.py:1143` | KEYWORD | `verdict=`, `citation_coverage=`, `unmatched=` | 0 positional | YES |
| 2 | `core/routing/focused_cognition.py:1492` | KEYWORD | `verdict=`, `citation_coverage=`, `unmatched=` | 0 positional | YES |
| 3 | `tests/test_memory_integrity_invariant.py:672` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |
| 4 | `tests/test_memory_integrity_invariant.py:894` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |
| 5 | `tests/test_memory_integrity_invariant.py:938` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |
| 6 | `tests/test_memory_integrity_invariant.py:987` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |
| 7 | `tests/test_memory_integrity_invariant.py:1034` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |
| 8 | `tests/test_memory_integrity_invariant.py:1353` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |
| 9 | `tests/test_memory_integrity_invariant.py:1397` | POSITIONAL | `"grounded", 0.5, []` | 3 | YES |
| 10 | `tests/test_memory_integrity_invariant.py:1443` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |
| 11 | `tests/test_memory_integrity_invariant.py:1493` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |
| 12 | `tests/test_memory_integrity_invariant.py:1547` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |
| 13 | `tests/test_recall_flip_eval_probes.py:229` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |
| 14 | `tests/test_focused_cognition.py:1094` | POSITIONAL | `"grounded", 0.5, []` | 3 | YES |
| 15 | `tests/test_focused_cognition.py:1125` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |
| 16 | `tests/test_focused_cognition.py:1171` | POSITIONAL | `"grounded", 1.0, []` | 3 | YES |

**Total sites: 16**

Safety reasoning for positional sites (rows 3–16): every call passes exactly 3 positional
args, filling slots 0/1/2 (`verdict`, `citation_coverage`, `unmatched`). The 3 new fields
occupy slots 3/4/5 with defaults — they are never touched by an existing positional call.
No collision possible.

Safety reasoning for keyword sites (rows 1–2): keyword calls are unaffected by field
ordering or the addition of new trailing fields with defaults.

---

## RecallOutcome constructor sites

| # | File:line | Style | Notes | Safe under trailing defaults? |
|---|-----------|-------|-------|-------------------------------|
| 1 | `daemon/maez_daemon.py:7478` | KEYWORD | All 16 current fields passed by name (`mode=`, `turn_kind=`, ..., `ack_emit_ms=`) | YES |
| 2 | `tests/test_recall_shadow.py:31` | KEYWORD | 10 non-default fields by name; defaulted tail left at defaults | YES |
| 3 | `tests/test_recall_outcome.py:434` | KEYWORD via `**base` | `base` dict built from keyword entries for non-default fields only | YES |
| 4 | `tests/test_recall_outcome.py:494` | KEYWORD | 10 non-default fields by name | YES |
| 5 | `tests/test_recall_outcome.py:510` | KEYWORD | 10 non-default fields by name (intentional bogus `reply_path` to test ValueError) | YES |
| 6 | `tests/test_recall_outcome.py:539` | KEYWORD via `**base` | Same pattern as row 3 | YES |

**Total sites: 6**

Safety reasoning: every `RecallOutcome` constructor is keyword-only (or dict-unpacked).
No site passes positional arguments at all. Adding a new trailing defaulted field
`reply_grounding: float | None = None` at slot 16 cannot interfere with any existing call.

---

## Field-name collision check

Searched entire repo (`core/`, `daemon/`, `tests/`, `scripts/`) for
`reply_grounding`, `grounded_sentences`, `total_sentences`:

```
grep -rn "reply_grounding\|grounded_sentences\|total_sentences" core/ daemon/ tests/ --include="*.py"
```

Result: **zero hits**. None of these names exist anywhere in the codebase today.
No collision for `GroundednessVerdict` or `RecallOutcome`.

---

## Field order feasibility confirmation

- `GroundednessVerdict` currently has NO defaulted fields; `unmatched` is the last
  (and only non-default) field. Python dataclass rules require defaulted fields after
  non-default ones. The 3 new fields are all defaulted and will be appended after
  `unmatched` — valid by dataclass rules.

- `RecallOutcome` already has a defaulted tail (`shadow_pair_id` through `ack_emit_ms`).
  Appending another defaulted field at the end is valid by dataclass rules.

---

## VERDICT

**ALL SAFE — trailing defaults break no constructor.**

All 16 `GroundednessVerdict` sites and all 6 `RecallOutcome` sites are safe. The 3
proposed trailing fields for `GroundednessVerdict` and the 1 proposed trailing field for
`RecallOutcome` may be added without modification to any existing call site. No field-name
collisions exist. No positional-arg overflow exists. No stop condition triggered.
