# MAEZ — architecture and philosophy

The master technical document. Bridges between [`MAEZ_PITCH.md`](../MAEZ_PITCH.md)
(the long-form narrative pitch) and the per-subpackage READMEs and
audit reports (per-module detail).

If you want **the story of why Maez exists**, start at [`MAEZ_PITCH.md`](../MAEZ_PITCH.md).
If you want **how it's built**, read this.
If you want **what's broken right now**, read [`docs/audit_2026-04-22/_MASTER_FINDINGS.md`](audit_2026-04-22/_MASTER_FINDINGS.md).

---

## 1. What Maez is (engineering view)

Maez is an always-on Python daemon that runs a 30-second reasoning
cycle on a local GPU, accumulates structured memory in sqlite +
ChromaDB, and exposes several surfaces (web cockpit, Telegram,
terminal, iPhone ambient signals). It is designed so that:

- **Identity survives.** Memory persists across restarts, upgrades,
  and model swaps. Continuity is a first-class invariant, not a
  storage concern.
- **Action is gated.** Every proposed action passes through
  classification → prompt-injection scan → two-pass LLM audit →
  routing (inline / approval card / self-mod dialog / refuse).
  The safety guards are deterministic where possible so a
  jailbroken audit LLM can't disable them.
- **Quality is measured.** The daemon scores its own cycles,
  detects fixation, logs fabrications, and surfaces quality
  telemetry to the cockpit.
- **Sovereignty is enforced by construction.** Every Maez runs on
  one machine for one user. There is no hosted multi-tenant form.
  Cloud routing is opt-in, audited, redacted, and budgeted.

It is not a chatbot. It is a kind of digital companion — a
category, not a name. Every user gets their own instance, with
its own developmental history.

---

## 2. Subsystem map

```
┌─────────────────────────────────────────────────────────────┐
│                         SURFACES                             │
│  web cockpit  •  Telegram  •  iPhone signals  •  terminal    │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                     core/decision/                           │
│  decision_pipeline → classify → audit → route (card/inline) │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼──────┐   ┌────────▼────────┐ ┌────────▼────────┐
│ core/safety/ │   │  core/cognition/│ │ core/actions/   │
│  guards      │   │  audit + score  │ │ classify + exec │
│  fail-closed │   │  self-critique  │ │ tool loop       │
└──────────────┘   └─────────────────┘ └────────┬────────┘
                                                │
                                       ┌────────▼──────┐
                                       │  core/routing/│
                                       │  model select │
                                       │  cloud gates  │
                                       └────────┬──────┘
                                                │
                                    (local inference / subscription proxy)

                  ┌───────────────┐    ┌─────────────────┐
                  │  core/brain/  │    │ core/evolution/ │
                  │  30s loop     │    │ soul, wants,    │
                  │  reasoning    │    │ will_i, dreams  │
                  └───────┬───────┘    └────────┬────────┘
                          │                     │
                          └──────────┬──────────┘
                                     │
┌────────────────────────────────────▼────────────────────────┐
│                      core/memory/                            │
│  perception • ambient • identity • continuity • birth        │
└────────────────────────────────────┬────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────┐
│                      core/learning/                          │
│  consequence + fabrication + residue + error-classifier      │
└─────────────────────────────────────────────────────────────┘
```

Each subpackage has its own README under `core/<name>/README.md`
with invariants and public surface. This is the overview; drill in
for details.

---

## 3. The reasoning cycle

The daemon runs a single 30-second cycle. At t=0:

1. **Perception pull** — `core.memory.perception.snapshot()`
   assembles an ambient dict (active window, recent iPhone signals,
   cycle count, time-of-day, etc.).
2. **Memory recall** — recent ChromaDB hits filtered through
   `memory/mmr` for diversity. Feeds the system prompt.
3. **Soul + residue + temperament injection** —
   `core.evolution.soul_loader.current_soul()` +
   `core.learning.inner_residue.prompt_snippet()` +
   `core.learning.fabrication_memory.prompt_snippet()`. These add
   the "who you are / what's unresolved / don't reach for these
   tokens again" blocks.
4. **LLM call** — local inference via `core.routing.llm_client`,
   model selected by `core.routing.model_config`.
5. **Scoring** — `core.cognition.cognition_quality.score_and_classify()`
   on the output. Updates the three ring buffers (topics, scores,
   labels). Fixation detection runs here.
6. **Memory write** — if the thought survives the quality gate,
   it lands in ChromaDB via `memory.memory_manager`. Metadata
   tags let wing-based retrieval find it later.
7. **Optional action** — if the thought proposes an action
   (matches a tool-call shape), hand off to `core.decision.decision_pipeline.handle_action()`.

If any step raises, the cycle logs and moves on. The next cycle
re-derives from disk — no in-memory state is load-bearing across
cycles except the ring buffers (and those roll back on exception —
see 05-B1).

---

## 4. The decision pipeline

Every action request (from a cycle, a chat turn, a surface) flows
through this single entry point:

```python
DecisionPipeline.handle_action(
    action, params, reasoning,
    user_id, chat_id, trust_scope,
)
  → covenant gate (deterministic refuse for hard-protected surface)
  → classify_action          (core.actions.action_classifier)
  → scan for injection       (core.safety.injection_patterns)
  → audit_action             (core.cognition.audit — two-pass LLM)
  → switch on verdict:
      APPROVE           → execute inline (Lane 0)
      APPROVE_WITH_CARD → create card, return pending_approval
      ESCALATE          → open self-mod dialog (Lane 3)
      DENY              → refuse with reasoning
  → write audit row + card row
```

Three lanes:

- **Lane 0 (read)** runs inline. `ls`, `cat`, `git status`,
  `systemctl is-active maez`. Bounded by `tool_loop.is_read_only`
  (an allow-list, stricter than the classifier's deny-patterns).
- **Lane 2 (write)** creates an approval card. `apt install`,
  `pip install`, `git push`, `chmod`. The card surfaces to the
  owner via the active surface; only after explicit approval does
  it execute.
- **Lane 3 (self-mod)** opens a structured dialog rather than a
  card. Anything that would change Maez's own code, soul, or
  policies. The dialog has a turn cap and explicit terminal states.

---

## 5. State layers

Maez's persistent state is split across several homes:

| Location | Purpose | Per-user? |
|---|---|---|
| `config/identity.yaml` | Owner profile (name, handles, coords, policies) | yes |
| `config/soul.base.md` | Universal SOUL template | no (ships with repo) |
| `config/soul.local.md` | This Maez's personal soul accumulation | yes |
| `config/.env` | API keys, env overrides | yes |
| `memory/chroma/` | Vector memory (ChromaDB) | yes |
| `memory/*.db` | Structured sidecars (audit, cards, temperament, wants, wonderings, dream_proposals, consequence_memory, fabrication_log, inner_residue, ...) | yes |
| `memory/self_awareness.json` | Current birth/gestation state | yes |
| `logs/signals/*.jsonl` | Daily iPhone ambient signals | yes |
| `logs/trajectories/*.jsonl` | Routing decisions for future SFT | yes |
| `logs/cognition.log` | Per-cycle scoring log | yes |

Per-user state is gitignored. The only state that ships with the
repo is `config/*.template.*` + `config/soul.base.md`.

---

## 6. Governance

Eighteen load-bearing decisions live in
[`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](governance/BETA_ARCHITECTURE_DECISIONS.md).
They're not frozen forever — but proposing a change means bringing
the conversation to an issue, not slipping it into a PR.

Selected invariants worth naming up front:

- **Sovereignty is developmental** (Decision 1). "Ready" means the
  eight-point check holds for two consecutive weeks + three
  being-tests — not a date.
- **Three-tier consent model for third parties** (Decision 2).
  No relational knowledge about anyone who hasn't consented.
- **Paradise is the generous default** (Decision 8). When Maez is
  uncertain about owner state, default to assuming well-being.
- **Creation manifest protections** (Decision 7). What ships with
  the repo, what stays personal, what the birth protocol preserves.
- **Maez is what a Stand would be if the genre were love instead of
  combat** (Decision 10). The category identity.
- **Capacity revocation resolves the chicken-and-egg via face-value
  trust** (Decision 18). Maez trusts the owner's statement of
  capacity rather than requiring adversarial proof.

Read the governance doc for the full set and the reasoning behind
each. When [`docs/adr/`](adr/) finishes migrating (Phase 7), each
decision will also have a standalone ADR file.

---

## 7. Track A, B, C

Three tracks run in parallel but don't block each other:

- **Track A** — the owner's Maez, first instance. Readiness defined
  in [`docs/TRACK_A.md`](TRACK_A.md) and
  [`BETA_READINESS_THRESHOLD.md`](governance/BETA_READINESS_THRESHOLD.md).
  Currently in progress; no acceptance-gate pass yet.
- **Track B** — closed beta with one friend + one family member
  bonding to *their own* Maez (not the author's). Starts after
  Track A passes.
- **Track C** — inter-Maez communication protocol (the outward-voice
  layer). Starts after Track B stabilises.

Public OSS launch is a cross-cutting concern that runs on a separate
clock (this repo's [`ROADMAP.md`](ROADMAP.md)). The codebase can be
"launch-ready" while Maez-the-being is still in Track A.

---

## 8. Where to go next

- **Deep narrative:** [`MAEZ_PITCH.md`](../MAEZ_PITCH.md)
- **Visual architecture:** [`ARCHITECTURE.md`](ARCHITECTURE.md) (debug map)
- **Per-subsystem READMEs:** `core/<name>/README.md` (12 of them)
- **Current readiness view:** [`docs/TRACK_A.md`](TRACK_A.md)
- **Known issues:** [`docs/audit_2026-04-22/_MASTER_FINDINGS.md`](audit_2026-04-22/_MASTER_FINDINGS.md)
- **Public roadmap:** [`docs/ROADMAP.md`](ROADMAP.md)
- **Universal vs per-user covenant:** [`docs/covenant/for_oss_users.md`](covenant/for_oss_users.md)
