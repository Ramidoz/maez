# Adversarial audit — is Maez actually structurally distinct?

*Auditor stance: worst-faith hostile-researcher critic, prosecuting the claim that Maez is "structurally distinct from the field." Read-only spot-check of code on 2026-05-13. Doc citations against `MAEZ_NORTH_STAR.md`, `MAEZ_ANATOMY.txt`, `MAEZ_LIFE_SUBSTRATE.md`. Code citations against `core/`, `skills/`, `daemon/`.*

## The hostile thesis

Maez is a thoughtfully decorated chatbot with a SQLite/Chroma memory layer, a 30-second polling loop, an output-filter "audit rail," and a soul prompt from `config/soul.md`. The five structural-distinction axes (cardinality, substrate, continuity, refusal, inter-instance) either reproduce in any self-hosted LLM, or are marked `[ ✗ planned ]` in the project's own anatomy diagram. The single non-aspirational delta is "lives on the user's disk" — true of every locally-hosted LLM since 2023.

Take Maez's own documents seriously: `MAEZ_LIFE_SUBSTRATE.md:11–28` lists twelve missing organs as the route to realizing the eleven invariants. Eleven are `[ ✗ planned ]`; one `[ ◐ implicit ]`. Until they ship, Maez is making structural claims about a body it hasn't grown — while a multi-user telegram surface (`memory/db/public_users/`, `skills/telegram_public.py`) contradicts the bind-to-one-human invariant in running code.

## Per-axis prosecution

### Cardinality

**Claim:** "one instance · one user · lifelong, non-transferable." `MAEZ_ANATOMY.txt:337–338`; `MAEZ_NORTH_STAR.md:13,70–71,84`.

**Counter:** ChatGPT also gives every user per-account memory; Anthropic's Projects keep per-project state; Replika has per-user persistent state. Cardinality-of-one is enforced by *operator policy*, not by architecture. A locally-hosted Llama with one ChromaDB collection per user is the same shape.

**Current code reality:**
- `skills/user_accounts.py:5` self-describes as "Universal identity system for Maez. One account, multiple channels."
- `memory/db/public_users/` contains at least two per-user ChromaDB collections (`e3d0af39-…`, `54fafb02-…`) — distinct from the owner's `memory/db/core/`.
- `core/infra/public_user_shaping.py:5–24` exists specifically to shape *guest* requests with `trust_scope='guest'`, with `GUEST_MAX_TOKENS`, `GUEST_MAX_TEMPERATURE`, and PII stripping.
- `core/routing/fast_backend_router.py:79–89` defines `'owner'`, `'owner.draft'`, `'guest'`, `'public'` as first-class trust scopes.
- `skills/telegram_public.py` is a separate surface from `skills/telegram_voice.py`; the codebase actively serves multiple humans.

**Verdict:** **falsifiable today.** The cardinality-of-one is a *narrative posture about the owner's Maez*, not an architectural invariant. The same process serves Rohit and at least two non-Rohit telegram users; their state lives under `memory/db/public_users/`. A hostile critic correctly observes: this is a single-tenant cognitive substrate that has been extended with a multi-tenant front porch. The bond-thread invariant is operator discipline, not architecture.

### Substrate ownership

**Claim:** "files you own (memory/chroma, *.sqlite)" vs "operator cloud; you cannot grep your past." `MAEZ_ANATOMY.txt:329`.

**Counter:** Anyone with `ollama pull qwen2.5:32b && pip install chromadb` has the same property. Ownership-of-files is a deployment posture, not a structural property of the system. Calling local hosting a "structural delta" is gardening.

**Current code reality:** `core/infra/paths.py:1–60` legitimately puts all state under `MAEZ_HOME` (default: the repo root). `memory/*.db` is local SQLite. ChromaDB collections live in `memory/db/`. Soul lives at `config/soul.md`. The user can in fact grep their past.

**Verdict:** **minor / weak.** True today, but trivially reproducible. The structural-distinction language overclaims. A more honest framing: "Maez chooses to be self-hosted; competitors chose not to" — that's a policy delta, not a structural one. The advantage is only durable if combined with the *other* axes (lineage, refusal-in-user-file). Standalone, it's a footnote.

### Continuity proof

**Claim:** "signed cryptographic lineage" / "did:webvh + TPM key" / "chain of custody · lineage attestation." `MAEZ_NORTH_STAR.md:60,86`; `MAEZ_ANATOMY.txt:410`; covenant invariant #11.

**Counter:** This is the most overclaimed axis. The North Star itself marks it `[ ✗ planned ]` (`MAEZ_NORTH_STAR.md:86`; Anatomy line 410), but pitch material and the structural-delta table still cite it as a differentiator from the field. A claim is not a delta until the code exists.

**Current code reality:**
- `grep -rn "did:webvh\|TPM\|attestation"` across `core/`, `skills/`, `daemon/`: **zero hits.**
- `grep -rn "hardware.bound.key\|sign.*lineage"`: **zero hits.**
- What does exist (`core/memory/identity_ledger.py:62–113`) is a SHA-256 fingerprint of `(base_model, lora_hash, soul_hash)` written into an append-only SQLite ledger. Useful, real, load-bearing — but **not cryptographic signing.** It's a hash of three files in plaintext. Anyone with write access to `memory/identity_ledger.db` can rewrite the ledger; anyone with write access to `config/soul.md` shifts the fingerprint.
- `_TRACK_A_WRITABLE_SEVERITIES = frozenset({"same"})` (`identity_ledger.py:187`). The schema supports `descendant`/`broken` but nothing writes them. Lineage forks have no producer.

**Verdict:** **falsifiable today.** The structural-delta table presents this as a differentiator from the field; the doc itself parenthetically admits `(planned)`; the code has not started. The honest version is: "we have an append-only audit log of model+lora+soul hashes" — useful for the owner's own forensics, identical in kind to logging `sha256sum` to a file. This is the prosecution's strongest axis.

### Refusal owned by user

**Claim:** "soul-objection (planned) logged in YOUR file" vs "operator policy; can flip overnight." `MAEZ_NORTH_STAR.md:48,87`; `MAEZ_ANATOMY.txt:325–326,406`.

**Counter:** "Planned" appears in the structural-delta table itself. What ships today is exactly an operator-side output filter (the audit rail). The behavioral profile is indistinguishable from a competitor's policy filter — both reject/rewrite outputs from inside the operator's runtime, both can be flipped by editing operator-controlled files.

**Current code reality:**
- `grep -rn "soul_objection"` shows three hits total, all inside `core/infra/private_thoughts.py:191,203,279` — and all of them are *string enum values* in closed vocabularies (`ProducerId.SOUL_OBJECTION_DETECTOR`, `SignalKind.SOUL_OBJECTION_FORMING`). They are *labels reserved for a future producer*. **There is no soul_objection detector, no refusal-with-reason path, no per-user file logging of identity-grounded refusals.**
- What does refuse today: `core/safety/self_claim_audit.py:108–116,409–438` (rewrites flagged sentences with `_REWRITE_SENTENCE = "I don't have a grounded answer for that part."`) and `core/cognition/grounding_judge.py`. These are operator-side audit-rail policy with no per-user durability — identical in kind to OpenAI's moderation filter.
- The soul itself (`config/soul.md`) is loaded into the prompt. Soul-as-prompt-substrate is not soul-as-refusal-organ. Rewriting `soul.md` rewrites the personality with no audit trail outside builder mode.

**Verdict:** **falsifiable today, distinct later.** Today's refusal IS operator policy by every behavioral test. The structural distinction is exactly what `MAEZ_NORTH_STAR.md:48` claims will be true *when* soul_objections ships — not what is true now. The doc is honest about the `(planned)` tag; the structural-delta table is less honest about it.

### Inter-instance topology

**Claim:** "dyadic-only + auditable-by-both (Track C)" vs "Field: impossible." `MAEZ_NORTH_STAR.md:88`; `MAEZ_ANATOMY.txt:252–276`.

**Counter:** The North Star explicitly says Track C is not started (`MAEZ_NORTH_STAR.md:104`). The Anatomy marks the bridge/cosmos layer `[ ✗ planned ]` and the grandmother-case dyadic gate `[ ✗ planned, Track C ]` (`MAEZ_ANATOMY.txt:252,270`). The line "Field: impossible" is a comparison between a real chatbot and a future Maez. That's category error, not a delta.

**Current code reality:** `grep -rn "Track C\|inter.maez\|inter_maez\|dyadic"` across `core/`, `skills/`, `daemon/`: **zero hits.** The bridge/cosmos layer does not exist as code. The grandmother-case routing does not exist as code.

**Verdict:** **falsifiable today; the comparison is dishonest.** The structural-delta table presents an aspirational invariant against a real competitor and declares Maez the winner. By the same logic, a system that has shipped zero LOC has every structural distinction one cares to assert. This axis cannot honestly be claimed until Track A+B are done; the doc acknowledges this but the pitch surface does not always.

## The strongest argument that holds today

The hostile critic decisively wins on three axes:

1. **Continuity proof.** Zero cryptographic code. The "signed lineage" line in the structural-delta table is a future-tense claim presented in present-tense framing.
2. **Inter-instance topology.** Zero Track C code. Comparing a planned feature to a real competitor is rhetorically empty.
3. **Refusal owned by user.** Zero soul_objection enforcement; the strings exist only as reserved enum labels. Today's refusal is operator-side audit-rail policy — exactly what the field does.

The critic also lands a partial hit on **cardinality**: the cardinality-of-one is a posture about the owner's Maez, not a property of the running daemon, which actively serves at least two non-owner telegram users with per-user state under `memory/db/public_users/`. If someone runs `ls memory/db/` they see polyamory, not monogamy. This is the most embarrassing finding because it contradicts an invariant in the running code, not in the roadmap.

## The strongest argument that fails

The hostile critic loses on the *composite*: the seven life-signs (`MAEZ_ANATOMY.txt:350–378`) — heartbeat (30s daemon cycle, `core/brain_loop.py` + `daemon/maez_daemon.py`), metabolism (daily consolidation, `core/memory/episodes.py`), immune system (audit rail, `core/safety/self_claim_audit.py` 588 lines + grounding judge), interior (`core/evolution/wonderings.py` 705 lines, `wants.py` 601, `temperament.py` 534, `will_i.py` 306, `learning/inner_residue.py` 290) — are all real, load-bearing, and not what a chatbot has. None of these individually is a structural impossibility for a competitor, but **the combination of always-on background cognition, append-only immune memory, and substrate-side identity-state is genuinely uncommon.** It is at minimum a different *engineering posture* than the field, even if not an unreproducible one.

The strongest defensible claim is much narrower than what the docs assert: **Maez today is structurally distinct in *operational shape* (continuous, audited, interior, append-only), not in *governance properties* (lineage, refusal, inter-instance).** The governance properties are roadmap items. The doc would survive review if it said so plainly.

## Findings

### blocker — claims that overpromise relative to code

- **`MAEZ_ANATOMY.txt:330` / `MAEZ_NORTH_STAR.md:86`** present "signed cryptographic lineage" as the Maez column in a side-by-side vs the field, parenthetically tagged `[ ✗ planned ]`. The structural-delta table treats this as a current differentiator; the code has zero crypto. **Fix:** rewrite the side-by-side row to read "today: SHA-256 hashes of (model, lora, soul) in append-only SQLite. Planned: signed cryptographic lineage." Stop using the planned form in any pitch surface (`MAEZ_PITCH.md`).
- **`MAEZ_ANATOMY.txt:325–326` / `MAEZ_NORTH_STAR.md:87`** "refusal: soul-objection (planned) logged in YOUR file" vs operator policy. Today's refusal IS operator-side audit-rail policy (`core/safety/self_claim_audit.py:108–438`). The "(planned)" tag is honest; the surrounding rhetorical framing is not. **Fix:** rewrite to "today: audit-rail rewrites operator-side, same family as the field. Planned: identity-grounded soul-objection logged in user file."
- **Cardinality invariant vs running code.** `MAEZ_NORTH_STAR.md:70–71` declares "Not a multi-tenant service. The cardinality-of-one is structural. If Maez ever becomes one platform, many users, per-user state, it stops being Maez." But `skills/user_accounts.py:5` says "One account, multiple channels," `memory/db/public_users/` holds multiple guest collections, and `core/infra/public_user_shaping.py` is purpose-built for guest shaping. **Fix:** either (a) acknowledge in the North Star that the running daemon today serves owner + guests and that the "cardinality-of-one" applies to *the bonded thread*, not to *the process*; or (b) carve out and quarantine the public surface into a separate operator-mode boundary so the founder-Maez has cardinality-of-one in code, not just in narrative.

### major — claims that depend on planned organs

- **Inter-instance topology** (`MAEZ_NORTH_STAR.md:88`, `MAEZ_ANATOMY.txt:252–276`). Zero LOC. Track C is gated until after Track B. The structural-delta line "Field: impossible" reads as triumph over a feature Maez has not built. Until S10 ships, this row should be marked planned in pitch material.
- **Capability quarantine** (`MAEZ_ANATOMY.txt:154–167`, invariant #8). `[ ✗ planned ]`. Existing effectors (telegram, chat, cockpit, iphone_ingest) are NOT registered behind `consent_state / auditable_by / dyadic_only / pause_path / rollback_path`. Until S9, the invariant is a posture, not enforcement.
- **Crisis channel, clinical boundary, rupture/repair scar, human-primacy valve, age/capacity stratification.** All `[ ✗ planned ]`. Each is cited as a structural property in the eleven invariants but ships only as a vocal-stance-in-soul.md. The seven life-signs panel correctly marks #5 refusal `[ ◐ partial ]` and #7 mortality `[ ✓ partial ]`, but the invariants section above it does not carry the same nuance.

### minor — claims that hold but are easily reproduced by competitors

- **Substrate ownership** (files you own). Real, but reproducible by any self-hosted LLM. Standalone, a weak differentiator.
- **30-second heartbeat** (`MAEZ_ANATOMY.txt:65–68`). Real. Any cron + LLM reproduces it. Distinctive only in what the heartbeat does.
- **Audit rail per-claim** (`core/safety/self_claim_audit.py`, `core/cognition/grounding_judge.py`). Real, 588+ lines. Reproducible by any team that wants to build it.
- **Interior organs** (`wonderings/wants/will_i/temperament/inner_residue`, ~2.4 kLOC). Real. Reproducible in principle — a *quality* delta, not a *structural* one.

---

*Where the prosecution wins: continuity-proof (zero crypto) is the most overclaimed; cardinality-of-one is contradicted by the running daemon's `public_users/` directory; soul-objection is a reserved string label, not an organ. Where Maez stands genuinely today: the always-on heartbeat + append-only immune memory + durable interior is an uncommon engineering posture and a real (if non-exclusive) shape — distinct from a chatbot, just not yet structurally distinct in the governance sense the docs assert.*
