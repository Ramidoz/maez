# Recall-Axis Dispatcher — Codex Peirce Pass-2 Review

## Verdict

STILL OPEN

## Per-Batch Closure Table

| Batch | v1.2 change cited (line/section) | Verdict | Evidence |
| --- | --- | --- | --- |
| Batch 1 | §4 lines 153-179; D16 lines 622-624; R#25 line 691 | CLOSED | `CompositionSpec` now carries `inventory_witness`, `source_availability`, `availability_limitations`, `freshness_window`, and `trust_scope_union`; UNKNOWN is non-presence; serialization/render/audit round-trip is anchored. |
| Batch 2 | Layer 1 lines 316-334; vocab lines 402-424; D17 lines 626-628; R#14/R#26 lines 680, 692 | CLOSED | Executable vs reserved labels are split; `CROSS_SURFACE_OWNER_TURNS` ambiguity is removed; G9/G11/G3 dependencies return unavailable rather than execute. |
| Batch 3 | Layer 0 lines 274-280; D1 lines 548-550; R#4/R#27 lines 668, 693 | CLOSED | Owner ingresses are enumerated; dispatcher-before-tool/recall is required; legacy gate path is fully qualified. |
| Batch 4 | §4 lines 234-244; D18 lines 630-632; R#28 line 694 | CLOSED | Prototype scoring, thresholds, precedence, no-match fallback, and deterministic tie behavior are specified. |
| Batch 5 | Archetype manifest/replay lines 502-526; R#1a line 665 | CLOSED | Manifest is versioned with hash/fixture requirements; replay validates full `CompositionSpec`; witnessed-turn sample language avoids distribution overclaim. |
| Batch 6 | Encoder seam lines 217-232; Layer 0 budget line 278; D13 line 612; R#17/R#29 lines 683, 695 | CLOSED | Shared `memory/embedder.py` API, singleton, Chroma consumption, contract validation, prewarm/cold semantics, and duplicate-instantiation test are specified. |
| Batch 7 | Inventory registry line 291; D5 line 574; D16 lines 622-624; R#19 line 685 | CLOSED | `InventorySummary` owner and per-source registry contract exist; Layer 0 cannot live-count; UNKNOWN/stale state is visible in spec/rendering. |
| Batch 8 | Provenance owner lines 206-213; D4 lines 568-570; R#6/R#8/R#20/R#30 lines 670, 672, 686, 696 | STILL OPEN | Owner module, closed templates, routing-through-renderer, and mismatch refusal are present, but audit payload fields for `audit_assistant_text` / `self_claim_audit` are only named generically as “audit metadata,” not specified. |
| Batch 9 | Refusal reasons lines 484-499; D6 lines 576-585; D11 lines 602-604; D19 lines 634-636; R#9/R#10/R#16/R#22/R#31 lines 673-674, 682, 688, 697 | CLOSED | Peirce closure holds: closed refusal reasons exist; caller-supplied verdict/source fields are refused; incoherent product-table pairs refuse; refusal stops downstream execution; RED anchors test behavior, not vocabulary presence only. |
| Batch 10 | Layer order lines 261-266; Layer 2 FSM lines 356-373; CompositionHint line 436; R#12/R#12a lines 677-678 | CLOSED | Repair is a Layer 2 modifier, not a hint; FSM states, cache key, persistence, cleanup, crash validation, and tests are specified. |
| Batch 11 | Layer 1 result/budget lines 303-314; D12 line 608; R#23/R#24/R#32 lines 689-690, 698 | CLOSED | Branch result states, deadlines, executor bounds, cancellation implication, stable merge ordering, and slow/error tests are specified. |
| Batch 12 | External execution lines 336-354; D20 line 640; R#33 line 699 | CLOSED | Owner module, per-source timeouts/attempts, global fresh deadline, error mapping, and freshness deferral are specified. |
| Batch 13 | Module map lines 375-385; D9 lines 594-596; R#34 line 700 | CLOSED | Concrete module paths are declared; dispatcher/producer-causality boundary is preserved; stale “likely” paths are forbidden. |
| Batch 14 | Budget lines 278, 314, 612; R#18/R#35 lines 684, 701; RED split line 703 | STILL OPEN | Warm/cold/prewarm and full-manifest anchors exist, but p95 adapter budgets against realistic local stores are not specified; line 703 still frames integration around mock substrate fixtures. |
| Batch 15 | Lines 560, 620, 668, 665 | CLOSED | “must not launder” fixed; `SANDBOX_WITNESSES` is D15; `core/brain/brain_loop.py:900` is cited; witnessed-turn sample language is used. |

## Still Open

Batch 8 fails at v1.2 lines 206-213 and 385. These lines name `core/dispatcher/provenance_renderer.py` and say audit metadata flows to `self_claim_audit.py`, but they do not define the actual audit payload fields required by pass-2 closure.

Closure criteria for v1.3: specify the audit payload contract passed to `audit_assistant_text` / `core/safety/self_claim_audit.py`, including at minimum spec digest/schema version, provenance framing, composition hint, source role map, availability limitations, template id, rendered block roles, and mismatch/refusal reason when applicable.

Batch 14 fails at v1.2 lines 684, 701, and especially 703. The tests cover warm/cold budget and full manifest/source registry, but line 703 still relies on mock substrate integration fixtures and does not require p95 adapter budgets on realistic local stores.

Closure criteria for v1.3: add explicit p95 adapter budget requirements using realistic local SQLite/Chroma/file-backed source fixtures, plus telemetry assertions for source-selection limits, slow-branch timeout, cancellation, and total prompt-budget contribution.

## NITs

None.
