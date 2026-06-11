# Gestation-Memory Renderer v0.1 — Design (honesty/clarity polish, display-only)

**Date:** 2026-06-10
**Status:** spec for owner spot-check
**Lane:** Claude builds (lane-swap — small, display-only, low covenant risk); owner spot-checks the diff (right-sized cross-lane for a pure-formatting change).
**Branch:** `gestation-render-v0.1` (from `c1a6e9b`)
**Parents:** Gestation-Memory v0 (the claim index + renderer). This changes **only** `GestationMemory.render()` and adds one read helper — **no** storage, source-validation, or rail changes.

## Why
Two display gaps surfaced in the v0 witness:
1. **Double-render:** a `milestone`/`decision` *fact* appears in both "What happened" *and* "What changed" — the same claim twice.
2. **Invisible corrections:** superseded claims (the preserved "we once believed X") are correctly excluded from `list_active`, so they never appear in the render — the honest "ink, not pencil" history is stored but unseen.

## Changes (pure renderer/display)
1. **Mutually-exclusive sections (a precedence partition):** every *active* claim is assigned to **exactly one** section by `_section_for(claim)`, in this order:
   - `interpretation` → **Interpretations**
   - else `scar` (bool) or `type ∈ {scar, correction, no_go}` → **What went wrong / what was corrected**
   - else `type ∈ {milestone, decision}` → **What changed**
   - else → **What happened**
   **Empty sections are omitted.** (Honest consequence of the type taxonomy: a non-wrong fact is always a `milestone`/`decision`, so "What happened" is the catch-all that — with the current types — renders nothing and is omitted. That's *why* v0 double-rendered: "What happened" and "What changed" were the same set. The partition + omit-empty fixes it without inventing content.)
2. **Show `type` on each line** — `[type/confidence]` so the binder reads honestly at a glance (e.g. `[milestone/documented]`).
3. **Corrections-history tail** — a final section listing each superseded claim and what replaced it ("once: <old> → now: <replacement>"), read from `gestation_claim_supersessions`. Superseded claims stay out of the main sections (still derived via `list_active`) but become *visible* here, so the preserved old belief is shown, not hidden. Omitted if there are no supersessions.

## What v0.1 does NOT touch
Storage (still append-only, trigger-enforced); source validation / fingerprints; the fact/interpretation quarantine; `record_claim`; the CLI's `record`. Only `render()` + a read-only `corrections_history()` helper.

## New helper
`corrections_history() -> list[tuple[GestationClaim, GestationClaim]]` — reads `gestation_claim_supersessions` (oldest first) and returns `(old_claim, replacement_claim)` pairs via `get()`. Read-only.

## Testing
- partition: each active claim appears in exactly one section; a `milestone` fact appears in **What changed** and **not** in **What happened** (no double-render).
- type shown: a rendered line carries `[milestone/documented]`.
- corrections-history: after a supersede, the old claim is absent from the main sections but present in the "Corrections history" tail with its replacement; the active replacement appears in its section.
- deterministic / no LLM unchanged (the existing boundary test still passes).
