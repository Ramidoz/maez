# Recall-Axis Dispatcher — Codex Engineering Pass-1 Review: Ohm

## Verdict

BLOCK

## Findings

### Blocking
- **B1. Layer 0 cold budget includes unowned encoder/model load cost**
  - Evidence: v1.1 says the embedding model is currently loaded inside Chroma and mandates a new shared `memory/embedder.py` singleton to avoid duplicate 160MB loads (§4, lines 198–203). Layer 0 then uses that MiniLM ranking during spec construction (§5, line 253), while D13 requires Layer 0 to complete within ≤50ms warm / ≤150ms cold (§7, lines 446–448). R#18 tests only the warm budget (§9, line 498).
  - Engineering consequence: if “cold” includes first encoder construction / ONNX session initialization, ≤150ms is not a credible implementation contract. If it excludes that work, v1.1 does not say so, so the first owner turn can silently pay model-init latency or duplicate Chroma + dispatcher encoder memory.
  - Closure criterion: v1.2 must define encoder lifecycle and “cold” precisely: either prewarm MiniLM at service readiness and measure Layer 0 cold after encoder initialization, or set a separate startup/prewarm budget. It must require a cold-path metric/test and fail if dispatcher and Chroma instantiate separate encoders.

- **B2. v1 “must include” Layer 1 axes that are reserved or unavailable**
  - Evidence: Layer 1 v1 “must include” `LIVED_GRAPH` and `CROSS_SURFACE_OWNER_TURNS` (§5, lines 268–280), but `LIVED_GRAPH` is explicitly dependent on G11 (§5, line 274; §6, line 309), G9/G11 are separate backlog items (§8, line 470), and R#14 says graph-assisted routing is reserved until traversal exists (§9, line 494). `CROSS_SURFACE_OWNER_TURNS` is not present in the `SubstrateSource` enum (§6, lines 299–315).
  - Engineering consequence: an implementer cannot honestly satisfy v1 fan-out. They must either create placeholder branches that count as routes, fan out to unsupported readers, or silently map a non-enum source. That makes D12’s concurrency/partial-failure behavior untestable against real sources.
  - Closure criterion: v1.2 must split “implemented v1 routes” from “reserved labels.” G9/G11-dependent routes must return explicit `RESERVED_UNAVAILABLE` / empty-reason results without fan-out until their reader APIs exist. `CROSS_SURFACE_OWNER_TURNS` must either become a closed enum value with a reader contract or be removed from the v1 route list.

### Major
- **M1. Per-branch timeout policy has no numbers, total deadline, or cancellation semantics**
  - Evidence: v1.1 says Layer 1 uses per-branch timeout and partial failure (§5, line 266; D12, lines 442–444), and D5 says timeout is an empty-result reason (§7, line 410). R#23/R#24 test concurrency and partial failure but not timeout values or cancellation (§9, lines 503–504).
  - Engineering consequence: every adapter can choose different timeouts, slow branches can keep running after the answer path moves on, and reply latency has no global upper bound. Concurrent fan-out can still exhaust a thread pool or event loop under load.
  - Closure criterion: v1.2 must specify per-source timeouts, a global Layer 1 deadline, max parallel branches, executor model, cancellation behavior, and the result shape for timeout with `elapsed_ms`.

- **M2. `InventorySummary` invalidation is underspecified across heterogeneous stores**
  - Evidence: Layer 0 must consult inventory summaries and distinguish presence / absence / UNKNOWN (§5, lines 245, 252; D2, lines 390–396), with cache invalidated by writes/mtime and no live `COUNT(*)` per reply (D13, line 448).
  - Engineering consequence: mtime is not a reliable uniform cursor for SQLite WAL, Chroma stores, local files, and bounded private readers. Without a source-by-source anchor table, Layer 0 either does slow live reads or emits stale presence/absence verdicts.
  - Closure criterion: v1.2 must provide a source inventory table: store path, cheap summary query, last-write cursor, writer invalidation hook, UNKNOWN fallback, and privacy gate for private-thought inventory.

- **M3. External fetch execution has no latency/error budget**
  - Evidence: decision-first topology says Layer 0 emits spec, Layer 1 recalls, then fetch happens (§5, line 221). External sources include `WEB_SEARCH`, `LIVE_REDDIT`, `FETCH_URL`, `ARXIV_OR_PAPERCLIP`, `FRONTIER_CONSULT` (§6, lines 316–326). `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` exists for failed fresh fetch (§6, line 346), but no execution budget is defined.
  - Engineering consequence: the original failure mode can recur as a bounded-memory dispatcher followed by unbounded or repeated external fetch attempts. There is no contract for when to stop and return substrate context with fresh-unavailable framing.
  - Closure criterion: v1.2 must define external-source owner, per-source timeout, max attempts, global fresh deadline, and error mapping into `FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT`.

- **M4. Layer 1 fan-out cost claim is too optimistic for the declared route set**
  - Evidence: v1.1 estimates concurrent fan-out as approximately max(branch) ≈80ms for 4 sources (§5, line 266), but v1 route list names 10 axes (§5, lines 268–280). The RED suite runtime estimate is broad and mock-shaped (§9, line 506).
  - Engineering consequence: the contract can pass on mocks while real Chroma/SQLite/private-reader branches blow the owner-facing latency budget. More sources also mean more recall blocks, serialization, and prompt-assembly cost.
  - Closure criterion: v1.2 must define source-selection limits, max branches per turn, max recall blocks/chars per source, and p95 adapter budgets using realistic local stores.

### Minor
- **Mi1. Layer 2 state retention lacks cleanup and sizing policy**
  - Evidence: Layer 2 uses `last_spec_by_bond_id` with TTL ~5min plus a single-row `dispatcher_last_spec` crash-recovery table (§5, line 283).
  - Engineering consequence: stale inherited specs or unbounded in-memory key growth are possible in long-running service use.
  - Closure criterion: v1.2 should specify keying, cleanup cadence, max entries, persisted schema, and when prior specs are invalidated.

- **Mi2. Budget tests do not cover the cold path or timeout path**
  - Evidence: R#18 covers warm Layer 0 only (§9, line 498); R#23/R#24 cover concurrency and partial failure without explicit slow-branch timeout assertions (§9, lines 503–504).
  - Engineering consequence: the most expensive paths can regress while the named RED anchors still pass.
  - Closure criterion: add cold/prewarm verification, slow-branch timeout tests, cancellation tests, and budget telemetry assertions.

- **Mi3. `FRONTIER_CONSULT` is still operationally ambiguous**
  - Evidence: `FRONTIER_CONSULT` is in `ExternalSource` (§6, line 324), but is “provenance-bearing only” and not a new consultation mechanism (§6, line 326; D10, line 436). Q10.7 remains open (§10, line 520).
  - Engineering consequence: external-source execution code must special-case a non-executable source or risk reporting a blocked capability as a failed fetch.
  - Closure criterion: mark it explicitly non-executable/reserved in v1 and exclude it from execution fan-out.

### Nit
- **N1. `SANDBOX_WITNESSES` cross-reference points at the wrong invariant**
  - Evidence: `SANDBOX_WITNESSES` says no-authorization is enforced by D12 and template policy (§6, line 314), but D12 is Layer 1 concurrent fan-out (§7, lines 442–444). D15 is the read-only authorization invariant (§7, lines 454–456).
  - Engineering consequence: minor reader confusion during implementation.
  - Closure criterion: change the cross-reference from D12 to D15.

## Summary

The direction is buildable, but v1.1 is not yet an implementable Ohm contract. It names the right concerns, then leaves the costly parts undefined: encoder cold-start, real route availability, timeouts, fan-out caps, inventory invalidation, and external fetch budgets. Fold those into v1.2 and this likely drops from BLOCK to RATIFY-WITH-AMENDMENTS.
