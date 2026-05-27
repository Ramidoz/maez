# Recall-Axis Dispatcher — Codex Arendt Pass-2 Review

## Verdict

STILL OPEN

## Per-Batch Closure Table

| Batch | v1.2 change cited (line/section) | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | §4 lines 153-180; D16 lines 622-624; R#25 line 691 | CLOSED | `CompositionSpec` now carries `inventory_witness`, `source_availability`, `availability_limitations`, `freshness_window`, and `trust_scope_union`; closed witness states and availability limitations are defined. |
| 2 | Layer 1 lines 316-335; external lines 348-354; vocab lines 397-424; D17 lines 626-628; R#26/R#14 lines 680, 692 | CLOSED | Executable and reserved labels are separated; `CROSS_SURFACE_OWNER_TURNS` ambiguity is removed; `LIVED_GRAPH`, `WEB_FAST_TURNS`, and `FRONTIER_CONSULT` cannot execute in v1. |
| 3 | Layer 0 lines 274-280; D1 lines 548-550; R#4/R#27 lines 668, 693 | CLOSED | In-scope owner ingresses are enumerated and must hit Layer 0 before tool/fetch/recall/render; excluded ingresses must become visible availability limitations; legacy JARVIS path is fully qualified in R#4. |
| 4 | Scoring lines 234-243; D18 lines 630-632; R#28 line 694 | CLOSED | v1.2 defines max-prototype scoring, normalization rule, thresholds, precedence order, tie/multi-match behavior, and no-match fallback. |
| 5 | Archetype manifest/replay lines 500-526; R#1a line 665 | CLOSED | Manifest is versioned with prototype/class/tag/hash requirements; replay corpus is ≥30 witnessed turns with class coverage, negatives, sentinels, full `CompositionSpec`, false-hybrid ceiling, and amendment trigger. |
| 6 | Encoder lines 217-232; latency/prewarm line 278; module map line 380; R#17/R#29 lines 683, 695 | CLOSED | Shared `MiniLMEncoder` API, Chroma adapter, contract validation, lifecycle/prewarm budget, and singleton tests are specified. |
| 7 | Inventory lines 287-291; D5 lines 572-574; D13 lines 610-612; R#19 line 685 | CLOSED | `core/dispatcher/inventory.py` owns per-source registry, invalidation, UNKNOWN fallback, privacy gate, WAL/Chroma/file-backed handling; Layer 0 live counts are forbidden. |
| 8 | Renderer lines 206-213; D4 lines 566-570; module map line 385; R#30/R#20 lines 686, 696 | CLOSED | `core/dispatcher/provenance_renderer.py` is named as owner, all owner synthesis paths must route through it, closed template behavior and mismatch refusal are tested. |
| 9 | Refusal vocab lines 484-498; D6 lines 576-584; D19 lines 634-636; R#9/R#10/R#31 lines 673-674, 697 | CLOSED | Closed refusal reasons cover caller-supplied verdict/source fields; refusal fails closed before downstream execution and serializes audit-safe evidence. |
| 10 | Layer order lines 261-266; repair FSM lines 356-373; D8 lines 590-592; R#12/R#12a lines 677-678 | STILL OPEN | FSM states exist, but prior-spec storage is under-keyed relative to pass-2 criteria: cache key omits timestamp and TTL, and tests do not explicitly cover cross-surface concurrent turns. |
| 11 | Fan-out lines 303-314; D12 lines 606-608; R#32 line 698 | STILL OPEN | Result states, timeouts, deadline, max parallelism, merge order, and prompt budgets are specified, but cancellation behavior is not defined. |
| 12 | External execution lines 336-354; D20 lines 638-640; R#33 line 699 | CLOSED | Owner module, per-source timeouts/attempts, global fresh deadline, reserved frontier behavior, failure-to-framing mapping, and freshness deferral are specified. |
| 13 | Module map lines 375-385; scope boundary lines 12-16; D9 lines 594-596 | CLOSED | Concrete owner modules are named for schema, Layer 0, inventory, embedder, Layer 1/readers, Layer 2, external execution, and provenance rendering; producer-causality remains separate. |
| 14 | Latency lines 278, 314; D13 lines 610-612; R#18/R#32/R#35 lines 684, 698, 701; runtime split line 703 | STILL OPEN | Warm/cold/prewarm and full-manifest budget tests are present, but cancellation telemetry and realistic local-store p95 adapter budgets are not required; line 703 explicitly leans on mock substrate integration tests. |
| 15 | D2 line 560; `SANDBOX_WITNESSES` lines 410, 618-620; R#4 line 668; replay wording lines 665, 735 | CLOSED | Cross-reference/naming nits are folded: “must not launder,” D15 witness reference, qualified brain-loop path, and witnessed-turn sample framing. |

## Still Open

Batch 10 fails at v1.2 lines 358 and 373. Line 358 names TTL, but line 373 keys prior spec storage only by `(bond_id, surface, conversation_id, turn_id)` and persists timestamp separately; it does not meet the pass-2 closure criterion requiring storage keyed by bond id, surface, turn/conversation id, timestamp, and TTL. Lines 677-678 test repair ordering and some FSM states, but do not explicitly test cross-surface concurrent turns. v1.3 closure criteria: include timestamp/TTL in the storage identity or explicitly define an equivalent collision-proof uniqueness model, and add a named test for cross-surface concurrent repair turns.

Batch 11 fails at v1.2 lines 303-314 and 606-608. They define concurrent fan-out, deadlines, max parallelism, failure isolation, and merge order, but do not define cancellation behavior when a branch exceeds per-source or global deadline. v1.3 closure criteria: state whether timed-out branches are cancelled, abandoned, joined later, or quarantined; define cleanup/audit behavior; add a test asserting cancellation/abandonment semantics.

Batch 14 fails at v1.2 lines 684, 698, 701, and 703. The tests cover warm/cold Layer 0, slow+failed branch deadline/order, and full manifest/source count, but not cancellation telemetry; line 703’s “mock substrate” integration split does not satisfy the requirement for p95 adapter budgets using realistic local stores rather than pure mocks. v1.3 closure criteria: add realistic local-store adapter budget tests with p95 assertions, plus timeout cancellation telemetry assertions.

## NITs

None.
