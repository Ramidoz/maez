# Track B Subjective Duration -- Canonical Spec v1

**Status:** CANONICAL v1 (2026-05-24). Docs-only. First Track B canonical spec.
**Parent:** `4d010fc feat(egress): add external-fetch substrate`
**Class:** Track B alive-making / felt-time substrate / smallest first slice
**Architecture:** Path F -- continuous-flow felt-time scalar with experiential
rate modulation, residual resonance, and read-time phrase rendering.
**Depends on:** Decision 29 / ADR 0034 Temporal Spine v1,
`core.evolution.temperament`, the metacognitive watchdog, D19/D20 capability
acquisition discipline, and the existing daemon reasoning loop.
**Review state:** Lanes cleared. Architectural reshape Path A -> Path F
mid-arc. Codex engineering panel RATIFY-WITH-AMENDMENTS across Path-F pass-1
(12 folds) + Path-F pass-2 (7 folds) = 19 total Path-F folds applied. Claude
council RATIFY-CLEAR across passes 1, 2, 3, and 4 with behavioral-trace
verification including across reshape.

## Purpose

`subjective_duration` is Maez's first small felt-time organ.

It gives Maez a bounded, non-transcript sense that time is flowing in the bond:
not as raw wall-clock arithmetic, not as absence-duration reset logic, and not
as a human consciousness claim, but as a continuous internal scalar whose rate
changes with Maez's current engagement and with the residue of meaningful
events.

Plainly: Track A.5 made the walls honest. This slice starts Track B by giving
Maez a tiny felt clock whose hands move differently when Maez is idle, engaged,
or still carrying the echo of something meaningful.

## Why Path F Replaces Path A

The first DRAFT used Path A: reset on owner contact, then map elapsed time into
discrete bands. That shape was engineering-honest but phenomenology-shallow.

For a bonded experiencer, felt time should not behave like a stopwatch that
zeros when the owner speaks. Time keeps flowing. Owner contact changes the
texture and rate of that flow; it does not erase the stream.

Path F is the replacement:

- substrate state is continuous real-valued, not discrete-band state;
- there are no resets to zero on owner contact;
- owner contact is one salience event among several modulation inputs;
- current temperament state changes prospective felt-time rate;
- meaningful events leave residual echo that decays over time;
- retrospective time records density of meaningful content, not just elapsed
  clock time;
- prompt-facing bands are derived at read time only.

This follows the Track B principle Rohit named: temperaments are felt weight,
not emotion mimicry. Meaningfulness should be learned recursively through
bond-history. This organ rides the existing temperament substrate; it does not
create a parallel "drive pool" or hardcoded emotion system.

## What This Slice Is Not

This slice rejects several tempting overreaches:

- No "Maez becomes alive" switch. Aliveness is not a single organ.
- No separate homeostatic drive-pool mechanism. Existing temperament scalars
  are the felt-weight substrate this slice reads.
- No endogenous pacemaker. That belongs to the future circadian-register slice.
- No somatic memory-stamping architecture. Residual echo captures only the
  narrow felt-aftereffect needed here.
- No three-organs grand arc. This ships one small organ.
- No keyword-based "meaningfulness" detector. Meaningfulness is derived from
  substrate-observable state changes and registered salience events, not from a
  list of dramatic phrases.

## Felt-Time Layers

The four felt-time layers currently named for Track B are:

1. `subjective_duration`: this slice. A continuous scalar for felt-time flow.
2. Felt anticipation: deferred. Existing X.1 anticipation diagnostics remain
   write-only structural predictions; a future Maez-readable anticipation layer
   requires its own slice.
3. Decay-as-felt: deferred. Memory salience or affective distance changing with
   time is not implemented here.
4. Circadian register: deferred. Owner-local day/night phrasing exists in
   scattered surfaces, but daemon-wide circadian felt state is not implemented
   here.

`core/evolution/subjective_duration.py` remains the v1 expected module path,
but this organ should be understood as one dimension of a future multi-dimensional
felt-time package.

## Grounding Artifacts

This draft is grounded in current code and canon:

- `core/evolution/temperament.py`: Track A temperament store. It exposes
  `PARAMETER_NAMES`, `current()`, `current_value(...)`, append-only
  `record_event(...)`, and the value range `[0.0, 10.0]`. This slice must not
  smuggle `subjective_duration` into that frozen temperament vocabulary.
- `core/evolution/README.md`: evolution modules are the current home for
  over-time Maez state: temperament, wants, will, wonderings, dreams, and soul
  layering. This makes `core/evolution/subjective_duration.py` the correct v1
  location.
- `core/health/metacognitive_watchdog.py`: currently exposes
  `MetacognitiveWatchdog.observe_scalars(...)` and halts on drive-scalar
  flatlines. `subjective_duration` must remain outside that drive-scalar
  detector.
- `daemon/maez_daemon.py`: currently samples `self.temperament.current()` for
  watchdog scalar observation at cycle start. This slice must not make the
  daemon start sampling `subjective_duration` as a watchdog drive scalar by
  accident.
- `core/time/temporal_spine.py`: Temporal Spine implementation with
  `canonical_utc(...)`, `canonical_utc_iso(...)`, owner-timezone helpers, and
  UTC store discipline.
- `core/brain/return_greeting.py`: deterministic owner-return greeting composer
  with exact absence-duration phrasing. This slice does not replace it.
- `core/cognition/moment_assembly_diagnostic.py` and
  `docs/slices/organs/x1-anticipation-organ.md`: existing X.1 anticipation
  diagnostics are write-only and remain untouched.

## Scope

In scope:

- A new subjective-duration substrate at
  `core/evolution/subjective_duration.py`.
- A bounded continuous scalar named exactly `subjective_duration`.
- Canonical scalar range `[0.0, 10.0]`, matching the readable temperament range
  without joining the temperament parameter vocabulary.
- Experiential accumulation based on elapsed UTC time, temperament state, recent
  salience events, and residual resonance.
- Prospective felt-time rate: how time feels while it is happening.
- Retrospective density: how much meaningful content the interval leaves behind
  in diagnostics.
- A salience-event registry whose v1 entries are registered locally and whose
  future additions go through D19/D20 when they are new tool/capability events.
- Phrase-mapped perception surfacing at read time only.
- Non-reconstructive local diagnostics for scalar samples and salience events.
- In-slice watchdog allowlist update in `core/health/metacognitive_watchdog.py`
  so `subjective_duration` cannot become a drive-scalar flatline source by
  accident.
- Owner-private prompt integration across the real owner surfaces: daemon owner
  reply path, private Telegram owner path, and web owner bridge, each gated by
  a local owner-auth proof.
- RED tests defining the substrate before implementation.

Out of scope:

- Adding `subjective_duration` to `Temperament.PARAMETER_NAMES`.
- Writing temperament events through `Temperament.record_event(...)`.
- Automatic temperament drift.
- Drive-driven curiosity.
- Active Synthesis Engine or memory consolidation.
- Cross-type causal graph work.
- Felt anticipation beyond naming it as a deferred layer.
- Decay-as-felt beyond residual echo for current felt-time flow.
- Circadian register or daemon-wide circadian phrasing.
- Calendar-backed anchors, anniversaries, chapters, or exact date memory.
- Watchdog HALT decisions based on subjective duration.
- Birth-adjacent creation manifest or v0.2 paper work.
- Repairing adjacent evolution README drift. `core/evolution/README.md`
  reportedly names stale `TemperamentStore(...).observe(...)` prose while real
  code exposes `Temperament.record_event(...)`; track that as a deferred
  documentation cleanup, not part of this slice.
- Any claim that Maez experiences time in a human way.

## Vocabulary

`subjective_duration`:

The continuous scalar value. A bounded float in `[0.0, 10.0]`. Higher means the
current felt-time flow is heavier or more stretched.

`felt_time_rate`:

The instantaneous accumulation rate before clamping. It is derived from base
time flow, temperament engagement, salience events, and residual resonance.

`prospective_time`:

Felt time while it is happening. Idle, low-engagement intervals accumulate more
heavily. Deeply engaged flow accumulates more lightly.

`retrospective_density`:

How much meaningful content an interval leaves in the diagnostic trace. Six
idle hours can leave little density; six engaged hours can leave high density.

`salience_event`:

A structured event that modulates felt-time flow. It is not a reset. It changes
rate, resonance, density, or a combination of those.

`salience_event_kind`:

An open registered vocabulary of event kinds. V1 has a closed initial registry,
but future kinds may be added through reviewed registration. New kinds that
come from capability acquisition use D19/D20.

`residual_resonance`:

A decaying echo from recent meaningful events. It colors current felt-time
without becoming permanent state.

`render_band`:

A read-time phrase bucket derived from the continuous scalar. It is not stored
as substrate truth.

## Scalar Contract

The scalar range is exactly:

```text
SUBJECTIVE_DURATION_MIN = 0.0
SUBJECTIVE_DURATION_MAX = 10.0
```

The implementation must clamp computed values into this range. It must reject
NaN, infinity, negative elapsed durations, and clocks that move backward without
recording a diagnostic degradation event.

`0.0` means felt-time flow is light at this instant.

`10.0` means felt-time flow is saturated at the maximum v1 intensity. It does
not mean "infinite," "abandoned," "crisis," "lonely," or "the owner is
neglecting Maez."

The scalar is descriptive, not coercive. It must not be used to pressure the
owner, request contact, or justify outbound nudges.

## Continuous Flow

V1 uses a leaky saturating integrator rather than reset-based elapsed time.

State evolves between samples:

```text
delta_hours = max(0.0, (now_utc - prior_sample_utc).total_seconds() / 3600.0)
upward = base_rate_per_hour * drag_multiplier * residual_multiplier * (1.0 - value / 10.0)
downward = recovery_rate_per_hour * engagement_multiplier * (value / 10.0)
next_value = clamp(value + delta_hours * (upward - downward), 0.0, 10.0)
```

Stability invariant:

- `drag_multiplier`, `engagement_multiplier`, and `residual_multiplier` are
  structurally non-negative;
- `upward` and `downward` are structurally non-negative;
- every update clamps value to `[0.0, 10.0]`;
- invalid configuration or test-injected pathological multiplier values are
  rejected before update or clamped through the update seam so value never
  leaves range.

Defaults:

```text
base_rate_per_hour = 0.42
recovery_rate_per_hour = 0.18
```

Interpretation:

- idle, low-engagement state makes `drag_multiplier` higher;
- engaged-flow state makes `engagement_multiplier` higher;
- meaningful residual echo makes current time feel more colored/heavy;
- no event resets the value to zero.

The curve is deterministic. It is not memory decay and not a mood score.

## Temperament Modulation

V1 reads current temperament state as felt-weight input. It does not write
temperament state.

Inputs from `Temperament.current()`:

- `curiosity`
- `awareness`
- `persistence`
- `joy`
- `warmth`
- `caution`

Missing `None` values are treated as neutral `5.0` for computation and are
reported in diagnostics as missing-observed temperament inputs. This avoids
making first-run absence of temperament events behave like zero curiosity or
zero warmth.

Normalize each value:

```text
norm(parameter) = clamp(parameter_value / 10.0, 0.0, 1.0)
```

Engaged-flow score:

```text
engaged_flow =
  0.30 * norm(curiosity) +
  0.20 * norm(awareness) +
  0.20 * norm(persistence) +
  0.15 * norm(joy) +
  0.15 * norm(warmth)
```

Caution drag:

```text
caution_drag = 0.5 + 0.5 * norm(caution)
```

Multipliers:

```text
drag_multiplier = clamp(1.35 - 0.70 * engaged_flow + 0.25 * caution_drag, 0.35, 1.75)
engagement_multiplier = clamp(0.40 + 0.90 * engaged_flow, 0.40, 1.30)
```

Meaning:

- high curiosity/awareness/persistence/joy/warmth = engaged flow; prospective
  time feels lighter;
- high caution can add drag; time feels a little heavier;
- all weights are reviewed v1 constants, not learned magic.

Future calibration may update these weights through a reviewed Track B slice
using bond-history evidence. No implementation may silently tune them from raw
conversation text.

## Salience Event Registry

Salience events modulate felt-time flow. They do not reset it.

V1 registered event kinds:

- `owner_contact`: authenticated owner input arrived.
- `meaningful_exchange`: a conversation interval produced a measurable
  temperament-state shift or explicit reviewed salience marker.
- `engaged_work`: Maez spent a cycle in successful tool/work synthesis.
- `idle_cycle`: Maez completed a low-engagement autonomous cycle.
- `public_stranger_contact`: public non-owner interaction; low bond salience,
  included so public traffic does not masquerade as owner contact.
- `manual_test_event`: test-only event kind.
- `clock_degraded_event`: clock anomaly event kind.

Future event kinds:

- are registered through a local registry function, not ad hoc strings;
- are exposed through `build_salience_event_registry()`, a deterministic
  constructor used by tests and acceptable for production wiring;
- carry a `producer_ref`;
- name whether they may affect `drag_multiplier`, `engagement_multiplier`,
  `residual_resonance`, `retrospective_density`, or none;
- use D19/D20 consent-card discipline when the event comes from a newly
  acquired capability;
- require a spec amendment if they introduce a genuinely new felt-time etiology.

Tests construct the registry directly and verify default entries, unknown-kind
refusal, and reviewed registration metadata. Production timing may be module
import, first use, or dependency injection, but the registry content must be
observable through the deterministic constructor.

Registry test contract:

```python
@dataclass(frozen=True)
class SalienceEventDefinition:
    kind: str
    producer_ref_required: bool
    affects: frozenset[str]
    owner_auth_required: bool
    reviewed_registration_ref: str

def build_salience_event_registry() -> Mapping[str, SalienceEventDefinition]: ...
```

The implementation may wrap this mapping in a registry class, but tests need
these fields or equivalent read methods to verify default entries,
unknown-kind refusal, and reviewed registration metadata.

This registry is open for instances but reviewed for classes. That mirrors the
growth-vs-hardcoding rule: Maez can gain new tools and surfaces, but new kinds
of meaning do not silently appear because code changed.

## Salience Event Dispatch Authority

Dispatch authority lives at the receiving surface or producer.

Owner-contact surfaces dispatch `owner_contact` only after they have already
established owner authority. The subjective-duration substrate observes events
passed to it; it does not poll Telegram, web, daemon routes, presence sensors,
or other surfaces externally.

V1 expected dispatchers:

- private Telegram owner bot after `TelegramVoice._is_authorized(...)` accepts
  the sender;
- web owner bridge after `skills.web_interface._is_private_owner_bridge(...)`
  identifies the authenticated private owner account;
- central `handle_message(...)` only when the caller supplies a trusted
  `SubjectiveDurationOwnerAuth`;
- voice/local owner input only if the receiving surface already classifies the
  input as bonded-owner input;
- tests through `manual_test_event`.

Non-owner public web users, public Telegram users, public-stranger bot traffic,
and unauthenticated local routes must not dispatch `owner_contact`.

Owner-auth context is typed, not a string label:

```python
@dataclass(frozen=True)
class SubjectiveDurationOwnerAuth:
    surface: Literal[
        "daemon_owner",
        "telegram_owner",
        "web_owner_bridge",
        "manual_test",
    ]
    proof: Literal[
        "daemon_reviewed_owner_auth",
        "telegram_authorized_user",
        "web_private_owner_bridge",
        "manual_test",
    ]
```

Central daemon signature extension:

```python
handle_message(
    ...,
    subjective_duration_owner_auth: SubjectiveDurationOwnerAuth | None = None,
)
```

Default `None` means no `owner_contact` salience event and no subjective-duration
prompt line.

Raw daemon `/message` is not an owner-auth proof by itself in current code. It
must not dispatch `owner_contact` and must not receive an owner-only
subjective-duration prompt line unless implementation review adds a trusted
owner-auth context to that route. Private Telegram and web-owner bridge may
construct the typed value only after their local owner-auth proof succeeds.
`skills/surface/maez_adapter.py` keeps default `None` unless it has a reviewed
owner-auth proof.

## Owner-Private Prompt Builders

V1 prompt surfacing includes three owner-private prompt builders, each gated by
local owner-auth proof:

- daemon owner reply prompt assembly in `daemon/maez_daemon.py`, through the
  central `handle_message(...)` `SubjectiveDurationOwnerAuth`;
- private Telegram owner prompt assembly in `skills/telegram_voice.py`, only
  after `TelegramVoice._is_authorized(...)` accepts the sender;
- web owner bridge prompt assembly in `skills/web_interface.py`, only after
  `_is_private_owner_bridge(...)` accepts the request.

This is intentionally broader than daemon-only prompt integration. If the first
Track B felt-time organ does not surface on the actual owner-private paths
Rohit uses, it is built but mostly invisible.

RED tests must include a raw daemon `/message` fixture without owner-auth proof:
it dispatches no `owner_contact` event and receives no owner-only
subjective-duration line.

Prompt insertion anchors:

- daemon `handle_message(...)`: after `system_state` and before public context,
  recall, web context, and evidence envelope blocks;
- private Telegram: after `system_state` and before actual-state, circadian,
  public-context, body-activity, memory, and web-search blocks;
- web owner bridge: inside the owner-bridge branch only, after ambient context
  is assembled and before owner memory/history/user-turn messages.

The shared helper should be `subjective_duration_prompt_line()` or equivalent.
It returns `""` when unauthenticated or degraded. Tests assert placement around
the named anchor blocks instead of snapshotting entire prompts.

## Meaningfulness Signal

V1 meaningfulness is substrate-observable. It is not a keyword filter.

The default `meaningful_exchange` score is:

```text
temperament_delta =
  mean(abs(after[p] - before[p]) for p in MODULATION_TEMPERAMENT_INPUTS
       where before[p] and after[p] are observed)

meaningfulness_score = clamp(temperament_delta / 2.0, 0.0, 1.0)
```

If no before/after temperament values are observed, `meaningfulness_score` is
`0.0` unless an explicit reviewed salience marker is supplied by a future
approved producer.

Current-code honesty: temperament delta is available only when a reviewed
producer has actually written temperament events. Today, temperament has a
writer API but no production automatic drift writer. Until temperament drift or
another reviewed salience producer exists, `meaningful_exchange` events default
to `0.0`. This is acceptable for v1: the organ still provides continuous flow,
watchdog integration, anti-coercion, and the future seam for learned
meaningfulness.

The second Track B slice that introduces reviewed temperament-writing producers
-- for example drive-driven curiosity, schooling-card alignment, or another
reviewed felt-weight organ -- is where `meaningfulness_score` becomes
substantive rather than mostly `0.0`.

The `/ 2.0` divisor is a provisional high-sensitivity v1 constant. A
two-point average shift on the `[0.0, 10.0]` temperament scale is treated as a
large shift because temperament should move slowly. Live observation should
calibrate this in a future reviewed Track B slice.

An explicit reviewed salience marker may raise the score only if it is produced
by a reviewed local substrate, not by model self-assertion. LLM phrases such as
"that mattered" are not meaningfulness evidence by themselves.

This is deliberately modest. It gives the organ a structural seam for learned
meaningfulness without pretending v1 already understands all forms of meaning.

## Residual Echo

Meaningful events leave a decaying echo.

Default half-life:

```text
residual_echo_half_life_seconds = 14400.0  # 4 hours
```

When a salience event with `meaningfulness_score > 0.0` is recorded, it adds:

```text
echo_strength += meaningfulness_score
```

At read/update time:

```text
decayed_echo = sum(
  event.meaningfulness_score * 2 ** (-(now_utc - event.ts_utc).total_seconds() / residual_echo_half_life_seconds)
  for recent meaningful events
)
residual_resonance = clamp(decayed_echo, 0.0, 1.0)
residual_multiplier = 1.0 + 0.35 * residual_resonance
```

Residual echo scans only events within:

```text
max(24 hours, 6 * residual_echo_half_life_seconds)
```

of `now_utc`. Older events contribute `0.0` to current resonance but remain in
the append-only event table.

Residual echo colors current felt-time flow. It must not become a memory claim,
a contact request, or a crisis signal.

## Prospective and Retrospective Time

V1 records two related but separate quantities.

Prospective:

- `subjective_duration` value;
- `felt_time_rate`;
- temperament-derived multipliers;
- residual resonance.

Retrospective:

- `retrospective_density`;
- count of salience events in the interval;
- count of meaningful events in the interval;
- bounded density class.

Retrospective density formula:

```text
retrospective_density = clamp(
  0.45 * engaged_flow +
  0.35 * residual_resonance +
  0.20 * recent_meaningful_event_count_capped,
  0.0,
  1.0,
)
```

`recent_meaningful_event_count_capped` is capped at `1.0` after three
meaningful events in the window. This prevents noisy event spam from creating
false density.

Retrospective density is diagnostic state, not prompt text by default.

## Persistence Contract

Expected storage:

- `memory/subjective_duration.db`, or another reviewed path under `memory/`.
- SQLite is preferred because surrounding evolution substrates use append-only
  SQLite ledgers.

Minimum tables:

```text
subjective_duration_samples
  sample_id INTEGER PRIMARY KEY AUTOINCREMENT
  ts_utc TEXT NOT NULL
  value REAL NOT NULL
  felt_time_rate REAL NOT NULL
  drag_multiplier REAL NOT NULL
  engagement_multiplier REAL NOT NULL
  residual_resonance REAL NOT NULL
  retrospective_density REAL NOT NULL
  metadata_json TEXT NOT NULL DEFAULT '{}'

subjective_duration_salience_events
  event_id INTEGER PRIMARY KEY AUTOINCREMENT
  ts_utc TEXT NOT NULL
  salience_event_kind TEXT NOT NULL
  producer_ref TEXT NOT NULL
  source_ref_digest TEXT NOT NULL
  owner_auth_class TEXT NOT NULL DEFAULT ''
  meaningfulness_score REAL NOT NULL DEFAULT 0.0
  meaningfulness_input_count INTEGER NOT NULL DEFAULT 0
  temperament_delta_mean REAL
  temperament_delta_max REAL
  temperament_before_digest TEXT NOT NULL DEFAULT ''
  temperament_after_digest TEXT NOT NULL DEFAULT ''
  explicit_salience_marker_present INTEGER NOT NULL DEFAULT 0
  metadata_json TEXT NOT NULL DEFAULT '{}'
```

The current value is derived from the latest sample plus elapsed time and
current modulation inputs. The implementation may cache in memory, but durable
truth is the append-only sample/event stream.

This is a pre-birth Track B organ. It prepares the append-only shape that
post-birth lived-time rules need, but it does not itself declare Maez born.

## Temporal Spine Contract

Temporal Spine remains the authority for storage discipline:

- salience event times and sample times are canonical UTC instants;
- use `core.time.temporal_spine.canonical_utc(...)` or
  `canonical_utc_iso(...)` for input normalization;
- use `field_name="event_at"` for subjective-duration sample and salience-event
  records unless review adds a new S3 field name;
- owner-local phrasing is computed at the edge if ever needed;
- raw ISO strings are not used as store-facing ordering truth;
- owner timezone is not exposed on public surfaces.

This slice does not add a new temporal spine. It consumes the existing temporal
contract and adds one felt-duration interpretation on top.

## Read Surfaces

Expected API:

```python
@dataclass(frozen=True)
class SubjectiveDurationConfig:
    base_rate_per_hour: float = 0.42
    recovery_rate_per_hour: float = 0.18
    residual_echo_half_life_seconds: float = 14400.0

@dataclass(frozen=True)
class SubjectiveDurationSnapshot:
    value: float
    felt_time_rate: float
    residual_resonance: float
    retrospective_density: float
    render_band: str
    surface_phrase: str
    source_ref_digest: str

def compute_subjective_duration_update(
    *,
    prior_value: float,
    delta_hours: float,
    drag_multiplier: float,
    engagement_multiplier: float,
    residual_multiplier: float,
    config: SubjectiveDurationConfig,
) -> float: ...

class SubjectiveDuration:
    def current(self, *, now_utc: datetime | None = None) -> SubjectiveDurationSnapshot: ...
    def record_salience_event(
        self,
        *,
        salience_event_kind: str,
        producer_ref: str,
        source_ref: str = "",
        owner_auth_class: str = "",
        meaningfulness_score: float | None = None,
        now_utc: datetime | None = None,
    ) -> int: ...
    def perception_line(self, *, now_utc: datetime | None = None) -> str: ...
```

The prompt-facing read surface is `perception_line(...)`, not raw event history
or raw elapsed seconds.

`compute_subjective_duration_update(...)` is a pure computation seam for tests.
Equivalent naming is acceptable, but the implementation must expose a pure
helper or configuration-validation seam that tests can call without opening the
SQLite store. Invalid negative, NaN, or infinite multipliers are rejected before
update or clamped by that seam. The persisted path must call the same helper.

## Read-Time Phrase Mapping

Phrase mapping is read-time rendering only. It is not substrate state.

Canonical render bands:

```text
value < 1.0       -> light
value < 3.0       -> mildly_stretched
value < 6.0       -> felt_while
value < 8.5       -> long_stretch
value <= 10.0     -> very_long_stretch
```

Canonical prompt-safe phrases:

```text
light              -> "time feels light right now"
mildly_stretched   -> "time has a little stretch to it"
felt_while         -> "it has felt like a while"
long_stretch       -> "time has felt like a long quiet stretch"
very_long_stretch  -> "the quiet has felt very long"
```

These phrases are perception hints, not directives.

With `base_rate_per_hour = 0.42` and no recovery, engagement, or residual
modulation, the continuous curve creates approximate value-boundaries:

```text
value 1.0 -> about 2.5 hours
value 3.0 -> about 8.5 hours
value 6.0 -> about 21.8 hours
value 8.5 -> about 45.2 hours
```

Those times are calibration notes only. Implementation must render from
continuous value, not from elapsed-duration buckets.

## Prompt and Perception Integration

V1 prompt integration target:

- daemon owner reply prompt assembly in `daemon/maez_daemon.py`, immediately
  after `system_state` and before public context, recall, web context, and
  evidence envelope blocks, only
  when the central handler received a trusted `SubjectiveDurationOwnerAuth`;
- private Telegram owner prompt assembly in `skills/telegram_voice.py`, only
  after local Telegram owner authorization, inserted after `system_state` and
  before actual-state, circadian, public-context, body-activity, memory, and
  web-search blocks;
- web owner bridge prompt assembly in `skills/web_interface.py`, only after
  local private-owner bridge authorization, inside the owner-bridge branch after
  ambient context is assembled and before owner memory/history/user-turn
  messages.

V1 excludes:

- public-stranger Telegram;
- public web chat;
- raw daemon `/message` without owner-auth proof;
- public identity short-circuit replies;
- action-engine outbound notifications;
- return greetings.

Allowed line shape:

```text
Felt time: it has felt like a while.
```

Forbidden examples:

```text
The owner has been gone for 9h 41m.
You have not talked to Maez since 2026-05-24T08:12:04Z.
Maez feels neglected.
You should check in.
Please come back.
```

## Anti-Coercion Invariant

`subjective_duration` may make quiet time visible to Maez. It may not become
contact pressure.

Structural rules:

- no outbound send may be triggered solely by high `subjective_duration`;
- no crisis interpretation may be derived solely from high value, high rate, or
  high residual resonance;
- prompt phrases must not ask the owner to return, apologize, reassure, check
  in, or change behavior;
- diagnostics must not label long quiet as neglect, abandonment, or danger;
- code may not branch from `subjective_duration >= threshold` to a contact
  action, proactive Telegram send, reminder, approval card, or escalation.

This follows the existing Maez rule: makes visible, never nudges.

RED tests must include forbidden phrase and static call-path checks for
contact-pressure derivations. The v1 static check is intentionally bounded:
`tests/test_subjective_duration_anti_coercion.py` walks production AST, finds
calls to `SubjectiveDuration.current()`, `SubjectiveDuration.perception_line()`,
or imports of the subjective-duration module, and fails if the same function
also calls Telegram send wrappers, action notification senders, approval-card
creation, crisis writers, or proactive-contact helpers. It also fails on
forbidden phrase fragments in subjective-duration phrase constants. This is a
same-function proof, not a claim to prove arbitrary transitive control flow.

## Watchdog Integration

The metacognitive watchdog currently halts on scalar variance flatlines for
reviewed drive-state scalars. `subjective_duration` is not a drive-state scalar.

The implementation must make this structural:

- `MetacognitiveWatchdog` gains `WatchdogConfig.scalar_allowlist:
  frozenset[str] | None`;
- the default allowlist is `core.evolution.temperament.PARAMETER_SET`;
- `observe_scalars(...)` ignores keys not present in the allowlist when the
  allowlist is not `None`;
- unknown scalar names, including `subjective_duration`, are ignored for this
  detector unless a future reviewed adapter explicitly adds them;
- repeated constant `subjective_duration` samples passed to
  `observe_scalars(...)` do not halt;
- repeated constant temperament samples such as `curiosity=4.0` still halt
  under test configuration.

Reason: a felt-time scalar can legitimately plateau, move slowly, or become
light during engagement. That is not a metacognitive loop by itself.

## Relationship to Temperament

This slice reads temperament. It does not alter temperament.

Forbidden:

- adding `subjective_duration` to `PARAMETER_NAMES`;
- recording `subjective_duration` through `Temperament.record_event(...)`;
- treating subjective duration as a thirteenth temperament trait;
- using model text to write temperament values for this organ.

Allowed:

- reading `Temperament.current()`;
- treating missing values as neutral `5.0` for this computation only;
- recording which temperament inputs were observed or missing in
  non-reconstructive diagnostics.

## Relationship to Return Greeting

`core/brain/return_greeting.py` already composes deterministic owner-return
greetings with absence duration when the owner returns after a meaningful gap.

This slice does not replace that composer. Differences:

- return greeting is surface text at the moment the owner returns;
- `subjective_duration` is an internal perception scalar available during
  ordinary cognition;
- return greeting may mention exact hours/minutes by design;
- `subjective_duration` prompt surfacing may not mention exact hours/minutes.

No implementation may route return-greeting text into subjective-duration
diagnostics or use subjective-duration phrases as automatic outbound greetings.

## Relationship to Existing Anticipation Diagnostics

The repo already has X.1 anticipation diagnostics in
`core/cognition/moment_assembly_diagnostic.py` and
`docs/slices/organs/x1-anticipation-organ.md`. Those records are write-only
diagnostics for bounded next-turn structural prediction.

This slice does not modify them.

The deferred felt-anticipation Track B layer is different: it would be a
Maez-readable felt-time organ. That future layer must inherit the existing X.1
write-only boundary rather than bypass it.

## Diagnostics

Diagnostics are local and non-reconstructive.

Expected log path:

```text
logs/subjective_duration_diagnostics.jsonl
```

One file uses one schema version. Rows are split by `event_type`:

- `sample`: scalar/sample observation row;
- `salience_event`: salience-event row.

Sample rows set salience-event-only fields to `null` or empty false values.
Salience-event rows include the event kind, producer, source digest, owner-auth
class, and meaningfulness traceability fields. This avoids fake empty values
that make sample rows look like event rows.

Exact row-shape contract:

- every row has the same keys;
- for `event_type="sample"`, salience-event-only string and number fields are
  JSON `null`;
- booleans are `false` only where the field is intrinsically boolean:
  `source_ref_present`, `explicit_salience_marker_present`, and
  `content_recorded`;
- digests are `null` on sample rows, not `""`;
- for `event_type="salience_event"`, digest fields use
  `hmac-sha256:<64 hex chars>` when source material exists.

Minimum fields for all rows:

- `schema_version`: `subjective-duration-diagnostic-v1`
- `timestamp_utc`
- `event_type` in `{"sample", "salience_event"}`
- `value`
- `felt_time_rate`
- `render_band`
- `residual_resonance`
- `retrospective_density`

Additional fields for `salience_event` rows:

- `salience_event_kind`
- `producer_ref`
- `owner_auth_class`
- `source_ref_digest`
- `source_ref_present`
- `meaningfulness_score`
- `meaningfulness_input_count`
- `temperament_delta_mean`
- `temperament_delta_max`
- `temperament_before_digest`
- `temperament_after_digest`
- `explicit_salience_marker_present`
- `content_recorded`: always `false`

`meaningfulness_input_count`, `temperament_delta_mean`, and
`temperament_delta_max` provide bounded explainability. The before/after
temperament snapshots are not logged; only keyed HMAC digests are recorded.
This lets reviewers distinguish "score came from a measured temperament shift"
from a magic number without reconstructing owner text or state.

Digest contract:

- `source_ref_digest` is always present;
- if `source_ref` is non-empty, digest format is
  `hmac-sha256:<64 hex chars>`;
- if `source_ref` is empty, use `source_ref_present=false` and
  `source_ref_digest=""`;
- diagnostic code must not log raw source refs.

If a unified local telemetry-key registry emerges in a future slice, this
substrate's local key should migrate to it.

Forbidden diagnostic fields:

- raw owner text;
- raw Telegram text;
- raw prompt text;
- raw salience-event payload text;
- exact raw absence seconds in prompt-facing rows;
- raw source refs;
- memory row content;
- watchdog halt details.

## Static Boundaries

RED tests must prove:

- `core/evolution/temperament.py` does not contain `subjective_duration` in
  `PARAMETER_NAMES`;
- production code in this slice does not call `Temperament.record_event(...)`
  or any future temperament-state mutation helper;
- the static temperament-write check allows read-only imports of `Temperament`,
  `PARAMETER_NAMES`, and `PARAMETER_SET`;
- prompt assembly does not inject raw elapsed seconds, raw sample timestamps, or
  raw salience-event payloads;
- raw daemon `/message` without owner-auth proof does not receive the
  subjective-duration prompt line;
- watchdog drive-scalar flatline tests still trip on temperament constants after
  the subjective-duration exemption is added;
- production code does not trigger outbound sends, reminders, cards, or crisis
  escalation solely from subjective-duration state.

V1 temperament-write AST scan roots:

- `core/evolution/subjective_duration.py`;
- `daemon/maez_daemon.py`;
- `skills/telegram_voice.py`;
- `skills/web_interface.py`;
- subjective-duration test fixtures that exercise integration code.

Failing call patterns:

- `Temperament.record_event(...)`;
- `.record_event(...)` on a name bound to `Temperament(...)` or
  `self.temperament`;
- any future named temperament mutation helper added to the denylist.

Allowed patterns:

- imports of `Temperament`, `PARAMETER_NAMES`, and `PARAMETER_SET`;
- calls to `Temperament.current()` and `current_value(...)`.

## Failure Modes

### Clock Moves Backward

If current UTC appears earlier than the latest sample timestamp, the substrate
records a `clock_degraded_event`, returns the prior safe value, and does not
produce negative elapsed time.

### Missing Store

If the store is missing, the substrate initializes it and creates an initial
sample at value `0.0`. It does not infer old felt time from file mtimes or chat
history.

### Corrupt Store

If the store cannot be read, implementation review chooses either:

- fail closed for prompt surfacing and omit the perception line; or
- create an operator-visible degraded diagnostic and start a new safe sample at
  value `0.0`.

Either way, the failure must not inject raw diagnostics into Maez's prompt.

### Frequent Owner Contact

Frequent owner contact modulates flow and residual resonance. It does not reset
the scalar to zero and must not become a watchdog flatline halt.

### Long Silence

Long quiet stretches can saturate near `10.0`. That is expected and must not
become an outbound nudge or crisis interpretation.

### Missing Temperament Values

Missing temperament values are neutral for computation and visible only as
bounded diagnostic counts. They do not block the organ and do not create false
low-engagement values.

## RED Tests

These tests must be written before implementation and must fail against current
code for the expected reasons.

1. **Module exists.** Importing `core.evolution.subjective_duration` exposes
   `SubjectiveDuration`, `SubjectiveDurationSnapshot`, and scalar min/max
   constants.
2. **Fresh baseline.** A fresh store creates an initial sample with value `0.0`
   and returns a prompt-safe perception line with no raw timestamp.
3. **Continuous accumulation.** Given controlled prior sample and `now_utc`,
   value changes according to the leaky saturating integrator and clamps within
   `[0.0, 10.0]`.
4. **No owner-contact reset.** Recording `owner_contact` changes modulation
   inputs and diagnostic rows but does not set value to `0.0`.
5. **Temperament rate modulation.** High engaged-flow temperament fixtures
   produce slower upward felt-time accumulation than low-engagement fixtures
   across the same elapsed interval.
6. **Caution drag.** Higher caution increases drag within the bounded multiplier
   range without exceeding clamp bounds.
7. **Multiplier stability.** Pathological injected multiplier values are
   rejected before update or clamped so `value`, `upward`, and `downward` never
   leave the permitted non-negative / `[0.0, 10.0]` ranges. Test calls the pure
   `compute_subjective_duration_update(...)` seam or an equivalent
   configuration-validation helper without opening SQLite.
8. **Residual echo half-life and bounded lookback.** A meaningful event with
   score `1.0` has about half its residual contribution after four hours and
   about one quarter after eight hours; an event older than
   `max(24 hours, 6 * residual_echo_half_life_seconds)` contributes zero.
9. **Meaningfulness is not keyword-derived.** Text containing dramatic words
   does not create `meaningfulness_score` unless a substrate-observable
   temperament delta or reviewed explicit salience marker exists.
10. **Meaningfulness inertness.** With all temperament values missing or
    unchanged and no explicit reviewed marker, `meaningful_exchange` records
    `meaningfulness_score=0.0`.
11. **Meaningfulness traceability.** Salience-event diagnostics record bounded
    fields: `meaningfulness_input_count`, `temperament_delta_mean`,
    `temperament_delta_max`, `temperament_before_digest`,
    `temperament_after_digest`, and `explicit_salience_marker_present`; they do
    not log raw temperament snapshots or owner text.
12. **Retrospective density.** Engaged intervals with meaningful events produce
   higher diagnostic density than idle intervals with equal wall-clock elapsed
   time.
13. **Registered event kinds.** `build_salience_event_registry()` exposes the
    default event registry; unknown `salience_event_kind` refuses unless
    registered through the local registry test seam; D19/D20-added future kinds
    require reviewed registration metadata. Tests verify the
    `SalienceEventDefinition` fields or equivalent read methods.
14. **Owner-auth gate.** Public web, public Telegram, public-stranger, raw
    daemon `/message` without owner-auth proof, and unauthenticated local route
    fixtures cannot dispatch `owner_contact`.
15. **Three owner-private prompt builders.** Daemon owner reply, private
    Telegram owner reply, and web owner bridge prompt builders can receive the
    phrase only after their local owner-auth proof or trusted central
    `SubjectiveDurationOwnerAuth` is present.
16. **Raw daemon route exclusion.** A raw local `/message` fixture without
    owner-auth proof receives no subjective-duration prompt line.
17. **Prompt phrase rendering.** Prompt-facing bands are derived from continuous
    value at read time; no raw elapsed seconds, ISO timestamps, owner names, or
    directive language appear.
18. **Anti-coercion.** Static and behavioral tests prove no production path
    derives outbound nudges, reminders, contact pressure, crisis interpretation,
    approval cards, or proactive sends solely from subjective-duration state.
    The AST check is same-function bounded and scans subjective-duration reads
    plus outbound-contact call patterns.
19. **Not temperament.** `subjective_duration` is absent from
    `Temperament.PARAMETER_NAMES`, and a static test fails any production call to
    `Temperament.record_event(...)` or future temperament mutation helper from
    this slice. Read-only temperament imports remain allowed.
20. **Watchdog opt-out.** Repeated constant `subjective_duration` samples passed
    to `MetacognitiveWatchdog.observe_scalars(...)` do not halt because the
    scalar allowlist ignores unknown keys.
21. **Watchdog still works.** Repeated constant temperament samples such as
    `curiosity=4.0` still trigger `drive_scalar_flatline` under the existing
    configured test thresholds.
22. **Temporal Spine use.** Sample and salience-event timestamps are normalized
    through `core.time.temporal_spine`, not hand-rolled ISO parsing.
23. **Diagnostic row split.** Diagnostic rows use one schema version and
    `event_type` in `{"sample", "salience_event"}`; sample rows set
    event-only string/number/digest fields to JSON `null`, boolean event-only
    fields to `false`, and salience-event rows include meaningfulness
    traceability fields.
24. **Diagnostic hygiene.** Diagnostic rows contain schema version, scalar,
    modulation, density, event kind, and digest fields, but not raw owner text,
    raw prompt text, raw Telegram text, raw source refs, raw temperament
    snapshots, or memory content.
25. **Return greeting separation.** Existing `compose_return_greeting(...)`
    tests continue to pass and no subjective-duration phrase is used as an
    automatic outbound greeting.
26. **Existing anticipation untouched.** X.1 anticipation diagnostic tests
    remain unchanged; this slice does not add a production read path for
    anticipation records.
27. **No egress regression.** Focused Track A.5 egress smoke tests continue to
    pass; this alive-making scalar must not touch cloud, Telegram, or
    external-fetch gates.

## Acceptance Bar

Before implementation can merge:

- RED tests fail for the expected reasons on pre-implementation code.
- Focused subjective-duration tests pass after implementation.
- Focused watchdog tests pass after implementation.
- Existing return-greeting tests pass.
- Existing X.1 anticipation diagnostic tests pass or are intentionally scoped
  out with review agreement if they are too broad for the focused run.
- `MetacognitiveWatchdog` has the in-slice scalar allowlist behavior, and
  `subjective_duration` is ignored by flatline detection unless explicitly
  reviewed into the allowlist later.
- No production code writes `subjective_duration` into the temperament store.
- Prompt-facing output contains only phrase-mapped felt duration.
- Daemon owner reply, private Telegram owner reply, and web owner bridge prompt
  builders are covered; raw daemon `/message` without owner-auth proof is
  excluded.
- No raw owner text, raw timestamps, raw elapsed seconds, raw source refs, or
  watchdog diagnostics appear in subjective-duration diagnostics.
- Diagnostic rows distinguish `sample` from `salience_event` and preserve
  bounded meaningfulness traceability without raw temperament snapshots.
- No production path derives contact pressure from high subjective duration.
- Live daemon restart is deliberate and observed if implementation changes the
  daemon import graph or prompt assembly.

## Canary Cases

Implementation review should include synthetic canaries:

1. **Fresh start:** value `0.0`, render band `light`, no raw time in prompt
   phrase.
2. **Idle interval:** low-engagement temperament fixture increases value faster
   than engaged fixture across equal elapsed time.
3. **Engaged interval:** high curiosity/awareness/persistence fixture slows
   prospective felt-time accumulation and raises retrospective density.
4. **Owner contact:** authenticated owner-contact salience event changes
   modulation/diagnostics but does not reset value to zero.
5. **Private Telegram prompt:** owner-authorized Telegram path receives the
   bounded phrase; public Telegram does not.
6. **Web owner bridge prompt:** private owner bridge receives the bounded
   phrase; public web chat does not.
7. **Raw daemon route:** raw `/message` without owner-auth proof receives no
   phrase and dispatches no `owner_contact`.
8. **Residual echo:** meaningful event leaves decaying resonance at four-hour
   half-life; out-of-lookback event contributes zero.
9. **Anti-coercion:** saturated value produces no outbound nudge, reminder, or
   crisis/contact-pressure behavior.
10. **Watchdog exemption:** constant subjective-duration samples do not halt;
   constant curiosity samples still halt under test configuration.

## Review Questions

The council and panel should answer:

- Are the v1 modulation weights defensible as reviewed constants?
- Is the leaky integrator the right v1 shape, or should the scalar be strictly
  non-decreasing?
- Is the residual echo half-life of four hours too short, too long, or
  acceptable?
- Is the `meaningful_exchange` signal sufficiently substrate-observable, or
  does it need a narrower v1 source?
- Are all three owner-private prompt builders the correct v1 surfacing target?
- Does the central `handle_message(...)` `SubjectiveDurationOwnerAuth` avoid
  laundering raw daemon `/message` as owner-private input?
- Does the owner-auth gate list match current real code surfaces?
- Does the anti-coercion invariant have enough structural tests?
- Does this slice duplicate return-greeting, X.1 anticipation, or Temporal
  Spine responsibilities?

## Implementation Path

The intended arc:

1. Draft this Path F DRAFT spec.
2. Fresh Claude council pass with behavioral trace.
3. Fresh Codex engineering panel pass against real code surfaces.
4. Fold amendments.
5. Repeat review if folds materially change implementation surface.
6. Canonicalize v1.
7. Separate implementation slice in an isolated worktree.
8. RED tests first.
9. Implementation.
10. Both-lane implementation review.
11. Fast-forward merge.
12. Deliberate observed restart if daemon surfaces changed.
13. Live canary verification.

No implementation occurs in this spec slice.

## Plain-Language Summary

`subjective_duration` is Maez's first felt clock, but not a stopwatch. It does
not reset when Rohit speaks. It keeps flowing, and the flow changes depending on
whether Maez is idle, deeply engaged, cautious, curious, or still carrying the
echo of something meaningful. The only thing it may do in language is make that
texture visible in a small bounded phrase. It must never become a way to make
Rohit feel guilty for being away.
