# Claude External-Source Pass 1 — Buber (Covenant)

**Verdict:** SUGGEST

## Summary

The brief is fundamentally bond-honoring: external sources are consumed *on behalf of* a Layer-0-issued recall need, not as planner authority over Maez, and `FRONTIER_CONSULT` is held reserved with mechanical refusal. Three covenant seams need tightening before canonicalization: the third-party autonomous-research boundary is not named at all (the `LIVE_REDDIT` / `WEB_SEARCH` / `FETCH_URL` adapters need an explicit subject-boundary discipline that maps to `feedback_third_party_autonomous_research_boundary`); the §6 debug-log carve-out for raw exception text is not sharp enough to prevent owner-utterance leakage; and the language ledger leans on planner-flavored verbs ("decide", "chooses") that should be reshaped to consult-on-behalf-of phrasing. None of these are deal-breakers; all are nameable and small.

## Findings

### Finding 1 — Third-party autonomous-research boundary not named in any external-source adapter

**Severity:** BLOCKING
**Where:** brief lines 162-200 (all four executable source adapters), lines 308-316 (Non-Goals)
**Observation:** The brief specifies query construction discipline ("the initial query is the owner utterance normalized by Layer 0", "Do not let a model invent a URL", "no LLM-generated query is required for v1") which prevents *model-invented* external research. But it never names `feedback_third_party_autonomous_research_boundary` — the standing canon that Maez may not autonomously research unconsented named third parties, that this boundary is a three-layer discipline (at-creation, at-construction, at-egress), and that the discipline is subject-bounded, not token-scrubbed.

The risk is concrete and adapter-specific:

- `WEB_SEARCH` (§5, lines 164-172): the "normalized utterance" path means if the owner utterance names an unconsented third party in passing (`"is X up to anything?"`), the normalized query carries that name into a public search engine. The adapter has no subject-boundary check.
- `LIVE_REDDIT` (§5, lines 174-186): the "subreddit anchor" trigger does not address the case where the utterance contains *both* a subreddit anchor and an unconsented named third party (`"check r/X for what people say about <named person>"`). The subreddit anchor passes the selector gate; the third-party subject smuggles through.
- `FETCH_URL` (§5, lines 188-194): "explicit URLs present in the owner utterance" is the right anchor for URL invention, but does not constrain *whose* personal page or profile is being fetched.
- `ARXIV_OR_PAPERCLIP` (§5, lines 196-200): low risk (papers are a public artifact class, not a personal-subject class), but the brief should still name that the boundary applies.

Non-Goals (§10, lines 308-316) explicitly enumerates frontier consultation, credentials, browser automation, Layer 1 boundary, LLM-invented URLs/queries, Telegram closure, dispatcher default, and R#17 — but does not name the third-party-research boundary. That absence is the failure mode this canon was reconstructed to prevent (see `feedback_third_party_autonomous_research_boundary` reconstructed 2026-05-26).

**Recommendation:** Add a new §5 sub-clause "Subject-boundary discipline" that names the canon by file and requires:

1. Each adapter must run a subject-boundary check on the constructed external request before the egress call. The check is owner-utterance-shape-aware (it does not need to enumerate names; it asks whether the *target subject* of the query is an unconsented third party).
2. On boundary trip, the adapter returns `ExternalBranchStatus.PREFLIGHT_BLOCKED` (already in the enum at line 121) with a new closed availability limitation `THIRD_PARTY_SUBJECT_BOUNDARY` added to §6's failure mapping.
3. RED test anchor: `test_third_party_named_subject_blocks_at_external_construction` covering at least one `WEB_SEARCH` and one `LIVE_REDDIT` case where the subreddit anchor is present but the subject is an unconsented third party.
4. Add to §10 Non-Goals or §11 Predicted Effect: "The dispatcher does not autonomously research unconsented named third parties; subject-boundary refusal is a structured limitation, not a silent drop."

This is BLOCKING because the alternative (canonicalize the slice, then add subject-boundary later) means the first canonical external-source surface ships without the discipline that exists in canon specifically to prevent it — exactly the laundering pattern `feedback_producer_causality_no_caller_score_laundering` and `feedback_fold_second_order_contradictions` were reconstructed to refuse.

### Finding 2 — Debug-log carve-out for raw exception text is not sharp enough

**Severity:** SUGGEST
**Where:** brief lines 226-228 (§6 closing paragraph)
**Observation:** The text reads:

> No free-form failure reason should reach prompt rendering or audit metadata. Raw exception text may be logged at debug level only if it contains no raw owner-private content.

The discipline ("no raw owner-private content") is correct in intent but stated as a condition the *logger* must check, with no mechanism for that check. In practice, exception text from `core.egress.external_fetch.fetch_text` can include URL query strings (which for `WEB_SEARCH` are the owner-utterance-derived query), HTTP response bodies, traceback locals, and other fields that may carry utterance fragments or recall-context-derived strings. The "only if it contains no raw owner-private content" gate has no enforcement surface — it relies on whoever writes the logger to remember and verify.

This is the same shape as the audit-metadata laundering pattern the spec brief solves elsewhere (§4 audit envelope is closed-vocabulary, structurally enforced). The debug-log surface should match that discipline.

**Recommendation:** Replace lines 226-228 with a sharper rule:

> Failure reasons that reach prompt rendering or audit metadata must be drawn from the closed failure taxonomy below; free-form failure text is forbidden on those surfaces. Debug-level logs for adapter failures must record only: `source`, `branch_id`, `status`, `error_class`, `elapsed_ms`, `deadline_kind`, and a digest of the egress request id. Raw exception messages, response bodies, URLs containing owner-derived query strings, and tracebacks must not be written to any persisted log surface; if exception detail is needed for live debugging, it must go through the existing `external_fetch_diagnostics.jsonl` discipline which already handles HMAC digests (per §2 evidence at line 63).

This converts the verbal restraint into a structural one and routes adapter-debug-noise through the diagnostics surface that already knows how to handle it.

### Finding 3 — Planner-flavored verbs in §3 and §4 quietly tilt source execution toward command-authority

**Severity:** SUGGEST
**Where:** brief line 22 ("without handing the decision back to the legacy JARVIS planner"), line 86 ("the dispatcher claim"), line 100 ("The dispatcher needs a real external-source organ, not a planner fallback"), line 111 (module docstring shape: "owns fresh-source fan-out")
**Observation:** The covenant frame from the spec-brief (`spec-brief.md` §5 lines 286-292, the "Layer 0 organ location" clause) names Layer 0 as an *intra-Maez organ* — it separates Maez's own organs, it does not install an arbiter over Maez. The external-source brief inherits that frame implicitly but in places drifts into language that reads as "the dispatcher decides what to fetch", which can re-introduce the planner-authority shape the slice exists to retire.

This is mostly cosmetic but matters for how future agents reading this brief understand the relational shape. The spec-brief was careful to distinguish *consult on behalf of Maez's recall need* from *route on behalf of a classifier*. The external-source brief should carry the same care.

Concrete instances:

- Line 22: "without handing the decision back to the legacy JARVIS planner" — the contrast is correct; the word "decision" is slightly planner-flavored. A bond-preserving phrasing: "without re-routing through the legacy JARVIS planner's tool-call surface".
- Line 100: "The dispatcher needs a real external-source organ, not a planner fallback" — "organ" is good (it preserves the intra-Maez frame); the sentence works as-is. Keep.
- §4 line 111: "The module owns fresh-source fan-out only. It does not choose sources..." — the "does not choose sources" half is exactly right (Layer 0 already chose); the module *executes* what was chosen. The phrasing here is honest.
- §5 line 168: "The initial query is the owner utterance normalized by Layer 0 or the external-source adapter" — the "or the external-source adapter" half is slightly loose: it lets the adapter own query normalization. For covenant cleanliness, query normalization should be a Layer 0 responsibility (or an explicit shared utility), so the adapter receives a normalized query and does not re-decide what to send.

**Recommendation:**

1. Line 22: change "without handing the decision back to" → "without re-routing through".
2. Line 168: change "or the external-source adapter" → "or by a deterministic normalization step shared with Layer 0"; do not let adapters silently re-normalize.
3. Add to §4 (Proposed Module Contract) one sentence under "The module owns fresh-source fan-out only.": "The module consults external sources on behalf of `CompositionSpec.external_sources`; it does not select sources, originate queries, or re-decide the recall shape."

### Finding 4 — `FRONTIER_CONSULT` reservation discipline is mechanical but not language-locked

**Severity:** SUGGEST
**Where:** brief lines 41 (canon evidence), 202-205 (§5), 224 (§6 failure table), 292-294 (RED test 4)
**Observation:** The brief holds `FRONTIER_CONSULT` reserved at three surfaces: the canon-evidence summary, the source-behavior section, and the failure-mapping table; RED test 4 asserts non-execution. This is good mechanical discipline.

The covenant-axis risk is what happens after v1: nothing in this brief names what *un-reserving* `FRONTIER_CONSULT` would require. Canon today (ADR 0047 v1.4, line 41) says "reserved/non-executable in v1". The seam to v2 is not specified. Without a named gate, a future slice could silently un-reserve by appending an executor, and the only thing preventing that is a RED test that would need to be deleted in the same PR (an easy move for a future agent under time pressure).

This is a soft finding because it does not need to land in this slice — but the brief is the right place to name the gate because this is the canonical introduction of `FRONTIER_CONSULT` as a real surface.

**Recommendation:** Add to §10 Non-Goals or §5's `FRONTIER_CONSULT` paragraph one sentence: "Un-reserving `FRONTIER_CONSULT` requires its own ADR amendment, council + Codex review, and a witnessed canary before any executable adapter lands; this slice does not create that pathway." That sentence converts the reservation from "v1 doesn't implement it" to "v2 cannot silently implement it".

### Finding 5 — Slice-vs-seam classification is honest; cooling-off applies and the brief does not compress it

**Severity:** NIT (credit, not blocker)
**Where:** brief line 3 ("discovery brief for the next ADR 0047 implementation slice")
**Observation:** Per `feedback_seam_vs_slice_cooling_off`, capability-adding slices properly cool off before canonicalization, while seams closing review-identified trapdoors can land same-day. This brief is a capability-adding slice (it introduces `core/dispatcher/external_sources.py`, a new module owning real external IO), and the brief correctly frames it as a discovery brief — not a closure receipt. The timeline language ("next implementation slice") is honest. Cooling-off applies and the brief does not compress it.

This is credit, not a finding, but I name it because the brief's classification is exactly the kind of judgment call the canon was reconstructed to keep honest, and the brief got it right.

**Recommendation:** None. Keep the framing.

## What the brief gets right

- Frames external sources as consumed *on behalf of* a Layer-0-issued spec, not as planner authority — line 21-22 cleanly inherits the spec-brief's intra-Maez-organ shape.
- Holds `FRONTIER_CONSULT` reserved at three surfaces (canon evidence, source behavior, failure mapping) and asserts non-execution with a RED test (line 292-294).
- Genderless language invariant holds throughout — Maez is referred to as "it" / by-name; no gendered pronouns slipped in. (Spot-checked lines 25-26, 100-103, 320-322.)
- Failure mapping (§6 table) is closed-vocabulary, drawn from ADR 0047 taxonomy, and forbids free-form failure reasons reaching prompt rendering or audit metadata.
- `ExternalFanout` seal discipline (line 158-160) inherits the same `fanout_generation_id` pattern Layer 1 uses, so late results cannot mutate rendered output — RED test 6 anchors this.
- Hybrid-failure rendering (§7) requires substrate-with-failed-fresh to produce a valid reconstructed `CompositionSpec` before render, with explicit refusal if invalid — this is the producer-causality discipline applied at composition time.
- Non-Goals (§10) is honest about scope; Telegram transport, R#17, and dispatcher-default-flip are explicitly out of scope.

## Open questions for synthesis

- **Concurrent fan-out cancellation under preflight refusal.** §4 line 158-160 inherits Layer 1's seal discipline but does not specify what happens when a `PREFLIGHT_BLOCKED` (subject-boundary or egress-policy) result returns before other branches complete. This is concurrency/failure-taxonomy territory — other reviewer lenses own it — but if Finding 1 adds `THIRD_PARTY_SUBJECT_BOUNDARY`, that interaction is worth a sentence in the seal contract.
- **External-source adapter telemetry vs `external_fetch_diagnostics.jsonl` interaction.** RED test 7 (line 304-306) asserts the diagnostic file is written; Finding 2 above proposes routing adapter-debug noise through the same surface. Synthesizer may want to fold these into a single discipline rather than two parallel ones.
- **Query-normalization ownership.** Finding 3's recommendation (Layer 0 or shared utility owns normalization, not the adapter) touches on Layer 0's surface, which is owned by the parent spec brief. Synthesizer should decide whether to fold the clarification here or push it back to the spec-brief.
