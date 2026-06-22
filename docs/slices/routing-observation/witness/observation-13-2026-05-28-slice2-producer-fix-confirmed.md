# Observation 13 — Slice 2 Producer Fix Confirmed (and Evidence-Precedence Disease Exposed)

**Context:** Slice 2 live witness, flag-ON, branch `slice2-live-reddit-validation` HEAD `e4e4d8f`.
**Window opened:** 2026-05-28T21:16:47-05:00 (daemon kill)
**Daemon flag-ON:** 21:17:00, PID 197532, `MAEZ_DISPATCHER_ENABLED=1`, branch HEAD `e4e4d8f`
**Probes:** 21:18 (`Search r/LocalLLaMA right now for recent local LLM posts.`), 21:18 follow-up (`Try that`)
**Window closed / restored:** 21:21:41, relaunched flag-absent, PID 199364
**Watermark:** routing DB rows with `created_at > 1780014826.957` are this window

## Verdict

**Slice 2 PASSES on its own scope. The producer-honesty fix is confirmed live.** A separate, larger finding (evidence precedence) was exposed and is explicitly deferred to the next slice.

## Slice 2 Success Criterion — MET

The decisive flip vs Obs 12, on the same r/LocalLLaMA probe hitting the same Reddit HTML block page:

| | Obs 12 (pre-fix) | Obs 13 (post-fix) |
|---|---|---|
| `dispatcher_external_branch` LIVE_REDDIT | `outcome=rows block_count=1` | `outcome=empty block_count=0 empty_reason=PARSED_BUT_NO_USABLE_FIELDS` |
| recorded as | `structured_evidence`, `spec_match=1.0` | (branch) honest empty |

The adapter no longer launders a block page into evidence. The false-positive success is gone. No learning system will now train on a block page as "success." This is exactly the producer-causality fix Slice 2 scoped.

Full obs 13 telemetry (probe 1, 21:18:13):
```
dispatcher_layer0_emit composition_hint=PARALLEL external_source_count=1 substrate_source_count=1
dispatcher_layer1_branch source=REDDIT_SOURCE outcome=rows row_count=1        # substrate had a real post
dispatcher_external_branch source=LIVE_REDDIT outcome=empty block_count=0 empty_reason=PARSED_BUT_NO_USABLE_FIELDS   # fix working
routing_observation path=dispatcher source=REDDIT_SOURCE tool=reddit_source status=success spec_match_score=1.000 outcome_quality=structured_evidence
```

The turn-level routing row reflects the *successful substrate branch* (REDDIT_SOURCE, 1 real post, `structured_evidence`), while the branch-level telemetry honestly records the LIVE_REDDIT block as empty. Both true; the orthogonality holds (routing fidelity `spec_match=1.0` preserved, content axis honest per-branch).

## The Larger Finding (NEXT slice, not this one)

**Maez held a real, fresh r/LocalLLaMA post in context (`REDDIT_SOURCE row_count=1`) and the owner-visible reply still said "zero usable results... DuckDuckGo is currently blocked by Reddit's login wall... the signal from r/LocalLLaMA is invisible to my web search tool."**

The substrate handed the voice a real post; the voice answered from a stale capability story (DuckDuckGo/blocked) instead of the evidence. This is **source-agnostic** — it is the disease, not a Reddit bug:

> Maez can have valid evidence available, but still answer from a stale capability story instead of that evidence.

The `Try that` follow-up turn reinforced it: it produced "I don't have a live tool loop on this channel... the interceptor will trigger the search automatically" — again narrating absent/blocked tooling rather than synthesizing from what was present.

This is the **Evidence Precedence** problem. It is explicitly **out of Slice 2's scope** (Slice 2 was the producer-honesty fix at the LIVE_REDDIT adapter) and is the subject of the next slice.

## Decomposition (operator framing, 2026-05-28)

The architecture's four substrate-side organs this arc is building (all brain-swappable):
1. **Producer honesty** — every source validates its payload before calling it evidence. (Slice 2 = first instance, LIVE_REDDIT. Generalize across all adapters later.)
2. **Evidence precedence** — when the substrate has relevant evidence in the turn, synthesis must privilege it over chat-history/soul/source-failure narratives. (NEXT slice — Reddit is the witness case, not the special case.)
3. **Outcome learning** — the router learns which source/method works from recorded outcomes (the flight recorder), not model vibes or hand-authored assumptions. (Slice 3.)
4. **Runtime self-model alignment** — soul/self-description stays aligned with the substrate so Maez does not faithfully recite obsolete architecture. (Ongoing; Finding 10 was the first instance.)

## Next-Slice Invariant (Evidence Precedence Guard)

> When Maez has relevant substrate evidence in the prompt, it must answer from that evidence or explicitly say why the evidence is insufficient. It must not claim the source is missing, blocked, unavailable, or not wired unless the evidence state actually says that.

## External Constraint Update (2026-05-28)

The official Reddit Data API application was **denied** ("not in compliance with Responsible Builder Policy and/or lacks necessary details"). Door status: `.json` blocked, DuckDuckGo→Reddit blocked, official API denied, public `.rss` feed working (25 entries, reliable), substrate (`reddit_skill` → memory) holds ~2823 real posts. The durable-API path is closed for now (soft denial; resubmission possible but slow/uncertain). This makes the public RSS feed the most legitimate working live path, and the substrate-recall path the most robust — both reinforce that **evidence precedence (#2)** is the highest-leverage next move.

## Service Posture After Witness

| Surface | State |
|---|---|
| Flag | absent (restored) |
| Daemon PID | 199364 (flag-absent) |
| SEGV trap | armed |
| Slice 2 branch | `slice2-live-reddit-validation` @ `e4e4d8f`, verified, ready to merge |

## Discipline Note

Slice 2 did exactly what it promised and nothing it didn't. The temptation here is to call it a failure because the owner reply was still bad — but that conflates two layers. Slice 2 = producer honesty (done, verified). The bad reply = evidence precedence (next slice). Keeping that boundary clean is what lets each fix be witnessed on its own terms instead of sprawling into an un-shippable mega-fix. Merge Slice 2; it is the prerequisite that ensures the learning system never trains on block-pages-as-success.
