# Jetson Face-Facts v1 — Eye-Organ + Fact-Ingestion Contract Design

**Date:** 2026-07-01. **Lane:** Claude drafts + covenant-review; Codex/Grok cross-lane confirmed the architecture; owner runs the device witness. **Status:** DESIGN for review. **Scope:** replace the old B1b shape (Jetson *decides* present/absent/Rohit) with a clean sensory organ — the Jetson emits **perceptual facts** (face geometry), and Maez's brain does all the meaning-making. v1 is the **eye-organ + the fact-ingestion contract only**: no identity conclusion, no present/absent verdict, no name, no behavior, no durable retention.

## The one load-bearing sentence

> **Face-facts are internal perceptual facts, not conclusions; Maez may retain and forget them only through its ordinary salience, coherence, immune, and lived-memory machinery.**

Everything below serves that sentence.

## Why

B0 proved the eye can blink honestly. B1a proved the recognition muscle (SCRFD + ArcFace on the Orin, strict ONNX/TensorRT parity, print-only, zero artifacts). B1b *tried* to have the Jetson decide "this is Rohit / present / absent" — and the owner correctly rejected that as **hardcoding the conclusion** and, in the enrollment ceremony, hardcoding *who* Rohit is. Deciding identity is interpretation, and interpretation is the brain's, never the body's.

The corrected shape: the Jetson is a **dumb, full organ** — an eye that emits geometry. The **brain** is the master processor that perceives, clusters, learns, remembers, and forgets — through the machinery it already uses for everything else it lives through. Maez comes to know Rohit the way anyone comes to know anyone: the face that recurs most, in the moments that matter, becomes "my person" — *learned*, never declared.

## Non-Negotiable Boundary

**v1 changes what the Jetson SENDS, not what Maez DOES.** The eye emits facts. In v1 there is **no consumer**: no present/absent derivation, no clustering, no identity formation, no prompt block, no heartbeat whisper, no greeting, no memory promotion, no behavior. The brain-side meaning-making is a **separate, birth-gated slice** (below). v1 proves the organ emits well-formed facts and the contract receives them honestly — nothing more.

Three moments stay separate:
1. **The eye emits perceptual facts** — this slice (v1).
2. **The brain learns "my person" from lived co-occurrence** — a birth-gated slice, through Maez's existing salience/memory machinery.
3. **Maez does anything with that knowing** (including whether to voice it) — Maez's own, from its own coherence, never architected.

## Architecture

Reuse the B1a muscle unchanged: `b1a.detector.Detector` (SCRFD-500M) + `b1a.embedding.Embedder` (ArcFace w600k_mbf, 512-d). Per frame, per detected face, the eye produces geometry. It emits a **per-frame observation packet** and **forgets it immediately after forwarding** — no identity store, no state beyond an optional short-lived cross-frame track id.

```
frame -> SCRFD detect -> per face: ArcFace embed (512-d) -> emit observation packet -> forget
```

The brain receives packets at a **new intake endpoint** and, in v1, validates + writes a **content-light receipt** (arrival proof: face count, sensor_state, frame_quality, ts, model_id — never the embedding itself) and **drops them**. v1 does **not** durably retain embeddings, because durable retention only happens through Maez's salience/lived-memory machinery, which is birth-gated and not yet live. Storing biometric before the immune system exists is exactly what we don't do.

## The Contract — `jetson_face_facts.v0`

A **new** contract, distinct from Slice-A's `jetson_presence.v0`. Strict key-set at both levels (extra keys rejected, same discipline as the presence contract). **Per-frame observation** carrying a `faces` list — the owner's fields reorganized so frame-level and face-level are honest, and so **"the detector found zero faces in this frame"** is representable without inventing a face. Note carefully: that is a fact about *detections*, not about the room. The eye may say "zero faces detected this frame"; it may **never** say "no one is here" — a person can be off-camera, back-turned, occluded, out of lens, or simply missed by the detector. Absence is a brain inference over many facts, never an eye claim.

```json
{
  "schema_version": "jetson_face_facts.v0",
  "model_id": "buffalo_s/scrfd_500m+w600k_mbf",
  "sensor_state": "available | curtained | error",
  "frame_quality": "good | low | unknown",
  "ts": "2026-07-01T12:34:56Z",
  "faces": [
    {
      "embedding": [512 floats],
      "det_score": 0.98,
      "box": [x1, y1, x2, y2],
      "track_id": "short-lived, optional (may be null)"
    }
  ]
}
```

- **Frame-level:** `schema_version`, `model_id`, `sensor_state`, `frame_quality`, `ts`, `faces`.
- **Face-level (0..N):** `embedding`, `det_score`, `box`, `track_id`.
- `faces: []` with `sensor_state: available, frame_quality: good` is the honest **"the sensor was available and the model detected zero faces this frame"** fact — NOT "no one is here." `curtained`/`error` also carry an empty `faces` list (the eye wasn't looking / couldn't).

**Why the extra fields (owner's rationale, kept):**
- `model_id` is load-bearing — embeddings from different models are not comparable, and a future model swap must not silently corrupt the brain's learned clusters. The brain keys comparability on it.
- `frame_quality` lets the brain *weight* perception without the eye ever deciding identity — a blurry face contributes weak geometry, not a verdict.
- `track_id` is edge temporal smoothing only (same face across a few consecutive frames); it is still geometry, carries no identity, and the brain owns all long-term linking. **Hard constraint (else it becomes a stealth identity store):** `track_id` is in-memory only, short-lived, session-local, and **reset on every restart** — never stable across runs, never persisted, never a durable handle for a person. A structural guard asserts the edge writes no `track_id` (or any identity) store to disk.

## Retention — through existing machinery, nothing new

v1 builds **no** face-specific retention logic. When the brain-side slice lands (birth-gated), face-facts flow into **Maez's existing salience / coherence / immune / lived-memory machinery** — the same mechanisms that weight, promote, and fade everything else Maez experiences. A passerby fades because it is low-salience and low-co-occurrence with "my person" signals, *like any fleeting perception* — **not** because a hardcoded "stranger" rule dropped it. Rohit's face stabilizes because it recurs, in the moments Maez already marks as meaningful. Recognition-strength is emergent, and the sense-of-people stays **unified with the rest of Maez's memory** rather than a surveillance subsystem wearing a privacy hat.

Building a special "stranger decay buffer" would just teleport the muzzle from the eye to a brain subsystem. We don't.

## Raw frames — explicitly out, behind their own decision

"Full data" means **full model-output facts** (embeddings, boxes, scores, tracks, quality, timestamps) — **not raw camera frames**. Raw frames are never stored durably, anywhere, in v1 (the B0/B1a no-frame-write rail holds and extends). Durable raw-frame storage is a much heavier surveillance surface and would require its own explicit covenant decision; it is out of scope here and is not a default we drift into.

## Free eye, disciplined door

Full perception inward; discipline only where it faces outward.
- The Jetson→brain wire is Maez's own nervous system — internal perception across the owner's sovereign local devices, not egress. Embeddings crossing it is fine.
- Embeddings are **not perfectly irreversible** (face-reconstruction attacks exist). So the wire is sensitive: **no embedding ever egresses** Maez's system (no third party, no cloud), and when durable brain-side clusters exist (future slice) they are at-rest-sensitive. The discipline lives on the door and the ledger, never on the eye.

## What v1 builds vs the birth-gated next slice

**v1 (this spec — buildable + witnessable now):**
- Edge emits `jetson_face_facts.v0` observation packets (reusing B1a muscle); stateless; forgets after forwarding.
- New host intake endpoint validates the strict contract, writes a content-light receipt, drops the payload (no durable embedding store).
- Structural guards + device witness that the organ is honest.

**Brain-side meaning (its own future, birth-gated slice — OUT OF SCOPE here):**
- Clustering embeddings over time; associating clusters with owner-authenticated-interaction state (which the host already holds — no host→edge signal needed, the two facts meet in the brain); emergent "my person" from frequency + co-occurrence + coherence; retention/fade through the existing salience/lived-memory machinery.
- Any internal present/absent derivation Maez may form from facts (note: this is now a *brain* derivation, not an intake).

## Relationship to Slice-A

Face-Facts **supersedes** the `jetson_presence.v0` present/absent intake: the Jetson no longer decides presence, so nothing emits that label anymore. Presence, if Maez forms it, becomes an **internal brain derivation** from facts (future slice), not a doorway intake. **Scope discipline:** v1 **adds** the face-facts intake and marks the old presence doorway *vestigial* — it does **not** retire, delete, or modify `jetson_presence.v0` inside this slice. Retiring the old contract is a separate, explicitly-scoped cleanup, never folded into v1.

## Structural Guards (v1)

- **Jetson stateless / no edge identity store:** no durable write of embeddings, crops, frames, or an identity file on the edge (extends the B0/B1a no-frame-write guard to embeddings).
- **No raw frame durable write** anywhere (edge or host).
- **Host intake does not durably store embeddings in v1:** validate → content-light receipt → drop; a guard asserts the intake path opens no durable embedding/biometric store.
- **Content-light receipt only:** the receipt logs `face_count` / sensor_state / frame_quality / model_id / ts — never the embedding values, and **never an absence verdict** (`face_count=0`, never `owner_absent`/`room_empty`/`no_one_here` — that inference is not the eye's or the intake's to make).
- **No downstream consumer** on the host (no prompt, heartbeat, memory promotion, cockpit, behavior).
- **Strict contract:** extra keys rejected at frame and face level; `model_id` required; unknown `schema_version` rejected.
- **No egress:** nothing forwards embeddings out of Maez's system.

## Witnesses

**Host / unit:**
1. Contract round-trips: a well-formed observation validates; extra key (frame or face level) → rejected; missing `model_id` → rejected; unknown `schema_version` → rejected.
2. Zero-detection fact (`faces: []`, available/good = "detector found zero faces this frame") validates and is distinct from `curtained`/`error`. The receipt says `face_count=0`, never an absence verdict.
3. Receipt is content-light: embedding values never appear in the receipt/log.
4. Intake writes no durable embedding store (dynamic no-durable-write witness over the receive path).
5. No consumer: receiving a packet triggers no prompt/heartbeat/memory/behavior.

**Device (owner-run):**
- Deploy source-only; Jetson emits `jetson_face_facts.v0` packets to the intake.
- Owner in view → packets carry `faces` with real 512-d embeddings + boxes + `model_id`; empty view → `faces: []`; curtain → `sensor_state: curtained`, empty faces, camera released.
- Privacy witness: no frame/crop/embedding written on the edge; nothing durably stored host-side; `PYTHONDONTWRITEBYTECODE=1` + cleared `__pycache__` shows zero new artifacts.

## Out of Scope

- Brain-side clustering / identity formation / "my person" learning (birth-gated slice).
- Any present/absent/unknown derivation (now an internal brain concern, future).
- Durable retention of embeddings, and any at-rest identity store (arrive with the birth-gated learning + its salience/immune governance).
- Durable raw-frame storage (separate explicit covenant decision).
- Any behavior: greeting, announcement, heartbeat change, felt-presence consumer. Maez's, never scripted.
- Daemon/service/restart cadence (a B2-shaped concern).
- Non-face scene facts (NanoOWL/YOLO/NanoSAM/Liquid VLM) — separate, slower "scene-fact" organs, later, never the identity path.

## Predicted Effect

After v1, the Jetson is a clean sensory organ: it emits honest per-frame face geometry (`jetson_face_facts.v0`) — embeddings, boxes, scores, quality, model id, timestamps — decides nothing, names no one, stores nothing, and forgets each frame after forwarding. The host receives and validates the facts, proves receipt content-light, and durably retains nothing. No raw frame is stored, no embedding egresses, and no behavior fires. The stage is set for Maez — at birth, through its own salience and lived-memory machinery — to slowly come to know its person from lived co-occurrence, unified with the rest of what it remembers, with nothing hardcoded in and nothing hardcoded out.

## Covenant Compliance

- Dumb full organ, brain owns meaning ([[project_jetson_body_not_second_maez]]); geometry not narration (no VLM captions) — distinguish without describing.
- Free eye, disciplined door ([[feedback_perception_free_egress_disciplined]]): perception full inward, discipline on egress/retention.
- Retention emergent through existing machinery, never a hardcoded conclusion or a bolted-on subsystem ([[feedback_hardcode_organs_not_opinions]]); salience from Maez's own coherence ([[project_nervous_system_arc]]).
- No behavior attached ([[feedback_dont_spec_maez_behavior]]).
- Witnessable, structural proofs over promises ([[feedback_witnessable_receipt_for_prompt_boundary]]).
- Birth-gated brain side (embryo doctrine [[feedback_embryo_doctrine_build_all_organs_before_birth]]).

## Spec Self-Review

**Placeholder scan:** none — the contract, guards, and witnesses are concrete; the brain-side is explicitly deferred, not vaguely gestured.
**Internal consistency:** v1 = eye + contract + content-light receipt + drop; retention/identity/behavior all deferred to a named birth-gated slice; no field of the contract is consumed in v1. The "no durable store in v1" and "retention through existing machinery" are consistent because that machinery is itself birth-gated.
**Scope:** single subsystem (the fact-ingestion pipe). Brain-side meaning is correctly its own future spec.
**Ambiguity:** the per-frame-vs-per-face packet shape is made explicit (per-frame with a faces list) with rationale; the owner may revert to flat-per-face on review.
