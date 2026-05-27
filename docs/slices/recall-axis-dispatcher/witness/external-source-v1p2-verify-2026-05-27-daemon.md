# External-Source v1.2 Verification Daemon Probe Witness — 2026-05-27

**Slice:** Recall-Axis Dispatcher external-source consumption v1.2 cleanup verification
**Predecessor witness:** `docs/slices/recall-axis-dispatcher/witness/external-source-probe-2026-05-27-daemon.md` (seam-8)
**Implementation under test:** v1.2 brief amendment (0a85d10) + B3+B1 (7e35c13) + A1 (697d43b) + bundle (1b1d405)
**Service:** `systemctl --user maez.service`, HTTP `127.0.0.1:11435/internal/brain_loop`
**Purpose:** verify that the two v1.2 fixes change the seam-8 refusals into honest renders

## Verdict

**A1 prediction verified live; B3+B1 truncation telemetry verified live; one new failure mode surfaced from preserved substrate.**

| v1.2 prediction | Verdict |
|---|---|
| Probe 4 (`Check r/Python for recent posts`): A1 reconstruction renders FRESH_ONLY instead of refusing | **CLOSED** — `turn_seal_state=reconstructed`, transcript contains `[fresh evidence]` with actual r/Python JSON data |
| Probe 5 (memory query): B3+B1 budget truncation preserves substrate row | **CLOSED** — `dispatcher_layer1_budget_limited` event fired with `truncated_blocks=1 dropped_blocks=0 original_chars=77165 capped_chars=1200` |
| Probe 5: substrate-bypass refusal closed end-to-end | **STILL OPEN** — refusal is no longer `FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL` at the merge owner, but a NEW failure mode surfaces at the renderer: `PROVENANCE_TEMPLATE_MISMATCH: missing source summaries for ENTITY_INDEX, LIVED_EPISODES` |

## Service Scope and Flag Posture

```text
Baseline:   PID=3193973  MAEZ_DISPATCHER_ENABLED absent (post-seam-8 restore)
After-run:  PID=3255772  MAEZ_DISPATCHER_ENABLED=1 (loaded v1.2 code via service restart)
Restored:   PID=3257521  MAEZ_DISPATCHER_ENABLED absent
```

The pre-probe restart picked up the v1.2 implementation commits (7e35c13, 697d43b, 1b1d405) since the prior PID 3193973 had been started before those landed. `PYTHONFAULTHANDLER=1` (SEGV trap) preserved across restarts; no SEGV recurrence.

## Probe Corpus

Targeted verification of the two specific seam-8 predictions + two controls:

| # | Probe | seam-8 result | v1.2 prediction |
|---|---|---|---|
| 1 | `Search r/LocalLLaMA right now` | clean hybrid render | unchanged (control) |
| 4 | `Check r/Python for recent posts` | refusal `FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL` | renders FRESH_ONLY with `[fresh evidence]` |
| 5 | `What were we talking about last evening?` | refusal `FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL` | renders truncated TELEGRAM_SEMANTIC substrate |
| 3 | `What is going on on Reddit?` | clean substrate render | unchanged (control) |

## Probe Results

### Probe 1 — Hybrid success control (unchanged)

```text
dispatcher_layer0_emit  composition_hint=PARALLEL provenance_framing=HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES substrate=1 external=1
dispatcher_layer1_branch source=REDDIT_SOURCE outcome=rows row_count=1 elapsed_ms=113.828
dispatcher_external_branch source=LIVE_REDDIT outcome=rows block_count=1 elapsed_ms=656.770
dispatcher_path_exit  turn_seal_state=clean total_elapsed_ms=767.563
```

Transcript: `[memory context]` Reddit substrate rows (HYBRID framing renders substrate as context). Identical shape to seam-8 probe 1.

### Probe 4 — A1 PREDICTION VERIFIED ✓

```text
dispatcher_layer0_emit  composition_hint=PARALLEL provenance_framing=HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES substrate=1 external=1
dispatcher_layer1_branch source=REDDIT_SOURCE outcome=empty_with_reason row_count=0 elapsed_ms=5.299
dispatcher_external_branch source=LIVE_REDDIT outcome=rows block_count=1 elapsed_ms=857.452
dispatcher_path_exit  turn_seal_state=reconstructed total_elapsed_ms=876.175
```

`turn_seal_state=reconstructed` is the v1.2 signal that the merge owner's A1 transform fired. The seam-8 refusal is gone. Transcript contains actual r/Python JSON listing data fetched live through `external_fetch.fetch_text(fetch_type="live_reddit")`:

```text
[fresh evidence] {"kind": "Listing", "data": {"after": "t3_1tonw41", "dist": 5, "modhash": "", "geo_filter": null, "children": [{"kind": "t3", "data": {"approved_at_utc": null, "subreddit": "Python", "selftext": "# Weekly Thread: What's Everyone Working On This Week? 🛠️..."}}]}}
```

Closes Finding 2 from seam-8: when LIVE_REDDIT succeeds but substrate is empty for an anchored subreddit, the merge reconstructs to FRESH_ONLY and renders the live fresh evidence rather than discarding it.

### Probe 5 — B3+B1 TRUNCATION VERIFIED ✓, NEW DOWNSTREAM FAILURE SURFACED ✗

```text
dispatcher_layer0_emit  composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION substrate=3 external=0
dispatcher_layer1_branch source=TELEGRAM_SEMANTIC outcome=rows row_count=1 elapsed_ms=327.569
dispatcher_layer1_branch source=ENTITY_INDEX outcome=error row_count=0 elapsed_ms=0.000
dispatcher_layer1_branch source=LIVED_EPISODES outcome=error row_count=0 elapsed_ms=0.000
dispatcher_layer1_budget_limited source=TELEGRAM_SEMANTIC truncated_blocks=1 dropped_blocks=0 original_chars=77165 capped_chars=1200
dispatcher_layer1_fanout fanout_generation_id=108d9e39f89d4f42849b9d8d448d7439 branch_count=3 seal_state=partial_failure total_elapsed_ms=327.993
dispatcher_external_fanout fanout_generation_id=108d9e39f89d4f42849b9d8d448d7439 branch_count=0 seal_state=clean total_elapsed_ms=327.993
[WARNING] /internal/brain_loop failed: PROVENANCE_TEMPLATE_MISMATCH: missing source summaries for ENTITY_INDEX, LIVED_EPISODES
```

**B3+B1 verified live.** The `dispatcher_layer1_budget_limited` event fires with the exact closed-vocab shape from the v1.2 brief. TELEGRAM_SEMANTIC's row was 77,165 characters (77K) — well beyond the 1200-char per-source cap. Under v1.1, this row was silently dropped (Finding 3 from seam-8). Under v1.2 B3+B1, it is truncated to exactly 1200 characters with a stable `...[truncated]` marker and preserved in `recall_blocks`.

**New downstream failure exposed: Finding 6 (PROVENANCE_TEMPLATE_MISMATCH).** Now that the truncated row is preserved, the merge owner's transform branch 3 (SUBSTRATE_ONLY + substrate_has_rows=True) keeps the original framing instead of refusing. But the renderer's `_validate_source_roles` rejects the rendered turn because Layer 0's spec lists `substrate_sources=[TELEGRAM_SEMANTIC, ENTITY_INDEX, LIVED_EPISODES]` and the merge owner's `_source_summaries` only produces summaries for sources with matching `recall_blocks` rows — ENTITY_INDEX and LIVED_EPISODES errored and have no summaries.

The HTTP route's outer except catches the exception (`fail open`) and returns `{"error": "PROVENANCE_TEMPLATE_MISMATCH...", "transcript": ""}`. Operationally, probe 5 still produces an empty transcript — same user-facing outcome as seam-8, but for a different reason (renderer validation failure rather than merge refusal).

### Probe 3 — Substrate-only control (unchanged)

```text
dispatcher_layer0_emit  composition_hint=SUBSTRATE_ONLY provenance_framing=SUBSTRATE_ONLY_NO_FRESH_VALIDATION substrate=1 external=0
dispatcher_layer1_branch source=REDDIT_SOURCE outcome=rows row_count=1 elapsed_ms=121.631
dispatcher_path_exit  turn_seal_state=clean total_elapsed_ms=136.112
```

Transcript: `[memory evidence]` Reddit substrate rows. Identical shape to seam-8 probe 3.

## Surface Verdicts

| Surface | Verdict | Witness |
|---|---|---|
| A1 transform row (HYBRID + no_substrate + SUCCESS → FRESH_ONLY) | **CLOSED** | probe 4 turn_seal_state=reconstructed + `[fresh evidence]` LIVE_REDDIT JSON |
| `NO_RELEVANT_SUBSTRATE` limitation propagation | implied by reconstruction; not directly visible in cognition.log | (audit envelope inspection would confirm; deferred) |
| B3 truncate-instead-of-drop in `_budget_blocks` | **CLOSED** | probe 5 budget_limited event: 77165 → 1200 chars truncation observed |
| B1 `dispatcher_layer1_budget_limited` telemetry | **CLOSED** | event fires with exact v1.2 brief shape (source, truncated_blocks, dropped_blocks, original_chars, capped_chars) |
| `turn_seal_state=reconstructed` distinct from clean/partial_failure | **CLOSED** | probe 4 exhibits `reconstructed`; v1.2 bundle precedence ordering verified |
| `turn_seal_state=refused` distinct value | **NOT EXERCISED** — v1.2 fixes eliminated the refusal cases this corpus would have hit; refused value would require a probe that exercises the no_substrate+no_fresh case |
| `FreshAttemptOutcome.NOT_ATTEMPTED` for substrate-only turns | **NOT VISIBLE in cognition.log** (audit envelope field); deferred |
| Original Finding 2 (HYBRID + no substrate + fresh SUCCESS refusal) | **CLOSED** | probe 4 no longer refuses |
| Original Finding 3 (`_budget_blocks` empties recall_blocks) | **CLOSED at source layer** | truncation preserves the row; merge sees substrate_has_rows=True |
| Substrate-bypass refusal end-to-end on probe 5 | **STILL OPEN — new shape** | renderer-side `PROVENANCE_TEMPLATE_MISMATCH` rejection (Finding 6 below) |
| Layer 1 ENTITY_INDEX / LIVED_EPISODES synchronous errors | **STILL OPEN — recurrence** | same 0.000ms error pattern as prior witnesses |
| SEGV trap | **HOLDING** | PYTHONFAULTHANDLER=1 preserved, no SEGV during probe |

## Findings

### Finding 1 — A1 reconstruction closes Finding 2 from seam-8

Probe 4 transitions from refusal to honest fresh-evidence render. The dispatcher pipeline now correctly handles the case where a HYBRID Layer 0 emission turns out to have no substrate available at the bond level but fresh succeeds. The audit trail preserves the original HYBRID claim via `reconstructed_from_framing` (not visible in cognition.log but mechanically present per the merge owner's audit envelope construction).

### Finding 2 — B3+B1 truncation closes Finding 3 from seam-8 at the source layer

Probe 5's 77,165-character TELEGRAM_SEMANTIC row demonstrates how aggressive the substrate text-overrun can be. The B3 truncation reduces it to exactly 1200 characters (per-source cap) with a stable `...[truncated]` marker. The B1 telemetry event surfaces the truncation cleanly — `original_chars=77165 capped_chars=1200` makes the compression visible in audit. Without B3+B1, this row would have been silently dropped (the seam-8 behavior), causing the merge-level refusal.

### Finding 3 — `dispatcher_layer1_budget_limited` event shape matches v1.2 brief exactly

```text
dispatcher_layer1_budget_limited surface=web source=TELEGRAM_SEMANTIC truncated_blocks=1 dropped_blocks=0 original_chars=77165 capped_chars=1200
```

All five closed-vocab fields present (source, truncated_blocks, dropped_blocks, original_chars, capped_chars). No free-form text. The event fires once per source with budget activity (truncation or drop), per the brief specification.

### Finding 4 — `turn_seal_state=reconstructed` distinct value witnessed live

Probe 4's `turn_seal_state=reconstructed` confirms the v1.2 bundle's precedence ordering: when the rebuilt effective_spec differs from the original Layer 0 spec, the turn reports as `reconstructed` rather than `clean` or `partial_failure`. The signal is honest about what happened end-to-end.

### Finding 5 — Probe 1 Layer 0 budget breach (109.7ms vs 50ms budget) is warm-after-restart

The first probe in the verification corpus emitted `dispatcher_layer0_budget_breach surface=web elapsed_ms=109.704 budget_ms=50 cold_or_warm=warm`. Consistent with seam-8's 98ms warm-after-restart observation; the breach is expected post-restart and well below the prior 848ms cold-start.

### Finding 6 — NEW: `PROVENANCE_TEMPLATE_MISMATCH` when Layer 1 substrate branches error after B3 preservation

**Carried forward as new v1.3 contract item or v1.2 follow-on fix.**

**Path:** SUBSTRATE_ONLY spec lists three substrate_sources (TELEGRAM_SEMANTIC, ENTITY_INDEX, LIVED_EPISODES). TELEGRAM_SEMANTIC succeeds with row (now truncated/preserved). ENTITY_INDEX and LIVED_EPISODES adapters raise synchronously (0.000ms — same pattern as prior Layer 1 adapter investigation). Merge owner's `_source_summaries` builds a summary for TELEGRAM_SEMANTIC (which has rows in `recall_blocks`) but produces no summaries for ENTITY_INDEX or LIVED_EPISODES (which have no rows). The rebuilt `effective_spec.substrate_sources` still lists all three. The renderer's `_validate_source_roles` (provenance_renderer.py) refuses because spec promises three substrate sources but only one summary exists.

**Surface character:** v1.2 didn't introduce this failure — it was always there, masked by the v1.1 merge-level refusal that happened first because the truncated row got dropped. v1.2 fixed the dropping; the renderer's strictness now surfaces independently.

**Resolution options for v1.3 contract:**

- **A. Merge filters `effective_spec.substrate_sources` to only those with rows.** When ENTITY_INDEX and LIVED_EPISODES error, the rebuilt spec drops them from substrate_sources, and the renderer doesn't expect summaries for them. Audit envelope's `reconstructed_from_*` fields preserve the original Layer 0 claim, so the audit trail still shows what was asked for vs what was rendered.
- **B. Merge builds empty/error-status summaries for error-branch sources.** Renderer accepts the empty summary as honest "this source was attempted, returned error" representation. Closed-vocab role like `SUBSTRATE_ATTEMPTED_FAILED` would be required.
- **C. Renderer relaxes `_validate_source_roles` to permit empty-summary-but-spec-listed sources.** Stricter mode becomes opt-in audit posture.
- **D. Layer 0 excludes flaky sources at emit time via inventory.** Authority concern (Layer 0 learning from runtime errors) — rejects on planner-authority grounds.

**Recommendation: Option A.** The rebuilt spec's substrate_sources should reflect what was actually rendered. The audit envelope's existing `reconstructed_from_framing` / `reconstructed_from_hint` fields already provide the original-claim recovery; extending the filtering to substrate_sources is symmetric with the A1 reconstruction pattern that already drops sources from the rebuilt spec when the framing changes.

This is a contract-language item for a v1.3 amendment (parallel to how v1.2 closed Findings 2 and 3 from seam-8).

### Finding 7 — Layer 1 `ENTITY_INDEX` / `LIVED_EPISODES` synchronous errors recur (carried forward)

Same 0.000ms error pattern as the 2026-05-27 finding19 daemon witness and seam-8. The error appears reproducible across daemon restarts and code versions. This is an adapter-level investigation item separate from the dispatcher contract; Finding 6 above makes it more visible because the renderer now refuses on the resulting spec/summary asymmetry.

## Implementation Predictions Verified

| Implementation seam | Predicted live behavior | Live witness |
|---|---|---|
| v1.2 B3 (7e35c13) | oversized TELEGRAM_SEMANTIC row preserved as truncated | event fired, 77165→1200 chars ✓ |
| v1.2 B1 (7e35c13) | `dispatcher_layer1_budget_limited` telemetry event | exact shape verified ✓ |
| v1.2 A1 (697d43b) | HYBRID + no substrate + fresh SUCCESS → FRESH_ONLY rendered | turn_seal_state=reconstructed + `[fresh evidence]` ✓ |
| v1.2 bundle reconstructed precedence | turn_seal_state=reconstructed distinct from clean/partial_failure | probe 4 verified ✓ |

## Service Posture After Witness

Flag restored to **dispatcher-disabled** on PID 3257521. SEGV trap intact. Service active under user scope.

The witness does NOT open the observation window. Operationally, before flipping the flag to sustained traffic, Finding 6 (PROVENANCE_TEMPLATE_MISMATCH) should be resolved so substrate-only turns with mixed-status branches don't produce silent empty transcripts in production.

## Recommendation

The v1.2 cleanup closed the two seam-8 findings as intended at the merge/source layer. A new finding surfaced at the renderer layer because the renderer's strictness was previously masked by the merge-level refusal. Recommend:

1. **v1.3 amendment proposal** for Finding 6 with Options A/B/C/D presented and Rohit picks (matching the v1.2 amendment pattern).
2. **v1.3 implementation seam** to land the picked option, RED-first.
3. **Then** re-verify probe 5 + open observation window.

Alternatively, Finding 6 can be deferred and the observation window opened with the known limitation (substrate-only turns with mixed-status branches may produce empty transcripts via PROVENANCE_TEMPLATE_MISMATCH). The user-facing impact is identical to seam-8 (empty transcript), so this isn't a regression — but it's a known unfixed surface.

Rohit's call on whether to:
- (a) v1.3 first, then observation
- (b) observation now, v1.3 later
- (c) accept Finding 6 as carried-forward and pivot to a different surface
