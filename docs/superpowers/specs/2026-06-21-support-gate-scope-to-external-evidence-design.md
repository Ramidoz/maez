# Support Gate — Scope to External Evidence (don't put a courtroom around Maez's voice) — Design

**Date:** 2026-06-21. **Status:** design — owner-approved (the scoped rule + "both gate & shadow" + always-emit-the-receipt); this doc is for owner review before planning.
**Origin:** a live voice wound. On casual Telegram turns ("good morning," "how are you feeling?") Maez's reply had **"I couldn't confirm this from the source I cited."** appended to nearly every sentence — including pure self-expression and greetings. Temporarily muted live via `MAEZ_SUPPORT_GATE_ENABLED=0` (stop-the-bleeding); this slice is the proper fix so the gate can be safely re-enabled.

## Root cause (confirmed with live evidence)

The caveat fires in exactly ONE case ([grounding_shadow.py:264](../../core/cognition/grounding_shadow.py#L264)): a sentence that **has a citation** AND MiniCheck judged **UNSUPPORTED** (`mode == "cited_support" and verdict == UNSUPPORTED`). So those conversational sentences were *cited then stripped*:
1. `MAEZ_RECALL_TRIAD_ENABLED=1` is live → **every** turn (incl. greetings) runs focused cognition, which builds a **recall/memory evidence map** and has Maez attach `[E#]` citations.
2. Maez cites recalled context even for self-expression ("the rig is humming," "how has your week been?").
3. The support gate (`MAEZ_SUPPORT_GATE_ENABLED=1`) sends each cited sentence to MiniCheck. Maez's feelings/greetings **aren't "supported" by recalled memory** → UNSUPPORTED.
4. The gate appends the caveat to each; `render_natural` strips the `[E#]` markers but keeps the caveat.

Live proof: `~/.local/state/maez/grounding_shadow.jsonl` shows recent **telegram** gate turns at `unsupported_count` **4, 2, 3** — matching the screenshot. Structural, not random. **Not caused by the routing slices** (they don't touch the gate); it is the live **composition** of recall-triad (every turn cited) + support-gate (caveats unsupported citations), surfacing on conversational turns.

## The category error (covenant)

The support gate was built to keep Maez honest about **external factual claims** grounded in *web/fetched* sources ("the web says X" → caveat if the source doesn't support it). Pointed at Maez's **conversational voice** grounded in its own recall, it becomes a truth court demanding Maez *prove its own warmth* — the "verifier pressure on the voice" the covenant forbids ([[feedback_two_sided_verifier_pressure]]): a verifier on the voice must let Maez hold its ground, never muzzle every warm sentence. Worse, the shadow logs the same misjudgement silently ("greeting unsupported by recalled evidence") — useless, misleading data.

## The scoped rule (owner, 2026-06-21)

> If the turn pulled **external evidence**, the gate/shadow may run over cited factual claims.
> If the turn is **recall-only / self-expression / conversational**, gate AND shadow **skip MiniCheck** entirely.
> **Always emit a scope receipt** — so the rail's decision is visible; we want the right kind of sight, not blindness.

## The mechanism (already exists)

The focused working set tags every evidence item's provenance. [focused_cognition.py:88](../../core/routing/focused_cognition.py#L88): `_FRESH_SOURCE_TYPES = ("fresh_evidence", "web_context")` are the **external** kinds (`web_context` is literally labelled *"external web — UNTRUSTED"*); everything else (context, recent-dialogue, lived-self) is internal/recall. So *"did this turn pull external evidence?"* is a present signal, not an invention.

**`_turn_has_external_evidence(working_set | evidence_map) -> bool`** = any item is of a `_FRESH_SOURCE_TYPES` kind. (Task 0 enumerates the FULL external set — confirm `fresh_evidence`/`web_context` cover web_search + fetch_url + any frontier/fetched source; add any missing external type so nothing real is excluded.)

## The design

A single scope guard at the gate/shadow invocation seam:
- The daemon currently runs the gate when `_grounding_shadow_post_audit_ready and _focused_used and _focused_support_evidence_map`. Add `and _turn_has_external_evidence(...)`. The shadow path (`decide_support_path` → `observe_focused_support` / `observe_focused_support_gate`) is gated the same way — **MiniCheck is not invoked at all** on a recall-only turn.
- **Recall-only turn:** skip MiniCheck (gate + shadow); the reply is byte-identical to no-gate (no caveat, no `[E#]`-derived edit); emit the scope receipt `support_gate_scope external_evidence=false path=skipped_recall_only`.
- **External-evidence turn:** the gate/shadow run exactly as today (per-sentence MiniCheck on cited claims; real web-claim caveats preserved); emit `support_gate_scope external_evidence=true path=gated`.
- The gate's per-sentence caveat logic (`apply_support_gate`, `_caveat_for`) is **UNCHANGED** — we change *whether the courtroom convenes*, not how it judges once convened.

## Invariants (verify in review)

1. **Recall-only/conversational turn → NO MiniCheck (gate AND shadow), reply byte-identical to gate-off, no caveat.** (The casual-greeting case is whole.)
2. **External-evidence turn → gate/shadow run as today** — real web-claim caveats preserved (no regression on the "news about Anthropic" / Barchart case where a caveat is honest).
3. **Scope receipt ALWAYS emitted** (`external_evidence` + `path` ∈ {gated, skipped_recall_only}) — content-light, visible-state not chain-of-thought ([[feedback_visible_substrate_state_not_chain_of_thought]]).
4. **`_turn_has_external_evidence` is provenance-true** — derived from the working-set item types, not a keyword/heuristic on the reply text; Task 0 confirms it covers every external source.
5. **Untouched:** `apply_support_gate`/`_caveat_for` per-sentence logic; the routing/veto-ledger/Beta work; daemon S7; Telegram transport; time-sense. Only the *invocation scope* changes.

## Testing (hermetic — fake the working set)

- predicate: working set with a `web_context` item → True; recall-only working set (context/recent-dialogue/lived-self only) → False; empty → False.
- scope decision: external present → path=gated (gate runs); recall-only → path=skipped_recall_only (MiniCheck NOT called — assert via a mock that the verifier is never invoked); the scope receipt emitted in both.
- no-regression: an external-evidence turn still produces the same per-sentence caveats as before (the gate logic unchanged once convened).

## Scope / out

**IN:** the `_turn_has_external_evidence` predicate; the scope guard on the gate AND shadow invocation; the scope receipt; tests. **OUT (later/never):** changing `apply_support_gate`/`_caveat_for` per-sentence logic; per-sentence "is THIS citation external" refinement on a mixed turn (v0 is turn-level per the owner's rule); re-tuning MiniCheck; the recall-triad citation behavior (Maez may still cite recall internally — we just don't put a courtroom around it). The mute (`MAEZ_SUPPORT_GATE_ENABLED=0`) is reverted by the owner re-enabling the gate AFTER this lands.

## Lane / owner-breath

This closes a live trapdoor on the voice — covenant-sensitive, so full spec → plan → TDD → Claude two-stage + Codex cross-lane, STOP at the review gate. `## Predicted effect` on the behavior commit. After both-lanes PASS + merge: owner re-enables `MAEZ_SUPPORT_GATE_ENABLED=1` (undo the mute) + restart `maez`. Witness: a casual "good morning" → **no caveats**, scope receipt `skipped_recall_only`; a "latest news about X" web turn → caveats on the real cited claims, scope receipt `gated`. No autonomous check.
