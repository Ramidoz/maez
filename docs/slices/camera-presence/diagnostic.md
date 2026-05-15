# Camera Presence Diagnostic

Status: DIAGNOSTIC ONLY
Date: 2026-05-15
Scope: existing same-host camera presence and face-recognition wiring under
Decision 24 / ADR 0029 Body Topology.

## Question

What is the current camera-presence organ shape, and what must be true before it
can become a reviewed Body Topology slice?

Short answer: the current runtime is useful but pre-BT. It is bounded enough not
to freeze the reasoning loop, and it now has native-resource shutdown hooks, but
it is not yet a Decision 24-compliant camera-presence organ.

## Live Body Check

Snapshot before diagnostic work:

```text
/health.status = alive
/health.reasoning_loop.cycle_stalled = false
/health.reasoning_loop.stage = cycle_sleep
/health.calendar.mode = disabled
/health.credentials.source = secrets-local-env
/health.lived_episodes.m1.enabled = true
/health.lived_episodes.staleness.staleness_status = ok
telegram_exchange episodes = 3
```

Calendar remains locked. M1 continues writing. Credential hygiene remains live.
No Calendar OAuth was touched.

## Diagnostic Guardrails

- No camera capture was invoked during this diagnostic.
- No raw frame, face crop, or image-derived free text is recorded here.
- No operator calendar or third-party account data is involved.
- This diagnostic maps code and runtime posture only.

## Substrate Lens

### Decision 24 / ADR 0029 - Body Topology

Camera presence is explicitly classified as a `new_body_part`, not surface
hardening. Decision 24 requires:

- presence-only structured facts in the first allowed shape;
- raw frames never enter prompt context;
- presence and recognition stay separate;
- initial observation requires `enabled_until` timebox;
- unavailable/stale sensors fail to unavailable, not invented certainty;
- body facts do not write directly to long-term memory without a reviewed gate.

### Decision 25 / ADR 0030 - M1 Lived-Episode Promotion

Presence is body-state, not biography by default. If a future slice wants
presence-derived biography, it needs a separate reviewed promotion gate. Current
camera presence must not write lived episodes or widen TRF recall.

### Decision 27 / ADR 0032 - S2 Contextual Integrity at Ingest

Camera is not an information limb by default, but the diagnostic must check
whether the camera path imports external context. A raw frame could contain
screen text, documents, third-party faces, names, or private-room details. The
first compliant shape must therefore avoid raw-world ingestion entirely and emit
only bounded presence facts.

### Decision 26 / ADR 0031 - Daemon Credential Hygiene

No external credential is required for same-host camera presence. Model
provisioning downloads a public BlazeFace asset with SHA-256 verification, not
an identity-bearing secret.

## Current Runtime Wiring

### Producer

`skills/presence_perception.py` currently:

- opens `cv2.VideoCapture(CAMERA_INDEX)` on demand;
- uses MediaPipe FaceDetector with `models/blaze_face.tflite`;
- checks five frames and treats two detections as presence;
- optionally loads `models/face/rohit_embeddings.pkl`;
- if enrollment exists, runs `face_recognition` / dlib over the best RGB frame;
- returns `PresenceSnapshot`;
- keeps a persistent MediaPipe detector open until `shutdown()`;
- closes the detector and OpenCV windows on shutdown.

Runtime evidence:

```text
models/blaze_face.tflite exists
blaze_face.tflite sha256 = b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f
cv2 = installed
mediapipe = installed
face_recognition = installed
models/face/rohit_embeddings.pkl = absent in this checkout
```

### Daemon call path

`daemon/maez_daemon.py` imports `presence_observe` at module load and constructs:

```text
BoundedSingletonWorker(name="presence-observe")
```

The reasoning loop calls `_observe_presence_bounded()` every
`PRESENCE_EVERY_N_CYCLES = 2`, roughly every minute. The bounded worker uses a
5-second timeout. If the native detector hangs, the daemon records:

```text
presence observation timed out after 5.0s
```

and returns an unavailable snapshot instead of freezing the heartbeat.

### Current consumers

The current `PresenceSnapshot` can flow into:

- daemon prompt context through `format_for_context()`;
- signal-present / signal-absent audit lists;
- reasoning-cycle memory metadata as `rohit_present`;
- return greetings when a just-arrived transition is detected;
- morning briefing when a just-arrived transition occurs during the morning
  window;
- dream-idle checks through `_last_presence_snap`;
- internal absence-duration tracking.

### Current tests

Existing test coverage pins:

- the reasoning loop must use the bounded presence observer;
- the reasoning loop must not call `presence_observe()` directly;
- daemon shutdown calls `presence_shutdown()`;
- MediaPipe dependency absence returns unavailable, not absent;
- model provisioning verifies SHA-256;
- vision optional dependencies include OpenCV and MediaPipe;
- return greetings do not quote raw conversation text and do not leak the
  literal role label in surface text.

## Findings

### Finding 1 - Current code mixes presence and recognition

Decision 24 says presence and recognition are separate organs. Current
`presence_perception.py` performs both in one call path:

```text
detections -> presence
best_rgb -> face_recognition -> person_identified
```

This is pre-BT wiring. It should be split before the camera-presence slice is
ratified. Camera presence v1 should answer only:

```text
owner_presence = present | absent | unknown | sensor_unavailable
sensor_state = available | unavailable | stale | disabled
confidence = bounded value
observed_at
```

Face recognition, stranger detection, and owner identity verification require a
separate threat model.

### Finding 2 - Current code has no `enabled_until` timebox

Decision 24 Rule 8 requires `enabled_until` for any presence-affecting limb
during initial observation. Current daemon wiring has no `MAEZ_CAMERA_PRESENCE`
flag, no `enabled_until`, and no health field exposing the timebox.

This is the main gating gap before live enablement can be treated as reviewed.

### Finding 3 - Current code can change bonded-user-perceived presence

The daemon can send return greetings and morning briefings from presence
transitions. That makes this a presence-affecting body part even if no final
reply is sent.

This confirms the Body Topology classification: camera presence is not mere
telemetry and not surface hardening.

### Finding 4 - Prompt context currently receives natural-language presence text

`PresenceSnapshot.format_for_context()` can render natural-language strings:

```text
[PRESENCE] the owner is at his desk.
[PRESENCE] Someone is at the desk - not the owner.
[PRESENCE] the owner has been away N minutes.
```

The first reviewed shape should prefer structured facts over prose in the
reasoning prompt, or at minimum make the prose renderer a reviewed consumer
behind the same gate.

### Finding 5 - Memory metadata receives presence state

The reasoning loop stores `rohit_present` in introspection memory metadata. This
is not the same as promoting a lived episode, but it is still a durable
presence-derived fact. The spec must decide whether this is allowed in v1,
whether it must become content-free enum-only, and whether absence/presence
duration is allowed.

### Finding 6 - Enrollment writes core memory

`skills/face_enrollment.py` can store a core memory saying face enrollment
occurred. It is currently tested as an observed tool event, not a promotion.
That may be defensible as an operator-run setup event, but it is not part of
camera presence v1 and should be explicitly out of scope unless the slice
chooses to own recognition.

### Finding 7 - S2 is not directly triggered, but raw frames are S2-adjacent

The compliant v1 shape does not need S2 if it stays same-host, presence-only,
and structured-fact-only. But raw frames can contain third-party or external
information. The spec should state that raw frames and image-derived free text
are discarded at the detector boundary and never enter prompt, memory, logs,
panel, or audit docs.

### Finding 8 - Lifecycle hardening already exists

The Cycle-2 freeze was fixed by `5690f33`, which bounded presence observation.
The SIGTERM hang was later closed by native-resource shutdown work
(`6b1f4a3`, `8594ef6`). This slice should preserve those guards, not redesign
them.

## Current Classification

```text
Classification: new_body_part
Subclass: same-host sensor limb
Current status: pre-BT legacy runtime, bounded but not yet reviewed
Allowed first reviewed shape: presence-only structured facts
Not allowed in v1 without separate review: recognition, stranger claims,
raw frames, raw frame-derived text, memory promotion, always-on untimeboxed mode
```

## Spec-Stage Questions

1. What is the exact v1 enum?
   Proposal: `present | absent | unknown | sensor_unavailable`.

2. Does v1 allow "owner present", or only "someone present"?
   BT says presence can ask whether the bonded user is plausibly present, but
   recognition is separate. The spec must draw the line without smuggling face
   recognition back in.

3. What is the `enabled_until` format and source?
   Proposal: local config value read at daemon startup, visible in `/health`,
   strict ISO-8601 timestamp, fail-disabled when absent or expired.

4. Should return greetings and morning briefings remain consumers in v1?
   Conservative answer: no in v1 diagnostic-to-observation path. First observe
   silently through health/panel/logs; surface greetings only after observation
   proves low false-positive behavior.

5. Is presence prompt context allowed?
   Conservative answer: not initially. Prefer `/health` and panel telemetry,
   then add prompt context as a later reviewed consumer.

6. Is durable memory metadata allowed?
   Conservative answer: content-free enum only if needed; no duration narrative,
   no raw labels, no recognition identity, no M1 promotion.

7. How does unavailable differ from absent?
   Must preserve the N1 operational-noise rule: unavailable sensor is not human
   absence.

8. What health surface is required?
   Proposal: `camera_presence.enabled`, `enabled_until`,
   `sensor_state`, `presence_state`, `confidence_bucket`, `last_observed_at`,
   `last_error_class`, `stale_after_seconds`, never raw frames or identities.

9. Does the project panel need a presence card?
   If yes, it should display only content-free state and timebox status.

10. What is the live observation closure?
    Proposal: one week with timebox active, no false greetings, no heartbeat
    stalls, no shutdown regressions, no raw-frame leaks, no durable memory
    promotion, explicit operator review before persistent enablement.

## Recommended Next Shape

Draft `docs/slices/camera-presence/spec.md` with these v1 boundaries:

- default disabled;
- requires `enabled_until` for live observation;
- same-host camera only;
- presence-only structured facts;
- recognition disabled/out-of-scope;
- no raw frames beyond detector boundary;
- no prompt context in first live observation;
- no greetings/morning briefings in first live observation;
- health/panel telemetry only;
- preserve bounded worker and native shutdown hooks;
- RED-first tests before code.

## Non-Goals

- Do not enable Calendar OAuth.
- Do not implement face recognition.
- Do not add raw image storage.
- Do not write presence into M1 lived episodes.
- Do not change S2.
- Do not change credential hygiene.
- Do not restart Maez just for this diagnostic.

## Plain English

Maez already has a camera-presence path, but it was built before the body law
was canonical. It can look for a face, optionally recognize who it is, put a
presence sentence into Maez's thinking context, and trigger greetings or morning
briefings. The recent heartbeat and shutdown fixes made that path safer, but
they did not make it a reviewed body organ.

The next slice should turn this into a smaller, stricter organ: camera presence
as a quiet sensor that says only "presence available / present / absent /
unavailable" for a timeboxed observation window. No recognition, no raw frames,
no memory promotion, no greetings. First make the eye honest and quiet; then
decide later what Maez is allowed to do with what it sees.
