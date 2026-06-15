# Self-Web-Claim Recall Hygiene — STOP-at-Gate Handoff (content-honesty Thread C)

**Branch:** `self-web-claim-hygiene` (main local-only/unpushed — NO push performed).
**Status:** built + per-task two-stage reviewed + whole-branch reviewed. **Asleep**
(`MAEZ_SELF_CLAIM_HYGIENE_ENABLED` unset → off = byte-identical). Awaiting Codex cross-lane
review, then the owner's sovereign breath (flag flip + restart + live witness).
**Spec:** `docs/superpowers/specs/2026-06-15-self-web-claim-recall-hygiene-design.md` (@85ba87c).
**Plan:** `docs/superpowers/plans/2026-06-15-self-web-claim-recall-hygiene.md`.

## What this fixes (the wound, verified live earlier)

On a Telegram turn, focused cognition ran with fresh web present, yet Maez repeated its own
earlier **fabricated** "news about Anthropic" reply ("Claude Corps", "Mythos 5 export controls")
because that reply had been stored at owner-grade `lived` trust and re-entered the evidence set,
beating the fresh block. This slice tags Maez's own web-grounded replies `self_web_claim`
(untrusted) at store, and excludes them from the evidence set when fresh evidence is present —
so fresh wins. Forward-only (see caveat).

## Commits (oldest → newest)

| SHA | What |
|---|---|
| `83c3286` | docs(proof): Task-0 feasibility (GO) |
| `7318c6e` | docs(plan): Task-0 correction — web_grounded from evidence-state markers |
| `aef3199` | feat(memory): `SELF_WEB_CLAIM` provenance (untrusted) |
| `6b8a005` | feat(recall): thread `provenance_source` → RecallItem → EvidenceItem |
| `700a37f` | feat(daemon): split store into two linked records on web-grounded turns |
| `4f31f5f` | fix(m1): owner-id-only promotion guard |
| `89a7ba7` | feat(focused): exclude self-web-claims when fresh present |
| `e5fdbe5` | fix(focused): gate the self-web-claim label on the flag (flag-off byte-identical) |
| `855f9d9` | test: flag-off byte-identical sweep |

## Verification (green)

- Feature suite `tests.test_self_web_claim_hygiene`: **21 OK**.
- Consolidated regression (focused / layer1 / external_sources / m1_daemon_wiring /
  m1_lived_episode_promotion / memory_provenance / memory_manager): **192 OK**.
- ruff: clean on all touched production files.
- Whole-branch review verdict: **READY FOR GATE** — the `self_web_claim` string is connected
  end-to-end (store-write → recall-filter, not a silent no-op); laundering boundary closed;
  flag-off byte-identical at all six seams.

## The end-to-end invariant (what the gate must trust)

`self_web_claim` is the identical literal at every hop: store writes
`provenance_source="self_web_claim"` → `meta["provenance_source"]` → `RecallItem.provenance_source`
→ `EvidenceItem.origin_provenance` → filter checks `== "self_web_claim"`. The reply id can NEVER
reach M1 `source_memory_ids` (structurally gated by `is_owner_record` + the owner-id-only guard;
episode body is structural-only). Kept-on-no-fresh items stay `untrusted` + hard-labeled, so they
can't outrank fresh on a later turn either.

## Codex cross-lane review — anchors (please review BEFORE any owner breath)

This touches the honesty/memory core. Independent-lane anchors:
1. `SELF_WEB_CLAIM` defaults `untrusted` and is distinct from `claude_tier_response`.
2. Store writes **two linked records instead of** the combined one (no duplicate); the reply is
   `self_web_claim`/`untrusted`; `_m1_raw_memory_id` binds to the **owner** record.
3. M1 promotion receives the owner id only — never the reply id, never both.
4. `web_grounded` signal = `{"fresh evidence","web search results"} & _evidence_state.marker_labels`
   (NOT `web_context` — that was empty on the dispatcher path; see Task-0 proof).
5. Recall excludes `self_web_claim` ONLY when fresh present; scope self-authored only
   (`external_web` untrusted memory is NOT excluded).
6. Off = byte-identical at all six seams (store / M1 / filter / 2 receipts / label).

## Owner sovereign breath (Claude does NOT do these)

```bash
# 1. Arm the flag (house strict-parser style) — edit ~/.config/maez/model.env, add:
#    MAEZ_SELF_CLAIM_HYGIENE_ENABLED=1
# 2. Restart:
systemctl --user restart maez.service && systemctl --user is-active maez.service
```

## Live witness — forward-only (prove it fired on a NEW turn)

The receipts land in `logs/maez.log` (the `maez`/`maez.focused` loggers — a `journalctl | grep`
would show nothing; grep the FILE).

1. **Trigger a NEW web-grounded turn** on Telegram, e.g. `news about Anthropic` (must actually
   fetch — look for "searching the web…"/a `/receipts` line).
2. **Store receipt:**
   ```bash
   date
   grep -h 'self_claim_stored' /home/rohit/maez/logs/maez.log* | tail -5
   ```
   Expect `self_claim_stored web_grounded=True provenance=self_web_claim trust_tier=untrusted
   reply_chars=<n> turn_link_id=<hex>` with a timestamp AFTER the restart.
3. **Recall receipt** (ask the SAME question again, or a follow-up that re-recalls the reply, while
   a fresh fetch happens):
   ```bash
   grep -h 'recall_hygiene' /home/rohit/maez/logs/maez.log* | tail -5
   ```
   Expect a row with `fresh_present=True excluded_self_claims>=1` — **the `excluded_self_claims`
   count ≥ 1 is the load-bearing proof** the self-claim was dropped from the evidence set on the
   live path.
4. **Behavior sanity (secondary):** the second answer should track the fresh web result rather
   than re-asserting the prior invented specifics. (The receipt is the proof; behavior is sanity.)

## Forward-only caveat (do NOT overclaim)

This slice changes **new** turns only. It does **not** heal the already-stored `lived` Anthropic
false record sitting in ChromaDB. Until that record ages out via consolidation or is evicted by a
separate owner-approved backfill, it can still re-surface. **Do NOT claim "the Anthropic wound is
healed" from this slice alone.** The slice's claim is: *self-web-claims from now on are tagged and
excluded*, proven by the receipts on a fresh turn.

## Recommended follow-ups (not in this slice)

1. **Shared constant for the web-grounded labels (drift guard).** The daemon hardcodes
   `{"fresh evidence","web search results"}`, duplicated from `core/routing/evidence_state.py`.
   They MATCH today (feature is live), but a future rename in `evidence_state.py` would silently
   turn the split into a no-op — the exact failure class Task 0 caught. Export a shared frozenset
   (e.g. `WEB_GROUNDED_LABELS`) + a coherence test asserting `turn_evidence_state` can actually
   produce them. Small, high-value hardening.
2. **`RecallBlock.to_dict()` awareness:** now emits `"provenance_source"` unconditionally
   (additive). Not surfaced in Maez's prompt or stored records, so prompt/record byte-identity
   holds — but any consumer that byte-compares that dict should be aware.
3. **The other content-honesty threads** (separate arcs): Thread A (real support checker beyond
   `check_groundedness`'s label-exists test) and Thread B (general fresh-vs-memory conflict).

## Revert (one breath)

`MAEZ_SELF_CLAIM_HYGIENE_ENABLED=0` (or remove the line) + `systemctl --user restart maez.service`.
Off is byte-identical, so revert is total.
