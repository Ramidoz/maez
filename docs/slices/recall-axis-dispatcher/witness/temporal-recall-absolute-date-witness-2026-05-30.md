# Witness — Temporal Recall v1 (Absolute-Date Anchoring) (2026-05-30)

**Slice:** Third of the recall-quality triad (living recall → continuity classifier → temporal
recall). Branch `temporal-recall-absolute-date` (`beb51e3`, `d6d51ed`, `6e1059b`, `1e8a3be`).
Implemented by Codex (Rohit-orchestrated), cross-verified + witnessed by Claude.
**Merged ff → `main @ 1e8a3be`, flag-off.**

## Cross-verification (Claude, independent)
- Diff read line-by-line; faithful to spec + plan + Rohit's amendments. Scope: 3 files
  (`memory/memory_manager.py`, `tests/test_memory_manager.py`, `tests/test_living_recall.py`);
  `core/routing/focused_cognition.py` **untouched** (0 lines).
- **Hard invariants honored:** (1) copy-don't-mutate persisted Chroma — `_tag_temporal_rows` tags
  `dict(meta)` copies, `test_persisted_chroma_metadata_not_mutated` guards it; (2) core never
  promoted to evidence — the date branch always returns `evidence={core:[],daily:[],raw:[]}`,
  date-confirmed rows land in context; (3) no `TemporalWindow` shadow (`AbsoluteRecallWindow`);
  (4) no non-temporal regression (early-return only when a window resolves).
- **Sound deviations:** `field_name="event_at"` (the temporal-spine's accepted instant field — the
  plan's `"timestamp"` would have made `try_canonical_utc` return `None` and silently break all date
  filtering; Codex caught a real bug in the plan); `_all_daily_rows` helper; both-form date labels;
  punctuation-stripped topic signal; `_RecallCollection` in-memory fake (seeds real rows, runs the
  real recall logic — not a mock of the logic under test).
- `.venv/bin/python -m unittest tests.test_memory_manager tests.test_living_recall
  tests.test_focused_cognition` → **123/123 OK** (run by Claude).
- Floor: the broad run shows a 3rd failure
  (`test_service_audit_behavior_records_cloud_retirement_without_raw_text`) that **passes in
  isolation on both clean `main` and the branch** → pre-existing full-suite ordering flake, not
  introduced (the branch touches no service-audit code; the integration test cleans up `os.environ`).

## Live witness (flag-on Telegram, instrumented `temporal_recall_witness` log; reverted after)
| Probe | Branch fired (definitive log) | Reply |
|---|---|---|
| "around April 27 …infrastructure?" | `exact_date window=2026-04-25..2026-04-30 core_in=3 daily_in=3 fallback=False` | recalled the April-27 TRELLIS.2 fabrication incident |
| "last month?" | `month_window window=2026-04-01..2026-05-03 core_in=3 daily_in=3 fallback=False` | April recap (pipeline diagnosis) |
| "what about January 3?" | `exact_date window=2026-01-01..2026-01-06 core_in=0 daily_in=0 fallback=False` | **honest "no record of January 3"** — no wrong-month confabulation |

`source_types=memory_context` confirmed date-confirmed rows reach context, never evidence. The
January-3 result is the decisive proof of corrigibility: empty window + no topic → no recall →
honest gap, where pre-change semantic recall would have dragged in the nearest journal. (The Jan
window is symmetric ±2 because "**about**" triggered the symmetric-tolerance rule — correct.)
Label-survival to `assemble_working_set` is proven in-process by
`test_absolute_date_label_survives_to_working_set` (date_match attribute present in a
`memory_context` working-set item).

## Posture
Merged flag-off: the absolute-date branch runs only when living recall / focused cognition is
enabled, inert in production until a default-on decision. `AbsoluteRecallWindow` is the layering
seam for the named-but-deferred v2 (event landmarks) and v3 (fuzzy relative) producers.
Daemon restored under the unit, flag-absent (PID 213951). Branch pruned (local; Rohit prunes Codex side).
