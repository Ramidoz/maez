# Self-Web-Claim Recall Hygiene (design) — content-honesty Thread C

**Date:** 2026-06-15. Co-designed with Rohit.
**Status:** design approved (4 cruxes resolved + 2 spec constraints). Awaiting spec review before plan.
**Arc:** content-honesty (Thread C of three). Thread A (real support checker) and Thread B
(fresh-vs-memory conflict resolution) are **separate, later** arcs — out of scope here.

## Why this exists (the wound, verified live)

On a Telegram turn (`news about Anthropic`, 2026-06-15 01:03), focused cognition **ran**
(`focused_synthesis_timing working_set_chars=11426 evidence_item_count=17`, source_types
`fresh_evidence,memory_context`). A freshly-fetched web block was present and contained
(`web_containment_applied path=dispatcher chars=2552 balanced=True`). Yet the reply repeated
Maez's **own earlier fabricated answer** ("Claude Corps", "Mythos 5 export controls") nearly
verbatim. Root cause: that earlier reply had been stored at owner-grade trust and re-entered
the evidence set as `memory_context`, where it beat the fresh block.

The trust-tier rail already exists end-to-end (`TrustTier` enum
`covenant > lived > observed > untrusted`, `memory/memory_manager.py:90-109`; tier travels
`metadata → RecallItem.trust_tier (core/brain/brain_loop.py:156) → EvidenceItem.origin_trust
(core/routing/focused_cognition.py:820)`; nightly consolidation already drops `untrusted`,
`memory/memory_manager.py:242`). It is simply **mislabeled at store** and **unenforced at
recall**:

1. **Store mislabel** — `daemon/maez_daemon.py:7230-7234` writes one combined record
   `"the owner (X): {text}\nMaez: {reply}"` with `provenance_source="user_utterance"`,
   `trust_tier="lived"`. Maez's reply inherits owner-grade trust. (A code NOTE at
   `:7227-7229` already flags the record as mixed-origin, but nothing acts on it.)
2. **Recall non-enforcement** — `origin_trust` reaches the `EvidenceItem`, but **nothing at
   focused-assembly time deweights or excludes by tier/provenance**. Fresh is ranked first
   (`focused_cognition.py:49`) and `origin_trust` is rendered, yet that proved insufficient:
   the model still believed the confident `lived` self-claim.

## Covenant frame

- **Honest-ingestion immune system** ([[feedback_honest_ingestion_immune_system]]): the
  unverified self-claim may **enter** the raw store (it happened — honest record) but must
  never become **trusted, recallable-as-fact selfhood** without passing the immune system.
- **Deweight, not delete** ([[feedback_forgetting_is_deweighting_not_deletion]]): the raw
  record persists; we only keep the self-claim out of the *trusted competing evidence set*.
- **Owner's words protected:** the owner's verified utterance stays `lived` even on
  web-grounded turns — never collaterally deweighted.
- **Receipt is proof** ([[feedback_witnessable_receipt_for_prompt_boundary]],
  [[feedback_visible_substrate_state_not_chain_of_thought]]): content-light receipts witness
  that the hygiene fired on the live path.

## Resolved design decisions

| Crux | Decision |
|---|---|
| **Trust signal** | A reply is untrusted-as-future-memory **iff the turn drew on fresh web/tool evidence** (`fresh_evidence_count > 0`). Pure owner-fact replies stay `lived`. |
| **Tagging unit** | **Split only when web-grounded.** Non-web-grounded turns keep the single combined `lived` record unchanged. |
| **Recall behavior** | **Exclude** self-web-claims from the competing evidence set **when fresh evidence is present**; **keep + visibly label** them when no fresh is present. |
| **Filter scope** | **Self-authored only** (by provenance), not all `untrusted`. Prior external-web observations are untouched. |

### Spec constraint 1 — new provenance source

Add **`ProvenanceSource.SELF_WEB_CLAIM`**, defaulting to `TrustTier.UNTRUSTED` in
`_DEFAULT_TIER_BY_SOURCE` (`memory/memory_manager.py:102-109`). Do **not** reuse
`CLAUDE_TIER_RESPONSE` — that means a frontier/subscription-model response ("an external model
said this"), which is a **different immune response** from "Maez interpreted web evidence and
said this." Recall targets `SELF_WEB_CLAIM` precisely.

### Spec constraint 2 — `provenance_source` must be threaded (Task-0 wiring, not an assumption)

Today **only `trust_tier` travels** the structured focused recall path; `provenance_source`
is rendered in some memory prompt paths but is **not** carried on focused's structured
`RecallItem`. The recall filter targets self-authored provenance, so the plan **must prove and
wire** the full chain before relying on it:

```
memory metadata.provenance_source
  → recall_for_telegram_living() row metadata
  → RecallItem.provenance_source            (NEW field; core/brain/brain_loop.py:117-159)
  → EvidenceItem.origin_provenance          (NEW field; core/routing/focused_cognition.py:810-882)
  → focused-assembly exclusion filter
```

This is a Task-0 proof/wiring item: confirm each hop carries `provenance_source` (add the
field where missing) **before** the filter is wired.

## Section 1 — Store side: two linked records when web-grounded

At the turn-store seam (`daemon/maez_daemon.py:7230-7234`), gated by the feature flag and
`web_grounded = (fresh_evidence_count > 0)`:

- **Non-web-grounded turn, or flag off:** unchanged — one combined record
  `"the owner (X): {text}\nMaez: {reply}"`, `provenance_source="user_utterance"`,
  `trust_tier="lived"`. (Q→A pairing preserved; zero blast radius on the common path.)
- **Web-grounded turn (flag on):** **do not write the old combined record.** Write **two
  linked records** instead (a shared `turn_link_id` in metadata preserves the Q→A pairing):
  - **owner utterance** → `"the owner (X): {text}"`, `provenance_source="user_utterance"`,
    `trust_tier="lived"`.
  - **Maez reply** → `"Maez: {reply}"`, `provenance_source="self_web_claim"`,
    `trust_tier="untrusted"`.

Writing two records *instead of* (never *in addition to*) the combined record prevents the
duplicate-storage failure where the old `lived` combined record coexists with the split
records and the reply text re-enters as `lived` anyway.

**Feasibility proof (plan Task-0):** confirm `fresh_evidence_count` (or an equivalent
"this turn used fresh evidence" signal) is reachable at the store call site. If not directly
available, thread it from the dispatcher/focused result; if that is invasive, STOP and revisit
the seam rather than forcing it.

## Section 2 — Recall side: exclude self-claims when fresh present

At the memory_context assembly in `core/routing/focused_cognition.py:810-829`, after the
`provenance_source` chain (constraint 2) is wired:

- Compute `fresh_present` = the working set contains at least one `fresh_evidence` item.
- For each candidate `memory_context` recall item:
  - `fresh_present AND item.origin_provenance == "self_web_claim"` → **exclude** (do not add
    to the evidence set). Fresh wins outright.
  - otherwise → **include**. A `self_web_claim` item with **no** fresh present is kept and
    **hard-labeled** untrusted/self-web-claim in the rendered evidence line (so Maez retains
    continuity — "I said this before, unverified" — but never asserts it as established fact).
- **Scope is self-authored only:** items whose provenance is *not* `self_web_claim` (e.g.
  prior `external_web` observations, owner utterances) are never excluded by this filter.

The existing fresh-first ranking and `origin_trust` rendering remain; this filter sits on top.

## Section 3 — Witness (content-light receipts)

Per the session's "receipt is proof" discipline, two `logger.info` receipts (no raw page/reply
text — hashes/counts only):

- **Store** (when the split-store fires): `self_claim_stored web_grounded=True
  provenance=self_web_claim trust_tier=untrusted reply_chars=<n> turn_link_id=<id>`.
- **Recall** (when the filter runs): `recall_hygiene fresh_present=<bool>
  excluded_self_claims=<n> kept_memory_items=<m>`. The `excluded_self_claims` count on a live
  fresh+memory turn is the **load-bearing witness** that the hygiene fired on the real path.

Flag off → neither receipt appears (byte-identical behavior).

## Section 4 — Flag, testing, rail

**Flag:** `MAEZ_SELF_CLAIM_HYGIENE_ENABLED` (`strict_env_flag`, `{1,true,yes,on}`).
Off = byte-identical (single combined store, no recall filter, no receipts).

**Testing (TDD, fakes only):**
- *Store:* web-grounded turn → two linked records (owner `lived` + reply `self_web_claim`/
  `untrusted`); non-web-grounded → one combined `lived` record; flag off → always combined;
  **no duplicate** — the combined record is absent whenever the split fires.
- *Provenance travel (constraint 2):* `provenance_source` survives `metadata → RecallItem →
  EvidenceItem` (assert the new fields carry it).
- *Recall:* `fresh_present` + `self_web_claim` → excluded; no-fresh + `self_web_claim` →
  kept + labeled; `external_web` `untrusted` memory with fresh present → **not** excluded
  (scope proof); flag off → no exclusion.
- *Receipts:* store-receipt fields; recall-receipt `excluded_self_claims` count matches the
  number actually dropped from the assembled set.

**Covenant rail:** raw store is never deleted from (deweight-not-delete); the unverified
self-claim enters the body but is barred from trusted recall (immune system); owner utterances
keep `lived` on every path; the receipts make the hygiene witnessable-as-true, never merely
asserted.

## Scope (explicit)

- **IN:** new `SELF_WEB_CLAIM` provenance; split-when-web-grounded store (two linked records);
  `provenance_source` threading (Task-0); the fresh-present exclusion filter + no-fresh
  keep/label; two receipts; the flag; tests.
- **OUT (separate arcs — different wound, different proof):**
  - **Thread A** — a real support checker (verify cited evidence *supports* the claim, beyond
    `check_groundedness`'s label-exists test at `focused_cognition.py:1401`).
  - **Thread B** — general fresh-vs-memory *conflict resolution* (when memory and fresh
    disagree on substance). Thread C only removes *self-authored unverified* memory from the
    fresh contest; it does not adjudicate trusted-memory-vs-fresh conflicts.
  - Generalizing the recall filter to **all** `untrusted` memory (we deliberately scoped to
    self-authored).
  - Re-tagging the **already-stored** mislabeled self-replies in ChromaDB (a backfill/eviction
    is its own decision; this spec governs new turns going forward).
