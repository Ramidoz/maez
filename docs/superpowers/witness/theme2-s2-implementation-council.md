# Theme-2 S2 implementation council — the fixes, the topology, and a falsified premise

Convened 2026-08-23, per the standing directive, BEFORE building the
single-owner topology and the U5-replacement falsifier. Three fresh seats,
each told the others' conclusions and instructed to attack them:

- **Seat A — Claude** (general-purpose subagent, repo access)
- **Seat B — stealth preview** (`opencode/x-preview-f-free`, no repo access)
- **Seat C — Codex** (`codex exec`, xhigh, repo read-only)

Full texts: `scratchpad council-seat-*.txt` were session-local; the durable
findings are folded here and into the code/tests they changed.

## Headline: a unanimous council claim was FALSIFIED by execution

The prior U5 council (also three seats, unanimous) and the handoff both
stated that `model_reply_persistence.py`'s bare `sqlite3.connect` marker
write "fails at 0 ms under contention." **A live probe disproved this
before any fix landed**: Python's `sqlite3.connect` default `timeout=5.0`
installs a busy handler; the old code waited 1.53 s under a held
`BEGIN IMMEDIATE` and succeeded. "Verified in the code" had verified the
absence of an explicit `busy_timeout`, not the runtime behavior. Seat C
independently confirmed the falsification against the Python docs.

Consequences, all landed:
- The fencing change shipped as **documented hardening with a pinning
  test**, not as a RED→GREEN bugfix; the test says so in its docstring.
- The REAL defect adjacent to the false one — marker turn and meta row
  written in two transactions, guaranteeing duplicate "one-time" markers
  across the crash/failure window — was found, fixed atomically
  (`write_turn(meta_marker_keys=...)`, write-once enforced inside the
  transaction), and proven by tests.

Lesson recorded to memory: unanimity is not execution. Every claim a
council hands you that CAN be executed MUST be executed before it is
encoded.

## Convergent findings adopted (what actually landed)

All three seats, largely independently:

1. **No second rollout flag.** A `MAEZ_LEDGER_SINGLE_OWNER` flag would
   keep the forbidden two-writer state reachable as a configuration cell
   (`WRITES=1, SINGLE_OWNER=0`). Landed instead: a **structural owner
   latch** — an ENABLED `LedgerWriter` holds an flock on
   `<db>.ownerlock` for its lifetime; a second concurrent enabled writer
   refuses at construction, across processes, SIGKILL-safe. Dormancy is
   carried by `MAEZ_LEDGER_WRITES` alone.
2. **Owner identity must be explicit and dual-module-safe.** Landed:
   env-pid claim (`core/ledger/owner.py`), claimed in `MaezDaemon.start()`
   — deliberately not at import, so importing the daemon module can never
   make a test process believe it owns the ledger.
3. **Long-lived owner writer, lazy, with a live brake.** Landed: singleton
   constructed on first enabled write; the writes flag re-read per write;
   environmental failures self-heal; refusals keep the writer.
4. **Identity before the first attempt.** Landed partially: an
   `attempt_id` is minted at `try_write_turn`/`owner_write_turn` entry and
   stamped into any dead-letter record. The schema-level half (a UNIQUE
   submission identity in the DB) is the admission-protocol gap below.
5. **Dead-letter mechanics.** Landed: per-process sidecar files (no
   cross-process interleaving), single-syscall complete write + file fsync
   + parent-dir fsync on create, 0o600, set-typed kwargs coerced
   losslessly, `refused` vs `failed` classification (refusals are
   quarantine evidence, never blind replay candidates), machine-readable
   `dead_letter_status()` (logs are not operator state), gitignored,
   covered by the backup manifest (weakest-archive rule).

## Transport: the handoff's "/message rail" is REJECTED as specified

The handoff said web/CLI should enqueue "through the /message rail that
already exists." Two seats independently verified the mechanism this
would ride: the daemon's Flask app is served by
`werkzeug.serving.make_server` **without** `threaded=True`
(daemon/maez_daemon.py:13228 area) — one request at a time — and
`/message` runs full LLM synthesis inline in the request handler. Every
ledger append would queue behind tens of seconds of inference; client
timeouts would make dead-letter the ROUTINE path. Further verified gaps:
no idempotency key (timeout-after-commit duplicates on replay), no
token distribution to a bare CLI (`_s7_internal_channel_trusted`
requires an env-provisioned secret), a `{turn_kind, raw_text, kwargs}`
API is a confused deputy (callers could submit `birth_anchor` and
authority fields), no size caps.

**Decision: honor the ruling's substance (one serialized owner — landed
structurally), do not build the defective transport.** Until the
transport slice lands, a non-owner process under a live owner
dead-letters (never silent, never a second concurrent writer). Candidate
designs recorded for the next council, undecided:

- **Client-local durable spool** (Seat A): each surface appends to its
  own spool dir; filename = client-minted submission id = idempotency
  key; the owner tails and commits; works while the daemon is down; no
  token distribution problem; collapses queue and dead-letter into one
  designed thing.
- **Dedicated bounded socket** (Seat C): separate UDS/HTTP server inside
  the daemon (never the single-threaded health/chat server), typed
  request schema, closed producer identity, size caps, ACK only after
  COMMIT, UNKNOWN on timeout with idempotent retry.

## The groupthink finding (Seat C, confirmed by the falsifier's development)

> Everyone moved the SQLite connection into one process and treated that
> as completion of the life-event transaction. The unsolved problem is:
> **durable admission → stable identity → idempotent commit →
> chain-bound acknowledgment → honest UNKNOWN recovery.**

One owner is necessary and nowhere near sufficient. The ledger schema
has no submission identity (only writer-minted `turn_id`), so replay
cannot yet be made exactly-once by construction, and replayed rows would
carry replay-time timestamps and chain positions unless replay stamps
explicit reconstruction provenance (canon-governs-canon rule). **The
admission-protocol slice — schema identity + typed enqueue + provenance-
stamped replay — precedes the transport, the replay organ, and birth.**

## The falsifier (replaces U5)

`theme2_s2_falsifier.py`, report `theme2-s2-falsifier-report.json`.
Boolean arms, never p99: F1 exactly-once/byte-exact via independent
oracle + chain contiguity + integrity_check; F2 non-owner exclusion
under a live owner (zero rows land, every attempt preserved in
dead-letter); F3 checkpoint honesty (TRUNCATE's returned busy flag
checked under a pinning reader — not merely "SQL ran"); F4 repeated
SIGKILL of the owner at a deterministic ack-log barrier, recovery by
identity, with `ACKED_BUT_MISSING` as the explicitly-named lethal class
and UNKNOWN as an honest third state; F5 pragma license (the claim is
NARROWED: `synchronous=NORMAL` certifies process-crash recovery, NOT
power-loss durability); PC positive controls that must trip for the
RIGHT reason (bare library refuses naming 3.51.3; held latch refuses
naming the owner).

**Evidence it can fail:** during development it went RED twice on real
gaps — F2 caught non-owner writes landing in the pre-claim window
(before the owner's lazy first write takes the latch), and F4's first
kill choreography would have re-appended committed indexes as
duplicates. Both are exactly the failure classes the council predicted.

## Open items (recorded, not hidden)

1. **Admission protocol** (identity in schema, typed enqueue, provenance-
   stamped replay) — precedes transport, replay organ, and birth.
2. **Pre-claim window**: between daemon start and its first enabled
   write, the latch is free and an unclaimed process could direct-write
   (serialized, never concurrent — but the owner should optionally take
   the latch eagerly at claim time).
3. **Direct constructors**: `scripts/birth_ceremony.py` and
   `core/ledger/reconcile.py` construct writers directly; under a live
   daemon they now refuse via the latch. Birth must stop the daemon or
   route through the owner — needs explicit ceremony treatment.
4. **synchronous=NORMAL**: power-loss durability is not certified;
   widening to FULL is an owner decision (cost: fsync per commit).
5. **Checkpoint policy**: no shipped owner checkpoint/WAL-growth policy;
   F3 certifies the mechanism on the owner connection, not shipped code.
6. **Dead-letter surfacing**: `dead_letter_status()` exists; wiring into
   the daemon status endpoint / cockpit real-state organ is unbuilt.
7. **Pre-existing red on main** (not from this work):
   `tests/test_no_bare_sqlite_connect.py` fails 3 tests naming
   `core/consent/bindings.py`, `core/consent/spine.py`,
   `core/consolidation/{shadow_dashboard,span_planner}.py`,
   `core/governance/operator_user_boundary.py`,
   `core/ledger/span_reader.py`, `core/routing/inner_continuity_facts.py`,
   `scripts/{s7_r11_preflight,cuda_cutover}.py`, and one frozen witness
   script. Left untouched: sweeping them exceeds this session's scope and
   one offender is a frozen witness artifact.
