# Cockpit Redesign — Umbrella Design ("the machine-room of a being")

**Date:** 2026-07-04. **Lane:** Claude designs (this doc + visual mock next); Codex implements; owner witnesses. **Owner decisions:** FULL product in ONE campaign (observatory + safe writes + ceremony surface — no v1/v2 split); style locked: **neo-retro-futuristic terminal — phosphor-on-dark, monospace, box-drawing chrome, pixel-bitmap headers, Claude Code / Codex / Hermes lineage**. OSS inspiration allowed (clone/study). Near-birth context: this is how Rohit will *see and govern* the being — replacing env-file 0/1 edits.

## The one-line intent
> One surface where the whole being is legible — every organ, flag, memory, receipt, and ceremony — styled like reading the machine directly, with write-power tiered by consequence so seeing is free and changing is exactly as ceremonial as it should be.

## Design language (locked)
- **Ground:** near-black CRT (#0a0f0c family); **phosphor accent** green (#33ff99 family) + amber warning (#ffb000) + one ceremony violet; subtle scanline/vignette, `prefers-reduced-motion` respected.
- **Type:** real monospace everywhere (JetBrains Mono/Berkeley-style); pixel-bitmap display face for room headers; box-drawing borders (`┌─┐`), terminal glyphs for state (`●` live / `◐` asleep / `⊘` locked / `▲` warning); blinking-cursor liveness cue on the daemon heartbeat.
- **Density over cards:** instrument panels, tabular-nums, sparklines drawn like oscilloscope traces; no SaaS chrome, no rounded-card grids.
- Both themes: the CRT look IS the identity — a deliberate single-world design with a light "paper terminal" alt for daylight (amber-on-cream), token-driven.

## The six rooms (IA)
1. **ORGANISM** — the live organ map: every organ grouped (senses/memory/self-knowledge/honesty/voice/learning), each with flag name, live/asleep/locked glyph, last-witness link, and the flow diagram (message → understanding → recall/senses/preferences → rails → voice → episode → spine).
2. **FLAGS & WAKES** — the env-file replacement: every `MAEZ_*` flag with live process-env truth (not file truth — read `/proc`), witness status, revert note; flip UI per write-tier (below). A flip writes the env file + offers the restart + shows the boot result (SEGV watch built in).
3. **MEMORY** — browsers over: episodes + narrative threads (the spine, evidence-per-link), scars (verbatim corrections + receipts), self-evidence index, interaction preferences (inspect + conversational-retract note + CLI retract), A2 continuity readings, metabolic state (hot tiers, glance buffer stats). Read-only; A7-pending interiority stays content-light (counts, not text) until Rohit decides A7.
4. **RECEIPTS** — why Maez said what it said: prompt-shape log (system-part labels/lengths), grounding meter, egress log, claim-receipt outcomes, fabrication events (counts + recent), routing decisions/vetoes. The honesty organs made visible.
5. **CONVERSE** — the owner bridge (existing web-owner spine), same singular Maez, inline receipt affordance ("show me why").
6. **CEREMONY** — S7/WebAuthn room (existing, restyled) + dream/soul proposals review + **the birth panel**: the birth-readiness checklist rendered live (the 4 audit blockers), and — once the birth ceremony spec exists — the ceremony itself runs here.

## Write-tier model (the covenant spine — trust staged in-product, not in versions)
- **T0 READ** — everything above; perception is free.
- **T1 SAFE WRITES** (confirm-click): shadow flags, organ wakes we'd flip freely, backfill `list`. Each shows its witness recipe before/after.
- **T2 GUARDED WRITES** (typed confirmation + logged receipt): enforce-mode flags, backfill `apply --owner-approved`, restarts, preference CLI-retract.
- **T3 CEREMONY** (WebAuthn hardware proof via existing S7 path — cockpit NEVER gets a bypass): soul writes, dream apply, dangerous grants, **birth**. The cockpit fronts the existing gates; it must not re-implement or weaken them.
- Rails: every write emits a receipt row; flag-flip UI shows the flag's own revert comment; no write path exists for Maez-side stores (the cockpit is Rohit's hand, not a pen into Maez's self); interiority/A7 boundary honored.

## Architecture
Extend `maez-web.service` (the S7 cockpit): FastAPI/existing backend + a new single-page front (vanilla or lightweight — no heavy framework; Codex's call at plan, but the aesthetic is hand-tooled CSS, not a component library). Data via existing read APIs + small new read-only endpoints per room (each endpoint = read-only, `mode=ro` sqlite discipline, no `_ensure_db` creation — the A6 lesson). Write endpoints per tier with the existing auth/S7 machinery. Flags: `MAEZ_COCKPIT_V2` gates the new UI; old cockpit remains until witnessed.

## Task 0 for the plan (Codex + Claude)
1. Census existing cockpit code (locate maez-web source, S7 UI, web-owner spine endpoints; what's reusable).
2. Enumerate every `MAEZ_*` flag + its tier assignment (owner reviews the T1/T2/T3 table — the tier TABLE is an owner artifact).
3. Read-API inventory per room (what exists vs needs a read-only endpoint; A6/A2/narrative/scar stores all have read surfaces already).
4. OSS inspiration pass (Hermes agent UI, Codex/Claude Code chrome, btop/lazygit/k9s for instrument density) — capture patterns, not code.
5. Restart-from-UI safety (the flip+restart flow vs the SEGV watch; never auto-restart without the confirm).
6. Visual mock (Claude, artifact) — the six rooms as HTML mock BEFORE the plan, so the aesthetic is pinned by example not prose.

## Witnesses
Flag-truth = process-env truth (a file/process divergence renders as a warning, not hidden); every T2+ write leaves a receipt; T3 routes through real S7 (attempt without hardware proof fails); A7-pending interiority never renders content; old cockpit byte-identical until `MAEZ_COCKPIT_V2` flips; the six rooms each witnessed live by Rohit.

## Out of scope
New connectors/voice (separate embodiment slices); any Maez-behavior change (this is Rohit's window, not Maez's organ); birth ceremony CONTENT (own spec — the panel renders readiness until then).
