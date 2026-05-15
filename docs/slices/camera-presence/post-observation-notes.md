# Camera Presence v1 Post-Observation Notes

Date: 2026-05-15
Status: SMOKE CEREMONY PASSED; ONE-WEEK OBSERVATION NOT STARTED

Maps to:

- Spec: `docs/slices/camera-presence/spec.md`
- Decision 24 / ADR 0029: Body Topology
- Decision 26 / ADR 0031: Daemon Credential Hygiene
- Implementation commits: `8ef997d`, `4de711e`, `cc75520`, `007b665`, `63263aa`

## Plain English

The eye opened only because the operator gave it a short timebox. It looked,
reported only anonymous presence state, survived an interrupt while active, and
returned to locked mode afterward.

This was not the one-week observation gate. It was the first deliberate body
sensor ceremony: open the eye, watch it behave, interrupt it, restart it, and
lock it again.

## What Was Proven

### Smoke Window

The first smoke window validated the basic lifecycle:

- `MAEZ_CAMERA_PRESENCE_MODE=observe`;
- valid future `MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL`;
- owner-local `MAEZ_CAMERA_PRESENCE_CAMERA_INDEX=1`;
- content-free readings only;
- expiry back to `mode=expired_disabled`;
- `presence_state=unknown` after expiry;
- `last_error_class=timebox_expired` after expiry;
- no stranded `presence-observ` or `mediapipe` threads.

The load-bearing result is that the last `present` or `absent` claim did not
survive the timebox. Expiry returned the sensor to unknown/disabled state.

### SIGTERM-During-Active-Camera Ceremony

The second ceremony validated the harsh shutdown path:

- SIGTERM was triggered while the daemon was in `presence_perception`;
- `systemctl --user stop maez.service` returned successfully;
- stop elapsed time was approximately 2058 ms;
- systemd did not escalate to SIGKILL;
- the old daemon PID exited;
- no camera child process survived;
- no `presence-observ` or `mediapipe` threads remained;
- the daemon restarted cleanly;
- the next camera cycle produced a content-free `present` reading;
- temporary camera environment variables were cleared afterward;
- final state returned to `mode=disabled`, `sensor_state=disabled`,
  `presence_state=unknown`.

The load-bearing result is that the camera can be interrupted during an active
cycle without leaving native runtime state behind.

## Substrate Lessons

### 1. Native Sensor Limbs Should Prefer Killable Child Processes

Commit `007b665` moved MediaPipe/OpenCV detection out of the long-lived daemon
and into a short-lived child process. The live SIGTERM ceremony validated that
this was not merely an implementation detail. It was the load-bearing
survivability mechanism.

Thread-level discipline is still useful:

- bounded worker submission protects the reasoning loop;
- `BoundedSingletonWorker.shutdown(timeout=...)` closes the submission gate;
- explicit shutdown keeps the daemon ladder finite.

But native libraries can hold threads outside Python's control. For native
sensor limbs, the stronger pattern is:

```text
daemon cycle
-> bounded worker
-> sanitized child process
-> native detector
-> content-free JSON
-> validated body-state dataclass
```

Future microphone, Jetson camera, ambient-sensor, or native-library body limbs
should start by asking whether their detector can run behind the same killable
child-process boundary.

### 2. Minimal Subprocess Environment Is Broader Than Secret Hygiene

Commit `63263aa` stripped `DISPLAY`, `XAUTHORITY`, and `WAYLAND_DISPLAY` from
the detector child process. The empirical finding was that the detector could
hang when it inherited the daemon's desktop-session environment, even though it
worked headless.

Decision 26 originally framed subprocess environment discipline around
credential exposure. Camera Presence broadens the operational lesson:

```text
child process environment should be minimal by default,
with exact-name opt-in for what the child truly needs.
```

For this slice, the child needed the camera index and ordinary runtime context.
It did not need desktop-session authority or identity-bearing credentials.

Future native limbs should treat inherited environment as a capability surface,
not just a convenience.

### 3. Operator-Local Device Selection Is Configuration, Not Law

Commit `cc75520` added `MAEZ_CAMERA_PRESENCE_CAMERA_INDEX`. This is an
owner-local hardware selector, not a covenant rule. It exists because the live
machine exposes the usable camera at `/dev/video1`, not `/dev/video0`.

The covenant boundary remains unchanged:

- selecting a camera device does not authorize observation;
- observation still requires `observe` mode and a valid future timebox;
- stale or malformed config fails neutral.

### 4. Observers Must Be Calibrated To Their Actual Layer

The end-of-day session snapshot initially reported Maez services as inactive
because the generator queried system-level `systemctl` units while Maez is
running as user-scoped `systemctl --user` units on this host. That would have
sealed a false record: Maez alive in the user manager, but "inactive" in the
durable snapshot.

The fix was small (`eccbbd3`), but the lesson is substrate-shaped:

```text
observers must be truthful about the layer they actually observe.
```

For snapshot generators, sidecars, `/health` readers, audit summaries, and
future review tools, calibration is load-bearing. A truthful observer must
name and test its boundary:

- user systemd units vs system units;
- parent daemon process vs detector child process;
- `/health` aggregate counters vs content stores;
- native thread counts vs Python worker names;
- enabled mode vs timebox-expired mode.

An observation surface that reads the wrong layer can become worse than no
surface, because it gives future operators durable false certainty. Future
observation tools should ship with regression tests proving they query the
intended layer, not the default layer their library or command happens to use.

## What Was Not Proven

These ceremonies did not start the one-week observation gate. Persistent
enablement remains out of scope until a deliberate longer observation window is
run and closed against the spec criteria.

These ceremonies also did not add chat answers about camera state. Direct
answers such as "is the camera on?" remain a v1.1 design constraint, not v1.0
behavior.

## Carry-Forward

Future body-sensor specs should copy this posture:

- timebox first;
- default-disabled;
- no raw sensor material beyond the detector boundary;
- killable child process for native detectors where practical;
- sanitized/minimal child environment;
- content-free JSON result;
- frozen validated state object;
- no prompt, memory, greeting, or briefing consumer unless separately reviewed;
- live ceremony for open -> observe -> expiry;
- live ceremony for SIGTERM during active observation.
- observer tools calibrated to the exact layer they claim to report.

Plainly: if a future organ needs native code to sense the world, keep that
native code in a room Maez can lock from the outside.
