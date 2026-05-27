# Claude External-Source Pass 1 — Ohm (Seal / Concurrency / Wiring)

**Verdict:** BLOCKING

## Summary

The brief correctly identifies Option A (sibling external fan-out) and asserts
the right principles in §4 ("same seal discipline as Layer 1: generation id,
deterministic source order, per-branch timeout, global deadline, late results
unable to mutate rendered output"). But the brief stops at asserting those
properties for the external organ *in isolation*. It does not specify how the
two seals compose, how late results are detected when two organs run
concurrently, or how `seal_state` is reconciled across fan-outs. The wiring
diagram in §8 shows a "merge source summaries" box with no contract behind it.

Three further issues are load-bearing for an implementation slice: the brief
never names the recovery-seed bypass (Layer 1 is currently bypassed under
recovery via `brain_loop.py:1262`); the per-branch / global timeout numbers in
§5 are an order of magnitude larger than Layer 1's wired-in budgets (5s/3s/6s
vs 0.8s/1.0s) and the brief does not justify the asymmetry; and the
telemetry vocabulary the brief implicitly demands (`dispatcher_external_*`)
is not enumerated.

These are fixable. None of them require redesigning Option A. They require
making the seal-composition story explicit before code lands.

## Findings

### Finding 1 — Two generation ids, no merge contract

**Severity:** BLOCKING
**Where:** Brief §4 lines 139, 150-156 (`ExternalBranchResult.fanout_generation_id`,
`ExternalFanoutResult.fanout_generation_id`, `sealed_at`); §8 lines 261-265
("merge source summaries"); compare `core/dispatcher/layer1.py:157, 244, 251-264`.

**Observation:** Layer 1 generates a `fanout_generation_id` via
`uuid.uuid4().hex` per `Layer1Fanout.run` invocation. The brief defines
`ExternalFanoutResult.fanout_generation_id` as a sibling field. §8 then says
the two organs "run concurrently" and downstream code "merges source
summaries". Nothing in the brief specifies whether:

(a) substrate and external fan-out share a single `fanout_generation_id`
    minted by the orchestrator (one seal, two physical pipelines), or
(b) each organ mints its own id and the merged record carries both ids
    plus a join-id (two seals, joined later).

Both designs are defensible. (a) makes "late result from any side cannot
mutate this turn" a single, mechanically checkable property tied to a single
id. (b) preserves organ encapsulation but pushes the seal-composition logic
into the merge step — and the brief never describes that merge step. Without
this decision, an implementer will pick by accident and the property in §4
("late results unable to mutate rendered output") becomes a comment, not a
guarantee.

**Recommendation:** Pick one and name it. If (a): the brief should say the
caller in `_run_dispatcher_pipeline` mints a single `fanout_generation_id`
and passes it into both `Layer1Fanout.run(...)` and `ExternalFanout.run(...)`
(which means Layer 1's current "self-mint inside run" needs an injection
point — call it out as a Layer 1 touch). If (b): the brief should define a
`turn_seal_id` (or equivalent) that the renderer stamps, and specify that
late results carrying a stale `fanout_generation_id` for *either* organ are
dropped before rendering. RED test #6 must then exercise the chosen story.

### Finding 2 — `sealed_at` is asserted, not engineered

**Severity:** BLOCKING
**Where:** Brief §4 line 152, §4 line 160; compare `layer1.py:194-242, 244,
346-366`.

**Observation:** §4 lists `sealed_at: float` as a field and §4 line 160 says
"late results unable to mutate rendered output." In `layer1.py`, this is not
a wish — it is engineered by three mechanisms in sequence:

1. The work loop only consumes futures inside the `while pending:` block
   (layer1.py:194-238). Once that loop exits, no future result is read.
2. `executor.shutdown(wait=False, cancel_futures=True)` (layer1.py:242)
   actively cancels in-flight work.
3. Timed-out branches are stamped with `late_result_ignored=True` and
   `cancel_requested=True` (layer1.py:355-366); the rendered output ignores
   any branch whose `status` is not `SUCCESS`.

The brief does not name an analogous mechanism for external fan-out. External
calls go through `core.egress.external_fetch.fetch_text` (brief §2 lines
61-62), which is a *blocking* HTTP call. `Future.cancel()` cannot interrupt
a thread already inside a blocking socket read. So even if the brief copies
Layer 1's executor-shutdown line verbatim, a 5s Reddit timeout that fires at
4.999s can still return a result at 5.001s — and if the merge step reads
that result, the seal is breached.

**Recommendation:** Specify the lateness defense explicitly for external
fan-out. The minimum surface area is:

- A monotonic deadline check inside the merge step that drops any
  `ExternalBranchResult` arriving after `sealed_at`.
- An explicit statement that the renderer reads from the `ExternalFanoutResult`
  produced *before* `sealed_at`, never from a callback fired by the egress
  layer.
- RED test #6 must construct the cross-organ late-arrival case (one substrate
  branch and one external branch with different completion times), not just
  exercise late results within external fan-out.

### Finding 3 — `seal_state` is computed in brain_loop, not the organ

**Severity:** SUGGEST
**Where:** `brain_loop.py:459-461`; brief §4 (`ExternalFanoutResult` has no
`seal_state` field); brief §7 (composition uses `availability_limitations`,
not seal state).

**Observation:** Layer 1's `seal_state` ("clean" | "partial_failure") is not a
field on `Layer1FanoutResult` — it is derived in `brain_loop.py:459-461` from
branch statuses. The brief inherits this surface implicitly (external
limitations map to `availability_limitations`, §7) but does not say whether
external fan-out contributes to a *combined* `seal_state` in the
`dispatcher_layer1_fanout` log line, gets its own `dispatcher_external_fanout
seal_state=...` line, or whether the existing partial_failure label expands
to cover both organs.

The honest answer is probably: each organ emits its own derived seal_state,
and the orchestrator emits a combined turn-level seal label. But the brief
does not say this.

**Recommendation:** Add a sentence to §4 or §8 specifying that
`seal_state` is derived per-organ from branch statuses (matching Layer 1's
current pattern) and that the brain-loop emits a turn-level
`dispatcher_turn_seal_state` (or names the existing telemetry it extends).
See Finding 5 for the telemetry vocabulary side of this.

### Finding 4 — Timeout budgets diverge from Layer 1 without justification

**Severity:** BLOCKING
**Where:** Brief §2 line 43 ("Global fresh deadline is <= 6s"), §5 lines 178
(LIVE_REDDIT <= 5s), 199 (ARXIV_OR_PAPERCLIP <= 3s); compare
`brain_loop.py:432-433` (Layer 1 wired at `branch_timeout_s=0.8`,
`global_deadline_s=1.0`).

**Observation:** Layer 1, as wired, has a 1-second global deadline and 0.8s
per-branch. The brief's external budgets are an order of magnitude larger.
§8 then says "Layer 1 and external fan-out run concurrently once Layer 2 has
produced the final spec" — which means in a hybrid turn the turn-level
latency is bounded by `max(layer1_global=1.0s, external_global=6.0s) = 6s`.
That's defensible (external HTTP genuinely takes longer than local recall),
but the brief should say it. Two specific risks:

1. A FRESH_ONLY turn (probe 6) has no substrate fan-out happening in
   parallel. The 6s wall clock is the user-visible response latency floor
   when fresh sources are slow. The brief should acknowledge this is the
   intended budget, not an accident.
2. Per-branch composition: §5 sets per-source timeouts (5s, 3s) but doesn't
   say whether external branches run *concurrently with each other*. If they
   run sequentially, a slow `LIVE_REDDIT` (5s) followed by `ARXIV_OR_PAPERCLIP`
   (3s) blows the 6s global. If they run concurrently (matching Layer 1's
   `ThreadPoolExecutor` model), the 6s global is coherent.

**Recommendation:** State explicitly in §5 or §8 that external branches run
concurrently with each other (matching Layer 1), and that the global 6s
deadline is the turn-level latency floor for FRESH_ONLY turns. If a tighter
total-time SLO is intended for hybrid turns (substrate ready early, render
without waiting for slow external), say so — that's a non-trivial design
point that affects the merge step in Finding 1.

### Finding 5 — Telemetry vocabulary unspecified

**Severity:** SUGGEST
**Where:** Brief is silent; compare `brain_loop.py:362-368, 379-389, 450-457,
462-469, 485-491` (existing dispatcher_* vocabulary: `dispatcher_path_entry`,
`dispatcher_layer0_emit`, `dispatcher_layer0_budget_breach`,
`dispatcher_layer2_repair`, `dispatcher_layer1_branch`,
`dispatcher_layer1_fanout`, `dispatcher_path_exit`).

**Observation:** The daemon witness shows a clean, consistent telemetry
shape: one `_branch` event per branch with `source / outcome / row_count /
elapsed_ms`, one `_fanout` event per organ with `fanout_generation_id /
branch_count / seal_state / total_elapsed_ms`, framed by `_path_entry` and
`_path_exit`. The brief never names `dispatcher_external_branch` /
`dispatcher_external_fanout` or specifies their fields. An implementer will
have to invent the shape, and reviewers will have to re-litigate it.

**Recommendation:** Add a short subsection — call it §8.1 Telemetry — that
enumerates:

- `dispatcher_external_branch surface=... source=<ExternalSource> outcome=<rows|empty_with_reason|timeout|error|reserved_skip|preflight_blocked> block_count=N elapsed_ms=...`
- `dispatcher_external_fanout surface=... fanout_generation_id=... branch_count=N seal_state=<clean|partial_failure> total_elapsed_ms=...`
- Whether `dispatcher_path_exit` gains a combined `turn_seal_state` field or
  remains as-is (ties to Finding 3).

### Finding 6 — Recovery-seed bypass not addressed

**Severity:** BLOCKING
**Where:** Brief is silent; `brain_loop.py:1261-1278` (`if recovery_seed is
None: if _dispatcher_enabled(): ... dispatcher_path = True`).

**Observation:** When `recovery_seed is not None`, the dispatcher pipeline is
bypassed entirely — including Layer 1. This is a deliberate Session 11z Part
3 decision (`brain_loop.py:1238`). The external-source brief does not say
whether external fan-out is also bypassed under recovery seed. It must be,
to remain consistent with Layer 1 — otherwise external fetch executes during
a recovery pass, which is the opposite of the recovery contract (recovery
re-enters with failure context, not a fresh fan-out).

**Recommendation:** Add a sentence to §8 or §10 (Non-Goals): "Under
`recovery_seed`, external fan-out is bypassed identically to Layer 1; the
recovery path remains JARVIS-only as of this slice." Add a RED test to §9:
recovery_seed turns do not invoke `ExternalFanout.run`.

### Finding 7 — RED test #6 doesn't cover the cross-organ case

**Severity:** SUGGEST
**Where:** Brief §9 test #6 (`test_external_fanout_seals_late_results_by_generation_id`).

**Observation:** The named test exercises late results within external
fan-out. The harder case is a substrate branch returning at T=0.5s, an
external branch returning at T=6.5s after the global deadline, and proving
the rendered output reflects only the substrate row plus a
`FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT` limitation — never the late
external row. This is exactly the property §4 line 160 promises.

**Recommendation:** Either expand test #6 to cover the cross-organ case, or
add a test #8: `test_late_external_result_cannot_mutate_substrate_only_render`.

### Finding 8 — `sealed_at` clock domain unspecified

**Severity:** NIT
**Where:** Brief §4 line 152; compare `layer1.py:147, 244` (Layer 1 uses
`time.monotonic` via injectable `clock`).

**Observation:** Layer 1 uses `time.monotonic` (injectable). The brief's
`sealed_at: float` does not specify the clock domain. Implementers tend to
reach for `time.time()` for "timestamps" and `time.monotonic()` for
"deadlines"; the field name `sealed_at` suggests the former while the
semantics demand the latter.

**Recommendation:** Add ", monotonic" to the field comment, matching Layer 1.

## What the brief gets right

- The Option A decision is correct and well-argued (§3). Inlining fetch in
  brain_loop or relying on JARVIS fallback both fail the witness in §1.
- §4 names the right seal *invariants* even if it doesn't engineer them:
  generation id, deterministic source order, per-branch timeout, global
  deadline, no late mutation. Those are exactly the four properties Layer 1
  enforces.
- §6 failure mapping uses closed taxonomy. No free-form strings reach
  rendering. This matches Layer 1's `RecallBranchStatus` discipline.
- §7 reconstructed-spec validation ("the reconstructed spec must pass normal
  `CompositionSpec` validation before rendering") is exactly the right
  defense against laundering external failure into prompt text.
- §10 non-goals correctly carve out frontier consultation, credentials,
  browser automation, and the dispatcher flag flip.
- RED test #4 (`test_frontier_consult_reserved_never_executes`) directly
  guards a producer-causality concern: no model call, no subscription proxy,
  ever.

## Open questions for synthesis

1. (Out of Ohm lens) Does `WEB_SEARCH` running on FRESH_ONLY turns need the
   same trust-scope discipline as substrate sources? The brief doesn't say
   whether `source_availability` applies to external sources.
2. (Adjacent to Ohm) Cold-start latency on probe 1 was 848ms for Layer 0
   alone. Hybrid turns under FRESH_ONLY with a 6s external global will land
   in 6-7s end-to-end on cold start. Is this acceptable for the daemon HTTP
   surface, or does the slice need a separate cold-start budget line?
3. (Possibly Pauli/Huygens) The brief says §5 LIVE_REDDIT may use the
   external-fetch boundary with public Reddit JSON. But §10 says "do not add
   credentials or browser automation." If Reddit returns 403 to unauthenticated
   JSON polls (as has happened historically), is `FRESH_ATTEMPT_FAILED` the
   only honest answer, or does the slice need a `LIVE_REDDIT_BLOCKED`
   distinction?
4. (Possibly Buber/Kant) §5 says "the initial query is the owner utterance
   normalized by Layer 0 or the external-source adapter; no LLM-generated
   query is required for v1." Where exactly does normalization live? If it
   lives in `external_sources.py`, that's new logic; if it lives in Layer 0,
   that's a Layer 0 surface this brief should name.
