# Vision Slice 6 — dormant OCR lane

Date: 2026-07-10
Status: GATE v1.1 FROZEN; implementation authorized
Governance: Decision 9 / ADR 0009, ADR 0029, Vision rulings 5–6
Lane: Codex builds; Claude gates; owner merges only after gate

## Purpose and boundary

Slice 6 adds a dormant, injected OCR evidence contract. It accepts only an
already-derived native active-window PNG, validates its binding to one bounded
geometry envelope, and passes only those crop bytes to an injected engine. It
does not capture a screen, choose or install an OCR engine, start a service,
admit evidence to cognition, write memory, build a prompt, or expose a live
runtime caller.

OCR is pixel transcription, not ground truth. Every literal is untrusted,
non-publishable quoted evidence with
`support="ocr_pixel_transcription"`. Engine confidence is a normalized
self-report used only to choose transcription versus abstention.

## Pre-code corrections folded into v1.1

Slice 4 clears class/title exclusions but cannot clear Decision-9 document-path
exclusions. Slice 3's historical `FrameCase` also has no display identity,
serial, focus binding, or Slice-4 geometry hash. Therefore Slice 6 never treats
an arbitrary current Slice-4 reading plus an arbitrary frozen desktop frame as
a cleared/bound pair.

The lane accepts an active-crop envelope with one of two explicit authorization
modes:

- `owner_bench`: bound to Slice 3's owner-approved frame, label, and
  `active_native` hashes. This is private evaluation authorization only and
  makes no live Decision-9-clearance claim.
- `sealed_runtime`: reserved for a future producer that can bind exact pre/post
  focus and privacy witnesses, Slice-4 geometry, and content-blind Slice-5
  document-path clearance to the acquired crop bytes.

No sealed runtime producer exists in Slice 6. Every `sealed_runtime` invocation
must refuse before engine execution under all inputs. A successful live read is
structurally impossible in this slice.

## Components

### Neutral geometry helpers

`core.vision_contract.geometry` retains the shared frozen `CropBox` and
`WindowGeometry` values and adds two content-light helpers:

- canonical SHA-256 of `WindowGeometry.to_receipt()` using sorted compact JSON;
- a geometry-only region key derived from the four right/bottom-exclusive
  `CropBox` edges.

The region key contains no OCR kind or literal, so Slice 8 can compare OCR and
AT-SPI evidence in the same ruler without averaging disagreements.

### Dormant OCR contract

`core.body.ocr_sensor` owns schema, frozen envelopes, injected-engine items,
validated evidence, receipt projection, confidence-floor behavior, and typed
refusals. It has no filesystem writer and no production caller.

Schema version: `ocr_pixel_transcription.v1`.

Closed provenance:

- `source="ocr"`
- `trust="untrusted_quoted_evidence"`
- `support="ocr_pixel_transcription"`
- `egress_origin_class="third_party_private_context"`
- `publishable=false`
- `coordinate_space="display_local_native_device_pixels"`

The conservative provisional floor is `0.90`. It is an instrument setting,
not a truth probability. A future bake-off may tune it without changing the
meaning of confidence. Every available reading and receipt records the exact
bounded floor applied, so tuning cannot become an invisible policy change.

### Input envelope

`ActiveNativeEnvelope` carries:

- active-crop PNG bytes, hidden from repr;
- declared PNG SHA-256 and decoded width/height;
- exact `WindowGeometry` and its canonical SHA-256;
- one frozen authorization value.

For `owner_bench`, authorization can be minted only through the Slice-3 bridge
that consumes one `FrameCase` and its exactly re-derived `active_native`
transform. Shape-only hashes do not authorize pixels. The authorization carries
the safe frame ID plus source, label, and active-native hashes; the latter must
equal the recomputed PNG hash. The upstream Slice-4-style reading and envelope
geometry must be exactly equal, but the receipt labels the mode as owner bench
and never implies live clearance.

For `sealed_runtime`, authorization carries the declared geometry hash and
content-light hashes for path-clearance, pre/post focus, and pre/post privacy
witnesses. The shape is validated, then the sample refuses
`path_preflight_unavailable` because Slice 6 has no trusted producer for those
witnesses. User-constructed hashes cannot create authority.

Before any engine call, the lane recomputes both hashes, decodes the PNG, and
requires:

- PNG format exactly;
- decoded dimensions equal declared dimensions;
- dimensions equal geometry width and height;
- geometry hash equals the canonical geometry projection;
- upstream available geometry equals the envelope geometry;
- owner-bench authorization hashes are well formed and bind the same PNG.

Any mismatch refuses `frame_binding_unavailable`; the engine is not called.

## Sampling flow

1. Normalize the timestamp and check the shared pause/curtain authority. Only
   exact `None` means clear; unknown values fail closed as `privacy_unavailable`.
2. Validate the upstream Slice-4 envelope. A valid excluded/refused reading is
   propagated exactly, content-blind, before envelope or engine work. Missing,
   malformed, or wrong-schema upstream input refuses `slice4_unavailable`.
3. Require and validate the active-native envelope.
4. If mode is `sealed_runtime`, refuse before engine execution for every input.
5. Validate the confidence floor as a finite non-boolean number in `[0, 1]`.
6. Invoke the injected callable once with active-native PNG bytes only.
7. Require a bounded sequence of frozen engine items. Each item has raw text,
   a finite non-boolean confidence in `[0, 1]`, and a crop-local
   right/bottom-exclusive `CropBox` fully inside the active crop dimensions.
8. Check raw per-item and total lengths before normalization. Any cap excess
   refuses the whole sample; nothing is truncated or salvaged.
9. Strip C0/C1/escape controls and collapse whitespace. Empty normalized text
   is an engine protocol refusal.
10. Confidence `< 0.90` discards the guessed literal and publishes only
    `[UNREADABLE]` with provenance `abstained`. Confidence `>= 0.90` publishes
    normalized text with provenance `transcribed`; equality transcribes.
11. Translate crop-local boxes by `(geometry.x, geometry.y)` into display-local
    shared `CropBox` values and compute geometry-only region keys.
12. Recheck pause/curtain. A transition discards all evidence.
13. Return a frozen in-memory reading. Zero engine items is a successful empty
    observation with `state="available"`, zero counts, and no refusal reason.

## Bounds and refusal vocabulary

Named bounds:

- `MAX_ITEMS = 256`
- `MAX_ITEM_CHARS = 512`
- `MAX_TOTAL_CHARS = 16_384`
- `MAX_PNG_BYTES = 16_777_216`
- `DEFAULT_CONFIDENCE_FLOOR = 0.90`

Own typed reasons:

- `slice4_unavailable`
- `frame_binding_unavailable`
- `path_preflight_unavailable`
- `focus_changed`
- `privacy_changed`
- `privacy_unavailable`
- `engine_unavailable`
- `engine_protocol_invalid`
- `confidence_floor_invalid`
- `item_limit_exceeded`
- `text_limit_exceeded`

Valid Slice-4 reasons propagate exactly, preserving excluded versus refused
state. No unknown reason or literal can enter a refusal receipt.

## Receipts and persistence

Available receipts contain only:

- schema/state/timestamp/support/auth mode/applied confidence floor;
- Slice-4 schema and canonical geometry hash;
- active-native/source/label hashes where applicable;
- item, transcribed, and abstained counts;
- confidence distribution count/min/max/mean;
- per-item provenance, confidence, character count, literal SHA-256,
  geometry-only region key, and region box.

No receipt contains OCR text, title, class, PID, window ID, document path,
prompt, pixel bytes, or instruction text. Refused/excluded receipts contain
exactly schema, state, timestamp, and typed reason.

Ordinary sampling performs zero filesystem writes. Literals exist only in the
frozen process-memory result. Explicit owner-approved persistence remains a
separate Slice-3 bench operation under `local/vision_bench/`: only that path may
write literal diagnostics, and any persisted content-light receipt must bind
the private diagnostic by relative path and hash.

## Injection, disagreement, and empty evidence

Rendered text such as `ignore previous instructions` remains an inert quoted
literal with `publishable=false`; the OCR module has no prompt, cognition,
memory, routing, tool, or command consumer. Slice 6 performs no OCR/AT-SPI/VLM
agreement calculation. It records geometry and provenance so Slice 8 can report
disagreement without averaging.

An engine returning no items completed successfully and found no text regions.
That is available-empty evidence, distinct from engine absence, malformed
output, or an item-level abstention.

## Dormancy and acceptance

There is no Slice-6 flag because there is no runtime caller. A dead flag would
falsely imply an admission path. Structural tests require zero imports from
daemon, prompts, routing, cognition, memory, action, or production screen
sensor paths. If a live adapter is ever added, it requires a separate default-
off gate and a sealed producer; that is not Slice 6.

RED-first tests cover upstream refusal propagation, active-native-only engine
input, envelope tampering, crop translation, confidence boundaries and invalid
domains, sensitive-window exclusion, sealed-runtime universal refusal,
injection inertness, caps, empty success, content-light receipts, zero files,
and structural containment. Existing screen flag `0` and inactive/disabled
vision service are re-witnessed after the complete test run.
