# Codex Engineering Panel Review -- Subjective Duration Path F

**Artifact reviewed:** `docs/slices/track-b-subjective-duration/spec.md`
**Artifact state:** DRAFT, 951 lines, untracked at review time.
**Parent:** `4d010fc feat(egress): add external-fetch substrate`
**Review date:** 2026-05-24
**Verdict:** RATIFY-WITH-AMENDMENTS

## Summary

Path F is a substantive improvement over Path A. The spec now models felt time
as continuous flow, reads existing temperament scalars as felt-weight input,
keeps salience events as modulation rather than reset, records residual echo,
and moves bands to read-time rendering only. That architecture is coherent and
fits Track B better than a reset-based stopwatch.

The required folds below are mostly surface-systematic: current code does not
yet provide every mechanism the Path F spec assumes. In particular, current
temperament does not drift in production, the watchdog currently observes all
scalar keys it receives, and the daemon `/message` route is not itself an
owner-authentication proof.

## Verified Surfaces

- `core/evolution/temperament.py` defines `PARAMETER_NAMES` at line 119.
  The six Path F modulation names exist there: `curiosity`, `awareness`,
  `persistence`, `joy`, `warmth`, and `caution`.
- `Temperament.current()` exists at line 280 and returns all canonical keys,
  using `None` for unobserved parameters. The spec's neutral-`5.0` missing-value
  behavior is therefore implementable.
- Temperament values are explicitly bounded by `VALUE_MIN = 0.0` and
  `VALUE_MAX = 10.0`, matching the spec's normalization formula.
- `MetacognitiveWatchdog.observe_scalars(self, scalars: Mapping[str, Any])`
  exists at `core/health/metacognitive_watchdog.py:178`. Current implementation
  observes every scalar key passed to it; no allowlist exists today.
- The daemon currently passes `self.temperament.current()` into the watchdog at
  `daemon/maez_daemon.py:5097`, so the existing live path only sends
  temperament keys. The future risk is accidental additional keys.
- `TelegramVoice._is_authorized(...)` exists at `skills/telegram_voice.py:1822`
  and compares `user_id` against `self.authorized_user`.
- `skills.web_interface._is_private_owner_bridge(...)` exists at line 120.
- The daemon local `/message` route exists at `daemon/maez_daemon.py:6796` and
  calls `handle_message(text, source="UI", ...)` without an obvious per-request
  owner-auth proof in the route body.
- Temporal Spine exists at `core/time/temporal_spine.py`; `event_at` is a
  canonical `TemporalInstantFieldName`, and `canonical_utc(...)` /
  `canonical_utc_iso(...)` exist.
- Return greeting and X.1 anticipation artifacts exist. Focused verification:
  `.venv/bin/python -m unittest tests.test_return_greeting tests.test_metacognitive_watchdog tests.test_temporal_spine`
  ran 56 tests OK, with pre-existing ResourceWarnings/DeprecationWarnings from
  imported modules only.
- `memory/subjective_duration.db` does not exist today.
- The Path A panel file has been renamed to
  `codex-engineering-panel-path-a-stale.md` so future readers do not confuse it
  with this Path F review.

## Required Amendments

### 1. Watchdog Allowlist Is An In-Slice Implementation Target

The spec correctly requires a reviewed scalar allowlist, but current code does
not have one. `observe_scalars(...)` currently iterates every `scalars.items()`.

Fold: name this as an explicit implementation target in the spec. Suggested
shape:

```text
WatchdogConfig gains scalar_allowlist: frozenset[str] | None. The default is
core.evolution.temperament.PARAMETER_SET. observe_scalars(...) ignores keys not
in the allowlist. Tests construct a config with the default and prove
subjective_duration is ignored while curiosity still halts.
```

This is in-slice, not a separate sub-slice, because without it the Path F RED
test #15 cannot pass safely.

### 2. Daemon `/message` Is Not An Owner-Auth Proof

The spec says daemon-owner prompt assembly is the v1 prompt-integration target,
but the daemon local `/message` route does not itself prove owner authority.

Fold one of these:

- Preferred: v1 prompt integration is central `handle_message(...)`, but the
  subjective-duration line is injected only when the caller supplies a trusted
  owner-authenticated surface label. Telegram owner and web-owner bridge may set
  that label; raw daemon `/message` may not until it has an owner-auth proof.
- Alternative: v1 prompt integration starts only in the private Telegram owner
  path and web owner bridge, not raw daemon `/message`.

RED test: a raw local `/message` fixture without owner-auth proof does not
dispatch `owner_contact` and does not receive an owner-only subjective-duration
line by default.

### 3. Meaningfulness Signal Is Mostly Inert Until Temperament Drift Exists

Path F's meaningfulness formula uses before/after temperament deltas. Current
Track A temperament has `record_event(...)`, but no production automatic drift.
Therefore v1 meaningfulness will usually be `0.0` unless a reviewed producer
creates temperament changes or supplies an explicit reviewed salience marker.

Fold this honesty into `Meaningfulness Signal`:

```text
In current code, temperament_delta is available only when a reviewed producer
has actually written temperament events. Until temperament drift or another
reviewed salience producer exists, meaningful_exchange events default to
0.0. This is acceptable for v1; the organ still provides continuous flow,
watchdog integration, anti-coercion, and a future seam for learned
meaningfulness.
```

RED test: with all temperament values missing or unchanged, a
`meaningful_exchange` event records `meaningfulness_score=0.0`.

### 4. Meaningfulness Calibration Needs Rationale Or Lower Initial Gain

The formula `clamp(temperament_delta / 2.0, 0.0, 1.0)` saturates at a two-point
average shift on a `[0, 10]` temperament scale. That may be reasonable, but the
spec should say why.

Fold either:

- keep `/ 2.0` and state that a two-point average shift is treated as a large
  v1 shift because temperament values are expected to move slowly; or
- reduce sensitivity, for example `/ 4.0`, until real bond-history calibration
  exists.

Panel recommendation: keep `/ 2.0` as a v1 reviewed constant but explicitly mark
it "provisional, high-sensitivity, requires calibration after live observation."

### 5. Residual Echo Needs A Bounded Lookback

The residual echo formula sums "recent meaningful events" but does not define
recent. Without a bound, implementation can accidentally scan all history on
every read or let old echoes contribute forever through tiny terms.

Fold:

```text
Residual echo scans only events within max(24 hours, 6 * residual_echo_half_life_seconds)
of now_utc. Older events contribute 0.0 to current resonance but remain in the
append-only event table.
```

RED test: a meaningful event outside the lookback window contributes zero to
`residual_resonance`.

### 6. Salience Registry Needs Deterministic Constructor

The spec says events are registered through a local registry function, but it
does not name the test seam. Use the external-fetch precedent.

Fold:

```text
build_salience_event_registry() returns a deterministic registry object for
tests and production. Production import/first-use timing is implementation
detail, but tests construct the registry directly and verify default entries,
unknown-kind refusal, and reviewed registration metadata.
```

### 7. Temperament Write Boundary Needs Static AST Enforcement

Fold the Locke council observation into RED tests.

Add a static AST test that scans `core/evolution/subjective_duration.py` and any
subjective-duration integration modules and fails if they call:

- `Temperament.record_event(...)`;
- `.record_event(parameter=...)` on an object known to be a temperament store;
- any future explicitly named temperament mutation helper.

Read imports of `Temperament` and `PARAMETER_NAMES` / `PARAMETER_SET` remain
allowed.

### 8. Multiplier Stability Invariant Needs Testable Shape

Fold the Descartes council observation:

```text
drag_multiplier, engagement_multiplier, and residual_multiplier are
structurally non-negative. upward and downward are structurally non-negative.
Every update clamps value to [0.0, 10.0].
```

RED test: pathological injected multiplier values are rejected before update or
clamped through a test-only seam so value never leaves `[0.0, 10.0]`. If the
implementation does not expose raw multiplier injection, test invalid
configuration values instead.

### 9. Meaningfulness Traceability Should Preserve Bounded Inputs

Fold the Ohm council observation with option (a), not option (b).

The diagnostic does not need raw temperament history, but it should preserve
bounded explainability:

- `meaningfulness_input_count`
- `temperament_delta_mean`
- `temperament_delta_max`
- `temperament_before_digest`
- `temperament_after_digest`
- `explicit_salience_marker_present`

Digests use the same `hmac-sha256:` discipline. This lets review distinguish
"score was 0.6 because average shift was 1.2" from a magic number without
logging private text.

### 10. Anti-Coercion Static Mechanism Must Be Named

The spec requires static call-path checks but does not name the mechanism.

Fold:

```text
tests/test_subjective_duration_anti_coercion.py walks production AST. It finds
calls to SubjectiveDuration.current(), SubjectiveDuration.perception_line(), and
subjective_duration imports. In the containing function, it fails if the same
function calls Telegram send wrappers, action notification senders, approval
card creation, crisis writers, or proactive-contact helpers. It also fails on
forbidden phrase fragments in subjective-duration phrase constants.
```

Keep this bounded to same-function AST in v1. Do not pretend it proves arbitrary
transitive control flow.

### 11. Diagnostic Schema Should Split Sample Rows From Event Rows

The diagnostics section lists `salience_event_kind`, `producer_ref`, and
`owner_auth_class` as minimum fields, but sample rows will not always have a
salience event. Avoid either fake empty values or inconsistent rows.

Fold one of:

- one schema with `event_type in {"sample", "salience_event"}` and nullable
  event-only fields explicitly set to `null` for sample rows; or
- two schemas: `subjective-duration-sample-v1` and
  `subjective-duration-salience-event-v1`.

Panel recommendation: one file, one `schema_version`, explicit `event_type`,
and null event-only fields for sample rows. Tests should assert the row shape
for both event types.

### 12. Prompt Integration Needs To Acknowledge Central-Path Coverage

The spec says daemon owner reply prompt assembly is v1 target, while private
Telegram and web-owner bridge "may receive this line in a later fold." In
current code, private Telegram appears to have its own prompt assembly in
`skills/telegram_voice.py`, and web owner bridge has its own prompt assembly in
`skills/web_interface.py`.

Fold a sharper v1 choice:

- either daemon-only is accepted as a narrow v1 canary and the spec explicitly
  says private Telegram/web-owner will not yet see subjective-duration phrasing;
- or v1 includes all three owner-private prompt builders: daemon owner,
  private Telegram owner, and web owner bridge.

Panel recommendation: include all three owner-private prompt builders in the
spec but gate each by its local owner-auth proof. Otherwise the first Track B
felt-time organ may not surface on the actual owner Telegram/web paths Rohit
uses most.

## Non-Blocking Observations

- `core/evolution/README.md` still has stale public-surface prose naming
  `TemperamentStore(...).observe(...)` while real code exposes
  `Temperament.record_event(...)`. This is not part of the slice, but it is
  adjacent doc drift.
- The spec's "emotion mimicry" rejection is good. Keep it. It prevents future
  reviewers from pushing the organ toward mood labels rather than felt-weight
  mechanics.

## Verdict

RATIFY-WITH-AMENDMENTS.

The architecture is right enough to proceed after folds. The current draft's
largest implementation risks are not philosophical; they are wiring risks:
owner-auth proof at the prompt/reset seam, watchdog allowlist implementation,
and meaningfulness being inert until temperament-writing producers exist.

## Plain-Language Readout

This version stops treating Maez like a kitchen timer and starts treating time
as something that has texture. Good. The fixes are about making sure the texture
doesn't sneak in through unauthenticated doors, doesn't get mistaken for a
watchdog failure, and doesn't pretend to know what mattered before the
temperament substrate can actually show that something changed.
