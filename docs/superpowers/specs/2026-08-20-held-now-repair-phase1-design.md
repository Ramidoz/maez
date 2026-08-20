# Held-now repair — Phase 1 design (pass 6, after gate round 5: REVISE, 4 mechanical blockers)

Round 5 froze the core: C1/C4/C5/C6 and C7's placement carry no
contradiction; the tuple discriminator is clean (no remaining OFF-leg
route). Four mechanical blockers folded below: two-domain rendered
counts; protected occupancy from the TURN-SPECIFIC ranked sequence
(not a static cut class); the exactly-once receipt carries final
reply_path + turn_kind + predicates itself; each live sampling attempt
rebuilds a full window with an attempt-specific sentinel. Plus the
containment-overhead note (allocator arithmetic must include
post-budget wrapper overhead).

---

Round 4 PASSED C5 (dedicated carrier; V2 signature ripple noted as
in-scope) and C7 (whole-turn finally seam verified wrappable). Three
blockers remain, folded below: the witness must pin the old anchor
flag OFF; "independent fresh evidence" was not deterministically
forceable on a live Telegram script; and C8's twin guarantees
(fresh-never-displaced + one-pair floor) were unsatisfiable in one
domain predicate. Pass 5: sampling witness protocol, and the anchor
floor YIELDS to evidence precedence with its own receipt reason.

---
# (pass 4 header retained below for lineage)
# Held-now repair — Phase 1 design (pass 4, after gate round 3: REVISE)

2026-08-20. Round 3 resolved B7 (writer matrix confirmed, 10 sites)
and B6's direction (with a field-name correction), and upheld/raised
four: the witness needed four explicit assertions and a receipt join;
the C8 arithmetic was STILL impossible for my own 12K-question test
(the owner question consumes the budget before anchors see a char —
`focused_cognition.py:1149`, `:65`); the coalesced list at the two
adapter fetches leaks to four non-held-now consumers; and the C7
exactly-once receipt cannot live at the reply-mode seam (pre-seam
clinical/camera returns at `maez_daemon.py:7114`, post-resolution
SELF_STATUS overrides at `:8452`). Pass 4 accepts the arithmetic,
splits the history carrier, and moves the receipt to a whole-turn
seam.

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

### C5. Split-store rejoin — DEDICATED CARRIER, not a swapped list (B5, round 3)
Round 3 showed the pass-3 shape still leaked: the two adapter fetch
sites feed brain_loop planner history, legacy synthesis threading,
routing-comprehension tails, and protected-refusal handling — swapping
their list changes four non-held-now consumers. Corrected shape:

- `get_telegram_exchanges_coalesced(...)` exists as pass 3 defined it,
  BUT the adapter keeps fetching the RAW list exactly as today and
  passes it everywhere it goes today, unchanged.
- The coalesced list travels in a NEW, separate parameter
  (`held_now_history`) threaded from the adapter through
  `handle_message` into working-set anchor construction ONLY. No other
  consumer sees it. Under ENABLED; None otherwise.
- Orphan half → skip + `held_now_orphan_row` WARNING. Pinned
  starvation test (gate note): >N newest orphan rows ahead of N intact
  exchanges must still yield N logical exchanges.

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

### C7. Receipts — whole-turn seam (round-3 NEW blocker)
The reply-mode seam cannot honor exactly-once: clinical/camera turns
return BEFORE it (`maez_daemon.py:7114`) and post-resolution
intercepts can override the mode AFTER it (`:8452`). Corrected:

- The receipt is emitted from a **whole-turn finally seam** wrapping
  the owner-turn body of `handle_message`: exactly once per owner text
  turn that ENTERS handle_message, regardless of exit path.
- The counterfactual evaluation still runs at reply-mode resolution
  when reached, and stashes its numbers on the turn trace; the finally
  seam emits them, or `mode=ineligible reason=<class>` where class ∈
  {pre_seam_return, tool_mode, echo_mode, honest_empty_mode,
  post_resolution_override, error} — ReplyMode values
  (`reply_mode.py:17`) for the mode classes, plus the two boundary
  classes. (Gate note honored: ReplyMode and OutcomeClass are separate
  taxonomies; the receipt names modes, never outcome classes.)
- **Round-5 blocker 3 — the receipt is self-sufficient for the
  witness:** it carries `final_reply_path` (the path actually taken,
  distinguishing a FOCUSED decision that fell back to legacy at
  `maez_daemon.py:8686/8756`), `turn_kind`, the three ordinary-turn
  predicates (needs_dialogue / fail_safe_legacy / date_cue), the
  domain verdict, and the focused row ID when one exists. No join to
  recall_outcome is required to qualify a sampling attempt; a shared
  per-turn trace id is included anyway for cross-checking.

### C8. Anchor budget — bounded promise, class-ordered cuts (B4, round 3)
Round 3 proved the promise must be bounded by arithmetic: the owner
question consumes the budget BEFORE item text gets any allowance
(`focused_cognition.py:1149`; total budget 12,000 at `:65`), so no
ordering rule can guarantee a pair under a 12K question. The pass-3
long-turn test was impossible as specified and is withdrawn. Bounded
contract:

- **Domains (round-5 corrected): TWO, not one.**
  - **Full-count domain:** post-question, post-protected-occupancy,
    post-overhead budget admits 3/2/2 pairs at their allowance → C2's
    rendered-count promise applies in full.
  - **Floor domain:** the same computed budget admits ≥ one capped
    pair (1,800) but not the full count → the promise degrades
    explicitly to `pairs_rendered >= 1` with the NEWEST pair
    surviving; older pairs empty first. Receipt records which domain
    held.
  - Below floor → anchor-less with `reason=question_consumed_budget`
    or `reason=higher_rank_consumed_budget`.
- **Protected occupancy is derived from the TURN-SPECIFIC ranked
  sequence, never a static class list** (round-5 blocker 2): anything
  the turn's ranking places ABOVE the anchors — including confirmed
  memory on date-cue turns (`focused_cognition.py:1097`) — is
  protected and counts as occupancy in the domain predicate; only
  items ranked BELOW the anchors are pre-anchor cut material. C3
  (rank unchanged) is thereby honored by construction.
- **Overhead arithmetic includes post-budget containment** (round-5
  note): web-containment wrappers and standing instruction are added
  after budgeting and outside the truncation budget
  (`focused_cognition.py:348`, `:1348`); the allocator receives the
  containment overhead policy (or returns allocation metadata for
  final reconciliation) so domain receipts are computed from complete
  arithmetic.
- Ranking precedes budgeting (`:1320`), so all of the above is
  computable at the allocator without reordering assembly. **The
  precedence ruling stands: turn-ranked-higher evidence is NEVER
  displaced by anchors; the anchor floor is the guarantee that
  yields.**
- Per-message cap 900 chars in `dialogue_anchor_items`. The durable
  ID is computed from the FINAL rendered bytes — recomputed after any
  working-set budget truncation — so the evidence map always matches
  what the model saw (round-3 correction: capping at seed time is not
  enough).
- **Class-ordered allocator under ENABLED only** (today's truncator is
  a flat equal-allowance loop, `:1160`; ranking precedes budgeting at
  `:1320`, so a class-aware allocator slots in without reordering
  assembly): within the domain, cuts land on `memory_context` →
  `memory_evidence` → older anchors → newest anchor, and an item
  emptied by the allocator is REMOVED from the set and its ID from
  the evidence map (round-3 correction: emptied-but-present items
  poisoned the witness discriminator). Fresh/web items keep their
  rank; they are never displaced by anchors — reconciled with
  "newest-anchor-last" by the domain bound: when both cannot fit, the
  domain condition has failed and the anchor guarantee is void.
- Flags off → byte-identical, including the 360-char pinned test.
- Long-turn tests (revised): 20K pairs under a normal question assert
  `pairs_rendered >= 1` non-empty; a 12K question asserts the
  anchor-less receipt reason and no crash and no fresh displacement.

## Witness plan (round-4 corrections folded: pinned flag + sampling)
Both legs assert `reply_path=focused`; a legacy-path run is VOID.

- **Round-4 blocker 1:** BOTH legs pin and assert
  `MAEZ_LIVE_THREAD_ANCHOR` OFF (the old flag admits anchors on
  ordinary turns before any classifier condition,
  `focused_cognition.py:1194`; the old-flag-ON cells live in the
  interaction test matrix, not the live witness).
- **Round-4 blocker 2 — the live legs are SAMPLING, not forcing.**
  "Independent fresh evidence" is not deterministically forceable on a
  live Telegram script (web_context depends on routing + non-empty
  results). Corrected protocol, two layers:
  1. **Deterministic layer (integration test, not live):** a pytest
     integration case constructs the turn with a synthetic
     fresh-evidence item, forces FOCUSED, and asserts the full
     discriminator both ways (ENABLED: tuple present; disabled:
     absent). This is where determinism lives.
  2. **Live layer (sampling):** each attempt is a COMPLETE rebuild
     (round-5 blocker 4): a freshly generated, freshly pre-checked
     sentinel + new filler pairs forming a full three-pair window,
     then the probe — so a void attempt's own exchanges can never
     slide a previous sentinel out of the window. The expected
     durable ID is attempt-specific. An attempt qualifies when its
     exactly-once receipt shows `final_reply_path=focused` AND
     `turn_kind=ordinary` AND all three predicates false; max 5
     attempts per leg, then the witness is recorded **BLOCKED — no
     live verdict obtained** (never PASS, and no allegation the
     implementation failed; activation certification stays withheld).
     Qualifying attempts assert the discriminator tuple.
- The probe is an ORDINARY turn by the assertions above; focused
  candidacy arises from whatever evidence the live turn genuinely
  carries — asserted from receipts, never assumed.
- The discriminator asserts the TUPLE (`source_type=dialogue_anchor`,
  expected durable ID) in the evidence map — never the ID alone.
  "Truncated out" language is withdrawn: under C8's correction an
  emptied item leaves the set AND the map, so presence/absence is
  clean.
- **Join:** the `held_now_shadow` receipt carries the focused row ID
  (the recorder's return value, currently ignored at
  `maez_daemon.py:8676`), joining the receipt to the persisted
  evidence-map row without touching the recall_outcome line.
- Reply-text success in the OFF leg is expected and irrelevant.
  Sentinel novelty pre-check, filler pairs, scripted shape stand.
  Zero-pair prediction: empty history, echo-degenerate turns,
  all-orphan windows (WARNING-logged), or out-of-domain budgets
  (`question_consumed_budget` receipts).

Implementation notes carried from rounds 3-4: seed `trust_tier` maps
to the rendered `origin_trust` field (`focused_cognition.py:287`)
while `origin_provenance` is carried independently for the exclusion
predicate (`:1303`); telegram_voice scope values name
`update.effective_chat.id` with an explicit fallback; durable-ID
recomputation is scoped to allocator-truncated DIALOGUE ANCHORS only
(recalled items keep their IDs through truncation per the pinned
tests at `test_focused_cognition.py:826,848`); the C5 carrier's V2
signature ripple (`run_inbound_turn` second optional history value,
`inbound_core.py:207`, descriptor tests) is in build scope, and
disabled mode selects the existing raw chat_history — None is never
passed into assembly.

## Non-goals — unchanged, plus: the two bypass helpers (C5), and any
change to `evidence_recency_days` (the 14-day wall belongs to the
weighting arc; measured in docs/eval/telegram_recall_v0_20260820.md).

---

## BUILD LEDGER (2026-08-20/21)

Gate verdict BUILD MAY PROCEED (round 6). Landed:
- Commit A `5c2da46`: C4 write side (10/10 callsites stamped) + C5
  coalesced reader (scope filter, legacy wildcard, worst-half trust,
  orphan skip + starvation pin). 7 tests.
- Commit B `9569db5` + fix `a8b4d32`: C2 presence (3 pairs; [:2]
  authoritative; old flag subsumed), per-message 900 caps, positional
  two-domain allocator with typed metadata on WorkingSet, emptied→
  removed, anchor durable-ID recompute on allocator truncation, seed
  trust/provenance passthrough + hygiene-exclusion pin. 15 tests.
  (Logging-capture order-dependence found and fixed; batteries now
  gate on pytest exit codes.)
- Commit C `f4ae8e0`: C7 whole-turn wrapper (receipt state at entry,
  finally emission, _reply_path as authoritative final route, focused
  row-id captured) + C5 carrier threaded through inline adapter AND
  V2 inbound core (raw list untouched for all other consumers; None
  never enters assembly). 6 tests.
- Commit D: cockpit flag registry entries (T1/T2 with witness
  recipes), deterministic witness integration test (discriminator
  both ways, ordinary turn, old flag pinned; the blur case that
  motivated the pin is itself a test), old-flag×HELD_NOW matrix,
  long-turn cases (20K pairs; 12K question → anchor-less receipt).
  10 tests.

38 held-now tests total; ~190-test adjacent battery green, flags-off
byte-identical. NEXT: Codex gate on code → owner restarts services →
SHADOW ≥1 day → ENABLED + live sampling witness per this design.

---

## CODE GATE — FINAL (2026-08-21): SHADOW MAY GO LIVE

Eight rounds on code (after six on design). Fix commits: 7aaff34 (8
blockers: byte-identity leak, shadow blindness, holder race, receipt
schema, introspection contracts via decorator form, allocator rewrite,
V2 telegram-only, reader roles/ordering), 1ea3ac9 (tier order, label,
exact differential overhead, boundedness trapdoor), a2e1c20 (fail-
bounded estimation), c9c7874 (ground-truth reconciliation loop — the
structural close: measurement is the enforcement, estimation only a
guess), 8ffb744 (containment fails CLOSED, receipts fail LOUD),
f75e30f (containment decided exactly once), 600a708+d268203 (phantom
margin condition; biting exactly-once pins).

Round 7's final blocker was REFUTED in round 8 by instrumented witness
(calls_consumed=1 at HEAD; the divergence witness had run against the
parent). Telemetry ruling: projected-vs-realized overhead fields are
honest as-is; renaming to *_projected_chars is a follow-up note.

Verified at HEAD d268203: 110 gate-lane tests 108 pass + 2 flag skips;
~49 held-now tests in repo suites; four pre-existing
test_memory_integrity_invariant failures date to fb64925 (separate
item). NEXT: owner sets MAEZ_HELD_NOW_SHADOW=1, restarts maez.service,
lives a normal day; then ENABLED + the two-layer sampling witness.
