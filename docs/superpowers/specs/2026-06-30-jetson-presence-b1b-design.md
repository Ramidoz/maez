# Jetson Presence B1b — Enrollment + Bounded Live Recognition Design

**Date:** 2026-06-30. **Lane:** Codex owns spec, plan, and implementation; Claude holds covenant review; owner runs the biometric witness. **Status:** DESIGN for review. **Scope:** the bounded live recognition slice after B1a. B1b enrolls the owner on the Jetson, computes `present` / `absent` / `unknown`, and can send those labels through the already-witnessed Slice-A doorway. It does **not** daemonize and does **not** make Maez feel or act on presence.

## Why

B0 proved the eye can blink honestly: open, read one frame, close, emit only `unknown`, write nothing. B1a proved the recognition muscle: SCRFD + ArcFace TensorRT runs on the real Orin, ONNX and TensorRT agree inside strict parity, the spike prints only, posts nothing, and writes no frame/crop/vector artifacts.

B1b is the first covenant-heavy recognition slice. It turns the proven local pipeline into an owner-gated enrollment and bounded live producer. This is the moment the eye can assert "Rohit appears present" or "Rohit appears absent," so the no-surveillance and no-false-absence rails have to be load-bearing in code and tests.

## Non-Negotiable Boundary

**"Live" in B1b means what the Jetson sends, not what Maez does with it.**

B1b changes the Jetson producer from B0's always-`unknown` labels to bounded recognition labels. The host doorway remains the same non-consuming shadow intake: validate, store latest, write content-light receipt. B1b must not add a prompt block, heartbeat whisper, greeting, idle-wake rule, private thought trigger, memory promotion, cockpit behavior, or any downstream consumer. The felt flip remains Slice C.

This keeps three moments separate:

1. **The eye asserts presence**: B1b.
2. **The producer stays alive as a service and goes stale safely**: B2.
3. **Maez notices or acts on presence**: Slice C.

## Architecture

B1b extends `devices/jetson_presence/jetson_presence/` with four small units:

| File | Role |
| --- | --- |
| `enrollment.py` | Owner-run ceremony. Captures multiple owner frames, extracts embeddings, calibrates thresholds from the enrollment distribution, and writes one Jetson-local profile. |
| `recognition.py` | Runs the B1a detector/embedder on frames and returns owner-match evidence only. Non-owner candidates are discarded before decision inputs are built. |
| `decision.py` | Pure logic. Converts owner-match evidence + allowed observation-window signals into the five-field `jetson_presence.v0` label. This is where occupancy non-leak and unknown-over-false-absence are enforced. |
| `run.py` | Adds an explicit bounded recognition path, e.g. `--recognize --loops N`. Default B0 behavior remains available and honest. No daemon; B2 owns service cadence. |

Existing reused units:

- `b1a.detector.Detector`, `b1a.embedding.Embedder`, `b1a.matcher.cosine_distance`.
- `labels.build_label` remains the B0 unknown builder; B1b adds a recognition-label builder rather than stretching the B0 helper.
- `emitter.post_label` remains the only network I/O, and only `run.py` may call it.

## Enrollment

Enrollment is **interactive-owner-only**.

- The owner runs a CLI ceremony on the Jetson, in front of the approved camera framing.
- Agents do not run enrollment. It is not triggered by cron, daemon startup, deploy, import, or `run --recognize`.
- The command refuses non-interactive stdin (`sys.stdin.isatty()` false) and requires an explicit confirmation phrase before capture starts.
- Pre-enrollment recognition emits `sensor_state: unenrolled`, `owner_present: unknown`, fixed `confidence: low`.

Enrollment captures multiple owner frames and stores only embeddings plus calibration metadata. Frames and crops remain in RAM and are dropped immediately. The profile never crosses to the host.

## Biometric At Rest

B1b makes an explicit at-rest choice:

**V0 stores the owner profile as Jetson-local restricted plaintext JSON (`0600` file inside a `0700` runtime directory), gitignored, deploy-excluded, and excluded from Maez backups.**

Rationale:

- Device locality and no off-device archive are the load-bearing protections in B1b.
- Encrypting the file with a key stored beside it would be security theater.
- A real encrypted-at-rest design needs an owner-held unlock secret or a Jetson OS credential/keyring design; that is a separate key-management slice and must be solved before claiming encryption.
- B1b is bounded and owner-operated, not daemonized. B2 may revisit profile unlock if persistent service operation needs stronger at-rest posture.

This is not "low sensitivity." The profile is durable biometric material. The spec chooses restricted local plaintext consciously rather than letting it happen by default.

## Threshold Calibration

B1b must not ship a magic match threshold.

During enrollment:

1. Collect a target set of good owner embeddings in the approved desk-presence envelope.
2. Reject enrollment if too few usable owner embeddings are collected.
3. Compute the pairwise owner-distance distribution.
4. Reject enrollment if the owner distribution is too wide for a safe v0 threshold. Wide enrollment means lighting/pose/camera conditions are unstable; the honest result is "try enrollment again," not a permissive threshold.
5. Derive:
   - `owner_intra_p95`: 95th percentile of pairwise owner distances.
   - `present_threshold`: `owner_intra_p95 + margin`.
   - `ambiguous_threshold`: `present_threshold + ambiguity_margin`.

V0 constants:

- `MIN_USABLE_OWNER_EMBEDDINGS = 10`
- `TARGET_OWNER_EMBEDDINGS = 24`
- `MAX_OWNER_INTRA_P95 = 0.55`
- `PRESENT_MARGIN = 0.05`
- `PRESENT_THRESHOLD_CAP = 0.62`
- `AMBIGUITY_MARGIN = 0.10`
- `AMBIGUOUS_THRESHOLD_CAP = 0.72`

Formula:

- Reject enrollment if usable embeddings `< MIN_USABLE_OWNER_EMBEDDINGS`.
- Reject enrollment if `owner_intra_p95 > MAX_OWNER_INTRA_P95`.
- `present_threshold = min(owner_intra_p95 + PRESENT_MARGIN, PRESENT_THRESHOLD_CAP)`.
- `ambiguous_threshold = min(present_threshold + AMBIGUITY_MARGIN, AMBIGUOUS_THRESHOLD_CAP)`.

These constants are deliberately conservative because B1b does not collect live non-owner negative examples. If real owner enrollment is too wide, B1b stops at "try enrollment again" rather than widening until the recognizer becomes convenient.

Runtime three-band rule:

- `distance <= present_threshold` -> strong owner match -> `present`.
- `present_threshold < distance <= ambiguous_threshold` -> ambiguous owner evidence -> `unknown`.
- no owner evidence inside the ambiguous band, across a reliable observation window -> `absent`.

The near-threshold band is intentionally not a generic "someone was seen" band. Ordinary non-owner mismatches are discarded and byte-identical to empty. The ambiguous band exists only to avoid false absence when the recognizer sees owner-like evidence that is not strong enough to assert present.

## Reliable Observation Window

The reliable-observation-window input table is closed:

Allowed inputs:

- `camera_open`
- `frame_health`
- `exposure_blur`
- `model_loaded`
- `enrollment_available`
- `window_duration`

Forbidden inputs:

- non-owner candidate count
- non-owner face clarity
- mismatch-vector strength
- "someone but not Rohit" evidence
- candidate identity labels
- coordinates, crop count, or room occupancy features

Non-owner candidates are discarded before the observation-window input is assembled. A non-owner in frame must not shorten, lengthen, qualify, or disqualify the window. At the decision layer, an empty reliable window and a reliable window full of discarded non-owner mismatches must produce byte-identical labels, including `confidence`.

## Decision Rule

Precedence:

1. Curtain sentinel active -> `sensor_state: curtained`, `owner_present: unknown`, `confidence: low`.
2. Camera unavailable -> `sensor_state: unavailable`, `owner_present: unknown`, `confidence: low`.
3. Enrollment profile missing/unreadable -> `sensor_state: unenrolled`, `owner_present: unknown`, `confidence: low`.
4. Model/load/runtime error -> `sensor_state: error`, `owner_present: unknown`, `confidence: low`.
5. Strong owner match in the window -> `sensor_state: available`, `owner_present: present`.
6. Ambiguous owner evidence in the window -> `sensor_state: available`, `owner_present: unknown`, `confidence: low`.
7. Reliable observation window and no owner evidence -> `sensor_state: available`, `owner_present: absent`.
8. Anything not reliable enough -> `sensor_state: available`, `owner_present: unknown`, `confidence: low`.

Conflicting means more than one candidate crosses the strong owner threshold in the same window, or a strong owner signal is mixed with a model/frame condition that makes the crop untrustworthy. Conflict emits `unknown`, not present/absent.

## Confidence

`unknown` always emits fixed `confidence: low`.

For `present` and `absent`, confidence is a bucketed composite, never a raw cosine distance:

- `present` confidence may use owner-match margin, frame health, and observation strength.
- `absent` confidence may use only the reliable-window allowed inputs: camera open, frame health, exposure/blur, model loaded, enrollment available, and window duration.
- `absent` confidence must not use any non-owner-derived signal.
- The raw distance, raw detection score, candidate count, and any "not Rohit" strength never cross the wire.

## Host Freshness Composition

B1b's device-level absence and Slice A's host-level staleness compose intentionally:

- B1b can emit `absent` only after a reliable device observation window.
- If B1b goes silent, the host ages `received_at` and turns the state into `unknown/stale`, never `absent`.

Both layers err toward unknown. There is no conflict: device absence requires fresh observations; host silence removes absence.

## Accepted Residual Risk

B1b cannot prove "no real stranger ever presents as Rohit" without collecting real non-owner biometric test assets, and collecting those assets is outside the covenant boundary. The false-present risk therefore rests on the calibrated owner threshold, the model's discrimination, the reject-too-wide enrollment gate, and later review of real owner-only witnesses. It is not empirically eliminated in B1b.

This residual is acceptable in B1b only because B1b is non-consuming shadow plumbing. A false-present B1b label can enter the host's existing shadow store/log surface, but it cannot make Maez greet, wake, speak, remember, or act as though Rohit is present. Before Slice C wires presence into any felt behavior, this residual must be re-reviewed and mitigated.

Photo/liveness spoofing is also out of scope for B1b. A clear photo or screen image of Rohit may be classified as Rohit by this v0 recognizer. Liveness / anti-spoofing is a required future design gate before presence can drive owner-facing behavior.

## Structural Guards

B1b must preserve and extend the existing guards:

- No frame/crop/vector writes in recognition paths, except the explicit owner profile written by the enrollment ceremony.
- No profile writes from `run --recognize`.
- No profile artifact copied by `deploy.sh`.
- No raw frame, crop, embedding, candidate, coordinate, or non-owner-derived field in the five-field payload.
- No new host endpoint and no host contract change.
- No downstream consumer on the host.

## Testing Requirements

Host/unit tests must pin:

1. Enrollment profile path is gitignored/deploy-excluded and written with restricted permissions.
2. Enrollment refuses non-interactive invocation.
3. Threshold calibration derives thresholds from owner enrollment distances and rejects too-wide enrollment distributions.
4. Strong owner match -> `present`.
5. Ambiguous owner evidence -> `unknown`.
6. Reliable window + no owner evidence -> `absent`.
7. Degraded / curtain / unavailable / unenrolled / error -> `unknown`.
8. Empty reliable window and non-owner-mismatch reliable window are byte-identical at both:
   - observation-window input, and
   - final emitted label.
9. Unknown confidence is fixed low.
10. Present/absent confidence is bucketed and never raw distance.
11. `run --recognize` uses the existing emitter and host doorway, but does not create any new host consumer.
12. Structural no-frame-write and no-POST guards remain green where they apply; B1b recognition code may import emitter only from `run.py`, never from `decision.py`, `recognition.py`, or `enrollment.py`.

Device witnesses must prove:

- Pre-enrollment bounded recognition emits `unenrolled/unknown`.
- Owner runs enrollment; profile appears only in the Jetson-local runtime directory with restricted permissions.
- Enrollment writes no frames/crops/images/vectors other than the explicit profile JSON.
- Owner present emits `available/present`.
- Owner gone or covered approved view emits `available/absent` only after the reliable window.
- Curtain emits `curtained/unknown` and releases the camera.
- Killing/stopping the bounded run is not B2 staleness yet; B2 owns daemon death and host stale witness.

## Out Of Scope

- Daemon/systemd service, restart safety, and continuous cadence (B2).
- Host heartbeat, greeting, prompt injection, cockpit behavior, or any felt presence consumer (Slice C).
- Liveness / anti-spoofing (photo, screen replay, mask, or similar attacks). Required before any Slice-C felt behavior uses presence.
- Visitor awareness, room occupancy, identity list, spatial zones, raw screen/voice, or third-party recognition.
- Encrypted-at-rest biometric design beyond the explicit v0 restricted-local choice.
- Robust recognition outside the desk-presence envelope.

## Predicted Effect

After B1b, the Jetson can be owner-enrolled and then run a bounded recognition command that sends honest `jetson_presence.v0` labels through the existing doorway: `present` when Rohit strongly matches, `absent` only after a reliable owner-and-frame-only observation window, and `unknown` for uncertainty, curtain, errors, unenrolled state, and ambiguity. The host still only stores/logs the latest shadow label; Maez does not yet feel or act on the signal. Raw frames, crops, non-owner evidence, and embeddings do not cross to the host, and the only durable biometric is the consciously chosen restricted Jetson-local owner profile.
