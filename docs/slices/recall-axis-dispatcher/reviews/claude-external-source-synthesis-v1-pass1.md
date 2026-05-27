# Claude External-Source Pass 1 Synthesis — v1.1 Amendment Proposal

**Status:** synthesis of six-reviewer Claude pass 1 on `docs/slices/recall-axis-dispatcher/external-source-consumption-brief.md` (committed at `fe2dc7a`).
**Date:** 2026-05-27
**Reviewers folded:** Buber (covenant), Locke (egress authority), Kant (spec-consumer), Descartes (provenance/anti-laundering), Hume (failure taxonomy/closed vocabulary), Ohm (seal/concurrency/wiring).
**Verdict counts:** BLOCKING — Locke, Descartes, Hume, Ohm. SUGGEST — Buber (with one BLOCKING finding folded), Kant.

## Overall Verdict

**BLOCKING with a small, named patch path.** Four reviewers reach blocking verdicts; one (Buber) raises a BLOCKING-grade finding under a SUGGEST overall; one (Kant) is SUGGEST throughout. None of the blocking findings invalidate Option A (sibling fan-out at `core/dispatcher/external_sources.py`) — all six reviewers credit Option A as the right architectural choice and the rejection of Option B/C as correctly grounded.

The patches required are contract-edit-sized: close three currently-open string fields, name a merge-step owner for hybrid spec reconstruction, resolve two unverified egress claims, engineer lateness defense, and name a subject-boundary discipline. All of these can land as a v1.1 brief amendment before the engineering pass begins.

## Convergent Themes

### Theme A — Open-vocabulary strings reach audit/prompt rendering

**Concurring reviewers:** Descartes (F1, F2 — both BLOCKING), Hume (F1 — BLOCKING), Buber (F2 — SUGGEST), Locke (F5 — SUGGEST).

**Pattern:** §6 of the brief declares "No free-form failure reason should reach prompt rendering or audit metadata." But §4 ships four open string fields on `FreshBlock` and `ExternalBranchResult`: `rationale: str` (success-side), `error_class: str | None`, `empty_reason: str | None`, `deadline_kind: str | None`. Hume verifies the laundering surface is already live: `brain_loop.py:310` concatenates these strings into `SourceSummary.text` which renders. Mirroring Layer 1's existing slop at a second site — and the first site where exception text comes from raw network/HTTP/TLS exceptions — extends the vector.

**Convergent fix (v1.1 §4 + §6):**

1. Drop `FreshBlock.rationale` outright. The block already carries source, retrieval_timestamp, freshness, and an egress witness id (see Theme F). Rationale is post-hoc framing and belongs (if anywhere) in dispatcher telemetry, not the prompt or audit envelope.
2. Close the three failure-side string fields with new StrEnums:
   - `ExternalErrorClass` covering `ADAPTER_MISSING`, `TIMEOUT`, `NETWORK_ERROR`, `HTTP_NON_2XX`, `RATE_LIMITED`, `AUTH_DENIED`, `TLS_FAILURE`, `DNS_FAILURE`, `PARSE_FAILURE`, `PREFLIGHT_REFUSED`, `UNCLASSIFIED`. `UNCLASSIFIED` is the conservative bucket whose non-zero count is itself the laundering signal.
   - `ExternalEmptyReason` covering `NO_RESULTS`, `SOURCE_ABSENT`, `RESERVED_SOURCE_UNAVAILABLE`, `DEADLINE_REACHED`, `PARSED_BUT_NO_USABLE_FIELDS`.
   - `DeadlineKind` covering `GLOBAL`, `BRANCH`.
3. Replace §6 lines 226-228 with: "Adapter exception handlers MUST log only the exception class name plus the closed taxonomy reason code (`ExternalErrorClass`, `ExternalEmptyReason`). Raw exception text MUST NOT reach any persisted logger, prompt rendering, or audit metadata. Where exception detail is needed for live debugging, route it through the existing `external_fetch_diagnostics.jsonl` discipline." This converts the verbal restraint into a structural one and is mechanically grep-checkable.
4. Add a RED test that `provenance_renderer.render_provenance(...).source_summaries[*].text` never contains a string outside the closed `ExternalErrorClass` / `ExternalEmptyReason` / `AvailabilityLimitation` vocabulary.

### Theme B — Hybrid-failure CompositionSpec reconstruction has no named owner

**Concurring reviewers:** Descartes (F3 — BLOCKING), Kant (F2 — SUGGEST close to BLOCKING), Ohm (F1 — BLOCKING; the §8 merge step has no contract behind it).

**Pattern:** §7 says hybrid turns must "reconstruct a valid `CompositionSpec`" with updated `availability_limitations`, `source_availability`, and `provenance_framing=FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT`. The brief does not name *who* reconstructs. The natural-but-wrong implementations are: (a) external fan-out mutates the spec it consumed (planner-authority leak); (b) brain_loop._run_dispatcher_pipeline mutates the spec based on a downstream verdict (caller-score-laundering — exactly the vector `DispatcherRefusalReason.CALLER_SUPPLIED_COMPOSITION_VERDICT` was built to refuse). Three things missing: producer not named, witness not named (which fan-out fields are legal inputs), reconstruction-as-reconstruction marker (audit envelope must distinguish reconstructed spec from Layer-0-emitted spec).

**Convergent fix (v1.1 §7 + §8):**

1. Name the merge-step owner explicitly. Add to §8 wiring shape: "After Layer 1 substrate fan-out and external fan-out both complete (or are sealed at deadline), a named `merge_fanout_results(spec, layer1_result, external_result)` step composes a `RenderedTurn` payload. The merge step is the sole owner of building a *new* `CompositionSpec` from the original spec + fan-out results. Neither fan-out edits the spec it consumed."
2. Define the legal reconstruction transform as a closed table in §7: `(prior_framing, prior_hint, fanout_status, substrate_has_rows) -> new_framing | new_hint | DispatcherRefusal`. If no row matches, the merge step emits a new `DispatcherRefusalReason.FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL`.
3. Add an audit envelope field `reconstructed_from_framing: ProvenanceFraming | None` (and `reconstructed_from_hint: CompositionHint | None`) so reconstruction is explicit and the original Layer 0 framing remains recoverable from audit. Reconstruction is reconstruction, never disguised as continuity (canon-governs-canon witness-before-claim).
4. The fresh-only-with-total-failure case (probe 6 shape): substrate_sources=0 + fanout_status=ALL_FAILED cannot reconstruct to a substrate-context framing (there is no substrate). The merge step must produce the deterministic no-usable-fresh fallback (Theme G), not silently rewrite framing.
5. RED test: `test_hybrid_reconstruction_records_prior_framing_in_audit_envelope`; `test_fresh_only_total_failure_cannot_be_rewritten_to_substrate_framing`.

### Theme C — Egress claims that don't survive code witness

**Concurring reviewer:** Locke (F1, F2 — both BLOCKING with verified code citations).

**Pattern:** Two egress claims in the brief are not backed by what's in the repo:

1. **LIVE_REDDIT route ambiguous.** `external_fetch.build_fetch_registry()` only registers `web_search`, `search_rss`, `fetch_url`, `currency_lookup`, `stock_lookup` (`core/egress/external_fetch.py:128-155`). A Reddit JSON URL routed through `fetch_type="fetch_url"` is classified `UNKNOWN_URL_FETCH` and returns `decision="would_block"`. Worse, `skills/reddit_skill.py:87-88` already uses raw `requests.get()` to Reddit JSON — a pre-existing smuggling path. Without a hard prohibition, the next implementor will reach for `reddit_skill` because it "already works."
2. **Paperclip CLI is asserted but unverifiable.** `which paperclip` returns nothing; only `.agents/skills/paperclip/SKILL.md` exists (a Markdown skill spec, not an executable). `grep -rn "paperclip"` over `core/` and `skills/` returns zero hits. Routing dispatcher external-source consumption through an unaudited sibling-agent binary would undo the entire point of the central egress boundary.

**Convergent fix (v1.1 §2 + §5 + §10):**

1. **LIVE_REDDIT — decide explicitly.** Either: (a) register a new `fetch_type="live_reddit"` in `build_fetch_registry()` with `threat_model_class=PUBLIC_LOOKUP` and `result_origin_class=tool_result_public`, with the brief stating the route is `external_fetch.fetch_text(fetch_type="live_reddit")` and only that; or (b) reuse `fetch_url` and document in §5 that the decision is `would_block` (substrate_shadow) with a TODO to promote. Option (a) is preferred. Either way, silence is unacceptable.
2. **Forbid reddit_skill bypass.** Add to §10 non-goals: "`core/dispatcher/external_sources.py` MUST NOT import or call `skills.reddit_skill.RedditSkill`, `urllib.request`, `requests`, `httpx`, or any other surface that does not route through `core.egress.external_fetch.fetch_text`." Add a unit test that the LIVE_REDDIT adapter has no such imports and calls `fetch_text` exactly once per branch.
3. **Paperclip — reduce v1 scope or defer.** Recommended: reduce `ARXIV_OR_PAPERCLIP` v1 to arXiv-via-`fetch_text(fetch_type="arxiv")` (new registry entry) against the arXiv API URL; mark paperclip as `RESERVED_UNAVAILABLE` alongside `FRONTIER_CONSULT` with rationale that paperclip's egress is unaudited. This keeps v1 honest about what egress paths actually exist.
4. **No query-string credentials.** Add to §10: "URLs composed by adapters MUST NOT contain credential-bearing query parameters (`api_token`, `api_key`, `access_token`, `bearer`, `session`, etc.). Header-level credentials are already mechanically stripped by `external_fetch._request_headers`; query-string credentials must be refused by adapter pre-checks."

### Theme D — Seal discipline asserted, not engineered

**Concurring reviewer:** Ohm (F1, F2, F4, F6 — all BLOCKING).

**Pattern:** §4 lists generation_id and sealed_at as fields and §4 line 160 promises "late results unable to mutate rendered output." Layer 1 enforces this through three engineered mechanisms (single read site, `cancel_futures=True`, `late_result_ignored=True`). External fan-out goes through blocking HTTP that cannot be cancelled mid-socket-read — `Future.cancel()` is a no-op on a thread already inside a blocking egress call. So a 5s Reddit timeout that fires at 4.999s can still return a result at 5.001s, and without an explicit lateness defense at the merge step, the seal is breached. Four sub-issues bundled:

1. Two `fanout_generation_id`s (Layer 1's and external's) with no merge contract.
2. `sealed_at` asserted but no engineered defense for blocking-IO late arrivals.
3. Timeout budgets diverge from Layer 1 (5s/3s/6s vs Layer 1's 0.8s/1.0s) without justification or explicit statement that hybrid turns are bounded by `max(layer1_global=1.0s, external_global=6.0s) = 6s`.
4. Recovery-seed bypass not addressed. `brain_loop.py:1261-1278` bypasses the dispatcher pipeline (including Layer 1) when `recovery_seed is not None`. External fan-out must be bypassed identically.

**Convergent fix (v1.1 §4 + §5 + §8 + §9 + §10):**

1. **Single shared generation_id.** The caller in `_run_dispatcher_pipeline` mints one `fanout_generation_id` per turn and passes it into both `Layer1Fanout.run(...)` and `ExternalFanout.run(...)`. This requires a small Layer 1 touch (an injection point for the id) — name it as a Layer 1 patch attached to this slice. One id, one seal, one mechanically checkable late-result property.
2. **Engineered lateness defense at the merge step.** Add to §4 or §8: "The merge step reads each `ExternalBranchResult` only if its completion timestamp is ≤ the turn's `sealed_at` (monotonic). Branches arriving after `sealed_at` are dropped, mapped to `SOURCE_TIMEOUT` with `late_result_ignored=True`, and never reach prompt rendering or audit envelope. The renderer reads from the `ExternalFanoutResult` produced before `sealed_at`, never from a callback fired by the egress layer after."
3. **State concurrency-among-external-branches explicitly.** Add to §5 or §8: "External branches run concurrently with each other (ThreadPoolExecutor, matching Layer 1's pattern). The 6s global deadline is the turn-level latency floor for FRESH_ONLY turns and the longer leg of `max(layer1_global, external_global)` for hybrid turns. This is intentional, not accidental."
4. **Specify clock domain.** `sealed_at: float` is monotonic (matches Layer 1's `time.monotonic` via injectable clock). Add the annotation.
5. **Recovery-seed bypass.** Add to §10 non-goals: "Under `recovery_seed`, external fan-out is bypassed identically to Layer 1; the recovery path remains JARVIS-only as of this slice." Add RED test: recovery-seed turns do not invoke `ExternalFanout.run`.
6. **Cross-organ late-arrival test.** Expand RED test #6 or add #8: `test_late_external_result_cannot_mutate_substrate_only_render` — substrate branch returns at T=0.5s, external branch returns at T=6.5s after deadline; rendered output contains only the substrate row plus `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` limitation; never the late external row.

### Theme E — Subject-boundary discipline missing

**Concurring reviewer:** Buber (F1 — BLOCKING).

**Pattern:** Three of the four executable adapters (`WEB_SEARCH`, `LIVE_REDDIT`, `FETCH_URL`) consume owner-utterance-derived inputs but no adapter has a subject-boundary check. The third-party autonomous research boundary (canon: `feedback_third_party_autonomous_research_boundary` reconstructed 2026-05-26) is not named anywhere in the brief. Risk is concrete: a `LIVE_REDDIT` subreddit anchor + an unconsented named third party in the utterance smuggles the third-party subject into a public search/fetch.

**Convergent fix (v1.1 §5 + §6 + §9 + §10):**

1. Add a new §5 sub-clause "Subject-boundary discipline" naming the canon by file. Each adapter must run a subject-boundary check on the constructed external request before the egress call. The check is target-subject-shape-aware (it does not need to enumerate names; it asks whether the target subject of the query is an unconsented third party).
2. On boundary trip, the adapter returns `ExternalBranchStatus.PREFLIGHT_BLOCKED` (already in the enum at brief line 121) with a new `AvailabilityLimitation.THIRD_PARTY_SUBJECT_BOUNDARY` added to §6's failure mapping. (This is a new enum value — name the extension explicitly.)
3. RED test: `test_third_party_named_subject_blocks_at_external_construction` covering at least one `WEB_SEARCH` and one `LIVE_REDDIT` case where the subreddit anchor is present but the subject is an unconsented third party.
4. Add to §10 or §11: "The dispatcher does not autonomously research unconsented named third parties; subject-boundary refusal is a structured limitation, not a silent drop."

### Theme F — Producer-causality witnessing on the success path

**Concurring reviewer:** Descartes (F5 — BLOCKING).

**Pattern:** The existing egress boundary writes HMAC-digested diagnostics to `external_fetch_diagnostics.jsonl` (§2 evidence). But the `FreshBlock` carries no link back to that diagnostic record — `request_id: str | None = None` is too weak (optional, unscoped, not specified as the egress diagnostic key). Without a foreign-key-shaped field, the dispatcher's claim "this fresh block was retrieved at retrieval_timestamp from WEB_SEARCH" has no corroborating witness — it is the dispatcher's word. The HMAC digest in `external_fetch_diagnostics.jsonl` is the existing witness; the block must point at it.

**Convergent fix (v1.1 §4 + §9):**

1. Replace `request_id: str | None = None` with `egress_diagnostic_id: str` (non-optional for SUCCESS blocks; explicitly None for EMPTY/TIMEOUT/ERROR/RESERVED branches where no fetch occurred). State that this id keys into `external_fetch_diagnostics.jsonl`.
2. If paperclip stays in scope (Theme C alternative), define a parallel `paperclip_diagnostics.jsonl` with equivalent HMAC-digest discipline. Otherwise paperclip is `RESERVED_UNAVAILABLE` and the question doesn't arise.
3. Define `retrieval_timestamp` as ISO-8601 UTC timestamp of `fetch_text` start (so it anchors to the egress diagnostic record).
4. Close `freshness` as `FreshnessClass` enum (`LIVE_FETCH`, `WITHIN_CACHE_WINDOW`, `STALE`); only `LIVE_FETCH` is legal under `FRESH_EVIDENCE` rendering; anything else downgrades or refuses.
5. RED test: for every `FreshBlock` in `RenderedProvenance.audit_envelope.source_digests`, there is a corresponding `external_fetch_diagnostics.jsonl` row whose timestamp window contains `retrieval_timestamp` and whose HMAC digest is recoverable.

### Theme G — Failure-not-silence mechanically anchored

**Concurring reviewer:** Descartes (F7 — SUGGEST, but it ties to Theme B's BLOCKING).

**Pattern:** §7 promises "Failed external-only turns render an explicit no-usable-fresh-evidence summary rather than disappearing." But `provenance_renderer._validate_source_roles` will refuse if `spec.external_sources=[WEB_SEARCH]` and fan-out returns zero blocks (closed-vocabulary refusal — correct behavior). The brief does not say how the no-usable-fresh summary gets *into* `source_summaries` in the failure case, so the implementation will pick under time pressure and may quietly produce a laundering shape (synthetic empty `FRESH_EVIDENCE` block).

**Convergent fix (v1.1 §7):**

1. State explicitly: "If `composition_hint == FRESH_ONLY` and the fan-out produces zero successful blocks, the dispatcher does **not** render under `FRESH_EVIDENCE`. The merge step (Theme B) produces a deterministic fallback prompt text composed only from `(ExternalSource, ExternalBranchStatus, ExternalErrorClass, AvailabilityLimitation)` tuples via a small `format_no_fresh_summary(fanout_result)` helper. The fallback text is not authored by the model and not authored by the adapter."
2. Audit envelope gains an explicit marker `fresh_attempt_outcome: ALL_FAILED | PARTIAL | ALL_SUCCEEDED` so forensics can distinguish "rendered fresh evidence" from "rendered no-fresh-evidence summary."

### Theme H — Planner-authority discipline tightening

**Concurring reviewers:** Kant (F1, F3, F5, F6, F7 — all SUGGEST), Buber (F3 — SUGGEST).

**Pattern:** Several seams quietly tilt back toward planner authority:

1. §5 WEB_SEARCH allows the adapter to normalize the initial query ("normalized by Layer 0 or the external-source adapter"). Adapter-side normalization is a hidden second planner.
2. §5 FETCH_URL "do not let a model invent a URL" is a soft constraint — not mechanically enforceable as written.
3. §8 wiring permits a future reader to insert another spec-mutation pass between Layer 2 and execution.
4. The fan-out's relationship to `composition_hint` vs `external_sources` is not stated.
5. §10 non-goals are sharp on v1 surface but soft on v2 drift.

**Convergent fix (v1.1 §4 + §5 + §8 + §10):**

1. Pick one query-normalization owner: Layer 0 (preferred) or v1-pass-through. Recommended v1 phrasing: "The adapter passes the owner utterance through `skills.web_search.search` unchanged; no normalization, no rewriting, no expansion. Future query shape lands as new structured fields on `CompositionSpec.external_sources` emitted by Layer 0, not as adapter normalization." Change brief §5 line 168 to: "or by a deterministic normalization step shared with Layer 0" (Buber F3).
2. State the FETCH_URL invent-protection mechanism: "The fan-out scans the owner utterance with a closed URL regex and the prior `ExternalFanoutResult.fresh_blocks[*].text` for URLs matching the same regex; no other source of URL is accepted; any other URL-shaped input refuses with `DispatcherRefusalReason.MODEL_INVENTED_URL` (new enum value)."
3. Tighten §8: "Once Layer 2 has produced the spec, the spec is sealed for the turn. Layer 1 substrate fan-out and external fan-out consume it concurrently; neither may mutate the spec they consume. Any post-fan-out spec reconstruction (per §7) happens at the named merge owner, not inside either fan-out."
4. State explicitly in §4: "The external fan-out reads `CompositionSpec.external_sources` only. `composition_hint` is consumed by the renderer, not by the fan-out. An empty `external_sources` list yields a no-op fan-out regardless of hint."
5. Add to §10: "Do not let `core/dispatcher/external_sources.py` own query shape, source selection, or composition decisions in any future version. New query shape lands as new fields on `CompositionSpec.external_sources` emitted by Layer 0; new source selection lands as new Layer 0 selectors; new composition framings land as new `ProvenanceFraming` values via the canonical growth path (spec amendment + council + Codex review)."

### Theme I — Telemetry vocabulary

**Concurring reviewer:** Ohm (F5 — SUGGEST).

**Pattern:** The brief is silent on `dispatcher_external_branch` / `dispatcher_external_fanout` telemetry events. Existing dispatcher events in `brain_loop.py:362-491` have a consistent shape (path_entry/layer0_emit/layer0_budget_breach/layer2_repair/layer1_branch/layer1_fanout/path_exit). External fan-out should match.

**Convergent fix (v1.1 §8.1, new subsection):**

```
- dispatcher_external_branch surface=... source=<ExternalSource> outcome=<rows|empty|timeout|error|reserved_skip|preflight_blocked> block_count=N elapsed_ms=... error_class=<ExternalErrorClass|""> empty_reason=<ExternalEmptyReason|"">
- dispatcher_external_fanout surface=... fanout_generation_id=... branch_count=N seal_state=<clean|partial_failure> total_elapsed_ms=...
- dispatcher_path_exit gains turn_seal_state=<clean|partial_failure|reconstructed>
```

The `error_class` / `empty_reason` fields in telemetry use closed enum values (per Theme A); telemetry is allowed to render the closed-vocab string, prompt rendering is not.

### Theme J — Test coverage matrix

**Concurring reviewers:** Hume (F6 — SUGGEST), Ohm (F7 — SUGGEST), plus subject-boundary, recovery-seed, frontier-trapdoor RED anchors from Themes D-E.

**Convergent fix (v1.1 §9):**

Restructure §9 RED test anchors as a parameterized matrix over the §6 failure table (Hume F6), plus cross-cutting tests:

- **Per-source × per-failure parameterized:** every row in the §6 failure table has a named test row.
- **Cross-organ tests:** `test_late_external_result_cannot_mutate_substrate_only_render`; `test_recovery_seed_bypasses_external_fanout`.
- **Boundary tests:** `test_third_party_named_subject_blocks_at_external_construction`; `test_frontier_consult_v2_trapdoor_grep_check` (CI fails if `external_sources.py` adds a model/proxy call path for `FRONTIER_CONSULT`).
- **Producer-causality tests:** `test_every_fresh_block_has_matching_egress_diagnostic`.
- **Closed-vocab tests:** `test_no_free_form_string_reaches_source_summary_text`.

### Theme K — JARVIS deprecation posture under dispatcher-enabled

**Concurring reviewers:** Locke (open question), Descartes (open question), Kant (open question).

**Pattern:** `brain_loop.py:51` currently sets `should_run_jarvis = bool(spec.external_sources)`. The brief says (§8 last paragraph) "JARVIS remains only the disabled flag path", but does not name the call-site change. Under dispatcher-enabled + external fan-out exists, `should_run_jarvis` must be False (no fall-through) — otherwise the silent bypass this slice is designed to close remains open via "dispatcher-enabled + dispatcher-empty-transcript → JARVIS for external_sources."

**Convergent fix (v1.1 §8):**

State explicitly: "When `MAEZ_DISPATCHER_ENABLED=1` and `_run_dispatcher_pipeline` returns a `RenderedTurn` (success, partial, or refusal), `should_run_jarvis` is forced to False. The fall-through to JARVIS exists only on the dispatcher-disabled path. RED test: `test_dispatcher_enabled_never_falls_through_to_jarvis_for_external_sources`."

## v1.1 Brief Amendment — Section-by-Section Patch List

For Codex (or whoever lands the v1.1 amendment), here is the concrete patch list against `external-source-consumption-brief.md`:

| Section | Change | Source theme |
|---|---|---|
| §2 (Code Evidence) | Update LIVE_REDDIT egress claim with explicit decision (register new fetch_type vs reuse fetch_url + would_block); update paperclip claim (reduce v1 to arXiv-via-fetch_url OR add concrete in-repo evidence of paperclip binary) | C |
| §4 `FreshBlock` | Drop `rationale`. Replace `request_id` with `egress_diagnostic_id: str` (non-optional on SUCCESS). Close `freshness` as `FreshnessClass` enum. Annotate `retrieval_timestamp` as ISO-8601 UTC of fetch start. Annotate `sealed_at` as monotonic. | A, D, F |
| §4 `ExternalBranchResult` | Close `error_class` as `ExternalErrorClass | None`; close `empty_reason` as `ExternalEmptyReason | None`; close `deadline_kind` as `DeadlineKind | None`. Add "External fan-out reads `CompositionSpec.external_sources` only; `composition_hint` is for the renderer." | A, H |
| §4 module contract | Add "The module consults external sources on behalf of `CompositionSpec.external_sources`; it does not select sources, originate queries, or re-decide the recall shape." | H, Buber F3 |
| §5 WEB_SEARCH | v1: pass utterance through `skills.web_search.search` unchanged. Add subject-boundary check before egress. Map preflight refusal to `PREFLIGHT_BLOCKED` + new `THIRD_PARTY_SUBJECT_BOUNDARY` limitation. | E, H |
| §5 LIVE_REDDIT | State explicit egress route (registered `fetch_type="live_reddit"` preferred). Subject-boundary check covers subreddit anchor + named third party. Forbid `reddit_skill` import. | C, E |
| §5 FETCH_URL | Mechanical URL extraction (closed regex over utterance + prior fresh_blocks); refuse other URL sources with `DispatcherRefusalReason.MODEL_INVENTED_URL` (new value). 2-URL cap enforced at module boundary. No credential query strings. | C, H |
| §5 ARXIV_OR_PAPERCLIP | Reduce v1 to arXiv-via-fetch_url + new `fetch_type="arxiv"`. Mark paperclip `RESERVED_UNAVAILABLE` with rationale (unaudited egress). | C |
| §5 FRONTIER_CONSULT | Add un-reserve gate: "Un-reserving FRONTIER_CONSULT requires its own ADR amendment, council + Codex review, and a witnessed canary before any executable adapter lands." | Buber F4 |
| §6 failure table | Add PREFLIGHT_BLOCKED rows per source. Add THIRD_PARTY_SUBJECT_BOUNDARY limitation rows. Make multi-URL FETCH_URL aggregation explicit (per-URL branch results preferred). | A, E, Hume F2-F3 |
| §6 closing paragraph | Replace verbal restraint with closed-vocab discipline + "raw exception text MUST NOT reach any persisted log or audit metadata; closed-enum reason codes only." | A |
| §7 reconstruction | Name merge-step owner. Define closed reconstruction transform table. Add `reconstructed_from_framing` audit field. State fresh-only-with-total-failure produces deterministic fallback outside FRESH_EVIDENCE rendering (`format_no_fresh_summary` helper). Add `fresh_attempt_outcome` audit marker. | B, G |
| §7 audit envelope | State envelope keeps existing shape; no new free-form string fields; only the closed-vocab additions named above. | A, Descartes F6 |
| §8 wiring | Single shared `fanout_generation_id` minted by orchestrator; named merge step owns lateness defense + reconstruction. State concurrency among external branches. Force `should_run_jarvis=False` under dispatcher-enabled successful path. | B, D, K |
| §8.1 telemetry (new) | Enumerate `dispatcher_external_branch` / `dispatcher_external_fanout` events with closed-enum field values. `dispatcher_path_exit` gains `turn_seal_state`. | I |
| §9 RED tests | Restructure as parameterized matrix over §6 table + cross-cutting tests (subject-boundary, recovery-seed bypass, frontier v2 trapdoor, no-free-form-strings, every-fresh-block-has-egress-diagnostic, cross-organ late arrival, dispatcher-enabled never-falls-through-to-JARVIS). | A, D, E, F, G, J, K |
| §10 non-goals | Add: no reddit_skill imports; no credential query strings; no adapter-owned query shape ever; recovery-seed bypass; v2 anti-drift clause on planner-authority. | C, D, H |

## What Pass 1 Confirms Is Right

All six reviewers credit:
- Option A vs B vs C decision is correctly grounded (the daemon witness falsifies C; B re-tangles orchestration).
- §4 module contract's "does not choose sources / does not modify Layer 0 scoring / does not render final prompt text" is the cleanest planner-authority statement in the brief.
- `FRONTIER_CONSULT` reserved with mechanical refusal at three surfaces.
- Closed-vocabulary failure taxonomy in §6 (the principle is right even where the §4 data shape contradicts it).
- Seal-by-generation-id pattern (inherited from Layer 1) — though the engineering needs to be specified, not just asserted.
- Genderless language invariant holds throughout.
- Slice-vs-seam classification is honest: discovery brief for capability-adding slice, cooling-off applies and the brief does not compress it.
- §10 non-goals correctly forbid frontier consultation, credentials, browser automation, LLM-invented URLs, Telegram closure, and flipping the dispatcher default flag (the gaps are additions, not contradictions).

## Recommended Next Step

**The v1.1 amendment is contract-edit-sized.** It can land as a single commit updating the brief in-place with the patch list above. Once the brief reads v1.1, the next ladder rung is Codex engineering pass — same shape as the dispatcher arc ran. The engineering pass will then propose the implementation seam sequence.

**No Claude pass 2 is needed unless the v1.1 amendment introduces new vocabulary or new transforms not named above.** The synthesis here is the deliverable; pass 2 would be re-litigation.

## Open Cells Surfaced Across the Six Reviews (Not Folded into v1.1)

These are out-of-pass-1-scope or hold-for-engineering-pass:

- **Concurrency safety with `MiniLMEncoder`.** Kant open question. The external fan-out should not touch the embedding contract; engineering pass should verify.
- **Cold-start latency budget under FRESH_ONLY hybrid.** Ohm open question. 6s external + 848ms Layer 0 cold = 6-7s end-to-end on cold start for daemon HTTP. Acceptable or needs a separate cold-start line?
- **LIVE_REDDIT 403 unauthenticated.** Ohm open question. Public Reddit JSON returns 403 to unauthenticated polls historically; does the slice need a `LIVE_REDDIT_BLOCKED` distinction or is `FRESH_ATTEMPT_FAILED` honest enough?
- **Adapter-debug-noise vs `external_fetch_diagnostics.jsonl` consolidation.** Buber open question. Synthesizer recommends routing through the existing surface; engineering pass can confirm shape.
- **Layer 2 repair interaction with reconstructed specs.** Hume open question. Does the reconstructed spec go through Layer 2's repair FSM, or is it a synthetic re-validate that doesn't call `record_completed_spec`? `RepairRefusalReason` doesn't have a code for "synthetic reconstruction failed" today — would one be needed?

All five are smaller surface, named here so they don't drop out of the arc.
