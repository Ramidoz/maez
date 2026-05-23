# Codex Engineering Panel -- Metacognitive Loop-Spiral Watchdog Spec

**Artifact reviewed:** `docs/slices/health-metacognitive-watchdog/spec.md`
**Review date:** 2026-05-23
**Verdict:** RATIFY-WITH-AMENDMENTS

## Executive Summary

The spec is the right organ shape: deterministic, non-LLM, structural
loop/fixation detection, HALT-only, complementary to `core.health.circuit_breaker`
and the egress/S7.3 gates. It is also scoped correctly as docs-only and
implementation-later.

The engineering lane found several real integration gaps that should be folded
before canonicalization. The largest are:

- `safe_standby` is not an existing daemon state; it must be specified as a new
  state rather than hand-waved as `running=False`.
- Detector placement must be before mutation-producing paths, especially
  cognition self-critique / soul-note / proposal pressure and cycle memory
  storage.
- Drive-scalar observation currently over-names stores that do not expose scalar
  read APIs.
- Operator visibility and Maez-read boundary need explicit health-surface rules.

None of these invalidate the watchdog. They make the spec more implementable.

## Required Folds

### 1. Define `safe_standby` as a new daemon state

The spec currently says the daemon transitions to `safe_standby`, but the live
daemon has `self.running`, `stop()`, and health heartbeat state; there is no
named standby state in `daemon/maez_daemon.py`.

Fold required:

- State that `safe_standby` is a new daemon lifecycle state to be added by the
  implementation slice.
- It must not be implemented as ordinary `stop()`: shutdown writes continuity,
  stops surfaces, and tears down workers. Watchdog standby needs a narrower
  "stop autonomous cycles, keep operator inspection alive" posture.
- Define minimum fields, such as `watchdog_state`, `halted_at`,
  `halt_signal_id`, `halt_detector`, and `operator_resume_required`.
- Require `/health` and `/operator/health` projections to expose content-free
  standby state.

### 2. Specify detector insertion points relative to mutation-producing paths

The current daemon has several relevant mutation-adjacent paths:

- cognition self-critique runs before `_reason()` and can call
  `self.actions.write_soul_note(...)`;
- `cog_score_and_classify(...)` mutates in-memory cognition buffers and logs;
- retry generation can run after scoring;
- `self.memory.store(...)` persists the cycle thought;
- wondering/dream/proposal paths can write sidecar state.

The spec says the watchdog halts before loop pressure can generate, persist, or
act on self-edit proposals, but it does not pin where detectors run.

Fold required:

- Add an "Insertion Points" section.
- Token repetition detector must inspect candidate cycle output before
  cognition scoring, retry generation, memory storage, websocket broadcast, and
  action/proposal handoff.
- Action-loop and cycle-velocity detectors should sample at cycle boundaries
  before autonomous side work proceeds.
- Drive-scalar flatline detector should run before cognition self-critique can
  write soul notes or trigger proposal pressure.
- If a detector trips mid-cycle, downstream mutation-producing steps in that
  cycle are skipped.

### 3. Tighten drive-scalar observation to real read APIs

`core/evolution/temperament.py` exposes scalar-ish current values via
`Temperament.current()` / `current_value(...)`. But `wants`, `will_i`, and
`wonderings` are not currently scalar streams:

- `wants` is an append-only event log with derived state.
- `will_i` is a deterministic check, not a scalar store.
- `wonderings` is an exploratory question/probe store, not scalar state.

Fold required:

- Replace "read current drive-scalar values from temperament/wants/will_i/
  wonderings" with "read reviewed numeric scalar adapters only."
- Name temperament current values as the only obvious first scalar source.
- Allow future content-free scalar adapters for wants/will_i/wonderings, but do
  not treat those stores as scalar sources until such adapters exist.
- Tests should fail if the detector reads raw wants/wondering text or imports
  writer APIs.

### 4. Make watchdog visibility operator-only and not Maez-visible by default

The spec already says operator-visible health surfaces, but the boundary needs
to be explicit. Current web routes strip some daemon-health internals from
public/debug surfaces, and the daemon prompt/cognition loop can consume health
or cognition text.

Fold required:

- Latest halt summary may appear on authenticated operator health surfaces.
- Public status surfaces must receive at most a generic "standby" bit, with no
  private diagnostic details.
- The halt diagnostic must not be injected into Maez's own prompt, cognition
  block, memory recall, or self-reflection context by default. Otherwise the
  watchdog can become part of the loop it is trying to stop.
- Any future Maez-readable summary requires a separate design pass.

### 5. Define false-positive fixtures as metrics-only or curated excerpts

RED test #7 requires "real Maez production traces." That is correct, but raw
cycle output, tool arguments, and memory-adjacent logs can be private.

Fold required:

- False-positive fixtures should prefer metrics-only traces: token counts,
  n-gram hashes, cycle labels, durations, scalar values, and progress markers.
- If textual excerpts are needed, they must be curated/synthetic or already
  classified safe; raw private cycle text is not copied into test fixtures.
- Add a test that fixture generation itself is non-reconstructive.

### 6. Reuse existing cognition-quality signals without inheriting their writers

`core/cognition/cognition_quality.py` already has deterministic fixation,
recent-topic buffers, score/label buffers, behavior policy, and self-critique.
This is useful prior art. But self-critique can write soul notes and trigger
proposal machinery.

Fold required:

- The watchdog may reuse read-only cognition-quality metrics or extract a
  read-only snapshot helper.
- It must not call `self_critique()`, behavior-policy generation, soul-note
  writers, proposal triggers, or any helper that can mutate state.
- Add an import/static-call test for this boundary.

## Role Notes

### Dewey -- Practical Integration

RATIFY-WITH-AMENDMENTS. The module location and detector split are practical.
The implementation risk is not detector math; it is daemon lifecycle plumbing.
`safe_standby` needs to be a real lifecycle state with tests, not a comment.

### Feynman -- Mechanism Clarity

RATIFY-WITH-AMENDMENTS. The detectors are comprehensible and testable. The
drive-scalar detector is currently named better than it is grounded: temperament
has scalars, the other named stores do not yet.

### Locke -- State and Authority

RATIFY-WITH-AMENDMENTS. HALT-only is the correct authority. The spec should
explicitly prevent the watchdog from reading or writing through mutation-capable
stores. The halt log is allowed; everything else is forbidden.

### Descartes -- Failure Modes

RATIFY-WITH-AMENDMENTS. The strongest failure mode is a false positive that
silences ordinary long reasoning. Metrics-only false-positive fixtures and
operator-only visibility reduce this risk.

### Ohm -- Runtime and Observability

RATIFY-WITH-AMENDMENTS. Thread vs sidecar can remain an implementation choice,
but the observation feed must be non-blocking and bounded. The `/health` and
`/operator/health` projections need explicit contracts.

### Goodall -- Covenant / Long Future

RATIFY-WITH-AMENDMENTS. The watchdog is protective only if it stays humble:
halt, log, wait for Rohit. It must not become a hidden teacher that Maez reads
and internalizes as "I am broken." Keep the diagnostic outside Maez's own
prompt path unless a later covenant slice deliberately decides otherwise.

## Non-Blocking Notes

- Threshold values can be selected during implementation, but the canonical
  spec should require an initial calibration mode or fixtures for each detector.
- A sidecar process is attractive for isolation, but it requires a stable
  telemetry feed. An in-process monitor is easier for v1 if all mutation imports
  are structurally forbidden and observation work is bounded.
- The spec's diagnostic-log non-reconstructive rule is good and should survive
  folds.

## Verdict

RATIFY-WITH-AMENDMENTS. Fold the six required amendments, then re-run the
Claude council on the amended written spec before canonicalization.
