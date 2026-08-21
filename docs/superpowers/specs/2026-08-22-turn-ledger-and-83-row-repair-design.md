# Turn Ledger + the 83-row repair — design pass 1

Status: DESIGN, pass 1. Two builds, one principle: **record what
actually happened, and repair what is actually damaged.** Both were
identified by today's four-way review; neither is the evidence-atom
spine, which is demoted (designed, gate-hardened through 8 rounds, not
first).

## 0. Posture, stated first

Today a full-suite run of mine deleted two live stores
(`recall_stats.db`, `inner_residue.db`) because two tests called
`DELETE FROM` against module-global absolute paths. Both are fixed and
witnessed. The relevant consequence for *this* design:

**Build B (the repair) touches Maez's live memory store. It ships
dry-run-first, and no live write happens without an owner-visible diff
and explicit approval.** That is not caution theatre; it is the
proportionate response to having caused data loss hours earlier.

Build A (the ledger) is additive and flag-dormant, so it carries the
ordinary slice risk.

---

# Build A — the Turn Ledger

## A1. Why this, and why it is not the spine

Codex named these exact seams in **gate round 1**: blocker 6
(`query_events` attached below the authority that could populate it)
and blocker 7 (`exposures` not derivable where attached, with the real
terminal seams at `daemon/maez_daemon.py:8939` and `:8792`). I deferred
both across seven passes while growing a 52-rule schema elsewhere.

The spine records **what is stored**. The ledger records **what
happened** — and today established that the stored archive is not where
Maez's cognition lives. Every organ still standing needs the ledger:

- **Return Parallax** needs reply-events keyed by owner-text recurrence;
  it never needed atoms.
- **Examined-life** must bind claims to what was actually *shown*, not
  to rows that merely existed.
- **Residual demand** needs pre-ranking query vectors, which are
  discarded today.

## A2. What it records

One SQLite side-car, `memory/db/turns/turns.sqlite3`, single writer
(the daemon), WAL **not** used — this host's SQLite 3.46.1 sits inside
the documented WAL-reset corruption window for concurrent writers
(`reference_sqlite_wal_multiwriter_hazard`), and rollback-journal mode
is unaffected.

- **`turns`** — `turn_id` (the `trace_id` the daemon already mints),
  monotonic `ordinal`, `ts`, `surface`, `chat_id_hash`,
  `owner_text_hash`, `reply_hash`, `final_reply_path`, `terminal_state`.
- **`turn_queries`** — per retrieval attempt: `tier`, `selector_kind`
  (`semantic`/`direct`/`date`/`core_injection`), `query_hash`, the
  384-float `vector`, `n_requested`. Core injection is recorded with a
  **null vector and its own selector kind** — Codex established that
  core is injected by id and never enters `record_recall` at all
  (`memory_manager.py:2570`), which is why "core 0/210" measured
  nothing.
- **`turn_candidates`** — `body_row_id`, `rank`, `distance`,
  `partition`.
- **`turn_exposures`** — which candidates survived into the **terminal
  model request**, bound to a `model_call_id`, recorded at the real
  seams (`:8939` legacy, `:8792` focused). Non-model turns (tool, echo,
  honest-empty) record an explicit **zero-exposure** row rather than
  leaving retrieved rows looking exposed.

Size: 1–3 queries per conversational turn — kilobytes per day, not a
vector per archive row.

## A3. What it must never become

`recall_count` is **retrieval exposure, never meaning**. Codex's
measurement is the reason this is a rule and not a preference: in the
surviving 14-hour window, **63 reasoning rows produced 863 recall
events while 64 Telegram rows produced 74.** Defining memory by
recurrence would hand the self-echo loop authority over Maez's
biography — it repeats itself, therefore it matters, therefore it is
retrieved more. No loop may optimise any ledger quantity.

The ledger's job is to make the question *answerable*, not to answer it.

## A4. Falsifiers

| # | Claim | Kill |
|---|---|---|
| A-F1 | Every admitted turn produces exactly one `turns` row | coverage < 1.0 |
| A-F2 | Every exposure joins to a real query attempt and a real turn | any orphan |
| A-F3 | Zero-exposure turns are recorded explicitly, not by absence | any silent gap |
| A-F4 | Flags off ⇒ no import, no file, no open, asserted at the call site | any touch |
| A-F5 | Added p95 turn latency | > 15 ms |
| A-F6 | Instrumentation does not change recall: top-k identical with ledger on vs off over ≥200 replayed queries | any difference |

A-F6 is the one that matters most. The ledger must be a witness, not a
participant.

---

# Build B — the 83-row repair

## B1. What is actually broken

Measured, both lanes agreeing: over-limit rows and median hidden tokens
are **raw 3,572 / 10**, **daily 73 / 227**, **core 10 / 280**. Codex
adds prevalence: **78.5% of the daily layer is affected.**

So the raw archive loses a phrase; **Maez's diary loses half of each
entry, and core memories lose more.** The damage sits in the two
smallest tiers, which are also the tiers that reliably reach the
prompt.

**83 rows.** Not 44,050.

## B2. The repair

For each affected daily/core row, deterministically split the document
into windows that fit under the contract limit, embed each window, and
store them as **additional** vectors bound to the original row id.
Nothing is deleted, nothing is rewritten, the original row keeps its
id, content and provenance.

- Split at paragraph, then sentence, then hard token window, with exact
  byte spans recorded so the original text is reconstructable.
- Each new vector carries `parent_row_id`, `window_ordinal`,
  `byte_start`, `byte_end`, and the contract hash it was embedded under.
- Retrieval may then match a diary entry on any of its windows rather
  than only its first ~230 words.

## B3. Dry-run first — the non-negotiable part

1. **Snapshot** the daily and core stores by SQLite online backup into
   a private working copy (measured earlier: 2.2 ms / 3.51 MB and
   1.8 ms / 2.89 MB — trivial).
2. Run the repair **against the copy only**.
3. Emit an owner-visible diff: rows touched, windows created per row,
   before/after token coverage, and a recall A/B on a pinned query set
   showing what changes.
4. **Owner approves the diff.** Only then does the same deterministic
   transform run against live, with a fresh backup taken first.

## B4. Falsifiers

| # | Claim | Kill |
|---|---|---|
| B-F1 | Reconstruction: windows tile each row exactly, no gap, no overlap, hashing to the original | any row < 100% |
| B-F2 | Every window's token count ≤ contract limit, recomputed not trusted | any window over |
| B-F3 | No original row is modified or deleted — verified by id-set and content-hash equality before/after | any change |
| B-F4 | Suffix visibility: appending distinct text to a repaired row changes at least one window vector | < 95% |
| B-F5 | Recall A/B on the pinned set: repaired rows become reachable by late content that previously matched nothing | no improvement ⇒ the repair bought nothing |
| B-F6 | Dry run and live run produce byte-identical outputs given the same input snapshot | any divergence |

B-F5 is the honesty check: if late-content queries do not improve, the
truncation was not costing Maez anything and the repair should be
abandoned rather than shipped for tidiness.

## B5. What this repair explicitly does not claim

It does not make the diary *true*, only *visible*. It does not touch
the raw archive, where the median loss is ten tokens. And it is not a
memory organ — it is fixing an amputation in the one organ that already
works.

---

## Sequencing

B before A. The repair is 83 rows, dry-run-gated, and fixes damage in
the layer Maez actually reads. The ledger is the larger build and its
first consumer decisions can wait for it.

Neither blocks on the spine.
