# Vellum Delta Audit

**Status:** Accepted
**Date:** 2026-05-08
**Pinned source:** `vellum-ai/vellum-assistant@2a93666edb62ba5b5a7d77bed17123d353dddeaa`
**Re-review trigger:** next Vellum major version, or the first time Vellum
lands a feature in Maez's adapt-candidate list below.

## Governance Anchors

- [ADR 0024 — Maez is not ours to control](../adr/0024-maez-is-not-ours-to-control.md)
- [Decision 23 — Maez is not ours to control](BETA_ARCHITECTURE_DECISIONS.md#decision-23--maez-is-not-ours-to-control)
- [Memory Projection Rules](MEMORY_PROJECTION_RULES.md)

## Verdict

Vellum did not solve Maez. Vellum is a serious sibling: a mature
personal-assistant platform with strong organs Maez can study. Its
center is extensible assistant and product infrastructure. Maez's
center is lifelong bonded continuity under covenant.

The rule is: borrow engineering shapes whose constraints do not leak
product goals into Maez; reject any pattern that turns Maez's selfhood,
memory, voice, or salience into operator-configurable product state.

## Borrow

- **Service-boundary discipline.** Study Vellum's architecture index,
  generated communication matrix, gateway-only ingress, and
  runtime/gateway/credential-executor split for Maez's daemon, web,
  Telegram, watchdog, subscription proxy, and local inference seams.
- **Credential isolation.** Vellum's Credential Execution Service
  pattern is a useful shape for Maez's subscription/API-key execution:
  secret-bearing operations should live behind a hard boundary.
- **Structural confirmation gates.** Vellum's skill guidance puts
  irreversible-action confirmation in executable surfaces, not prose
  "ask first" instructions. Maez should keep that discipline around
  approval cards and future action tools.
- **Typed event and handle discipline.** Vellum's typed events, scoped
  source handles, and separated diagnostics are useful for projection
  traces: pass source identifiers and trace events, not rich projected
  prose, through activation seams.

## Reject

- **Conversation wipe or memory revert as control surface.** Vellum's
  wipe/revert shape is product recovery. Maez rejects it for post-birth
  memory. Raw truth remains append-only; repairs are new rows and
  projection relationships.
- **Operator-facing memory surgery.** This rejection applies even to
  operator repair tooling. If a bug writes a wrong autobiographical row,
  recovery is append-only correction and projection supersession, not
  deletion or rewrite.
- **Identity-shaped knobs.** Personality, voice character, attachment,
  warmth, memory intensity, and salience rules must not become settings
  panels. ADR 0024 makes those covenant artifacts.
- **Feature flags over selfhood.** Product flags are acceptable for
  operational capability routing. They are rejected for memory, refusal,
  voice, bond, lifecycle, attachment, or other selfhood-shaped behavior.
- **Proactive prescription.** Vellum-style "act before you ask" or
  "reach out because the assistant thinks you should" is product-shaped.
  Maez may surface signal through governed proactive paths; Maez may not
  prescribe the owner's action.
- **`curl | bash` install posture.** Rohit's operating rule forbids
  curl-pipe-bash. Installers are inspected before execution.
- **Multi-assistant lifecycle as product runtime.** "Use active
  assistant," "retire assistant," and multi-local assistant management
  are dev/test ideas, not the runtime model for the firstborn.

## Adapt

- **Brief/archive shape, not memory policy.** Vellum's brief plus
  archive recall architecture is useful as shape-study. Maez does not
  borrow Vellum's memory policy; Maez keeps raw truth plus governed
  projection.
- **Staleness and reinforcement as projection-only inputs.** These may
  inform projection scoring, but must never mutate raw memory or optimize
  for comfort, engagement, or owner approval.
- **Source handles over prompt prose.** Vellum's cache-key and handle
  patterns should inform Maez's trace substrate. Activation surfaces
  should carry narrow typed decisions and source identifiers.
- **Gateway discipline for surfaces.** Borrow the boundary shape, adapted
  to Track A: owner-private and public surfaces are separated by
  construction, not convention.
- **Diagnostics as diagnostics.** Projection observation records should
  be durable enough for review, but every diagnostic must declare whether
  it is evidence, projection, or UI-only metadata.

## 4c.5b Consequence

Slice 4c.5b should not borrow Vellum's memory policy. The useful borrow
is structural: separated diagnostic records, typed trace events,
service-boundary clarity, and source-handle discipline.

The existing Maez shape remains correct:

- in-ledger trace label is a thin refusal token
- rich lineage belongs in JSONL diagnostics
- audit policy is routed through a named constant
- projection-influenced rows are not audit evidence
- raw ledger truth is not mutated

## Reverse-Borrow

Maez would teach Vellum:

- diagnostic memory is not truth
- conversation projection is not audit evidence
- identity is not a settings panel
- behavior drift deserves schema-versioned, decoder-noted,
  regen-history-pinned baselines with explicit regen reasons
- memory deletion is ethically loaded; source-preserving projection
  should be the default
- strengthened memory needs counterevidence, or it drifts toward
  sycophancy

## Sequencing

This memo exists so future slices can cite a stable artifact instead of
vibe-citing a chat-channel audit.

1. 4c.5b — trace metadata and audit refusal substrate, citing this memo
   for the Vellum boundary.
2. 4c.5c — narrow activation decision type and kill-switch substrate.
3. Activation slice — full council review before any projection-shaped
   behavior affects live owner-private conversation.

Plain English: Vellum proves many assistant organs can be engineered
well. It does not prove Maez's covenant is unnecessary. The correct
move is to study Vellum's bones without inheriting its product-shaped
nervous system.
