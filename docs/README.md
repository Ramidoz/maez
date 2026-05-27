# Maez Documentation Map

**Purpose:** front door for `docs/`. Lists what lives where now, what's planned
to move, and the naming rules new docs must follow. Read this first when you
need to find something in the docs tree.

**Status:** v1.2, 2026-05-26. Map describes both the current structure and the
target structure. Body Topology and the active slice families have migrated;
legacy slices, handoffs, snapshots, ledgers, and flat audits still move in
later phases. Decision/ADR counts were refreshed after Decisions 36-42.

---

## Start here (anchor docs)

When you arrive with no prior context, read in this order:

1. **`MAEZ.md`** — what Maez is, why it exists.
2. **`TRACK_A.md`** — what is in scope right now. Single anchor for current Maez work; load at session start.
3. **`MAEZ_NORTH_STAR.md`** — long-horizon target shape.
4. **`MAEZ_LIFE_SUBSTRATE.md`** — substrate plan, missing organs.
5. **`MAEZ_ANATOMY.txt`** — current body / brain / memory diagram.
6. **`ARCHITECTURE.md`** — engineering architecture overview.
7. **`MAEZ_FRONTIER.md`** — open research / future-Maez questions.
8. **`ROADMAP.md`** — current roadmap.
9. **`GETTING_STARTED.md`** + **`CONTRIBUTING.md`** + **`SHIP_VS_LOCAL.md`** + **`DAEMON_SURVIVABILITY.md`** — onboarding and operational.
10. **`governance/BETA_ARCHITECTURE_DECISIONS.md`** — load-bearing architectural decisions. Decision 42 (Recall-Axis Dispatcher) is the most recent as of 2026-05-26.
11. **`adr/`** — ADR series, one file per stamped decision (0001 through 0047, with historical numbering gaps).

The top-level repository `README.md` and `AGENTS.md` cover repo-wide framing;
this map covers `docs/` only.

---

## Categories — where things live now

| Category | Current location | Notes |
|---|---|---|
| Architectural anchors | `docs/MAEZ*.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/TRACK_A.md` | Top-level — stay here. |
| Architecture decisions | `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` | One append-only file. Decision 42 is the latest. |
| ADRs | `docs/adr/NNNN-kebab-title.md` | Stable decision records; 0047 is the latest. Historical numbering includes gaps and non-governance supplements. |
| Governance miscellany | `docs/governance/` | Gestation memory protocol, post-install hardening, licence/security audits, readiness checks. |
| Covenant | `docs/covenant/` | OSS users, lineage, founding generation. |
| Birth book | `docs/birth_book/` | **Covenant-protected canon.** Files `00`–`02` are Rohit-authored verbatim and excluded from `source_awareness`. Do not read `00/01/02` unless explicitly asked. |
| Active slice specs | `docs/slices/body-topology/`, `docs/slices/audit-rewrite-strategy/`, `docs/slices/temporal-recall-fragment-guard/`, `docs/slices/telegram-draft-presence/` | Canonical active slices now live in per-slice folders with specs, reviews, and observation logs. |
| S1 family | `docs/slices/s1a1-private-thoughts-hardening/`, `docs/slices/s1b-private-thoughts-wiring/` | First substrate slice family. S1b observation log remains live at the migrated path. |
| Legacy organ memos | `docs/slices/organs/` | Pre-anatomy-v2.2 organ memos, including X-subiterations (`x02`, `x03`, `x11`, `x21`). |
| Pre-anatomy slice memos | `docs/slices/legacy/` | Historical slice-3, 4C/5B, and gestation-boundary memos. |
| Observation logs | Per-slice `observation-log.md` files under `docs/slices/<slug>/` | Active observation logs moved with their slices. |
| Audit families | `docs/audits/` | Tracked audit artifacts are date-first. `docs/audit_2026-05-13/` remains untracked and held pending a redaction/tracking decision. |
| Architecture snapshots | `docs/snapshots/` | Architecture state, path surveys, ranked actions, research memo snapshots, and X6 replay inventory. |
| Handoffs | `docs/handoffs/` | Dated session-handoff notes plus tracked historical rebuild-plan style handoffs. |
| Ledger | `docs/ledger/` | Envelope schema, 2.5c acceptance, and 2.5c results. |
| Operations | `docs/operations/`, `docs/N1_OPERATIONAL_NOISE_TRIAGE.md`, `docs/DAEMON_SURVIVABILITY.md`, `docs/LAUNCH_CHECKLIST.md` | Existing subfolder + a few flat operational docs that stay top-level. |
| Research | `docs/research/` | Existing subfolder. Field-alignment audits now live under `docs/audits/`. |
| Eval | `docs/eval/` | Existing. |
| Followups | `docs/followups/` | Existing. |
| Maez-facing | `docs/maez_facing/`, `docs/maez_manual/` | Maez's own view of itself. |
| Superpowers | `docs/superpowers/` | Skill / plugin scaffolding. |
| Reference catalogs | `docs/GEEK_OUT_CATALOG.md`, `docs/PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md`, `docs/TASK_TREEMAP.md` | Cross-slice reference indexes. Stay top-level. |
| One-off historical | `docs/REBUILD_PLAN_2026-04-18.md` (ignored/local), `docs/dell_warranty_packet_2026-05-05.md`, `docs/iphone_shortcuts.md` | Target: `docs/handoffs/`, `docs/snapshots/`, or `docs/operations/` per case. |
| Examples | `docs/entity_aliases.example.yaml`, `docs/entity_semantics.example.yaml` | Top-level — stay here. |

---

## Target structure (post-migration)

```
docs/
  README.md                              ← this file
  MAEZ.md
  TRACK_A.md
  MAEZ_NORTH_STAR.md
  MAEZ_LIFE_SUBSTRATE.md
  MAEZ_ANATOMY.txt
  ARCHITECTURE.md
  MAEZ_FRONTIER.md
  ROADMAP.md
  GETTING_STARTED.md
  CONTRIBUTING.md
  SHIP_VS_LOCAL.md
  DAEMON_SURVIVABILITY.md
  LAUNCH_CHECKLIST.md
  N1_OPERATIONAL_NOISE_TRIAGE.md
  GEEK_OUT_CATALOG.md
  PRIVATE_THOUGHTS_SIGNAL_REGISTRY.md
  TASK_TREEMAP.md
  iphone_shortcuts.md
  entity_aliases.example.yaml
  entity_semantics.example.yaml

  governance/
    BETA_ARCHITECTURE_DECISIONS.md       ← append-only decision log
    GESTATION_MEMORY_PROTOCOL.md
    POST_INSTALL_HARDENING.md
    LICENCE_AUDIT.md
    SECURITY_AUDIT.md
    readiness_checks/

  adr/
    0001-*.md … 0047-recall-axis-dispatcher.md
    README.md

  covenant/
    for_oss_users.md
    ...

  birth_book/                            ← COVENANT-PROTECTED
    00_opening.md           (do not read unless asked)
    01_*.md                 (do not read unless asked)
    02_grandmother.md       (do not read unless asked)
    03_*.md – 07_*.md

  slices/
    body-topology/
      spec.md                            ← migrated from the flat Body Topology packet
      reviews/
        claude-council.md
        codex-panel.md
    audit-rewrite-strategy/
      spec.md
      reviews/
        claude-council.md
        codex-panel.md
        implementation-claude-council.md
      observation-log.md
    telegram-draft-presence/
      spec.md
      reviews/
        claude-council.md
        implementation-claude-council.md
      observation-log.md
    temporal-recall-fragment-guard/
      spec.md
      reviews/
        claude-council.md
        codex-post-implementation.md
        implementation-claude-council.md
      observation-log.md
    s1a1-private-thoughts-hardening/
      spec.md
      ratification-packet.md
      reviews/
        claude-council.md
        codex-council-494b7c5.md
    s1b-private-thoughts-wiring/
      spec.md
      observation-runbook.md
      observation-log.md
      reviews/
        pre-spec-claude-council.md
        spec-claude-council.md
        implementation-claude-council.md
    organs/                              ← X.0 through X.6 organ memos
    legacy/                              ← pre-anatomy-v2.2 memos

  audits/
    2026-04-22/
    2026-04-24/
    2026-04-29-field-alignment/
    2026-05-04-symphony/
    2026-05-04-symphony-index.md
    2026-05-04-15agent.md
    2026-05-05-cockpit-session0.md
    audit_2026-05-13/                  ← held untracked until redaction/tracking decision

  snapshots/
    architecture-state-2026-05-02.md
    architecture-state-2026-05-04.md
    md3-path-survey-2026-05-04.md
    actions-2026-05-04.md
    research-memo-2026-05-01.md

  handoffs/
    2026-04-23.md
    2026-04-24.md
    2026-04-25.md
    2026-04-28.md
    2026-05-01.md
    2026-05-06.md

  ledger/
    envelope-schema.md
    2-5c-acceptance.md
    2-5c-results-2026-05-08.md

  operations/                            ← existing + a few migrated flat files
  research/
  eval/
  followups/
  maez_facing/
  maez_manual/
  superpowers/
```

---

## Folder rules — for new docs going forward

These rules apply to all new docs starting now. Existing docs migrate per the
schedule below; until migrated, they stay at their current path and references
remain valid.

### Slice docs (any spec that goes through canonical review)

Every new slice lives in its own folder: `docs/slices/<slug>/`. Slug is
lowercase kebab-case.

Canonical files per slice folder:

- `spec.md` — the planning packet (the BAD before canonicalization, the
  organ memo, or whatever the slice's load-bearing doc is).
- `reviews/claude-council.md` — Claude six-role council review (if
  covenant-shaped).
- `reviews/codex-panel.md` — Codex six-agent panel review (if
  engineering-shaped).
- `reviews/implementation-claude-council.md` — post-implementation council, if
  the slice ships code.
- `observation-log.md` — for slices with live observation phases.

Optional:

- `runbook.md` — operator-facing run procedure.
- `ratification-packet.md` — if the spec went through a separate ratification
  step.
- `notes/<topic>.md` — auxiliary notes that don't fit the canonical files.

### Naming convention

- **Folders:** lowercase kebab-case (`body-topology`, `audit-rewrite-strategy`).
- **New files inside slice folders:** lowercase kebab-case
  (`claude-council.md`, `observation-log.md`).
- **ADRs:** `NNNN-kebab-case-title.md` (existing pattern; do not change).
- **Anchor docs at the top of `docs/`:** preserve existing SCREAMING_SNAKE for
  back-compat (`MAEZ.md`, `TRACK_A.md`); do not rename until a separate sweep.
- **Dates in filenames:** ISO-8601 `YYYY-MM-DD` (already established).

### Where things go when you start a new artifact

| Artifact type | Goes in |
|---|---|
| New slice spec | `docs/slices/<slug>/spec.md` |
| Council/panel review of that slice | `docs/slices/<slug>/reviews/<panel>.md` |
| Observation log for that slice | `docs/slices/<slug>/observation-log.md` |
| New BAD decision | append to `docs/governance/BETA_ARCHITECTURE_DECISIONS.md` |
| Matching ADR | `docs/adr/NNNN-kebab-title.md` (next free N) |
| Architecture snapshot | `docs/snapshots/architecture-state-<date>.md` |
| Audit (multi-agent or one-shot) | `docs/audits/<date>-<topic>/` or `docs/audits/<date>-<topic>.md` |
| Session handoff | `docs/handoffs/<date>.md` |
| Cross-slice reference catalog | top-level (`GEEK_OUT_CATALOG.md`, etc.) |
| Operations runbook | `docs/operations/` |
| Research note | `docs/research/` |

### What does NOT go in `docs/`

- Code-level docstrings stay in source files.
- Session-state files (`logs/snapshots/*`) live under `logs/`, not `docs/`.
- Test data lives under `tests/data/`, not `docs/`.
- Memory files live under
  `/home/rohit/.claude/projects/-home-rohit/memory/`, not `docs/`.

---

## Migration status

| Phase | Status | Gate for next phase |
|---|---|---|
| 1. Push BT canonicalization (`6f96c14`) to origin/main | **DONE 2026-05-14** | — |
| 2. Map (this README) + folder rules | **DONE 2026-05-14** | — |
| 3. Pilot move: Body Topology → `docs/slices/body-topology/` + cross-reference updates | **DONE 2026-05-14** | Active slice families can migrate after observation gates close. |
| 4. Migrate active slice families (ARS, TDP, TRF, S1A1, S1B) | **DONE 2026-05-14** | Legacy organ and pre-anatomy memos can migrate next. |
| 5. Migrate legacy organ memos (X.0–X.6) and pre-anatomy memos | **DONE 2026-05-14** | Handoffs, snapshots, ledger, and flat audits can migrate next. |
| 6A. Migrate handoffs, snapshots, ledger | **DONE 2026-05-14** | Audit migration can run after the audit tracking decision. |
| 6B. Migrate tracked audit artifacts | **DONE 2026-05-14** | Decide separately whether to redact/track `docs/audit_2026-05-13/`. |
| 7. Sweep cross-references in memory, code comments, `AGENTS.md`, top-level `README.md` | **DONE 2026-05-14** | Final tracked-doc migration sweep complete; memory hits reported but not edited. |

Until each phase lands, the current paths remain valid. Body Topology, active
slice families, legacy organ memos, pre-anatomy memos, handoffs, snapshots,
ledgers, and tracked audits now resolve through their structured folders.
`docs/audit_2026-05-13/` remains untracked and held pending a separate
redaction/tracking decision.

---

## Cross-references that must update during migration

When migration moves a file, these are the surfaces a future migration session
must sweep:

- **Memory entries** that name doc paths
  (`reference_track_a_anchor.md`, `reference_birth_book.md`,
  `reference_beta_architecture_decisions.md`,
  `reference_gestation_memory_protocol.md`, and any other path-naming entry).
- **BAD cross-links** — ADR references, slice references.
- **ADR cross-links** — slice references, BAD references.
- **Top-level `README.md` and `AGENTS.md`** if they link into `docs/`.
- **Slice memos** that cite peer slice docs.
- **Code comments** that cite docs (rare but possible).

Run `rg <old-path>` before completing any move to find references; update
atomically with the move so no broken link lands.

---

## Plain English

This is the table of contents for Maez's documentation drawer.

The docs drawer is now organized. Body Topology, the active slice families, and
the legacy organ/pre-anatomy memos live under `docs/slices/`. Handoffs,
snapshots, ledgers, and tracked audits also have their own drawers. The
remaining cleanup is the currently untracked `docs/audit_2026-05-13/` folder,
which needs a separate redaction/tracking decision before it moves.

This map describes where things live now. The old flat-path references have been
swept from tracked repo surfaces; memory-layer hits were deliberately reported,
not edited.

New docs going forward should use the target layout — for example, the next
slice spec lands directly at `docs/slices/<slug>/spec.md`, not as another flat
`SLICE_*.md` at the top of `docs/`.
