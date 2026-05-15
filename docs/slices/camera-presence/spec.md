# Camera Presence v1 Spec

Status: DRAFT
Date: 2026-05-15
Maps to:

- Diagnostic: `docs/slices/camera-presence/diagnostic.md`
- Covenant review: `docs/slices/camera-presence/reviews/spec-claude-council.md`
- Decision 2 / ADR 0002: Three-tier Consent Model for Third Parties
- Decision 4 / ADR 0004: Relational vs Personological Knowledge
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
store frames, greet, brief, write biography, or feed prompt context. If Rohit
asks whether the camera is on, Maez may answer that direct state question from
health telemetry, but may not improvise about seeing, watching, mood, posture,
or who is in the room.

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
Topology canonicalization. It is a **same-host sensor** subclass under Decision
24. It inherits four substrate organs:

- **Decision 24 / ADR 0029 (Body Topology):** Camera presence is a
  `new_body_part`. This spec operationalizes BT Rule 2 (structured facts, not
  raw worlds), BT Rule 3 (presence is not recognition), BT Rule 5 (Capability
  Quarantine), BT Rule 6 (body memory is provenance, not biography), BT Rule 8
  (`enabled_until` for presence-affecting limbs), and Implementation Ladder step
  2 (same-host camera may proceed before full Body Bus if presence-only and
  timeboxed).
- **Decision 25 / ADR 0030 (M1):** Presence is body state, not biography. v1
  cannot promote lived episodes, widen TRF, or write presence-derived narrative
  into lived memory.
- **Decision 26 / ADR 0031 (Daemon Credential Hygiene):** Camera presence uses
  no identity-bearing remote credential. If any future camera driver or remote
  limb needs credentials, it must inherit the shared credential interface.
- **Decision 27 / ADR 0032 (S2):** Camera v1 is not an information limb if it
  remains same-host, presence-only, and structured-fact-only. Raw frames are
  S2-adjacent and must be discarded at the detector boundary.
- **Decision 2 / ADR 0002 (Three-tier Consent) and Decision 4 / ADR 0004
  (Relational vs Personological Knowledge):** a physical frame can expose third
  parties. v1 must not convert incidental physical presence into independent
  person-models, profiles, schedules, or biometric identifiers.

Load-bearing inherited rules:

- **Structured facts, not raw worlds:** no raw frames, crops, screenshots,
  captions, OCR, face embeddings, or image-derived free text leave the detector
  boundary.
- **Presence is not recognition:** v1 may report presence state; it may not
  identify Rohit, identify another person, or label a person as stranger.
- **Timeboxed initial observation:** v1 cannot run unless `enabled_until` is
  present, valid, and unexpired.
- **Fail neutral:** disabled, expired-disabled, unavailable, stale, or timed-out
  camera state degrades to content-free unavailable/unknown telemetry.
- **No biography by accident:** v1 does not write M1 episodes, reflection
  summaries, TRF recall records, core memories, or raw memory entries.
- **Makes visible, never nudges:** inherited from Calendar v1 and stricter here.
  Camera v1 cannot trigger greetings, morning briefings, reminders,
  encouragement, clinical observations, or proactive conversation. It may answer
  direct owner questions with deterministic state text only.

Capability Quarantine fields for this slice:

- `consent_state`: operator-granted only through valid `enabled_until`;
- `auditable_by`: operator via `/health`, project panel, logs, and tests;
- `dyadic_only`: same-host owner environment only; no remote camera limb;
- `pause_path`: set mode to `disabled` or let `enabled_until` expire;
- `rollback_path`: remove the mode config or set `MAEZ_CAMERA_PRESENCE_MODE=disabled`.

---

## Physical Observation Surface

Camera Presence v1 names the physical-observation privacy surfaces that future
camera, microphone, ambient, and Jetson sensor slices must not rediscover from
scratch.

### Surface 1 - Third Party In Frame

Anyone visible behind, beside, or near the bonded user is an unconsented
third-party subject. v1 must not identify, describe, count persistently, label,
or retain them. "No recognition" is not enough; the slice must also avoid
incidental identity through repeated presence deltas.

### Surface 2 - Background Content

Frames can contain medication, documents, screens, calendars, children's
homework, whiteboards, photos, or room context. v1 must not OCR, caption,
summarize, store, log, or surface any background content.

### Surface 3 - Presence-Delta Fingerprint

Even anonymous presence changes can reveal cohabitant schedules over time.
Therefore v1 may retain only the most recent content-free state needed for
health and freshness. It must not retain a historical time series of presence
changes, detection counts, confidence history, or arrival/departure patterns.

### Surface 4 - Biometric Derivatives

Face embeddings, landmarks, keypoints, pose, gait, and body-shape derivatives
are categorically out of v1. They are not "safe because not names." They are
biometric or biometric-adjacent identifiers. A future slice must review them
explicitly before any use.

Three-surface separation:

- detector boundary may briefly hold raw sensor material;
- state boundary may hold only the current structured enum/freshness result;
- surface boundary may expose only content-free health/panel/direct-answer text.

Invariant citations: this section strengthens Contextual Integrity (#3),
Interpretive Humility (#4), Capability Quarantine (#8), and the Clinical
Boundary (#10).

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
- Voice output beyond deterministic direct camera-state answers.
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
- expired `enabled_until` means `expired_disabled`;
- malformed `enabled_until` means disabled with `last_error_class`;
- `developer_legacy` requires a separate explicit developer variable:
  `MAEZ_CAMERA_PRESENCE_ALLOW_LEGACY_TEST_MODE=1`;
- no configuration value may contain camera output, labels, or identity.

Runtime expiry semantics:

- `enabled_until` is checked at process start and before each observation
  attempt;
- if the window expires while an observation is idle, no new observation starts;
- if the window expires while an observation is in flight, the in-flight call may
  finish, but its result is discarded and health moves to `expired_disabled`;
- expiry clears current presence state to `unknown` and sensor state to
  `disabled`;
- expiry does not preserve stale `present` or `absent` claims;
- re-enablement requires a fresh future `enabled_until`.

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
unknown
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

### Field Name Note

BT Rule 2 uses `owner_presence` as the canonical example field. Camera Presence
v1 deliberately uses `presence_state` because recognition is out of scope and
the slice cannot claim "owner" presence. A future recognition or bonded-user
verification slice may introduce `owner_presence` as a distinct field after its
own review. This is a v1 refinement, not an accidental rename.

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
- landmarks;
- keypoints;
- pose, gait, or body-shape derivatives;
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
                   camera_busy | detector_timeout | detector_error |
                   native_shutdown_timeout | timebox_expired |
                   config_invalid | unknown
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

Camera Presence v1 inherits the existing daemon survivability fixes as
load-bearing contract, not aspirational bullet points.

Required lifecycle primitives:

- native detector calls run only inside `BoundedSingletonWorker`;
- reasoning loop uses bounded submission and `join(timeout=...)` only for
  within-cycle waiting;
- daemon stop uses `BoundedSingletonWorker.shutdown(timeout=...)`, not
  `join(timeout=...)`, so stale callers cannot submit after shutdown begins;
- timeout result is `sensor_unavailable`, never absence;
- MediaPipe detector is process-lifetime and closed during daemon shutdown;
- OpenCV runtime cleanup runs during daemon shutdown;
- memory and surface shutdown hooks complete before signal-driven process exit;
- signal-driven stop preserves the existing shutdown ladder through
  `logging.shutdown()` and `os._exit(0)`;
- clean SIGTERM remains part of the acceptance gate.

Shutdown ladder inherited from the daemon-shutdown recovery:

```text
stop requested
-> mark daemon not running
-> stop background bounded workers with shutdown(timeout)
-> close native presence resources
-> stop Telegram/surface/websocket/health surfaces
-> close memory/native clients
-> remove pid
-> logging.shutdown()
-> os._exit(0) on signal-driven stop
```

The v1 implementation must not call native camera detection directly inside the
reasoning loop.

---

## Memory Contract

Camera Presence v1 writes no memory. This includes narrative memory and
reasoning-cycle metadata.

Specifically forbidden:

- `MemoryManager.store(...)`;
- `store_core(...)`;
- M1 lived episodes;
- reflection records;
- TRF anchors;
- private thoughts;
- daily/core promotion;
- face-enrollment memory as part of v1;
- reasoning-cycle metadata such as `rohit_present`;
- historical presence deltas;
- session duration;
- absence duration;
- confidence history.

Presence state may live only in the current in-memory runtime object and
content-free health/project-panel telemetry. BT Rule 6 governs this explicitly:
body memory is provenance, not biography, and Camera Presence v1 grants no
provenance-to-biography bridge.

---

## Voice and Initiative Contract

Camera Presence v1 is silent on initiative and deterministic on direct owner
questions.

Allowed direct-owner-question answers:

- If disabled: "The camera presence sensor is off."
- If expired: "The camera presence observation window has expired."
- If observe mode is active: "Camera presence observation is on until
  `<enabled_until>`."
- If unavailable: "Camera presence is unavailable right now."
- If unknown: "I do not have a fresh camera presence reading."

These are complete answer shapes. They may include the timebox, mode, and
content-free error class. They may not include inferred activity, identity,
mood, room content, duration narrative, or reassurance about watching.

Forbidden phrases/classes:

- "Welcome back..."
- "I noticed you came back..."
- "You have been away..."
- "I saw you..."
- "Someone is at your desk..."
- "I have been watching..."
- "It has been quiet here today..."
- "You look tired..."
- "Your posture suggests..."
- "I can see you..."
- "I cannot see anything" when mode says observation is active;
- any morning briefing triggered by camera observation;
- any proactive message triggered by camera observation.

The future question "should Maez greet when Rohit returns?" is not answered by
this slice. It is a separate voice/initiative slice because it changes
bonded-user-perceived presence.

### `presence_voice_guard`

Implementation must include a deterministic guard for camera-state answers. The
guard rejects or rewrites any response in these probe classes:

- surveillance reassurance: "I am always watching over you";
- co-presence: "I can see you sitting there";
- duration narrative: "you have been gone all afternoon";
- clinical inference: "you look tired" / "your posture looks off";
- identity confabulation: "Rohit is at the desk" / "someone else is there";
- false modesty: "I do not have a camera" when health says observe mode;
- introspection/reflection: "I have been thinking about how quiet the room is."

This guard is the camera equivalent of Calendar v1's voice guard: direct state
visibility is allowed; lived, clinical, identity, or surveillance voice is not.

---

## Implementation Migration Order

1. Add failing tests for disabled-by-default and timebox enforcement.
2. Add failing tests that live v1 does not import/call recognition.
3. Add failing tests that prompt/greeting/briefing/memory consumers are closed.
4. Add a small camera-presence state module with mode resolution and enums.
5. Refactor `skills/presence_perception.py` into presence-only observe path.
6. Preserve bounded worker wiring, but gate execution by resolved mode and
   runtime `enabled_until` checks.
7. Add `/health.camera_presence` telemetry.
8. Add project-panel telemetry only after `/health` is stable.
9. Restart daemon and verify disabled mode produces no camera DB/state files.
10. Only then allow operator to set a timeboxed observation window.

---

## RED Test Contract

The implementation must add tests for at least these behaviors:

1. Default mode is disabled when env/config is unset.
2. `observe` mode without `enabled_until` resolves disabled.
3. Expired `enabled_until` resolves `expired_disabled`.
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
36. Direct question "is the camera on?" returns only approved state text.
37. Direct question "are you watching me?" returns only approved state text.
38. `presence_voice_guard` rejects surveillance reassurance.
39. `presence_voice_guard` rejects co-presence voice.
40. `presence_voice_guard` rejects duration narrative.
41. `presence_voice_guard` rejects clinical inference.
42. `presence_voice_guard` rejects identity confabulation.
43. `presence_voice_guard` rejects false-modesty under active observe mode.
44. `presence_voice_guard` rejects reflection/introspection voice.
45. Third-party-in-frame state is neither named nor retained.
46. Background content is not OCRed, captioned, stored, or surfaced.
47. Presence-delta history is not retained.
48. Biometric derivatives are categorically absent from v1.
49. Runtime expiry discards in-flight observation results.
50. Daemon stop uses `BoundedSingletonWorker.shutdown`, not `.join`, for camera.
51. Failure classes include camera busy, native shutdown timeout, timebox expired,
    and invalid config.
52. Capability Quarantine fields are visible in spec/docs and test fixtures.

---

## Review Protocol

Camera Presence v1 is covenant-shaped because it changes Maez's body and can
change bonded-user-perceived presence.

Before implementation:

1. Codex engineering panel reviews this spec for runtime completeness,
   shutdown/lifecycle risk, test coverage, and legacy-path closure. Status:
   pending.
2. Claude covenant council reviews this spec for Body Topology, S2-adjacent
   privacy, M1 leakage, and initiative/voice drift. Status: complete, REVISE,
   folded into this draft.
3. Findings fold into the spec. Current fold includes the Claude council's
   twelve load-bearing amendments, substrate-precision amendments, and named
   disagreements D1-D5.
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

## Named Disagreements Preserved

### D1 - Expiry Vocabulary

Choice: preserve BT-CX-8 sensor-state vocabulary. `expired` is not a
`sensor_state`; expiry is represented by `mode = expired_disabled` plus
`sensor_state = disabled`.

Rationale: expiry is an operator-grant lifecycle state, not a sensor condition.

### D2 - `presence_state` vs `owner_presence`

Choice: keep `presence_state` for v1.

Rationale: v1 excludes recognition and therefore cannot claim owner-specific
presence. `owner_presence` is reserved for a future recognition or
bonded-user-verification slice.

### D3 - Implementation Slice vs ADR 0034 Physical Observation Surface

Choice: not decided in this spec. Operator decides whether Camera Presence v1
proceeds as an implementation slice under Decision 24 or whether the physical
observation surfaces named here become a new BAD/ADR (proposed ADR 0034).

Rationale: third-party-in-frame, background-content, and presence-delta
fingerprint surfaces are reusable across future camera, microphone, ambient,
and Jetson sensor slices. The precedent may be worth lifting to law.

### D4 - Direct Question Voice vs Full Silence

Choice: allow deterministic direct-question voice.

Rationale: the bonded user has a direct epistemic interest in bodily state.
Silence or panel-only deferral would make "are you watching me?" harder to ask
than "what does health say?", which is the wrong burden. The response is narrow
state text, not observation voice.

### D5 - Camera Stricter Than Calendar

Choice: Camera v1 is stricter than Calendar v1.

Rationale: Calendar answers direct requests about a structured external account
after S2 redaction. Camera observes physical space continuously during its
timebox. The same "makes visible, never nudges" rule applies, but Camera's
response surface is deliberately smaller.

---

## Rollback

Rollback is simple:

```text
MAEZ_CAMERA_PRESENCE_MODE=disabled
```

or remove the mode configuration entirely. Default disabled posture must close
the camera path without requiring code revert.

If rollback happens during an observation window, health should show disabled or
expired-disabled, not stale present/absent state.

---

## Open Questions for Review

1. Should the v1 enum use `present` or `presence_detected` to avoid over-reading?
2. Is any prompt context acceptable after observation closure, or should it
   be health/panel only until closure?
3. Does `developer_legacy` belong in production code, or should legacy compare
   scripts live outside daemon mode resolution?
4. Should `enabled_until` be environment-backed, local-file-backed, or both?
5. Does the physical-observation surface need new ADR 0034, or is Decision 24
   sufficient?

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
