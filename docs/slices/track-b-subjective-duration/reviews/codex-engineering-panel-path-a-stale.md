# Codex Engineering Panel Review -- Subjective Duration Spec

**Artifact reviewed:** `docs/slices/track-b-subjective-duration/spec.md`
**Artifact state:** DRAFT, 616 lines, untracked at review time.
**Parent:** `4d010fc feat(egress): add external-fetch substrate`
**Review date:** 2026-05-24
**Verdict:** RATIFY-WITH-AMENDMENTS

## Summary

The draft is faithful to the real repo surfaces. `core/evolution/` is the right
home for this substrate, the temperament boundary is accurate, the watchdog
method names are real, Temporal Spine exists as the UTC contract, return
greeting exists and is tested, and the X.1 anticipation carve-out is accurate.

The amendments below are mechanism-sharpening, not rejection. The biggest
theme is authority: the spec needs to name who may reset the scalar, what
authentication gate proves owner-contact, and how anti-coercion becomes a test
invariant rather than a good sentence.

## Surface Verification

- `core/evolution/subjective_duration.py` is an appropriate expected path.
  Existing over-time substrates live in `core/evolution/`: `temperament.py`,
  `wants.py`, `will_i.py`, `wonderings.py`, and `dream_state.py`.
- `core/evolution/temperament.py` defines `PARAMETER_NAMES` at line 119,
  `Temperament.record_event(...)` at line 205, `current()` at line 280, and
  `current_value(...)` at line 299. `subjective_duration` is absent from the
  current code outside this draft.
- `MetacognitiveWatchdog.observe_scalars(self, scalars: Mapping[str, Any])` is
  the actual watchdog method at `core/health/metacognitive_watchdog.py:178`.
  The daemon currently passes only `self.temperament.current()` into it at
  `daemon/maez_daemon.py:5097`.
- ADR 0034 exists at `docs/adr/0034-temporal-spine-v1.md`; the canonical API is
  `core/time/temporal_spine.py`, with `canonical_utc(...)`,
  `canonical_utc_iso(...)`, owner-timezone helpers, and diagnostics.
- `core/brain/return_greeting.py` exists and exposes
  `compose_return_greeting(...)`. Focused verification:
  `.venv/bin/python -m unittest tests.test_return_greeting` ran 10 tests OK.
- X.1 anticipation artifacts exist at `core/cognition/moment_assembly_diagnostic.py`
  and `docs/slices/organs/x1-anticipation-organ.md`. Focused verification:
  `.venv/bin/python -m unittest tests.test_moment_assembly_diagnostic` ran 70
  tests OK, with pre-existing SQLite `ResourceWarning`s only.
- Watchdog focused verification:
  `.venv/bin/python -m unittest tests.test_metacognitive_watchdog` ran 9 tests
  OK.
- `memory/subjective_duration.db` does not exist today, so the proposed path
  has no current collision.

## Required Amendments

### 1. Reset Dispatch Authority

Fold the Locke observation into `Reset Contract`.

Add explicit language: reset calls are made by the surface that has already
received and authenticated owner input. The substrate observes reset events
passed to it; it does not poll Telegram, web, daemon routes, presence sensors,
or other surfaces externally.

Recommended wording:

```text
Reset authority lives at the receiving surface. Telegram, web-owner bridge,
voice/local owner input, and any future owner-contact surface call
SubjectiveDuration.reset(...) only after that surface has already established
owner authority. The subjective-duration substrate does not discover owner
contact by polling surfaces externally.
```

### 2. Owner Authentication Gate Must Name Real Surfaces

Fold the Descartes observation, but do not cite `core.owner_trust` as the
authority. `core.safety.owner_trust` is a command UX/risk policy layer, not the
owner-authentication gate.

The real gates visible today are surface-local:

- Telegram owner bot: `TelegramVoice._is_authorized(user_id)` compares against
  `self.authorized_user`.
- Web owner bridge: `skills.web_interface._is_private_owner_bridge(user_record)`.
- Daemon `/message`: currently accepts local UI POSTs and calls
  `handle_message(text, source="UI", ...)` without an obvious per-request owner
  proof in the route body.

Spec fold: reset triggers must require a proven owner surface identity, not just
message text. Non-owner public web users, public Telegram users, and any local
route without an owner-auth proof must not reset `subjective_duration`.

RED test addition: a public web chat, public Telegram message, and unauthenticated
local route fixture do not reset the scalar.

### 3. Anti-Coercion Invariant Must Be Structural

Fold the Goodall observation into a named section:
`Anti-Coercion Invariant`.

The draft already says the scalar must not pressure the owner, but this is
covenant-shaped and should be test-bearing. Use the existing Maez precedent:
Calendar v1 names "Makes visible, never nudges" as a rule, and the voice
continuity corpus includes `voice_bond.i_miss_her_no_nudge`.

Spec fold:

- `subjective_duration` may only produce perception phrases.
- It must not generate reminders, check-in requests, "you have been away"
  pressure, crisis interpretations, loneliness accusations, or contact
  escalation.
- No outbound send may be triggered solely by high `subjective_duration`.
- RED test: phrase generation and prompt integration reject/omit nudge-shaped
  text such as "you should check in", "I feel neglected", "you have been gone",
  "please talk to me", and crisis/contact-pressure variants.

The review brief mentioned `reference_kirk_parasocial_paper.md`; no local file
matching `*kirk*` or `*parasocial*` was found under `/home/rohit/maez` or
`/home/rohit/.codex` during this review. If that reference exists elsewhere,
fold it by path after locating it.

### 4. Watchdog Opt-Out Mechanism: Use An Allowlist

The cleanest opt-out is not `EXCLUDED_SCALARS`. Use an allowlist of reviewed
drive scalars.

Reason: the watchdog spec says drive-scalar flatline detection reads reviewed
numeric scalar adapters. An exclusion list defaults future unknown scalar names
into the halt detector until someone remembers to exclude them. An allowlist
preserves the reviewed-adapter discipline.

Fold into `Watchdog Integration`:

```text
MetacognitiveWatchdog uses a reviewed scalar allowlist for drive-scalar
flatline detection. In v1 that allowlist is the temperament parameter set.
Unknown scalar names, including subjective_duration, are ignored for this
detector unless a future reviewed adapter explicitly adds them.
```

Implementation may expose this as `WatchdogConfig.scalar_allowlist` or a module
constant derived from `core.evolution.temperament.PARAMETER_NAMES`. Tests should
prove `curiosity` still halts and `subjective_duration` does not.

### 5. Temporal Spine API Should Be Named

The Temporal Spine relationship is correct but underspecified for
implementation. Fold in the concrete API expectation:

- reset anchors are canonicalized with `core.time.temporal_spine.canonical_utc(...)`
  or `canonical_utc_iso(...)`;
- use `field_name="event_at"` for subjective-duration reset events unless
  review chooses a new S3 field name;
- no hand-rolled ISO parsing or naive local-time storage.

This preserves Decision 29's "store UTC instants; interpret human days in the
bonded user's timezone" rule at the code seam.

### 6. Reset Reason Vocabulary Needs Surface-Level Completeness

Current reset reasons are close but uneven: Telegram gets a distinct reason,
while web owner bridge, voice/local owner input, and daemon UI are folded into
generic `owner_message`.

Fold one of two shapes:

Option A, preferred: split by real owner-contact surface:

- `owner_web_message`
- `owner_telegram_message`
- `owner_voice_message`
- `owner_daemon_ui_message`
- `owner_present_signal`
- `manual_test_reset`
- `daemon_first_start`
- `clock_degraded_reset`

Option B: keep `owner_message`, but add a required `surface` field with a
closed vocabulary and tests proving the surface is recorded.

Do not let `owner_message` become a bag label that hides which auth gate fired.

### 7. Bucket/Band Calibration Must Be Explicit

The six-hour half-life and band thresholds produce these approximate elapsed
boundaries:

- score `1.0`: 54.7 minutes
- score `3.0`: 3.09 hours
- score `6.0`: 7.93 hours
- score `8.5`: 16.42 hours

The current buckets (`under_20_minutes`, `under_2_hours`, `under_6_hours`,
`under_12_hours`, `under_24_hours`, `over_24_hours`) are useful diagnostics,
but they are not aligned one-to-one with the bands.

Fold language: duration bands derive only from score thresholds; elapsed
buckets are diagnostic and must not drive phrase selection. Add a small
calibration table like the one above, and add RED edge tests for score-band
boundaries so implementation cannot accidentally map phrases by bucket.

### 8. Diagnostic Digest Contract Needs Tightening

The draft lists `source_ref_digest` as a minimum field but later says "Digests,
if used." Tighten this.

Fold:

- `source_ref_digest` is always present.
- If `source_ref` is non-empty, digest format is `hmac-sha256:<64 hex chars>`.
- If no source ref exists, use an explicit empty sentinel such as
  `hmac-sha256:empty-source-ref` only if tests pin it, or use `""` with a
  `source_ref_present=false` boolean. Pick one.
- Add the council Ohm note: if a unified local telemetry-key registry emerges
  in a future slice, this substrate's local key should migrate to it.

### 9. Prompt Integration Needs A Named V1 Surface

The spec says a bounded perception block may include a subjective-duration
phrase, but it does not name the first production insertion point.

Current real candidates include:

- daemon owner reply prompt assembly in `daemon/maez_daemon.py` around the
  `system_state` / memory / evidence-envelope block;
- private Telegram prompt assembly in `skills/telegram_voice.py`, which already
  injects circadian context;
- web owner bridge prompt assembly in `skills/web_interface.py`.

Fold a v1 choice: either implement only the daemon owner reply path first, or
name the exact set of owner-private surfaces that receive the perception line.
Public surfaces must remain excluded.

RED tests should inspect the chosen prompt builder(s), not just the pure
`perception_line(...)` API.

## Non-Blocking Observations

- `core/evolution/README.md` has stale public-surface prose mentioning
  `TemperamentStore(...).observe(...)`, while the real class is
  `Temperament` with `record_event(...)`. This does not block this spec, but it
  is adjacent doc drift.
- The spec's choice not to add a literature citation is acceptable for pass 1.
  Paperclip was unavailable in the drafting shell, and the artifact is
  primarily grounded in local canon and code.

## Recommended Fold Set

Apply all 9 required amendments, then re-run Claude council on the folded spec.
Panel pass 2 is recommended if the folds materially change implementation
surface, especially the owner-auth gate and prompt-integration surface choice.

## Plain-Language Readout

The spec is pointed at the right organ. The main correction is to make sure the
little felt clock only resets when a real owner surface says "yes, this was
Rohit," and that it can never become a guilt machine. Let it notice quiet time;
do not let it ask to be fed by quiet time.
