# GitHub Limb v0.1 — Boundary Honesty (rail the existing read + retire the auto-push)

**Date:** 2026-06-04
**Status:** SETTLED (Claude + Codex cross-lane). Ready for implementation plan.
**Lane:** Codex implements / Claude reviews ([[feedback_parallel_agents_for_maez]]).
**Builds on:** the merged/witnessed GitHub Limb v0 (`core/information_limb/github_limb.py` — device flow, `read:user`, content-free, in-memory) and the Slice-1 egress firewall (`core/egress/gate.py`).

---

## 0. The reframe (why this is not "add a read surface")

v0.1 was conceived as "the first GitHub read surface beyond identity." Exploring the code reframed it: GitHub personal data is **already** read and injected into cognition, with none of the limb's covenant rails. So v0.1 is **boundary honesty for the GitHub flow that already exists**, not a new pristine surface beside an open door.

### Verified findings (code-grounded, 2026-06-04)
1. **The egress lock is built but has no producer.** `owner_account_context` is a categorical cloud-egress block in `core/egress/gate.py` (`OWNER_ACCOUNT_CONTEXT`, gate.py:52–54; enforced at gate.py:197–232, *ignores `redaction_allowed`*) and is enforced at the proxy (`core/subscription_proxy/server.py:690–710` — 403, no adapter call, content-free record). The proxy comment is explicit: *"owner_account_context: born-enforced (Slice 1; nothing tags it yet, so it changed zero existing flows)"* (server.py:685). **The lock works; nothing turns the key.**
2. **The existing reader is unrailed.** `skills/github_skill.py` authenticates with a broad PAT (`MAEZ_GITHUB_TOKEN` — *not* the limb's scoped device-flow token), reads `/user/repos?affiliation=owner` (**including private repos**), recent **commit messages**, and activity events, and `get_context_block()` returns a **plain string** that the daemon injects into the cognition prompt every 10 cycles (`daemon/maez_daemon.py:4296–4301`) and into cycle candidates (`_extend_cycle_candidates("fresh_evidence", …, salience=65)`, daemon:4298). None of it carries `owner_account_context`.
3. **The auto-push is real, dormant, and armed.** `_write_journal_entry()` calls `GitHubPublisher().publish_nightly()` (daemon:7623–7633). `publish_nightly()` does `git push -u origin main` (github_publish.py:270) to the **public** repo `git@github.com:Ramidoz/maez.git` — shipping the *entire* tracked branch, not the three "curated" files. `origin/main` last moved 2026-05-19 (`5e6b05e`); local `main` is **652 commits ahead** (unpushed). It went quiet because it aborts when the PAT is 401'd; a token refresh re-arms an unattended nightly public push.
4. **Private layers are safe.** `config/secrets.local.env`, `config/.env`, `config/soul.md`, `config/soul.local.md`, `config/identity.yaml`, `memory/private_thoughts.db` are all **untracked** → never pushed. `config/soul.base.md` and `PROGRESS_PUBLIC.md` are the intentional public layer.

### Decisions locked (owner, 2026-06-04)
- **Reader:** keep Maez's full GitHub visibility (private repos/commits/activity — borrowed-limb data the owner chose to share), but **rail it**: tag `owner_account_context` so the egress gate categorically blocks it from any cloud model. Maez may see it locally; it may never leave the body to a cloud model. Auth stays PAT for now (scoped-token migration deferred).
- **Publisher:** **retire the unattended auto-push.** What becomes public is the owner's deliberate act, not a cron's — the same principle as the manual, daemon-pausing backup ritual.
- This slice is **boundary honesty, not digestion.** Honest-ingestion routing is real but separate (see §6).

---

## 1. The one acceptance rule that governs everything: **no "tag then flatten"**

A label that does not *survive* to the egress boundary is theater. The requirement is **not** "`GitHubSkill` returns a tag"; it is "**the subscription proxy receives `owner_account_context` spans and blocks.**" An `origin_class` flattened to a plain string at the first hop is exactly as useless as the internal `CycleEvidenceCandidate.source_type` (an evidence/authority label the egress gate never reads). The witness is the proxy refusing the door — not any intermediate label being set.

This is producer-causality ([[feedback_producer_causality_no_caller_score_laundering]]) applied to provenance survival, and integration-witness discipline ([[feedback_unit_test_is_not_integration_witness]]): the unit fact "a span was tagged" does not prove the integration fact "the gate blocked it."

---

## 2. Design

Two fixes, both at **boundaries**. No digestion logic, no new ingestion surface.

### Fix 1 — owner-account provenance that survives to the egress chokepoint

**1a. Producer boundary.** `skills/github_skill.py`'s owner-account output is represented as `ProvenancedText` with `origin_class="owner_account_context"` — not a bare string. (Confirmed safe: `owner_account_context` is in `KNOWN_ORIGINS`, gate.py:56–64, so `ProvenanceSpan` will not silently downgrade it to `unclassified` at provenance.py:35.)

**Fail-closed stamping (owner call, locked):** stamp the **whole `[GITHUB]` block** `owner_account_context`, *including the public "trending AI repos" section*. Over-protecting public GitHub snippets from cloud egress is harmless; under-protecting private owner-account context is not. Splitting public-trending back out is a later refinement, explicitly **not** a v0.1 concern.

**1b. Survival.** Any egress-visible representation of the GitHub block must reach the cloud chokepoint (`core/routing/claude_tier.py` — the only place cognition-derived content becomes a `maez_egress_segments` bundle, claude_tier.py:347 / :429) **still carrying** the `owner_account_context` span. `claude_tier` provenance is caller-driven: a `ProvenancedText` flows its spans into `maez_egress_segments`; a plain string is wrapped "legacy_raw" and falls back to `owner_message_context` with `redaction_allowed=True` (server.py:457) — which is **not** categorically blocked. So the provenance must be preserved across every hop on any path that can carry the GitHub block toward `claude_tier`.

**1c. Witness (integration, not unit).** A canary GitHub owner-account text is driven through the **real** path — `claude_tier` → `_build_egress_request` (server.py:446) → `decide_egress` → proxy enforcement — and the test asserts:
- the proxy returns **403 / no adapter call** (the door refuses it), and
- the decision reason is `owner_account_context_blocked_default`, and
- the block holds **even with `redaction_allowed=True`** (categorical beats redaction), and
- telemetry stays **content-free**.

Local cognition is unchanged: the block still enters the local cycle prompt and the 27B reads it freely. The lock constrains only cloud egress.

### Fix 2 — retire the unattended auto-push

Remove the `GitHubPublisher().publish_nightly()` call from `_write_journal_entry()` (daemon:7623–7633) so the journal path performs **no** unattended publish / `git push`. Keep `skills/github_publish.py` available for a future *deliberate, owner-initiated* publish (a separate slice if wanted), but nothing fires it automatically.

**Witness:** a guard test asserting the journal/post-journal code path performs no unattended `publish_nightly()` / `git push` behavior (e.g., the call site is gone and is not re-introduced — a source-contract guard in the spirit of the existing `# sqlite-raw-ok` markers, or a behavioral test that `_write_journal_entry` does not invoke the publisher).

---

## 3. Locked acceptance rules (the spec contract)

1. **Producer:** the GitHub owner-account block is represented as `ProvenancedText(owner_account_context)` (whole block, including trending).
2. **Survival:** any egress-visible path to `claude_tier` preserves that span into `maez_egress_segments` — no flatten-to-string en route.
3. **Witness:** canary GitHub owner-account text reaches the real proxy path and is **403, adapter not called**, reason `owner_account_context_blocked_default`, holding even with `redaction_allowed=True`, telemetry content-free.
4. **Fail-closed honesty:** if the current diffuse memory/recall route cannot preserve provenance without the digestion slice, **name that as a residual, documented gap** — do not claim full closure. (v0.1 closes the direct path + proves the gate; any residual diffuse path is written down for the next slice, not papered over.)
5. **Auto-push:** the unattended `publish_nightly()` is removed from the journal path; future publishing is a deliberate owner action only.

---

## 4. Architecture, components, data flow

**Components touched**
- `skills/github_skill.py` — producer; emit `ProvenancedText(owner_account_context)` instead of a plain string.
- `daemon/maez_daemon.py` — (a) the injection boundary (~4296–4301) must preserve the provenance onto any egress-visible path, not flatten it; (b) remove the publish call (~7623–7633).
- `core/routing/claude_tier.py` — the egress assembly; confirm GitHub-derived `ProvenancedText` lands in `maez_egress_segments` with `owner_account_context`.
- `core/egress/provenance.py`, `core/egress/gate.py`, `core/subscription_proxy/server.py` — **read-only** for v0.1: the lock and span types already exist; v0.1 supplies the first producer, it does not modify the gate.
- Tests: a new canary integration test (Fix 1 witness) + a guard test (Fix 2).

**Data flow (the wristband, all the way to the door)**
```
github_skill.get_context_block()
  → ProvenancedText(text, origin_class="owner_account_context")     [1a producer]
  → daemon injection / cycle path  (provenance preserved, NOT flattened)   [1b survival]
  → (if a cloud query is assembled) core/routing/claude_tier.py
  → body["maez_egress_segments"] spans  (origin_class travels on the wire)
  → subscription_proxy _build_egress_request → decide_egress
  → gate: owner_account_context ∈ categorical block → BLOCK (ignores redaction)
  → proxy: 403, adapter NOT called, content-free record                    [1c witness]
```
Local cognition (the 27B cycle) consumes the block unchanged — egress is the only thing constrained.

**Error handling / fail-closed**
- The gate is already fail-closed and categorical (gate.py:197–232). v0.1 adds no new gate logic.
- If provenance cannot be preserved on some path (acceptance rule 4), that path is **documented as a residual gap**, not silently treated as closed.
- Removing the publish call is fail-safe: absence of an unattended push cannot leak; a future deliberate publish is out of scope.

---

## 5. Scope boundary (explicit)

**In v0.1**
- GitHub owner-account block represented as `ProvenancedText(owner_account_context)` at the producer.
- Provenance **survival** to the `claude_tier` egress chokepoint on the direct path, proven by a canary that the proxy 403s with adapter not called.
- Removal of the unattended `publish_nightly()` from the journal path + a guard test.
- Documentation of any residual diffuse memory/recall path that cannot yet preserve provenance.

**Out (deferred to the digestion slice, gated behind "egress is provably safe first")**
- Routing the `[GITHUB]` block through honest-ingestion (quarantine → provenance → reflection → maybe-integrate, [[feedback_honest_ingestion_immune_system]]).
- Threading owner-account provenance through **every** diffuse memory/recall path.
- Merging `skills/github_skill.py` into `core/information_limb/github_limb.py` (one limb surface for auth/health + read).
- PAT → device-flow scoped-token migration; splitting public-trending out of the owner-account stamp.
- Any *deliberate* re-introduction of a curated public publish.

---

## 6. Covenant rails (carried, non-negotiable)
- Borrowed-limb data: Maez may **see** owner-account GitHub data locally; it may **never** leave the body to a cloud model (the wristband + the door).
- Provenance = WHERE it came from: categorical, deterministic, instant (the real lock, [[project_organ_roadmap]] / parked sketch §3).
- No tag-then-flatten: survival to the boundary, witnessed at the boundary.
- Local-first is the guardianship: no unattended cloud push; public exposure is the owner's deliberate act.
- Tokens not passwords; read-only; content-free health surfaces.

---

## 7. Open / implementer-must-verify
1. **Live vs latent cloud path.** Does GitHub-derived content have a *live* path to `claude_tier` today (via recall feeding a cloud-routed query), or only a latent one? The canary proves the block either way; if live, prove the producer→chokepoint provenance actually carries the tag (no flatten) on that real path. If the only honest answer requires the digestion slice, invoke acceptance rule 4 (name the residual gap).
2. **Injection-boundary preservation.** Confirm the daemon injection (~4296–4301) and `_extend_cycle_candidates` path can carry `ProvenancedText` (or an equivalent provenance handle) without flattening — and if not, scope the minimal change that lets the *direct* egress path preserve it for v0.1.
3. **No gate edits.** v0.1 must not weaken or alter `core/egress/gate.py`; it only supplies the first producer. Any temptation to touch the gate is out of scope.

---

## 8. Plain-English summary
This slice makes GitHub data wear a wristband all the way to the door, and proves the door refuses it. Separately, it removes the unattended "Maez pushes itself to public GitHub at night" behavior. That's clean boundary honesty — not digestion. How Maez *digests* what's inside is a later, separately-witnessed slice.
