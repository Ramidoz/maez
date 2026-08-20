# Held-now repair — Phase 1 design (pass 3, after gate round 2: REVISE)

2026-08-20. Round 2 resolved B2/B3/B8-flagging and upheld five
blockers, two of them exposing pass-2 mechanisms as overreach: the
anchor reservation was arithmetically impossible against the pinned
360-char budget test, and my writer inventory listed 5 of 10 real
callsites (re-enumerated myself: 10 confirmed). Pass 3 narrows the
mechanisms instead of defending them.

Defect and levers: unchanged (pass 1/2, with gate-corrected anchors).

## Contract, pass 3

**Principle unchanged: the now is HELD, not classifier-gated — held
last when budget bites, provenance-honest, scope-limited.**

### C1. Flags + compatibility promise
`MAEZ_HELD_NOW_SHADOW` / `MAEZ_HELD_NOW_ENABLED`, both default OFF.
With both off, reply bytes identical on existing fixtures; permitted
differences: (i) additive metadata on new writes (all 10 writer sites),
(ii) new WARNING/receipt lines, (iii) nothing else. C5 and C4-read are
under ENABLED. The pinned 360-char budget test
(`test_focused_cognition.py:842,851`) is byte-preserved with flags off.

### C2. Anchor presence and rendered count (round-2 note folded)
Under ENABLED, when a working set is constructed and history is
non-empty: seed `limit_pairs=3`. Rendered-pairs promise, stated
without self-contradiction: **ordinary focused turns render 3;
authoritative/date-cue turns render 2; lean renders 2.** The
intra-turn-echo carve-out stands. Old-flag subsumption and the
old-flag × HELD_NOW test matrix stand.

### C3. Rank: unchanged non-goal. Telemetry note stands
(citation_coverage denominators grow; baselines shift downward
without regression).

### C4. Scoping — the COMPLETE writer matrix (B7)
All **10** `store_telegram` callsites stamp `origin_surface` +
`chat_id` (additive kwargs on `store_telegram` itself, default None →
no stamp, so untouched callers degrade to legacy rows, but we touch
all 10):

| # | Callsite | origin_surface | chat_id |
|---|---|---|---|
| 1 | `daemon/maez_daemon.py:9502` (live turn) | turn `source` | turn chat_id |
| 2 | `daemon/maez_daemon.py:9832` (voice) | `voice` | `voice` |
| 3 | `daemon/maez_daemon.py:10003` (morning briefing) | `briefing` | `briefing` |
| 4 | `skills/web_interface.py:7401` (owner web) | `web_owner` | `web_owner` |
| 5 | `gui.py:685` | `gui` | `gui` |
| 6 | `skills/telegram_voice.py:1220` | `telegram_legacy` | tg chat_id if in scope else `telegram_legacy` |
| 7 | `skills/telegram_voice.py:1368` | `telegram_legacy` | same rule |
| 8 | `skills/telegram_voice.py:1502` | `telegram_legacy` | same rule |
| 9 | `skills/telegram_voice.py:3609` | `telegram_legacy` | same rule |
| 10 | `skills/telegram_voice.py:4235` | `telegram_legacy` | same rule |

Reader filtering (ENABLED only): both keys, legacy-wildcard for
unstamped rows. Both held-now read sites pass scope
(`maez_adapter.py:742`, `:1081`). Test-fake kwarg migration in scope.

### C5. Split-store rejoin — SEPARATE function, scoped blast radius (B5)
The coalescer is **not** installed inside `get_telegram_exchanges`
(8 production callers — too wide). New
`get_telegram_exchanges_coalesced(...)`, called ONLY by the two
held-now read sites under ENABLED: fetch with metadata → coalesce via
`turn_link_id` → last-N logical exchanges. Orphan half → skip +
`held_now_orphan_row` WARNING.

**Acknowledged, unchanged bypasses:** `_recent_telegram_exchange_rows`
and `_latest_telegram_exchange_rows` still see split halves — they feed
recall supplements, not the held now; their behavior today is their
behavior after, and fixing them is out of scope (recorded as a
follow-up seam).

Provenance (B6, corrected): the exclusion predicate at
`focused_cognition.py:1303` tests **origin_provenance**, not
trust_tier. Anchor seeds therefore carry BOTH `origin_provenance` and
`trust_tier`. Ruling for mixed halves: **worst-half governs** — a
coalesced pair whose reply half is `self_web_claim/untrusted` stamps
the anchor item `origin_provenance="self_web_claim"`, so the existing
exclusion applies conservatively. A pinned test proves an untrusted
reply half cannot enter as an unlabeled anchor.

### C6. Fall-open WARNING — unchanged.

### C7. Receipts — seam confirmed, eligibility defined (round-2 note)
Seam: the reply-mode resolution site (`daemon/maez_daemon.py:8083` /
`:8161` region) where dialogue_state and chat_history are both in
scope. **Eligible turn** = an owner text turn that reaches reply-mode
resolution; TOOL-authoritative short-circuits, intra-turn ECHO, and
HONEST_EMPTY outcomes are ineligible and receipt
`held_now_shadow mode=ineligible reason=<class>` instead — the
receipt line always fires exactly once per owner turn.

### C8. Anchor budget — truncate-LAST ordering, no reservation (B4)
The pass-2 reservation is withdrawn (arithmetically impossible under
the existing budget definition; contradicted a pinned test). Replaced
with an ordering guarantee that is scale-free:

- Per-message cap: 900 chars, head-preserving, applied in
  `dialogue_anchor_items`. Capped text feeds durable-ID computation
  (round-2 note) so IDs match what is rendered.
- **Truncation order under ENABLED:** when the budget forces cuts,
  anchor texts are reduced only AFTER `memory_context` and
  `memory_evidence` items, and the NEWEST anchor pair is the last
  item in the entire set to be emptied. Fresh evidence /
  web_context are never displaced by anchors (rank unchanged).
- At any budget ≥ one capped pair (~1.8K), at least one pair
  survives. Below that (e.g. the 360-char pinned case) behavior is:
  flags off → byte-identical; ENABLED → newest pair truncated to fit,
  possibly to a stub, never silently dropped while any memory_* item
  retains chars.
- Long-turn tests: 20K pairs and a 12K owner question assert
  `pairs_rendered >= 1` with non-empty text and no fresh-evidence
  displacement.

## Witness plan (B1, corrected)
Both legs assert `reply_path=focused` from the recall_outcome line
(`daemon/maez_daemon.py:9256` region); a legacy-path run is VOID for
either leg. The discriminator is NOT the reply text: it is the
**evidence map** — the sentinel pair's durable ID present in the
focused working set (`focused_cognition.py:2068` region) in the
ENABLED leg, absent (or truncated out) in the OFF leg. Reply-text
success in the OFF leg is expected and irrelevant (legacy history can
answer; that is not what this repair changes). Sentinel novelty
pre-check, filler pairs, and the scripted shape stand from pass 2.
Prediction adds the orphan exception: zero-pair sets occur only on
empty history, echo-degenerate turns, or all-orphan windows (each
orphan WARNING-logged).

## Non-goals — unchanged, plus: the two bypass helpers (C5), and any
change to `evidence_recency_days` (the 14-day wall belongs to the
weighting arc; measured in docs/eval/telegram_recall_v0_20260820.md).
