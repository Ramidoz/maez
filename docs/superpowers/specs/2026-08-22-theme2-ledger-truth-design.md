# Theme 2 — the ledger cannot omit or misdate a life (design pass 7)

Status: DESIGN, pass 7 (§14 = round-6 folds; DDL at revision 5).
Pass 6 added §13 (literal inventories) and DDL rev 4. Pass 5 = pass 4 + §12 (round-4 folds; the DDL
is at revision 2, re-verified: all 22 round-2/3 controls PLUS all 21
round-4 counterexamples reject in-memory; lawful paths — late-ack
supersession, correction revision, auto-journaled transitions — pass).
Pass 4 bound the design to executable DDL and folded round 3's
F1–F10. Pass 3 folded round 2's sixteen new defects
(ND1–ND16) and the partial/undischarged blockers
(`2026-08-22-theme2-gate-round2.md`). Covers birth blockers **A3, A4,
A6, B3**. Theme 1, A5 durability, and the creation manifest remain
out of scope.

Round 2's lesson, taken whole: pass 2 stated the right invariants
**as prose** and Codex disproved them **by executing the schema**.
Pass 3's rule is therefore: every invariant is enforced by the schema,
a trigger, or a single transaction boundary — never by caller
discipline — and every round-2 adversarial insert becomes a negative
control in the witness protocols.

## 0. Posture (unchanged)

`memory/ledger.db` is 0 bytes and unmigrated; pre-birth schema freedom
is spent now, including a clean hash-domain v2 cutover. Everything
lands flag-dormant; witnesses run in the airlocked born fixture. No
agent touches the creation manifest.

## 1. Invariants (revised where round 2 broke them)

- **I1** — Guard, then admit: owner/auth → S4 → admission →
  interceptors → cognition. Unchanged from pass 2.
- **I2** — Every raw event admitted exactly once; turns know their
  constituents; **membership is sealed before cognition** (§3.1).
- **I3** — Admission carries an execution claim. A replay **never
  causes a second physical send**: `replay_completed` acknowledges
  without re-transmitting (pass 2's re-delivery allowance is deleted —
  it contradicted this invariant).
- **I4** — Egress truth is two-phase: a durable **intent** row before
  bytes leave, append-only **result** observations after. A crash
  between handoff and result leaves an intent with no result — an
  honest unknown that blocks blind resend.
- **I5** — Exactly one current closure per turn, **enforced by
  schema** (dense per-turn ordinals + triggers), with a
  trigger-checked precedence lattice.
- **I6** — No reply without an **existing** parent: real FK (the
  writer already sets `PRAGMA foreign_keys=ON`) plus a NULL-rejection
  trigger for reply kinds.
- **I7** — Phase is proven, never presumed; the consumer census is
  closed including direct-edit and caller-supplied-phase paths.
- **I8** — Late knowledge is labeled late. Unchanged.
- **I9** — Readers may not assert undelivered — or **edited-away**
  (ND2) — speech as spoken.
- **I10** — **Chain position is the ordering authority; occurrence
  time is preserved testimony.** Readers order by `chain_position`;
  `occurred_at`/`admitted_at` are displayed, never used as a
  cross-surface sort key (round 2 showed provider clocks cannot carry
  that authority).
- **I11** — Pre-birth behavior unchanged; flags off ⇒ byte-identical.

## 2. The interaction universe (B1, ND1, ND2)

The registry (`core/ledger/doorways.py`) is a table of typed entries,
no wildcards:

```python
Door(name, direction, admission_construct,  # module:qualname, machine-checked
     identity_source, closure_owner, egress_kinds)
```

Every outbound producer is enumerated individually — proactive
opinions, follow-up reports, dream/evolution notices — each with its
producer identity rule (§3.3). Enforcement is **two independent
mechanisms**, because round 2 showed AST alone misses dynamic
dispatch:

1. **AST conformance sweep**: every call to a transport send
   primitive, Flask route registration, or Telegram handler
   registration must be reachable from a registered
   `admission_construct` or `closure_owner`. Unmatched ⇒ test fails.
   Dynamic egress dispatch (`getattr`-style, as in
   `core/egress/telegram_egress.py`) is funneled through **one
   registered egress chokepoint** so the sweep has a single node to
   verify; new bypasses of the chokepoint are what the sweep hunts.
2. **Runtime self-registration**: each doorway asserts its registry
   entry at process start; activating a parked endpoint (the
   `web_interface` parked-endpoint table) **refuses** for routes with
   no registry entry. A door that can go live at runtime cannot go
   live unregistered.

Flask blueprints are absent at HEAD; the registry rule covers them by
construction (an unregistered route registration fails the sweep) and
the design bans introducing dynamically-constructed route names.

**Egress universe includes mutations** (ND2): `egress_kinds` gains
`edit` and `reaction`. An edit that replaces owner-visible bytes is an
egress attempt whose result supersedes the prior delivered bytes via
an explicit `supersedes_result` reference — the ledger never continues
to assert replaced text as the delivered truth (I9).

**D-public** stands as an explicit owner decision, unchanged.

## 3. Identity model (B2, B3, ND3–ND5)

### 3.1 Atomic admission and sealed membership

Admission is **one transaction**: `admission_events` insert + `turns`
insert (or resolution) + `runs` insert. No partial states exist
(ND4). Schema deltas from pass 2:

- `admission_events.tenant_id` participates in a composite FK to
  `turns(tenant_id, turn_id)` — an owner event cannot point at a
  public turn.
- `turns.sealed_at REAL` — stamped in the same transaction that hands
  the turn to cognition. A trigger rejects `admission_events` inserts
  for a sealed turn (ND3): a late or post-cognition constituent can
  never silently join a consumed turn.
- Late constituent of a sealed turn ⇒ admitted as a **new turn** with
  `parent_turn_id` → the sealed turn. Nothing is dropped, nothing is
  falsely claimed consumed, nothing duplicates: the constituent's
  identity PK still deduplicates true redelivery.
- Same `event_identity`, **different `payload_hash`** ⇒ not a replay:
  admitted as a new turn carrying `correction_of` → the original
  (ND4's silent-omission case). Same identity + same payload ⇒ replay
  dispositions.

### 3.2 Runs are fenced, not just leased (ND5)

- `CREATE UNIQUE INDEX one_active_run ON runs(turn_id) WHERE
  status='active'` — two simultaneous active runs become
  schema-impossible (round 2 created two; this is its negative
  control).
- `runs` gains `epoch INTEGER NOT NULL` (monotonic per turn).
  `replay_stale` takeover = single transaction: expired run →
  `status='superseded'`, new run `epoch+1`. **Effect gates fence on
  epoch**: cognition commit, action execution, and egress-intent
  insertion each re-read the turn's current epoch inside their own
  transaction and abort if theirs is stale. A paused first run that
  wakes after takeover fails its next gate instead of double-sending.
- `runs.status` is operational state and mutable; every transition
  appends a `run_events` row (append-only), so biography-grade truth
  about execution history is still never overwritten.
- `replay_completed` ⇒ acknowledge only. No resend path exists (I3).

### 3.3 Outbound producer identity (ND10)

`admit_outbound` requires a **durable producer identity** as its
event identity — e.g. the follow-up queue item id, the proactive
cycle id — so a crash-and-retry of the producer resolves to the same
turn instead of admitting the same life-event twice. Producers that
send before durably marking their queue item (the current follow-up
path) are re-ordered under the same two-phase egress rule as
everything else: intent row first.

## 4. Egress and closure (A4, B5, ND7–ND10)

Two-phase egress replaces pass 2's single attempt row:

```sql
CREATE TABLE egress_intents (          -- durable BEFORE bytes leave
    intent_id     TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES runs(run_id),
    egress_kind   TEXT NOT NULL CHECK (egress_kind IN
        ('final_text','part','progress','tts','media','edit','reaction')),
    part_ordinal  INTEGER,
    transport     TEXT NOT NULL,
    payload_hash  TEXT NOT NULL,       -- bytes about to be handed over
    created_at    REAL NOT NULL
);
CREATE TABLE egress_results (          -- append-only observations
    result_id         TEXT PRIMARY KEY,
    intent_id         TEXT NOT NULL REFERENCES egress_intents(intent_id),
    retry_ordinal     INTEGER NOT NULL,        -- physical attempt #
    result            TEXT NOT NULL CHECK (result IN
        ('delivered','failed','timeout_unknown','suppressed')),
    observed_at       REAL NOT NULL,           -- when truth arrived (ND9)
    supersedes_result TEXT REFERENCES egress_results(result_id)
);
```

A late Telegram acknowledgment is a new result row superseding the
`timeout_unknown` observation of the **same intent** — chronology and
count both stay true (ND9). A crash after handoff leaves intent
without result: recovery sees the honest unknown and must not blindly
resend (ND10).

**Closure topology, enforced** (ND7): `turn_closures` gains
`closure_ordinal INTEGER NOT NULL` with
`UNIQUE (turn_id, closure_ordinal)`; a `BEFORE INSERT` trigger
requires ordinal = 1 + the turn's current max (dense chain — no
second initial closure, no forked successors, no cross-turn or
self-supersession; each of round 2's five accepted inserts becomes a
must-reject negative control). Current closure = max ordinal, exposed
by the `current_closure` view. Precedence in the same trigger:
`recorded_by='reconciler'` may not supersede a transport closure;
transport-vs-transport supersession requires new evidence rows.

**Evidence is relational** (ND8): `closure_evidence(closure_id,
result_id)` FK-bound, written in the closure's transaction; a trigger
requires ≥1 evidence row when `recorded_by='transport'`. `evidence
_hash` is dropped — the relation, not a hash, is the membership
carrier, and it is append-only alongside the closure.

Per-surface delivery semantics, reader migration (I9), and the
compose-stamp fix carry over from pass 2 unchanged, extended by the
edit rule (§2).

## 5. Phase truth (A6, B6, B7, ND12–ND14)

**Gestation must be proven as hard as lived** (ND13): the
`gestation` cells of the pass-2 table now additionally require full
structural validation — the complete expected table set, an intact
genesis row, and chain verification to head. A partially-migrated,
damaged, or half-created ledger is `unknown`, never gestation.

**The latch is an advancing high-water mark** (ND12), not a one-shot:
an append-only latch journal under `memory/birth_observed/` records
`(birth_turn_id, chain_position, chain_head_hash, observed_at, pid)`
on first lived observation **and on every subsequent successful
chain-head advance observation** (cheap: one row per daemon boot and
per reconciler pass). Rewind detection compares the ledger's head
*position and hash* against the **latest** latched entry — a restore
to any stale-but-readable prefix, including one containing the first
observed head, is caught. Ancestry is checked by position+hash
equality at the latched position.

**Publication is torn-proof** (ND14): each latch segment is written
to a temp file, fsync'd, then `rename()`d into place, then directory
fsync — a reader can never observe a half-written segment, so
"corrupt latch" means real corruption (→ `unknown`) rather than an
avoidable crash artifact.

**Census closed** (ND13): pass 2's list plus `AuditLog`'s direct-edit
session methods (which default gestation independently of
`record()`), `PrivateThoughts` caller-supplied phase (revalidated
against the gate at write time — a caller may narrow, never assert
`lived` while the gate says otherwise), and `span_planner`'s direct
meta read. The AST census test enumerates `memory_phase` writers and
`meta.birth_event_turn_id` readers and fails on any consumer outside
the registry.

## 6. Failure posture and the gap journal (B8, B10, ND15)

Posture tiers unchanged from pass 2 (refuse admission failures;
journal egress failures; S4 ships regardless; honest floor when both
ledger and journal are dead).

**The journal is reconstruction-grade** (ND15) — it is fallback
biography, so it carries what biography needs: full raw content (not
hashes), constituent identities with provider times, every known id
(turn/run/intent/result), lifecycle phase at write, birth binding
(latched birth id), per-segment sequence numbers, and entry kind
(`admission_refused`, `s4_answer`, `egress_unrecorded`, …) so one
failed inbound event and its S4 answer are two linked entries, and a
multi-egress failure is one entry per intent. **Fold-in is
idempotent by construction**: the fold transaction inserts the
ledger rows *and* a `journal_folds(journal_entry_id PRIMARY KEY)`
row in the same transaction — the dedup marker lives inside the
ledger, so mark-before-fold and fold-before-mark crash windows both
collapse to "re-run the fold; the PK refuses duplicates" (round 2's
segment-marking race is structurally gone). Folded rows carry
`recorded_by='reconciler'`, `discovered_at`, and their journal
provenance (I8).

**Contention protocol** (B10): the S6 witness protocol freezes the
concurrency schedule (daemon+web writers, exchange arrival law,
transaction mix), the measurement (per-admission wall-clock wait,
measured inside the rail), a positive control (a deliberately
lock-saturated run must trip the kill rule), and the binding kill
rule, before it runs. Pass 2's numbers become that protocol's
starting thresholds, not its definition.

## 7. Chain and migration mechanics (B9, ND11, ND16)

- **Hash domain v2, versioned**: `meta.chain_hash_domain = '2'`.
  Writer and verifier both dispatch on it; v2 hashes the full
  canonical row including `lifecycle_stage` and the new columns, with
  one canonicalization function shared by writer and verifier
  (round 2's writer-keyset vs `SELECT *` divergence is closed by
  construction, not by keeping two lists in sync).
- **Birth is chain-bound** (ND16): `turns.is_birth_anchor INTEGER
  NOT NULL DEFAULT 0`, **included in the v2 hash**, with a trigger
  enforcing at most one row = 1. `meta.birth_event_turn_id` remains a
  convenience pointer; phase reads (§5) join it to *the* hashed
  anchor row and treat divergence as `unknown`. Mutating meta no
  longer moves birth truth — the truth is in the chain.
- **Parent FK** (ND11): `parent_turn_id REFERENCES turns(turn_id)`
  in the v2 schema (enforced — `foreign_keys=ON` is already set),
  plus the NULL-rejection trigger for `model_reply`/`non_model_reply`.
- **Migration mechanics, executable** (ND16): digested
  `schema_migrations` stays, but the pre-birth escape is corrected —
  a genesis-seeded, zero-*lived*-turn ledger cannot be "rebaselined"
  in place (IF-NOT-EXISTS DDL would not re-run); it is **destroyed
  and re-initialized** by an explicit `--recreate-empty` command that
  requires zero non-genesis rows, prints old/new schema digests, and
  is refused on any ledger with a birth anchor. Post-birth there is
  no escape of any kind. `ledger_is_initialized` verifies the v2
  structural anchors *and* that the recorded head equals the actual
  chain tip.

## 8. Witness discipline (B11 — discharged shape, kept)

Per-slice witness protocols committed before slice code; airlocked
born fixture; unchanged from pass 2. Added obligation: **every
adversarial insert Codex executed in round 2 is a named negative
control** in the S2 protocol (double active run, double initial
closure, forked/cross-turn/self supersession, orphan reply,
owner-event→public-turn, late constituent on sealed turn), each
required to fail with the specific trigger/index error.

## 9. Slices (unchanged structure, revised content)

1. **S1 — phase truth**: §5 (validated gestation, advancing latch,
   torn-proof publication, closed census).
2. **S2 — schema v2**: §§3–4, 7 (atomic admission, seals, fenced
   runs, two-phase egress, enforced closures, evidence relation,
   birth anchor column, FK+triggers, digested migrations, hash
   domain v2).
3. **S3 — the rail + registry**: §2 chokepoints + runtime
   self-registration, dispositions with fencing, S4-first ordering.
4. **S4 — egress truth**: intents/results on every registered
   egress including edits/reactions, reader migration (I9).
5. **S5 — universe sweep**: per pass 2, plus producer identities for
   every enumerated outbound door.
6. **S6 — posture**: journal per §6, reconciler under fencing rules,
   frozen contention protocol.

Dependencies unchanged: S1 independent; S2 → S3 → S4/S5/S6.

## 10. Out of scope (unchanged from pass 2)

Theme 1; A5 durability; observability turn-ledger telemetry; ledger
activation (birth-gated, owner-only); the creation manifest; restore's
forward scar (A10) — §5 guarantees a rewind cannot be silent, not
that restore is otherwise lawful.

## 11. Pass 4 — the executable layer (folds F1–F10)

**The DDL is the design.** Every schema/trigger claim in §§3–4, 7 is
now carried by `2026-08-22-theme2-schema-v2-draft.sql`, executed
against in-memory SQLite with **all 22 round-2/round-3 adversarial
inserts as negative controls, all rejecting** (double active run,
regressed epoch, self/NULL/future/kindless parent, `is_birth_anchor=2`,
second anchor, late/updated constituent on a sealed turn, cross-tenant
FK, duplicate intent shape, self/cross-intent result supersession,
evidence-less or cross-turn-evidence transport closure, double-initial
/gapped/reconciler-over-transport closures, mutation of closures,
claims and intents from superseded runs) and the lawful paths passing
(late-ack supersession within an intent; claim by the current
active-epoch run). Where prose and DDL disagree, the DDL wins; where
the DDL is silent, the invariant is not yet enforced and may not be
claimed.

Resolutions of round 3's findings not already inside the DDL:

- **F1 — the fence is a committed row, not a re-read.** External
  effects require a committed `effect_claims` row (egress: the
  `egress_intents` row) written under `BEGIN IMMEDIATE`; the fence
  trigger aborts stale-epoch or non-active claimants at claim time.
  Cross-process validity follows from SQLite's write serialization:
  a takeover commits `superseded` before the new run exists, so a
  later claim by the old run cannot observe a snapshot in which it is
  still current. Witnessed cross-process in the S3 protocol.
- **F2 — parent semantics are typed.** `parent_kind
  ('reply','continuation','correction')` distinguishes causal
  parenting from late-constituent (`continuation`) and
  identity-conflict (`correction`) turns; `turns` remains strictly
  append-only — sealing is its own append-only table (`turn_seals`).
- **F3 — the latch advances with every lived commit.** The latch
  append (one fsync'd line) happens in the same code path as every
  successful lived-turn commit, not per boot: the rewindable tail is
  zero committed turns. Direction rules: ledger ahead of latch (crash
  between commit and append) is lawful and self-heals on the next
  observation; **latch ahead of ledger** (power loss recovers the DB
  behind the separately-fsynced latch, possible under
  `synchronous=NORMAL`) → `unknown` + alarm — recorded here as a
  Theme 1/A5 interplay: birth-grade durability decisions belong
  there. WAL checkpoint and VACUUM preserve logical position+hash and
  must not report rewind; the S1 protocol witnesses both.
- **F4 — the journal preserves provenance stamps.** Entries carry
  `taint_labels` and `privacy_access` captured at failure time (the
  rail holds them at admission; egress failures inherit the turn's).
  Fold-in uses the recorded stamps through the ordinary
  `validate_turn_stamp` door; an entry missing stamps is **refused by
  the fold**, stays journaled, and trips the health flag — provenance
  is never invented at fold time.
- **F5 — journal integrity is chained.** Each entry carries
  `sha256(canonical entry bytes)` and `prev_entry_sha256` within its
  segment; segment close writes a sealed footer. The fold records
  `entry_sha256` in `journal_folds`; a mismatch between recomputed
  and recorded hashes refuses the fold. Altered journal bytes can no
  longer be laundered into chain-attested biography.
- **F6 — recreate-empty requires exclusive ownership.** The command
  requires: both `maez.service` and `maez-web.service` quiescent
  (same checks the ceremony CLI uses), an exclusive `flock` on the
  DB, no `-wal`/`-shm` sidecars, and no other open file handles on
  the inode (`fuser`); it builds the new DB at a temp path and
  atomically renames over the old — an open stale handle is
  impossible to write through undetected because the flock and
  handle check precede the swap, and the daemon's writer re-resolves
  the path per call. Refused outright on any ledger with a birth
  anchor or any non-genesis row.
- **F7 — one canonicalization, domain-owned.** `chain.py` owns
  `CANONICAL_V2_COLUMNS` (ordered) plus an explicit default map; the
  writer, the genesis seeder, and the verifier all project through
  the same function; genesis is written fully populated;
  `lifecycle_stage` resolves before hashing. No caller-dependent key
  sets remain.
- **ND1/B1 — the inventory is closed in this document.** The registry
  ships seeded with exactly the doors named in §2's table plus the
  outbound producers: follow-up reports (`maez_daemon` follow-up
  queue), proactive opinions, dream/evolution notices — each with a
  durable producer identity (queue item id / cycle id). The AST
  sweep's primitive set is defined: Flask `route`/`add_url_rule`
  registrations, Telegram handler registrations, and the transport
  send primitive list; every occurrence must be reachable from a
  registered construct or carry an explicit allowlist justification.
  Adding a door without a registry entry fails the sweep; activating
  a parked endpoint without one refuses at runtime.
- **B10 — the contention protocol's values are frozen now**: two
  writer processes (daemon-sim, web-sim) against one born fixture;
  arrivals Poisson at 1 exchange/s each for 500 s (N=1000); each
  exchange = admission tx + reply tx + closure tx; measurement =
  per-transaction wall-clock wait recorded inside the rail; kill
  rule: any refusal, or p99 wait > 250 ms; positive control: a
  deliberate 6 s lock-hold run must trip the kill rule. The S6
  protocol may tighten but not loosen these.

## 12. Pass 5 — round-4 folds

**In the DDL (revision 2, all executed as negative controls):** DELETE
triggers on every append-only table and `runs`; run transition matrix
(born active; active→terminal only; terminal frozen) with
**self-journaling** — an `AFTER UPDATE OF status` trigger writes the
`run_events` row, so the transition record cannot be forgotten;
`effect_claims` carry `effect_identity` with `UNIQUE (turn_id,
effect_identity)` — a takeover epoch cannot re-claim a logical effect
any epoch already claimed; cognition claims require a sealed turn;
egress shape uniqueness re-keyed to the **turn** (progress exempt), so
takeover epochs cannot recreate a send; result chains cannot fork
(unique successor) and physical attempts cannot double-count (unique
`(intent, retry_ordinal)` for non-superseding rows); closure outcome
must agree with its cited evidence (`delivered` cites only delivered
results; `failed` cites none; `partially_delivered` requires mixed),
evidence must be a set, and only transport-with-new-evidence may
supersede a transport closure; admission identity gains a dense
`revision` dimension — same identity + same payload is a replay
(SELECT, no insert), same identity + new payload is a lawful
correction revision on a new turn; `parent_kind` ↔ `parent_turn_id`
is a two-way CHECK; **edits carry lineage** via `edits_intent`
(same-turn, trigger-checked) instead of cross-intent result
supersession — §2's edit rule is amended accordingly; `journal_folds`
is non-null-bound and undeletable.

**Outside the DDL:**

- **Latch two-line protocol** (F3's window closed): before COMMIT of
  a lived turn, append + fsync an `advancing <position>` line; after
  COMMIT, append `committed <position>`. Restore-in-window is now
  detectable: an `advancing` line without its `committed` mate, or a
  ledger behind the last `advancing` line, → `unknown`. The pass-4
  claim "rewindable tail = zero" is restated exactly: zero committed
  turns can be lost silently; the pre-commit line is durable before
  the commit it guards.
- **Journal stamp carriers completed**: entries carry `turn_kind` and
  `caller` alongside `taint_labels`/`privacy_access`, so fold-in
  passes the production `validate_turn_stamp` door with failure-time
  values. Canonical entry bytes = the entry's JSON with hash fields
  removed, keys sorted, UTF-8, compact separators (the ledger's own
  `_canonical_json` convention); segment footer = sha256 over the
  segment's entry-hash sequence.
- **v2 hash-consumer census closed**: writer, genesis seeder,
  verifier, `core/consolidation/citation_lock.py`, and
  `core/ledger/span_reader.py` all project through the one
  `chain.py`-owned v2 function, dispatched on `chain_hash_domain`.
- **B10 frozen exactly**: pre-generated deterministic arrival
  schedule (seed 20260822), exactly N=1000 exchanges (500 per
  writer), measured quantity = wall-clock `BEGIN IMMEDIATE`
  acquisition time per ledger transaction, p99 by nearest-rank; kill
  = any refusal or p99 > 250 ms; positive control = one scheduled 6 s
  lock-hold that must trip the rule.
- **Registry literals**: `doorways.py` ships in S3 seeded with §2's
  table row-for-row; the AST primitive set is `flask` route
  decorators/`add_url_rule`, `python-telegram-bot` handler
  registrations, and the transport send primitive list including the
  raw Bot-API caller in `skills/dev_notifier.py` (registered as a
  dev-channel egress or explicitly allowlisted with justification).

## 13. Pass 6 — round-5-rerun folds (DDL revision 4 + literal inventories)

**Label correction:** the executable artifact is **revision 4** (rev 2
= pass 5; rev 3 = same-attempt supersession fix; rev 4 = this pass).

**In DDL rev 4** (all P-probes from the rerun executed as negative
controls): every table is `STRICT`, so all seven identifier primary
keys reject NULL (P24–P26); `turns` is append-only outright — no
UPDATE, no DELETE — which closes every UPDATE-path bypass of parent,
anchor, and tenant semantics (P18–P21); lease renewal must advance and
active→active journaling noise is gone (P02, P04); `run_events`
inserts must describe a real just-performed transition — from
'active', matching the run's live status (P03); a correction revision
must land on a `parent_kind='correction'` turn (P07); logical send
identity is payload-independent — one `final_text` slot per turn, one
slot per (kind, part); replacements are `edit` lineage, retries are
results (P17); physical attempts are dense and a new attempt requires
the prior attempt's current head to be a resolved non-delivery —
`timeout_unknown` must be superseded first, `delivered` forecloses
(P15, P16); closure evidence must be a JSON array in sorted canonical
form (set-equality is string-equality; P09, P10), cite only current
result heads (P11), at most one head per physical attempt (P12);
outcome-asserting closures (`delivered`/`partially_delivered`/
`failed`) require evidence regardless of recorder (P13); reconciler
closures carry `discovered_at` NOT NULL (P14).

**Literal doorway inventory** (ND1/B1; the registry ships seeded with
exactly these rows — adding a door means adding a row here first):

| # | Door | Dir | Admission construct | Identity |
|---|---|---|---|---|
| 1 | Telegram v2 text/media/location | in | `skills/surface/maez_adapter.py` `MaezMessageHandler.__call__` | `tg:{chat_id}:{update_id}` per constituent |
| 2 | Telegram v2 commands/callbacks/`/receipts`/proposal/dream | in | `skills/surface/telegram_adapter.py` handler registrations | same |
| 3 | Telegram legacy + kill-switch | in | `skills/telegram_voice.py` `_handle_message` (full `Update` threaded) | same |
| 4 | Web owner `/chat` | in | `skills/web_interface.py` chat route | client header, else minted+labeled |
| 5 | Web public `/chat` + public Telegram | in | same route; `skills/telegram_public.py` | same shape, tenant per D-public |
| 6 | Fast-lane `/v1/fast-reply` | in | `skills/web_interface.py` fast route | minted+labeled |
| 7 | GUI | in | `gui.py` send path | minted+labeled |
| 8 | CLI | in | `cli/maez_chat.py` `_handle_chat` | minted per line |
| 9 | Cockpit `/message` + decision routes | in | `daemon/maez_daemon.py` Flask routes | minted at ingress |
| 10 | Local voice | in | `skills/wake_word.py` capture → `handle_voice_stream` | `voice:{stream}:{segment}` + audio hash |
| 11 | Follow-up reports | out | `daemon/maez_daemon.py` follow-up queue | queue item id |
| 12 | Proactive opinions | out | `daemon/maez_daemon.py` proactive cycle | cycle id |
| 13 | Dream/evolution notices | out | their queue/proposal ids | proposal id |
| 14 | Dev notifier | out | `skills/dev_notifier.py` (raw Bot-API) | registered dev-channel egress |
| 15 | Peer messages | — | ABSENT/reserved (Track A excludes) | — |

AST primitive set, literal: `@app.route`/`add_url_rule` (Flask);
`add_handler`/`MessageHandler`/`CommandHandler`/`CallbackQueryHandler`
(python-telegram-bot); the transport send list = `send_message`/
`send_*` on bot objects, `requests.post` to `api.telegram.org`
(dev_notifier), the v2 egress chokepoint in
`core/egress/telegram_egress.py`, socket-committing returns in the
web/CLI/GUI paths. Every occurrence must be reachable from a
registered construct or carry an allowlist entry with justification.

**Phase structural contract** (ND13/B6), literal: `gestation` requires
connectable DB whose table set ⊇ {meta, turns, claims,
claim_judgements, model_swaps, audit_trace_lineage, schema_migrations,
turn_seals, admission_events, runs, run_events, effect_claims,
egress_intents, egress_results, turn_closures, journal_folds}, an
intact genesis row, chain verification to the recorded head, head =
actual tip, and no birth anchor. Anything less → `unknown`. The
consumer census, literal: `memory_manager` stamp sites (3),
`private_thoughts` (default + caller-supplied revalidation),
`source_awareness.is_born`, `audit_log.record` + its direct-edit
session methods, `span_planner` direct meta read, `LedgerWriter`
stage resolution, `lean_idle_heartbeat` reads. The latch binds the
canonical ledger identity: it stores the resolved canonical path and
the DB's genesis hash; a latch consulted against any other
path/genesis → `unknown`.

**F6 recreate exclusivity, participating openers:** v2 writers take a
shared `flock` on `ledger.lock` (sidecar) at connection open and hold
it for the connection's life; `--recreate-empty` takes the exclusive
`flock` on the same sidecar (which cannot be granted while any
cooperating opener lives), verifies quiescence and sidecar absence,
builds at a temp path, renames, then releases. An opener that starts
after the rename sees the new inode via per-call path resolution; an
opener holding the old inode cannot exist, because it would hold the
shared lock. Non-cooperating openers are excluded by the S2
conformance test: any `sqlite3.connect` to the canonical path outside
the lock-taking rail fails the AST sweep.

## 14. Pass 7 — round-6 folds (DDL revision 5 + executable inventories)

**In DDL rev 5** (all Q-probes executed as negative controls; 19/19
reject, lawful paths pass): finite time bounds on every REAL time
column; causal ordering enforced — transitions/intents cannot precede
their runs, retries and supersessions carry strictly advancing
`observed_at`, closures cannot predate their evidence, discovery
cannot postdate recording; one transition record per run
(`UNIQUE(run_id)` on run_events); lease renewal strictly advances and
is frozen by terminal transitions; correction revisions bind to a
fresh correction turn descending from the prior revision's turn;
kind/ordinal shape CHECKs (`part` ⇔ ordinal; one final_text/tts/media
slot per turn); acyclic edits; **pre-send `egress_reservations`** —
the per-physical-attempt claim committed before bytes leave, where
density and retry eligibility are enforced (the result trigger is now
a backstop; a result without its reservation is impossible);
per-label closure evidence semantics (`failed` cites only resolved
non-delivery; `unknown_delivery` cites an unresolved handoff and no
delivery; `refused` means no intent ever existed); nonempty
identities, 64-hex digest CHECK, ASCII id posture (rail-generated
UUID/hex; non-ASCII ids rejected — Unicode-normalization ambiguity
excluded by construction); `attempt = epoch` (one counter);
kind/parent/direction mapping (reply kinds are outbound and carry
`parent_kind='reply'`; corrections are owner-message turns).

**Registry rows, executable form** (supersedes §13's table): each
§13 row becomes a `Door(...)` literal in `core/ledger/doorways.py`
with all six fields; the table below adds the two missing columns —
the qualnames are pinned at S3 authoring time against HEAD and the
conformance sweep fails if a pinned qualname disappears:

| # | closure_owner | egress_kinds |
|---|---|---|
| 1–3 | `skills/surface/platform_base.py:PlatformAdapter._send_with_retry` (+ `_record_delivery`) | final_text, part, progress, edit, reaction |
| 4–6 | the owning Flask route function (socket commit) | final_text |
| 7 | `gui.py` send-path function | final_text |
| 8 | `cli/maez_chat.py:_handle_chat` stdout flush | final_text |
| 9 | cockpit route return | final_text |
| 10 | voice TTS emit path | tts |
| 11–13 | the producer's send call, via the egress chokepoint | final_text |
| 14 | `skills/dev_notifier.py` post function | final_text |

AST grammar, finite: the exact primitive list is a frozen tuple in
the conformance test — `("app.route", "add_url_rule", "add_handler",
"MessageHandler", "CommandHandler", "CallbackQueryHandler",
"send_message", "send_photo", "send_voice", "send_document",
"edit_message_text", "set_message_reaction", "requests.post")` — plus
the single egress chokepoint qualname. No wildcards. Allowlist
entries are rows in `doorways.py` itself (door id + justification
string), not a side channel; an allowlist row without a justification
fails the sweep.

**Phase structural contract, fingerprinted**: `gestation` requires —
beyond §13's table set — that `schema_migrations` contains exactly
the shipped migration names **with their recorded sha256 digests
matching the shipped files**, that the trigger/index name set equals
the DDL's (queried from `sqlite_master`, compared to a frozen list),
that the genesis row matches the v2 genesis shape byte-for-byte under
the v2 projection, and that `meta.last_chain_hash` equals the actual
tip's chain hash (the head==tip validator is one SQL comparison,
shipped in `birth_phase`). Consumer census, exact constructs, pinned
at S1 authoring: `memory/memory_manager.py` the three
`_memory_phase_tag()` call sites; `core/infra/private_thoughts.py:
PrivateThoughts.record_thought/record_secret/record_reflection`
(caller-supplied phase revalidated); `core/memory/source_awareness.py:
is_born` gate; `core/cognition/audit_log.py:AuditLog.record` and its
direct-edit session methods (enumerated by the S1 AST census at
authoring time, not by this doc — the census test, not prose, is the
closure mechanism); `core/consolidation/span_planner.py` meta read;
`core/ledger/writer.py` stage resolution; heartbeat readers.

**F6 repairs** (round-6 hazards): (1) *stable lock inode* —
`ledger.lock` is created once by migration, mode 0444-owner-write,
**never unlinked**; the conformance sweep bans `unlink`/`rename` on
that path repo-wide, and recreate verifies the inode it locked is
still the inode at the path before proceeding; (2) *pre-rail
handles* — recreate additionally requires `meta.rail_version` ≥ the
lock-taking rail's version in BOTH services' last-boot markers
(written at startup), i.e. recreate is lawful only after every
service has restarted onto the rail — a pre-rail descriptor cannot
exist; (3) *temp-WAL* — the temp DB is built in rollback-journal
mode (`journal_mode=DELETE`), fully closed, and verified
sidecar-free before the rename.

**§2 edit rule**: formally amended to §12's lineage mechanism
(`edits_intent`); the §2 sentence describing result-supersession for
edits is void — DDL wins.

## 15. Pass 8 — round-7 folds (DDL revision 6) and S1 authoring begins

**In DDL rev 6** (15 new negative controls executed; all reject;
lawful paths pass): R7-01 closed with `COALESCE(..., 'missing')` — a
missing prior result now blocks the next reservation instead of
slipping past SQL-NULL; R7-02 chronology bound (run ≤ intent ≤
reservation ≤ observation, retry reservations after the prior
observation); **R7-03 resolved by giving reservations their own
`authorized_run`** — the intent's originating run is a historical
fact, the authorizing run is the current active max-epoch run, so a
takeover epoch has a lawful retry path (executed: superseded r1's
intent retried under r2; stale authorizer rejected); R7-04 symmetric
(a correction turn hosts exactly one constituent, from either
direction); **R7-05 exhaustive evidence** — outcome closures must
cite *every* current head of the turn and resolved labels forbid
observation-less reservations; R7-06 split: new intents/reservations
on a closed turn are trigger-refused, late observations remain
lawful, and `closure_consistency_violations` (a view, asserted empty
by the reconciler and every witness) detects a current closure
invalidated by late knowledge — executed: the view flagged exactly
the late-ack case; R7-07 mapped (`suppressed` = all heads suppressed;
`unresolved_crash` = reconciler-only, never contradicting delivered
evidence); R7-08 id discipline (`length>0`, byte-length equality
kills embedded NUL and multibyte, printable-ASCII GLOB) on every id
plus transport and event identity; R7-09 finite/causal time completed
(admission, seals, folds, claims-vs-run); R7-10 reply parents must be
inbound turns, corrections descend from owner messages, and the
`turn_kind` CHECK domain is pinned in the v2 turns baseline.

**S1 witness protocol committed** at
`docs/superpowers/witness/theme2-s1-protocol.md` (v1): 24-cell
resolution table, latch crash/advance/checkpoint/foreign cases,
consumer-refusal outage test with exact-set zero-gestation-stamp SQL,
AST census with seeded-consumer kill, flags-off invariance, and the
six-mutation structural fingerprint test. Per §8 discipline it
precedes any S1 code.
