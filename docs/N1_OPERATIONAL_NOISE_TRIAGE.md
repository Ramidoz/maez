# N1 Operational Noise Triage — 2026-05-13

This note classifies the three operational noise sources separated from S1b so
they do not get normalized as permanent background errors.

## Dispositions

| Noise source | Disposition | Result |
| --- | --- | --- |
| Google Calendar OAuth `invalid_grant` | fix by owner reauth; code classifies until then | Calendar returns a specific reauthorization error and backs off repeated credential refresh attempts for one hour. |
| Missing `mediapipe` in presence detection | fix dependency/model path if presence is desired; code prevents false absence | Presence returns `success=False` when the sensor stack is unavailable instead of converting dependency failure into "owner away." Missing dependency warnings log once per dependency. |
| WebSocket invalid HTTP handshake tracebacks | accept as non-WebSocket probe noise; code filters only that dependency traceback | The daemon suppresses `websockets.server` "opening handshake failed" records caused by invalid/empty HTTP handshakes while leaving real websocket server failures visible. |

## Boundary

This is an operational hardening slice. It does not wire S1b, change private
thoughts behavior, or alter the canonical conversation result. The live service
must restart before the daemon-side filter and perception changes affect the
running process.
