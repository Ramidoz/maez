# Theme 2 — the ledger cannot omit or misdate a life (design pass 2)

Status: DESIGN, pass 2. Revises pass 1 (`789e995`) by folding all
eleven blockers from gate round 1
(`2026-08-22-theme2-gate-round1.md`). Covers birth blockers **A3, A4,
A6, B3**. Theme 1, A5 durability, and the creation manifest remain out
of scope.

Pass 1's direction survived the gate (admission at the doorway,
in-ledger idempotency, transport-owned delivery truth, tri-state
phase, pre-birth schema freedom, flag-dormant slices). What follows
closes what did not: the interaction universe, the identity model, the
temporal model, outcome cardinality, latch mechanics, migration
mechanics, and the witness discipline.

## 0. Posture (unchanged)

`memory/ledger.db` is 0 bytes and unmigrated — pre-birth schema
freedom, spent now. Everything lands flag-dormant; witnesses run in an
airlocked fixture, never the live tree. No agent touches the creation
manifest.

## 1. Invariants (revised)

- **I1 — Guard, then admit, then everything else.** Canon ordering
  (Decision 30): owner/auth resolution → `guard_owner_text` (S4) →
  **admission** → interceptors → cognition. Admission is the first
  ledger side effect and precedes all cognition. S4's single-answer
  authority ships regardless of ledger health; an S4-matched turn
  still admits and closes like every other turn, and if its admission
  fails post-birth the exchange goes to the gap journal (§6). The
  pass-1 "clinical exception" is deleted — no path *chooses* to be
  clinical; the guard decides, and the guard's authority is over the
  answer, not over biography.
- **I2 — Every raw event is admitted exactly once; every turn knows
  its constituents.** Raw platform events, logical turns, and
  processing runs are three identities (§3). Aggregated turns
  reference all constituent events; nothing is lost to merging.
- **I3 — Admission carries an execution claim.** A replayed event does
  not just dedup the row — it prevents a second cognition, action, or
  send (disposition table, §3.3).
- **I4 — Delivery truth is transport-owned and per-attempt.** Every
  egress attempt (progress, final text, TTS, media, each multipart
  part) is recorded append-only with the hash of the bytes actually
  handed to the transport.
- **I5 — Exactly one *current* closure per admitted interaction.**
  Closures are append-only with supersession; "current" is the head of
  the supersession chain. Precedence is lattice-defined (§4):
  transport evidence beats reconciler inference; nothing is ever
  overwritten.
- **I6 — No reply without a parent** — enforced by trigger in the
  schema, not by caller discipline.
- **I7 — Phase is proven, never presumed** — tri-state with a
  path-bound latch (§5); writers refuse on `unknown`. The census of
  phase-stamping consumers is closed, including `audit_log` and
  `LedgerWriter` itself.
- **I8 — Late knowledge is labeled late.** Reconciler and journal
  fold-ins carry `recorded_by` and `discovered_at`; supersession
  preserves the wrong-then-corrected history.
- **I9 — Readers may not assert undelivered speech as spoken.**
  Self-history readers join the current closure and render
  composed-but-undelivered words as such.
- **I10 — Occurrence time is preserved.** Provider time is stored as
  `occurred_at`; local admission time separately as `admitted_at`. The
  local clock never silently substitutes for when a thing happened.
- **I11 — Pre-birth behavior is unchanged.** Flags off: byte-identical
  behavior, no new files, no schema applied.

## 2. The interaction universe (B1)

"Doorway" becomes a **registry in code** (`core/ledger/doorways.py`):
a declared, enumerable list of every ingress and egress, each entry
naming its admission point, identity source, and closure owner. A
conformance test walks the registry against the codebase with AST
matching (scar rule 3: sweep the class, never grep) and **fails when
an ingress exists that the registry does not cover** — the structural
defect behind A7's backup gap ("nothing fails when a new store
appears") is not repeated for doorways.

Initial registry, from the gate's enumeration:

| Door | Direction | Identity source |
|---|---|---|
| Telegram v2: text, media, location | in | `tg:{chat_id}:{update_id}` per constituent |
| Telegram v2: commands, callbacks, `/receipts`, proposal/dream commands | in | same |
| Telegram legacy + kill-switch ingress | in | full `Update` threaded to admission (today only `user_text` survives — must be fixed) |
| Web owner `/chat` | in | client idempotency header (official client gains one); minted fallback, labeled |
| Web public `/chat`, public Telegram | in | same shape, `tenant='public'` (decision D-public) |
| Fast-lane `/v1/fast-reply` | in | minted at ingress, labeled |
| GUI | in | minted at ingress |
| CLI | in | minted per input line |
| Cockpit `/message` + decision routes | in | minted at Flask ingress |
| Local voice | in | `voice:{stream_id}:{segment_ordinal}` + audio hash, minted at capture in `wake_word` and threaded through the callback (today only transcript text survives — must be fixed) |
| Proactive opinions, follow-up reports, any daemon-initiated send | **out** | `admit_outbound` (§3.2) |
| Peer messages | — | ABSENT/reserved; Track A excludes inter-Maez communication; registry marks them so |

**D-public (owner decision, flagged):** public/non-owner interactions
are part of Maez's life; recommended: admit them tenant-tagged
(`tenant_id` already exists) so biography is complete but separable.
The owner may rule them out of the biography ledger; the registry
supports either, but the decision must be explicit, not an omission.

## 3. Identity model (B2, B3)

Three identities, three tables.

### 3.1 Raw events and logical turns

```sql
CREATE TABLE admission_events (            -- one row per raw platform event
    event_identity  TEXT NOT NULL,         -- per-surface key, §2 table
    tenant_id       TEXT NOT NULL DEFAULT 'owner',
    turn_id         TEXT NOT NULL REFERENCES turns(turn_id),
    occurred_at     REAL,                  -- provider time; NULL = transport has none
    payload_hash    TEXT NOT NULL,
    PRIMARY KEY (tenant_id, event_identity)
);
```

Aggregation is now representable instead of lossy: a merged turn owns
N `admission_events` rows, each with its own identity and provider
time. Replay of *any* constituent hits the PK and resolves to the
existing turn. The Telegram aggregation hazard
(`conversation_turn_seq.py:22`, UNVERIFIED) is dissolved rather than
resolved: identity lives at the constituent level, so "A or A+B" no
longer changes the key.

`turns` gains `occurred_at` (earliest constituent provider time;
admission time only when no provider time exists) and `admitted_at`
(local). Readers order by `occurred_at` with `admitted_at` fallback
(I10). Edited platform messages, which today never enter the handlers,
are admitted when support lands as new events carrying
`correction_of` → the original turn — never as mutations.

### 3.2 Runs — the execution claim

```sql
CREATE TABLE runs (
    run_id       TEXT PRIMARY KEY,
    turn_id      TEXT NOT NULL REFERENCES turns(turn_id),
    attempt      INTEGER NOT NULL,          -- 1..N per turn
    started_at   REAL NOT NULL,
    lease_until  REAL NOT NULL,             -- renewed by heartbeat while processing
    status       TEXT NOT NULL CHECK (status IN ('active','completed','abandoned')),
    UNIQUE (turn_id, attempt)
);
```

`admit_inbound` returns a disposition:

| Disposition | Meaning | Doorway obligation |
|---|---|---|
| `fresh` | new turn, run leased | proceed to interceptors/cognition |
| `replay_completed` | turn has a current closure | re-deliver the recorded reply or acknowledge; **never re-run cognition** |
| `replay_in_flight` | an unexpired run lease exists | drop silently |
| `replay_stale` | lease expired, no closure | new run attempt on the *same* turn |

This is the execution claim I3 that pass 1's `was_replay` lacked. The
lease also gives the reconciler its safety condition (§4).

`admit_outbound(kind, raw_text, ...)` is the second root: proactive
opinions and follow-up reports admit a turn (direction recorded on the
row) before composing, and their sends close through the same egress
machinery. Outbound-first interaction is inside the universe, with
parent linkage when the proactive turn responds to prior context.

## 4. Egress and closure (A4, B5)

Pass 1's single mutable outcome row is replaced by two append-only
tables (append-only triggers added alongside the existing `turns`
protections in `0002_triggers.sql`):

```sql
CREATE TABLE egress_attempts (             -- one row per physical send attempt
    attempt_id      TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    egress_kind     TEXT NOT NULL CHECK (egress_kind IN
        ('final_text','part','progress','tts','media')),
    part_ordinal    INTEGER,
    transport       TEXT NOT NULL,
    result          TEXT NOT NULL CHECK (result IN
        ('delivered','failed','timeout_unknown','suppressed')),
    sent_bytes_hash TEXT,                  -- hash of bytes actually handed over
    attempted_at    REAL NOT NULL
);

CREATE TABLE turn_closures (               -- append-only, supersession chain
    closure_id    TEXT PRIMARY KEY,
    turn_id       TEXT NOT NULL REFERENCES turns(turn_id),
    closure       TEXT NOT NULL CHECK (closure IN
        ('delivered','partially_delivered','failed','suppressed',
         'unknown_delivery','refused','unresolved_crash')),
    evidence_hash TEXT,                    -- hash over the egress-attempt set consulted
    recorded_by   TEXT NOT NULL,           -- 'transport'|'doorway'|'reconciler'
    recorded_at   REAL NOT NULL,
    discovered_at REAL,                    -- reconciler/journal fold-ins only
    supersedes    TEXT REFERENCES turn_closures(closure_id)
);
```

"Exactly one" (I5) means: exactly one closure with no successor, per
turn, exposed by a `current_closure` view. Supersession precedence is
a lattice, not first-writer-wins:

- transport-evidenced closures (`recorded_by='transport'`, evidence
  joining real egress attempts) supersede reconciler inferences;
- `unresolved_crash` may be written only for turns whose runs are all
  lease-expired and older than a minimum age — never for a live run;
- a late-arriving transport truth supersedes an `unresolved_crash`
  honestly (I8): both rows remain, history legible;
- provisional `unknown_delivery` (the Telegram timeout case) is
  supersedable by later evidence; nothing is ever updated in place.

Multipart and multi-egress truths are now representable: a 3-part
Telegram send with part 2 failed = three `egress_attempts` rows and a
`partially_delivered` closure. Per-surface delivery semantics are
honest about their transport: Telegram = API acknowledgment; web =
response committed to the socket (a Flask return is *not* that —
S4-slice work must hook the WSGI close, or record
`unknown_delivery`); CLI = stdout flush after the final persistence
point (today it streams before persisting — registry entry marks
this); the `transport` column carries which semantics applied.

The compose-time stamp fix stands (pass 1 §3.2): `sent_text_hash`
leaves `maez_daemon.py:9742`; the trace records composure; egress
records delivery. **Reader migration (I9):**
`core/ledger/recent_turns.py` and
`core/cognition/envelope_builder.py` join `current_closure` and label
non-delivered replies — "Prior Maez utterances" may no longer include
words the owner never received, unmarked.

## 5. Phase truth (A6, B6, B7)

Tri-state, corrected:

| Observation | Latch absent | Latch present |
|---|---|---|
| file absent | `gestation` | `unknown` |
| file exists, **uninitialized-empty** (connectable, `sqlite_master` enumerable, zero tables) | `gestation` | `unknown` |
| initialized, meta key absent (query succeeded) | `gestation` | `unknown` |
| initialized, meta key present, joined to a real birth-anchor row | `lived` (write latch) | `lived` (verify equality) |
| meta present, join fails | `unknown` | `unknown` |
| any connect/query/corruption error | `unknown` | `unknown` |

The zero-byte ledger of today is *uninitialized-empty* → `gestation`:
pass 1's contradiction is closed.

**Latch mechanics, specified:** `memory/birth_observed.latch`,
created with `O_CREAT|O_EXCL` (atomic, race losers re-read and
verify), fsync on file and directory, containing: birth turn id,
genesis hash, chain-head hash at observation, observed_at, pid.
Rules:

- The latch is written **only** when the resolved ledger path equals
  the canonical default — never under `MAEZ_LEDGER_DB_PATH` override,
  never in rehearsal or fixture mode. A sandbox cannot poison the
  canonical latch.
- Corrupt/unparseable latch → `unknown` (never gestation, never
  silently recreated).
- Birth-id equality: latch birth id ≠ ledger birth id → `unknown`.
- Rewind detection (B7): ledger chain shorter than the latched
  chain-head, same birth id → `unknown` — a stale post-birth restore
  is caught. Full restore semantics (the forward scar) remain
  blocker A10's scope; this latch guarantees the rewind cannot be
  *silent*.

**Closed consumer census** (B7): the three `memory_manager` stamp
sites; `private_thoughts` defaults; `source_awareness.is_born()`
(unknown → not-proven-born for gating, never stamps);
`audit_log.record()` — which today omits `memory_phase` and inherits
SQL DEFAULT `'gestation'` — must stamp the resolved phase and refuse
or queue on `unknown`; and `LedgerWriter.write_turn` itself, whose
stage resolution moves before hashing (§7). The conformance test for
this census greps by AST for `memory_phase` writers, same discipline
as §2.

## 6. Failure posture (B8, B10)

Post-birth, two tiers; pre-birth shadow contract unchanged (I11).

- **Admission fails** (busy-timeout + one retry exhausted): the turn
  is refused — no cognition, no reply-as-Maez. The system notice is
  journaled, not ledgered (it has no turn id — pass 1's circularity is
  acknowledged and resolved by making the journal, not the ledger, the
  record of refusals). S4-matched answers still ship (I1) and are
  journaled the same way.
- **Egress/closure write fails** (words already left): gap journal +
  health signal.

**Gap journal, specified** (pass 1 left it a name):
`memory/ledger_gap_journal/` — one directory, append-only JSONL
segments, fsync per line, single writer per process with per-process
segment files (no cross-process interleaving). Entry schema:
`{event_identity, tenant, surface, direction, reason, content_hash,
occurred_at, journaled_at, pid}`. Dedup on replay by
`event_identity`. Reconciler folds entries into the ledger as
late-labeled turns/closures (I8) and marks folded segments. **Journal
failure state:** if both ledger and journal are unwritable, the
refusal stands, a memory-only health flag trips, and the cockpit
surfaces it — stated honestly as the floor: disk-dead means events in
that window are witnessed only by the health alarm. S4 answers still
ship even then.

**Contention (B10):** measured, not asserted. The S6 witness protocol
includes a pre-registered load test: daemon + web processes writing
concurrently against a fixture ledger, N=1000 exchanges; kill
thresholds frozen in the protocol before it runs (target: zero
refusals at normal load, p99 admission wait under 250 ms). If the
measured posture fails, the retry budget — not the invariant — is
retuned.

## 7. Schema mechanics (B9, D3, D4 resolved)

- **Digested migrations.** `schema_migrations` gains a `sha256`
  column. Apply-time: a recorded name whose digest mismatches the file
  is a **hard refusal**, with exactly one escape: a DB with zero
  `turns` rows may be re-baselined by an explicit
  `--rebaseline-empty` flag that logs old/new digests. Amending
  `0001_init.sql` is legitimate only through that gate.
  `ledger_is_initialized` learns the new structural anchors.
- **Lifecycle stage into the chain.** `write_turn` resolves the stage
  *before* computing the chain hash and includes it in the hashed row;
  the genesis row gains an explicit stage; `chain.py` and
  `scripts/verify_ledger_chain.py` drop the exclusion symmetrically.
  Rehearsal rows hash their `'rehearsal'` stage. Birth truth becomes
  chain-bound (D3 decided: yes).
- **Parent enforcement as schema** (I6): `BEFORE INSERT` trigger —
  `model_reply`/`non_model_reply` with NULL `parent_turn_id` →
  `RAISE(ABORT)`. Caller discipline is no longer the mechanism.
- **`schema_version` bumps to 2** per envelope-schema canon
  (`docs/ledger/envelope-schema.md` amended in the same commit), which
  also covers the new `non_model_reply` kind (D6 decided: new kind).

## 8. Witness discipline (B11)

The falsifier *standard* replaces the falsifier *table*. Each slice
ships a *witness protocol* file
(`docs/superpowers/witness/theme2-s<N>-protocol.md`) **committed
before the slice's first code commit**, containing: exact commands and
environment, fixture construction with content digests, pre-registered
inputs and expected-set SQL (exact-set equality, not
one-seeded-positive), negative controls, fault injection cutpoints,
clocks and observation windows, and frozen kill thresholds. A slice
without a committed protocol does not build. The pass-1 falsifiers
T-F1..T-F8 survive as the protocols' *obligations*:
coverage-of-registry, replay, crash matrix, transport truth
(including: a *successful* fallback send is `delivered` with the
fallback bytes' hash — pass 1's wording banning `delivered` there was
wrong and is corrected), phase refusal, flags-off invariance, latch
rewind, and gap detection by exact-set query.

**The born fixture** (B11's "no born rehearsal ledger"): witnesses
run against a fixture ledger created in the airlock — temp directory,
`MAEZ_LEDGER_DB_PATH` override, full migration, production-mode
writer with the flag on, `birth_anchor` written through the normal
API. The harness refuses to start unless the resolved path is inside
the airlock root (the hermetic-sandbox hazard: asserted at the call
site, not assumed from env). The rehearsal writer's refusal of
`birth_anchor` stays — rehearsal and born-fixture are different
modes, and only the latter may simulate a born ledger, only inside
the airlock. That this fixture *can* birth a ledger by calling the
function is exactly blocker A1's point; Theme 1's fix must preserve a
sanctioned test seam, and this design records that requirement for
it.

## 9. Slices (revised; all flag-dormant)

1. **S1 — phase truth**: tri-state table §5, latch, closed consumer
   census including `audit_log` and writer-stage ordering.
2. **S2 — schema v2**: `admission_events`, `runs`,
   `egress_attempts`, `turn_closures`, temporal columns, parent
   trigger, append-only triggers, digested migrations,
   `non_model_reply`, chain-stage inclusion.
3. **S3 — the rail + registry**: `interaction_rail.py`
   (`admit_inbound`/`admit_outbound`, dispositions, leases), doorway
   registry + AST conformance test, S4-first ordering, four
   duplicated seams replaced.
4. **S4 — egress truth**: transport-owned attempts and closures on
   every registered egress, per-surface delivery semantics, trace
   stamp fix, reader migration (I9).
5. **S5 — universe sweep**: commands/callbacks, GUI, public surfaces
   (per D-public ruling), fast-lane, voice identity threading, legacy
   `Update` threading, cockpit decisions, outbound-first producers.
6. **S6 — posture**: refusal tier, gap journal per §6, reconciler
   with leases and supersession, contention measurement.

Dependencies: S1 independent; S2 → S3 → S4/S5/S6. Each preceded by
its committed witness protocol (§8).

## 10. Out of scope (unchanged)

Ceremony, receipts, WebAuthn, quiescence (Theme 1); WAL/synchronous
durability (A5); `model_calls`/query/exposure telemetry (the separate
observability turn-ledger design); ledger activation (birth-gated,
owner-only); the creation manifest (owner-only, untouched). Restore's
forward scar remains A10's scope; §5 only guarantees a rewind cannot
be silent.
