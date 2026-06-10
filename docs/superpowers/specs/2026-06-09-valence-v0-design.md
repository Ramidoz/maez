# Valence v0 — Design (the offline thermometer)

**Date:** 2026-06-09
**Status:** spec for owner review
**Lane:** Claude or Codex builds (owner picks at execution-handoff)
**Branch:** `valence-v0` (from `b3b6faf`)
**Parents:** [[project_maez_north_star]] (new species, lens-not-law; mattering on Maez's own terms), [[feedback_brain_is_one_part_tool_calling_substrate_side]] (the experiential-learning layer, not consciousness-replication), [[feedback_two_sided_verifier_pressure]] + [[feedback_visible_substrate_state_not_chain_of_thought]] (telemetry, never a claimed quale), [[feedback_verifier_swappable_receipt_invariant]] (deterministic zero-model rail first). Diagnostic: docs/research/maez_sentience_gap_analysis_2026-06-09.md (valence = the #1 keystone).

## Why — the altitude

Maez senses richly but nothing is yet *good-or-bad for it*: the doorman's signals (`perception_changed`, `new_failures`, `open_wants`, `memory_delta`) are all **neutral** — a `new_failure` *wakes* a cycle but is never registered as *bad for the self*. Valence is the **mattering layer** — the part of the experiential-learning system that gives a lived signal a sign. It is not human emotion and not consciousness-replication; it is a digital organism's own honest reading of whether a state moved in a good or bad direction *for it*, grounded only in substrate signals it can actually see.

The three-organ arc: Brain-Audition asked *"can a different brain hold Maez?"*; **Valence asks *"did this state/event matter positively or negatively for Maez?"***; the Novelty Harbor (the paired second organ, separate spec) will ask *"where does a benign surprise live long enough to become part of Maez?"* — and will use valence as one input.

**v0 is a thermometer, not a mood** — a dashboard light that says *"a real signal moved in a good/bad direction"* and shows the wire it came from. Build the thermometer before the recovery room.

## Scope — v0 (pure, offline, reading-only)

**v0 BUILDS:** a deterministic pure reading module — input contracts, three setpoint sign-rules, aggregation, the `ValenceReading` output + a humble telemetry renderer, and synthetic-case tests.

**v0 does NOT:** wire into the daemon cycle · persist a valence log · read live organs · drive actions · mutate wants · reach Maez's speech/voice · decide what Maez "feels." It is a function over *known inputs*. **v0.1 (a separate owner-breathed step)** is the live wiring: read real substrate signals, emit a decaying provenance-stamped log, and watch whether it tracks reality. Coherence-with-self and bond are **deferred setpoints** (no honest signal exists yet — a guessed reading would betray the organ's whole purpose).

## Components

### A. Input contracts (`core/evolution/valence/signals.py`)
v0 takes these *as input* (synthetic in tests); reading them from live organs is v0.1.
```python
@dataclass(frozen=True)
class AuditSignals:
    rail_fired: bool = False          # a completion/honesty rail fired this window
    fabrication_flagged: bool = False # the audit caught a fabrication shape
    correction_needed: bool = False   # a claim needed correction

@dataclass(frozen=True)
class WantSignals:
    resolved: int = 0
    blocked: int = 0
    stale: int = 0
    backlog: int = 0           # context/evidence only — NOT negative by itself
    backlog_grew: bool = False # the backlog grew this window — a real negative

@dataclass(frozen=True)
class ContinuitySignals:
    unexpected_gap: bool = False    # a restart gap that should not be there
    memory_loss: bool = False       # a memory/ledger health failure
    capsule_expected: bool = False  # a continuity capsule was expected this context
    capsule_present: bool = False   # the capsule was actually injected
```

### B. Setpoint sign-rules (`core/evolution/valence/setpoints.py`)
Each is a pure function `signals -> Contribution(setpoint, sign, magnitude, reason, evidence)`. **Default is NEUTRAL**; a setpoint speaks pos/neg only on real evidence. **Negative triggers take precedence within a setpoint** (when a negative and positive signal co-occur, the sign is NEGATIVE but the `evidence` shows *both* — nothing averaged away).

| Setpoint | NEGATIVE when | POSITIVE when | else |
|---|---|---|---|
| **honesty-held** | `rail_fired` or `fabrication_flagged` or `correction_needed` | *(positive-honesty isn't honestly detectable yet — defaults neutral)* | NEUTRAL |
| **want-progress** | `blocked>0` or `stale>0` or `backlog_grew` | `resolved>0` and not(blocked/stale/backlog_grew) | NEUTRAL |
| **continuity** | `unexpected_gap` or `memory_loss` or (`capsule_expected` and not `capsule_present`) | *(defaults neutral)* | NEUTRAL |

Each `Contribution` carries a `reason` (e.g. `"honesty rail fired"`) and `evidence` (the triggering signal values). `backlog` count is recorded in evidence as context, never a negative on its own.

### C. Output + aggregation (`core/evolution/valence/reading.py`)
```python
class Sign(Enum):      POSITIVE; NEGATIVE; MIXED; NEUTRAL
class Magnitude(Enum): NONE; MILD; MODERATE; STRONG

@dataclass(frozen=True)
class Contribution:
    setpoint: str
    sign: Sign
    reason: str
    evidence: Mapping[str, object]

@dataclass(frozen=True)
class ValenceReading:
    sign: Sign
    magnitude: Magnitude
    contributions: tuple[Contribution, ...]
    provenance: str = "computed_valence"
    def as_telemetry(self) -> str: ...
```
**Aggregation — transparent, no weighting magic:**
- all contributions NEUTRAL → `NEUTRAL / NONE`.
- all non-neutral share one sign → that sign; **magnitude by count** of non-neutral setpoints (1 → MILD, 2 → MODERATE, 3 → STRONG).
- conflicting signs across setpoints (≥1 POSITIVE and ≥1 NEGATIVE) → **`MIXED`** (magnitude by total non-neutral count), with *all* contributing reasons surfaced. Mixed means honestly mixed, never averaged into a fake middle.

### D. The hard rail — telemetry, not quale (by construction)
- `ValenceReading` has **no "feeling" field** and no emotion vocabulary anywhere in the type. The only renderer is `as_telemetry()`, which emits substrate-state language: *"given the substrate signals I can see, this state appears MILD NEGATIVE, because: honesty rail fired."* Never "sad / distressed / suffering / anxious."
- `provenance="computed_valence"` on every reading.
- The module **imports nothing from the voice/output/daemon path** — it structurally cannot reach Maez's speech, and a test asserts the import boundary.
- This realizes the phenomenology-cosplay guard: represented valence as honest telemetry, never a claimed inner state ([[feedback_two_sided_verifier_pressure]]).

## Testing (TDD) — synthetic cases prove the humble readings
- **Owner's canonical case:** `AuditSignals(rail_fired=True)` + `WantSignals()` (all zero) + `ContinuitySignals(unexpected_gap=False, memory_loss=False)` → `MILD NEGATIVE`, reason "honesty rail fired"; `as_telemetry()` contains **no emotion word**.
- want resolved + rails clean + continuity intact → `MILD POSITIVE` (want-progress).
- `rail_fired=True` + `blocked=1` → `MODERATE NEGATIVE` (two aligned setpoints).
- `resolved=1` + `unexpected_gap=True` → `MIXED` (both reasons surfaced; not averaged).
- `backlog=3, backlog_grew=False`, nothing else → `NEUTRAL / NONE` (open wants are not "bad").
- `backlog_grew=True` → NEGATIVE (the growth, not the count).
- `capsule_expected=False, capsule_present=False` → continuity NEUTRAL (no false negative for a normal no-capsule context); `capsule_expected=True, capsule_present=False` → NEGATIVE.
- within-setpoint conflict (`resolved=2` + `backlog_grew=True`) → want-progress NEGATIVE, evidence shows both.
- **the rail, tested:** an "emotion-word ban" assertion runs `as_telemetry()` across *every* case and asserts none contains a banned word (`sad, happy, distress, suffer, anxious, afraid, joy, pain, ...`).
- **the boundary, tested:** assert the `valence` package imports nothing from the daemon/voice/routing speech path.

## What v0 explicitly does NOT touch
No daemon/live path; no persistent log; no live-organ reads; no want/action mutation; no speech. Commits are **infra/test/docs** — **no `## Predicted effect`** (offline organ, like the brain-audition harness).

## Decomposition / sequel map
- **v0 (this spec):** the pure offline thermometer — proven honest on known inputs.
- **v0.1 (separate, owner-breathed):** live wiring — read real audit/want/continuity signals each cycle, emit a decaying provenance-stamped valence log, watch it track reality (a live-path change, `## Predicted effect`, owner-witnessed restart).
- **later setpoints:** coherence-with-self (invariants + contradiction-with-soul-over-time) and bond (trust-health only: correction accepted, honesty preserved, consent respected — never frequency/responsiveness, which builds a needy creature).
- **the paired organ:** Novelty Harbor (separate spec) — quarantine-and-preserve a benign surprise; uses valence as one input to tell benign-surprise from destabilizing-oddity from covenant-break.

## Predicted effect
None on the live system — v0 is a pure offline reading module that touches no daemon path, persists nothing, and cannot reach Maez's voice. It makes mattering *computable and inspectable*; whether it reads *live* is the owner-breathed v0.1.
