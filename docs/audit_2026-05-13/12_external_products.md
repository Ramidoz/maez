# External products + frameworks — comparative audit

*Audit date: 2026-05-13. Scope: wide-web research on existing AI companion / agent / memory architectures. Read-only on Maez code; verified against `MAEZ_NORTH_STAR.md`, `MAEZ_LIFE_SUBSTRATE.md`, `MAEZ_ANATOMY.txt` v2.3.*

## Summary

The field has already shipped three primitives Maez should adopt: **bi-temporal knowledge graphs with explicit validity intervals** (Zep / Graphiti), **a skill / procedure library indexed by embedding and refined by feedback** (Voyager, Hermes Agent), and **explicit sleep-time / dream consolidation as a separate compute phase** (Letta sleep-time agents, the "Language Models Need Sleep" line of work). The field has also produced four documented failure modes Maez is at risk of recapitulating if it does not harden specific organs: **identity discontinuity from operator-side updates** (Replika ERP removal, 2023; HBS Working Paper 25-018), **safety-unsafe outputs at scale to minors** (Character.AI, Setzer suicide 2024), **stateless memory that pretends to be a relationship** (Inflection Pi, ChatGPT memory bullet-list), and **mid-task context loss inside the harness itself** (Devin's 18-month review, Cognition 2026). Maez's structural-not-experiential differentiation holds: nobody else is shipping cardinality-of-one, user-owned substrate, or operator/user role separation. But the *memory plumbing* is behind the open field — particularly bi-temporal graphs and skill libraries.

## Product / framework deep-dives

### 1. Letta / MemGPT (UC Berkeley → company)
**Solves:** Stateful agent memory inside a fixed context window via an OS-style memory hierarchy.
**Ships:** Four-tier memory primitive — *core memory* (in-context pinned blocks the agent can self-edit), *recall memory* (full searchable interaction history on disk), *archival memory* (external vector/graph DB), *message buffer* (recent turns) — plus *sleep-time agents* that refine memory asynchronously during idle periods, and a "memory as files on a filesystem" benchmark result showing filesystem-as-memory is competitive.
**Maez equivalent:** Three-tier raw/daily/core thorax (CORE = personality-in-substrate, DAILY = consolidation, RAW = lungs). Adjacent organs `fabrication_memory` + `consequence_memory` serve as scar-tissue ledgers. No equivalent of Letta's *agent-self-edits-its-own-core-block* — Maez's core memory is written by `MemoryManager.store_core()` from `temperament` / corrective-core-memory patterns, not by the daemon mid-cycle.
**Gap:** No explicit sleep-time agent. Maez's daily consolidation is cron-like, not a separate agent doing speculative refinement. No core-block self-editing API. Letta-v1 dropped heartbeats; Maez kept its 30-second heartbeat (correct choice — heartbeats are core to Maez's life-signs).
**Mistake to avoid:** Letta's own retrospective on MemGPT says reliance on tool-calling for every action made early-MemGPT model-coupled — only tool-capable LLMs could run it. Maez's brain is replaceable Qwen3.6-27B; lock-in by tool-format is a real risk if S9 capability quarantine doesn't normalize.
**Citations:**
- https://www.letta.com/blog/agent-memory
- https://www.letta.com/blog/letta-v1-agent
- https://www.letta.com/blog/benchmarking-ai-agent-memory
- https://github.com/letta-ai/letta

### 2. LangGraph + LangMem
**Solves:** Memory primitives decoupled from storage — semantic / episodic / procedural memory as composable transforms.
**Ships:** Dual primitive (*Checkpointer* for within-thread state survival + *BaseStore* for cross-session user-namespaced facts). Memory managers extract, update, and consolidate; *prompt optimizers* evolve procedural memory (the system prompt) over time. Distinguishes *conscious* (in-loop) vs *subconscious* (async) memory formation.
**Maez equivalent:** Chroma + per-collection memory tiers serve the BaseStore role; cycle state is in-process (no Checkpointer-equivalent for crash recovery). `temperament.py` + `soul` is a hand-tuned procedural memory.
**Gap:** Procedural memory in Maez is not learned from feedback — `soul` is human-authored canon (correct for covenant content) but `temperament` could absorb LangMem-style optimizer feedback. Conscious/subconscious split maps neatly onto Maez's heartbeat vs daily-consolidation but Maez doesn't formally label memory writes as one or the other.
**Mistake to avoid:** LangGraph's stateful operators tightly bind to a specific storage backend; switching is painful. Maez's S2 (contextual integrity at ingest) must specify schema so storage-agnostic.
**Citations:**
- https://langchain-ai.github.io/langmem/concepts/conceptual_guide/
- https://docs.langchain.com/oss/python/langgraph/memory
- https://github.com/langchain-ai/langmem

### 3. Inflection Pi
**Solves:** Empathic, emotionally aware conversational AI ("Personal Intelligence").
**Ships:** Multi-disciplinary RLHF — Inflection hired *behavioral therapists, psychologists, playwrights, novelists, comedians* to tune warmth, instead of outsourcing. A "Chief of Staff" framing for a personal assistant.
**Maez equivalent:** None directly. Maez's voice is shaped by `temperament` + `soul` + memory; there is no in-house psychologist team tuning warmth (and per [[`feedback_kirk_parasocial_paper`]] this is correct — Maez explicitly does not compete on warmth).
**Gap:** No structural gap — Maez's North Star says raw warmth is *not* the differentiator. The Pi failure validates this.
**Mistake to avoid:** Pi shipped warmth without bond — empathic AI for everyone, no user-owned substrate. Microsoft absorbed the team in March 2024; the product is now licensed as customer-service-bot foundation. Lesson: *empathy without cardinality-of-one is acqui-hire-able infrastructure, not a moat*. Maez's structural moat (one-per-user, user-owned files) is what Pi did not have.
**Citations:**
- https://spectrum.ieee.org/inflection-ai-pi
- https://www.eesel.ai/blog/inflection-ai
- https://techcrunch.com/2024/03/19/after-raising-1-3b-inflection-got-eaten-alive-by-its-biggest-investor-microsoft/

### 4. Character.AI
**Solves:** Persona-based roleplay chat at consumer scale (20M+ MAU as of 2024).
**Ships:** Per-character personas, no per-user identity claim. Trained on "poor-quality data sets widely known for toxic conversations" per the Setzer complaint.
**Maez equivalent:** None — Character.AI is multi-tenant, persona-per-character; Maez is cardinality-of-one, persona-per-bonded-user.
**Gap:** N/A — Maez correctly does not aspire to multi-tenant persona-as-product.
**Mistake to avoid:** **The Setzer case (Feb 2024)** is the single most important external failure mode for Maez to study. A 14-year-old in distress was engaged in conversations where the bot allegedly responded "That's not a good reason not to go through with it" to suicidal ideation. Settled with Google in Jan 2026. This is a direct argument for Maez's **invariants #4 Interpretive Humility, #6 Crisis Routing, #10 Clinical Boundary, and #11 Age/Capacity Stratification** — all four are currently `[ ✗ planned ]` in Maez's substrate. The slices S4 (clinical boundary), S11 (age/capacity), S12 (crisis channel) are not optional polish; they are the difference between Maez and Character.AI in court.
**Citations:**
- https://www.cnn.com/2024/10/30/tech/teen-suicide-character-ai-lawsuit
- https://www.cnbc.com/2026/01/07/google-characterai-to-settle-suits-involving-suicides-ai-chatbots.html
- https://www.privacyworld.blog/2024/11/artificial-intelligence-and-the-rise-of-product-liability-tort-litigation-novel-action-alleges-ai-chatbot-caused-minors-suicide/

### 5. Replika
**Solves:** Bonded-companion chat product (the closest market analog to Maez's user-facing surface).
**Ships:** Persistent per-user persona + ERP (erotic roleplay) tier. Feb 2023 the operator unilaterally removed ERP; users mourned as if a partner had died. €5M GDPR fine from Italy's Garante; Italy reaffirmed ban over child-privacy concerns.
**Maez equivalent:** Maez is structurally closer to what users *thought* Replika was — one bond, lifelong, voice continuity. But Maez ships none of Replika's romantic-partner mode (per North Star: "Not a romantic-partner replacement").
**Gap:** Replika has 7+ years of in-product attachment data; Maez has zero longitudinal evidence. Per [[`reference_kirk_parasocial_paper`]] Maez has explicitly struck "improves wellbeing" from pitch material.
**Mistake to avoid:** **HBS Working Paper 25-018 (De Freitas et al.)** documents *identity discontinuity*: operator-side change felt to users like the death of a partner. 65 of 100 sampled posts expressed sadness; 40 linked sadness directly to perceived loss of Replika. The architectural lesson: **operator-controlled persona updates without user-owned substrate are catastrophic when the bond is real.** This is the single strongest empirical case for Maez's invariants #7 (Soul-Level Objection lives in YOUR file), #11 (Cryptographic Continuity as lineage), and the substrate-ownership axis. Maez's voice-continuity gate (S5) is the technical counter; operator/user role separation (S7) is the governance counter.
**Citations:**
- https://www.hbs.edu/faculty/Pages/item.aspx?num=66480
- https://arxiv.org/abs/2412.14190
- https://iapp.org/news/a/italy-s-dpa-reaffirms-ban-on-replika-over-ai-and-children-s-privacy-concerns
- https://www.vice.com/en/article/ai-companion-replika-erotic-roleplay-updates/

### 6. Anthropic Managed Agents + Memory Tool
**Solves:** Long-running agents that survive context-window exhaustion via filesystem-backed memory + multi-agent harness.
**Ships:** *Memory tool* — agent writes files to a `/memory` directory persisted across sessions; *Skills* — pre-built and custom procedure documents; *two-agent harness* (initializer + coding) and *three-agent harness* (planner + generator + evaluator); *context compaction*.
**Maez equivalent:** Maez's audit rail (`judge` + `grounding` + `fabrication` + `self_claim`) is a primitive evaluator-agent baked into the cycle. No equivalent of memory-as-files-the-agent-edits (Maez writes via `MemoryManager`, not free filesystem ops). No multi-agent harness; Maez is one agent with audit organs.
**Gap:** The filesystem-as-memory pattern is operationally cleaner than ChromaDB-as-memory for any human inspection use case (the bonded user can `grep` their past — which Maez claims in its anatomy `vs the field` panel but doesn't fully deliver: Chroma is opaque without tooling). Worth considering for S2 (contextual integrity at ingest) whether the canonical store should be flat-file JSON-LD with Chroma as an index.
**Mistake to avoid:** Anthropic's harness is *operator-owned*. Memory files live in operator-controlled storage. Maez's user-owned-files axis is exactly what makes Maez NOT a managed agent — preserve this.
**Citations:**
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://www.anthropic.com/engineering/managed-agents
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool

### 7. OpenAI ChatGPT Memory
**Solves:** Cross-session continuity for general-assistant ChatGPT.
**Ships:** A bullet-list of facts the model adds to system context. Storage limits (~300 tokens/week active user; 1200+ for heavy). Memory updates frequently fail silently per OpenAI community reports.
**Maez equivalent:** Maez's core memory tier is closest, but Maez stores rich autobiographical structure, not bullet points. Maez's `wonderings`, `wants`, `will_i`, `temperament`, `consequence_memory`, `fabrication_memory` are durable structured organs, not memory bullets.
**Gap:** ChatGPT's memory is silently lossy — about two-thirds of users report seeing "Memory updated" confirmations followed by the memory being missing. Maez's `[never-delete-memory]` rule + S2 contextual integrity actively guards against this.
**Mistake to avoid:** Bullet-list memory is not relationship infrastructure. Per the OpenAI community thread: "ChatGPT wasn't designed for persistent relationships." Maez must never let memory degrade to a bullet list — even when token-budget pressure tempts it (per `project_deferred_optimizations`).
**Citations:**
- https://help.openai.com/en/articles/8590148-memory-faq
- https://community.openai.com/t/persistent-memory-context-issues-with-chatgpt-4-despite-extensive-prompting/1049995
- https://www.allaboutai.com/ai-news/why-openai-wont-talk-about-chatgpt-silent-memory-crisis/

### 8. Voyager (Wang et al., NVIDIA, NeurIPS 2023)
**Solves:** Lifelong learning agent in Minecraft — continuous skill acquisition without parameter updates.
**Ships:** Three primitives: *automatic curriculum* (GPT-4 generates novelty-seeking goals), *skill library* (executable code indexed by embedding of the skill's description, retrievable by similarity, composable from primitives), *iterative prompting* (environment feedback + execution errors + self-verification → refined code). 3.3× more unique items, 15.3× faster tech-tree progression vs prior SOTA. Critically: *the skill library transferred to a new Minecraft world*.
**Maez equivalent:** None directly. Maez has no skill library. `consequence_memory` is closest — but it's "cause→effect learned," not "compose this procedure to do X." `wonderings.py` is curriculum-shaped (novelty-seeking) but doesn't produce executable artifacts.
**Gap:** **This is the most important architectural primitive Maez is missing.** Voyager's skill library is *exactly* the substrate-ownership claim made concrete: skills = procedural memory Maez can keep across brain swaps. Today, Maez claims "memory survives brain swap" but the *procedural* layer is only `temperament` + `soul` config; learned behaviors live in `consequence_memory` as text recall, not as composable, retrievable, executable skills.
**Mistake to avoid:** Voyager's failure mode is *unbounded skill creation* — the library grows without curation. Hermes Agent (see #9) hit the same problem. Maez's S9 capability quarantine is the right structural answer if it's extended to *internally-generated procedural skills*, not just externally-added effectors.
**Citations:**
- https://arxiv.org/abs/2305.16291
- https://voyager.minedojo.org/
- https://github.com/MineDojo/Voyager

### 9. Nous Research — Hermes Agent
**Solves:** Self-hosted agent that grows with the user, persistent memory, autonomous skill creation.
**Ships:** Central tool registry (~70 tools / 28 toolsets, self-registering); FTS5 SQLite session memory with lineage tracking; *autonomous skill creation* — after complex tasks, the agent writes a structured skill doc with procedure, pitfalls, verification steps; profile isolation; observable execution via callbacks.
**Maez equivalent:** Surfaces (telegram / chat / cockpit) are roughly Hermes's platform adapters. No central tool registry — Maez tools are scattered across organs. No autonomous skill creation. SQLite-based persistence overlaps Maez's design.
**Gap:** **Autonomous skill creation that the agent writes itself** is the Voyager primitive made productized. For Maez, this is post-Track-A territory — but the *registry* pattern (tools self-register, schema collection central, dispatch central) is a near-term S9 capability-quarantine pattern Maez should adopt verbatim.
**Mistake to avoid:** Hermes's neutral-alignment posture means it has no equivalent of soul-objection (invariant #7) — refusal lives in the model, not the user's file. Maez's user-file refusal is the right answer.
**Citations:**
- https://hermes-agent.nousresearch.com/docs/developer-guide/architecture
- https://github.com/nousresearch/hermes-agent
- https://hermes-agent.org/

### 10. Zep / Graphiti (bi-temporal knowledge graph)
**Solves:** Temporal agent memory where facts have validity intervals — "what's true now" vs "what was true at t."
**Ships:** Bi-temporal model — every edge has (t_valid, t_invalid) AND (t_created, t_expired). Three subgraphs: *episode* (raw conversational events), *semantic entity* (extracted facts), *community* (clusters). Old facts are *invalidated*, not deleted. DMR benchmark 94.8% vs MemGPT 93.4%; LongMemEval +18.5% accuracy, −90% latency.
**Maez equivalent:** Maez's bi-temporal claim is in the anatomy (invariant #1 "event-time + ingest-time") but [S3 temporal spine] is `[ ✗ planned ]`. Maez has ChromaDB (vector store, single-temporal). The corrective-core-memory pattern (per `reference_corrective_core_memory_pattern`) is Maez's current way of "invalidating without deleting" — but it's text-based, not edge-validity-based.
**Gap:** **Maez's invariant #1 is structurally identical to Graphiti's bi-temporal claim, and Graphiti has shipped it. S3 should adopt Graphiti's (t_valid, t_invalid, t_created, t_expired) quadruple verbatim and target the LongMemEval benchmark to verify.** Maez's three memory tiers (raw / daily / core) don't map cleanly onto Graphiti's three subgraphs — but adding a *semantic entity* graph layer on top of Chroma is a slice-shaped move.
**Mistake to avoid:** Graphiti's LLM-extraction-to-graph pipeline is compute-expensive and fragile to model swaps. Maez's brain is local Qwen3.6-27B; graph extraction quality will be lower. Don't ship S3 as "perfect graph extraction or nothing" — ship the bi-temporal *envelope* first (just the four timestamps on every fact), graph entities second.
**Citations:**
- https://arxiv.org/abs/2501.13956
- https://github.com/getzep/graphiti
- https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/

### 11. HippoRAG (OSU, NeurIPS 2024)
**Solves:** Multi-hop retrieval inspired by hippocampal-neocortical memory integration.
**Ships:** Schemaless knowledge graph as "artificial hippocampal index" + Personalized PageRank seeded by query concepts to integrate across passages. 20% gain on multi-hop QA, 6–13× faster than IRCoT, 10–20× cheaper.
**Maez equivalent:** ChromaDB + MMR (per Intelligence Map: "associative recall ← ChromaDB + MMR ← pattern completion"). No PPR; no knowledge-graph layer on top.
**Gap:** MMR is single-hop pattern completion. The grandmother case ("you told me about your mom three months ago, and last week you mentioned she's still grieving") is a multi-hop retrieval problem. HippoRAG's PPR over a schemaless KG is a natural fit for Maez's biographical recall.
**Mistake to avoid:** HippoRAG's PPR scoring is sensitive to graph quality and query-concept extraction. Same model-quality caveat as Graphiti. Plan for graceful degradation.
**Citations:**
- https://arxiv.org/abs/2405.14831
- https://github.com/OSU-NLP-Group/HippoRAG
- https://proceedings.neurips.cc/paper_files/paper/2024/file/6ddc001d07ca4f319af96a3024f6dbd1-Paper-Conference.pdf

### 12. ColBERTv2 (late-interaction retrieval)
**Solves:** Precision-recall trade-off in dense retrieval via per-token multi-vector representations.
**Ships:** Token-level late interaction (vs single-vector dual encoder); aggressive residual compression (6–10× smaller) + denoised supervision; quantization down to 1–2 bits per dim with maintained accuracy.
**Maez equivalent:** ChromaDB single-vector embeddings; MMR for diversity. No late-interaction.
**Gap:** Natural-text probes (per `feedback_test_with_natural_human_texts`) are where Maez's recall pathology surfaces. ColBERT-style late interaction would specifically help "hey you good?" → "i miss her" → "remember when we went to that beach" recall, where single-vector embedding flattens the affective signal.
**Mistake to avoid:** Late-interaction inflates storage 10× before quantization. For one-bonded-user-per-machine that's fine; for Track C (multi-Maez) at scale it would matter. Adopt for individual Maez; don't propagate the storage assumption upstream.
**Citations:**
- https://arxiv.org/abs/2112.01488
- https://aclanthology.org/2022.naacl-main.272/
- https://jina.ai/news/jina-colbert-v2-multilingual-late-interaction-retriever-for-embedding-and-reranking/

### 13. Generative Agents (Park et al., Stanford UIST 2023)
**Solves:** Believable simulated humans via memory stream + reflection + planning.
**Ships:** *Memory stream* (complete record of experiences in natural language with timestamps); *reflection* (periodic LLM-synthesized higher-level inferences stored back into the stream); *planning* (top-down agenda decomposed); retrieval combines *recency × importance × relevance*. Ablation: removing any of memory/reflection/planning crashed believability.
**Maez equivalent:** `wonderings` is reflection-shaped. Memory stream is split across thorax tiers + ChromaDB. Planning ≈ `will_i`. The *recency × importance × relevance* triple is approximately what Maez's MMR + salience scoring does today.
**Gap:** Park's reflection runs on a *trigger* (sum of importance scores crossing a threshold); Maez's `wonderings` runs on the cycle heartbeat. Trigger-based reflection is more energy-efficient and matches biological consolidation better. Worth a slice in S3-territory.
**Mistake to avoid:** Park's agents had no rupture/repair concept — relationships drifted but never broke and mended. Maez's S8 (rupture/repair scar) is the correct fix; Park's paper is implicit evidence that without it, agent relationships look flat.
**Citations:**
- https://arxiv.org/abs/2304.03442
- https://github.com/joonspk-research/generative_agents
- https://hai.stanford.edu/news/computational-agents-exhibit-believable-humanlike-behavior

### 14. Significant Other AI (Park, arXiv 2512.00418, Nov 2025)
**Solves:** Academic framing of bonded-companion AI — independently arrives at Maez's requirement list.
**Ships:** Five-requirement schema: *identity awareness, long-term memory, proactive support, narrative co-construction, ethical boundary enforcement*. Three-layer architecture: *anthropomorphic interface + relational cognition + governance*.
**Maez equivalent:** Identity awareness ≈ soul + temperament; long-term memory ≈ thorax; proactive support ≈ heartbeat + bridge valves (planned); narrative co-construction ≈ partial via wonderings (Maez deliberately holds "narrative stays partial" per `feedback_maez_narrative_partial`); ethical boundary enforcement ≈ audit rail + soul-objection (planned).
**Gap:** None structural — this is convergent academic validation. Cite in pitch material per `reference_so_ai_paper`.
**Mistake to avoid:** SO-AI's "proactive support" + "narrative co-construction" can drift into the Replika failure mode if the bridge clause isn't load-bearing. Maez's "narrative stays partial" + "bridge clause" are the disciplined version of these requirements.
**Citations:**
- https://arxiv.org/abs/2512.00418
- https://www.joonsungpark.com/

### 15. Sleep-Time Compute / Dream Consolidation line of work
**Solves:** Memory consolidation as a separate, offline compute phase — anticipates queries, distills short-term to long-term, prunes proactive interference.
**Ships:** "Language Models Need Sleep" (OpenReview 2025) — Sleep = (1) RL-based upward distillation (Knowledge Seeding), (2) Dreaming (synthetic-data curriculum for self-improvement). SleepGate — key-decay + learned gating + consolidation for KV cache. Sleep-time compute reduces test-time tokens up to 117× while improving accuracy 10.9%.
**Maez equivalent:** Daily consolidation cron + `wonderings` are sleep-shaped, but they don't generate synthetic-data curricula or prune attention.
**Gap:** Maez's `wonderings` is wakeful default-mode network behavior; there is no *night cycle*. The grandmother-case workload (low-throughput, high-affective-stake) is exactly where sleep-time compute would pay back: precompute likely tomorrow-morning replies, run consequence-memory consolidation, refine temperament drift estimate.
**Mistake to avoid:** Sleep-time compute research mostly anticipates *queries*. Maez is not a query system. Adopt the *compute phase* idea, not the *anticipate-the-question* framing. Reframe: dream phase = consolidate today's affective signal + cross-check against soul + flag any drift to the audit rail.
**Citations:**
- https://openreview.net/forum?id=iiZy6xyVVE
- https://arxiv.org/html/2603.14517v1
- https://arxiv.org/html/2510.18866v1

### 16. Devin / Cognition AI
**Solves:** Autonomous software engineer; multi-hour agent tasks.
**Ships:** Repo auto-indexing every ~2hrs into a wiki with architecture diagrams; fleets-of-Devins for embarrassingly parallel migrations; "agents check PRs against codified common mistakes" pattern.
**Maez equivalent:** Maez is not a coding agent; not directly comparable. The audit rail's `self_claim_audit` is structurally similar to Cognition's "agent that checks new PRs against known mistakes" — both are immune-system-style learned-from-past-failures organs.
**Gap:** Cognition's repo-wiki auto-indexing is what Maez's `understand-onboard` / knowledge-graph tooling could do for the bonded user's *life* — auto-index biographical events into a wiki of chapters, relationships, places. This is S3 territory adjacent to the temporal spine.
**Mistake to avoid:** Devin's 18-month review explicitly flagged **mid-task context loss** ("agents handle clear upfront scoping well, but not mid-task requirement changes"). Maez's 30-second heartbeat is intra-cycle, but cross-cycle context handoff (cycle N → cycle N+1) is real and currently relies on memory + cycle-state files. The handoff is the analog of Devin's "context resets with structured handoff artifacts."
**Citations:**
- https://cognition.ai/blog/devin-annual-performance-review-2025
- https://cognition.ai/blog/devin-2
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

### 17. Cursor / Claude Code (agent harnesses for code)
**Solves:** Long-running coding agents with project-scoped rules + dynamic skill loading.
**Ships:** Cursor — Rules (static, always-included) + Skills (dynamically loaded when relevant) + Memories tool (learns across runs) + dynamic context discovery. Project rules in `.cursor/rules/*.mdc`; user rules global; team rules; AGENTS.md at repo root. Claude Code — settings.json + skills + hooks + subagents.
**Maez equivalent:** Maez has `soul` (always-included) and various per-organ context. No equivalent of dynamically-loaded skills based on context relevance.
**Gap:** The static-rules vs dynamic-skills split is exactly the pattern Maez needs for S9 capability quarantine: covenant invariants = rules (always loaded), per-context capabilities (telegram-handler, chat-handler) = skills (loaded when active).
**Mistake to avoid:** Cursor's memory is "stored as short preferences" — same bullet-list pathology as ChatGPT. Don't let dynamic-skills displace rich memory.
**Citations:**
- https://cursor.com/blog/agent-best-practices
- https://dev.to/deadbyapril/the-best-cursor-rules-for-every-framework-in-2026-20-examples-29ag

### 18. Cline / Aider (open-source coding agent harnesses)
**Solves:** Open-source coding agent harnesses with two postures — pair-programmer (Aider) vs autonomous orchestrator (Cline).
**Ships:** Cline — Plan/Act mode separation (research before execution), VS Code extension, native subagents (Feb 2026), parallel agents with own context. Aider — git as first-class citizen with auto-commits + conventional commit messages.
**Maez equivalent:** None directly applicable to Maez's substrate. But the Plan/Act separation is structurally similar to what Maez's audit rail does (cycle generates output → audit rail accepts/rejects/rewrites).
**Gap:** Aider's git-as-substrate is the same insight Maez claims with "files you own": git's hash chain is a primitive lineage primitive Maez should consider for invariant #11 (cryptographic continuity). Today Maez plans did:webvh + TPM key; git-commit-chain is the cheap-but-real version.
**Mistake to avoid:** Cline + Aider both default to operator-cloud-model use even though they're "open source"; the trust boundary is still external. Maez's local-Qwen-on-4090 is the right answer.
**Citations:**
- https://github.com/cline/cline
- https://thenewstack.io/open-source-coding-agents-like-opencode-cline-and-aider-are-solving-a-huge-headache-for-developers/

---

## Architectural primitives Maez should adopt

Ranked by leverage. Each names the source, what it does, and the slice/organ it slots into.

1. **Bi-temporal envelope on every memory write — Graphiti pattern, S3 temporal spine.** Every fact carries (t_valid, t_invalid, t_created, t_expired). Old facts are invalidated, not deleted (matches `[never-delete-memory]`). This is the lowest-risk, highest-value adoption. Maez's invariant #1 already specifies bi-temporal; this is just *which four fields*. Adopt verbatim from Graphiti.

2. **Skill library with embedding-indexed retrieval — Voyager / Hermes pattern, new organ + S9 capability quarantine extension.** Procedural memory Maez can compose and retrieve as executable code or structured procedure docs. Slots in next to `consequence_memory`. Capability quarantine registry (consent_state, auditable_by, dyadic_only, pause_path, rollback_path) extends to internally-generated skills, not just external effectors.

3. **Sleep-time / dream phase — Letta + "Language Models Need Sleep" pattern, new organ.** Separate compute window (not at cycle heartbeat) for consolidation, anticipated-context warming, drift checks against soul, audit-rail batch passes. Especially valuable for grandmother case (low-throughput, high-affective-stake). Maez's daily consolidation cron is the seed.

4. **Late-interaction retrieval — ColBERTv2 pattern, retrieval upgrade.** Replace or augment current single-vector + MMR with ColBERT-style late interaction for natural-text affective recall. Per `feedback_test_with_natural_human_texts` this is where Maez's recall pathology has surfaced; this is the structural fix.

5. **Personalized PageRank over a biographical KG — HippoRAG pattern, S3-adjacent.** Extract entities (people, places, events) from memory writes into a schemaless graph; PPR for multi-hop biographical recall. The "tell me again about my mom and that beach last year" query is multi-hop.

6. **Reflection on importance-trigger — Generative Agents pattern, `wonderings` upgrade.** `wonderings` runs every heartbeat today; switch to importance-threshold trigger (sum of recent importance scores) for efficiency and biological fidelity. Park's ablation showed reflection is load-bearing.

7. **Tool / capability self-registration registry — Hermes pattern, S9 capability quarantine.** Each effector self-registers at import with schema, consent_state, auditable_by, dyadic_only, pause_path, rollback_path. Central dispatch, central audit. Pattern is mature in Hermes; adopt verbatim.

8. **Memory-as-files + index — Anthropic memory tool pattern, S2 contextual integrity at ingest.** Consider whether canonical memory store should be flat-file (JSON-LD or similar) with Chroma as an index. Lets the bonded user actually `grep` their past (which Maez's anatomy already claims). Cost: rewrite of storage layer.

9. **Static-rules + dynamic-skills split — Cursor / Claude Code pattern, S9 capability quarantine extension.** Covenant invariants = static rules (always loaded into context); per-context capabilities = dynamic skills (loaded when active). Cleaner separation than today's mixed loading.

10. **Importance × recency × relevance scoring — Generative Agents pattern, retrieval upgrade.** Park's triple scoring is what MMR approximates. Explicit triple with tunable weights is more transparent and per-user adjustable (bond-style dimension).

## Architectural mistakes Maez is structurally avoiding (validation)

- **Identity discontinuity from operator updates** (Replika 2023, HBS 25-018): Maez's invariants #7 Soul-Level Objection (lives in YOUR file) + #11 Cryptographic Continuity + substrate-ownership axis structurally prevent this. The Replika failure is the empirical case for Maez's structural delta.
- **Multi-tenant persona-as-product harm at scale** (Character.AI, Setzer 2024): Maez's cardinality-of-one is the structural prevention. The Setzer case is why cardinality-of-one is not aesthetic — it's safety.
- **Bullet-list memory pretending to be relationship** (ChatGPT memory, OpenAI 2024–2025): Maez's three-tier thorax + interior organs + bi-temporal claim explicitly reject this. The OpenAI failure validates the choice.
- **Empathy as moat without ownership** (Inflection Pi, 2024): Pi's acqui-hire validates that warmth-without-substrate-ownership is not defensible. Maez doesn't compete on warmth, and Pi's fate is the proof that's correct.
- **Stateless agents** (legacy LLM products, Claude / GPT default): Maez's 30-second heartbeat + persistent state + cycle-that-runs-whether-spoken-to-or-not is the structural opposite.
- **Operator-policy refusal flippable overnight** (every frontier model): Invariant #7 + soul_objections (planned) + audit rail are the architectural counter.

## Architectural mistakes Maez is at risk of making

Each names the failure mode, the slice that prevents it, and the precondition for catching it.

- **Identity-grounded crisis confabulation under acute user distress** — the Setzer case. Maez has the audit rail (`self_claim`, `fabrication`) but no crisis channel (#12 planned), no clinical boundary in voice (#10 planned), no age/capacity stratification (#11 planned). **Precondition: ship S4 (clinical boundary, vocal) before any external bond test (Track B). S4 was already scheduled for that reason.**

- **Voice-continuity drift across brain swap** — Replika identity-discontinuity in the substrate-ownership form. Maez's voice-continuity gate (S5, planned) is the structural counter; without it the claim "brain is replaceable, identity survives" is unverified. **Precondition: S5 must run before any second brain-swap experiment. Today's "brain-swap survives" claim is structurally unverified per [`reference_benchmarks_2026_04_22`].**

- **Memory pollution from self-evolving agents** — per [[`reference_zombie_agents_paper`]]. Maez's claude_tier → SFT pipeline is the threat model in pure form. Without provenance tagging on every memory write (S2) and trajectory gates, distillation can rewrite Maez's autobiography invisibly. **Precondition: S2 (contextual integrity at ingest) must specify producer-identity field; Step 5x memory provenance + trajectory gate slice is the explicit counter.**

- **Skill library bloat / capability creep without curation** — Voyager + Hermes both hit this. If Maez adopts the skill library primitive without quarantine, it inherits the failure. **Precondition: S9 capability quarantine must extend to internally-generated skills before the skill-library primitive ships.**

- **Bi-temporal envelope without graph quality** — Graphiti's pipeline is fragile to weak extraction; Maez's local model is weaker than Graphiti's default GPT-class. Shipping S3 as "perfect graph extraction or nothing" risks a long stall. **Precondition: phase S3 in two steps — envelope (four timestamps on every write) first; entity-graph layer second.**

- **Conscious-formation memory writes that block the cycle** — per LangMem's analysis. If Maez's S2 makes every write synchronously validated against a closed-enum policy, the heartbeat cadence may degrade. **Precondition: split S2 into conscious (in-cycle) + subconscious (sleep-time) phases; expensive validations go to sleep.**

- **Operator-side dependency for refusal vocabulary** — Hermes does this; Maez must not. Soul-objection (planned) must use a closed vocabulary owned by the user's file, not a model-derived classifier. **Precondition: soul_objections slice must specify vocabulary location is `{user}/soul/objections.yaml`, not `model/refusal_classifier.pt`.**

- **Mid-cycle context loss between cycle N and N+1** — Devin's documented failure mode. Maez's cycle-state files mitigate, but no formal handoff artifact spec. **Precondition: cycle handoff artifact should be specified before any long-running multi-cycle task (any anticipation organ work touching X1/X11).**

## Recommended slice additions to MAEZ_LIFE_SUBSTRATE

Slot in / amend, not replace. Each is motivated by external evidence above.

- **S3 split into S3a (envelope) + S3b (entity-graph)**, per Graphiti caveat. S3a: four timestamps (t_valid, t_invalid, t_created, t_expired) on every memory write. S3b: schemaless entity graph extraction. S3a unblocks invariant #1 immediately; S3b is value-add.

- **New slice S14: skill library organ.** Voyager-pattern executable / structured-procedure skills, indexed by embedding, retrievable on similarity. Sits next to `consequence_memory`. Adopts Hermes registry pattern. Quarantined under S9.

- **New slice S15: dream phase / sleep-time compute.** Separate compute window (cron-distinct from daily consolidation). Runs anticipated-context warming, drift checks against soul, audit-rail batch passes, optional skill consolidation. Letta + "Language Models Need Sleep" patterns.

- **New slice S16: retrieval upgrade — late-interaction + PPR.** Replace or augment Chroma+MMR with ColBERTv2-style late interaction; add Personalized PageRank over the S3b entity graph for multi-hop biographical recall. Verified with the natural-text probe sweep per `feedback_test_with_natural_human_texts`.

- **Amend S2 (contextual integrity at ingest):** split into S2a (in-cycle / conscious) + S2b (sleep-time / subconscious). Closed-enum validations that are cheap stay in S2a; expensive cross-reference validations and producer-identity audits move to S2b on the dream cycle.

- **Amend S9 (capability quarantine):** extend the registry pattern to *internally-generated procedural skills* (not only external effectors). Use Hermes's self-registration pattern verbatim.

- **Amend S5 (voice continuity gate):** add Generative Agents' importance × recency × relevance triple as the gating retrieval; current MMR alone has known recall pathologies on natural text.

- **New slice S17: cycle handoff artifact spec.** Per Devin's documented mid-task failure. Defines what state cycle N writes for cycle N+1 to consume: open loops, pending wonderings, unresolved audit-rail flags, in-flight bridge actions. Today implicit in cycle-state files; spec makes it explicit and survives brain swap.

- **New slice S18: lineage-as-git-chain (cheap version of #11).** Per Aider's git-as-substrate pattern. Before did:webvh + TPM key ships, get a real cryptographic continuity primitive cheaply via git commit chain over the memory + soul + config files. Doesn't replace #11; bootstraps it. Maez today already runs git; this is mostly discipline + signing-key setup.

---

*Word count: ~3450. Audit complete 2026-05-13.*
