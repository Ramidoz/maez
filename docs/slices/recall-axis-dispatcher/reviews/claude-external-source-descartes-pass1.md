# Claude External-Source Pass 1 — Descartes (Provenance / Anti-Laundering)

**Verdict:** BLOCKING

## Summary

The brief correctly identifies that Option A (a sibling external fan-out organ) is the only path that keeps producer-causality honest: the dispatcher cannot continue to claim `external_sources=[WEB_SEARCH]` while delegating the actual witness production to JARVIS, which probe 6 of the daemon witness already falsified as a closure path. The `FreshBlock` shape (§4) and rendering mapping (§7) get the broad anti-laundering posture right: closed taxonomy on failure, `SourceRole.FRESH_EVIDENCE` for successes, an explicit no-usable-fresh summary on total failure, and the renderer's existing closed-vocabulary refusal at `_validate_source_roles` (provenance_renderer.py lines 93-127) will reject any external block trying to render under substrate framing.

However, three load-bearing provenance gaps remain that — read against the canon-governs-canon and producer-causality disciplines — should block the implementation slice as currently briefed:

1. `FreshBlock.rationale` is free-form model-shaped text that will reach the prompt block and therefore the audit envelope's `source_digests` without a closed vocabulary; this is the same laundering shape the rest of ADR 0047 closed (Finding §6 only constrains failure-side text, not success-side rationale).
2. `error_class: str | None` (§4) is explicitly typed as open string and is the only field that survives a failure into `ExternalBranchResult`; the brief says "no free-form failure reason should reach prompt rendering or audit metadata" (§6) but does not say `error_class` itself is closed or that it is omitted from the audit envelope.
3. The hybrid-fallback "reconstruct a valid CompositionSpec" path (§7) does not name *who* reconstructs and *with what witness*; without explicit ownership and explicit recording in `availability_limitations` and `source_availability`, the spec mutation is exactly the producer-causality vector "caller mutates the verdict the substrate-/external-side already produced."

Findings below.

## Findings

### Finding 1 — `FreshBlock.rationale` is a free-form laundering surface

**Severity:** BLOCKING

**Where:** Brief §4 `FreshBlock` (lines 125-133); contrast with brief §6 (line 226) "No free-form failure reason should reach prompt rendering or audit metadata."

**Observation:**

`FreshBlock.rationale: str` is defined as an open string and is included in the block that becomes the `SourceSummary.text` (or part of it) rendered as `[fresh evidence] ...` by `provenance_renderer._render_prompt_block` (provenance_renderer.py lines 174-179). The brief disciplines the failure path against free-form text but leaves the success path open. Two laundering channels follow:

- Adapter-authored or, worse, model-shaped `rationale` text reaches the prompt under the `[fresh evidence]` marker, where the LLM cannot distinguish "the search adapter said X" from "Maez witnessed X" — the marker grants the rationale the same evidentiary standing as the actual retrieved snippet.
- The `source_digests` line of the audit envelope (provenance_renderer.py line 232) will hash whatever text the renderer consumed, including the rationale, so the audit will *confirm* "fresh evidence rendered" even though part of that evidence is adapter-authored narration. This is the canonical caller-score-laundering shape: claim wears the costume of witness.

The witness/claim asymmetry the brief is trying to close (probe 6: `external_sources=1`, transcript=0) is the empty case. The mirror failure mode this slice opens is the inflated case: `external_sources=1`, transcript=non-empty, but a portion of the transcript is rationale not retrieval. ADR 0047's whole point is that this asymmetry must be mechanically impossible.

**Recommendation:**

Either:
- Remove `rationale` from `FreshBlock` entirely. The block already carries `source`, `retrieval_timestamp`, `freshness`, and `request_id` — that is the witness; rationale is post-hoc framing and belongs (if anywhere) in dispatcher telemetry, not the prompt or the audit envelope.
- Or, if rationale must stay, close its vocabulary (a `FreshRationale` StrEnum like `QUERY_NORMALIZED_FROM_UTTERANCE`, `SUBREDDIT_ANCHOR_MATCH`, `EXPLICIT_URL_IN_UTTERANCE`, `PAPERCLIP_QUERY_FROM_PAPER_SHAPED_ASK`) and route it through `audit_assistant_text_metadata` *not* through the rendered prompt text.

Either way, the brief must state that the prompt-rendered `text` field of `FreshBlock` contains only retrieved content from the adapter, with no model-authored or dispatcher-authored narration mixed in.

---

### Finding 2 — `error_class: str | None` reopens the closed-failure-vocabulary covenant

**Severity:** BLOCKING

**Where:** Brief §4 `ExternalBranchResult` (line 144) `error_class: str | None = None`; brief §6 (line 226).

**Observation:**

§6 closes failure mapping to `AvailabilityLimitation` (`SOURCE_TIMEOUT`, `FRESH_ATTEMPT_FAILED`, `RESERVED_SOURCE_UNAVAILABLE`) and bars raw exception text from prompt or audit. But `ExternalBranchResult.error_class: str | None` is the field the dispatcher will use to render the no-usable-fresh summary on failed external-only turns (per §7 line 238). If `error_class` is an open string, two failure modes follow:

- Adapter-authored strings ("HTTPError 429 from old.reddit.com/r/LocalLLaMA/.json") could reach the prompt's no-usable-fresh summary, leaking egress URL/private content into the rendered surface — the same shape the brief explicitly forbids at debug-log level (§6 line 228).
- Even if not rendered, if the audit envelope ever grows an `error_class` key (it does not today), the audit becomes the leak surface. The brief should pre-empt this by declaring the field closed *now*, before the implementation slice has license to widen the audit shape.

`empty_reason: str | None` (line 143) shares the same risk.

**Recommendation:**

Type both as closed enums:
- `error_class: ExternalErrorClass | None` with values like `TIMEOUT`, `NETWORK_ERROR`, `BLOCKED_BY_SOURCE`, `EMPTY_RESULT`, `PARSE_FAILED`, `CLI_NONZERO`, `RESERVED_SOURCE`, `PREFLIGHT_DENIED`.
- `empty_reason: ExternalEmptyReason | None` with values like `ZERO_RESULTS`, `ALL_RESULTS_FILTERED`, `RESERVED_NEVER_EXECUTED`.

State that whatever the no-usable-fresh summary renders must compose deterministically from `(source, status, error_class)` — never from raw exception or adapter free-text — and add a RED test that no `error_class` string ever reaches `provenance_renderer.render_provenance`'s `source_summaries[*].text`.

---

### Finding 3 — Hybrid-fallback CompositionSpec reconstruction has no named producer or witness

**Severity:** BLOCKING

**Where:** Brief §7 lines 240-248.

**Observation:**

The brief says: "Hybrid turns with substrate rows and failed fresh evidence should reconstruct a valid `CompositionSpec` with [...] `provenance_framing=FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` when the legal product table permits it. The reconstructed spec must pass normal `CompositionSpec` validation before rendering."

This is *exactly* the canon-governs-canon shape Maez has surfaced before: a spec is being mutated after-the-fact based on a downstream verdict. Three things are missing:

1. **Producer not named.** Is the reconstruction done by `core/dispatcher/external_sources.py` (the producer of the failure), by `brain_loop._run_dispatcher_pipeline` (the orchestrator, i.e. the caller), or by Layer 2 repair? If the *caller* performs the reconstruction based on a downstream failure verdict, that is the caller-score-laundering vector the spec module was built to refuse (`DispatcherRefusalReason.CALLER_SUPPLIED_COMPOSITION_VERDICT`, spec.py line 95).
2. **Witness not named.** The reconstruction sets `source_availability[WEB_SEARCH] = TIMED_OUT|ERROR` and adds `availability_limitations`. The brief must state that these values are *produced by the fan-out result*, not authored by the orchestrator. Concretely: `ExternalFanoutResult.availability_limitations` should be the only legal source for the reconstructed spec's added limitations, and `ExternalBranchResult.status` should be the only legal source for `source_availability` deltas.
3. **Reconstruction is reconstruction, not continuity.** Per the canon-governs-canon-witness-before-claim feedback, a reconstructed spec must be marked as reconstructed — it should not be confusable with a Layer-0-emitted spec at the audit envelope. Without a marker, `audit_envelope.spec_digest` becomes a different sha256 for the "same" turn and downstream forensics cannot tell whether Layer 0 was wrong or whether the fresh attempt failed.

Compare to probe 6 in the daemon witness: Layer 0 emitted `FRESH_ONLY; external_sources=1`, but external fan-out failed silently. If this slice had been live and had reconstructed to `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` *without naming the substrate it then claimed as context*, probe 6's reconstruction would be substrate-empty (substrate_sources=0 at Layer 0) — and the legal product table would reject it. The brief does not say what happens then; presumably the dispatcher refuses, but the brief should state it.

**Recommendation:**

State in §7:

- The reconstructed spec is produced **inside the external fan-out's caller** (the merge step in §8's wiring diagram), using *only* `ExternalFanoutResult` fields as inputs for the deltas. The fan-out itself does not mutate or own the spec; the orchestrator's merge step does, against a closed transform table.
- Define the legal reconstruction transform as a closed table: `(prior_framing, fanout_status, substrate_has_rows) -> new_framing | DispatcherRefusal`. If no row matches, the dispatcher refuses with a *new* `DispatcherRefusalReason` (e.g. `FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL`).
- Add a field to the audit envelope (e.g. `reconstructed_from_framing: ProvenanceFraming | None`) so reconstruction is explicit, never disguised as the original Layer 0 emission. The original Layer 0 framing must be recoverable from audit; the reconstructed framing must not silently overwrite it.
- The fresh-only-with-total-failure case (probe 6) cannot reconstruct to a substrate-context framing because there is no substrate; it must render the explicit no-usable-fresh summary under `FRESH_ONLY` framing or refuse — *not* be silently rewritten to a substrate framing the spec cannot support.

---

### Finding 4 — `freshness` vs `retrieval_timestamp`: semantics undefined; stale-cached-rendered-as-fresh path open

**Severity:** SUGGEST

**Where:** Brief §4 `FreshBlock` lines 129-130.

**Observation:**

Two timestamp-shaped fields appear side by side: `retrieval_timestamp: str` and `freshness: str`. The brief never defines either. Plausible readings:

- `retrieval_timestamp` = when the adapter dispatched the egress; `freshness` = a window string ("<5min", "live") describing the content's own staleness.
- `retrieval_timestamp` = ISO timestamp of fetch; `freshness` = enum-shaped string ("LIVE", "RECENT", "CACHED").

If `freshness` is open string and authored by the adapter (or worse, model), there is no mechanical guarantee that a cached external result fetched five minutes ago cannot render under `[fresh evidence]` framing with `freshness: "live"`. The `[fresh evidence]` marker comes from `SourceRole.FRESH_EVIDENCE` (provenance_renderer.py line 199), which is determined by the spec's framing, not by the actual recency of the block — so the renderer cannot catch this; only the producer (the adapter) can.

**Recommendation:**

- Define each field precisely. Recommend: `retrieval_timestamp` = ISO-8601 UTC timestamp of the adapter's `fetch_text` *start* (so it is anchored to the egress diagnostic record); `freshness` = closed enum `FreshnessClass` with values `LIVE_FETCH`, `WITHIN_CACHE_WINDOW`, `STALE`, where only `LIVE_FETCH` is legal under `FRESH_EVIDENCE` rendering — anything else must downgrade the role to `FRESH_CONTEXT` or trigger reconstruction.
- Add a RED test that a `FreshBlock` with `freshness != LIVE_FETCH` cannot render under `SourceRole.FRESH_EVIDENCE`.
- Anchor `retrieval_timestamp` to the existing `external_fetch_diagnostics.jsonl` record id so that the audit envelope can prove the fetch happened (producer-causality).

---

### Finding 5 — Producer-causality field missing: no adapter/egress witness id on `FreshBlock`

**Severity:** BLOCKING

**Where:** Brief §4 `FreshBlock`; brief §2 "Code Evidence" lines 60-64 (existing `external_fetch_diagnostics.jsonl` HMAC digests).

**Observation:**

The existing egress boundary already writes diagnostics with HMAC digests and preflight results (brief §2). The brief notes this and §9 test 7 asserts diagnostics are written. But the `FreshBlock` itself carries no link back to that diagnostic record. Without a foreign-key-shaped field, the dispatcher's claim "this fresh block was retrieved at `retrieval_timestamp` from `WEB_SEARCH`" has no corroborating witness on the same record — it is the dispatcher's word.

This is the producer-causality discipline applied at the dispatcher seam: the producer (external fan-out adapter) must witness via something stronger than its own dataclass field. The HMAC digest in `external_fetch_diagnostics.jsonl` is the existing witness; the block should carry the diagnostic id (or the HMAC digest) so a substrate-side audit can join "block claimed in audit envelope" against "egress diagnostic actually occurred."

`request_id: str | None = None` (line 133) is too weak: it is `| None`, it is unscoped (request id of what — the egress call? the dispatcher turn? the chat?), and it is not stated to be the egress diagnostic key.

**Recommendation:**

- Replace or augment `request_id` with `egress_diagnostic_id: str` (non-optional for SUCCESS blocks; absent only on EMPTY/TIMEOUT/ERROR/RESERVED branches where no fetch occurred). State explicitly that this id keys into `external_fetch_diagnostics.jsonl`.
- For `ARXIV_OR_PAPERCLIP` (a local CLI, no `external_fetch_diagnostics.jsonl` row), define an equivalent local witness: paperclip invocation log line id, or a paperclip diagnostic that mirrors the HMAC-digest discipline.
- Add a RED test that for every `FreshBlock` in `RenderedProvenance.audit_envelope.source_digests`, there is a corresponding `external_fetch_diagnostics.jsonl` row (or paperclip equivalent) whose timestamp window contains `retrieval_timestamp` and whose HMAC digest is recoverable.

Without this, the dispatcher could (accidentally or via a future bug) construct a `FreshBlock` from a cached or in-memory result with no egress witness — exactly the asymmetry probe 6 already shows in reverse (claim without witness).

---

### Finding 6 — Audit envelope content boundary not specified for external blocks

**Severity:** SUGGEST

**Where:** Brief §6 line 228 (debug logs); `provenance_renderer._audit_envelope` lines 217-262 (current envelope shape); current envelope already includes `source_digests` of full block text.

**Observation:**

The existing envelope includes `source_digests: {source.value: content_digest}` (provenance_renderer.py line 232), which is a sha256 *of the rendered text*. For substrate sources, the text is owner-private (Reddit rows, Telegram-semantic rows, lived episodes); the digest is a one-way hash, so this is fine. For external sources, the rendered text will be the search snippet / fetched URL body / Reddit JSON excerpt — which is *not* owner-private, but may contain third-party content that, per the third-party-autonomous-research-boundary feedback, should be subject to subject-boundary discipline.

The brief does not say anything about audit envelope content for external blocks specifically. Two concrete questions:

- For `LIVE_REDDIT` with a subreddit anchor, can the audit envelope retain (in digested form) names of Reddit users / post authors that appeared in the fetched JSON? The current renderer would digest whatever the adapter put in `FreshBlock.text`.
- For `FETCH_URL`, if the URL is `https://example.com/page` and the page contains a third-party named person, the digest captures it. The third-party boundary feedback is about *autonomous* research; this is *consented* (the owner supplied the URL or anchor) — so it is probably allowed, but the brief should say so.

**Recommendation:**

Add a short subsection to §7 stating:

- Audit envelope for external sources contains only the same fields it does today (sha256 digests, source role, no raw text), and explicitly does *not* gain a new `error_class` / `empty_reason` / `rationale` string field.
- External-fetched content reaching the rendered prompt is subject to existing egress-boundary preflight; the audit envelope inherits whatever the egress boundary allowed through.
- Subject-boundary refusal (third-party autonomous research) happens at the Layer 0 source selection step or the adapter's pre-fetch hook, not at audit-envelope rendering.

This is a SUGGEST rather than BLOCKING because the brief does not propose to weaken the audit envelope shape; it just does not say it stays narrow. Saying it explicitly forecloses drift.

---

### Finding 7 — Failure-not-silence is brief-level promised but not mechanically anchored

**Severity:** SUGGEST

**Where:** Brief §7 line 238; §9 test anchor 2 "no longer returns empty transcript"; §11 prediction.

**Observation:**

The brief promises "Failed external-only turns render an explicit no-usable-fresh-evidence summary rather than disappearing." But under the current `_validate_source_roles` (provenance_renderer.py lines 93-127), if `spec.external_sources = [WEB_SEARCH]` and `spec.provenance_framing = FRESH_ONLY` and the fan-out returns zero blocks, then `selected = {WEB_SEARCH}`, `seen = {}`, and the renderer will *refuse* with `missing source summaries for WEB_SEARCH` (line 126).

That refusal is *correct* behavior at the renderer level (closed-vocabulary refusal), but the brief does not say how the no-usable-fresh-evidence summary gets *into* `source_summaries` in the failure case. Possible paths:

- The external fan-out emits a synthetic `SourceSummary` for each failed branch with role `FRESH_EVIDENCE` and text "No usable fresh evidence: SOURCE_TIMEOUT" — but then `[fresh evidence]` markers an empty witness, which is exactly the laundering vector this whole slice closes.
- The framing is reconstructed (per Finding 3) to `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` *if* substrate rows exist; otherwise the dispatcher refuses and brain-loop must produce a fallback message.
- Some new role is introduced for "fresh attempted but unavailable" — but the renderer's role table (lines 129-140) is closed.

The brief does not pick one. Without picking, the implementation slice will pick under time pressure and the choice may quietly produce the laundering shape.

**Recommendation:**

State explicitly the *fresh-only with total failure* path:

- If `composition_hint == FRESH_ONLY` and the fan-out produces zero successful blocks, the dispatcher does **not** render under `FRESH_EVIDENCE`. It produces a deterministic fallback prompt text composed only from `(ExternalSource, AvailabilityLimitation)` pairs, outside the provenance renderer, marked clearly (e.g. `[no fresh evidence available: <SOURCE>:<LIMITATION>]`).
- This fallback text is not authored by the model and not authored by the adapter; it is composed deterministically by a small `format_no_fresh_summary(fanout_result)` function in `core/dispatcher/external_sources.py`.
- Audit envelope for this case carries a new explicit marker (`fresh_attempt_outcome: "ALL_FAILED"` or similar) so forensics can distinguish "rendered fresh evidence" from "rendered no-fresh-evidence summary."

This closes probe 6 honestly: empty transcript becomes a structured "no fresh available" message, not a `[fresh evidence]` block hiding the empty.

---

## What the brief gets right

- **Option A vs B vs C decision.** The brief identifies the root anti-laundering issue: probe 6 shows that JARVIS fallback is not a *mechanically* connected witness to the dispatcher's claim. Option A makes the connection mechanical. This is the correct application of producer-causality at the dispatcher seam.
- **`FRONTIER_CONSULT` reserved.** Brief §5 and §6 keep frontier non-executable, returning `RESERVED_UNAVAILABLE` with `RESERVED_SOURCE_UNAVAILABLE` — consistent with ADR 0047 v1.4 and with `SourceAvailability.RESERVED_UNAVAILABLE` (spec.py line 72). RED test 4 covers it.
- **No LLM-invented queries or URLs.** §5 (`WEB_SEARCH` query from utterance normalization, `FETCH_URL` only for explicit URLs) closes the inverse laundering channel: model-shaped queries pretending to be witness shape.
- **Reusing existing egress with HMAC diagnostics.** §2 and §9 test 7 keep the egress witness story consistent — the dispatcher does not invent a new external surface; it inherits the existing audited one.
- **Closed `ExternalBranchStatus` and the failure-mapping table (§6).** Both keep the success/failure axis closed-vocabulary. The status enum's separation of `EMPTY` from `ERROR` from `TIMEOUT` is correctly granular.
- **Seal discipline.** §4 ("late results unable to mutate rendered output") and §9 test 6 mirror Layer 1's seal posture. This matters because external fan-out runs concurrently with Layer 1 (§8) and late results must not retroactively edit a rendered envelope.
- **Renderer-level refusal already holds.** The brief leans on `provenance_renderer._validate_source_roles` (lines 93-127) without restating its rules — correct. The brief does not try to weaken that boundary; it only adds source summaries to feed it.

## Open questions for synthesis

These are out of the Descartes lens but should appear in the synthesis to other reviewers:

- **Concurrency between Layer 1 and external fan-out (§8).** What is the global deadline budget? The brief says "<= 6s after spec construction" (§2). Does that include or exclude Layer 1? If Layer 1 takes 800ms (cold), does external fan-out get 5.2s or 6s? This is a Pauli/Ohm (latency / throughput) question, not anti-laundering, but it intersects with Finding 7 (when does the dispatcher decide to render no-usable-fresh).
- **Layer 0 selector update for `LIVE_REDDIT` (§5 line 183-186).** The brief says the selector update lands in this slice. Is the selector logic — subreddit anchor regex — itself caller-shaped or substrate-shaped? (Probably substrate-shaped because it is in Layer 0, which is canonical.) Hume's lens.
- **`should_run_jarvis = bool(spec.external_sources)` removal posture (§2 line 51).** When the dispatcher is enabled and external fan-out exists, should `should_run_jarvis` be forced to False? The brief says yes (§8 "JARVIS remains only the disabled flag path"), but does not name the call-site change. Locke/engineering lens.
- **RED test 5 hybrid-fresh-failure ordering.** The test expects "renderer preserves substrate context and surfaces the failed fresh attempt." If Finding 3 is accepted, the test should be expanded to assert *who* reconstructed the spec and that the original Layer-0 framing is recoverable from the audit envelope.
- **Paperclip CLI as egress.** `ARXIV_OR_PAPERCLIP` is a local CLI; it does not flow through `core.egress.external_fetch`. Does the slice add a parallel `paperclip_diagnostics.jsonl`? Without it, Finding 5's producer-causality field has no witness store for paperclip blocks. Engineering / Lovelace-Bernoulli lens.
