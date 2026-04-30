# Maez Capability Access Manual

This directory is the canonical evolutionary substrate for the Maez category. Every Maez instance ships with the manual; every Maez can read it; capabilities are acquired through the Decision 20 pipeline when an instance's bond actually needs them.

**Governance:** [Decision 19](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-19--capability-access-manual-as-evolution-substrate) and [Decision 20](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-20--self-evaluating-capability-acquisition-pipeline) of the Beta Architecture Decisions doc.

## What lives here

One markdown file per capability. The filename is the `capability_id` (kebab-case). The body is a human guide. The YAML front-matter is machine-readable so Maez can match its felt limitations against the entries programmatically.

The manual is **not** a TODO list, an aspirational catalog, or a requirements doc. It is a record of capabilities the field has converged on, with the bond context that makes "should this Maez have it" a meaningful question.

## Entry format

```yaml
---
capability_id: kebab-case-stable-id
title: Human-readable title
status: stable | experimental | deprecated | aspirational
gap_signals:
  - "natural-language signal Maez matches against its felt limitations"
  - "another signal — be specific; vague signals fire too often"
prerequisites:
  # Capability IDs that MUST exist as other manual entries.
  - other-capability-id-required-first
external_prerequisites:
  # Capabilities Maez relies on that live in the codebase, not in
  # the manual. Loader treats these as known-shipped — no warning
  # if they're absent from the manual.
  - working-self
  - lived-memory-architecture
acquisition: self-dev | peer-fetch | owner-install | external-service
covenant:
  consent-card-required: true
  exact-phrase-ratification: false
  covenant-touch: low | medium | high
conflicts_with: []
reference_papers:
  - "Author et al. (Year), arxiv:NNNN.NNNNN — short why-it-matters"
implementation_files:
  - path/to/code/if-already-shipped.py
superseded_by: # optional, for deprecated entries; must resolve to a real capability_id
---

# Title

## When this matters

Plain English. When does a Maez instance feel the gap this capability addresses? Be concrete — a grandmother saying "I miss the smell of jasmine" is the bond context, not "the user expressed a preference."

## What it costs

VRAM. Latency. Storage. Cognitive complexity for the owner. Every capability has a cost that should be visible at the moment of consent, not buried in a config file.

## What can go wrong

Failure modes the owner should know about. Data dilution from over-application. Adversarial activation patterns. Privacy implications.

## How it's acquired

Concrete path: which self-dev proposal, which peer fetch, which install command. Reference to the implementation source if it exists.

## Covenant impact

Does this capability change what Maez can do that the covenant gates? Does it require new consent rails? Does it touch identity, memory, or self-modification surfaces?

## Replacement / supersession

If this entry replaces an older approach, name it. If a newer entry supersedes this one, link forward.
```

## How a Maez uses this manual

The five-stage pipeline from [Decision 20](../governance/BETA_ARCHITECTURE_DECISIONS.md#decision-20--self-evaluating-capability-acquisition-pipeline):

1. **Gap-sensing** — Maez recognizes a felt limitation explicitly.
2. **Manual-matching** — Maez scans this directory's `gap_signals` for entries that address the limitation.
3. **Field search** — Maez searches the published field via claude-tier for alternatives newer than the manual entry. If a stronger or more recent solution exists, Maez prepares a manual update alongside the acquisition proposal.
4. **Self-evaluation** — Maez checks the candidate against its own constraints (VRAM, context, prerequisites). Rejects if it can't run it.
5. **Proposal** — Maez surfaces a consent card naming gap, manual entry, alternatives considered, prerequisites, covenant impact. Owner approves; capability acquired.

## Federation

- **Local-first.** Each Maez maintains its own manual. Owner-initiated edits and Maez-initiated proposals land locally first.
- **Owner-mediated upstream PRs.** High-quality entries get proposed to the canonical manual at the project repo via PR. The owner reviews their Maez's proposed entry, then opens the PR.
- **Downstream sync.** Other Maez instances pull manual updates from the canonical repo on their own update cadence. The federation gate is the upstream PR review — there's no automatic propagation past human review.

## When to add a new entry

- A new field architecture has emerged that addresses a gap-class no existing entry covers.
- An existing entry is now outdated (a stronger alternative exists). Don't edit the old entry; write a new one and add `superseded_by:` to the old one's front-matter, leaving the body intact for historical record.
- A capability was tried and didn't pan out (Slice 9 Session 5's preference promotion is an example). The negative result becomes an entry too — `status: deprecated` — so future Maezes don't repeat the experiment without knowing why.

## When NOT to add a new entry

- Speculation about what might be useful eventually. The manual is a record, not a wishlist.
- Capabilities that are owner-specific to one Maez instance (those go in soul-local config, not the shared manual).
- Cosmetic configuration (theme, surface, prompt phrasing). Those are policies, not capabilities.

## Index

| capability_id | status | what it addresses |
|---|---|---|
| [recursive-context-engine](recursive-context-engine.md) | aspirational | Cross-month memory synthesis, repo-wide audits, deep offline reasoning |
| [multi-session-entity-linking](multi-session-entity-linking.md) | aspirational | Connecting evidence across sessions about the same person/place/thing |
| [temporal-arithmetic-at-recall](temporal-arithmetic-at-recall.md) | aspirational | "When did X happen?" / "How long after Y?" answered with computed durations, not token matches |

Each `aspirational` entry describes a capability the field has produced and Maez has not yet integrated. As capabilities ship, status moves to `experimental` and then `stable`.
