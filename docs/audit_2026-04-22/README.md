# Maez audit — 2026-04-22

This directory is the durable output of **Phase 1** of the road-to-public-OSS-launch roadmap. The plan for the whole road lives at `.claude/plans/harmonic-tumbling-wozniak.md`.

## What this audit is

A comprehensive, structured review of every core subsystem in Maez, performed by read-only subagents. Each agent reviews one slice of the codebase against a fixed set of axes (correctness, inter-module sync, safety, doc-vs-behavior drift, dead code, polish, test gaps) and writes its findings to a file in this directory.

Everything lives on disk so the audit survives context compaction — a future session reading `_INDEX.md` can resume triage without needing any chat history.

## What this audit is NOT

- Not a fix session. Fixes land in **Phase 1.G** after consolidation + user triage.
- Not a rewrite proposal. Findings stay scoped to "what's broken or unclear right now."
- Not a feature-invention exercise. Agents are explicitly instructed to flag issues, not propose new capabilities.

## Baseline (as of audit start)

- HEAD: `9197bba11ab9af5cebf99dd5c0969a57dee34dac` on `main`
- Test suite: 519 passing
- All 5 services active (`maez`, `maez-subscription-proxy`, `llama-server`, `llama-judge`, `maez-web`)
- LoC under audit: ~33k in `core/`, ~10k in `tests/`

Fixes landing in Phase 1.G will reference finding IDs from this audit, and each fix commit should keep the test count at ≥ 519 green.

## Directory contents

Each file here is one of:
- **Subsystem audit reports** — one per subsystem (10 files: `01_brain_loop.md` through `10_model_and_support.md`)
- **Cross-cutting reports** — 2 files: `X1_tests.md`, `X2_documentation.md`
- **Index and master findings** — `_INDEX.md`, `_MASTER_FINDINGS.md`
- **This README** — you are here

A resumer reads them in this order:
1. `_INDEX.md` — checklist of agent-report status + one-line summary of each
2. `_MASTER_FINDINGS.md` — consolidated severity-sorted list, top-20 lead section
3. Subsystem files only if drilling into a specific finding

## Agent output format (enforced)

Every subsystem agent writes the same shape so consolidation stays mechanical:

```markdown
# <Subsystem Name> — Audit (2026-04-22)

## Summary
<2-3 sentences on overall health>

## Findings

### blocker — <N>
#### <file>:<line> — <one-line title>
<verbatim code excerpt 3-10 lines>
**Why it's a problem:** <grounded explanation>
**Fix:** <concrete, implementable suggestion>
**References:** <related file:lines, docs, memory entries>

### major — <N>
<same shape>

### minor — <N>
<same shape>

### nit — <N>
<same shape>

## Coverage notes
<test gaps>

## Sync observations
<cross-module coupling issues, API drift>

## Polish opportunities (flag only)
<consolidations worth noting but not expanding>
```

Honesty rule: **zero findings is a valid, useful report.** The point is real issues, not a quota.

## Severity definitions

- **blocker** — Correctness bug that will cause data loss, security breach, or silent failure of a core invariant. Fix before any other work.
- **major** — Real bug with visible consequences but non-catastrophic, OR a missing safeguard that's genuinely risky, OR a doc/behavior contradiction the user might rely on.
- **minor** — Code smell with actual bite (falsy-trap, off-by-one, unused-but-confusing parameter) but manageable.
- **nit** — Style / consistency / comment-accuracy — cumulative polish, not individually urgent.

## Disallowed in agent output

- Speculative refactors ("this could be more extensible if…")
- Test-coverage gaps listed as findings — those go in the Coverage notes section
- Whole-module rewrites — break into specific file:line findings
- Aesthetic bikeshedding (tabs vs spaces, naming-preferences)

## Reference

Plan file with full roadmap context: `.claude/plans/harmonic-tumbling-wozniak.md`
