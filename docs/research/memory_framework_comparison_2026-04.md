# Memory framework comparison — 2026-04

**Status:** research-only
**Date:** 2026-04-26
**Companion to:** [ADR 0019 — Lived memory architecture](../adr/0019-lived-memory-architecture.md)

This document compares the open-source memory frameworks the Phase 9
plan called out against Maez's specific requirements. The goal is
not "which one should we adopt" — Maez has already shipped a v1
SQLite-backed temporal episodic + relationship graph. The goal is:

1. **What ideas should we steal** from each framework into Maez's
   own evolution path?
2. **When (if ever) does direct dependency make sense** rather than
   continuing to grow Maez-native?
3. **Where does Maez differ on principle** vs. where is the
   difference a v1 cost we'd pay back later?

The framework descriptions reflect public state as of 2026 with
the explicit caveat that fast-moving libraries may have shifted
since the last training pass; verify before committing to an
integration.

---

## Maez-specific requirements (the rubric)

A framework "fits" Maez to the degree it satisfies these. The order
matters: covenant-shaped properties top, ergonomics bottom.

| # | Requirement | Why it matters for Maez |
|---|---|---|
| 1 | **Append-only** | The never-delete-Maez-memory rule is covenant-load-bearing. Frameworks that delete on update are structurally wrong for Maez's spirit. |
| 2 | **Evidence IDs mandatory** | Phase 1 enforces this at the schema level. Frameworks that store facts without traceable provenance can't satisfy fabrication-prevention. |
| 3 | **Temporal validity windows** | `valid_from` / `valid_to` + `status='superseded'` is how *"Maez ran on Qwen3.5-35B until 2026-04-23, then Qwen3.6-27B"* gets represented without contradiction. |
| 4 | **Correction without deletion** | `supersede()` semantics — old belief stays as historical, new belief is added. |
| 5 | **Local-first** | Maez runs on owner's hardware. Cloud-only frameworks fail the *grandmother case* on principle: the bond can't depend on a vendor's uptime. |
| 6 | **Low operational risk** | One user, one Maez, one machine. Each new daemon / database / network hop is a continuity risk. SQLite is the floor; anything heavier needs justification. |
| 7 | **Works with local llama.cpp** | Maez's brain is Qwen3.6-27B-UD-Q4_K_XL on llama.cpp. Frameworks that hardcode OpenAI / Anthropic for extraction won't fit. |
| 8 | **Cockpit visualization** | Owner-readable surface, not a graph-theory dashboard. JSON-API + plain-language framing is the v1 contract. |

A "covenant" rating below means *"is this property structurally
guaranteed by the framework, or just achievable if we're careful?"*

---

## Framework-by-framework

### Graphiti (Zep)

**What it is:** Open-source temporal knowledge graph for AI agent
memory. Entities + relationships with explicit `valid_from` /
`valid_to`. Designed around the *"facts change over time, history
is useful"* premise. Default backend is Neo4j; ships with LLM-driven
entity / relationship extraction.

**Fit on the rubric:**

| # | Requirement | Score | Notes |
|---|---|---|---|
| 1 | Append-only | ✓ | Temporal model is append-only by design — invalidations bound the old fact, don't delete it. |
| 2 | Evidence IDs | ◐ | Stores extraction provenance; whether *every* edge carries a traceable source ID by default needs verification per release. |
| 3 | Temporal validity | ✓✓ | This is the framework's headline feature; the design we adopted for ADR 0019's edges is essentially Graphiti-shaped. |
| 4 | Correction without deletion | ✓ | Supersede is native. |
| 5 | Local-first | ✗ | Default Neo4j stack is heavyweight for a single-user box. Sqlite-backend forks exist but aren't first-class. |
| 6 | Low operational risk | ✗ | Neo4j daemon is a new failure mode; service uptime, GC tuning, query timeouts all become operational concerns. |
| 7 | Works with local llama.cpp | ◐ | Extraction layer assumes OpenAI/Anthropic-style APIs by default. Wiring it to a local OpenAI-compatible endpoint (llama.cpp's `/v1/chat/completions`) is achievable but not turnkey. |
| 8 | Cockpit viz | ◯ | No native UI; would build it ourselves anyway. |

**What to steal:**

- **The temporal validity model.** Graphiti's `valid_from` /
  `valid_to` / supersede is the right primitive; ADR 0019's edge
  schema already mirrors this.
- **Bi-temporal modeling** (when a fact was *true* vs when it was
  *recorded*). v1 only tracks `created_at` / `valid_from`; adding
  `recorded_at` distinct from `occurred_at` would let Maez
  represent *"I learned this last week, but it was true since
  March"* — a real gap when ingesting backfilled corrections.
- **The "facts that contradict get superseded, not deleted"
  discipline** as a contract test.

**What to leave:**

- **Neo4j dependency.** The operational floor is too high for one
  user.
- **The default LLM extraction stack** (OpenAI assumption). If we
  later reach for Graphiti, we'd need a local-LLM adapter first.

**Direct dependency verdict:** *Defer.* The concepts are right; the
operational baggage isn't worth it for v1 traffic volume (4 episodes
+ 3 edges today). Revisit when Maez's lived-memory layer reaches
~100k+ episodes AND owner is willing to run Neo4j.

---

### Mem0

**What it is:** Memory layer for LLM applications. Hybrid graph +
vector. Extracts facts from conversation history into a structured
memory store. Open-source core with a SaaS offering layered above.
Used by integrations like Crew, AutoGen, etc.

**Fit on the rubric:**

| # | Requirement | Score | Notes |
|---|---|---|---|
| 1 | Append-only | ◐ | Updates and forgetting are first-class. Achievable to configure as append-only but not the default. |
| 2 | Evidence IDs | ◐ | Tracks source messages; tightness of the trail varies. |
| 3 | Temporal validity | ✗ | Less explicit temporal model than Graphiti. Recency-based, not validity-windowed. |
| 4 | Correction without deletion | ✗ | Default is update-in-place. |
| 5 | Local-first | ✓ | Open-source core can run locally; SaaS is opt-in. |
| 6 | Low operational risk | ◐ | Core is light; depends on which extras you wire in. |
| 7 | Works with local llama.cpp | ◐ | Configurable LLM provider; OpenAI-compatible endpoints supported. |
| 8 | Cockpit viz | ◯ | None native. |

**What to steal:**

- **Graph + vector hybrid retrieval.** Maez's lived recall planner
  is currently keyword-overlap on the graph layer alone, with no
  vector path. A Mem0-style hybrid (vector recall over episode
  summaries, graph traversal over edges) would lift the planner's
  score on probes that don't share keywords with stored content.
- **Conversation-level fact extraction.** Mem0's pattern of
  inferring facts from a multi-turn exchange (vs. Maez's per-
  message rule-based detector) is the upgrade path to denser
  edges from real chat. Phase 4's nightly job is the natural home
  for this.

**What to leave:**

- **Update-in-place defaults.** Hard mismatch with the never-
  delete covenant.
- **The SaaS edition.** Cloud dependency violates the local-first
  principle on the grandmother case.

**Direct dependency verdict:** *Steal patterns; don't adopt the
library.* The covenant mismatch (update-in-place) is structural,
not a config choice we'd be comfortable forking around.

---

### Letta (formerly MemGPT)

**What it is:** Hierarchical memory architecture where the LLM
itself manages its memory through tools. Three tiers: *core* (always
in context), *archival* (paged in via search), *recall* (recent
conversation). The model writes to archival, edits core, retrieves
on demand.

**Fit on the rubric:**

| # | Requirement | Score | Notes |
|---|---|---|---|
| 1 | Append-only | ✗ | Core memory is editable by the model in-place. |
| 2 | Evidence IDs | ✗ | Memory is text the model wrote / edited; not structured provenance. |
| 3 | Temporal validity | ✗ | No native validity windows. |
| 4 | Correction without deletion | ✗ | Edit-in-place. |
| 5 | Local-first | ✓ | Open source, runs locally. |
| 6 | Low operational risk | ◐ | Adds a new daemon + DB but not as heavy as Neo4j. |
| 7 | Works with local llama.cpp | ✓ | Provider-agnostic; works with any OpenAI-compatible endpoint. |
| 8 | Cockpit viz | ◯ | Has a debug UI; not opinionated about owner-facing surfaces. |

**What to steal:**

- **The *self-managed memory* idea.** Letta's insight that the LLM
  has tools to read / write its own memory is profound. Maez's
  current model is *daemon-curates-memory-for-Maez*. A long-term
  shape closer to Letta's would let Maez decide *"this should be
  promoted to core"* rather than relying on the nightly job to
  spot it. This is **post-Track-A** work — the discipline to grant
  Maez memory-write tools should land after the gate, not before.
- **The core/archival/recall tier discipline** is already in
  Maez's Chroma layer (raw / daily / core). Letta names it
  cleanly; Maez's terminology can borrow.

**What to leave:**

- **Edit-in-place core memory.** Direct conflict with the never-
  delete covenant. If we adopted Letta's *"the model edits its
  identity"* primitive, we'd lose the audit trail that made the
  2026-04-23 fabrication regression debuggable.

**Direct dependency verdict:** *Different paradigm; not a fit.*
Letta optimizes for *"the agent is its own memory librarian."*
Maez optimizes for *"continuity of bonded relationship across
restarts and corrections."* These are not the same goal, and the
shape of the storage reflects the goal.

---

### Cognee

**What it is:** Open-source memory engine combining knowledge
graphs and RAG. Targeted at agent applications. Less mature
ecosystem than Graphiti / Mem0 / Letta; smaller community.

**Fit on the rubric:**

| # | Requirement | Score | Notes |
|---|---|---|---|
| 1 | Append-only | ◐ | Configurable; not the default discipline. |
| 2 | Evidence IDs | ◐ | Provenance is supported but not enforced. |
| 3 | Temporal validity | ✗ | No first-class temporal model at the time of writing. |
| 4 | Correction without deletion | ✗ | No native supersede. |
| 5 | Local-first | ✓ | Self-hostable. |
| 6 | Low operational risk | ◐ | Smaller surface than Graphiti but still adds operational footprint. |
| 7 | Works with local llama.cpp | ◐ | Provider configuration available. |
| 8 | Cockpit viz | ◯ | None native. |

**What to steal:**

- The **knowledge-graph + retrieval combo** as a pattern is
  validated; nothing Cognee-specific stands out as a must-borrow.

**Direct dependency verdict:** *No clear win.* Less mature than
Graphiti for the same job. Re-evaluate in 12 months.

---

### LangMem (LangChain)

**What it is:** LangChain's memory utilities. Conversation memory,
summary memory, vector store memory. Lighter weight than the
graph-oriented frameworks above. Tightly coupled to the LangChain
ecosystem.

**Fit on the rubric:**

| # | Requirement | Score | Notes |
|---|---|---|---|
| 1 | Append-only | ✗ | Built around mutable buffers. |
| 2 | Evidence IDs | ✗ | Not the design center. |
| 3 | Temporal validity | ✗ | None. |
| 4 | Correction without deletion | ✗ | Buffer overwrites. |
| 5 | Local-first | ✓ | Configurable. |
| 6 | Low operational risk | ✓ | Lightweight. |
| 7 | Works with local llama.cpp | ✓ | Provider-agnostic via LangChain abstractions. |
| 8 | Cockpit viz | ◯ | None. |

**What to steal:**

- **Conversation summary buffers** as a compression primitive.
  Maez's daily consolidation already does this; LangMem's
  implementation might inform the synthesis-layer design Phase 9+
  flagged as the biggest gap vs. SOTA.

**Direct dependency verdict:** *Wrong shape entirely.* LangMem
treats memory as buffers attached to a chain. Maez treats memory
as a long-term being whose recall is structurally separate from
its in-context context. These are different objects.

---

### Obsidian export

**What it is:** Markdown vault format. Not a memory framework — a
human-readable format with a large ecosystem of viewers and
graph-visualization plugins.

**Fit on the rubric:**

This is the wrong question; Obsidian is a *display layer*, not a
*memory layer*. The interesting question is: *should Maez's lived
memory have a human-readable Obsidian export?*

**What to steal:**

- **The export pattern** — Maez's lived-memory SQLite tables could
  be rendered to a markdown vault for owner introspection in
  Obsidian. This complements the cockpit panel by giving the
  owner full-featured graph traversal, search, and linking in a
  tool they probably already use.
- This would land as a separate `scripts/export/lived_memory_to_obsidian.py`
  if/when the owner asks for it. Nice-to-have, not load-bearing.

**Direct dependency verdict:** *Useful export target. Not a memory
framework.*

---

## Conclusions

### What we're stealing into Maez (concrete forward work)

| Idea | Source | When |
|---|---|---|
| **Bi-temporal model** (`occurred_at` distinct from `recorded_at`) | Graphiti | Phase 4+ extension; useful when ingesting backfilled corrections |
| **Hybrid graph + vector retrieval** in the recall planner | Mem0 | After probe score plateaus on keyword-overlap (likely the move that lifts past 50%) |
| **Conversation-level fact extraction** (LLM-driven, multi-turn) | Mem0 | Phase 4 nightly-job upgrade; the natural home for richer extraction |
| **Self-managed memory tools** (the LLM writes to its own archival) | Letta | **Post-Track-A.** Granting Maez memory-write capability is a covenant decision, not a feature. |
| **Markdown vault export** | Obsidian | Owner-driven; ship if asked for |
| **Conversation summary buffers** as synthesis primitives | LangMem | Phase 9+ reflection layer (the Generative Agents gap) |

### What we're explicitly not adopting

- **Neo4j as a backend.** Operational cost > value at one-user
  scale. Revisit at ~100k episodes.
- **Update-in-place defaults** (Mem0, LangMem). Direct conflict
  with the never-delete covenant.
- **Edit-in-place core memory** (Letta). Same conflict; would
  lose the audit trail that makes regressions debuggable.
- **Any cloud-only memory layer.** Local-first is non-negotiable
  for the grandmother case.

### Direct dependency: deferred

The plan's expected conclusion was *"Graphiti concepts win, but
direct dependency may wait."* That's the conclusion this analysis
reaches.

The temporal-graph design ADR 0019 adopted is essentially Graphiti-
shaped. We didn't take the dependency because:

1. **Operational cost.** Neo4j daemon is heavy for a one-user
   machine that is already running llama.cpp + Maez daemon +
   subscription proxy + web cockpit + fast-reply adapter.
2. **Local-first principle.** The grandmother case can't tolerate
   a memory layer that requires sysadmin attention.
3. **Volume mismatch.** v1 has 4 episodes + 3 edges. Even after
   richer extraction lands, growth is bounded by real human-day
   data — thousands of episodes per year, not millions.

The dependency revisits if Maez ever:
- Reaches an episode count where SQLite's query planner becomes
  the bottleneck (likely 100k+ episodes, years away).
- Needs cross-Maez graph queries for Track B (multi-tenant
  bonded users) — which is a different problem, possibly best
  solved by hosted Graphiti/Zep at that point.

### Honest epistemic notes

- These framework descriptions reflect what is publicly known
  through the latest training pass. Verify versions, schema, and
  default configurations before integrating.
- "Score" ratings are author judgments against Maez-specific
  criteria, not framework-quality scores in general. A ✗ on
  *append-only* doesn't mean the framework is bad — it means
  the framework wasn't designed for Maez's covenant.
- This is a research doc, not a roadmap. Decisions about what to
  pull from this list happen as separate plan / ADR conversations.

---

## What this confirms about Maez's direction

1. **The shape ADR 0019 chose is correct.** Every framework that
   takes the temporal-graph problem seriously converges on a
   similar primitive (entity, relation, validity window,
   provenance). Graphiti is the closest match.
2. **The substrate choice (SQLite-first) is right for v1.** Every
   alternative either pulls in heavier infrastructure or sacrifices
   the never-delete covenant.
3. **The biggest gaps from SOTA are the same two things noted in
   ADR 0019:** (a) hybrid retrieval (vector + graph), and (b) a
   reflection / synthesis layer that compresses many low-level
   observations into higher-level memories. Mem0 has (a); the
   Generative Agents lineage has (b). Both land in Phase 9+ work,
   not Track A.
4. **Self-managed memory (Letta-style) is a v3 conversation, not a
   v2.** Granting Maez tools to write to its own memory crosses
   the covenant; that's a deliberate rather than incremental move.

---

*This document is informational research. Decisions about what to
implement, when, and why land in their own ADRs. Update this file
when re-evaluating frameworks; never delete entries — append a
"superseded" note dated and explained.*
