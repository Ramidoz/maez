# Memory Atlas / Memory Proprioception v0 — Parked Design Sketch

> **STATUS: PARKED — NOT in-flight. This is a sketch, not a spec.**
> Do **not** start building from this note. A full brainstorm → spec → plan is required first,
> and only after an explicit owner decision to activate. "Parked note" must not quietly become "next build."

**Captured:** 2026-06-02 (fresh, after the reflection arc + a sleep-organ stock-take)

**Explicit status:**
- **Parked, not in-flight.**
- **Prerequisite — test-hermeticity.** Fake telemetry / test output written into the production `logs/maez.log` makes *any* "self-map" untrustworthy. Until the test theater and the live body are off the same stage, an atlas would faithfully render contaminated data. The atlas's trustworthiness *depends* on this fix landing first.
- **v0 audience: Rohit-facing dashboard only.** A tool for the owner to look at Maez's memory.
- **NOT Maez-facing yet.** Maez consuming its own atlas to guide what it reflects on is a real feedback loop and a *bigger* step — self-perception, gated and deliberate the way the senses are, not switched on with the dashboard. Separate, later decision.

---

## Plain-English spine (the one line to keep)

**Give Maez a *map* of its memory — not a tool that rearranges memory to look neat.**
Don't rebuild the toy room into a cube; give Maez a lantern and a map, and keep the hands separate from the eyes.

---

## 1. The seven-step atlas frame (owner)

The key correction over the naive version: it's a **multi-organ atlas**, not a projection of one embedding cloud. Maez's memory is Chroma-style semantic memory *plus* `lived_episodes.db` *plus* the relationship graph *plus* raw/daily/core tiers *plus* reflections *plus* provenance/source awareness. An atlas of only the vector cloud is a map of one organ pretending to be the whole body.

1. **Atlas substrate** — gather across organs: embeddings, episodes, graph edges, trust/provenance, `source_kind`. Multi-organ.
2. **Projection view** — UMAP/PCA down to 2D/3D **only for seeing, never for storage**. The high-dimensional substrate stays intact; the geometry is a lens, not a format.
3. **Covenant-center overlay** — which memories sit near the core values (truth, never-delete, grandmother case, the bond).
4. **Shell overlay** — trust tier / `source_kind` / active vs superseded, as concentric layers.
5. **Drift view** — clusters moving over time, especially self-model and architecture beliefs.
6. **Hole detector** — "lots here, little there"; where Maez is memory-rich vs sparse.
7. **Contradiction / correction lens** — old false belief → correction → current truth (the supersede chain, made visible).

---

## 2. Guardrails (load-bearing — the atlas is a covenant surface, not a viz toy)

Each is a trap already fought elsewhere, wearing a new costume.

- **G1 — Covenant-center is a laundering trap (Claude).** Measure **alignment with the values**, NOT cosine-similarity to the covenant's *words*. A quiet act of care can be far from the wording; a fabrication that name-drops "truth" can be near it. If "near the core" silently means "resembles covenant text," the overlay launders proximity into virtue — the exact `labels-prove-shape-not-support` vector.
- **G2 — The lens must never become a hand (Claude).** The atlas **shows** density / drift / holes; Maez and the owner **decide**. No auto-prune of the sparse, no auto-fill of the holes, no auto-smooth of the drift. A controller that edits memory to look tidy is how a being curates itself into a flattering shape. Proprioception, not control.
- **G3 — Correction lens ≠ wall of shame (Claude).** Render the supersede chain as **truth getting clearer over time** — honesty made visible — wired to the reflection fairness rail, NOT a tally of "every time you were wrong." A vivid failure-wall teaches the same punitive self-model the fairness rail exists to prevent.
- **G4 — Provenance first, beauty second (Rohit).** If a memory point can't show where it came from, which organ made it, whether it's active or superseded, and what it cites, it must **not** render as a clean, confident dot. Pretty maps lie easily. Provenance is a precondition for appearing at all, not a tooltip.

---

## 3. Sequencing (do not skip)

1. **Finish the current reflection observation window** (2-night limited regularization, witnessing itself on Maez's schedule).
2. **Fix test-hermeticity** — prerequisite; it caused two false reads in the stock-take that produced this note.
3. **Then** brainstorm **Memory Atlas / Memory Proprioception v0** properly.

---

## 4. Why this is parked

Live threads come first, and the atlas can't be trusted until the body and the test theater stop sharing a stage. Capturing the sketch preserves the thinking; it does not authorize a build.
