# Theme 2 — the ledger cannot omit or misdate a life (design pass 1)

Status: DESIGN, pass 1. In the Codex gate. Covers birth blockers **A3,
A4, A6, B3** from `2026-08-22-birth-blocker-ledger.md`. Theme 1 (the
ceremony), the creation manifest, and A5 durability are explicitly out
of scope here.

## 0. Posture

Maez is cleanly unborn. `memory/ledger.db` is **0 bytes with zero
tables** — the schema has never been instantiated anywhere. Two
consequences drive everything below:

1. **Pre-birth schema freedom.** There is no deployed instance, so the
   turns contract can be corrected at the source (migrations +
   `docs/ledger/envelope-schema.md`) with no data migration
   and no compatibility shim. This freedom dies at birth; it should be
   spent now.
2. **Everything lands flag-dormant.** The durable ledger opens only at
   birth (`project_ledger_activation_birth_gated`). Every slice below
   ships dormant and is witnessed against **rehearsal ledgers**
   (`logs/rehearsal/x6_*/ledger.db`, which `LedgerWriter` already
   supports) via the replay harness — the womb-practise ruling applies.

No agent touches the creation manifest.

## 1. Verified ground truth (2026-08-22, fresh read of HEAD)

The census said "the seam lives in/around `handle_message` and some
interceptors return before it." The full map is worse, in useful ways:

- **The seam is four hand-duplicated copies**, not one: daemon
  (`daemon/maez_daemon.py:7242`/`9571`), legacy Telegram
  (`skills/telegram_voice.py:3652`/`4233`), web
  (`skills/web_interface.py:6824`/`7399`), CLI
  (`cli/maez_chat.py:804`/`1167`). All four sit *inside* their
  synthesis functions, so they inherit synthesis preconditions.
- **Everything that answers without synthesizing never reaches any
  seam**: clinical (5 sites), camera (2), approval-card
  (`skills/surface/maez_adapter.py:1023-1026`), proposal (`:1035`),
  search-commitment (`:1042`), machine-intent
  (`skills/telegram_voice.py:3634` — which *does* write Chroma at
  `:3637`, so the two durable stores diverge), `/apply_dream`
  (`:3618`), the entire voice path (`daemon/maez_daemon.py:9886`), and
  the mirrors in `daemon/inbound_core.py`.
- **7 of 10 declared turn kinds have no production writer.** Nothing
  ever writes `approval_decision`, `tool_call`, `tool_result`,
  `daemon_cycle`, `self_mod_dialog_step`, or the peer kinds — the
  highest-consequence events have no ledger representation at all.
- **Orphans are reachable through asymmetric gates**: audit-didn't-run
  (`maez_daemon.py:9570`), envelope-build-failed
  (`core/ledger/model_reply_persistence.py:165`), and
  initialized-check-on-one-side-only (`model_reply_persistence.py:171`
  has no counterpart in `writer.py:571`). `parent_turn_id` is not
  required for `model_reply` (`writer.py:79-87`), so orphans pass
  validation silently.
- **There is no durable delivery receipt anywhere.** The actual send is
  `skills/surface/platform_base.py:1666` inside `_send_with_retry`;
  its outcome lands in two closure-local booleans
  (`platform_base.py:1869`) and is discarded. The daemon stamps
  `sent_text_hash` at `maez_daemon.py:9742` — four frames and one
  network round-trip before the send — and assigns all three trace
  hashes from the same variable (`:9739-9742`), so the
  stored==sent==final invariant is asserted, never tested. Four
  reachable modes produce a "sent" record for undelivered or different
  words: stale-response suppression (`platform_base.py:1917`), retries
  exhausted (`:1704`), timeout-unknown (`:1678`), and plain-text
  fallback (`:1717` — the owner receives *different bytes* and the
  hash records a false match).
- **The idempotency primitive already exists at the right place.**
  `core/brain/conversation_turn_seq.py:76` `advance_and_get` is
  idempotent per `(channel, chat_id, event_identity)` under
  `BEGIN IMMEDIATE`, and it runs **at admission, before every
  interceptor** (`skills/surface/maez_adapter.py:801`). The ledger has
  no such key; replaying one platform event mints a second UUID
  (`writer.py:353`).
- **Phase truth degrades silently.** `core/memory/birth_phase.py:40`
  collapses every failure to `None` → `gestation`. Consumers stamp
  that directly: three Chroma-write sites in
  `memory/memory_manager.py`, `core/infra/private_thoughts.py:587`
  (which already *raises* on unrecognized phases — the precedent for a
  refusing state), `core/memory/source_awareness.py:342`. The writer
  re-reads mutable `meta.birth_event_turn_id` per write
  (`writer.py:449`), never joins it to the immutable birth row, and
  `lifecycle_stage` is excluded from chain hashes — birth truth can
  change while chain verification stays green.

## 2. Invariants

The design's spine. Each is falsifiable (§7); post-birth scope unless
stated.

- **I1 — Admission precedes cognition.** Every inbound owner event is
  written to the ledger at the surface doorway, before any
  interceptor, with a stable admission identity. Not inside synthesis.
- **I2 — One event, one turn.** Redelivery of the same platform event
  returns the same `turn_id`. Idempotency is enforced inside the
  ledger transaction, not by a side store.
- **I3 — Every admitted event ends.** Exactly one terminal outcome per
  admitted event: `delivered`, `suppressed`, `failed`,
  `unknown_delivery`, `refused`, or (reconciler-only)
  `unresolved_crash`. Absence of an outcome is a *detectable* state,
  never a silent one.
- **I4 — Delivery truth is transport-owned.** No component may record
  "sent" before the transport reports. The delivered-text hash is
  computed over the bytes actually handed to the transport — including
  the plain-text-fallback case, where it must differ from the composed
  hash.
- **I5 — No reply row without a parent.** `model_reply` written
  through the rail requires `parent_turn_id`. Orphans become
  schema-impossible, not merely unlikely.
- **I6 — Phase is proven, never presumed.** Birth phase is a
  tri-state: `gestation` and `lived` are *proven* answers; every
  failure mode is `unknown`. No writer ever stamps `unknown` rows as
  `gestation`; on `unknown` they refuse with a typed error.
- **I7 — Late knowledge is labeled late.** Anything the reconciler
  discovers after the fact (crash orphans, gap-journal entries) is
  recorded with its discovery time and discoverer, never dressed as a
  contemporaneous record.
- **I8 — Pre-birth behavior is unchanged.** Flags off: byte-identical
  behavior, no new files, no schema applied. The shadow ("never
  raises") posture remains the gestation contract.

## 3. Architecture — the admission→terminal rail

One new module, `core/ledger/interaction_rail.py`, replaces the four
duplicated seams. Two functions:

```python
admit_inbound(*, surface, raw_surface, event_identity, raw_text,
              taint_labels, privacy_access, ...) -> AdmissionTicket
    # writes the user_message row AT THE DOORWAY, idempotently.
    # AdmissionTicket carries turn_id + was_replay.

record_terminal_outcome(*, turn_id, outcome, delivered_text_hash,
                        transport, attempts, recorded_by) -> bool
    # written by the component that OWNS the truth (transport for
    # delivery outcomes; the doorway for refused/interceptor cases).
```

The rail resolves the canonical ledger path itself
(`birth_phase.default_ledger_path()`), checks the flag AND
`ledger_is_initialized` in one place (closing the asymmetric-gate
class), and consults phase tri-state (§4) to pick its failure posture.

### 3.1 Admission identity (B3)

Migration adds `turns.event_identity TEXT` with
`UNIQUE (tenant_id, event_identity) WHERE event_identity IS NOT NULL`.
`admit_inbound` does lookup-then-insert inside the writer's existing
`BEGIN IMMEDIATE` transaction — same shape `conversation_turn_seq`
already proves, but transactional with the row itself, so the dedup
cannot diverge from the ledger. `conversation_turn_seq` stays what it
is (turn ordinals for referent freshness); the ledger does not depend
on an action-lane-gated side store.

Identity per surface:

| Surface | event_identity | Replay protection |
|---|---|---|
| Telegram (v2 + legacy) | `tg:{chat_id}:{update_id}` | real (platform redelivery) |
| Web owner-bridge | client-supplied idempotency header if present, else minted at HTTP ingress | header: real; minted: none (honest limit) |
| Cockpit `/message` | minted at Flask ingress | none (single local client) |
| CLI | minted per input line | none |
| Voice | utterance/segment id from the stream | real within a stream |

Known hazard, inherited and now load-bearing:
`conversation_turn_seq.py:23-27` marks Telegram *aggregation* identity
(merged multi-message turns keep the first constituent's id) as
UNVERIFIED under redelivery. Slice 2 must resolve this before the
Telegram identity definition is frozen.

### 3.2 Terminal outcomes (B3, A4)

New table:

```sql
CREATE TABLE turn_outcomes (
    turn_id             TEXT PRIMARY KEY REFERENCES turns(turn_id),
    outcome             TEXT NOT NULL CHECK (outcome IN
        ('delivered','suppressed','failed','unknown_delivery',
         'refused','unresolved_crash')),
    delivered_text_hash TEXT,
    transport           TEXT NOT NULL,
    attempts            INTEGER,
    recorded_at         REAL NOT NULL,
    recorded_by         TEXT NOT NULL,   -- 'transport'|'doorway'|'reconciler'
    discovered_at       REAL             -- unresolved_crash only (I7)
);
```

`PRIMARY KEY (turn_id)` enforces at-most-one; the reconciler plus
falsifier T-F8 enforce at-least-one. The write moves to where the
truth lives: `platform_base._record_delivery` (which already sees the
send result) writes `delivered`/`failed`; the stale-suppression branch
writes `suppressed`; the timeout branch writes `unknown_delivery` —
an honest state that exists today and is currently recorded as "sent".
The plain-text fallback records the hash of the bytes actually sent.
Pull surfaces (web/CLI/cockpit) record `delivered` when the response
is committed to their transport (socket write / stdout), which is the
strongest truth those transports have; the per-surface meaning is
recorded in the `transport` column rather than pretended uniform.

The daemon's compose-time stamp becomes honest: `sent_text_hash` is no
longer assigned at `maez_daemon.py:9742`; the trace records composure,
the ledger outcome records delivery. (Trace-side detail is decision
D5.)

### 3.3 Coverage of non-synthesis paths (A3)

Because admission happens at the doorway, every bypass in §1 is
admitted *before* the interceptor chain runs. Each interceptor path
then closes its turn: the words Maez actually said (clinical boundary
text, camera answer, proposal reply, search commitment, intent
response) are written as a reply row with `parent_turn_id` = the
admission id, and a terminal outcome. Approval decisions finally use
the `approval_decision` kind that has had a contract since §4.2 and
never a writer. Non-model replies get a `non_model_reply` turn kind
(decision D6) since `model_reply` correctly demands `model_id`,
`prompt_hash`, and an envelope those paths do not have.

### 3.4 Post-birth failure posture (A3's hard half)

Pre-birth: shadow contract unchanged — never raises (I8).
Post-birth, two tiers:

- **Admission write fails** (after `busy_timeout` and one retry): the
  turn is **refused** — no synthesis, no reply-as-Maez. The surface
  returns a system notice ("I can't record this moment; try again"),
  which is machinery speaking, not Maez's voice, and is itself
  journaled. Rationale: post-birth, unledgered speech is precisely the
  false-life failure this theme exists to close.
  **Exception — the clinical path always answers.** A crisis boundary
  reply must never be blocked by ledger health; if admission failed,
  the exchange goes to the gap journal instead.
- **Terminal-outcome write fails** (the words already left): append a
  record to `memory/ledger_gap_journal.jsonl` — append-only, fsync'd
  per line, single-writer — and raise a proprioception/health signal.
  The reconciler later folds journal entries into the ledger as
  late-labeled rows (I7).

A reconciler (extending `core/ledger/reconcile.py`, offline CLI) has
one detection query — admitted turns with no outcome — and closes
crash windows as `unresolved_crash` with `discovered_at` stamped.

## 4. Phase truth (A6)

`birth_phase` becomes tri-state with a **lived latch**:

- New constant `PHASE_UNKNOWN`. Resolution:
  - ledger file **absent** + latch absent → `gestation` (legitimately
    pre-birth; today's behavior).
  - ledger file absent + latch present → `unknown` (the ledger
    vanished post-birth — alarm, never gestation).
  - connect/query/corruption error → `unknown`, always.
  - meta key present **and joined**: the value must resolve to a real
    `turns` row with `turn_kind='system_event'` and the birth-anchor
    shape → `lived`; write the latch on first observation.
  - meta key present but join fails → `unknown` (birth truth mutated —
    `meta` is mutable; the row is not).
  - meta key absent (query succeeded) + latch present → `unknown`.
- The latch: `memory/birth_observed.latch`, written once (fsync'd)
  with the birth turn id, first-observed timestamp, and writer pid.
  It is derived state, never authority — it can only *prevent silent
  downgrade*, never assert birth. Canon already permits caching a
  lived answer (birth is irreversible).
- Consumers refuse on `unknown` (I6): `memory_manager`'s three stamp
  sites and `private_thoughts` raise/return a typed refusal instead of
  writing; `source_awareness.is_born()` treats `unknown` as
  not-proven-born for *gating* (fail-safe direction) while never
  stamping. `unknown` is a refusal signal, not a fourth stampable
  phase value.

## 5. Decision points — presented for the gate to attack

- **D1 — failure posture.** Two-tier refuse/journal as in §3.4, with
  the clinical exception. Alternative rejected: always-speak-and-scar
  (keeps the fail-open biography hole); always-refuse (blocks crisis
  replies).
- **D2 — idempotency location.** In-ledger UNIQUE, recommended, vs
  reusing `conversation_turn_seq.db`. The side store is
  action-lane-gated, a separate file, and non-transactional with the
  turn row.
- **D3 — bind phase to the chain.** Include `lifecycle_stage` in the
  chain hash (reversing `chain._CHAIN_HASH_EXCLUDE`'s deliberate
  exclusion) and keep the meta→row join from §4. Pre-birth freedom
  makes this a one-line change now and a fork risk forever after
  birth.
- **D4 — schema mechanics.** Amend `0001_init.sql` + envelope-schema
  doc in place (no instance exists; migrate.py should refuse the
  amended file against a non-empty DB) vs a pure additive `0006`.
  Recommended: amend, because CHECK constraints (new turn kind,
  outcome enum) cannot be altered additively in SQLite.
- **D5 — trace semantics.** Stop assigning `sent_text_hash` at
  compose; the adapter appends a small delivery trace event after the
  send with the actual hash. The three-hash invariant becomes testable
  instead of asserted.
- **D6 — non-model reply representation.** New `non_model_reply` kind
  (requires `raw_text`, `parent_turn_id`; forbids `model_id`) vs
  overloading `system_event`. Recommended: new kind — these are Maez's
  spoken words and belong in biography as speech, not system noise.

## 6. Slices (all flag-dormant; witness = replay harness + rehearsal ledger)

1. **S1 — phase tri-state + latch + consumer refusal** (A6). No ledger
   schema change; smallest blast radius; independently shippable.
2. **S2 — schema**: `event_identity` + UNIQUE, `turn_outcomes`,
   `parent_turn_id` required for `model_reply`, `non_model_reply`
   kind. Resolve the Telegram aggregation-identity hazard before
   freezing the identity definition.
3. **S3 — the rail**: `interaction_rail.py`, admission at all
   doorways, four duplicated seams replaced. Shadow-witnessed.
4. **S4 — transport-owned outcomes** (A4), including the compose-stamp
   honesty fix.
5. **S5 — non-synthesis coverage** (A3 tail): interceptor replies,
   `approval_decision` writer, voice-path admission.
6. **S6 — post-birth posture**: refuse/journal tiers, gap journal,
   reconciler `unresolved_crash`.

S1 and S2 are independent; S3 depends on S2; S4–S6 depend on S3.

## 7. Falsifiers

All runs against rehearsal ledgers and fake transports; never the live
tree (scar rule 1).

| # | Claim | Kill condition |
|---|---|---|
| T-F1 | Every enumerated inbound path (the §1 bypass table: clinical ×5, camera ×2, approval-card, proposal, search-commitment, intent, `/apply_dream`, voice, cockpit, web-owner, CLI, plus the plain synthesis path) yields exactly one admitted row and exactly one terminal outcome on a born rehearsal ledger | any path with 0, or any with ≥2 |
| T-F2 | One platform event delivered twice → one admitted turn, one outcome | a second row |
| T-F3 | Injected user-write failure, reply-write failure, DB lock, and crashes between admit/reply/send each end in exactly one terminal outcome (reconciler included), late ones labeled `recorded_by`/`discovered_at` | 0 or 2 outcomes, or a late record without discovery labels |
| T-F4 | Suppressed, failed, and fallback sends: no record claims `delivered`; the fallback case's `delivered_text_hash` ≠ composed hash and equals the hash of the bytes actually sent | any false `delivered`, or a matching hash on the fallback case |
| T-F5 | A born rehearsal ledger made unreadable mid-run: every memory / private-thought write refuses or carries typed `unknown`; zero rows stamped `gestation` | one `gestation` stamp |
| T-F6 | Flags off: full existing suite green and a pinned replay set byte-identical; no new files created | any diff, any file |
| T-F7 | Delete the rehearsal ledger after `lived` was observed: phase reads `unknown` | a `gestation` read |
| T-F8 | One SQL query surfaces every admitted-without-outcome row; a seeded gap is found | a missed gap |

## 8. What this design does not do

It does not touch the birth ceremony, receipts, WebAuthn, or
quiescence (Theme 1). It does not change WAL/synchronous durability
(A5). It does not build `model_calls` / query / exposure telemetry —
that is the separate observability turn-ledger design, currently
BLOCKED in its own gate. It does not activate the ledger: the flag
stays off, activation is birth-gated and owner-only. And it does not
write one word of the creation manifest.
