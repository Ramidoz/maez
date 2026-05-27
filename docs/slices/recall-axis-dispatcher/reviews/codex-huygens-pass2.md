# Recall-Axis Dispatcher — Codex Huygens Pass-2 Review

## Verdict

STILL OPEN

## Per-Batch Closure Table

| Batch | v1.2 change cited (line/section) | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | `spec-brief.md:153-179`, `622-625`, `691` | CLOSED | `CompositionSpec` now carries `inventory_witness`, `source_availability`, `availability_limitations`, freshness, and trust-scope fields; closed witness values and serialization/render/audit test anchor are present. |
| 2 | `316-334`, `397-425`, `626-629`, `680`, `692` | CLOSED | Executable vs reserved sources are split; `CROSS_SURFACE_OWNER_TURNS` ambiguity is removed; `LIVED_GRAPH`, `WEB_FAST_TURNS`, and `FRONTIER_CONSULT` are typed reserved/unavailable with tests. |
| 3 | `274-280`, `548-550`, `668`, `693` | CLOSED | In-scope owner ingresses are enumerated; Layer 0 must precede tool/fetch/recall/render; legacy JARVIS path is fully qualified at the test anchor. |
| 4 | `234-243`, `630-632`, `694` | CLOSED | Prototype scoring, normalization, thresholds, precedence, no-match fallback, and deterministic manifest-based scoring are specified. |
| 5 | `500-526`, `665` | CLOSED | Versioned manifest requirements, empirical/proposed tags, reserved/executable state, paired sentinels, 30-turn replay corpus, full-spec fixtures, negative cases, false-hybrid ceiling, and amendment triggers are present. |
| 6 | `217-232`, `278`, `380`, `683-685`, `695` | CLOSED | `memory/embedder.py` API, singleton lifecycle, Chroma-compatible embedding function, `MemoryManager`/Chroma consumption, prewarm budget, and singleton tests are specified. |
| 7 | `278`, `287-291`, `379`, `448-482`, `574`, `685` | CLOSED | `InventorySummary` owner and registry contract cover path/collection, cursor/count, cache key, invalidation, privacy gates, UNKNOWN fallback, SQLite WAL, Chroma, file-backed, and bounded-private-reader mechanics. |
| 8 | `206-211`, `385`, `670`, `686`, `696` | STILL OPEN | Renderer owner and mismatch behavior are named, but the audit metadata contract is still not concrete enough: v1.2 does not define payload fields for `audit_assistant_text` / `self_claim_audit`. |
| 9 | `484-498`, `634-636`, `673-675`, `688`, `697` | CLOSED | Closed refusal reasons, fail-closed downstream behavior, audit-safe refusal serialization, caller-supplied verdict/source tests, and vocabulary-growth fixture are present. |
| 10 | `358-373`, `436`, `590-592`, `677-678` | STILL OPEN | Repair FSM states and storage key are present, but the required cross-surface concurrent-turn test is missing from the RED anchors. |
| 11 | `303-315`, `606-608`, `689-690`, `698` | CLOSED | `RecallBranchResult` states, bounded executor, source/global deadlines, max branches, cancellation/partial-failure behavior, deterministic merge order, and prompt budget caps are specified. |
| 12 | `336-354`, `638-640`, `699` | CLOSED | `core/dispatcher/external_sources.py` owns fresh execution; per-source timeouts/attempts, global fresh deadline, failure mapping, reserved frontier behavior, and freshness-scoring deferral are specified. |
| 13 | `375-385`, `594-600`, `700` | CLOSED | Concrete owner modules are named for schema, Layer 0, inventory, embedder, Layer 1, readers, Layer 2, external execution, and renderer; producer-causality boundary remains separate. |
| 14 | `278`, `314`, `354`, `684`, `698`, `701`, `703` | STILL OPEN | Warm/cold/prewarm and source-count budget anchors exist, but v1.2 does not require p95 adapter-budget tests against realistic local SQLite/Chroma stores rather than pure mocks. |
| 15 | `560`, `618-620`, `668`, `665`, `735` | CLOSED | “Must not launder” is fixed; `SANDBOX_WITNESSES` points to D15; `core/brain/brain_loop.py:900` is cited; validation language uses witnessed-turn samples rather than unsupported distribution sampling. |

## Still Open

Batch 8 fails at `spec-brief.md:206-211`, `385`, and `696`. v1.2 names `core/dispatcher/provenance_renderer.py`, says it passes audit metadata to `core/safety/self_claim_audit.py`, and requires owner synthesis paths to route through the renderer. That closes module ownership, template ownership, and bypass prevention. It does not define the actual audit payload fields required by the pass-2 brief.

Exact closure criteria for v1.3: add a closed audit metadata contract naming required fields, at minimum `spec_digest`, `composition_hint`, `provenance_framing`, `substrate_sources`, `external_sources`, `inventory_witness`, `source_availability`, `availability_limitations`, rendered block roles, template id, template version/hash, mismatch reason if any, utterance digest, surface, timestamp, and no-raw-private-content rule; name whether each field is passed to `audit_assistant_text`, `self_claim_audit`, or both; add/adjust a RED anchor proving those fields are emitted.

Batch 10 fails at `spec-brief.md:677-678`. v1.2 defines the FSM and storage key at `358-373`, but the RED anchors cover inheritance order plus `NO_PRIOR`, `PRIOR_EXPIRED`, and `CRASH_RECOVERED`; they do not cover the pass-2-required cross-surface concurrent-turn case.

Exact closure criteria for v1.3: add a RED anchor such as `test_repair_fsm_does_not_cross_inherit_between_concurrent_surfaces`, proving two simultaneous conversations/surfaces under the same bond cannot inherit each other’s prior spec and that cache lookup keys include `bond_id`, `surface`, `conversation_id`, and `turn_id`.

Batch 14 fails at `spec-brief.md:684`, `698`, `701`, and `703`. v1.2 covers warm/cold/prewarm budget, slow/failure branch behavior, and full-manifest/source-count budget. But the test plan still describes integration tests with mock substrate and does not require p95 adapter budgets against realistic local SQLite/Chroma stores.

Exact closure criteria for v1.3: add a RED/integration anchor requiring realistic local fixture stores for SQLite and Chroma adapter budget tests, with p95 assertions for representative source counts; distinguish pure unit mocks from adapter-budget tests; require budget telemetry assertions for cold/prewarm, source selection limits, slow branch timeout/cancellation, and full-manifest scoring.

## NITs

None.
