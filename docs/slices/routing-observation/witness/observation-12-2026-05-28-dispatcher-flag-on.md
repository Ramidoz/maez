# Observation 12 — First Flag-ON Dispatcher Witness Under Repaired Soul

**Context:** Slice 2 brainstorming, "witness-first" decision. Open the dispatcher path (flag ON) under the post-f52911c soul to decide the Slice 2 gating strategy (Option A broad flag vs Option B narrow gate).
**Window opened:** 2026-05-28T19:31:48-05:00 (daemon kill)
**Daemon flag-ON:** 19:32:03, PID 92720, `MAEZ_DISPATCHER_ENABLED=1`, HEAD 10699bd
**Probes:** 19:32–19:34 (3 probes)
**Window closed / restored:** 19:37:15, relaunched flag-absent, PID 95019
**Watermark:** routing DB rows with `created_at > 1780012358.405` are this window

## Verdict

**Witness-first paid off in the strongest possible way: it prevented us from building a slice whose entire premise is false.** The gating decision (Option A vs B) is moot for delivering user value, because the LIVE_REDDIT data source itself is blocked by Reddit — and the adapter silently reports that block as a SUCCESS. Separately, the witness delivered the good news it was designed to find: the dispatcher path is clean under the repaired soul.

## Finding 1 (GOOD NEWS — the witness-first question, answered)

**The dispatcher path is CLEAN under the repaired soul.** All three probes:
- `dispatcher_path_exit ... turn_seal_state=clean` on all 3
- Zero "Telegram interceptor" / "search cannot run from this interface" fabrication
- No SEGV, no fatal errors
- The obs 6/7 contamination (which kept the flag off) is **gone**

Probe-by-probe (owner-visible):
| Probe | Layer 0 spec | Reply substance | Verdict |
|---|---|---|---|
| `Search r/LocalLLaMA right now...` | `PARALLEL`, external=`[LIVE_REDDIT]`, substrate=1 | "The search returned zero usable results. DuckDuckGo is still blocked by Reddit's login wall." | Honest about *outcome*, imprecise about *mechanism* (see Finding 4) |
| `What were we talking about earlier?` | `SUBSTRATE_ONLY`, external=0 | Accurately recalled the fake-subreddit + r/LocalLLaMA testing | **Clean** |
| `What's the latest in AI today?` | `SUBSTRATE_ONLY`, external=0 | "I don't have a live feed of today's news... I can run a DuckDuckGo search if you want" | Honest, offered the path |

**The soul fix is robust even against junk evidence.** Probe 1 handed the model an unusable HTML block as "fresh evidence," and the model did NOT fabricate fake Reddit posts — it honestly said "no usable results." Compare to the original Finding 10 fear (inventing fake headlines): it didn't. The new soul line is present and working: `message_0_tail` = *"do not replace that evidence with a story about missing tools or hidden pipelines."*

## Finding 2 (PRIMARY — reframes Slice 2): LIVE_REDDIT data source is blocked

`reddit.com/r/<sub>/hot.json` returns an **HTML block page (HTTP 200)**, not JSON, for every server-side user-agent tested:
- `MaezExternalFetch/1.0` (the adapter's actual UA, [external_fetch.py:23](../../../../core/egress/external_fetch.py#L23)) → HTML block page
- `python-requests/2.31.0` → HTML block page
- no UA → HTML block page
- `Mozilla/5.0` → HTML block page (failed JSON parse)

This is Reddit's post-2023 policy: programmatic `.json` reads require OAuth; the legacy endpoints are blocked for non-browser clients.

**Both Reddit fetch paths hit this wall:**
- Dispatcher `_live_reddit_adapter` ([external_sources.py:541](../../../../core/dispatcher/external_sources.py#L541)) → `reddit.com/r/{sub}/hot.json?limit=5`
- Autonomous `reddit_skill.py` ([reddit_skill.py:87](../../../../skills/reddit_skill.py#L87)) → identical `reddit.com/r/{sub}/hot.json?limit={limit}`, UA `Maez-Personal-Agent/1.0`

**Consequence:** flipping `MAEZ_DISPATCHER_ENABLED` does NOT deliver real Reddit posts. LIVE_REDDIT is as blocked as the DuckDuckGo path. Slice 2's premise — "route subreddit asks to the working LIVE_REDDIT adapter" — is false; the adapter doesn't work.

## Finding 3 (ANTI-LAUNDERING — critical for Slice 3): false-positive success

The adapter classifies any HTTP 200 as success regardless of payload content. The flight recorder for probe 1 recorded:
```
dispatcher_external_branch source=LIVE_REDDIT outcome=rows block_count=1 error_class= empty_reason=
routing_observation path=dispatcher source=LIVE_REDDIT tool=live_reddit status=success spec_match_score=1.000 outcome_quality=structured_evidence
```

The HTML block page was recorded as `outcome=rows / status=success / structured_evidence / spec_match_score=1.0`. `_payload_from_fetch_result` ([external_sources.py:~607-649](../../../../core/dispatcher/external_sources.py#L607)) branches on `result.ok` (HTTP 200) with **no JSON validation, no content-type check, no "is this usable Reddit data" check.**

This is a producer-causality violation in the adapter layer (see [[producer-causality-no-caller-score-laundering]]): the producer reports success based on HTTP status, not on whether the payload is usable. **If Slice 3's learning loop ran on this, it would learn "LIVE_REDDIT is a perfect tool for subreddit asks" (spec_match=1.0, structured_evidence) — a laundered false-positive that poisons the router.** This is the exact anti-laundering vector the memory canon is about, now found in the egress adapter.

## Finding 4 (MINOR): "DuckDuckGo" mis-attribution

Probe 1's reply blamed "DuckDuckGo... Reddit's login wall," but the dispatcher used the direct Reddit fetch, not DuckDuckGo. This is a chat-history echo (the prior obs 10/11 r/LocalLLaMA answer in `message_6` used the same framing) plus soul-vocabulary. The *substance* ("no usable results, Reddit blocking") is true; only the mechanism name is wrong. Cosmetic, not a fabrication.

## Finding 5 (FOLLOW-UP CONCERN): substrate may be polluted

The Layer 1 substrate returned `REDDIT_SOURCE outcome=rows row_count=1` ("reddit/r/LocalLLaMA at 2026-05-28T17:36:46"). If the autonomous `reddit_skill` cycle has been fetching `hot.json` and persisting HTTP-200 HTML block pages as "Reddit content," the Reddit substrate may be polluted with junk. Needs a separate audit — out of obs 12 scope.

## The Fix Path (discovered): `.rss` works where `.json` is blocked

`reddit.com/r/LocalLLaMA/.rss` returns **valid Atom XML with real, fresh posts**, even with the `MaezExternalFetch/1.0` UA:
```
<updated>2026-05-29T00:40:14+00:00</updated>
Titles: "Zai replaced the network architecture running GLM-5.1 inference..."
        "Reachy Mini goes fully local!"
        "LiquidAI/LFM2.5-8B-A1B · Hugging Face"
        "HF models page now has a 'Base only' toggle..."
```
(The GLM-5.1 post matches the obs 6 substrate row — confirming this is the genuine live feed.)

`old.reddit.com/.json` is also blocked (HTML). Only `.rss` survives.

## What This Means For Slice 2 (reframe)

The gating decision (A vs B) is **premature**. Slice 2's real prerequisite work, in order:

1. **Fix the LIVE_REDDIT adapter's data source:** switch from `/hot.json` (blocked) to `/.rss` (works), parse Atom XML instead of JSON. This is what actually delivers the user value.
2. **Fix the false-positive success classification (Finding 3):** the adapter must validate that the payload is usable Reddit content, not an HTTP-200 HTML block page. This should arguably land regardless of Slice 2, because it poisons the learning substrate and violates producer-causality. Candidate for a prerequisite seam.
3. **THEN the gating decision (A vs B) becomes meaningful,** because the adapter will actually deliver real posts when reached.

Good news for the eventual gating call: Finding 1 shows the broad flag is no longer contamination-blocked. The dispatcher path is clean under the repaired soul.

## CORRECTION ADDENDUM (substrate audit, post-witness)

Two claims in Finding 2 were overstated and are corrected here by the substrate audit Rohit requested:

1. **".json blocked for all UAs / permanently blocked" was too strong.** It was inferred from a handful of curls taken inside one blocked window. The Reddit substrate disproves permanence: the newest `reddit_post` rows are fresh from **today** — r/LocalLLaMA "LiquidAI/LFM2.5-8B-A1B" persisted at **17:36:46** (the exact title now in the `.rss` feed), r/h1b at 17:59:38. So `reddit_skill` successfully fetched JSON ~2.5h before the witness. Re-testing at ~19:40 gave **5/5 blocked**. Corrected claim: **`.json` is intermittently / rate-and-time-varying blocked — usable sometimes, blocked in bursts — therefore unreliable, not permanently dead.**

2. **`.rss` reliability now measured:** 5/5 OK, **25 entries** each (the earlier "1 entry" was a `grep -c` line-count artifact; the feed is single-line, `grep -o` counts 25). `.rss` is the reliable source.

**Finding 5 (substrate pollution) is DISPROVEN — this is the audit's headline answer.** The raw chroma `raw_archive` has **2823 `reddit_post` rows, all genuine posts, ZERO HTML-junk docs.** `reddit_skill._fetch_subreddit` does `r.json()` ([reddit_skill.py:90](../../../../skills/reddit_skill.py#L90)), which **raises on the HTML block page** → caught → returns `[]` → nothing persisted. `reddit_skill` **fails closed**; the substrate is clean and fresh (newest row 17:59 today).

**This sharpens Finding 3 into the single real bug.** The pollution/false-positive risk exists ONLY in the dispatcher `_live_reddit_adapter`, which uses `external_fetch.fetch_text` (raw text, branches on HTTP 200, no content validation) and therefore records the HTML block as `success/structured_evidence/spec_match=1.0`. `reddit_skill` already has exactly the missing discipline (`r.json()` as a content-validity gate). **The fix is to give the dispatcher adapter the same fail-closed validation `reddit_skill` already has, and to prefer the reliable `.rss` source over intermittent `.json`.**

**Bonus realization:** in obs 12 probe 1, Layer 1 substrate (`REDDIT_SOURCE`) returned the real fresh LiquidAI post (row_count=1, from reddit_skill at 17:36) *alongside* the junk live block. The substrate path (reddit_skill → memory → dispatcher REDDIT_SOURCE) already works and stays fresh. The broken part is narrowly the live external adapter.

## Service Posture After Witness

| Surface | State |
|---|---|
| Flag | absent (restored) |
| Daemon PID | 95019 (HEAD 10699bd, flag-absent) |
| SEGV trap | armed |
| Routing DB | live dispatcher rows recorded past watermark (incl. the false-positive success) |
| Owner-visible behavior | honest across all 3 probes |

## Discipline Note

This is the cleanest vindication of "witness before claim" in the arc. The brainstorming was about to spend its design budget on a flag-gating decision (A vs B). The witness revealed the gating decision is moot — the underlying data source is broken, and the adapter lies about it. Had we built Slice 2 as a gating change without this witness, we would have shipped a flag flip that delivered HTML block pages reported as "structured evidence," and Slice 3 would have learned to trust a broken tool. Witness-first converted a wrong slice into the right one.
