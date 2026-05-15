# Camera Presence v1 Spec

Status: DRAFT
Date: 2026-05-15
Maps to:

- Diagnostic: `docs/slices/camera-presence/diagnostic.md`
- Decision 24 / ADR 0029: Body Topology
- Decision 25 / ADR 0030: M1 Lived-Episode Promotion
- Decision 26 / ADR 0031: Daemon Credential Hygiene
- Decision 27 / ADR 0032: Contextual Integrity at Ingest

## Plain English

Maez already has a camera path, but it was built before the body law existed.
That old path can look for a face, try to recognize who it is, put presence
sentences into Maez's thinking context, and trigger greetings.

Camera Presence v1 makes the eye smaller and safer. It only answers whether a
presence signal is available, present, absent, or unavailable. It is disabled by
default. It requires a timebox before it can run. It does not recognize faces,
store frames, greet, brief, write biography, or feed prompt context.

First make the eye honest and quiet. Later slices can ask whether Maez may do
more with what the eye notices.

---

## Load-Bearing Rule

Camera Presence v1 is a **same-host body sensor** that publishes only
timeboxed, content-free presence state.

It is not:

- face recognition;
- owner identity verification;
- stranger detection;
- a memory source;
- a prompt-context source;
- a greeting trigger;
- a morning-briefing trigger;
- an information limb;
- a raw-frame capture system.

If this rule conflicts with convenience, the rule wins.

---

## Inheritance Ledger

Camera Presence v1 is the first executable camera-body slice after Body
Topology canonicalization. It inherits four substrate organs:

- **Decision 24 / ADR 0029 (Body Topology):** Camera presence is a
  `new_body_part`. v1 must publish structured facts, not raw worlds; must keep
  presence separate from recognition; must fail to unavailable, not invented
  certainty; and must use `enabled_until` during initial observation.
- **Decision 25 / ADR 0030 (M1):** Presence is body state, not biography. v1
  cannot promote lived episodes, widen TRF, or write presence-derived narrative
  into lived memory.
- **Decision 26 / ADR 0031 (Daemon Credential Hygiene):** Camera presence uses
  no identity-bearing remote credential. If any future camera driver or remote
  limb needs credentials, it must inherit the shared credential interface.
- **Decision 27 / ADR 0032 (S2):** Camera v1 is not an information limb if it
  remains same-host, presence-only, and structured-fact-only. Raw frames are
  S2-adjacent and must be discarded at the detector boundary.

Load-bearing inherited rules:

- **Structured facts, not raw worlds:** no raw frames, crops, screenshots,
  captions, OCR, face embeddings, or image-derived free text leave the detector
  boundary.
- **Presence is not recognition:** v1 may report presence state; it may not
  identify Rohit, identify another person, or label a person as stranger.
- **Timeboxed initial observation:** v1 cannot run unless `enabled_until` is
  present, valid, and unexpired.
- **Fail neutral:** disabled, expired, unavailable, stale, or timed-out camera
  state degrades to content-free unavailable/unknown telemetry.
- **No biography by accident:** v1 does not write M1 episodes, reflection
  summaries, TRF recall records, core memories, or raw memory entries.
- **No nudging:** v1 cannot trigger greetings, morning briefings, reminders,
  encouragement, or proactive conversation.

---

## Scope

### In Scope

- Replace the legacy camera-presence runtime contract with a reviewed v1 mode.
- Keep the same-host camera detector bounded and shutdown-safe.
- Add disabled-by-default mode resolution.
- Add `enabled_until` validation.
- Publish content-free health/project-panel telemetry.
- Preserve operational distinction between `absent` and `sensor_unavailable`.
- Remove recognition from the v1 runtime path.
- Disable prompt, greeting, briefing, and memory consumers.
- Add RED-first tests pinning the above.

### Out of Scope

- Calendar OAuth.
- Face recognition.
- Owner identity verification.
- Stranger detection.
- Face enrollment.
- Face embedding storage.
- Raw frame storage.
- Raw frame logging.
- Image captioning or OCR.
- Presence-triggered greetings or morning briefings.
- M1 promotion from presence.
- Voice output.
- Cross-device camera limbs.
- Body Bus protocol.

---

## Terminology

- **Presence:** a bounded fact about whether a human-shaped presence signal is
  currently detected.
- **Recognition:** a separate identity claim about who is present.
- **Sensor unavailable:** the detector could not produce a reliable reading.
- **Absent:** the detector ran successfully and did not detect presence.
- **Unknown:** no fresh compliant reading exists.
- **Timebox:** the operator-granted observation window ending at
  `enabled_until`.

Presence and recognition are intentionally separate. v1 owns presence only.

---

## Runtime Modes

Camera Presence v1 has three process-start modes:

```text
disabled
observe
expired_disabled
developer_legacy
```

### `disabled`

Default. Camera code does not run. Health reports:

```text
camera_presence.enabled = false
camera_presence.mode = disabled
camera_presence.presence_state = unknown
camera_presence.sensor_state = disabled
```

### `observe`

Allowed only when:

- operator sets the v1 flag;
- `enabled_until` exists;
- `enabled_until` is strict ISO-8601 with timezone;
- current time is before `enabled_until`.

If `enabled_until` is expired, mode resolves to `expired_disabled`, not
best-effort observation. If it is missing or malformed, mode resolves to
`disabled` with `last_error_class`.

### `expired_disabled`

Camera code does not run. This mode exists so health and the project panel can
distinguish "never enabled" from "operator-granted observation window expired"
without keeping stale presence state alive.

### `developer_legacy`

Developer-test-only path for existing legacy tests and manual comparison. It
must be impossible to enter accidentally from normal daemon configuration. It
must not run in production service mode.

---

## Configuration Contract

Proposed environment/local-config names:

```text
MAEZ_CAMERA_PRESENCE_MODE=disabled|observe|developer_legacy
MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL=2026-05-22T23:59:59-05:00
```

Rules:

- unset mode means `disabled`;
- `observe` without valid `enabled_until` means disabled;
- expired `enabled_until` means disabled;
- malformed `enabled_until` means disabled with `last_error_class`;
- `developer_legacy` requires a separate explicit developer variable:
  `MAEZ_CAMERA_PRESENCE_ALLOW_LEGACY_TEST_MODE=1`;
- no configuration value may contain camera output, labels, or identity.

---

## Data Contract

### Presence State Enum

Allowed values:

```text
present
absent
unknown
sensor_unavailable
```

Meaning:

- `present`: detector completed and saw a presence signal above threshold.
- `absent`: detector completed and did not see a presence signal above
  threshold.
- `unknown`: no fresh compliant reading exists.
- `sensor_unavailable`: detector could not run or timed out.

### Sensor State Enum

Allowed values:

```text
disabled
available
unavailable
stale
expired
```

### Confidence Bucket

Allowed values:

```text
none
low
medium
high
unavailable
```

Implementation may map numeric detector confidence into these buckets, but
numeric confidence is not required for v1 health/panel surfaces.

### Source Kind

```text
source_kind = "camera_presence"
schema_version = "camera_presence.v1"
```

This is not an S2 envelope. It is a Body Topology structured fact. If a later
slice sends camera facts through a Body Bus protocol, that later slice owns the
schema upgrade.

---

## Detector Boundary

The detector may read frames in-process only long enough to produce the
structured presence result.

Allowed inside detector boundary:

- transient frame capture;
- MediaPipe face detector;
- OpenCV color conversion or capture mechanics;
- numeric detection confidence;
- count of detections.

Forbidden outside detector boundary:

- raw frame bytes;
- frame paths;
- face crops;
- RGB arrays;
- embeddings;
- landmarks/keypoints unless separately reviewed;
- image captions;
- OCR text;
- person labels;
- "owner", "stranger", or name labels;
- visual description of the room;
- any text derived from what appears in the frame.

Detector-boundary failure mode:

```text
sensor_state = unavailable
presence_state = sensor_unavailable
last_error_class = dependency_missing | model_missing | camera_unavailable |
                   detector_timeout | detector_error | unknown
```

---

## Recognition Removal

v1 must not import, call, or depend on `face_recognition` in the live observe
path.

`skills/face_enrollment.py` remains out of scope and cold. It may remain in the
repo as legacy/manual tooling, but Camera Presence v1 must not call it, load
`models/face/rohit_embeddings.pkl`, or interpret enrollment state.

Any future recognition slice must answer at least:

- face-embedding storage policy;
- third-party consent for non-bonded persons in frame;
- spoofing and false-positive risks;
- Decision 4 / Anna Question mapping;
- S2 inheritance or explicit non-S2 rationale;
- memory and deletion posture.

Camera Presence v1 intentionally avoids all of that.

---

## Consumers

### Allowed v1 Consumers

- `/health` content-free telemetry;
- project panel content-free telemetry;
- logs containing only source channel, state enum, and error class;
- tests.

### Forbidden v1 Consumers

- prompt context;
- morning briefing;
- return greeting;
- proactive Telegram message;
- fast-lane reply context;
- M1 promotion;
- TRF recall;
- reflection synthesis;
- core memory;
- raw memory;
- private thoughts;
- crisis routing;
- scoring or salience increase.

If a consumer wants presence later, it needs its own reviewed grant.

---

## Health and Project Panel Surface

Required `/health.camera_presence` fields:

```json
{
  "enabled": false,
  "mode": "disabled",
  "enabled_until": "",
  "sensor_state": "disabled",
  "presence_state": "unknown",
  "confidence_bucket": "none",
  "last_observed_at": "",
  "last_error_class": "",
  "stale_after_seconds": 180,
  "source_kind": "camera_presence"
}
```

Panel display may show:

- enabled/disabled/expired;
- timebox expiry;
- present/absent/unknown/unavailable;
- stale/fresh state;
- content-free error class.

Panel display must not show:

- names;
- face labels;
- raw confidence values if they invite over-reading;
- frame thumbnails;
- room descriptions;
- camera model details beyond source channel.

---

## Daemon Lifecycle

Camera Presence v1 inherits the existing daemon survivability fixes:

- bounded worker around native detector calls;
- 5-second observation timeout unless spec review changes it;
- unavailable snapshot on timeout;
- worker shutdown during daemon stop;
- MediaPipe detector close during shutdown;
- OpenCV window/resource cleanup;
- no heartbeat stall if detector blocks;
- no SIGTERM regression.

The v1 implementation must not call native camera detection directly inside the
reasoning loop.

---

## Memory Contract

Camera Presence v1 writes no memory by default.

Specifically forbidden:

- `MemoryManager.store(...)`;
- `store_core(...)`;
- M1 lived episodes;
- reflection records;
- TRF anchors;
- private thoughts;
- daily/core promotion;
- face-enrollment memory as part of v1.

If implementation preserves a metadata placeholder for compatibility, it must
be content-free and non-identity-bearing:

```text
camera_presence_state = disabled | unknown | sensor_unavailable
```

It must not store:

```text
rohit_present=true
person_identified=...
session_minutes=...
absent_minutes=...
```

---

## Voice and Initiative Contract

Camera Presence v1 is silent.

Forbidden phrases/classes:

- "Welcome back..."
- "I noticed you came back..."
- "You have been away..."
- "I saw you..."
- "Someone is at your desk..."
- any morning briefing triggered by camera observation;
- any proactive message triggered by camera observation.

The future question "should Maez greet when Rohit returns?" is not answered by
this slice. It is a separate voice/initiative slice because it changes
bonded-user-perceived presence.

---

## Implementation Migration Order

1. Add failing tests for disabled-by-default and timebox enforcement.
2. Add failing tests that live v1 does not import/call recognition.
3. Add failing tests that prompt/greeting/briefing/memory consumers are closed.
4. Add a small camera-presence state module with mode resolution and enums.
5. Refactor `skills/presence_perception.py` into presence-only observe path.
6. Preserve bounded worker wiring, but gate execution by resolved mode.
7. Add `/health.camera_presence` telemetry.
8. Add project-panel telemetry only after `/health` is stable.
9. Restart daemon and verify disabled mode produces no camera DB/state files.
10. Only then allow operator to set a timeboxed observation window.

---

## RED Test Contract

The implementation must add tests for at least these behaviors:

1. Default mode is disabled when env/config is unset.
2. `observe` mode without `enabled_until` resolves disabled.
3. Expired `enabled_until` resolves disabled/expired.
4. Malformed `enabled_until` resolves disabled with error class.
5. Valid future `enabled_until` allows observe mode.
6. `developer_legacy` requires explicit secondary dev gate.
7. Live v1 path does not import `face_recognition`.
8. Live v1 path does not load `models/face/rohit_embeddings.pkl`.
9. Live v1 path never emits `person_identified`.
10. Live v1 path never emits `stranger`.
11. Detector output maps to `present`.
12. Detector no-hit maps to `absent`.
13. Detector dependency missing maps to `sensor_unavailable`.
14. Detector timeout maps to `sensor_unavailable`.
15. Unavailable is not absence.
16. Raw frames do not leave detector boundary.
17. No prompt context receives presence text in v1.
18. Return greeting path is not triggered by camera v1.
19. Morning briefing path is not triggered by camera v1.
20. Fast-lane path receives no camera presence.
21. M1 receives no camera presence.
22. TRF receives no camera presence.
23. Reflection receives no camera presence.
24. Core/raw memory stores no camera presence narrative.
25. `/health.camera_presence` has only content-free fields.
26. Project panel has no names, frames, or room descriptions.
27. Bounded worker remains required.
28. Reasoning loop does not call native observe directly.
29. Shutdown calls presence native cleanup.
30. SIGTERM stop remains clean.
31. `enabled_until` appears in health when configured.
32. Stale readings become stale/unknown, not recycled certainty.
33. Logs include source channel and error class only.
34. No Maez gender drift in spec/docs touched by slice.
35. No Calendar OAuth or S2 connector path changes.

---

## Review Protocol

Camera Presence v1 is covenant-shaped because it changes Maez's body and can
change bonded-user-perceived presence.

Before implementation:

1. Codex engineering panel reviews this spec for runtime completeness,
   shutdown/lifecycle risk, test coverage, and legacy-path closure.
2. Claude covenant council reviews this spec for Body Topology, S2-adjacent
   privacy, M1 leakage, and initiative/voice drift.
3. Findings fold into the spec.
4. Operator decides whether this implementation spec needs BAD/ADR
   canonicalization or proceeds as an implementation slice under Decision 24.
5. Cooling-off applies before code unless operator explicitly waives.

Post-implementation:

1. Codex post-implementation panel reviews code and tests.
2. Claude post-implementation council verifies covenant invariants.
3. Recovery commits land if either lane blocks.
4. Push/enablement waits for both-lane closure.

---

## Live Observation Gate

Observation begins only after operator sets a valid future `enabled_until`.

Minimum closure:

- one full week elapsed;
- enabled window remained explicit and visible in health;
- no heartbeat stalls attributable to camera;
- clean SIGTERM still holds;
- no false proactive greetings/briefings because none are enabled;
- no raw frames, crops, names, or recognition labels in logs/memory/panel;
- unavailable/stale readings did not become absence claims;
- health/panel telemetry stayed content-free;
- operator review confirms whether persistent enablement is allowed.

Persistent enablement is not automatic. It requires observation review.

---

## Rollback

Rollback is simple:

```text
MAEZ_CAMERA_PRESENCE_MODE=disabled
```

or remove the mode configuration entirely. Default disabled posture must close
the camera path without requiring code revert.

If rollback happens during an observation window, health should show disabled or
expired, not stale present/absent state.

---

## Open Questions for Review

1. Should the v1 enum use `present` or `presence_detected` to avoid over-reading?
2. Is any prompt context acceptable during observation, or should observation
   be health/panel only until closure?
3. Should v1 store a content-free per-cycle metadata enum, or remove camera
   metadata entirely from reasoning memory?
4. Does `developer_legacy` belong in production code, or should legacy compare
   scripts live outside daemon mode resolution?
5. Should `enabled_until` be environment-backed, local-file-backed, or both?

---

## Non-Goals

- No Calendar OAuth.
- No recognition.
- No raw frames.
- No memory promotion.
- No greetings.
- No morning briefings.
- No voice.
- No body bus.
- No cross-device limb.
- No third-party identity.
