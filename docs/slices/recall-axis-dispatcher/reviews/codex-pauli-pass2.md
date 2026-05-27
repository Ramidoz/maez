# Recall-Axis Dispatcher — Codex Pauli Pass-2 Review

## Verdict

STILL OPEN

## Per-Batch Closure Table

| Batch | v1.2 change cited (line/section) | Verdict | Evidence |
| --- | --- | --- | --- |
| Batch 1 | spec v1.2 lines 153-180, 622-624, 691 | CLOSED | `CompositionSpec` now carries `inventory_witness`, `source_availability`, `availability_limitations`, freshness, and trust-scope fields; closed inventory values include present/absent/unknown/mixed; serialization/render/audit round-trip test is added. |
| Batch 2 | lines 329-335, 402-424, 626-628, 692 | CLOSED | Executable vs reserved labels are split; `CROSS_SURFACE_OWNER_TURNS` ambiguity is removed; `LIVED_GRAPH`, `WEB_FAST_TURNS`, and `FRONTIER_CONSULT` return `RESERVED_UNAVAILABLE`. |
| Batch 3 | lines 280, 548-550, 668, 693 | CLOSED | Owner ingresses are enumerated and Layer 0 is required before tool/fetch/recall/render; test covers Telegram, web, brain loop, daemon, continuation, pending-offer, and enabled voice/electron paths. |
| Batch 4 | lines 234-242, 630-632, 694 | STILL OPEN | v1.2 declares thresholds and max-prototype scoring, but only says “deterministic tie handling”; it does not define the actual tie-resolution rule or stable ordering. |
| Batch 5 | lines 500-526, 665 | CLOSED | Versioned manifest requirements, class coverage, sentinel pairs, full `CompositionSpec` fixtures, negative cases, false-hybrid ceiling, and amendment triggers are specified. |
| Batch 6 | lines 217-232, 278, 683, 695 | CLOSED | `memory/embedder.py` API, singleton, Chroma-compatible surface, contract validation, prewarm/cold budget split, and shared-instantiation test are specified. |
| Batch 7 | lines 287, 291, 572-574, 685 | CLOSED | `core/dispatcher/inventory.py` owns per-source registry, cursor/cache/invalidation/privacy handling, UNKNOWN fallback, and no live per-reply `COUNT(*)`. |
| Batch 8 | lines 206-213, 568-570, 696 | STILL OPEN | v1.2 names `provenance_renderer.py` and says all owner synthesis paths must use it, but does not define the concrete audit payload fields for `audit_assistant_text` / `self_claim_audit`, nor enumerate existing owner synthesis surfaces tightly enough to prevent bypass by scattered prompt builders. |
| Batch 9 | lines 484-498, 634-636, 673-675, 697 | CLOSED | Closed refusal reasons, fail-closed downstream stop, audit-safe refusal event, caller-supplied verdict/source tests, and vocabulary-growth test anchors are present. |
| Batch 10 | lines 366-373, 436, 677-678 | STILL OPEN | FSM states and storage are specified, but required test coverage for cross-surface concurrent repair turns is not explicitly anchored. |
| Batch 11 | lines 303-314, 606-608, 689-690, 698 | CLOSED | Closed `RecallBranchResult` states, bounded executor, per-branch/global deadlines, deterministic merge order, prompt budget caps, and slow/error branch tests are specified. |
| Batch 12 | lines 336-354, 638-640, 699 | CLOSED | `external_sources.py` owns fresh execution; per-source timeouts/attempts/global deadline/error mapping are specified; freshness scoring is explicitly deferred. |
| Batch 13 | lines 375-385, 594-596, 700 | CLOSED | Concrete module map covers schema, Layer 0, inventory, embedder, Layer 1/readers, Layer 2, external sources, and provenance renderer; producer-causality write authority stays out of scope. |
| Batch 14 | lines 278, 314, 684-685, 698, 701, 703 | STILL OPEN | Warm/cold and timeout tests exist, but v1.2 does not require p95 adapter budgets against realistic local stores; line 703 instead frames integration tests around mock substrate. |
| Batch 15 | lines 560, 620, 668, 735 | CLOSED | “must not launder” is fixed; `SANDBOX_WITNESSES` points to D15; `core/brain/brain_loop.py:900` is cited; witnessed-turn language replaces distribution-sampling overclaim. |

## Still Open

Batch 4 fails at lines 238 and 632. The thresholds are declared, but “deterministic tie handling” is not an executable rule. v1.3 closure: define exact tie behavior, for example stable class ordering after `multi_match_delta`, explicit multi-match composition behavior, and the fallback when tied classes imply incompatible source/framing choices.

Batch 8 fails at lines 206-211 and 570. The renderer owner is named, but the audit metadata contract remains generic and existing prompt-builder bypass surfaces are not enumerated. v1.3 closure: list the owner synthesis surfaces/path set that must call `core/dispatcher/provenance_renderer.py`, and define concrete audit fields passed into `audit_assistant_text` / `self_claim_audit` such as spec digest, provenance framing, source roles, availability limitations, template id, and mismatch/refusal reason.

Batch 10 fails at lines 373 and 677-678. The cache key includes surface/conversation, but the RED anchor does not prove cross-surface concurrent repair isolation. v1.3 closure: add an explicit test anchor for simultaneous Telegram/web repair turns proving prior specs cannot cross surfaces or conversations.

Batch 14 fails at lines 684-685, 698, 701, and especially 703. The budget suite covers Layer 0 and branch timeout shape, but not p95 adapter budgets using realistic local stores. v1.3 closure: require p95 budget assertions for representative SQLite/WAL, Chroma, file-backed, and bounded-reader adapters, with source-selection limits tested against the full manifest/registry rather than pure mocks.

## NITs

None.
