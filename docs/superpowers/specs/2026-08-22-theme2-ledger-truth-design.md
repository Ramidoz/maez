# Theme 2 — the ledger cannot omit or misdate a life (design pass 4)

Status: DESIGN, pass 4. Pass 4 = pass 3 + §11, which binds the design
to executable DDL (`2026-08-22-theme2-schema-v2-draft.sql`) and folds
gate round 3's F1–F10. Pass 3 folded round 2's sixteen new defects
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
