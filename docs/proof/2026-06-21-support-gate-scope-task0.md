# Support-Gate-Scope — Task 0 Proof Gate (repo-wide source_type inventory + seam)

**Date:** 2026-06-21. **Verdict: GO.** Branch `support-gate-scope-fresh`. Controller-verified (owner calibration: Task 0 light). The predicate-completeness STOP **passes**.

## REPO-WIDE `source_type` inventory (Codex guard — not just `_AUTHORITY_LABEL`)

`grep -rhoE "source_type=[\"'][a-z_]+[\"']" core/ daemon/ skills/` → 9 real values, classified vs THIS gate seam:

| source_type | class | reaches gate seam? | in `_FRESH_SOURCE_TYPES`? | verdict |
|---|---|---|---|---|
| `fresh_evidence` | fresh/current (observed/tool/body) | YES (focused branch) | **YES** | gated ✓ |
| `web_context` | web (external) | YES (focused branch) | **YES** | gated ✓ |
| `memory_evidence` | recall (past) | yes | no | correctly EXCLUDED (recall) |
| `memory_context` | recall (past) | yes | no | correctly EXCLUDED (recall) |
| `dialogue_anchor` | recall/continuity | yes | no | correctly EXCLUDED (recall) |
| `owner_message_context` | recall/context | yes | no | correctly EXCLUDED (recall) |
| `temporal_recall_status` | recall status | yes | no | correctly EXCLUDED (recall) |
| `signal_absence` | absence marker (not a claim) | yes | no | correctly EXCLUDED (no claim to check) |
| `empty_result` | absence marker (not a claim) | yes | no | correctly EXCLUDED (no claim to check) |
| `photo_vision` | fresh (first-party vision) | **NO** (see below) | no | OUT-of-v0 with proof |

(`observed` appears in `_AUTHORITY_LABEL` as a *label* for fresh items, not a distinct assigned `source_type` — fresh observations are tagged `fresh_evidence`, which IS gated.)

## `photo_vision` — fresh, but does NOT reach this seam (HARD item, PASS)

The photo-synthesis branch ([maez_daemon.py:6816-6840](../../daemon/maez_daemon.py#L6816)) calls `synthesize_photo_turn`, sets `reply`/`_focused_used=True`/`_reply_path=FOCUSED`, but does **NOT** build `_focused_support_evidence_map` (stays `{}` from :6607) and does **NOT** set `_focused_working_set` (stays `None` from :6604). `_focused_support_evidence_map` is built ONLY in the focused branch ([:6935](../../daemon/maez_daemon.py#L6935), after `_assemble_working_set` :6872). So the gate's outer `if _grounding_shadow_post_audit_ready and _focused_used and _focused_support_evidence_map:` is **falsy** on photo turns → the gate never convenes there today. `photo_vision` is correctly OUT-of-v0. **Defense-in-depth:** even if a photo turn reached the seam, `_focused_working_set` is `None` → `turn_has_fresh_evidence(None)` → `False` (fail-safe toward the voice) → gate skips. (If a future change DOES route photo through the support gate, add `photo_vision` to `_FRESH_SOURCE_TYPES` — first-party vision is a fresh claim worth checking.)

## Predicate-completeness STOP (PASS)

Every source_type classified "fresh/current AND reaches this seam" — `fresh_evidence`, `web_context` — IS in `_FRESH_SOURCE_TYPES`. No fresh-and-reaching type is missing. Recall (`memory_*`, `dialogue_anchor`, `owner_message_context`, `temporal_recall_status`) and absence markers (`signal_absence`, `empty_result`) are intentionally excluded. **GO.**

## Seam proof (PASS)

Gate block at [maez_daemon.py:7277](../../daemon/maez_daemon.py#L7277) (`decide_support_path` → `observe_focused_support_gate`/`observe_focused_support`), under `if _grounding_shadow_post_audit_ready and _focused_used and _focused_support_evidence_map:`. `_focused_working_set` in scope there (init `None` :6604, set :6872). `EvidenceItem.source_type` is the field ([focused_cognition.py:255/381](../../core/routing/focused_cognition.py#L255)). `evidence_map_from_working_set` returns `{label:text}` only ([grounding_shadow.py:369](../../core/cognition/grounding_shadow.py#L369)) — provenance-stripped, so the predicate MUST read the working set. No circular import: the daemon already imports from `core.routing.focused_cognition`. `_run_support_scope` extraction is clean.

**GO** — inventory complete, photo_vision proven OUT, STOP passes, seam confirmed.
