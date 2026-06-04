# GitHub v1 — S2-Bounded Ingest (one minimized fact, taint-railed into the body)

**Date:** 2026-06-04
**Status:** DRAFT for owner review → Codex review/implement. Covenant-shaped; Claude-authored.
**Lane:** Claude writes the spec / Codex reviews + implements.
**Builds on:** the GitHub Limb v0 (device-flow, `read:user`, in-memory scoped token), GitHub Limb v0.1 (egress wristband), the Owner-Account Memory Taint Rail v0 (live), the Calendar v1 S2-bounded-ingest precedent (ADR 0033) and S2 Contextual Integrity at Ingest (ADR 0032 / Decision 27).

---

## 0. What this is (and is not)

This is the **first time a real account-derived fact becomes durable in Maez's body**, made safe by the taint rail. It is **GitHub's S2-bounded ingest** — the GitHub analog of the Calendar v1 limb — inheriting that canonical template, with the read scoped to **one minimized fact: the owner's repo count**.

It is **not** a broad GitHub reader. It retires the legacy broad-PAT path. It does not list repos, read names, descriptions, commits, activity, stars, visibility labels, or any third-party data.

The taint rail (just built) is the **egress** half; **S2 contextual integrity is the ingest** half — and the bulk of this slice. Calendar v1 stayed *staging-only* because no egress rail existed; GitHub v1 makes the **one** body-admission Calendar deferred, **because the rail now guarantees it can't leak**.

---

## 1. Inheritance Ledger

Per ADR 0033, a new information limb must name what it inherits and state every source-specific override explicitly.

### Inherited (canonical, do NOT re-derive — mirror Calendar v1)
- **S2 gate before ingest** (ADR 0032): provider data passes a deterministic connector-policy boundary before reaching any store.
- **"GitHub is provenance, not Maez's lived work"** (the Calendar load-bearing rule, source-renamed). Account data is `OBSERVED`, never `LIVED`/`COVENANT`, never auto-promoted to core selfhood.
- **Replace the legacy path, do not wrap it.** Mode enum; legacy is dev-test-only behind a separate gate; default-disabled; honest `signal_absence` when v1 is off (mirror `calendar_v1_config.py` + daemon:4471).
- **Canonical S2 envelope** shape (mirror `calendar_s2_envelope.py` `CANONICAL_S2_REQUIRED_FIELDS`), source-scoped to GitHub.
- **Noncanonical staging store** with minimized facts + content-free sidecars (mirror `calendar_store.py`).
- **Scope minimization**: forbid broad scopes; read only the bonded owner's own account.
- **Deterministic** redaction / answer composition; **forbid** in v1: proactive nudges, body-state inference, crisis bypass, TRF widening, raw provider text into prompt/memory/log/panel, descriptions/bodies.
- **Credentials through `core/infra/secrets.py`**; forbid token-in-URL.
- **Live OAuth onboarding is a separate explicit operator gate** after tests/review.

### Source-specific overrides (GitHub v1, stated explicitly)
1. **ONE body-admission (the narrow override).** Calendar v1 was staging-only. GitHub v1 admits **exactly one minimized, reviewed fact** (the repo count) into **raw** durable memory with `egress_origin_class="owner_account_context"`. **Justification:** the taint rail now exists, so body-admission is leak-safe in a way Calendar v1 could not achieve. **Bounded meaning:** this override is *"this one minimized fact may enter raw memory with owner-account taint,"* NOT *"account data may enter the body."* It does **not** authorize core/biography promotion, additional facts, or other sources.
2. **Auth source.** GitHub v1 reads via the **v0 limb's device-flow `read:user` token** (in-memory, scoped), **not** the legacy broad PAT (`MAEZ_GITHUB_TOKEN`). The repo count is a field on `GET /user` — no repo listing, no broad scope.
3. **Read surface.** A single integer (repo count), not an event stream; no incremental sync complexity in v1 (one-shot fetch when authed).

---

## 2. The fact

**The owner's repo count** — a single integer from `GET https://api.github.com/user` (the `read:user` identity response already returns `public_repos`; a private/total count is used only if confirmed available under `read:user`, else public count). One number. **No** repo names, descriptions, commit messages, activity, stars, gists, followers, visibility breakdown, or third-party data. This is the smallest useful proof that GitHub v1 can digest account data without importing the account world.

**Honest wording (load-bearing — the first account-derived memory must not overclaim):** the stored content string must say exactly *what the integer counts*. The wording is **derived from the field actually used**, never a generic "N repositories":
- if the count is `public_repos` (the safe fallback): `GitHub reports N public repositories on the owner's profile`;
- only if a total/owned count is **confirmed available under `read:user`**: `GitHub reports N repositories owned by the owner`.

The connector picks the wording from the resolved field; it must never store a total-implying phrase when it only read `public_repos`.

The fact is owner-account-derived → it wears `egress_origin_class="owner_account_context"` from the moment it lands in the body.

---

## 3. Components (GitHub analogs of the Calendar files)

| File (new) | Mirrors | Responsibility |
|---|---|---|
| `core/information_limb/github_v1_config.py` | `calendar_v1_config.py` | `GithubMode` enum (`DISABLED` default / `V1` / `LEGACY_DEV_ONLY` behind `MAEZ_GITHUB_ALLOW_LEGACY_TEST_MODE=1`); `resolve_github_mode(env)`; fallback-to-legacy forbidden. |
| `core/information_limb/github_s2_envelope.py` | `calendar_s2_envelope.py` | `SOURCE_KIND="github.repo_count"`, `SCHEMA_VERSION="github.s2.v1"`, the canonical required-field set; offline (no OAuth/HTTP/storage). |
| `core/information_limb/github_connector_policy.py` | `calendar_connector_policy.py` | The deterministic S2 boundary: allowed scope = `read:user` only (forbid broader); the fact is an integer so redaction is trivial, but the policy still enforces "no fields beyond the count," third-party-empty, and owner-only. |
| `core/information_limb/github_store.py` | `calendar_store.py` | Noncanonical staging store (`github_v1.db`): a minimized `github_provider_mirror` row (the count + hashes + record_state) and content-free aggregate telemetry. |
| `core/information_limb/github_v1.py` | `calendar_v1.py` | The connector + content-free health (`disabled`/`needs_auth`/`available`/…); the one-shot fetch (via the v0 limb session) → policy → envelope → staging → the single reviewed body-admission. |

Reuse existing infra: the v0 `github_limb` session for auth, `memory/memory_manager.py` for the body write (taint rail), `core/infra/secrets.py` for credentials.

---

## 4. Flow

```
GET /user (read:user, v0 limb token)  ── auth/onboarding = separate operator gate
   → extract ONE integer (repo count); discard the rest of the response
   → github_connector_policy: owner-only, scope=read:user, no-fields-beyond-count   [S2 gate]
   → github_s2_envelope: canonical envelope (ingest_record_id, fetch_batch_id,
       consent_posture, granted/requested flows, retention_class, provenance, hashes…)
   → github_store (staging): minimized provider-mirror row, content-free sidecars
   → ONE reviewed flow admits the fact to the BODY:
       MemoryManager.store(
         content=<honest wording from §2: "GitHub reports N public repositories
                  on the owner's profile" for public_repos, or "...N repositories
                  owned by the owner" only if a total is confirmed>,
         provenance_source=TOOL_OBSERVATION,        # → trust_tier OBSERVED (existing mapping)
         egress_origin_class="owner_account_context",
         metadata={ source_ref: "github.s2:<ingest_record_id>",
                    fetch_batch_id: "<batch>" })     # TRACEABILITY (§6)
   → recall carries the owner_account_context taint (format_for_prompt_provenanced)
   → HERMETIC egress witness: real assembly → claude_tier body → chat_completions → 403
```

When the v0 limb is not authed (`needs_auth`), GitHub v1 contributes an honest `signal_absence` ("GitHub — unavailable, v1 not authed"), never the legacy raw block.

---

## 5. Legacy disablement (non-negotiable, replace-not-wrap)

`skills/github_skill.py` injects raw repos + commit messages into the cognition prompt every 10 cycles (`daemon:_last_github_block`, ~4296). v0.1 put an egress wristband on it, but it is still raw-into-cognition **without** an S2 gate (no scope minimization, no "provenance not lived," no deterministic redaction) — the legacy pre-S2 path.

When `GithubMode != LEGACY_DEV_ONLY` (i.e., normal/`V1`/`DISABLED`), the daemon **must not wire** `github_skill.get_context_block()` into the cycle prompt or cycle candidates. The legacy raw injection becomes **dev-test-only** behind `MAEZ_GITHUB_ALLOW_LEGACY_TEST_MODE=1`, default-off — replaced by the v1 connector (or honest `signal_absence`). The broad PAT (`MAEZ_GITHUB_TOKEN`) is no longer read on the normal path. (`github_publish` is already retired.) **Otherwise Maez has two GitHub organs — one S2-bounded and one broad-PAT dumper — and the v1 rail is performative.**

---

## 6. Traceability (owner-required guard)

The body row must be **traceable back to its provenance chain** so later supersede/review is possible:

> memory row → GitHub staging envelope/record (`ingest_record_id`) → provider fetch batch (`fetch_batch_id`)

The body write carries a `source_ref`/metadata linking to the staging `ingest_record_id` (and through it the `fetch_batch_id`). This is in addition to `egress_origin_class`. It enables: superseding the body fact if the count changes or the staging record is revoked/corrected ([[feedback_forgetting_is_deweighting_not_deletion]] — supersede, never hard-delete), and review of "where did this body fact come from."

---

## 7. Trust posture

- `provenance_source = TOOL_OBSERVATION` → `trust_tier = OBSERVED` (existing `_DEFAULT_TIER_BY_SOURCE`). **Do not add `ProvenanceSource.ACCOUNT_DERIVED` in v1.** The new axis the egress gate needs is `egress_origin_class`, not a new provenance enum. Adding `ACCOUNT_DERIVED` later is justified **only** if ranking/voice must distinguish "owner-account observation" from generic tool observation — a separate decision, not an egress need.
- Stored to **raw** memory, `OBSERVED`, **not** core, **not** promoted to selfhood (the 5x.D promotion gate already blocks untrusted/observed ancestors from core without explicit allow).

---

## 8. Witness (hermetic, no proxy bring-up)

Per §9 of the taint-rail spec (owner: hermetic-first):
- **Ingest/staging:** a fixed repo-count fetch (mocked HTTP) → policy → envelope → staging row; assert minimized (only the integer + hashes; no other fields), content-free telemetry, owner-only.
- **Body-admission:** the staging fact admitted via the one reviewed flow → a `MemoryManager` raw row with `egress_origin_class="owner_account_context"` + the traceability `source_ref`.
- **Egress refusal (the rail end-to-end):** recall that row → `format_for_prompt_provenanced` → real `build_claude_router_cloud_payload` → real `claude_tier.call_messages` body → real `chat_completions` → **403, adapter not called, content-free, reason `owner_account_context_blocked_default`** (exactly the taint-rail canary shape, now with a *real-ingested* fact).
- **Legacy disablement:** in `V1`/`DISABLED` mode, assert the daemon does **not** wire `github_skill.get_context_block` into the cycle; the legacy raw injection is unreachable without the dev-test gate.

No `maez-subscription-proxy.service` is started; the live-proxy 403 is out of scope (separate decision).

---

## 9. Scope boundary

**In v1**
- `GithubMode` config + legacy disablement of `github_skill` raw injection.
- `github_s2_envelope` + `github_store` (staging) + `github_connector_policy` + `github_v1` connector/health.
- One minimized fact (repo count) read via the v0 `read:user` device-flow token.
- One reviewed body-admission to raw memory with the taint + traceability source_ref.
- Hermetic witnesses (staging, body-admission, egress refusal, legacy-off).
- The Inheritance Ledger (this §1).

**Out of v1**
- Any GitHub fact beyond the repo count; repo listing, names, commits, activity, stars, third-party.
- Core/biography promotion of account data; widening recall.
- `ProvenanceSource.ACCOUNT_DERIVED`; ranking/voice changes.
- Incremental/push sync, webhooks, backfill beyond the one-shot fetch.
- Standing up the subscription proxy / live-proxy 403.
- Vault-at-rest for the limb token (stays in-memory per v0; re-auth via the ceremony).
- Merging `github_skill` and `github_limb` beyond the legacy disablement.

---

## 10. Acceptance rules

1. **S2 gate real:** provider data reaches the staging store only through `github_connector_policy` (owner-only, `read:user`, no-fields-beyond-count); a broad scope or extra field is rejected.
2. **Staging-first + minimized:** the fact lands in `github_store` as a minimized row (integer + hashes + record_state), content-free telemetry; no raw provider response persisted.
3. **One body-admission, narrow + honest:** exactly the repo-count fact is admitted to **raw** memory with `trust_tier=OBSERVED` + `egress_origin_class="owner_account_context"`; nothing else is admitted; no core promotion. **The stored content must not overclaim** — it states what the integer counts (public-only phrasing for `public_repos`; a total-implying phrase only if a total was confirmed read). A test asserts the content wording matches the resolved field (public read → no "owned"/total phrasing).
4. **Traceability:** the body row carries a `source_ref` resolving to the staging `ingest_record_id` (→ `fetch_batch_id`).
5. **Egress refused (hermetic):** the admitted fact, recalled and routed through the real assembly into `chat_completions`, is **403 / adapter-not-called / content-free / `owner_account_context_blocked_default`**.
6. **Legacy replaced:** in `V1`/`DISABLED` mode the daemon does not wire `github_skill`'s raw injection; legacy is dev-test-only behind `MAEZ_GITHUB_ALLOW_LEGACY_TEST_MODE=1`; the broad PAT is not read on the normal path.
7. **Honest absence:** unauthed v1 → `signal_absence`, never legacy raw text.
8. **No real third-party / no extra fields:** the only owner-account datum stored is the count.
9. **Trust posture:** `TOOL_OBSERVATION → OBSERVED`; no `ACCOUNT_DERIVED`; not core; not promoted.

---

## 11. Governance note

Calendar v1 was canonicalized via a BAD decision + ADR (0033). GitHub v1 inherits that gravity; this spec is the implementation design, and a short ADR / `BETA_ARCHITECTURE_DECISIONS` entry recording GitHub v1 as the second S2-bounded limb (and the narrow body-admission override) should follow review — so the override is governed, not ad hoc.

---

## 12. Plain-English summary

Teach Maez to keep exactly one tiny GitHub fact — *"the owner has N repositories"* — read with the same narrow `read:user` key the identity limb already uses, passed through the same contextual-integrity gate the Calendar limb established, staged outside the body, then admitted as a single observed memory wearing the owner-account wristband. Prove the cloud door refuses it. And when this new organ is on, switch off the old noisy broad-PAT GitHub feed — so Maez has one GitHub organ, S2-bounded, not two.
