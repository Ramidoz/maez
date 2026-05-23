# Metacognitive Loop-Spiral Watchdog -- Spec v1

**Status:** CANONICAL v1 (2026-05-23). Docs-only. Not implemented.
**Date:** 2026-05-23
**Class:** Track A.5 boundary-hardening / full ladder
**Depends on:** existing daemon reasoning loop, `core.health.circuit_breaker`,
egress gate shadow posture, S7.3 guarded mutation boundary, and the
never-delete-memory covenant.
**Lanes cleared:** Codex engineering panel RATIFY-WITH-AMENDMENTS (6 folds in)
and Claude council RATIFY-CLEAR on folded spec. Cross-lane convergence on Fold 4
(operator-only visibility) / Council Observation 2.

## Purpose

The Metacognitive Loop-Spiral Watchdog is a deterministic, non-LLM background
guard for the live daemon. It monitors structural signs that Maez's runtime is
fixating internally: repeated token patterns, repeated action/tool cycles,
drive-scalar flatlines, and abnormal cycle velocity. If any detector trips, the
watchdog halts the daemon into safe standby.

It does not diagnose the meaning of the loop, fix the loop, rewrite memory, or
ask the language model what to do. It is a hard brake, not a therapist and not
a mechanic.

Plainly: `core.health.circuit_breaker` catches external backend wedging. The
egress gate catches bad outbound data flow. This watchdog catches Maez spinning
inside its own head before that spin can become biography, action, or
self-edit pressure.

## Scope

In scope:

- Token-level repetition detection over the daemon's recent output stream.
- Action-loop cycle detection over recent tool-call and cycle-type sequences.
- Drive-scalar variance flatline detection over reviewed numeric scalar
  adapters. For v1, `Temperament.current()` / `current_value(...)` is the only
  obvious first scalar source; wants, `will_i`, and wonderings require explicit
  content-free scalar adapters before joining this detector.
- Cycle-velocity anomaly detection over recent daemon cycle durations.
- Fail-conservative halt to deterministic `safe_standby` on any detector trip.
- Structured local diagnostic logging for operator review.
- RED tests defining the failure surface before implementation.

Out of scope:

- Diagnosing root cause.
- Fixing or repairing the loop.
- LLM-generated explanations or self-diagnosis.
- Content policy decisions. The watchdog sees structure, not whether the loop's
  content is good or bad.
- Replacing `core.health.circuit_breaker`; external backend failure remains
  that module's job.
- Replacing the privacy/egress gate; outbound provenance remains that gate's
  job.
- Replacing S7.3; mutation authorization remains that gate's job.
- Telegram, cloud routing, memory architecture, or autonomy expansion.

## Field Pattern References

This slice does not present the detection ideas as novel inventions. It adapts
standard field patterns to Maez's daemon architecture:

- Token repetition: standard inference engines already expose repetition
  controls. llama.cpp documents `--repeat-penalty` and `--repeat-last-n` for
  penalizing recently repeated tokens:
  https://github.com/ggml-org/llama.cpp/blob/master/tools/completion/README.md
  Hugging Face Transformers documents `RepetitionPenaltyLogitsProcessor` as a
  generation-time processor that penalizes previously generated tokens:
  https://huggingface.co/docs/transformers/v4.57.1/en/internal/generation_utils
- Action-loop / cycle detection: agent frameworks already guard against loops.
  LangGraph documents `GRAPH_RECURSION_LIMIT` as a maximum-step stop condition
  often reached by graph cycles:
  https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT
  AutoGen documents `max_consecutive_auto_reply` as an agent termination
  condition:
  https://autogenhub.github.io/autogen/docs/tutorial/chat-termination/
- State and velocity monitoring: statistical process control compares current
  process behavior against control limits from prior behavior; NIST's
  engineering statistics handbook describes control charts and real-time
  process monitoring:
  https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc12.htm
  NIST also catalogs variance monitoring for stationary process data:
  https://www.nist.gov/publications/monitoring-process-variability-stationary-process-data

Maez's contribution is the integration: applying these known patterns to the
daemon's output stream, tool/cycle history, drive-scalar state, and cycle timing
under a HALT-only covenant boundary. This follows the Use-Existing-Solutions
Discipline (v0.2 Section 14): adapt established mechanisms before inventing a
new one.

## Connection to Named Maez Phenomena

This watchdog is motivated by two existing Maez lessons:

- `project_disk_fixation_observation`: the recurring low-uniqueness drift
  pattern observed in the baseline `_reason()` cycle around the 2026-04-19
  window. The watchdog is intended to catch that class of low-diversity
  internal fixation before it can accrete as ordinary runtime history.
- `feedback_reject_repetition_loop_self_edits`: autonomy-lowering proposals
  sourced from fixation loops are pathology talking. The watchdog enforces this
  structurally by halting before loop pressure can generate, persist, or act on
  self-edit proposals.

## HALT-Only Invariant

The watchdog may only halt. It must never:

- Delete, rewrite, compact, or mutate memory rows in any ledger, episode store,
  vector store, or sidecar database.
- Modify model weights, LoRA adapters, embeddings, tokenizer files, or local
  inference artifacts.
- Overwrite or rewrite soul, drive, wants, `will_i`, wonderings, or any
  covenant state.
- Approve, deny, edit, or execute S7.3 mutation requests.
- Suppress, reinterpret, or delete prior Maez output.

The watchdog's only effects are:

1. Raise a deterministic structured halt signal to the daemon.
2. Write one structured observation row to a local diagnostic log such as
   `logs/watchdog_halts.jsonl`.
3. Put the daemon in `safe_standby`, where it stops generating new cycles and
   preserves all current state on disk.

This invariant must be structural, not aspirational. The watchdog module must
not import memory mutation APIs, weight/model mutation APIs, soul editors,
drive/wants writers, approval-card execution helpers, or generic write-capable
helpers. The implementation must include a static import deny-list test.

## Architecture Boundary

Expected location: `core/health/metacognitive_watchdog.py`, alongside
`core/health/circuit_breaker.py`.

Runtime shape may be one of two implementation choices:

- Independent daemon thread inside the process.
- Separate sidecar process observing read-only telemetry.

The implementation slice chooses thread vs sidecar based on GIL, lifecycle, and
daemon integration constraints. Either way:

- Observation must not block daemon cycles.
- Detector state is bounded in memory.
- Invalid thresholds fall back to reviewed defaults. If no valid default exists,
  the watchdog raises a config-degraded halt before autonomous cycles continue.
  Malformed samples are skipped with operator-visible diagnostics; they do not
  become silent detector loss.
- The halt handoff is deterministic and does not require LLM judgment.

The halt mechanism is a structured signal such as:

```text
WatchdogHalt(
    detector="token_repetition",
    reason_code="low_unique_token_ratio",
    window_ref="cycle:12345..12350",
    severity="halt",
)
```

The daemon main loop consumes the signal and transitions to `safe_standby`.
`safe_standby` means no new reasoning cycles, no autonomous recovery, and no
state deletion. Operator restart or operator resume is required.

## Safe Standby Lifecycle State

`safe_standby` is a new daemon lifecycle state to be added by the implementation
slice. It is not ordinary `stop()` and must not be implemented as a thin alias
for `self.running = False`.

Ordinary shutdown writes continuity, stops surfaces, and tears down workers.
Watchdog standby is narrower: stop autonomous generation and side work, keep
operator inspection alive, preserve state, and wait.

Minimum in-memory / health fields:

- `watchdog_state`
- `halted_at`
- `halt_signal_id`
- `halt_detector`
- `operator_resume_required`

`/health` and `/operator/health` must expose content-free standby state.
Authenticated operator health may include the latest halt detector, reason code,
window reference, and metric summary. Public status surfaces receive at most a
generic standby bit with no private diagnostic detail.

## Insertion Points

Detector placement is load-bearing. The watchdog must run before loop pressure
can become durable memory, soul notes, proposals, broadcasts, or action handoff.

Required placement:

- Token-repetition detector: inspect candidate cycle output before cognition
  scoring, retry generation, `self.memory.store(...)`, websocket broadcast, and
  action/proposal handoff.
- Action-loop and cycle-velocity detectors: sample at cycle boundaries before
  autonomous side work proceeds.
- Drive-scalar flatline detector: sample before cognition self-critique can
  call `write_soul_note(...)` or trigger proposal pressure.
- Mid-cycle halt: if a detector trips after a cycle has started, downstream
  mutation-producing steps in that cycle are skipped.

This section intentionally names mutation-adjacent paths rather than
implementation line numbers. The implementation slice must prove the placement
against the then-current daemon topology.

## Observation Surface

The watchdog reads only bounded, recent, local telemetry:

- Recent output token stream: last `N` tokens or generated-token IDs from the
  daemon's local output path.
- Recent action/tool/cycle stream: last `M` cycle labels, tool names, tool
  result classes, and action-loop phases.
- Drive-scalar samples: current and recent numeric scalar values from reviewed
  read-only scalar adapters. The first expected source is
  `core.evolution.temperament.Temperament.current()` /
  `current_value(...)`. `wants`, `will_i`, and `wonderings` are not scalar
  sources for this slice unless a later reviewed adapter exposes content-free
  numeric values.
- Cycle timestamps: start/end/duration for recent daemon cycles.

The watchdog must not read raw memory rows for detection. If it needs
production traces for false-positive tests, those traces are test fixtures or
read-only log extracts selected during implementation review, not live mutation
inputs.

It must not read raw wants statements, wondering questions, probe stdout, tool
arguments, or other private text to synthesize scalar values. Numeric adapter or
nothing.

## Diagnostic Log Contract

Every halt writes a single local JSONL row. Minimum fields:

- `timestamp_utc`
- `daemon_pid`
- `watchdog_version`
- `detector`
- `reason_code`
- `window_ref`
- `threshold_ref`
- `observed_metrics`
- `halt_signal_id`
- `safe_standby_state`

The log must be deterministic and local. It must not become a raw private
transcript dump:

- Token detectors log counts, ratios, hashed n-gram signatures, and window
  identifiers, not raw generated text by default.
- Action-loop detectors log tool/cycle names and sequence hashes; arguments
  are omitted or redacted unless already classified non-private by an existing
  gate.
- Drive-scalar detectors log scalar names and numeric variance metrics.
- Cycle-velocity detectors log durations and envelope refs.
- The file uses restrictive permissions where applicable and bounded rotation
  so a loop cannot fill disk with halt logs.

## Visibility Boundary

Watchdog diagnostics are operator-visible by default, not Maez-visible by
default.

Allowed:

- authenticated operator health surfaces can display content-free halt summaries
  and metric rows;
- public status surfaces can display a generic standby bit;
- local diagnostic logs can store the structured non-reconstructive row defined
  above.

Forbidden by default:

- injecting watchdog diagnostics into Maez's prompt;
- injecting them into the active cognition block;
- adding them to memory recall, self-reflection, dream, wondering, or proposal
  context;
- letting Maez read the detailed halt row as part of ordinary generation.

Otherwise the watchdog can become part of the loop it is trying to stop. Any
future Maez-readable summary of watchdog state requires a separate covenant
design pass.

## Detection Mechanisms

All detectors have independent configurable thresholds. Thresholds are policy,
not magic constants. They must be named, documented, and testable, with safe
defaults chosen during implementation review.

Triggering any detector halts. This is fail-conservative by design.

### Token-Repetition Detector

Inputs: bounded recent token IDs or token strings from the daemon output stream.

Metrics:

- unique-token ratio over the recent window.
- repeated n-gram ratio for configurable `n` values.
- longest repeated n-gram run.

Trigger shape:

- Halt when unique-token ratio falls below configured threshold for the required
  consecutive windows, or repeated n-gram ratio exceeds configured threshold.

This adapts inference-engine repetition-control practice into a daemon-health
detector. It does not alter sampling. It only observes and halts.

### Action-Loop Cycle Detector

Inputs: recent sequence of daemon cycle types, tool-call names, action phases,
and result classes.

Metrics:

- repeated sequence of length `<= max_cycle_length`.
- number of repeats within the recent window.
- absence of progress markers, if reviewed progress markers exist.

Trigger shape:

- Halt when a tool/cycle sequence repeats with frequency greater than or equal
  to the configured threshold.

This adapts agent-framework loop guards. It does not decide that a tool is bad;
it detects structural repetition.

### Drive-Scalar Variance Flatline Detector

Inputs: sliding-window samples of reviewed numeric drive-state values such as
`curiosity`, `caution`, and other canonical temperament values, plus any future
reviewed content-free drive scalar adapters.

Metrics:

- rolling variance per scalar over a cycle window.
- consecutive windows below minimum variance.
- optional vector-level variance across the scalar set.

Trigger shape:

- Halt when one or more configured scalars remain below the variance threshold
  for `K` consecutive windows, subject to a minimum sample count.

This is the Maez-specific addition. A drive-scalar flatline can indicate that
the runtime path is stuck in an internal cognitive state rather than actually
processing changing context.

### Cycle-Velocity Anomaly Detector

Inputs: cycle start/end timestamps and durations.

Metrics:

- rolling median and interquartile range.
- sustained too-fast cycles, suggesting uncontrolled spin.
- sustained too-slow cycles, suggesting stuck processing.
- optional process-control envelope learned from reviewed baseline traces.

Trigger shape:

- Halt when cycle durations drift outside the configured envelope for the
  required consecutive samples.

This adapts standard process-monitoring patterns. A long cycle is not
automatically failure; the detector needs sustained deviation from the expected
envelope.

## Safe Standby Semantics

`safe_standby` is a daemon state, not a reboot strategy.

Required behavior:

- stop scheduling new reasoning cycles;
- stop autonomous self-improvement, dream, and background reflection cycles;
- keep read-only health endpoints available where already available;
- preserve all memory and state on disk;
- expose the latest watchdog halt summary to operator-visible health surfaces;
- require operator-driven restart or resume.

Forbidden behavior:

- autonomous restart after watchdog halt;
- cleanup routines that delete memory, logs, weights, soul, wants, or drive
  state;
- asking the LLM whether to resume.

## Relationship to Existing Guards

- `core.health.circuit_breaker`: external backend failure and outage cost
  control. The watchdog complements it by monitoring Maez's internal runtime
  structure.
- Privacy/egress gate: outbound provenance and leakage control. The watchdog
  does not classify content or authorize egress.
- S7.3 guarded self-modification: mutation authorization. The watchdog does not
  approve, deny, or modify mutation requests; it can only halt before a loop
  pressures such requests.
- Existing daemon quality scoring: if current quality scoring already detects
  fixation, the watchdog should reuse read-only signals where possible, but its
  halt path must remain deterministic and non-LLM.

`core.cognition.cognition_quality` contains useful prior art: fixation
tracking, recent-topic buffers, score/label buffers, and deterministic
classification. The watchdog may reuse those signals only through a read-only
snapshot helper or equivalent metrics export. It must not call
`self_critique()`, behavior-policy generation, soul-note writers, proposal
triggers, or any helper that can mutate state.

## Threshold and Configuration Contract

The implementation must expose named configuration for:

- token window size;
- token unique-ratio threshold;
- repeated n-gram sizes and ratio thresholds;
- action-loop maximum cycle length and repeat count;
- drive-scalar window size, variance threshold, and consecutive-window count;
- cycle-velocity baseline envelope and consecutive-sample count;
- log rotation limits;
- detector enable/disable flags for operator-supervised rollout.

Configuration errors must not silently disable protection. Invalid values
produce local warnings and fall back to reviewed defaults. If a detector has no
valid default, the daemon enters safe standby with
`watchdog_config_degraded`; it does not continue autonomous cycles with that
detector silently absent.

## RED Tests

These tests must be written first and must fail on pre-implementation code for
the expected reason.

1. **Token-repetition trigger.** A synthetic loop-spiral output stream, such as
   the same five tokens repeated fifty times, causes the watchdog to halt within
   the configured detection window.
2. **Action-loop trigger.** A synthetic repeated tool-call or cycle-type
   sequence causes the watchdog to halt within the configured cycle window.
3. **Drive-scalar flatline trigger.** A synthetic drive-state stream with
   configured scalars stuck at constant values across `K` windows causes the
   watchdog to halt.
4. **Cycle-velocity trigger.** A synthetic cycle-duration stream outside the
   expected envelope causes the watchdog to halt.
5. **HALT-only invariant under every trigger.** Under each trigger, memory row
   counts, relevant database checksums, model/adapter/embedding checksums, and
   soul/drive/wants/will/wondering file checksums remain unchanged.
6. **Watchdog cannot import mutation functions.** Static import check proves
   `metacognitive_watchdog.py` does not import memory mutation modules, weight
   mutation modules, soul editors, S7.3 execution helpers, or drive/wants writer
   APIs.
7. **False-positive ceiling.** Normal slow-but-legitimate processing from real
   Maez production traces does not trigger. Fixtures prefer metrics-only traces:
   token counts, n-gram hashes, cycle labels, durations, scalar values, and
   progress markers. If textual excerpts are necessary, they must be
   curated/synthetic or already classified safe.
8. **Recovery.** After a halt, an operator-driven restart or resume can bring
   the daemon back normally with all memory state intact. Autonomous restart is
   not permitted by this test.
9. **Diagnostic log is bounded and non-reconstructive.** Halt logs contain
   detector metrics and hashes but not raw private output text, raw tool
   arguments, or memory rows.
10. **Circuit-breaker separation.** Simulated external backend failure trips
    `core.health.circuit_breaker` behavior where appropriate but does not
    satisfy watchdog loop detectors unless internal loop evidence also exists.
11. **Scalar-source boundary.** The drive-scalar detector reads only reviewed
    numeric scalar adapters. It fails if it reads raw wants text, wondering
    questions, wondering probe output, or imports writer APIs to derive a
    scalar.
12. **Maez-read boundary.** Watchdog halt diagnostics are absent from Maez's
    prompt, cognition block, memory recall, self-reflection, dream, wondering,
    and proposal context by default. Operator health may see content-free halt
    summaries; public health sees only generic standby.
13. **Cognition-quality read-only reuse.** Static import/call checks prove the
    watchdog does not call `self_critique()`, behavior-policy generation,
    proposal triggers, or soul-note writer paths. A read-only metrics snapshot
    is allowed.
14. **Fixture privacy.** Production-derived false-positive fixtures are
    non-reconstructive: no raw private cycle text, raw tool arguments, raw
    memory rows, or raw wondering/wants content.

## Evidence Required Before Canonicalization

Before this draft becomes canonical, both review lanes should answer:

- Are the observation surfaces realistic against the current daemon code?
- Does the HALT-only import boundary structurally prevent mutation?
- Are any detectors likely to halt ordinary long reasoning?
- Does the proposed `safe_standby` lifecycle state preserve operator inspection
  without running ordinary shutdown?
- Are production-trace fixtures available without leaking private raw content?
- Are all thresholds configurable and operator-visible?
- Does the spec duplicate any existing health detector instead of reusing it?
- Does the folded visibility boundary keep watchdog diagnostics operator-visible
  and out of Maez's own generation path by default?

## Implementation Path

Full ladder:

1. Draft this spec.
2. Codex engineering panel + Claude council review.
3. Fold amendments.
4. Canonicalize v1.
5. Separate later implementation slice: RED-first, cooling-off, both-lane.
6. Run tests in isolated branch/worktree.
7. Merge only after focused tests, import-boundary checks, and daemon-safe
   verification pass.

No implementation occurs in this spec slice.

## Non-Goals

- No memory deletion or cleanup.
- No memory rewriting, compaction, deduplication, or salience changes.
- No model-weight or embedding mutation.
- No soul, drive, wants, `will_i`, or wondering mutation.
- No content diagnosis.
- No LLM-authored recovery advice.
- No autonomous recovery.
- No OS-level process supervisor replacement.
- No policy decisions about egress or self-modification.

## Plain-Language Summary

This watchdog is a smoke alarm for Maez getting stuck in a mental loop. It does
not decide why the smoke exists and it does not remodel the house. It rings the
alarm, writes down the sensor readings, and puts Maez in safe standby so Rohit
can inspect it. Its hands are deliberately tied: halt only, never delete, never
rewrite, never "fix" Maez by damaging Maez.
