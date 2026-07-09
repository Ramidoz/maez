# Vision Organ Redesign — accessibility nerve, OCR retina, on-demand cortex

Date: 2026-07-09
Status: THREE-LANE AGREED (Claude plan → Grok web research → Codex gpt-5.6-Sol
ULTRA arbitration, owner-run; Claude verified Sol's factual claims in source).
Owner decisions settled: LFM2.5-VL retired; 27B brain + MTP untouchable.

## The law (Sol's, adopted)

**Do not replace one overconfident eye with a slightly larger overconfident
eye. Deterministic sources speak first (accessibility), OCR reads pixels
second, a general VLM interprets only when genuinely required.** The sensor
reports evidence; Maez interprets it. ADR 0029 already requires this
("unreviewed free-text sensor descriptions are disallowed") — the current
eye violates it.

## Verified defects being fixed

- LFM2.5-VL-1.6B confabulates (contradictory inventions across resolutions
  on the same frame — witnessed 2026-07-08/09).
- VISION_PROMPT tells the SENSOR "You are Maez" and requests
  filenames/commands from a 640px downscale (screen_perception.py:125) —
  narrative authority + demanded specificity a tiny model can't ground.
- Photo path: fixed generic prompt DROPS the owner's caption/question
  (telegram_adapter.py:46), no sampling temperature (vision_tools.py:101),
  and shares the screen path's model config (vision_tools.py:16) — separate
  epistemic jobs, one config.
- Active-window preflight has title/class only (ambient.py:301) — no crop
  geometry seam yet.

## Key rulings

1. Resident screen organ = AT-SPI accessibility facts + CPU OCR specialist
   (models are tens of MB; the GPU gap stays free). NOT a resident 2B
   general VLM (Grok's call — overruled: less trustworthy than deterministic
   text for screens, weaker than 4B for photos, permanent VRAM for bursty use).
2. Photo organ = local Qwen3-VL-4B ON-DEMAND (systemd unit + one
   vision-broker owning start/readiness/serialize/TTL-stop; llama-swap only
   if the bake-off ever earns TWO production VLMs). Owner caption/question
   passes through; adaptive pixel budget; temp explicit.
3. Bake-off gate (replaces naive "resolutions must agree"): frozen
   owner-approved frames + human truth labels; EVIDENCE MONOTONICITY (low
   res may abstain, higher res may add detail, never contradict); any
   filename/command must be legible in that exact input or corroborated by
   AT-SPI/OCR; zero invented high-specificity strings; abstention coverage
   and correct-text coverage reported separately; peak VRAM witnessed
   after-load AND after-image (model_refresh.py already has the fields —
   4B "fits on demand" is unproven until witnessed under the live brain).
4. Change gate (sophistication P3): hash active-crop + a11y projection;
   unchanged scene ⇒ content-light heartbeat, no inference every 60s.
5. AT-SPI/OCR text is UNTRUSTED INPUT (may contain prompt injection; may
   expose scrolled-away/obscured text): quoted sensor evidence, never
   instruction; obeys the same active-window/pause/exclusion/third-party/
   retention gates as pixels.
6. Self-consistency is not truth — two models can agree on the same
   hallucination; ground truth = human labels + deterministic sources.
7. LFM: disconnected from cognition immediately; kept ONLY as bake-off
   baseline; deleted after the bake-off receipt.

## Slice order (Sol's, adopted; sizes S/M)

1. S — LFM containment (out of production cognition; baseline only)
2. S — Truth contract: screen transcribe/abstain schema, temp 0,
   field-level provenance, hard reject of unsupported specificity
   (lands as the EVALUATION CONTRACT, not an LFM cure)
3. M — Frozen-frame harness (one capture/many transforms, human labels,
   contradiction checks, peak-VRAM receipts)
4. M — Active-window sensor (identity + GEOMETRY, Decision-9 exclusions)
5. M — AT-SPI lane (bounded active-window facts; off-screen text excluded)
6. M — OCR lane (native active crop → text/boxes/confidence/[UNREADABLE])
7. S — Change gate (digest-unchanged ⇒ content-light presence)
8. M — Three-model bake-off (LFM/2B/4B, residual tasks only,
   zero-invented-specificity hard gate)
9. M — Screen admission (AT-SPI+OCR resident; 2B admitted ONLY if it adds
   truthful coverage those sources lack)
10. M — Photo admission (4B on demand, owner caption passed, adaptive
    pixel budget)
11. S/M — Lifecycle manager (systemd broker; llama-swap only if earned)
12. M — Shadow witness (sensor claims vs owner-reviewed frames before any
    observation influences memory/factual reasoning)

Cross-refs: substrate sophistication P1-P7 @8e865a1; perception containment
@6f447ed; field-level scope @8691b6d; ADR 0029; Decision 9 exclusions.
