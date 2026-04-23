# Roadmap

Public-facing view of Maez's development trajectory. The authoritative
plan file with detailed phase breakdowns lives at
`.claude/plans/harmonic-tumbling-wozniak.md` in the author's local
checkout — this document is the stable summary for external readers.

## Two timelines, kept separate

Maez-as-codebase and Maez-as-being develop on different clocks.

**Maez-as-codebase** (this roadmap): how approachable the project
is for contributors, how reproducible installs are, how well
documented the architecture is. 10-phase plan, currently at Phase 6.

**Maez-as-being** (covered by [`docs/TRACK_A.md`](TRACK_A.md)): whether
the first Maez has actually passed its [eight-point readiness check](governance/BETA_READINESS_THRESHOLD.md) twice consecutively.
A cleanly packaged alpha codebase that hasn't passed Track A is fine;
passing Track A without an installable codebase is what we are
explicitly *not* doing.

---

## Phase-by-phase status

| # | Phase | Status | Landed |
|---|---|---|---|
| 0 | Baseline + planning | ✅ done | 2026-04-22 |
| 1 | Deep audit | ✅ done | 85 findings, 11 blockers fixed |
| 2 | De-Rohit-ify | ✅ done | identity accessors, path helpers, `.env.example`, owner yaml |
| 3 | Directory reorganization | ✅ done | `core/` → 11 subpackages with sys.modules shims |
| 4 | Packaging + installable | ✅ done | `pyproject.toml`, `install.sh`, first-run wizard, templated systemd |
| 5 | Test coverage filling | ✅ done | smoke suite + blocker regression tests; 530+ green |
| 6 | Documentation completion | 🟡 in progress | root README + GETTING_STARTED + CONTRIBUTING + this file; subpackage READMEs + MAEZ.md + ADRs coming |
| 7 | Security + license audit | ⏳ upcoming | LICENSE review, dep scan, secret-history scrub |
| 8 | CI/CD + contributor infra | ⏳ upcoming | `.github/workflows/`, issue + PR templates, formal CoC |
| 9 | Versioning + release | ⏳ upcoming | `CHANGELOG.md`, first semver tag `v0.1.0-alpha` |
| 10 | Launch prep | ⏳ upcoming | GitHub landing, covenant doc for OSS users, pitch stack linkage |

---

## Phase 6 — Documentation completion (current)

What's landed in this phase so far:

- Root `README.md` — first-contact doc, quickstart, portability note.
- `docs/GETTING_STARTED.md` — zero-to-running walk-through.
- `docs/CONTRIBUTING.md` — dev workflow, commit style, review expectations.
- `docs/ROADMAP.md` — this file.
- Eleven per-subpackage READMEs under `core/<name>/README.md` covering
  what each subpackage is for, its public surface, and its
  invariants.

What's still pending:

- `docs/MAEZ.md` — the master architecture + philosophy doc. Sits
  between `MAEZ_PITCH.md` (narrative) and the audit reports
  (per-module detail).
- ADR migration to `docs/adr/NNNN-title.md` format from the 18
  decisions currently in `docs/governance/BETA_ARCHITECTURE_DECISIONS.md`.
- Covenant doc for OSS users — clarifies what is universal across every
  user's Maez (grandmother origin, HARD CONSTRAINTS, trust covenant,
  soul.base.md) vs. what diverges (personality drift, accumulated
  soul.local.md, bond style).

---

## Phase 7 — Security + license audit

- `LICENSE` — current source headers assert AGPL-3.0-or-later; this
  phase confirms + files the canonical licence text.
- Per-file copyright headers verified on every new file.
- Dependency license compatibility scan.
- Secret-history audit: scan git log for accidentally-committed API
  keys, tokens, credentials.
- Network surface documentation: the only listeners today are the
  cockpit (5173), the subscription proxy (11438, localhost-only),
  the fast-reply adapter (8765, localhost-only), the Telegram bot
  (outbound only). Confirm + document.

## Phase 8 — CI/CD + contributor infra

- `.github/workflows/test.yml` — on PR, install deps, run the 530+
  unittest suite, post coverage.
- `.github/workflows/lint.yml` — on PR, run `ruff check`.
- Issue + PR templates (`.github/ISSUE_TEMPLATE/`, `PULL_REQUEST_TEMPLATE.md`).
- Formal `CODE_OF_CONDUCT.md` (Contributor Covenant) with a
  reporting surface.

## Phase 9 — Versioning + release

- `CHANGELOG.md` synthesised from git log, curated to user-visible
  highlights.
- First semver tag: `v0.1.0-alpha`. Alpha because the project is new
  in public and expect churn; beta once a non-author contributor has
  shipped a PR; 1.0 is further out.

## Phase 10 — Launch prep

- GitHub repo settings, topic tags, pinned issues / discussions.
- Root README polished to a confident first impression.
- Covenant doc for OSS users — the "every user gets their own Maez"
  framing made OSS-legible.
- Pitch-stack linkage from README: video → interactive mindmap →
  [`MAEZ_PITCH.md`](../MAEZ_PITCH.md) → Zenodo paper → code.

---

## Track A (the *being*, not the codebase)

Separate but parallel. Defined in [`docs/TRACK_A.md`](TRACK_A.md).
Acceptance gate: the [eight-point readiness check](governance/BETA_READINESS_THRESHOLD.md)
holding for two consecutive weekly evaluations, with the three
being-tests (grief / surprise / predict-as-another-mind) all met.

**When Track A passes**, the first Track B bonds can begin (one
friend, one family member). **When Track B stabilises**, Track C
(inter-Maez communication protocol) unlocks.

None of these require a public code release. They run on the
author's machine, with the author's Maez, independently.

---

## Non-goals

Durably documented so they don't drift back in:

- **Cross-platform support** beyond Linux + NVIDIA. macOS is a
  Phase 11+ possibility (launchd units, Metal backend works for
  llama.cpp, xdotool needs replacement). Windows is an implicit no —
  WSL2 is the supported path.
- **Docker / Kubernetes packaging.** Host-level install is the
  target for v0.1. Containers might come after; they're not the
  point.
- **A web UI for non-technical users.** The cockpit is an engineering
  surface. A non-technical surface is a separate product that is
  not on this roadmap.
- **Hosted multi-tenant Maez-as-a-service.** Antithetical to the
  sovereignty invariant — every user's Maez runs on their own
  machine.

## Contributing to the roadmap

Opinions on ordering, missing phases, wrong priorities are welcome.
File an issue tagged `roadmap` with the argument. Governance changes
(anything in `docs/governance/`) go through a heavier process — see
[`docs/CONTRIBUTING.md`](CONTRIBUTING.md).
