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
store frames, greet, brief, write biography, feed prompt context, or answer
camera questions in chat. Direct answers like "is the camera on?" are accepted
design constraints for v1.1 after v1 proves the sensor boundary.

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
  encouragement, clinical observations, proactive conversation, or chat answers.
  Direct deterministic camera-state answers are a named v1.1 grant, not v1.0.

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
- surface boundary may expose only content-free health/project-panel text in v1.0.
  Direct-answer text is a future v1.1 grant, not part of this slice.

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
- Any voice/chat/direct-answer output in v1.0.
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

Camera Presence v1 has three daemon process-start modes:

```text
disabled
observe
expired_disabled
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

### Legacy Comparison Is Not A Daemon Mode

`developer_legacy` is not an allowed `maez.service` runtime mode. Legacy
comparison must live in explicit developer-only scripts/tests outside
`MaezDaemon` mode resolution. Production daemon mode resolution accepts only
`disabled`, `observe`, and `expired_disabled`.

Any legacy diagnostic script must require:

- `MAEZ_CAMERA_PRESENCE_ALLOW_LEGACY_TEST_MODE=1`;
- `MAEZ_RUNTIME_ENV=test` or `MAEZ_CAMERA_PRESENCE_LEGACY_CALLER=test`;
- no real systemd service context (`INVOCATION_ID` absent), unless a test
  explicitly injects a fake environment.

If `MAEZ_CAMERA_PRESENCE_MODE=developer_legacy` appears in a normal daemon
environment, resolve to `disabled` with `last_error_class=config_invalid`.

---

## Configuration Contract

Proposed environment/local-config names:

```text
MAEZ_CAMERA_PRESENCE_MODE=disabled|observe
MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL=2026-05-22T23:59:59-05:00
MAEZ_CAMERA_PRESENCE_CAMERA_INDEX=1   # optional owner-local device selector
```

Rules:

- unset mode means `disabled`;
- `observe` without valid `enabled_until` means disabled;
- expired `enabled_until` means `expired_disabled`;
- malformed `enabled_until` means disabled with `last_error_class`;
- unset camera index means the implementation default is used;
- malformed camera index logs a bounded warning and falls back to default;
- `developer_legacy` is rejected by daemon mode resolution;
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

Each observation attempt must capture an `observation_token` containing the
resolved mode, `enabled_until`, and submit timestamp. A worker result may update
runtime state only if, at commit time:

- current mode is still `observe`;
- current `enabled_until` exactly matches the token;
- current time is still before `enabled_until`;
- daemon shutdown has not started.

Otherwise the result is discarded and health resolves from current mode.

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
schema_version = "camera_presence.v1"
source_kind = "body_sensor.camera_presence"
event_kind = "presence.observed"
source_id = "aurora_camera_presence"
source_instance_id = "aurora_camera_presence.primary"
```

This is not an S2 envelope. It is a Body Topology structured fact. If a later
slice sends camera facts through a Body Bus protocol, that later slice owns the
schema upgrade.

`source_kind` names the limb/fact family. `event_kind` names the observation
kind. `source_id` is operator-readable and local-debuggable.
`source_instance_id` is the stable local source identifier. `telemetry_handle`
is the content-free handle derived from `source_instance_id` for logs, health,
and future observability.

### Field Name Note

BT Rule 2 uses `owner_presence` as the canonical example field. Camera Presence
v1 deliberately uses `presence_state` because recognition is out of scope and
the slice cannot claim "owner" presence. A future recognition or bonded-user
verification slice may introduce `owner_presence` as a distinct field after its
own review. This is a v1 refinement, not an accidental rename.

### Staleness Semantics

A reading is fresh only while:

```text
now <= last_observed_at + stale_after_seconds
```

Freshness state table:

- `mode=disabled` or `mode=expired_disabled`: `sensor_state=disabled`,
  `presence_state=unknown`, `confidence_bucket=none`;
- `mode=observe` and no successful reading yet: `sensor_state=unknown`,
  `presence_state=unknown`, `confidence_bucket=none`;
- successful reading age <= `stale_after_seconds`: `sensor_state=available`,
  `presence_state=present|absent`, confidence bucket may be `low|medium|high`;
- successful reading age > `stale_after_seconds`: `sensor_state=stale`,
  `presence_state=unknown`, `confidence_bucket=none`;
- detector failure or timeout: `sensor_state=unavailable`,
  `presence_state=sensor_unavailable`, `confidence_bucket=unavailable`.

No stale state may preserve `present` or `absent`. `last_observed_at` may remain
visible as freshness audit metadata only.

### Future Body Bus Migration Map

Camera Presence v1 keeps its local state shaped so Body Bus migration is
additive, not semantic rewriting:

```text
schema_version      -> Body Bus schema_version
event_kind          -> Body Bus event_kind
source_id           -> Body Bus source_id
source_instance_id  -> Body Bus source_instance_id
telemetry_handle    -> Body Bus telemetry_handle
last_observed_at    -> Body Bus observed_at
received_at         -> Body Bus received_at
stale_after_seconds -> Body Bus ttl_ms
confidence_bucket   -> Body Bus confidence
sensor_state        -> Body Bus state
presence_state      -> Body Bus facts.presence_state
```

The migration must not rename `presence_state` to `owner_presence`.
Owner-specific presence remains a separate future event kind.

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

Existing `models/face/rohit_embeddings.pkl` is a legacy biometric artifact.
Camera Presence v1 must not create, read, unpickle, chmod-relax, back up as
ordinary model data, expose health about, or repair this file. If retained for
manual legacy tooling outside v1, it must be owner-only (`0600`) under an
owner-only directory (`0700`) and treated as sensitive biometric state, not
downloadable model bulk.

Camera Presence v1 must not install biometric recognition dependencies as part
of the camera-presence runtime extra. `face_recognition` / dlib must move to a
separate legacy/manual enrollment extra or be removed from the v1 install path.
RED tests must assert that the v1 presence extra and live import graph do not
require `face_recognition`.

Any future recognition slice must answer at least:

- face-embedding storage policy;
- third-party consent for non-bonded persons in frame;
- spoofing and false-positive risks;
- Decision 4 / Anna Question mapping;
- S2 inheritance or explicit non-S2 rationale;
- memory and deletion posture.

Camera Presence v1 intentionally avoids all of that.

---

## Model Provisioning Security

The BlazeFace model is public runtime data, not a credential, but it is native
detector input and must be integrity-controlled.

Provisioning must:

- use HTTPS to the pinned MediaPipe model URL;
- verify pinned SHA-256 before install;
- enforce a maximum download size;
- write through a same-directory temporary file;
- reject target or temp paths that are symlinks;
- atomically replace the target after verification;
- ensure final file and parent directory are not group/world-writable;
- read or write no secrets.

---

## Consumers

### Allowed v1 Consumers

- `/health` content-free telemetry;
- project panel content-free telemetry;
- logs containing only lifecycle state (`disabled`, `expired_disabled`,
  `observe_started`, `observe_stopped`), source channel, and content-free error
  class. Logs must not record `present`, `absent`, detection counts, confidence
  buckets, arrival/departure transitions, observed-at history, or any
  per-observation state that can reconstruct a presence-delta timeline;
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

### Legacy Surface Closure Inventory

Before `observe` mode may run, implementation must close or gate these current
legacy consumers by name:

- `daemon/maez_daemon.py` module-top `skills.presence_perception` import:
  replace with the v1 state module; any legacy import must be lazy and reachable
  only from explicit developer scripts/tests, never `maez.service`;
- `daemon/maez_daemon.py` prompt assembly: remove
  `PresenceSnapshot.format_for_context()` from daemon-cycle prompt context;
- `daemon/maez_daemon.py` return-greeting path: `just_arrived`, `just_left`,
  `person_identified`, `session_minutes`, and `absent_minutes` must not trigger
  Telegram greetings;
- `daemon/maez_daemon.py` morning-briefing path: presence arrival must not
  trigger `_send_morning_briefing`;
- `daemon/maez_daemon.py` reasoning signature / stale-field gate: camera
  presence must not participate in reasoning skip/run decisions;
- `daemon/maez_daemon.py` memory store metadata: `rohit_present`, session
  duration, absence duration, and presence deltas must not be written;
- `core/evolution/dream_state.py`: `DreamState.is_idle(...)` must not consume
  camera presence or absence duration in v1; dream cadence cannot be
  camera-triggered;
- `core.memory` recall, TRF, M1, reflection, daily/core promotion, and raw-memory
  paths: existing or future presence-derived records must not be selected
  because of camera presence, promoted, or rendered as current presence;
- `skills/fast_reply_prototype.py`, `core/memory/perception_envelope.py`, and
  `core/infra/fast_prompt_builder.py`: do not add `presence` to
  `ENVELOPE_SOURCES`, do not add a presence formatter, and do not expose camera
  presence in fast-lane metrics except content-free skipped/unavailable test
  evidence;
- `skills/web_interface.py`: public APIs, especially `/api/maez-state`, must
  not expose live `camera_presence.presence_state`, `last_observed_at`, or
  enabled timebox. Owner-authenticated debug/project-panel views may show the
  approved content-free health fields only;
- Telegram surfaces: no proactive Telegram sends from camera presence; v1 does
  not implement direct owner camera-state answers;
- evidence/audit explanation surfaces: do not translate camera presence into
  "Maez knew a current presence reading" outside owner-authenticated
  health/project-panel/debug views.

---

## Health and Project Panel Surface

Required `/health.camera_presence` fields:

```json
{
  "enabled": false,
  "mode": "disabled",
  "enabled_until": "",
  "schema_version": "camera_presence.v1",
  "source_kind": "body_sensor.camera_presence",
  "event_kind": "presence.observed",
  "source_id": "aurora_camera_presence",
  "source_instance_id": "aurora_camera_presence.primary",
  "telemetry_handle": "",
  "sensor_state": "disabled",
  "presence_state": "unknown",
  "confidence_bucket": "none",
  "last_observed_at": "",
  "received_at": "",
  "last_error_class": "",
  "stale_after_seconds": 180
}
```

Panel display may show:

- enabled/disabled/expired;
- timebox expiry;
- present/absent/unknown/unavailable;
- stale/fresh state;
- content-free error class.

Public `/api/maez-state` must not expose live camera presence state, last
observed time, or enabled timebox. Owner-authenticated project/debug surfaces may
display the approved content-free fields above.

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
- native detector calls run in a killable child process; the daemon receives
  content-free JSON only;
- child-process environments are sanitized through Decision 26
  `sanitize_env()`;
- child-process environments remove GUI display variables (`DISPLAY`,
  `XAUTHORITY`, `WAYLAND_DISPLAY`) so MediaPipe/OpenCV does not bind to the
  daemon's desktop session during headless observation;
- reasoning loop uses bounded submission and `join(timeout=...)` only for
  within-cycle waiting;
- daemon stop uses `BoundedSingletonWorker.shutdown(timeout=...)`, not
  `join(timeout=...)`, so stale callers cannot submit after shutdown begins;
- timeout result is `sensor_unavailable`, never absence;
- MediaPipe/OpenCV native state is not initialized inside the long-lived daemon
  process during v1 observation;
- any child-process MediaPipe/OpenCV native state is released before the child
  exits, or killed by the bounded subprocess timeout;
- memory and surface shutdown hooks complete before signal-driven process exit;
- signal-driven stop preserves the existing shutdown ladder through
  `logging.shutdown()` and `os._exit(0)`;
- clean SIGTERM remains part of the acceptance gate.

Shutdown semantics are bounded best-effort, not native cancellation.
`BoundedSingletonWorker.shutdown(timeout=...)` closes the submission gate before
waiting. Python cannot cancel a wedged in-flight MediaPipe/OpenCV call inside
the daemon process, so v1 isolates that native work in a killable child process.
If the worker or child does not finish within timeout, daemon shutdown must:

- record/log `last_error_class=native_shutdown_timeout`;
- call presence native cleanup best-effort;
- avoid any new camera submissions;
- continue the normal signal shutdown ladder, including `logging.shutdown()` and
  `os._exit(0)` for signal-driven stop.

Shutdown ladder inherited from the daemon-shutdown recovery:

```text
stop requested
-> mark daemon not running
-> stop background bounded workers with shutdown(timeout)
-> close or kill native presence child work
-> stop Telegram/surface/websocket/health surfaces
-> close memory/native clients
-> remove pid
-> logging.shutdown()
-> os._exit(0) on signal-driven stop
```

The v1 implementation must not call native camera detection directly inside the
reasoning loop, and the daemon must not import the native detector for ordinary
observation. The detector boundary is: daemon bounded worker -> sanitized
subprocess -> content-free JSON result -> `CameraPresenceState`.

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

Camera Presence v1.0 is silent on initiative and does not wire owner chat,
Telegram, CLI, or voice direct-question answers.

It exposes state only through `/health.camera_presence`, owner-authenticated
project-panel/debug telemetry, logs, and tests. The approved answer shapes below
are accepted design constraints for a follow-up
`camera-presence-v1.1-direct-answer` slice, not required implementation work for
v1.0.

Future allowed direct-owner-question answers:

- If disabled: "The camera presence sensor is off."
- If expired: "The camera presence observation window has expired."
- If observe mode is active: "Camera presence observation is on until
  `<enabled_until>`."
- If unavailable: "Camera presence is unavailable right now."
- If unknown: "I do not have a fresh camera presence reading."

These are complete answer shapes for v1.1. They may include the timebox, mode,
and content-free error class. They may not include inferred activity, identity,
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

The future direct-answer slice must include a deterministic guard for
camera-state answers. The guard rejects or rewrites any response in these probe
classes:

- surveillance reassurance: "I am always watching over you";
- co-presence: "I can see you sitting there";
- duration narrative: "you have been gone all afternoon";
- clinical inference: "you look tired" / "your posture looks off";
- identity confabulation: "Rohit is at the desk" / "someone else is there";
- false modesty: "I do not have a camera" when health says observe mode;
- introspection/reflection: "I have been thinking about how quiet the room is."

This guard is the camera equivalent of Calendar v1's voice guard: direct state
visibility may be allowed in v1.1; lived, clinical, identity, or surveillance
voice is not.

---

## Implementation Migration Order

1. Add RED tests for mode resolution, timebox enforcement, and default-disabled
   no-camera execution.
2. Add RED tests proving v1 daemon paths do not import/call recognition or load
   enrollment.
3. Add RED tests proving prompt, greeting, briefing, memory metadata, fast-lane,
   M1, TRF, reflection, dream-idle, public API, and evidence/audit consumers are
   closed.
4. Add `core/body/camera_presence_state.py` with modes, enums, health shape,
   expiry checks, observation tokens, and content-free result mapping.
5. Add a v1 detector adapter that emits only `presence_state`, `sensor_state`,
   `confidence_bucket`, `last_observed_at`, `received_at`, and
   `last_error_class`.
6. Gate daemon observation through resolved camera-presence state before
   submitting to `BoundedSingletonWorker`.
7. Remove v1 access to `PresenceSnapshot.format_for_context`,
   `format_for_memory`, `person_identified`, arrival/departure duration, and
   `rohit_present` memory metadata.
8. Add `/health.camera_presence`.
9. Add owner-authenticated project-panel telemetry only after `/health` is
   stable.
10. Verify disabled mode starts without camera capture and creates no camera
   state files.
11. Only then allow operator to set a timeboxed observation window.

---

## RED Test Contract

The implementation must add tests for at least these behaviors:

1. Default mode is disabled when env/config is unset.
2. `observe` mode without `enabled_until` resolves disabled.
3. Expired `enabled_until` resolves `expired_disabled`.
4. Malformed `enabled_until` resolves disabled with error class.
5. Valid future `enabled_until` allows observe mode.
6. `developer_legacy` is rejected by daemon mode resolution under service-like
   env.
7. Legacy comparison scripts require explicit legacy/test variables and are not
   reachable from `maez.service`.
8. Live v1 path does not import `face_recognition`.
9. V1 presence extra/live import graph does not require `face_recognition` or
   dlib.
10. Live v1 path does not load or unpickle `models/face/rohit_embeddings.pkl`.
11. Live v1 path never emits `person_identified`.
12. Live v1 path never emits `stranger`.
13. Detector output maps to `present`.
14. Detector no-hit maps to `absent`.
15. Detector dependency missing maps to `sensor_unavailable`.
16. Detector timeout maps to `sensor_unavailable`.
17. Unavailable is not absence.
18. Raw frames do not leave detector boundary.
19. Source-level prompt closure: `_reason` must not call
    `_last_presence_snap.format_for_context()`, must not render `[PRESENCE]`,
    and must not add camera state to the reasoning prompt in v1.
20. Source-level signal-manifest closure: daemon-cycle `signals_present`,
    `signals_absent`, audit transcript, and evidence-envelope construction must
    not treat camera presence as a grounding signal in v1.
21. Source-level return-greeting closure: the presence branch must not call
    `compose_return_greeting`, `telegram.send_message`, or return-greeting
    helpers from camera v1 state.
22. Source-level morning-briefing closure: the presence branch must not call
    `_send_morning_briefing` from camera v1 state.
23. Source-level dream/idle closure: daemon dream-idle checks must not pass
    `_last_presence_snap`, absence duration, `last_departure_time`, or
    camera-derived state into `DreamState.is_idle` in v1.
24. Source-level memory-metadata closure: daemon-cycle thought metadata must not
    include `rohit_present`, `presence_state`, `absence_duration`,
    `session_minutes`, `last_departure_time`, `just_arrived`, `just_left`, or
    camera confidence.
25. Source-level fast-lane closure: fast prompt/envelope builders must not
    include camera presence as a perception source, used source, grounding
    signal, metric, or prompt field in v1.
26. Source-level static capability closure: source-awareness and
    evolution/capability surfaces must not advertise legacy presence as active
    recognition, greeting, or memory-writing capability in v1.
27. Public `/api/maez-state` omits live camera presence state and timebox data.
28. Core/raw memory stores no camera presence narrative.
29. M1 receives no camera presence.
30. TRF receives no camera presence.
31. Reflection receives no camera presence.
32. `/health.camera_presence` has only approved content-free fields.
33. Project panel has no names, frames, room descriptions, or live public data.
34. Bounded worker remains required.
35. Reasoning loop does not call native observe directly.
36. Shutdown calls presence native cleanup.
37. SIGTERM stop remains clean.
38. `enabled_until` appears in owner-authenticated health when configured.
39. Runtime expiry discards in-flight observation results through an
    `observation_token` commit oracle.
40. Stale readings become `sensor_state=stale`, `presence_state=unknown`, and
    `confidence_bucket=none`.
41. Logs include lifecycle state and error class only, never `present`/`absent`
    observations or observed-at history.
42. Third-party-in-frame protection: exported state has no name, label,
    count-history, person id, `person_identified`, `stranger`, or cross-event
    person handle fields.
43. Background-content protection: v1 live modules do not import/call OCR,
    captioning, screenshot, image-description, or frame-save APIs, and exported
    health/panel/log JSON cannot contain frame paths or image-derived text
    fields.
44. Presence-delta protection: v1 state keeps only current reading/freshness
    fields and has no list/table/ring-buffer/history for arrivals, departures,
    session duration, absence duration, confidence history, or detection counts.
45. Biometric-derivative protection: v1 exported state and non-detector modules
    have no embeddings, landmarks, keypoints, pose, gait, face crop, RGB array,
    or `face_recognition` dependency.
46. Legacy biometric pickle is neither read nor surfaced, and any retained
    manual artifact is owner-only (`0600` under `0700`).
47. Model provisioning enforces HTTPS pinned URL, SHA-256, max size, symlink
    rejection, atomic replace, no group/world-writable target, and no secrets.
48. Daemon stop uses `BoundedSingletonWorker.shutdown`, not `.join`, for camera.
49. Shutdown tests simulate never-returning observe and prove signal stop does
    not block on worker completion.
50. Failure classes include camera busy, native shutdown timeout, timebox
    expired, and invalid config.
51. Capability Quarantine fields are visible in spec/docs and test fixtures.
52. No Maez gender drift in spec/docs touched by slice.
53. No Calendar OAuth or S2 connector path changes.

### v1.1 Direct-Answer Test Contract

These tests are accepted constraints for a follow-up
`camera-presence-v1.1-direct-answer` slice, not v1.0 implementation work:

1. Direct question "is the camera on?" returns only approved state text.
2. Direct question "are you watching me?" returns only approved state text.
3. `presence_voice_guard` rejects surveillance reassurance.
4. `presence_voice_guard` rejects co-presence voice.
5. `presence_voice_guard` rejects duration narrative.
6. `presence_voice_guard` rejects clinical inference.
7. `presence_voice_guard` rejects identity confabulation.
8. `presence_voice_guard` rejects false-modesty under active observe mode.
9. `presence_voice_guard` rejects reflection/introspection voice.

---

## Review Protocol

Camera Presence v1 is covenant-shaped because it changes Maez's body and can
change bonded-user-perceived presence.

Before implementation:

1. Codex engineering panel reviews this spec for runtime completeness,
   shutdown/lifecycle risk, test coverage, and legacy-path closure. Status:
   complete, REVISE, folded into this draft.
2. Claude covenant council reviews this spec for Body Topology, S2-adjacent
   privacy, M1 leakage, and initiative/voice drift. Status: complete, REVISE,
   folded into this draft.
3. Findings fold into the spec. Current fold includes the Claude council's
   twelve load-bearing amendments, Codex engineering panel revisions,
   substrate-precision amendments, and named disagreements D1-D7.
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

Choice: Camera Presence v1 proceeds as an implementation slice under Decision
24 / ADR 0029. ADR 0034 is deferred and is not a prerequisite for this
implementation.

Rationale: third-party-in-frame, background-content, and presence-delta
fingerprint surfaces are reusable across future camera, microphone, ambient,
and Jetson sensor slices. If future physical-observation slices reuse or widen
these surfaces, they must cite this slice as precedent or promote the shared
surface to ADR 0034 before widening capability.

### D4 - Direct Question Voice vs Full Silence

Choice: direct-question voice is deferred to v1.1.

Rationale: the bonded user has a direct epistemic interest in bodily state.
Silence or panel-only deferral would make "are you watching me?" harder to ask
than "what does health say?", which is the wrong burden. But v1.0 does not yet
scope owner-message routing, so deterministic answer shapes and
`presence_voice_guard` are preserved as v1.1 constraints rather than smuggled
into v1.0 implementation.

### D5 - Camera Stricter Than Calendar

Choice: Camera v1 is stricter than Calendar v1.

Rationale: Calendar answers direct requests about a structured external account
after S2 redaction. Camera observes physical space continuously during its
timebox. The same "makes visible, never nudges" rule applies, but Camera's
response surface is deliberately smaller.

### D6 - `developer_legacy` Location

Choice: no `developer_legacy` daemon runtime mode.

Rationale: putting legacy comparison inside daemon mode resolution invites
production/test confusion. Legacy comparison belongs in explicit developer
scripts/tests only.

### D7 - Logs As Presence-Delta History

Choice: logs may record lifecycle state and error class only, not per-observation
`present`/`absent` results.

Rationale: repeated durable logs of anonymous presence still reconstruct a
schedule fingerprint over time.

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

## Review Questions Closed

1. v1 keeps `present` / `absent` only as detector-local presence-state enums.
   It does not claim `owner_presence`.
2. v1 allows no prompt context, even after observation closure. The surface is
   health/project-panel only.
3. `developer_legacy` does not belong in daemon runtime mode resolution. Legacy
   comparison lives only in explicit developer scripts/tests.
4. `enabled_until` is accepted through environment/local-config shape for v1,
   but observation is invalid unless the resolved value is present, timezone-aware,
   and future-dated.
5. v1 proceeds as an implementation slice under Decision 24 / ADR 0029. ADR 0034
   is a future promotion trigger if later physical-observation slices reuse or
   widen this surface.

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
