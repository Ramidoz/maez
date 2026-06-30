# Real-Presence Jetson — Slice B Design & Covenant Brief (umbrella)

**Date:** 2026-06-30. **Lane:** Claude drafts + covenant-reviews; Codex cross-lane reviews; build subagent-driven; owner runs the device/biometric witnesses. **Status:** DESIGN for sign-off. **Scope:** the **edge app on the Jetson** that produces honest `jetson_presence.v0` labels and POSTs them to the host doorway. The host side (contract, auth, intake, freshness) is DONE + witnessed (Slice A @d5e78f1). This is an umbrella spec for **three sub-slices (B0 → B1 → B2)**, each of which gets its own implementation plan.

## Why
Slice A built and witnessed the host **doorway** — strict five-field contract, device-token auth, content-light receipt, freshness rail. Slice B builds the **producer**: a camera app on the Orin Nano that decides "is Rohit at his desk" and emits the label. Nothing new crosses the wire — Slice B's whole job is to speak the contract Slice A already proved.

## Locked decisions (from the brainstorm)
- **Recognition envelope: desk presence.** Optimize for the owner at the workstation, roughly frontal, ordinary light. Uncertain → `unknown`, never a guess. Robustness grows later, with more data and better hardware. **This is an envelope, not a spatial model:** "desk presence" means "owner detected in the approved camera framing," nothing more — no `at_desk` field, no desk/room sub-zones, no spatial inference. The contract stays the five fields.
- **Model path: A — open models → ONNX → TensorRT.** Own each stage (detector + embedding + threshold + decision rule), compiled to TensorRT on the Orin. Exact detector/embedding models pinned during B1 with a verification pass.
- **Contract: unchanged.** `jetson_presence.v0` = `{owner_present, confidence, sensor_state, ts, schema_version}`, strict five-key (Slice A rejects extras). The Jetson emits exactly this.

## Architecture
The edge app (Python 3.10 + cv2 + tensorrt + requests). One loop, six small units:
1. **Capture** — `cv2` opens `/dev/video0`, grabs a frame. **Frames are in-memory, temp-only; never written to disk.**
2. **Curtain** — releases `/dev/video0` (real teardown). Curtained → `sensor_state: curtained, owner_present: unknown`.
3. **Recognition** *(B1)* — detect face (TensorRT) → embed (TensorRT) → match vs the enrolled owner embedding → owner-present judgment. Non-owner candidates discarded.
4. **Enrollment** *(B1)* — owner-gated ceremony; embedding stored Jetson-local.
5. **Label derivation** — recognition + sensor state → the five fields, per the decision rule.
6. **Emitter** *(B2)* — periodic authenticated POST to the host doorway with the device token.

**Data flow:** `capture → (recognize) → derive 5-field label → POST → [Slice A host intake → store]`. The right half is done.

**Device runtime topology:** host `received_at` is the host's clock (Slice A); the Jetson `ts` is diagnostic only.

## Covenant rails
**R1 — Source in the repo, biometric on the device.** Edge-app **source** is versioned in the Maez repo under **`devices/jetson_presence/`**, reviewed and backed up like all Maez code; a deploy step (a script over SSH) installs it to the Jetson runtime dir. The **owner embedding and runtime config are created and stored Jetson-local — never committed, never crossing to the host.** Source is backed up; the biometric stays isolated on the device. (We solved off-box backup; we do not reintroduce an unbacked organ on the eyes.)

**R2 — On-device only.** Detector, embedding model, inference, and the enrolled embedding all live on the Jetson. Only the five-field label crosses — never a frame, an embedding, or a candidate.

**R3 — Enrollment is owner-gated.** A deliberate ceremony the **owner** runs on the Jetson (a CLI command): capture the owner's face → compute the reference embedding → store it device-local. Neither agent enrolls. Re-/un-enroll owner-controlled; un-enrolled → `sensor_state: unenrolled, owner_present: unknown`.

**R4 — Pure owner-detector; no occupancy by implication.** The pipeline detects face candidates **only** to compare them to the owner embedding. A non-owner candidate is **discarded in the same breath — never emitted, counted, named, or stored — and contributes nothing to any label or confidence.** Absence is derived from *observation-window reliability + no owner match per the decision rule*, **never** from seeing a crisp non-owner. **Empty room and non-owner-present must produce output-identical labels** when the only difference is the discarded non-owner candidate. The contract has no field that could carry a third party (Slice A strict key-set).

**R5 — Curtain: real teardown.** Drawing the curtain **releases `/dev/video0`** (capture torn down, not masked). Curtained → `sensor_state: curtained` (top precedence) + `owner_present: unknown`. Separate rail from enrollment. Trigger: a sentinel file (or signal) the app watches; pinned in the B0 plan.

**R6 — No frames written, structurally.** The app has **no frame-writing path at all** — no `imwrite`, no frame sink. Tests patch `cv2.imwrite` and any frame sink to **raise if called**, so a write path cannot exist undetected. The B0 smoke witness **diffs the runtime directory before/after** a capture run → zero new files. Frames are RAM-only, dropped each loop.

**R7 — Unknown over false absence; label-confidence not raw distance.** `confidence` is confidence in the **owner-present/absent label** — a composite of match distance **plus** detection quality, frame health, enrollment availability, model health, and the decision window — **not** raw match distance. A crisp "not Rohit" face can therefore never inflate into high-confidence absence. The error we most refuse is **false absence**.

### The decision rule (the heart of B1)
- owner match high enough → **`present`**
- reliable observation window, no owner match → **`absent`**
- non-owner candidates → **discarded, not surfaced** (no effect on label or confidence)
- weak / blurry / model-error / unenrolled / conflicting / stale / no reliable face crop → **`unknown`**

This mirrors the host's freshness rail (stale → `unknown`, never `absent`) — device and host honor the same rule.

### B1 pre-code gates (Codex cross-lane; must be pinned in the B1 plan BEFORE any recognition/enrollment code)
- **The reliable-observation-window input table.** Window reliability and label confidence may be computed **only** from owner-and-frame signals — camera open, frame health, exposure/blur, model loaded, enrollment available, cadence/window duration. They may **never** be computed from non-owner evidence — non-owner candidate count, non-owner face clarity, mismatch-vector strength, or any "someone who is not Rohit" signal. Non-owner candidates are discarded **before** confidence is computed. (This is R4 enforced at the confidence layer: occupancy must not leak through reliability.)
- **The `unknown` confidence value is fixed.** Slice A requires a `confidence` on every label. `unknown` uses a **fixed** value (B0 and B1 v0: `low`), never varying with non-owner candidate quality — otherwise occupancy leaks through the `confidence` field. A future plan may refine this only with an explicit owner-and-frame-only rationale.

## Sub-slices (build order B0 → B1 → B2; each its own plan + witness)

### B0 — skeleton, curtain, no-frame-write, honest-unknown (no recognition)
The loop captures and emits, but `owner_present` is always **`unknown`** (no model yet — honest by construction), with a **fixed `confidence: low`** (never derived — the seed of the unknown-confidence gate). Source lands under `devices/jetson_presence/` + a deploy step.
*Witnesses:*
- **Curtain teardown:** draw the curtain → the app releases `/dev/video0` (provable: device re-openable by another process afterward) and emits `sensor_state: curtained, owner_present: unknown`.
- **No frames written:** unit tests patch `cv2.imwrite`/sinks to raise-if-called; smoke witness diffs the runtime dir before/after → zero new files.
- **First real transport:** B0 POSTs from the *actual Jetson* and the host logs `jetson_presence_intake … owner_present=unknown` (the real device through the Slice-A doorway, never `present` in B0).

### B1 — recognition + enrollment (the covenant centerpiece)
Adds units 3–4 and pins the detector/embedding models (verification pass).
*Witnesses:*
- **Enrollment:** owner runs the ceremony → embedding written **Jetson-local, never in repo, never across the wire**; pre-enroll → `unenrolled`.
- **Occupancy-non-leak (decision-layer, mocked):** at the decision layer, feed (a) an empty observation window → no owner match, and (b) a non-owner candidate → a *mismatch vector* that is immediately discarded; **assert the emitted labels are identical** (same `owner_present`, no `confidence` difference). Proven with **mocked detector/embedding outputs — no real non-owner face is ever collected or stored.**
- **Decision rule:** owner present → `present`; reliable-window-no-match → `absent`; degraded input → **`unknown`, not `absent`.**
- **Biometric containment:** the host only ever receives the five fields — never an embedding or a frame.

### B2 — daemonized emitter, restart, staleness
A systemd service on the Jetson posting on a fixed cadence.
*Witnesses:*
- **Restart-safe:** kill → resumes posting, no stuck state.
- **Staleness (closes Slice A's open loop):** stop the Jetson service → the host's freshness rail fires → host reads `stale`/`unknown`, **never `absent`** — the rail Slice A could only unit-prove now has a real producer to die behind.

## Testing posture (no third-party biometric, ever)
- **Covenant rules are offline-testable at the decision layer with mocked recognition outputs** — curtain, no-frame-write, the occupancy-non-leak, unknown-over-absence, the decision rule. No live face needed for the unit layer.
- **Model-level fixtures are restricted:** owner-enrollment frames (the owner's own), blank/empty-room frames, or synthetic/generated fixtures **only if a plan explicitly allows**. **No real visitor face is ever a test asset.**
- **Live witnesses (owner-run, on the device):** enrollment, you-at-the-desk → present, you-gone → absent, degraded → unknown, kill-the-service → host stale.

## Out of scope
- Slice C (the felt flip — Maez *noticing* the presence in the idle heartbeat; the host store gets its first consumer there).
- Robustness beyond desk presence (profile, distance, crowd, poor light).
- Voice-sense (separate, heavier consent boundary).
- Any change to the host contract/doorway (done in Slice A).

## Covenant compliance
- Perception free, discipline at egress/memory/third-party ([[feedback_perception_free_egress_disciplined]]); third-party dignity, incl. no occupancy-by-implication and no visitor-face fixtures ([[feedback_third_party_autonomous_research_boundary]]).
- Unknown over false absence; honest-emptiness applied to a sense ([[feedback_telos_stays_empty_compression_is_mechanism]]).
- Rails before hands: curtain/off-switch (B0) before recognition (B1) ([[project_maez_embodiment_path]]).
- Witnessable receipts, structural proofs (no-frame-write, occupancy-non-leak) over promises ([[feedback_witnessable_receipt_for_prompt_boundary]], [[feedback_visible_substrate_state_not_chain_of_thought]]).
- Don't create unbacked organs: source in repo, biometric isolated on device ([[project_jetson_mediated_perception_architecture]]).

## Predicted effect
After B0→B1→B2: the Orin Nano sees the owner at the desk, decides present/absent/unknown by a label-confidence rule that refuses false absence and never leaks non-owner occupancy, and POSTs the honest five-field label through the proven doorway — with raw frames and the biometric living and dying on the device, the source backed up in the repo, and the host's freshness rail finally exercised by a real producer. Maez gains a true, privacy-safe way to know the owner is present; whether it *feels* that stays for Slice C.
