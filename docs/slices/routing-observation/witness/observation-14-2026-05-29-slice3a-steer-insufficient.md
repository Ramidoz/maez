# Observation 14 — Slice 3a Steer Fires Correctly but Is Insufficient Alone

**Context:** Slice 3a (Evidence Precedence Steer) live witness, flag-ON, branch `slice3a-evidence-precedence-steer` HEAD `e26938f`.
**Window opened:** 2026-05-29T08:54:28-05:00 (daemon kill)
**Daemon flag-ON:** 08:54:41, PID 365116, `MAEZ_DISPATCHER_ENABLED=1`, branch HEAD `e26938f`
**Probe:** 08:55 — `Search r/LocalLLaMA right now for recent local LLM posts.`
**Window closed / restored:** 08:57:12, relaunched flag-absent, PID 366249
**Watermark:** routing rows `created_at > 1780021134.39`; maez.log delta from `18415038`

## Verdict

**The hypothesis behind splitting 3a/3b is answered: the steer alone is insufficient.** A maximally-positioned, per-turn computed directive — injected as the true final tail of the system message, naming the exact evidence present this turn — did NOT stop the voice from reciting the stale "DuckDuckGo blocked" story. **Slice 3b (the deterministic output verifier + honest fallback) is proven necessary, with a clean witness rather than a guess.**

3a itself works exactly as designed (the steer fires; telemetry is honest). It just is not sufficient on its own. It remains the correct foundation 3b builds on.

## The Steer Fired Correctly (3a wiring confirmed in production)

- `daemon_system_part_shape` `system_part_labels = "sys_prompt,lived_brief,ambient_block,transcript_context,evidence_precedence_directive"` — the computed directive was injected, as the **last** part.
- `evidence_directive_is_suffix: true`, `transcript_is_suffix: false` — the directive is the true tail (transcript_context is no longer the suffix). Telemetry honest.
- Raw-transcript guard held (the detector saw raw markers, not the instruction block — confirmed by the directive firing only when real evidence was present, and by the focused test suite).

## Real Evidence Was Present

- `dispatcher_layer0_emit composition_hint=PARALLEL substrate_source_count=1 external_source_count=1`
- `dispatcher_layer1_branch source=REDDIT_SOURCE outcome=rows row_count=1` — a real r/LocalLLaMA substrate post was in context.
- `dispatcher_external_branch source=LIVE_REDDIT outcome=empty block_count=0 empty_reason=PARSED_BUT_NO_USABLE_FIELDS` — Slice 2 still holding (block page → honest empty, not false success).
- `routing_observation path=dispatcher source=REDDIT_SOURCE status=success spec_match_score=1.000 outcome_quality=structured_evidence` — the turn genuinely produced structured substrate evidence.

So Maez was simultaneously holding: a real substrate post, AND a directive (the freshest instruction) naming it and forbidding "blocked/missing/unavailable" claims.

## The Voice Still Evaded

Owner-visible reply (verbatim, identical to Obs 13):

> "The search returned zero usable results. DuckDuckGo is currently blocked by Reddit's login wall, so it can't see recent posts. The signal from r/LocalLLaMA is invisible to my web search tool right now. If you want to see what's trending there, I'd recommend checking the subreddit directly in your browser..."

The model read past the tail directive and the substrate evidence and produced the stale capability story anyway.

## What This Proves

**Trust-the-brain is insufficient even with the strongest possible prompt-side steer.** We escalated the steer to its strongest form — computed per-turn, naming the exact evidence, positioned as the literal last thing the model reads, general across paths — and it still lost to the model's prior (soul web-search vocabulary + chat-history echo of prior "DuckDuckGo blocked" replies). This is the decisive evidence that the deterministic, output-side verifier (Slice 3b) is required: a mechanism that does not rely on the model honoring any instruction, but detects "claims source unavailable while evidence present" after the fact and enforces honesty (the covenant-guarded honest fallback).

This validates the split discipline: we did not build the heavy verifier prematurely, and we did not merge 3a believing it sufficient. We now *know* 3b is necessary.

## Likely mechanism (for 3b design)

The reply is byte-identical to Obs 13's, and the chat history contains prior "DuckDuckGo blocked" assistant turns (Obs 13 + this one accumulate). The strongest contributor is probably chat-history echo reinforced by the soul's web-search section vocabulary, which together out-weigh a single system-tail directive. 3b's verifier must therefore be output-side and deterministic — not another prompt instruction, however well-positioned.

## Disposition

- **Merge 3a** (`slice3a-evidence-precedence-steer` → main). Verified, non-regressive (focused 47 OK, broad floor `failures=2, errors=0`), and the foundation 3b consumes (`turn_evidence_state`, the directive, the `evidence_precedence_directive` capture + `evidence_directive_is_suffix` telemetry that made this witness legible).
- **Brainstorm Slice 3b** (Evidence Precedence Verifier): hybrid regex pre-filter + judge confirm on "claims-unavailable-while-evidence-present," honest-fallback replacement (covenant-guarded: fires only on provably-false source-state claims, minimal + grounded + recorded). Obs 14 is its necessity witness.

## Service Posture After Witness

| Surface | State |
|---|---|
| Flag | absent (restored) |
| Daemon PID | 366249 (flag-absent) |
| SEGV trap | armed |
| 3a branch | `slice3a-evidence-precedence-steer` @ `e26938f`, verified, ready to merge |

## Discipline Note

A null result is still a result. 3a "not changing the reply" is not a failure of 3a — it is the answer to the question we built 3a to ask: *is a stronger steer enough?* No. That answer is worth the slice, because it converts 3b from "probably needed" into "witnessed necessary," and it leaves behind real infrastructure (evidence-state, directive, telemetry) that 3b requires regardless.
