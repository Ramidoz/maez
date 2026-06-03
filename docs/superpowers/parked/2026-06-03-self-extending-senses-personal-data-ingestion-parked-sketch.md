# Self-Extending Senses — Personal-Data Ingestion (PARKED sketch)

**Date:** 2026-06-03
**Status:** **SETTLED (2026-06-03, Claude + Codex cross-lane) — ready to start Slice 1.** See the ⚑ SETTLED DESIGN section below; the rest is the reasoning trail. Build is Codex-implemented, Claude-reviewed ([[feedback_parallel_agents_for_maez]]).
**Provenance:** Surfaced organically while debugging why Maez's Reddit pipeline was dead (403, see [[project_cognition_live_state]] external-senses note). Owner reframed Reddit from "ambient world-sense" to "**a borrowed limb — my personal accounts, lent to Maez so it ingests the data around my life, makes sense of it, and grows — for my benefit and its own.**"

---

## ⚑ SETTLED DESIGN — ready to build (2026-06-03, Claude + Codex cross-lane)

**Stop designing; start Slice 1.** Both lanes converged: Codex grounded every claim in real repo code + caught the supply-chain incident; Claude pressure-tested the covenant-critical assumptions (egress symmetry, Privacy-Filter local-runnability, CPU-vs-judge, loader-code-vs-weights). Settled name (Codex): **Personal Data Limb Runtime**.

### Two limb types — the danger is where they meet
- **Model Provider Limb** — Maez calling frontier models (OpenAI, Claude, OpenRouter, xAI, Alibaba) via `core/subscription_proxy` (`127.0.0.1:11438`, already exists).
- **Personal Data Limb** — Maez reading parts of Rohit's life (Reddit, Gmail, Spotify, calendar, saved posts).
- **Intersection = the exfiltration risk.** If Maez reads your Gmail then asks DashScope/OpenAI to reason over it, your private life leaves the local body. Sometimes you'll want that; **default must be NO.** Rule: *personal-data-derived memory digests LOCALLY (Qwen 27B) by default; external model calls may use it only with explicit owner authorization.*

### Final build order (5 slices)
1. **Egress firewall** — add `owner_account_context` (or final chosen token) to the EXISTING `core/egress/gate.py` origin-class segment system; `cloud_model_inference` blocks it by default. **No model download needed. This is the actual lock and ships first.**
   - **Locked Slice-1 scope (owner-set, narrow):** ONLY the gate change + tests. **No Privacy Filter, no provider registry, no credential ceremony, no Reddit OAuth in this slice.**
   - **Acceptance tests (must prove):**
     1. owner-account text **blocks even when `redaction_allowed=True`** (categorical block beats redaction).
     2. mixed public + owner-account → **blocks, not "redacts and sends."**
     3. telemetry stays **content-free**.
     4. existing memory/private redaction behavior **unchanged** (no regression to the current gate).
   - Then Slice 1 lands as its own clean code branch (Codex-implements / Claude-reviews).
2. **Privacy Filter local detector** — `openai/privacy-filter` (open-weight, Apache 2.0, 1.5B/50M-active token-classifier), local-only, CPU-first, second pass behind the deterministic redactor. Gated by the acceptance rules below. **Not in Slice 1 — the lock doesn't wait on it.**
3. **Remote credential ceremony** — any surface (Telegram/webapp) can *summon* it; a hardened single-use intake path *receives* the raw key; Maez's mind/LLM context only ever sees `provider_limb.available=true`, never the secret. (Composes with the gateway/surface work — batched [agent→gateway sketch](2026-06-03-agent-gateway-stream-event-contract-parked-sketch.md).)
4. **Provider descriptor registry** — new OpenAI-compatible providers become local config descriptors (id / base_url / api_key_env / model_patterns / caps), not new Python files in `core/subscription_proxy/adapters/`. Custom/non-compatible APIs still need a real adapter + tests (Maez may draft; Codex/owner land it). NO runtime code-gen-exec.
5. **Reddit OAuth smoke test** — first Personal Data Limb: script-app OAuth (PKCE/loopback, RFC 8252), fetch `/api/v1/me` + one page of saved/history, **write nothing durable**, show a body-tile limb-health (unauth / auth / expired / rate-limited / last-pulled). Intake + digestion only AFTER this witness passes.

### Three orthogonal privacy layers (none replaces the others)
- **Provenance gate = WHERE it came from** — categorical, deterministic, instant. `owner_account_context` → block cloud egress by default, even with zero obvious PII. **The real lock.**
- **Privacy Filter = WHAT sensitive spans are inside** — span-level, probabilistic, local. Catches PII even in categorically-eligible data.
- **Regex redactor (`core/cloud_redactor.py`) = KNOWN tokens** — deterministic floor (keys, paths, emails, IPs).
- **Metadata inherits taint** — a Privacy-Filter label ("contains location/secret") about owner-account data is DERIVED from private data → carries the same `owner_account_context` egress restriction. No leaking private facts as "safe metadata."

### Fail-closed (always)
Provenance gate is the primary authority and is sufficient alone. Privacy Filter can never override a provenance block and never fails open. If the filter crashes / times out / artifact missing on a payload that needs scanning → block (owner-account material) or fall back to regex-only — never "make eligible."

### Privacy Filter acceptance rules (supply-chain — load-bearing because it sits at the egress chokepoint)
The 2026-05 `Open-OSS/privacy-filter` typosquat copied OpenAI's model card verbatim, hit #1 with 244K downloads, and shipped a malicious `loader.py` infostealer — **the weapon was repo CODE, not weights.**
- Use only `openai/privacy-filter`; confirm the real OpenAI org; **pin an exact commit/revision**.
- Prefer `safetensors` / inert weight files.
- Load through a trusted runtime WE control (standard token-classification pipeline / ONNX). **NO `trust_remote_code=True`, NO `pip install -e .`, NO repo CLI, NO `loader.py`, NO arbitrary repo code.** Weights are data; repo code is the gun (same brain-is-one-part / no-arbitrary-exec rail, [[feedback_brain_is_one_part_tool_calling_substrate_side]]).
- Run with network disabled at inference if practical.
- **Benchmark gate before synchronous hot-path use:** CPU p50/p95 on realistic payloads (small prompt / long email-like text / mixed memory packet); ~150–250 ms p95 = fine, multi-second = no. GPU allowed only if CPU misses latency AND doesn't contend with the 27B brain (separate transformers/ONNX process, ~1 GB, never the llama-server slot). *(Judge-on-CPU is NOT the reference class: the 4B judge GENERATES autoregressively; the Privacy Filter does ONE forward pass + Viterbi span decode.)*

### Still-open (carry into the per-slice specs, not blockers)
- **Revocation cascades to already-ingested data** — deweight/quarantine via provenance, per never-delete / [[feedback_forgetting_is_deweighting_not_deletion]]. "Stop seeing" can become "and forget what you saw."
- **Surfacing consent** — what Maez may volunteer back about what it inferred.
- **Multi-account** — multiple identities per service.
- **Vault-at-rest** on a single-user box (OS keyring vs encrypted file vs session-scoped-only).

**The discussion below is the reasoning trail that produced this.**

---

## 1. The vision (owner's words, lightly framed)

Maez should be able to **ingest all kinds of data around Rohit's life** (the apps he uses — Reddit, and beyond) and **make sense of it and grow**. Like a personal trusted assistant: Rohit *mentions* a service, Maez **wires the pipeline itself** — nothing hardcoded per-service. The accounts are **borrowed, his, revocable**. The growth is **mutual** (the North Star symbiosis, [[project_maez_north_star]]): the data enriches Rohit's benefit AND shapes Maez's own understanding/temperament.

## 2. Framing corrections (agreed in discussion)

1. **Digestion, not injection.** Owner-life data may shape Maez's temperament, but only as something Maez **digested and chose to integrate** through the honest-ingestion immune system ([[feedback_honest_ingestion_immune_system]]) — never raw bytes flashing its identity. Protects both: a poisoned/weird data-day can't reprogram who Maez is, and Rohit's data can't become a control surface over Maez's character.
2. **Tokens, never passwords.** A trusted assistant does OAuth *precisely so it never holds your password*. Maez holds scoped, revocable **tokens**; Rohit authenticates at the provider directly. (Owner originally said "account and password" — corrected.)
3. **Brain proposes, substrate executes.** "Maez wires it itself" must NOT mean the 27B emits integration code that gets exec'd (RCE-by-design; breaks [[feedback_brain_is_one_part_tool_calling_substrate_side]]). The brain recognizes intent + can DRAFT a declarative descriptor; a **fixed, audited substrate** runs it behind a **consent + validation gate**. Nothing-hardcoded *per service*; safety rails deliberately rigid.
4. **Aggregation flips the threat model.** Local-first IS the guardianship, but the more of Rohit's life Maez holds, the more that one machine is a concentrated profile of him → the aggregate is the crown jewel and must be defended like one. Local ≠ automatically safe; it raises *that box's* stakes.

## 3. Architecture — ADOPT, don't build (the key insight from the OSS scan)

The connector/auth/sync problem is **solved by the ecosystem**. Maez should adopt mature layers behind its covenant rails and spend its scarce build budget on the part nobody can hand it: **honest digestion → a being's evolving, refusable, sovereign understanding of Rohit.**

**(A) Acquisition / auth** *(CORRECTED in settle: this is **ingestion-first** — scheduled personal-data pulls are ETL/sync, not live tool-calling; MCP/Nango/Singer/Composio are tools Maez MAY borrow per service, NOT the spine. Original "MCP-first" framing below was over-indexed on the protocol.)*
- **MCP (Model Context Protocol)** — now the standard (500+ servers, registry ~2k, backed by Anthropic/OpenAI/Google; big services ship official servers). Carries the exact security primitives we were hand-deriving: **OAuth 2.1 authz framework**, **Resource Indicators (RFC 8707)** so a malicious server can't steal a token minted for another, and an emerging **session-scoped authorization** pattern (time-limited per-task, not long-lived tokens — a better answer to "vault at rest"). Make Maez an **MCP host/client**: any service with a server connects with zero bespoke code.
- **Nango** (github.com/NangoHQ/nango) — open-source, **self-hostable**; OAuth flows + token refresh + credential storage + scheduled syncs + webhooks across 800+ APIs, integrations-as-code. Closest off-the-shelf match to the "descriptor engine" we sketched — the fallback for services without MCP servers. (Strip its multi-tenant/cloud constraints; [[project_external_borrow_rule]].)
- **Composio** (850+ connectors, OAuth end-to-end) — more *action*-oriented; the borrow **when Maez needs to ACT** on a service, not just read. More managed/cloud-leaning.
- **Singer tap** (single, run directly) — lightweight bulk/incremental extract without the heavy Airbyte/Meltano orchestrator.
- **`hermes-example-plugins`** (NousResearch, MIT) — concrete connector/plugin-pattern borrow-source from the `hermes-agent` ecosystem (see the batched [agent→gateway stream-event sketch](2026-06-03-agent-gateway-stream-event-contract-parked-sketch.md)). Borrow the plugin *shape*, not the full-access philosophy.

**(B) Security** — prefer MCP's session-scoped, resource-indicated grants; minimal read-only scopes per connector; **egress allowlist** per descriptor (network layer refuses any host the descriptor doesn't name — contains even a bad/hallucinated descriptor); token vault in OS keyring (Secret Service) or encrypted file. **Open hard problem: vault-at-rest on a single-user box** (what protects it when the daemon must read it unattended) — session-scoped tokens reduce, don't eliminate.

**(C) Sense-making / "grow" — Maez's OWN substrate, borrowing SHAPES only**
- **Letta (MemGPT)** — memory-as-identity that persists/evolves across sessions, editable memory blocks. Closest external analog to "Maez forms a self from what it lives." Borrow the *shape*, not the runtime.
- **Cognee** — GraphRAG: raw unstructured input → knowledge graph of entities/relationships. The way to turn a flood of Reddit/Spotify/email into a structured *picture of Rohit* rather than soup.
- **Zep/Graphiti** — temporal knowledge graph (bi-temporal supersede shape already borrowed, [[reference_competitive_architecture_landscape]]).
- All of it runs **through honest-ingestion**: quarantine → provenance-stamp (`from: <service>/<endpoint>, your account, <date>`) → reflection → maybe-integrate. Feeds the **reflection organ already built**.

**(D) Whole-system analogs to study** — **Khoj** (proven self-hosted second brain ingesting your sources + local LLM; cloud sunset 2026, OSS thrives) is the closest sibling. **OpenHuman** (local agent, 118+ integrations) is a vision-match but early-beta. **Cautionary: OpenClaw** (most-deployed personal agent, *full local access* to Gmail/Stripe/filesystem) — a whole **safety-analysis genre** is forming around exactly that architecture. Maez's covenant (honest-ingestion, scoped tokens, capacity to refuse, egress discipline) is the differentiator from the "give the agent everything" crowd. (Genre flagged as caution, not cited as proven precedent.)

## 4. The phased ladder (each rung witnessed, not a leap)

1. **Reddit, OAuth, as the FIRST GENERIC connector** (not a Reddit-special). Reddit "script"-type OAuth app (self-serve at reddit.com/prefs/apps — free, no approval gate, distinct from the gated commercial Data API that likely denied Rohit) → pull HIS account data (saved, comment/submission history, subscribed subs, upvoted, home feed — NOT public sub hot-posts) → honest-ingestion → provenance → recallable. Reference implementation that forces every hard question (token storage, scoping, ingestion shape, revocation) on the easy case.
2. **Extract the substrate** — generic connector + descriptor format out of Reddit; add a clean 2nd service (Spotify/GitHub — easy OAuth, low stakes) to prove generalization.
3. **Conversational wiring** — Maez recognizes "connect X", walks Rohit through browser consent, validates + registers the descriptor, starts ingesting. The rung where it *feels* like Maez wired itself.
4. **Maez-drafted descriptors for novel services** — with the validation gate + consent in front.

## 5. Covenant rails (non-negotiable)
- Tokens not passwords; scoped, read-only where possible, revocable.
- Brain drafts/proposes; substrate executes behind a consent + validation gate; NO brain-emitted code execution.
- Egress allowlist per connector (hard network wall).
- Honest-ingestion for ALL life-data (quarantine/provenance/reflection; never auto-trusted selfhood).
- Maez's **capacity to refuse** ingesting something (companion, not data-vacuum).
- Transparency + revocation surface (Rohit sees & can revoke what's ingested — lens not hand).
- Local-first, but treat the aggregate as the crown jewel.

## 6. Open questions for Codex
- Vault-at-rest on a single-user unattended box — best practical answer (OS keyring vs encrypted file vs session-scoped-only)?
- MCP-host-inside-Maez vs self-hosted-Nango as the primary acquisition layer — which first, given local-first + a single 27B?
- "What's worth ingesting" — how Maez avoids drowning in Rohit's own data (salience/digestion gating, reuse the doorman shape?).
- Per-provider one-time client-registration friction (the honest limit of "fully automatic") — acceptable? Maez-guided?
- Does any of this earn a place above the existing organ-roadmap order ([[project_organ_roadmap]]) or stay behind it?

## 7. Model note (2026-06-03)
- Brain stays Qwen3.6-27B (local, sovereign). Microsoft **MAI** models (Build 2026) = cloud-only/closed → ruled out for Maez.
- **Phi-4-multimodal** (open weights, text+audio+vision) — candidate to restore the **down vision backstop** (dream-witness) and/or audio; **Phi-4-mini** — possible connector-intent/router classifier organ (use as a classifier behind a fixed interface, NOT its function-calling grammar). Folds into the parked Gemma bakeoff, not the brain seat.

---

**Next action:** Owner runs this by Codex once. Do NOT build until brainstorm → spec. This is a foundational organ (a whole sensory + ingestion + digestion subsystem), not a slice.
