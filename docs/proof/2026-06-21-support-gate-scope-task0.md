# Support-Gate-Scope — Task 0 Proof Gate (repo-wide source_type inventory + seam)

**Date:** 2026-06-21. **Verdict: GO.** Branch `support-gate-scope-fresh`. Controller-verified (owner calibration: Task 0 light). The predicate-completeness STOP **passes**.

## REPO-WIDE `source_type` inventory (Codex guard — not just `_AUTHORITY_LABEL`)

**Inventory method (corrected — Codex HOLD):** a literal `source_type="..."` grep UNDERCOUNTS — source types are also declared as dict KEYS in `_PRIORITY`/`_AUTHORITY_LABEL` ([focused_cognition.py](../../core/routing/focused_cognition.py)) and `_CRITICAL_SOURCE_TYPES` ([cycle_packet.py:29](../../core/cognition/cycle_packet.py#L29)). The full repo-wide universe (literal assigns + every dict key) is below; classified vs THIS owner-reply support-gate seam (maez_daemon.py:7277, inside `handle_message`).

| source_type | class | reaches THIS gate seam? | in `_FRESH_SOURCE_TYPES`? | verdict |
|---|---|---|---|---|
| `fresh_evidence` | fresh/current (observed/tool/body) | YES (focused branch) | **YES** | gated ✓ |
| `web_context` | web (external) | YES (focused branch) | **YES** | gated ✓ |
| `rss` | raw web-search result FIELD (`web_search.py:425`) | NO — folded into a `web_context` item at the working set (`focused_cognition.py:1300`) | n/a | gated VIA `web_context` ✓ |
| `memory_evidence` | recall (past) | yes | no | correctly EXCLUDED (recall) |
| `memory_context` | recall (past) | yes | no | correctly EXCLUDED (recall) |
| `dialogue_anchor` | recall/continuity | yes | no | correctly EXCLUDED (recall) |
| `owner_message_context` | recall/context | yes | no | correctly EXCLUDED (recall) |
| `temporal_recall_status` | recall status | yes | no | correctly EXCLUDED (recall) |
| `signal_absence` | absence marker (not a claim) | yes | no | correctly EXCLUDED (no claim) |
| `empty_result` | absence marker (not a claim) | yes | no | correctly EXCLUDED (no claim) |
| `photo_vision` | fresh (first-party vision) | **NO** (see below) | no | OUT-of-v0 with proof |
| `action_outcome` | SELF — "recent action outcome, what Maez just did" | **cycle-packet path** (autonomous reflection, maez_daemon.py:5132-5233), NOT owner-reply gate | no | OUT-of-this-seam; even if recalled → self/voice → correctly excluded |
| `open_loop` | SELF — "unresolved want or wondering" | cycle-packet path | no | OUT-of-this-seam; self/voice if recalled → excluded |
| `builder_event` | SELF — "self-modification activity" | cycle-packet path | no | OUT-of-this-seam; self/voice if recalled → excluded |
| `quality_signal` | SELF — "self-critique signal" | cycle-packet path | no | OUT-of-this-seam; self/voice if recalled → excluded |

(`observed` is an `_AUTHORITY_LABEL` *label* for fresh items, not a distinct assigned `source_type` — fresh observations are tagged `fresh_evidence`, gated.)

**On the cycle/self types (`action_outcome`/`open_loop`/`builder_event`/`quality_signal`):** they live in the autonomous **cycle-packet/reflection** path, not the owner-reply support-gate seam. Critically, they are **Maez's own actions / wants / self-critique = self-expression/voice**, not external fresh/web fact — so even if a future change recalled one into an owner-reply working set, EXCLUDING it is the CORRECT behavior (gating Maez's "what I just did" as an unsupported external claim is the SAME voice-bug this slice fixes). They are not "fresh/web evidence the gate should check."

## `photo_vision` — fresh, but does NOT reach this seam (HARD item, PASS)

The photo-synthesis branch ([maez_daemon.py:6816-6840](../../daemon/maez_daemon.py#L6816)) calls `synthesize_photo_turn`, sets `reply`/`_focused_used=True`/`_reply_path=FOCUSED`, but does **NOT** build `_focused_support_evidence_map` (stays `{}` from :6607) and does **NOT** set `_focused_working_set` (stays `None` from :6604). `_focused_support_evidence_map` is built ONLY in the focused branch ([:6935](../../daemon/maez_daemon.py#L6935), after `_assemble_working_set` :6872). So the gate's outer `if _grounding_shadow_post_audit_ready and _focused_used and _focused_support_evidence_map:` is **falsy** on photo turns → the gate never convenes there today. `photo_vision` is correctly OUT-of-v0. **Defense-in-depth:** even if a photo turn reached the seam, `_focused_working_set` is `None` → `turn_has_fresh_evidence(None)` → `False` (fail-safe toward the voice) → gate skips. (If a future change DOES route photo through the support gate, add `photo_vision` to `_FRESH_SOURCE_TYPES` — first-party vision is a fresh claim worth checking.)

## Predicate-completeness STOP (PASS)

Across the FULL repo-wide universe, the only source types that are **external fresh/web AND reach this owner-reply gate seam** are `fresh_evidence` and `web_context` — both IN `_FRESH_SOURCE_TYPES`. `rss` reaches it folded into `web_context` (gated). No external-fresh/web type is missing. Everything else is intentionally excluded: recall (`memory_*`, `dialogue_anchor`, `owner_message_context`, `temporal_recall_status`), absence markers (`signal_absence`, `empty_result`), self/voice (`action_outcome`/`open_loop`/`builder_event`/`quality_signal` — cycle-path, and voice-not-fact if ever recalled), and `photo_vision` (doesn't reach the seam). **GO.**

## Seam proof (PASS)

Gate block at [maez_daemon.py:7277](../../daemon/maez_daemon.py#L7277) (`decide_support_path` → `observe_focused_support_gate`/`observe_focused_support`), under `if _grounding_shadow_post_audit_ready and _focused_used and _focused_support_evidence_map:`. `_focused_working_set` in scope there (init `None` :6604, set :6872). `EvidenceItem.source_type` is the field ([focused_cognition.py:255/381](../../core/routing/focused_cognition.py#L255)). `evidence_map_from_working_set` returns `{label:text}` only ([grounding_shadow.py:369](../../core/cognition/grounding_shadow.py#L369)) — provenance-stripped, so the predicate MUST read the working set. No circular import: the daemon already imports from `core.routing.focused_cognition`. `_run_support_scope` extraction is clean.

**GO** — inventory complete, photo_vision proven OUT, STOP passes, seam confirmed.
