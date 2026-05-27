# Recall-Axis Dispatcher — Codex Engineering Pass-1 Review: Arendt

## Verdict

BLOCK

## Findings

### Blocking
- **B1. Full JARVIS replacement lacks an exhaustive interception contract**
  - Evidence: D1 says “Layer 0 must emit a `CompositionSpec` before JARVIS/tool dispatch or substrate recall” and “fully replaces the legacy `_should_run_jarvis_loop` gate” (`spec-brief.md:386-389`), but R#4 only names the `brain_loop.py:900` short-circuit (`spec-brief.md:483`).
  - Engineering consequence: an implementation can pass R#4 while legacy paths still bypass Layer 0: duplicated Telegram wrapper paths, direct `needs_web_search()` branches in daemon/voice/web surfaces, pending-offer web-search firing, and action-engine `web_search`/`fetch_url` paths. The Reddit-class failure can recur through a different ingress.
  - Closure criterion: v1.2 must enumerate every reply-time ingress and legacy routing path, then require dispatcher-before-tool/dispatcher-before-recall tests for each, or explicitly mark a path out of v1 with a visible availability limitation.

- **B2. v1 “must include” source set conflicts with reserved/unavailable sources**
  - Evidence: Layer 1 says v1 “must include at least” `LIVED_GRAPH` and `CROSS_SURFACE_OWNER_TURNS` (`spec-brief.md:268-279`), while the enum says `LIVED_GRAPH` only works “once G11 traversal API exists” and `WEB_FAST_TURNS` only works “once trust-scope unification is available” (`spec-brief.md:303-314`). The dependency map says G9/G11 closure is separate (`spec-brief.md:470`).
  - Engineering consequence: the closed enum and fan-out executor are asked to route to sources that are either unavailable or not even named consistently in the enum. Builders cannot tell whether these are active branches, reserved enum values, or explicit unavailable results.
  - Closure criterion: v1.2 must split `ACTIVE_V1` sources from `RESERVED` sources, align `CROSS_SURFACE_OWNER_TURNS` vs `WEB_FAST_TURNS`, and require reserved branches to return typed unavailable results rather than entering normal fan-out.

### Major
- **M1. `CompositionSpec` is declared as four fields but later requires undeclared state**
  - Evidence: §4 declares only `substrate_sources`, `external_sources`, `composition_hint`, and `provenance_framing` (`spec-brief.md:152-159`) and commits to those as v1 mandatory structure (`spec-brief.md:162`). D2 then requires `inventory_witness: UNKNOWN` and `no_relevant_substrate` markers (`spec-brief.md:392-397`); D7 requires visible scope limitations (`spec-brief.md:422-424`).
  - Engineering consequence: UNKNOWN inventory, absence, trust-scope limitation, and source availability cannot be serialized, inherited, audited, or rendered without ad hoc side channels.
  - Closure criterion: v1.2 must add typed metadata fields, likely `inventory_witness`, `availability_limitations`, and `trust_scope_policy`, or explicitly define where those states live.

- **M2. Repair-turn state transition is under-specified**
  - Evidence: repair turns are ordered `Layer 0 → Layer 2 → Layer 1` (`spec-brief.md:228-233`), while Layer 2 depends on `last_spec_by_bond_id`, TTL, and crash recovery state (`spec-brief.md:281-289`).
  - Engineering consequence: first-turn “are you sure?”, stale prior specs, cross-surface concurrent turns, and crash recovery can inherit the wrong topic or source set.
  - Closure criterion: v1.2 must define a finite state machine for `NO_PRIOR`, `PRIOR_VALID`, `PRIOR_EXPIRED`, and `CRASH_RECOVERED`, keyed by at least bond plus surface/conversation, with expiry and collision behavior.

- **M3. Fan-out concurrency lacks a result and merge contract**
  - Evidence: D12 requires concurrent fan-out with per-branch timeout and explicit empty reasons (`spec-brief.md:442-444`), but Layer 1 output is only “recall blocks” (`spec-brief.md:256-266`).
  - Engineering consequence: timeout, branch error, reserved source, and true empty result can collapse into the same shape; prompt order can become nondeterministic; thread-safety choices for SQLite/Chroma are left to implementation guesswork.
  - Closure criterion: v1.2 must define `RecallBranchResult` states, per-source/default timeout budgets, cancellation behavior, deterministic merge ordering, and tests for slow plus failed branches.

- **M4. Cross-surface scope is both required and deferred**
  - Evidence: D7 is “non-regression only” (`spec-brief.md:422-424`), `WEB_FAST_TURNS` is gated on future trust-scope unification (`spec-brief.md:306`), and Q10.5 leaves cross-surface union open (`spec-brief.md:518`).
  - Engineering consequence: v1 can either silently omit owner web turns while claiming cross-surface composition, or over-unify owner/guest scopes to satisfy the dispatcher.
  - Closure criterion: v1.2 must choose: reserve web fast-turn recall with explicit unavailable markers, or define the trust-scope union API and owner-auth constraints for v1.

### Minor
- **Mi1. R#23 tests mechanism, not the concurrency guarantee**
  - Evidence: R#23 allows “asyncio.gather or ThreadPoolExecutor” (`spec-brief.md:503`).
  - Engineering consequence: a test can pass while wall-clock behavior, timeout isolation, and deterministic partial results remain unproven.
  - Closure criterion: add a slow-branch plus failed-branch fixture that proves max-branch latency and stable output ordering.

- **Mi2. Layer 0 cold latency is ambiguous**
  - Evidence: D13 requires ≤50ms warm / ≤150ms cold (`spec-brief.md:446-448`) while §4 requires a shared MiniLM singleton (`spec-brief.md:198-203`).
  - Engineering consequence: “cold” could mean cache cold, process cold, or encoder cold; the latter likely blows the budget.
  - Closure criterion: define cold/warm states precisely and require encoder prewarm if model-load time is excluded.

- **Mi3. Intra-Maez location test is ceremonial as written**
  - Evidence: R#21 says concrete test is “refined during implementation” (`spec-brief.md:501`).
  - Engineering consequence: the organ-location invariant can become a vocabulary assertion rather than a boundary test.
  - Closure criterion: require a concrete no-external-service test: no socket/subprocess/RPC path for Layer 0 construction.

### Nit
- **N1. Typo in D2**
  - Evidence: “D2 must not laundering” (`spec-brief.md:398`).
  - Engineering consequence: none.
  - Closure criterion: change to “must not launder.”

- **N2. `SANDBOX_WITNESSES` cites the wrong enforcement invariant**
  - Evidence: enum note says no-authorization is enforced by “D12 below” (`spec-brief.md:314`), but D12 is concurrency; D15 is the sandbox read-only invariant (`spec-brief.md:454-456`).
  - Engineering consequence: future implementers may attach the enforcement to fan-out rather than authorization policy.
  - Closure criterion: cite D15 and assembly policy instead of D12.

## Summary

The direction is buildable, but v1.1 is not yet a safe implementation contract. The two hard blockers are legacy bypass closure and the active-vs-reserved source contradiction. Fix those, then tighten state metadata, repair transitions, and fan-out result semantics; after that this becomes an implementable dispatcher slice rather than a strong design brief with trapdoors.
