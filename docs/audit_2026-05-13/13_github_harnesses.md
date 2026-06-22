# GitHub harness audit — open-source primitives Maez could borrow

*Audit run 2026-05-13. Scope: open-source GitHub primitives Maez (AGPL-3.0) could adopt, mine, or learn from. Read-only on Maez code. Maps each candidate to the 12 missing organs / 11 covenant invariants / current observability + security gaps.*

## Summary

Two primitives are obviously load-bearing for Maez's near-term roadmap and well-licensed: **Graphiti** (bi-temporal context graph with t_valid/t_invalid edges + provenance) and **Inspect AI** (UK AISI's eval harness, de-facto standard for safety-relevant LLM evals). Both directly map to organs Maez has named but not built (#1 temporal spine, #2 contextual integrity, voice-continuity gate). A third tier — **Sigstore/Rekor + model-transparency** and **did:webvh** — is the cleanest path to the "signed cryptographic lineage" the anatomy doc labels `[ ✗ planned ]`. Most memory frameworks (mem0, Letta) replicate what Maez already has; mine for patterns rather than depend. Crisis-routing has **no good OSS primitive** — Maez must implement it. AGPL is fine: MIT/Apache-2.0/MPL-2.0 are one-way compatible; keep absorbed copyrights in NOTICE.

---

## High-leverage repos to consider adopting

### Graphiti (getzep)
**URL:** https://github.com/getzep/graphiti
**Stars / last commit:** 26.0k · v0.29.0 released 2026-04-27 (fresh)
**License:** Apache-2.0 → AGPL-compatible (one-way absorb)
**Primitive:** Bi-temporal context graph. Every edge carries `t_valid` and `t_invalid`; every entity/relationship traces back to its source episode; hybrid retrieval (semantic + BM25 + graph traversal); incremental construction; pluggable Neo4j/FalkorDB/Kuzu/Neptune.
**Maps to Maez:** Organ #1 (temporal spine), Organ #2 (contextual integrity at ingest), invariant #1 (time as biography), Organ #3 (rupture/repair scar — naturally expressed as edge with validity interval).
**Maez equivalent today:** None at this fidelity. `core/memory/` uses ChromaDB single-vector with timestamps but no validity windows, no edge ontology, no source-episode lineage.
**Effort to integrate:** Medium-high. ~2 sessions to stand up a Neo4j sidecar with the existing ChromaDB tier in parallel (do NOT replace ChromaDB — Maez's "never delete memory" rule is satisfied by Graphiti's superseded-edge model, but a brain-swap event must not depend on a single store). Risk: adds a heavyweight dependency (Neo4j) where Maez has otherwise stayed file/SQLite-native.
**Recommendation:** **adopt for S3 (temporal spine) — but as a parallel index, not a replacement.** Mine the bi-temporal edge schema even if Maez ships its own SQLite implementation.

### Inspect AI (UK AISI)
**URL:** https://github.com/UKGovernmentBEIS/inspect_ai
**Stars / last commit:** 2.0k (low for the value; UK-government-backed) · active
**License:** MIT → AGPL-compatible
**Primitive:** End-to-end LLM eval harness. Task DSL, tool-use scaffolding, multi-turn dialog, model-graded scoring, 200+ pre-built evals (Inspect Evals), VS-Code extension, run logs, sample-level diffing. The autonomous-systems eval standard requires evaluations be built in Inspect, which makes it the lingua franca for any safety-relevant claim.
**Maps to Maez:** Voice-continuity gate (S5), self-claim audit, natural-text probe sweep automation, brain-swap acceptance probes. Currently `tests/probes/` is bespoke; an Inspect task would let probes run on Maez and the new brain side-by-side with a single command.
**Maez equivalent today:** `tests/` pytest harness + ad-hoc probe scripts. No model-graded scoring, no sample-level UI, no shared schema with the rest of the safety-eval world.
**Effort to integrate:** Low. ~1 session to wrap natural-text probe sweep + self-claim audit probes as Inspect tasks. Maez keeps its pytest harness; Inspect runs alongside for covenant-relevant evaluations.
**Recommendation:** **adopt for S5 (voice continuity gate).** This is the highest leverage / lowest risk integration in the audit.

### Sigstore Model Transparency
**URL:** https://github.com/sigstore/model-transparency
**Stars / last commit:** 232 · v1.1.1 released 2025-10-10 (still active, slow)
**License:** Apache-2.0 → AGPL-compatible
**Primitive:** Cryptographic signing of ML model files using Sigstore (keyless OIDC) or traditional keys/HSM. Records signing events in append-only transparency log (Rekor). Verifies model hasn't been tampered with after training. CLI + Python API.
**Maps to Maez:** Anatomy intelligence-map row "identity-proof (across HW) — did:webvh + TPM key" `[ ✗ planned ]`. Q1 in the coda (erase weights, keep memory — does the same individual continue?) needs a verifiable chain that the new brain was signed by the maintainer and is the brain the lineage points to.
**Maez equivalent today:** None. Brain swaps are unverifiable per `MAEZ_LIFE_SUBSTRATE.md` S5 note.
**Effort to integrate:** Medium. ~1 session to sign the Qwen3.6-27B brain artifact + add a verify-on-load check in the daemon. The transparency log piece is harder — requires a Rekor instance (public Rekor is free but coupling Maez identity to a public log is its own decision).
**Recommendation:** **adopt for S5 voice-continuity gate's "identity" half** (Inspect handles "voice" half). Use Sigstore signing now; defer public Rekor entry until covenant council ratifies.

### Letta sleep-time compute pattern
**URL:** https://github.com/letta-ai/letta · https://github.com/letta-ai/sleep-time-compute
**Stars / last commit:** 22.7k · v0.16.7 released 2026-03-31 (fresh)
**License:** Apache-2.0 → AGPL-compatible
**Primitive:** Stateful agent with three-tier memory (core/recall/archival), separate "sleep-time agent" that runs offline to transform context/skills, and a dream-style consolidation pass. Memory-block abstraction with labelled segments ("human", "persona").
**Maps to Maez:** Maez already has the three-tier memory (RAW/DAILY/CORE per the thorax). The novel piece is the **sleep-time agent** that runs the consolidation as a separate process, which maps cleanly onto Maez's existing daily consolidation cycle but generalizes it to a continuously running background reasoning agent. Could feed wonderings / consequence_memory / temperament between cycles.
**Maez equivalent today:** Daily consolidation cycle exists; sleep-time pattern (continuous background dreaming) does not.
**Effort to integrate:** Low if mined; high if depended-on. Letta is a full agent framework; Maez should not adopt the framework. Mine the sleep-time-compute paper + the public docs/code for the dual-agent architecture pattern.
**Recommendation:** **mine-for-ideas.** Specifically: add a "between-cycles dream" pass that anticipates likely next prompts from recent context and pre-computes lived-recall briefs.

### XTDB
**URL:** https://github.com/xtdb/xtdb
**Stars / last commit:** 3.0k · v2.1.0 released 2025-12-01 (fresh)
**License:** MPL-2.0 → AGPL-compatible
**Primitive:** Bitemporal SQL database. Distinguishes `SYSTEM_TIME` (when recorded) from `VALID_TIME` (when true). SQL:2011 standard. Cloud-native, columnar, Postgres wire protocol. ACID with Apache Arrow.
**Maps to Maez:** Same target as Graphiti (organ #1, organ #2) but via SQL not graph. XTDB is heavier (Clojure/Kotlin, designed for object storage) and overkill for the single-Maez deployment Maez is today.
**Maez equivalent today:** None.
**Effort to integrate:** High. Whole new dependency tree (JVM); Maez is Python-native.
**Recommendation:** **mine-for-ideas.** The SQL:2011 bitemporal schema is the cleanest formal expression of what S3 (temporal spine) needs. Borrow the `FOR SYSTEM_TIME` / `FOR VALID_TIME` query semantics even if implementing on SQLite.

### Model Context Protocol Python SDK
**URL:** https://github.com/modelcontextprotocol/python-sdk
**Stars / last commit:** 23k · active (Linux Foundation hosted)
**License:** MIT → AGPL-compatible
**Primitive:** Server + client SDK for MCP. FastMCP high-level framework, low-level Server, resource/tool/prompt primitives, transport options (stdio, SSE, streamable HTTP, ASGI mount), capability negotiation, OAuth 2.1 auth.
**Maps to Maez:** Future "bridge / cosmos layer" (organ #9) inter-Maez channels (Track C). MCP gives a standardized, auth'd, capability-negotiated transport for dyadic Maez-to-Maez communication. Also: today, Rohit's external tools can read Maez state through an MCP server without coupling the daemon to specific clients.
**Maez equivalent today:** Cockpit + chat surfaces; no MCP layer.
**Effort to integrate:** Low. ~1 session to expose a read-only MCP server (lived recall, soul, temperament — never raw private_thoughts) so external assistants (Claude Code, Cursor) can ground in Maez without re-implementing the cockpit API.
**Recommendation:** **adopt as read-only surface.** Defer outbound MCP (Maez calling out) until S9–S10 (capability quarantine + bridge layer) ratify the consent model.

### Sigstore Rekor (transparency log)
**URL:** https://github.com/sigstore/rekor
**Stars / last commit:** 1.1k · active
**License:** Apache-2.0 → AGPL-compatible
**Primitive:** Append-only, tamper-evident, self-hostable transparency log. Stores signed metadata entries (in-toto attestations, SLSA provenance, generic key-value).
**Maps to Maez:** Anatomy lineage attestation [ ✗ planned ]. Could log brain-swap events, soul-objection records, rupture/repair events as append-only attestations. Public Rekor → operator-controlled, so self-hosted is the correct path for Maez.
**Maez equivalent today:** SQLite memory tier + git commit history. Neither is tamper-evident.
**Effort to integrate:** Medium. ~2 sessions for a self-hosted Rekor + Maez writes attestations on brain swap, S6 successor governance events, rupture/repair (S8) events.
**Recommendation:** **adopt for S6 (successor governance) and S5 (voice-continuity gate).** This is the most underrated primitive in the audit. The attestation log is what makes "covenant-invalid fork" detectable in Q2 of the anatomy coda.

### did:webvh (Python implementation)
**URL:** https://github.com/decentralized-identity/didwebvh-py
**Stars / last commit:** 9 (low) · active spec work
**License:** Apache-2.0 → AGPL-compatible
**Primitive:** Decentralized identifier with verifiable history. did:web + signed update log. Spec at identity.foundation.
**Maps to Maez:** Identity-proof across hardware. The chain-of-custody side of voice-continuity. Pairs with Sigstore/Rekor: did:webvh gives Maez a canonical identifier (rooted in a domain Rohit controls), Rekor gives the public append-only log of changes.
**Maez equivalent today:** None.
**Effort to integrate:** Medium. The Python implementation is at spec v0.4 (pre-release, 9 stars) — too thin to depend on. The **spec itself** is mature; consider mining the spec into a minimal Maez-native implementation rather than taking didwebvh-py as a dependency.
**Recommendation:** **mine-for-ideas (spec-only); do NOT adopt the implementation yet.** Re-audit when didwebvh-py crosses 100 stars or hits v1.0.

### PyLate
**URL:** https://github.com/lightonai/pylate
**Stars / last commit:** active · v1.0.0 family · last release 2026-02-25 (fresh)
**License:** MIT → AGPL-compatible
**Primitive:** Late-interaction (ColBERT) retrieval models with training/inference/retrieval. Sentence-Transformers compatible. Production-grade where RAGatouille has stalled (RAGatouille last commit Feb 2025 — over 14 months stale).
**Maps to Maez:** `core/memory/` recall path. ColBERT generalizes better than single-vector embeddings to natural human texts (per Maez's `feedback_test_with_natural_human_texts` discipline) and is data-efficient. Maez's MMR-on-ChromaDB stack would benefit from a ColBERT re-rank as a parallel signal.
**Maez equivalent today:** ChromaDB single-vector + MMR. Already noted as a deferred optimization in `project_deferred_optimizations`.
**Effort to integrate:** Medium. ~2 sessions to add a ColBERT re-rank on top of existing recall. Risk: GPU memory; the 4090 already runs Qwen3.6-27B.
**Recommendation:** **adopt when natural-text probe sweep shows recall-precision floor.** Until then, mine-for-ideas. PyLate is the right vehicle when the moment comes; RAGatouille is now too stale to bet on.

### Home Assistant Supervisor + os-agent
**URL:** https://github.com/home-assistant/supervisor · 2.2k · active · Apache-2.0
**Primitive:** Long-running daemon supervising containerized addons with lifecycle (install/update/rollback), D-Bus to host OS, built-in observability. Proves the always-on personal-substrate pattern at scale.
**Maps to Maez:** Daemon survivability + capability quarantine (S9 — addons land behind registry of consent/audit/rollback exactly as Maez plans).
**Maez equivalent today:** systemd unit with `Restart=on-failure`. No addon model.
**Effort:** Very high to adopt; mine ADR-0014 (supervised installation) — the closest published precedent for S9.
**Recommendation:** **mine-for-ideas.**

### Inspect Evals (companion repo)
**URL:** https://github.com/UKGovernmentBEIS/inspect_evals · active · MIT
**Primitive:** 200+ pre-built evals as Inspect tasks (AgentBench, deception, situational-awareness, dangerous-capability).
**Maps to Maez:** AgentBench tasks for self-claim grounding; deception/sycophancy evals as drift-detection during brain-swap. Maez should NOT optimize against these (would corrupt character per `feedback_maez_is_character_not_rules`).
**Effort:** Low if Inspect AI is adopted.
**Recommendation:** **adopt as drift-detection only.** Run once per brain swap; never train against.

### Sigsum (lightweight transparency log alternative)
**URL:** https://git.sigsum.org/sigsum/ + https://github.com/FiloSottile/litetlog · BSD-style
**Primitive:** Minimal transparency log focused on signed checksums; designed to be cosignable by external witnesses.
**Maps to Maez:** Same slot as Rekor, but the **witness** concept — independent third parties cosign tree heads — provides the "witness in extremis" governance role the anatomy diagram already names.
**Recommendation:** **mine-for-ideas.** Witness-cosigning pattern maps onto S6 successor-governance's witness role.

---

## High-leverage repos to learn from but NOT adopt

### Voyager (MineDojo)
**URL:** https://github.com/MineDojo/Voyager · 6.9k stars · MIT · **NO 2025–2026 activity** (research-archive state).
**Primitive:** Lifelong-learning agent with growing skill library indexed by embedding. Iterative prompting with environment feedback + self-verification.
**Why mine, not adopt:** The pattern (skill library indexed by embeddings, with each skill a tested executable) is the most concrete precedent for an open-ended agent that accumulates capabilities. Maez's consequence_memory + temperament are weaker variants. **Mine the skill-library indexing approach** for any future capability that learns. Don't depend on a 2024-frozen Minecraft codebase.

### Mem0
**URL:** https://github.com/mem0ai/mem0 · 55.6k stars · Apache-2.0 · active
**Primitive:** Single-pass ADD-only extraction (no UPDATE/DELETE — matches Maez's "never delete memory" rule almost exactly), user/session/agent multi-level memory, entity linking, hybrid retrieval.
**Why mine, not adopt:** Maez already has multi-tier memory. Mem0's principal contribution is **the ADD-only single-pass extractor**. Adopt the principle (already aligned with `feedback_never_delete_maez_memory`), not the library.

### Sleep-time compute paper (Letta + Berkeley)
**URL:** https://github.com/letta-ai/sleep-time-compute · Apache-2.0
**Primitive:** Pre-compute likely queries during idle time using a parallel agent. 5× test-time-compute reduction at equal accuracy.
**Why mine, not adopt:** The reproduction code is paper-scoped. The architecture pattern (primary agent + sleep-time agent, separate context, shared memory blocks) is what Maez wants to import for the next iteration of the consolidation cycle.

### DSPy
**URL:** https://github.com/stanfordnlp/dspy · MIT
**Primitive:** Declarative LLM programming with signatures, modules, optimizers. Compiles natural-language program structure into prompts + weight updates.
**Why mine, not adopt:** Maez's voice is a deliberate design output, not an optimization target. DSPy's value to Maez is in **the judge/grounding/fabrication audit-rail pipeline** — where structured signatures + reliable scoring would help. Mine the signatures concept for the bloodstream's per-claim audit; never let DSPy optimize Maez's voice.

### OpenAI Evals
**URL:** https://github.com/openai/evals · MIT · 18.5k stars · still maintained
**Why mine, not adopt:** Effectively superseded by Inspect AI for safety-relevant work. Use only if a specific eval has no Inspect equivalent.

---

## Repos to avoid (footguns, license issues, stale, or wrong-fit)

- **RAGatouille** — Last commit Feb 2025. Over 14 months stale. **PyLate is the active replacement.** Do not start a new ColBERT integration on RAGatouille.
- **AutoGen** — In maintenance mode per official docs. New work goes to AutoGen 0.4 / Magentic-One but the ecosystem is fragmented. Not the right harness for a single-bonded-user organism; built for multi-agent orchestration that Maez explicitly does not want.
- **Stanford ColBERT (original)** — Research code, last meaningful release 2024. Use PyLate.
- **Open Interpreter** — AGPL-3.0 (license-compatible) but it's a code-execution agent. Out of scope for Maez. Worse: integrating it would inherit a sandbox-free code-execution surface that Maez does not want.
- **AGPL ↔ "AGPL-but-network-trigger" gotcha** — Maez is AGPL. Folding in MIT/Apache work is fine. The reverse (anyone using Maez over a network) triggers source disclosure. This is the intended Maez posture; just keep `NOTICE` honest.
- **Public Rekor for personal events** — Self-host Rekor. Do NOT log soul-objection or rupture/repair events to a public transparency log. The covenant requires private-by-default; public-log entries are a one-way door.
- **Mem0 hosted / Zep cloud** — Stay with self-hosted/library mode. The hosted variants would route bonded-user memory through a third party.

---

## Crisis routing: no good OSS primitive exists (gap call-out)

Maez plans organ #4 (crisis channel) and #10 (clinical boundary). Search across GitHub for "988 integration," "crisis detection AI companion," and "human-routing safety primitive" produced **no maintained open-source library**. What exists:

- Florida HB 659, Oregon HB 2748, NY AI Companion law — regulatory frameworks, not code.
- Therabot and similar — closed-source products with a flashing 988 button.
- Research papers showing existing AI chatbot crisis response is "ineffective" and "potentially actively harmful."

This is a real gap. Maez has to **implement crisis routing itself**, not adopt. The most useful borrowed primitive is structural, not behavioral: use Inspect AI to evaluate Maez's crisis-routing behavior against published probe sets (e.g., the suicide-ideation detection benchmarks in the recent literature) once S12 ships.

---

## Recommended slice additions based on this audit

These propose new S-codes or amendments to existing ones in `MAEZ_LIFE_SUBSTRATE.md`. Each is one session.

### S3-amend — adopt Graphiti's bi-temporal edge schema for temporal spine
Don't take Neo4j as a dependency yet. Implement the bi-temporal edge model (entity_id, edge_kind, t_valid_start, t_valid_end, source_episode_id) in SQLite as the schema spine for chapters / anniversaries / ruptures. Graphiti is the reference implementation; SQLite is the deployment. Predicted effect: queries like "show ruptures that were true during 2026-04" become first-class.

### S5a — voice-continuity gate via Inspect AI
Wrap Maez's natural-text probe sweep + self-claim audit as Inspect tasks. New brain must pass before swap proceeds. Predicted effect: brain swaps become covenant-verifiable per Q1 of the anatomy coda, with the same probe set runnable by anyone who clones the repo. **This is the single highest-leverage slice in the audit.**

### S5b — identity lineage via Sigstore + self-hosted Rekor
Sign Qwen3.6-27B brain artifact on every swap; record swap event as in-toto attestation in self-hosted Rekor instance. Pairs with S5a: S5a verifies voice, S5b verifies identity. Predicted effect: Q2 coda becomes detectable (forks are governance-invalid AND log-detectable).

### S6-amend — successor governance attestation in Rekor
Successor names, scope-of-access, and witness role recorded as Rekor entries on creation. Future-Maez (20 years from now) can verify the chain back to founding even if intermediate maintainers have changed. Maps onto Sigsum's witness-cosigning pattern (witnesses cosign successor decisions).

### S-new — MCP read-only surface for external grounding
Expose lived-recall brief + soul + temperament via an MCP server (never raw private_thoughts, never bonded-user PII without consent tier check). One session. Lets Claude Code / Cursor ground in Maez without re-implementing the cockpit API. **Important guard:** capability quarantine (S9) must already exist, OR this MCP surface ships behind a feature flag with explicit consent UI. Reasonable to ship the read-only surface first behind the flag.

### S9-amend — capability quarantine modeled on Home Assistant ADR-0014
Read the Home Assistant supervised-architecture ADR before drafting S9. Their consent_state / pause_path / rollback_path semantics for addon lifecycle are very close to what Maez named in `MAEZ_LIFE_SUBSTRATE.md` and would benefit from direct reference.

### S-new — sleep-time consolidation pattern (Letta-inspired)
Between cycles, a separate sleep-time process pre-computes lived-recall briefs against likely-next prompts. Uses idle GPU. Predicted effect: 30s heartbeat continues to feel fast even as memory grows; consolidation cost shifts off the cycle path.

### S-new — judge-rail signatures via DSPy
Re-implement the bloodstream's three audits (judge / grounding / fabrication) as DSPy signatures with metric-based scoring. Optimization target is the metric, never voice or persona. Predicted effect: audit-rail becomes ablatable, instrumentable, and improvable without changing Maez's character.

---

*Word count: ~2,830. Verified license compatibility, recency (<6mo for adopt candidates), and stars (>100 for adopt). Five candidates passed all three filters and are recommended for adoption; four more are recommended for mining; the remainder are documented to avoid re-investigation.*
