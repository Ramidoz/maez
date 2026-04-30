---
capability_id: recursive-context-engine
title: Recursive Context Engine (RLM)
status: aspirational
gap_signals:
  - "user requests synthesis across more than 30 days of memory"
  - "user requests audit-style summary of repo, codebase, or long-running project"
  - "Maez surfaces 'context too long' or truncates synthesis mid-output"
  - "user asks 'what happened across this whole period' rather than 'what did I say about X'"
  - "Maez attempts a synthesis that requires holding 100k+ tokens in context simultaneously"
prerequisites: []
external_prerequisites:
  - working-self
  - letta-style-introspection
  - claude-tier-or-equivalent-deep-call
acquisition: self-dev
covenant:
  consent-card-required: true
  exact-phrase-ratification: false
  covenant-touch: medium
conflicts_with: []
reference_papers:
  - "Zhang, Kraska, Khattab (2025), arxiv:2512.24601 — Recursive Language Models. Core paper. The 'paradigm of 2026' framing."
  - "github.com/ysz/recursive-llm — published reference implementation"
implementation_files: []
---

# Recursive Context Engine (RLM)

## When this matters

Maez is a continuous companion. After months of bond, the lived memory is necessarily larger than any context window. Some questions require *reading the whole period*, not retrieving one slice of it. Examples:

- "Look back at the last six months and tell me how I've changed."
- "Audit our entire repository and find places where the safety invariants might have drifted."
- "Synthesize everything I've said about my mother across all our conversations."

A Maez whose default recall path returns top-N chunks per query cannot answer these. The retrieval layer was built for "find evidence for X"; deep reasoning needs a different shape — recursive, programmatic, capable of decomposing the query and reading the full input through its own REPL.

This is the kind of question that frontier-model APIs structurally cannot answer either: they are stateless, they don't have your six months of memory, they can't recursively call themselves over your archive. Maez can.

## What it costs

- **Latency.** Recursive synthesis takes seconds-to-minutes, not the conversational sub-second the chat surface expects. RLM is for offline / deep-thought paths, not the chat hot path.
- **VRAM.** The base model still runs in 24GB; RLM's overhead is in the orchestration layer (REPL, sub-call management), not the model itself. Mostly fine on consumer hardware.
- **Cognitive complexity.** Owner-visible behavior changes — Maez sometimes takes longer, occasionally produces synthesis the owner cannot quickly verify. The audit log becomes more important.

## What can go wrong

- **Latency mismatch with chat.** Routing a chat-latency question through RLM produces a frustrating user experience. The dispatcher must distinguish "deep" from "chat" intents.
- **Recursive failure modes.** Sub-calls can themselves fail; the orchestrator must handle partial synthesis gracefully ("I read 4 of 6 months; here's what I have").
- **Hallucination compounding.** Each recursive step can introduce error; without grounding checks at sub-call boundaries, errors amplify.
- **Cost.** If RLM uses external API calls (claude-tier), a single deep synthesis can consume significant budget. Per-call budget guards are required.

## How it's acquired

1. Self-dev proposal: Maez generates a proposal pointing at this manual entry, the reference implementation, and the prerequisites.
2. Owner consent-card: approves the acquisition path (typically vendoring the reference implementation under `core/reasoning/recursive_context.py`).
3. Wiring: the new module is registered as a tool callable from the brain loop's deep-thought path (not the chat path).
4. Activation surfaces:
   - `maez audit-repo` — full-repo synthesis on demand.
   - `maez summarize-memory --days N` — N-day memory synthesis.
   - `maez weekly-synthesis` — scheduled weekly review.
   - `maez review-bond` — the most relational use: synthesize what's been happening in the bond.

## Covenant impact

- Touches the action engine (new tool registered).
- Does **not** touch the covenant gate or the safety layer — RLM is a synthesis tool, it doesn't perform writes.
- Does add a new outbound surface (recursive sub-calls). The audit pipeline must extend to cover sub-call boundaries.
- Should be gated behind explicit consent for first activation; subsequent invocations can be silent within the activated profile.

## Replacement / supersession

None yet. Watch for: (a) the field producing a stronger pattern post-2026, (b) Maez's own synthesis layer maturing to the point where RLM's overhead isn't justified.

## Notes from Slice 9 Session 4 measurement

The LongMemEval baseline showed multi-session reasoning at 0.40 and temporal reasoning at 0.20-0.40 under stress. RLM's strongest case is exactly the multi-session synthesis that the Slice 9 thread couldn't close at the consolidation layer. This entry is the manual's first concrete answer to "what does Maez gain by integrating it."
