# Evidence-Atom Spine — design pass 2 (contract level)

Status: DESIGN, pass 2. No code. Pass 1 (commit 885192f) was **BLOCKED
by the Codex design gate with 12 numbered blockers**; this pass answers
all twelve. Gate round 2 pending. Origin: Codex foundation attack
(`2026-08-21-codex-foundation-attack.md`, 7d5743a). This spine is the
FIRST Phase-4 build item, preceding every organ.

Claude independently re-executed three of the gate's load-bearing
claims before accepting them (house rule: no rubber-stamping):
write-bypass audit baseline **RED confirmed** (1 failure,
`core/eval/telegram_corpus.py:160`); backup routing confirmed — only
the literal filename `chroma.sqlite3` is routed through the online
backup API at `scripts/backup/backup.py:129` and WAL/shm sidecars of
other SQLite files are skipped; lineage statistics confirmed —
**16/82 = 19.51% sentinel-bearing rows**, **2,948/4,700 = 62.72%
omitted ancestor edges**. Pass 1's falsifier table labelled the second
number as the first. That was a laundered statistic in my own
document; it is corrected in §7 below.

## 0. What this is

An append-only, flag-dormant, side-car record of four things the live
store does not record: **atoms** (units whose embedding covers their
whole text), **lineage** (real edges plus an honest count of what is
unknowable), **recall events** (the pre-ranking query vectors that are
discarded today), and **prompt exposures** (what was actually
serialized into a model request). The spine never mutates, moves,
deletes, or re-embeds a live-store row.

It earns permission to MEASURE. It does not earn permission to call any
measurement conscience, mood, importance, or truth.

## 1. The four defects, restated with measured scope

| # | Defect | Measured today | Spine element |
|---|---|---|---|
| D1 | Embedding truncates at 256 tokens, whole-document, no chunking | over-limit rows: **raw 3,571/44,037 = 8.11% (max 2,910 tok); daily 24/40 = 60.00% (max 557); core 10/134 = 7.46% (max 926)** | `atom_content` + `atom_occurrences` |
| D2 | Ancestry is comma-packed and capped | 19.51% of lineage rows carry the `,+N` sentinel; **62.72% of declared ancestor edges have no id recorded anywhere** | `lineage_edges` + `lineage_summary` |
| D3 | Query vectors never materialized; only a hash survives | 0 vectors retained | `recall_events` + `query_attempts` |
| D4 | No record of what reached the model | no construct exists | `prompt_exposures` |

D1 is hereby scoped to **all three live collections** (blocker 4):
daily is the worst offender at 60%, so a raw-only spine would leave the
most truncated layer blind.

Anchors (all verified current at HEAD by the gate): `def store(...)`
`memory/memory_manager.py:1479`; `def store_telegram(...)` `:1576`;
`def store_core(...)` `:1977`; `def consolidate_daily(self)` `:1644`;
`_PROMOTED_FROM_INLINE_CAP` `:1859`; `def _query_collection(...)`
`:2154`; `def get_all_core(...)` `:2087`; `def record_recall(...)`
`core/memory/memory_scoring.py:204`; `def get_encoder(...)`
`memory/embedder.py:47`; `def strict_env_flag(...)`
`core/infra/env_flags.py:23`; `def _entry(...)`
`core/cockpit/flags.py:65`; `def advance_and_get(...)`
`core/brain/conversation_turn_seq.py:77`.

## 2. Invariants (revised)

1. **Append-only.** No UPDATE, no DELETE in production code. Nothing is
   ever corrected in place; supersession is a new row.
2. **Never writes to the live stores.** Enforced by test, not by
   intention (§8, F-W).
3. **Flags-off ⇒ zero cost.** No import of the spine module, no SQLite
   open, no filesystem touch. Tested at the call site, not inside the
   module (blocker 9).
4. **Never blocks a reply.** Spine writes go to a bounded in-process
   queue drained off the reply path. Queue overflow increments a GAP
   counter; it never blocks and never raises.
5. **Best-effort observation with durable GAP receipts** (blocker 9,
   replaces pass 1's impossible completeness claim). The spine and
   Chroma cannot share a transaction. Any row the spine did not observe
   is recorded as a GAP — never silently absent, never backfilled with
   invented content. Bounded late observation is permitted only inside
   the open epoch and only from bytes still present in the live store;
   such rows carry `observed_late=1` so any analysis can exclude them.
6. **HISTORICAL_UNTRACEABLE is explicit and permanent.** Pre-spine rows
   are labelled untraceable forever. Codex's recency-bias self-attack
   is made structural: the bias is labelled, not hidden.
7. **Content-light receipts; protected at rest.** Directory `0700`,
   database and sidecars `0600`, private backup classification, and a
   **keyed** equality witness (domain-separated HMAC) rather than bare
   SHA-256 of short utterances, which are dictionary-testable
   (blocker 11).
8. **No maximand.** The spine is a record, not a target.

## 3. Schema (contract level)

Location `memory/db/spine/`, one file per **sealed epoch** (§6).
`journal_mode=WAL`, `busy_timeout` set, short transactions — pass 1's
blanket `BEGIN IMMEDIATE` is withdrawn (it serialized the daemon, web,
and script writers).

### 3.1 `atom_content` — content identity (blocker 2, 3)
`content_hash` TEXT PK (keyed HMAC of the exact bytes) ·
`byte_len` INT · `token_count` INT (measured with the contract
tokenizer) · `splitter_version` INT · `contract_hash` TEXT (hash of the
embedding contract in force) · `vector` BLOB (384×float32) ·
`vector_hash` TEXT · `embed_ts` REAL.

**Twin rule:** identical bytes ⇒ one row. Any residual computation must
treat a twin as reconstructable with residual 0.
**Invariant:** `token_count <= contract.truncation_tokens`, recomputable
from the stored bytes-span, never trusted as self-reported (blocker 12,
F4).

### 3.2 `atom_occurrences` — occurrence identity (blocker 2)
`occurrence_id` TEXT PK (hash over layer ‖ body_row_id ‖ ordinal ‖
splitter_version) · `content_hash` FK · `layer` TEXT (`raw`/`daily`/
`core`) · `body_row_id` TEXT · `ordinal` INT · `byte_start`,
`byte_end` INT · `row_content_hash` TEXT · `reassembly_hash` TEXT ·
`role` TEXT · `parse_status` TEXT · `pair_id` TEXT NULL ·
`provenance_source`, `trust_tier` TEXT (copied verbatim, never
re-derived) · `observed_late` INT · `created_ts` REAL.

Pass 1 collapsed content and occurrence into one key, which would have
aliased a recurrence with its twin — fatal for Return Parallax, whose
whole mechanism is *the same bytes appearing at two different times*.
Content identity and occurrence identity are now separate, and the
Parallax join is `atom_content.content_hash` across two distinct
`atom_occurrences` rows.

**Reassembly witness:** for every body row, the concatenation of its
occurrences' byte spans in ordinal order must reproduce the row bytes
exactly; `reassembly_hash` records the check. This is the answer to
Q1 (§9) — atoms are additive because reassembly is provable, not
because we promise it.

**Atomization (v0, deterministic, no model):** split at the production
container boundary, then paragraph, then sentence, then hard token
window. Every byte lands in exactly one atom. Roles are structural
only; **no role is ever invented** for unparseable rows (§9 Q4).

### 3.3 `lineage_edges` + `lineage_summary` (blocker 5)
`lineage_edges`: `child_id`, `parent_id`, `relation`
(`consolidated_from`/`promoted_from`/`derived_from`/`atom_of`),
`edge_ts`, `epoch`.
`lineage_summary`: `child_id` PK, `declared_count` INT,
`known_edge_count` INT, `unknown_parent_count` INT, `source_key` TEXT.

**Invariant (now satisfiable):**
`known_edge_count + unknown_parent_count == declared_count`.
Pass 1 demanded edge-count equality while also mandating a single
sentinel edge for an arbitrarily large unknown parent set — arithmetically
impossible. The unknown count is now a number, not an edge.

Note the corrected diagnosis: packed accounting already reconciles on
82/82 rows, so the live defect is **not** a count mismatch — it is that
2,948 declared ancestors have no recorded id anywhere and are therefore
**unfollowable**. The spine fixes follow-ability going forward and
labels the historical hole.

### 3.4 `recall_events` + `query_attempts` (blocker 6)
Pass 1 attached query capture at `_query_collection`, which receives
only `(collection, query, n)` — no channel, chat, identity, or ordinal.
Capture therefore moves **up** to the caller.

`recall_events`: `recall_event_id` PK · `channel` · `chat_id` ·
`event_identity` · `turn_seq` INT NULL · `ordinal_source` TEXT
(`turn_seq_store` / `unavailable`) · `issued_ts` · `epoch`.
`query_attempts`: `attempt_id` PK · `recall_event_id` FK ·
`collection` · `selector_kind` (`semantic`/`direct`/`date`/
`core_injection`) · `query_hash` · `vector` BLOB NULL ·
`vector_hash` · `contract_hash` · `n_requested`.

Two consequences, stated plainly:
- One admitted recall fans out into several attempts, and some
  attempts have **no vector at all** (`get_all_core` at
  `memory/memory_manager.py:2087` injects core directly). `selector_kind`
  makes that visible instead of pretending everything is semantic.
- `advance_and_get` returns `None` while both action-lane flags are off
  (`core/brain/conversation_turn_seq.py:88`). The spine therefore
  records `turn_seq = NULL, ordinal_source='unavailable'` and **does
  not couple its activation to the action-lane flags**. An honest null
  beats a fabricated ordinal.

### 3.5 `prompt_exposures` + `zero_exposure_receipts` (blocker 7)
Append-only cannot write `shown=0` and later update it to `1`, so the
pass-1 `shown` column is withdrawn. Two immutable classes instead:

`candidates`: `attempt_id` FK · `body_row_id` · `rank` · `distance` ·
`partition` (`evidence`/`context`).
`prompt_exposures`: `model_call_id` · `recall_event_id` ·
`occurrence_id` or `body_row_id` · `carrier` (`legacy`/`focused`) ·
`exposed_ts`. Written **only** at the terminal serialization seam,
after all trimming and carrier selection — legacy at
`daemon/maez_daemon.py:8939`, focused needs its own equivalent receipt
at `daemon/maez_daemon.py:8792`. Everything earlier (recall return,
`format_for_prompt`, raw-tail trimming at
`memory/memory_manager.py:3371`, the mid-block character cut at
`:3527`) is too early to be truthful.
`zero_exposure_receipts`: tool / echo / honest-empty / no-model turns
record an explicit zero rather than leaving retrieved rows looking
exposed.

"Exposed" means *serialized into the request*. It does not mean the
model used it. The spine may never claim the stronger reading.

## 4. Observation model and crash posture (blocker 9)

- Writes are enqueued after the live-store write returns success, and
  drained by a single writer off the reply path.
- On daemon start, a reconciliation pass compares body-row ids in the
  **open epoch's** time window against observed occurrences. Missing
  rows produce `observation_gaps` rows (`layer`, `body_row_id`,
  `reason`, `detected_ts`). Late observation is permitted only within
  the open epoch, only from bytes still in the live store, and is
  marked `observed_late=1`.
- Sealed epochs are never reconciled. A gap in a sealed epoch stays a
  gap forever — that is what "append-only" costs, and the cost is
  recorded rather than paid in silence.
- Blocker 1 consequence: the spine observes the three allowlisted
  chokepoint methods from inside `memory/memory_manager.py` — it adds
  no new writer and does not broaden the audit allowlist. Its claim is
  narrowed from "every raw write" to **"every write that passes the
  chokepoint."** The pre-existing bypass at
  `core/eval/telegram_corpus.py:160` (audit currently RED, reproduced)
  is a repo defect filed separately; rows entering by that path are
  recorded as gaps, not as observed.

## 5. Hazard H1 — resolved geometrically, still gated on API shape (blocker 8)

The gate executed the parity probe on 200 real content-light queries:
**max cosine deviation 2.22e-16, mean 6.11e-17, max component deviation
0, top-10 set equality 200/200, order equality 200/200**, and a second
comparison over 818 retained vectors also 200/200 with zero distance
delta. The model-geometry hazard did not materialize.

One real defect remains: `get_encoder().encode_many()` returns
`list(vector)` (`memory/embedder.py:33`), leaving `numpy.float32`
scalars, which Chroma's `query_embeddings=` validation **rejects**.
Explicit `numpy.asarray(..., dtype=float32)` succeeds.

Revised contract: keep the live path on `query_texts=`; capture vectors
on a **pure shadow path** that does not alter the live query at all.
Cutover to `query_embeddings=` is a separate, later decision requiring a
canonical conversion helper plus a direct Chroma API acceptance test.
Instrumentation may not change what Maez recalls.

## 6. Retention — sealed epochs (blocker 11, Q5)

Silent pruning would contradict the advertised spine, so retention is
**lifetime, with capacity engineering made explicit**:

- The spine rotates into sealed, immutable epoch files. Old epochs are
  verified and archived under the same protections; none is ever
  rewritten.
- Measured budget: one 384×float32 vector per existing raw row is
  ~67.6 MB before index overhead; vectors for query attempts and atoms
  accrue for life. Bytes/day is measured, not estimated (F13).
- A free-space floor is enforced fail-neutral: on breach the spine
  **stops writing and emits GAP receipts**. It never blocks a reply and
  never deletes to make room.

## 7. Falsifiers — rebuilt to be executable (blocker 12)

Pass 1's table is withdrawn. Every falsifier below names a denominator,
a pinned corpus, and a kill number; each ships with its harness script
in the slice that introduces it. Items marked ✗ in pass 1 are corrected
or replaced.

| # | Falsifier | Denominator / corpus | Kill |
|---|---|---|---|
| F1 | Twin residual: two occurrences sharing a `content_hash` reconstruct each other | pinned twin-pair manifest from the store's exact duplicates | residual > 1e-6 ⇒ kill (pass 1's "0.9712 today" was an old mixed-row baseline, not a twin measurement — corrected) |
| F2 | Neighborhood stability k=5 vs k=20 on the atom tail | pinned tail manifest + seed + bootstrap protocol, published with the harness | Jaccard < 0.70 ⇒ kill |
| F3 | `known_edge_count + unknown_parent_count == declared_count` | all new lineage-bearing children | any child violating ⇒ kill. (Baseline restated honestly: 19.51% sentinel-bearing rows; 62.72% unfollowable edges; packed accounting already reconciles 82/82) |
| F4 | Atom token count **recomputed** from stored byte spans, not trusted | all atoms in epoch | any atom > contract limit ⇒ kill |
| F5 | Recall coverage: recall events per **admitted turn** (denominator defined as turns reaching the recall call site), attempts per event ≥ 1 | admitted turns in epoch | coverage < 1.0 ⇒ kill |
| F6 | Whole-text visibility: for every over-limit row, atoms cover 100% of bytes (reassembly hash matches) **and** mutating an atom's own bytes changes that atom's vector | all over-limit rows (3,571 raw / 24 daily / 10 core today) | any reassembly mismatch, or < 95% of atom-local mutations changing the atom vector ⇒ kill. (Pass 1's row-suffix rule was invalid after splitting — appending text correctly creates a *new* atom while leaving old atoms unchanged) |
| F7 | `HISTORICAL_UNTRACEABLE` / gap classes never transition to a traceable class | all labelled rows | any transition ⇒ kill. (Pass 1 referenced `UNRECONCILABLE`, which belongs to the examined-life organ, not this schema — removed) |
| F8 | **Spine never writes to live-store files** — enforced by path allowlist assertion in the writer plus the existing bypass audit | every spine write | any write outside `memory/db/spine/` ⇒ kill. (Pass 1's "live store bytes unchanged" was invalid: a live store is *expected* to change during a shadow week) |
| F9 | Encoder parity **and** API shape: geometry thresholds plus a direct `query_embeddings=` acceptance test | ≥200 real queries | set equality < 99%, deviation > 1e-4, or API rejection ⇒ cutover blocked |
| F10 | Added turn latency, p95, with defined N, warmup, concurrency, paired flag-off/on runs, clock boundary, and failures included | pinned benchmark protocol | > 25 ms ⇒ kill |
| F11 | **Crash completeness:** injected kill between live write and spine drain produces a GAP receipt, never a silent absence | ≥50 injected crashes | any unrecorded miss ⇒ kill |
| F12 | **Observation-gap rate** in steady state | rows in epoch | > 0.5% ⇒ kill |
| F13 | **Bytes/day** and free-space floor behavior under a simulated full disk | measured week | unbounded growth unmeasured, or a breach that blocks a reply ⇒ kill |
| F14 | **Concurrent-writer contention:** daemon + web + script writing together | pinned concurrency harness | any spine-induced lock error surfacing into a turn ⇒ kill |
| F15 | **File modes and backup/restore integrity:** `0700`/`0600` verified; spine restored from backup opens and matches | every backup run | wrong mode, or restore mismatch ⇒ kill |

## 8. Backup (blocker 10, must land before S0 fixes the location)

`_SQLITE_FILENAMES_INSIDE_DIRS` at `scripts/backup/backup.py:129`
contains only `chroma.sqlite3`; every other SQLite file inside a backed-up
directory is flat-copied while its WAL/shm sidecars are skipped
(`:153`) — so a live `spine.sqlite3` would be captured **without its
committed WAL contents**. Verified directly, not assumed.

Required before S0: add the spine filename (or an extension-based
rule) to that set, plus a restore witness proving a spine file backed
up under live writes reopens and matches. F15 covers it.

## 9. Answers to pass-1's open questions (as resolved by the gate)

- **Q1 — does atomization destroy interactional wholes?** It would if
  `body_row_id` were the only preservation. Now: layer/locator, exact
  ordered byte spans, `row_content_hash`, `splitter_version`,
  `reassembly_hash`, and `pair_id` are all carried, so the whole is
  provably recoverable and the body row remains authoritative. No
  consumer may treat one atom as the exchange.
- **Q2 — cut over query embeddings?** No, not yet. Shadow capture only;
  cutover is a separate decision (§5).
- **Q3 — is "shown" derivable?** Only at the terminal model-call seam,
  separately for legacy and focused carriers, and it means *serialized*
  (§3.5).
- **Q4 — the unparseable 11.46%?** Not one class. Of 159
  non-boundary-parseable Telegram rows, **82 are deliberate turn-linked
  halves** (41 owner + 41 assistant) that already have structural
  identity and are atomized individually with their pair preserved; the
  remaining **77 unlinked legacy rows** get an honest `unknown` /
  `unparsed_container` role plus parse status, and are split
  deterministically by paragraph/sentence/window with exact byte spans.
  Roles are never invented.
- **Q5 — retention?** Lifetime, via sealed immutable epochs with
  measured capacity and fail-neutral overload (§6).

## 10. Slice plan

- **S0** — epoch file, schema, modes, flags
  (`MAEZ_EVIDENCE_SPINE_SHADOW`/`_ENABLED`), backup routing + restore
  witness. Witness: flags-off ⇒ no import, no open, no file (tested at
  the call site); F8, F15.
- **S1** — atomization at the three chokepoint methods, all layers.
  Witness: F4, F6, F12, and reassembly on 100% of observed rows.
- **S2** — lineage edges + summary. Witness: F3.
- **S3** — recall events + query attempts, shadow capture only.
  Witness: F5, F9 (geometry already green, API test pending).
- **S4** — candidates + prompt exposures at the terminal seams, plus
  zero-exposure receipts. Witness: exposure joins, carrier coverage.
- Crash/contention/capacity witnesses (F11, F13, F14) run across
  S1–S4 rather than at one slice.

Organs attach only after S1–S4 have run in shadow. Return Parallax
cannot fire before S1, since its byte-equality witness is an
`atom_content.content_hash` join across distinct occurrences.

## 11. What this design still does not claim

Atoms are units of *visibility*, not meaning. Lineage is *honest*, not
complete. Recording demand does not make anything important. And under
shadow flags nothing about the live conversation changes — which is
the point.
