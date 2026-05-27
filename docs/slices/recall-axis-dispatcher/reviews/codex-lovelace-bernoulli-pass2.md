# Recall-Axis Dispatcher — Codex Lovelace/Bernoulli Pass-2 Review

## Verdict

STILL OPEN

## Per-Batch Closure Table

| Batch | v1.2 change cited (line/section) | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | `spec-brief.md:153-179`, `622-624`, `691` | CLOSED | `CompositionSpec` now carries `inventory_witness`, `source_availability`, `availability_limitations`, freshness, and trust scope; closed witness values and serialization/render/audit test anchor are present. |
| 2 | `spec-brief.md:329-334`, `395-424`, `626-628`, `692` | CLOSED | Executable vs reserved labels are split; `CROSS_SURFACE_OWNER_TURNS` ambiguity is removed; reserved labels return unavailable and are test-anchored. |
| 3 | `spec-brief.md:280`, `548-550`, `668`, `693` | CLOSED | Ingress set is enumerated; Layer 0 is required before tool/fetch/recall/render; legacy JARVIS path is fully qualified. |
| 4 | `spec-brief.md:236-242`, `630-632`, `694` | STILL OPEN | Threshold constants and tie determinism are now measurable, but the no-match fallback does not define exact source-selection rules. |
| 5 | `spec-brief.md:502-527`, `665`, `735` | CLOSED | Versioned manifest requirements, corpus size, class coverage, negative cases, sentinel pairs, full-spec fixtures, false-hybrid ceiling, and amendment trigger are measurable; language says witnessed-turn samples, not distribution sampling. |
| 6 | `spec-brief.md:217-232`, `278`, `380`, `683`, `695` | CLOSED | Shared `MiniLMEncoder` API, singleton, Chroma surface, contract validation, lifecycle budget, and no-double-instantiation test are specified. |
| 7 | `spec-brief.md:287`, `291`, `572-574`, `612`, `685` | CLOSED | `InventorySummary` owner, registry fields, invalidation/cursor model, privacy gates, UNKNOWN fallback, and no-live-count test are specified. |
| 8 | `spec-brief.md:206-213`, `385`, `568-570`, `696` | STILL OPEN | Renderer ownership and mismatch behavior are present, but audit payload fields for both `audit_assistant_text` and `self_claim_audit` are not specified. |
| 9 | `spec-brief.md:391-393`, `484-498`, `673-675`, `697` | CLOSED | Closed refusal reasons, fail-closed downstream semantics, audit serialization, caller-supplied verdict/source refusal, and vocabulary-growth fixture are covered. |
| 10 | `spec-brief.md:366-373`, `436`, `677-678` | STILL OPEN | FSM states and storage key exist, but tests do not cover cross-surface concurrent turns and post-repair construction validation explicitly enough. |
| 11 | `spec-brief.md:303-314`, `608`, `689-690`, `698` | STILL OPEN | Result states, timeouts, global deadline, merge order, and budgets exist, but cancellation behavior is not explicitly specified or test-anchored. |
| 12 | `spec-brief.md:336-354`, `638-640`, `699` | CLOSED | External execution owner, per-source budgets, attempt caps, global deadline, error mapping, and freshness-scoring deferral are specified. |
| 13 | `spec-brief.md:375-385`, `594-596`, `700` | CLOSED | Concrete module map names all v1 deliverables and preserves dispatcher vs producer-causality boundaries. |
| 14 | `spec-brief.md:278`, `314`, `684`, `698`, `701`, `703` | STILL OPEN | Warm/cold/prewarm and full-manifest tests exist, but p95 adapter budgets using realistic local stores are not required; the split instead mentions mock substrate integration. |
| 15 | `spec-brief.md:560`, `620`, `668`, `665` | CLOSED | “must not launder,” D15 `SANDBOX_WITNESSES`, fully qualified `core/brain/brain_loop.py:900`, and witnessed-turn sample language are corrected. |

## Still Open

Batch 4 fails at `spec-brief.md:242`: it defines fallback `CompositionHint` and `ProvenanceFraming`, but not the exact source-selection rule for no-match cases. v1.3 closure: specify which `substrate_sources` and `external_sources` are selected when no archetype clears `no_match_below`, separately for `PRESENT`, `UNKNOWN`, and `ABSENT`, with deterministic ordering and reserved-source handling.

Batch 8 fails at `spec-brief.md:210-211`: it says audit metadata is passed to `self_claim_audit.py`, but does not name payload fields and omits `audit_assistant_text`. v1.3 closure: list the required audit payload fields and require both `audit_assistant_text` and `self_claim_audit` to receive them, with a test asserting the envelope.

Batch 10 fails at `spec-brief.md:677-678`: tests cover repair order plus no-prior/expired/crash states, but not cross-surface concurrent turns or post-repair construction validation as required. v1.3 closure: add explicit RED anchors for cross-surface concurrent prior-spec isolation and validation/refusal of the modified post-repair `CompositionSpec`.

Batch 11 fails at `spec-brief.md:314` and `698`: deadlines and stable merge order are specified, but cancellation behavior after timeout is not. v1.3 closure: define whether slow branches are cancelled, abandoned, or allowed to finish out-of-band; require telemetry/audit state and a test proving behavior.

Batch 14 fails at `spec-brief.md:703`: the test split names mock substrate integration, but pass-1 required p95 adapter budgets using realistic local stores rather than pure mocks. v1.3 closure: add a realistic-store budget fixture with p95 assertions for selected local adapters and source-count limits.

## NITs

None.
