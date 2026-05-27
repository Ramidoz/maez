# Recall-Axis Dispatcher — Codex Ohm Pass-2 Review

## Verdict

STILL OPEN

## Per-Batch Closure Table

| Batch | v1.2 change cited (line/section) | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | `CompositionSpec` fields §4 lines 153-164, 167-179; D16 lines 622-624; R#25 lines 691 | CLOSED | Availability is now schema-bearing: `inventory_witness`, `source_availability`, `availability_limitations`, freshness, trust-scope. D16 requires population before serialization/render/audit. |
| 2 | Layer 1 source split lines 316-334; `SubstrateSource` lines 397-412; `ExternalSource` lines 416-424; D17 lines 626-628; R#14/R#26 lines 680, 692 | CLOSED | Executable vs reserved sources are explicit; `CROSS_SURFACE_OWNER_TURNS` ambiguity is removed; reserved labels return unavailable and are tested. |
| 3 | Owner ingress coverage lines 280, 548-550; R#4/R#27 lines 668, 693 | CLOSED | v1.2 enumerates Telegram, web, brain-loop, daemon, continuation, pending-offer search, and enabled voice/electron ingress; requires Layer 0 before tool/fetch/recall/render. |
| 4 | Scoring calculus lines 234-242; D18 lines 630-632; R#28 line 694 | STILL OPEN | Threshold constants and fallback are present, but tie behavior is named only as “deterministic tie handling,” not defined. |
| 5 | Archetype manifest lines 500-517; replay corpus lines 518-526; R#1a lines 664-665 | CLOSED | Manifest requirements include prototype text, class ids, empirical/proposed tags, reserved/executable state, fixture/hash; replay corpus is 30 turns with negative cases and full `CompositionSpec` fixtures. |
| 6 | Encoder seam/API lines 219-232; Layer 0/prewarm budget line 278; D13 lines 610-612; R#17/R#29 lines 683, 695 | CLOSED | Shared singleton API, Chroma-compatible surface, contract validation, Chroma/dispatcher shared ownership, and separate prewarm budget are specified. |
| 7 | Inventory registry line 291; D5 lines 572-574; D13 lines 610-612; R#19 line 685 | CLOSED | `core/dispatcher/inventory.py` owns per-source registry, cursor/cache/invalidation/privacy gates, UNKNOWN fallback; Layer 0 cannot run live counts. |
| 8 | Renderer owner lines 206-213; D4 lines 566-570; module map line 385; R#30 line 696 | CLOSED | `core/dispatcher/provenance_renderer.py` owns templates, limitation phrasing, audit metadata, mismatch refusal/event policy, and all owner synthesis surfaces. |
| 9 | Refusal reasons lines 484-498; D6 lines 576-584; D19 lines 634-636; R#9/R#31 lines 673, 697 | CLOSED | Closed refusal reasons exist; caller-supplied verdict/source fields refuse; refusal stops downstream tool/fetch/recall/render and audits safely. |
| 10 | Layer order lines 261-266; repair FSM lines 356-373; `CompositionHint` repair modifier lines 426-436; R#12/R#12a lines 677-678 | CLOSED | Repair is a Layer 2 modifier, not a hint; finite states, keying, TTL, crash recovery validation, cleanup, and tests are present. |
| 11 | Fan-out lines 303-314; D12 lines 606-608; R#32 line 698 | STILL OPEN | Deadlines and merge order are specified, but cancellation behavior is not. “Global deadline ≤ 200ms before prompt-assembly fallback” does not say whether in-flight branches are cancelled, drained, detached, or allowed to mutate late. |
| 12 | External owner/budget lines 336-354; D20 lines 638-640; R#33 line 699 | STILL OPEN | Owner, timeouts, max attempts, and global deadline exist. Error mapping and stop conditions are still too coarse: only Reddit bot-block is specifically mapped, while web/fetch/arxiv/frontier failure classes are not enumerated. |
| 13 | Module map lines 375-385; scope boundary lines 12-16; D9 lines 594-596 | CLOSED | Concrete paths are named for schema, Layer 0, inventory, embedder, Layer 1, readers, Layer 2, external sources, and renderer; producer-causality remains separate. |
| 14 | Layer 0 budget line 278; D13 lines 610-612; R#18/R#35 lines 684, 701; RED suite estimate line 703 | STILL OPEN | Budget values exist, but warm/cold definitions are not precise enough, cancellation telemetry is absent, and the test-cost section says integration tests use “mock substrate,” while the closure criterion requires realistic local stores and p95 adapter budgets. |
| 15 | D2 grammar fix line 560; D15 sandbox witness reference lines 618-620; brain-loop path line 668; witnessed-turn wording lines 664-665 | CLOSED | The listed nits/cross-reference fixes are folded. |

## Still Open

Batch 4 fails at lines 630-632 and 694. These lines require deterministic tie handling and a test, but do not define the tie rule. v1.3 closure: state the exact tie behavior, e.g. multi-match when scores are within `multi_match_delta`, otherwise stable ordering by class id or manifest order, and state how ties affect emitted `CompositionHint`, `ProvenanceFraming`, and source set.

Batch 11 fails at lines 303-314, 606-608, and 698. These define concurrency, timeouts, global deadline, and stable merge, but not cancellation behavior. v1.3 closure: specify what happens at per-branch timeout and global deadline: cancel futures/tasks, ignore late returns by generation id, drain with bounded grace, and assert no late branch can mutate the merged recall after prompt fallback.

Batch 12 fails at lines 346-354 and 638-640. These define budgets but not source-specific error mapping/stop conditions beyond Reddit bot-block and generic external failure. v1.3 closure: enumerate failure classes for `WEB_SEARCH`, `LIVE_REDDIT`, `FETCH_URL`, `ARXIV_OR_PAPERCLIP`, and `FRONTIER_CONSULT`; map each to `FRESH_ATTEMPT_FAILED`, `FETCH_BUDGET_EXHAUSTED`, `SOURCE_TIMEOUT`, or `RESERVED_SOURCE_UNAVAILABLE`; define stop conditions for timeout, max attempts, global deadline, empty result, and reserved source.

Batch 14 fails at lines 278, 610-612, 684, 701, and 703. Warm/cold are budgeted but not precisely defined, and the RED suite estimate relies on mock substrate despite the realistic-store criterion. v1.3 closure: define warm vs cold states operationally; add budget telemetry assertions for Layer 0, Layer 1, cancellation, and external fetch; require p95 adapter tests against realistic local SQLite/Chroma/file-backed fixtures with representative source counts, not pure mocks.

## NITs

None.
