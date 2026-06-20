# Learned Tool-Routing Slice 1 — Task 0 Proof Gate

**Date:** 2026-06-20. **Verdict: GO.** Branch `learned-routing-slice1`. Verified by the controller (owner calibration: Task 0 = light proof-gate).

## HARD GATE 1 — the write-back seam (PASS)

- Observation id captured at insert: `_legacy_routing_observation_id = record_legacy_web_search_observation(...)` at [maez_daemon.py:5902](../../daemon/maez_daemon.py#L5902); initialized `None` at :5865.
- It is in scope at the support-gate seam: `observe_focused_support_gate(reply, ...)` at [maez_daemon.py:7137](../../daemon/maez_daemon.py#L7137) (same `handle_message`, fn starts :5499). The gate runs only on `_support_path == "sync_gate"` (`MAEZ_SUPPORT_GATE_ENABLED`) — when it doesn't run, there's no receipt and only the thin signal applies (Task 2 guards with `_gate_receipt or {}`).
- NO update path exists today: store has only INSERT (`_record`, [observation/__init__.py:350](../../core/routing/observation/__init__.py#L350)). → Task 1 adds `attach_post_turn_quality`; Task 2 changes `observe_focused_support_gate` to return `(reply, gate_receipt)`.

## HARD GATE 2 — a bad-for-the-wound signal exists & is reachable (PASS)

- **Caveat count key:** `gate_receipt["caveated_unsupported"]` — built at [grounding_shadow.py:345](../../core/cognition/grounding_shadow.py#L345), attached to `GateOutcome.gate_receipt` at :364. (Siblings `caveated_unmatched`, `caveated_unverified` exist; we use `caveated_unsupported` for the wound.)
- **Thin signal:** `_compute_quality(result) -> (quality, result_count, snippet_chars)` ([web_search.py:51](../../skills/web_search.py#L51)); `quality=="thin"` when `result_count < _THIN_RESULT_COUNT(=3)` OR `snippet_chars < _THIN_SNIPPET_CHARS(=450)`. **NOT `evidence_block_count`** (which is always 0/1 → would brand every search unusable). Guarded on `result_count > 0` so a true-empty search keeps `empty_but_honest`.
- **Calibrated mapping (Task 2 verbatim):** `unusable` when `caveated_unsupported ≥ 1` OR (`quality == "thin"` AND `result_count > 0`); else leave the insert-time `outcome_quality`.

**Empirical confirmation of the wound** (main DB, 211 rows): `structured_evidence` **195**, `empty_but_honest` 10, `closed_refusal` 5, `tool_error` 1. No `unusable` exists — the teacher is mute today exactly as Codex flagged. Calibration introduces `unusable`.

## HARD GATE 3 — the request-class fork (PASS — decision: hash-only for Slice 1)

- No learnt class is persisted today (only `utterance_hash` + coarse `utterance_shape`). Layer0's class is computed at decision time but never written.
- **Layer0 cost:** `emit_spec` embeds the utterance via MiniLM (`from memory.embedder import get_encoder`; `encoder.encode_many(...)` [layer0.py:186](../../core/dispatcher/layer0.py#L186)) — a model inference per call, on the live reply path, coupling Slice 1 to the dormant triad's encoder.
- **Decision: `_LAYER0_ENABLED = False` for Slice 1** → exact-`utterance_hash` priors. Rationale: (1) avoids a MiniLM encode on every web-search turn; (2) the owner repeats "summarize today's signals" *verbatim* — exact-repeat is the correct grain for "it keeps saying the same thing"; (3) semantic-class generalization (Layer0) is a clean, separately-witnessed later organ. The classifier module ships both branches (both tested); only the flag stays off.

## Data volume / cold-start (PASS — forward-only as designed)

Worktree DB cold (empty); main DB has 211 pre-calibration rows that LACK `request_class_id` and have mute `outcome_quality`, so they are correctly excluded from priors (forward-only). The witness accrues over post-flag lived turns on the main checkout — expected and honest.

## Scope (PASS)

Change set: `core/routing/observation/__init__.py`, `core/routing/observation_class.py` (new), `core/routing/observation/priors.py` (new), `core/cognition/grounding_shadow.py` (tuple return), `daemon/maez_daemon.py` (3 seams), tests, docs. Untouched: the strict honesty gate logic, daemon S7 path, Telegram, time-sense, cockpit-reauth work. Four flags default-off = byte-identical.

**GO** — all three hard gates pass; the two forks are resolved (write-back via update-method + tuple return; class via exact-hash for Slice 1).
