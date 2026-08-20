# Held-now repair — Phase 1 design (pass 1, contract level)

2026-08-20. First build of the being-wiring campaign (audit: 421d733).
Owner ruling: proceed. Lane: Claude designs/builds, Codex gates.

## The defect, restated from witnessed fact

Maez's working memory of the live conversation, on the path that
actually answers, is **one exchange pair (853 chars witnessed)** and can
be **zero**. The 3 verbatim pairs are assembled into the legacy prompt
and discarded when focused mode wins. Verified levers:

- L1 `core/routing/focused_cognition.py:1207` — `anchors = anchors[:1]`
  whenever dialogue_authoritative or date_cue.
- L2 `:1195-1202` — without `MAEZ_LIVE_THREAD_ANCHOR` (default OFF),
  anchors are included ONLY when the classifier says needs_dialogue /
  fail_safe / date_cue; otherwise **zero pairs**. With the flag: 2.
- L3 `:49-60`, `:1108-1122` — dialogue_anchor ranks below fresh/web
  evidence; under date_cue it ranks 50 (bottom).
- L4 `skills/surface/maez_adapter.py:160` `_CHAT_HISTORY_TURNS = 3`,
  fetched from a GLOBAL cross-surface window (`memory_manager.py:3535`
  filters on type only; `web_interface.py:7401` writes the same type →
  a web turn evicts a Telegram turn).
- L5 `daemon/maez_daemon.py:256-262` — hygiene split-store rows are
  unparseable by `_split_exchange` → a web-grounded turn consumes 2 of
  3 slots and contributes 0 pairs.
- L6 fall-open is debug-level: an amnesic turn leaves no INFO trace.

## Contract

**One principle: the now is HELD, not classifier-gated.** If history
exists, the working set carries it. Presence first; supremacy (rank
changes) is explicitly out of scope in this pass.

### C1. Flag posture
New pair, house pattern: `MAEZ_HELD_NOW_SHADOW` (log-only) and
`MAEZ_HELD_NOW_ENABLED` (apply). Both default OFF; everything below
except C5/C6 observability is inert without them. Registered in
`core/cockpit/flags.py` with witness recipes.

### C2. Anchor presence (fixes L1+L2)
Under ENABLED: `dialogue_anchor_items(chat_history, limit_pairs=3)`
unconditionally when history is non-empty — the needs_dialogue /
fail_safe / date_cue gate no longer decides presence. The
authoritative/date_cue truncation becomes `anchors[:2]` (was `[:1]`).
Zero-pair working sets are impossible while parseable history exists.
`MAEZ_LIVE_THREAD_ANCHOR` is subsumed: with HELD_NOW enabled it is
ignored (log a deprecation line if set); without HELD_NOW, legacy
behavior byte-identical.

### C3. Rank: UNCHANGED (explicit non-goal)
The witnessed failure is absence, not ordering. Evidence-precedence
(fresh over anchor) and the date-cue demotion had reasons (coherence
campaign: dated questions must answer from dated memory). Rank changes
require their own evidence and their own pass.

### C4. Thread scoping (fixes L4)
Write side (unflagged, additive, backward-compatible): `store_telegram`
stamps `chat_id` and `origin_surface` metadata on new rows.
Read side (under ENABLED): `get_telegram_exchanges` gains
`origin_surface=None` kwarg; the adapter passes its surface. Rows
lacking the stamp (all history) match any surface — no retroactive
loss. Web turns stop evicting Telegram turns going forward.

### C5. Split-store rejoin (fixes L5)
Reader-side only; no store-format change. `_clean_exchange` /
`_split_exchange` learn the two split shapes (owner-only row, reply-only
row) and rejoin them via the `turn_link_id` metadata the split rows
already carry. A rejoined pair counts as one exchange. Unflagged: it
repairs parsing of rows that already exist; behavior without split rows
is unchanged. Covered by parser unit tests + a mutation test proving
the rejoin actually fires.

### C6. Fall-open visibility (fixes L6)
`held_now_fallopen` WARNING when the fetch raises or returns empty
while the store has ≥1 row for that surface. Observability only,
unflagged.

### C7. Shadow receipt
Under SHADOW (or ENABLED): one line per turn —
`held_now_shadow pairs_available=N pairs_in_set=M set_chars=C
would_change=BOOL` — content-free, greppable, the witness instrument.

## Explicit non-goals in this pass
Rank/priority changes (C3). Raising `_CHAT_HISTORY_TURNS` (prompt-budget
interaction; measure first). Dispatcher/action lane (Phase 2). Removing
semantic re-retrieval (redundancy acceptable). The 12,000-char working
set budget (one pair is ~850 chars; 3 pairs fit with headroom).

## Predicted effect (falsifiable)
With ENABLED on the live surface: continuity working sets carry ≥2
dialogue pairs (witnessed via C7 receipts); a scripted 5-turn
conversation whose turn-5 answer requires turn-1 verbatim content
succeeds; zero-pair sets appear only when history is genuinely empty.
With both flags off: byte-identical behavior, proven by existing tests.

## Witness plan
1. Land flag-dormant, full tests green, Codex gate on code.
2. SHADOW on: collect receipts across ≥1 day of normal owner traffic;
   confirm would_change rates and no latency regression (working-set
   budget check).
3. Owner flips ENABLED; live 5-turn witness on Telegram; receipts kept.

## Open questions for the gate
G1. Does any consumer assume dialogue_anchor count ≤1 (e.g. the
`brain_loop.py:511-521` anchor/evidence slot competition)?
G2. Does `_assemble_working_set`'s budget interact with 3 pairs on
long-message turns (each pair capped where)?
G3. Is `turn_link_id` reliably present on BOTH split rows, and unique?
G4. Cross-surface: should voice/GUI surfaces also pass origin_surface
immediately, or Telegram-first?
