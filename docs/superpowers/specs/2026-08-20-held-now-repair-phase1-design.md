# Held-now repair — Phase 1 design (pass 2, after gate round 1: REVISE)

2026-08-20. Pass 1 (c5dbb81) drew 8 blockers from the Codex gate — all
verified and upheld, including two defects in my own witness design
(the 5-turn test could pass without exercising the change, and turn 1
would not even be fetched under the 3-pair window). Pass 2 addresses
all eight. Corrected anchors per gate notes: date-rank branch begins at
`focused_cognition.py:1106`; the type-only global query is
`memory_manager.py:3540`; the live history fetch is
`maez_adapter.py:1081` (line 160 is only the constant).

## The defect (unchanged, restated)

Maez's working memory of the live conversation, on the answering path,
is one exchange pair and can be zero. Levers L1-L6 as in pass 1, with
gate corrections above.

## Contract, pass 2

**Principle: the now is HELD, not classifier-gated — with its budget
reserved and its provenance preserved.**

### C1. Flag posture (revised for B8)
`MAEZ_HELD_NOW_SHADOW` (counterfactual receipts only) and
`MAEZ_HELD_NOW_ENABLED` (apply). Both default OFF.

**Compatibility promise, stated precisely (B8):** with both flags off,
reply BYTES are identical on all existing fixtures, with exactly three
permitted differences: (i) additive metadata keys on NEW store writes
(C4 write side), (ii) new WARNING/receipt log lines (C6/C7 shadow),
(iii) nothing else. The C5 rejoin — which changes prompt-bearing
content — moves UNDER `ENABLED` (was unflagged in pass 1; gate B8
upheld). Split rows parse exactly as today when off.

### C2. Anchor presence and rendered count (revised for B3)
Under ENABLED, when history is non-empty and a working set is
constructed: `dialogue_anchor_items(limit_pairs=3)` unconditionally;
authoritative/date-cue truncation becomes `anchors[:2]` (was `[:1]`).
**The contract is RENDERED pairs, not seeded pairs:** the lean renderer
(`focused_cognition.py:734`, currently `anchors[:2]`) renders **2**
pairs minimum under ENABLED; full-focused renders 3. C7 receipts carry
BOTH `pairs_in_set` and `pairs_rendered` so the gap is observable.

**Explicit carve-out (B3):** the intra-turn-echo early return
(`focused_cognition.py:1188`) is retained — a degenerate case where the
"history" is the current turn echoed; documented as the one exception
to presence. "Unconditionally" in pass 1 overclaimed; withdrawn.

`MAEZ_LIVE_THREAD_ANCHOR` subsumption unchanged, PLUS (gate note): a
full old-flag × HELD_NOW interaction test matrix
(default/off/on × shadow/enabled × ordinary/direct), extending
`test_live_thread_anchor.py` pins rather than replacing them.

### C3. Rank: UNCHANGED (explicit non-goal) — unchanged from pass 1.
Telemetry expectation (gate note): with more anchors in the set,
`citation_coverage` denominators grow; recall-outcome baselines will
shift downward without any behavior regression. Recorded so the shift
is not misread as one.

### C4. Scoping: surface + chat, with a writer/reader matrix (B7)
Pass 1 under-specified. The promise is renamed **surface+chat scoping**.

Writer matrix — every `telegram_exchange` writer stamps
`origin_surface` and `chat_id` (additive, unflagged):

| Writer | origin_surface | chat_id source |
|---|---|---|
| `daemon/maez_daemon.py:9502` (live telegram) | the turn's `source` | the turn's chat_id (in scope at `:7006`) |
| `skills/web_interface.py:7401` (owner web /chat) | `web_owner` | fixed token `web_owner` (no native chat id) |
| `gui.py:681` | `gui` | fixed token `gui` |
| `daemon/maez_daemon.py:9832` (voice) | `voice` | fixed token `voice` |
| `skills/telegram_voice.py:4235` (legacy outbound path) | `telegram_legacy` | telegram chat_id if in scope, else fixed token |

Reader: `get_telegram_exchanges(origin_surface=None, chat_id=None)` —
filtering applies ONLY under ENABLED, by BOTH keys, with
**legacy-wildcard semantics**: rows missing the stamps match any scope
(no retroactive loss). BOTH read sites pass scope: the inbound-core
provider (`maez_adapter.py:742`) and the inline fetch (`:1081`).
Test-fake migration for the new kwargs is in scope (gate note).

### C5. Split-store rejoin — batch coalescer, provenance preserved (B5+B6)
Pass 1's parser-seam design was wrong (single-string parsers cannot see
sibling rows) and would have erased the provenance distinction that
motivated split storage. Redesigned:

- **Where:** inside `get_telegram_exchanges`, BEFORE logical-exchange
  limiting (`memory_manager.py:3556` currently sorts then slices raw
  rows): fetch rows WITH metadata → coalesce split pairs via
  `turn_link_id` → THEN take the last N **logical exchanges**. A split
  pair consumes ONE slot. Under ENABLED.
- **Incomplete links (gate note: writes are non-atomic, link id is
  per-invocation):** an orphan half is skipped with a WARNING
  (`held_now_orphan_row`), never rendered half-paired.
- **Provenance (B6):** the coalesced exchange carries
  `trust_tier = worst(halves)` and `provenance_source` of each half in
  its metadata. `dialogue_anchor_items` seeds gain a `trust_tier`
  passthrough so the existing `self_web_claim` exclusion logic
  (`focused_cognition.py:1303`) can act on anchors exactly as it acts
  on other items — the rejoined reply renders as conversational
  continuity, never as an unlabeled factual authority. A test pins
  that an untrusted reply half never bypasses the exclusion.

### C6. Fall-open visibility — unchanged (WARNING, unflagged; named in
the compatibility promise).

### C7. Receipts — counterfactual shadow seam (B2)
Pass 1's "one line per turn" was unimplementable where I placed it
(working-set assembly only runs when FOCUSED wins). Revised: a pure
counterfactual evaluator `held_now_shadow_eval(chat_history,
dialogue_state, ...)` → called from `handle_message` at the reply-mode
resolution site on EVERY eligible surface turn, mode selection and
reply untouched. Receipt:
`held_now_shadow mode=<focused|legacy> pairs_available=N
pairs_in_set=M pairs_rendered=R set_chars=C would_change=BOOL`.
Under SHADOW or ENABLED.

### C8 (new, B4). Anchor budget: reserved, capped, never emptied
Long messages break pass 1's guarantee (gate measured: three 20K-char
pairs → anchors truncated to ~3K each; a 12K owner question → every
anchor EMPTIED, then lean drops empty anchors). Contract:

- Per-message cap inside `dialogue_anchor_items`: 900 chars per
  message, head-preserving with ` ...[truncated]` (planner convention,
  `_MAX_EXCHANGE_CHARS=800` adjacent precedent). 3 pairs ≤ ~5.5K.
- **Reserved anchor budget:** the working-set assembler reserves
  `min(3600, anchor_total)` chars for dialogue anchors BEFORE other
  classes consume budget; anchors are truncated only within their
  reservation and are never emptied while non-empty input exists.
- Long-turn tests for lean AND full-focused: 20K-char pairs, 12K-char
  owner question, assert `pairs_rendered >= 2` and non-empty texts.

## Witness plan (rewritten, B1)

"Turn" = one owner message + one Maez reply (one exchange pair).
Window fact: only 3 prior pairs are fetched — the pass-1 "5-turn"
test was unfalsifiable as written and is withdrawn.

1. Land flag-dormant; full suite green; existing pins untouched;
   Codex gate on code.
2. SHADOW on live: ≥1 day of receipts; confirm `would_change` rate,
   `pairs_rendered` distribution, no latency regression.
3. ENABLED witness, scripted on Telegram:
   - Pair 1 plants a sentinel fact chosen to be (a) novel — zero
     archive hits, verified by a pre-check query — and (b) unlikely to
     embed near the probe phrasing, so semantic recall cannot supply it
     (receipt must show the sentinel entered via `dialogue_anchor`
     items, not memory tiers).
   - Pairs 2-3 are unrelated filler.
   - Probe (turn 4) requires the sentinel verbatim; phrased to be
     focused-eligible; the receipt must assert `mode=focused` — a
     legacy-path pass is a VOID witness, rerun, not a pass.
   - **Mutation leg:** same script with ENABLED off must FAIL to
     produce the sentinel (else the witness proved nothing). Both legs
     recorded.

## Non-goals — unchanged from pass 1 (rank changes, window size,
dispatcher/Phase-2, semantic-recall removal), plus: no atomicity fix
for the split write (orphan tolerance instead; a durable turn-spine is
Phase-4+ territory per the audit's Codex repair 1).

## Predicted effect (falsifiable, revised)
ENABLED on live: continuity working sets render ≥2 pairs (receipts);
the sentinel witness passes with `mode=focused` and fails with the
flag off; zero-pair sets occur only with empty/echo-degenerate history;
with both flags off, byte-identical replies on existing fixtures per
the narrowed promise.
