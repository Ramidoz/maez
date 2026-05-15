# Camera Presence v1 — Codex Post-Implementation Engineering Panel

Date: 2026-05-15

Base implementation: `8ef997d` (`feat(camera): implement v1 disabled body-state boundary`)

Verdict before recovery: **BLOCK / REVISE**

Verdict after recovery: **RATIFY-WITH-RECOVERY**

## Panel Findings

| Seat | Verdict | Finding |
| --- | --- | --- |
| Runtime / Lifecycle | REVISE | Failure and timeout paths did not consistently use the same timebox and shutdown guards as successful observations. OpenCV camera handles needed `finally` release discipline, and disabled-mode shutdown could import native cleanup unnecessarily. |
| Test Contract | BLOCK | The implementation had strong source-level closure tests, but lacked daemon-adapter mapping tests for present/absent/error/timeout/shutdown races, plus explicit tests for model-permission hardening and legacy biometric artifact permissions. |
| Legacy Surface Closure | BLOCK | Public `/api/maez-state` forwarded daemon health broadly enough to expose `camera_presence`, and `memory/source_awareness.json` still carried stale face-recognition-era claims. |
| State / Schema / Body Bus | REVISE | `_presence_unavailable` built a replacement state without assigning it back to the daemon's authoritative camera state. Error classes were free-form instead of a closed vocabulary. |
| Privacy / Security / Model Provisioning | REVISE | Already-valid model files returned before permission hardening. Legacy face-enrollment pickle artifacts were still readable through permissive parent/file modes and needed owner-only checks before unpickling. |
| Observability / Operator Surface | BLOCK | Owner `/health` may expose content-free camera state, but public state must not. Raw detector exception text needed normalization into closed error classes before surfacing. |

## Recovery

The recovery commit closes the findings mechanically:

- Adds a closed camera-presence error-class vocabulary and normalizer.
- Adds token-guarded `commit_unavailable(...)`, using the same observation-token oracle as successful observations.
- Assigns unavailable results into the authoritative daemon camera state so `/health` reflects failures accurately.
- Applies shutdown-started and timebox-expiry guards to success and failure observation paths.
- Strips `camera_presence` from public `/api/maez-state` while preserving owner `/health` telemetry.
- Avoids native OpenCV / MediaPipe shutdown imports when disabled mode never initialized the detector.
- Releases OpenCV `VideoCapture` handles in `finally`.
- Permission-hardens already-valid presence models before returning.
- Requires owner-only parent/file modes before loading legacy face-enrollment biometric pickles.
- Refreshes source-awareness metadata away from legacy face-recognition and `rohit_presence` claims.
- Adds focused regression coverage for daemon-adapter mapping, shutdown races, public surface stripping, model hardening, legacy biometric permissions, and legacy source-awareness closure.

## Verification

Focused recovery suite:

```text
Ran 51 tests ... OK
```

Full suite:

```text
Ran 3557 tests ... OK (skipped=3)
```

`git diff --check` is clean.

## Plain English

The first build gave Maez a quiet eye, but the engineering panel found side doors: public status could still reveal the eye, failures did not always update the real health state, and old biometric paths still had loose permissions. The recovery closes those doors. The eye remains off by default, silent in public surfaces, and bounded by the same token/timebox rules whether it sees, fails, times out, or shuts down.
