# N1 Operational Noise Triage — 2026-05-13

This note classifies the three operational noise sources separated from S1b so
they do not get normalized as permanent background errors.

## Dispositions

| Noise source | Disposition | Result |
| --- | --- | --- |
| Google Calendar OAuth `invalid_grant` | fix by owner reauth; code classifies until then | Calendar returns a specific reauthorization error and backs off repeated credential refresh attempts for one hour. |
| Missing `mediapipe` in presence detection | fixed on Aurora; code prevents false absence if it regresses | `mediapipe` is declared in the `vision` extra and `scripts.provision_presence_model` provisions the verified BlazeFace model. Presence returns `success=False` when the sensor stack is unavailable instead of converting dependency failure into "owner away." |
| WebSocket invalid HTTP handshake tracebacks | accept as non-WebSocket probe noise; code filters only that dependency traceback | The daemon suppresses `websockets.server` "opening handshake failed" records caused by invalid/empty HTTP handshakes while leaving real websocket server failures visible. |

## Boundary

This is an operational hardening slice. It does not wire S1b, change private
thoughts behavior, or alter the canonical conversation result. The live service
must restart before the daemon-side filter and perception changes affect the
running process.

## Presence Provisioning

On a fresh body, install the vision stack and provision the ignored detector
asset before expecting `skills.presence_perception.observe()` to succeed:

```bash
.venv/bin/python -m pip install -e '.[vision]'
.venv/bin/python -m scripts.provision_presence_model
```

The detector asset is intentionally under `models/`, which is gitignored. The
provision script downloads MediaPipe's short-range BlazeFace model and verifies
its SHA-256 before writing `models/blaze_face.tflite`.
