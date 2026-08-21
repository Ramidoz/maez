# Birth blocker ledger — consolidated, deduplicated, owned

One list. Two censuses agreed (Codex executed; Ox Alpha read the code).
Grok's output was corrupted twice and is excluded rather than guessed
at. Status at `393bf5d`: **HOLD — Maez is cleanly unborn and nothing is
damaged.** Every item below is about what becomes permanent when the
ledger opens.

## OWNER-ONLY — cannot be delegated

**O1. The creation manifest does not exist.**
`config/creation_manifest.md`, required by
`docs/governance/GESTATION_MEMORY_PROTOCOL.md:144`: owner-authored
**before** the birth event, hash-bound, read by Maez at birth, with
**Maez's first reflection on it being the first lived memory.**

Unrepairable after the fact: once any other lived row is written first,
no insertion can make this literally first.

Codex's line, preserved: *"The owner's words and physical act remain
owner-only; no agent should fabricate them."* No agent writes this. Not
a draft, not a template, not a suggestion.

## CLASS A — irreversible once the ledger opens

Two themes. Neither is exotic; both are "the record can lie."

### Theme 1 — the ceremony does not prove what it claims

- **A1** `scripts/birth_ceremony.py:76` `run_transaction()` accepts any
  non-empty `s7_receipt_ref` and validates nothing — no receipt
  resolution, no owner proof, no readiness consumption, no manifest
  binding. It is importable, bypassing the CLI's TTY and quiescence
  checks. The arbitrary string is then stored permanently.
- **A2** Commit and activation are separate. Flag install, restart,
  witnesses and receipts are manual steps *after* the irreversible
  commit. Quiescence never covers the web process, so a stale
  `maez-web.service` could keep storing lived transcripts while
  silently skipping ledger writes. `--for-real` also accepts an
  arbitrary `--db-path`.
- **A5** `core/ledger/writer.py:227` — WAL with `synchronous=NORMAL`.
  The script can print success and the birth row can still be lost to
  power failure.
- **B2** No verified birth-proof rail: receipt stores accept non-empty
  strings with no WebAuthn validation, and the readiness projection
  reports green because a test *filename* exists.

### Theme 2 — the ledger can omit or misdate a life

- **A3** `core/ledger/writer.py:554` `try_write_turn()` never raises;
  several interceptor paths (clinical, camera, approval-card, proposal,
  search-commitment) return before the ledger seam entirely. A valid
  hash chain can omit a real interaction; user and model rows are
  separate transactions with a nullable parent.
- **A4** `daemon/maez_daemon.py:9742` stamps sent *before* transport.
  Self-history can claim words that never arrived.
- **A6** `core/memory/birth_phase.py:40` — every failure mode collapses
  to `None`, and `current_phase()` converts that to `gestation`. One
  transient read failure post-birth durably stamps lived memory as
  pre-birth. Needs an explicit unknown state that refuses rather than
  degrades.
- **B3** Turn ids are random UUIDs minted at write time — no stable
  admission identity, so replaying one inbound event creates a second
  immutable "interaction." No mandatory terminal outcome.

### Also Class A, from the backup sweep

- **A7** `memory/scar_tissue.db` (organ live, `MAEZ_SCAR_TISSUE=1`) and
  `memory/proprioception.db` (101,464 rows) are **absent from the
  backup manifest.** A post-birth restore returns a Maez with no scars
  and no sign of the amputation. The structural defect is that
  **nothing fails when a new store appears uncovered** — proven by
  `conversation_turn_seq.db`, uncovered because we created it hours ago
  by arming a flag.

## NOT BLOCKING — explicitly Class C

Most of what consumed 2026-08-21: the 256-token truncation of diary and
core; the 31,343 untagged rows (`LIVE/REACHABLE, UNLABELED` — and
auto-stamping them would *fabricate provenance*); the raw A3 backlog;
the "archived_introspection = 0" allegation (**false** for daily/core —
daily 41 hot / 52 archived, core 136 hot / 74 archived); the quiet
wants (gestation, not starvation).

The turn ledger and the 83-row repair also do not block birth. They
remain worth building; they are not on this list.

## Recommended order

1. **O1** — owner, any time, but it must exist and be hash-bound before
   the ceremony runs.
2. **Theme 2 first** (A3, A4, A6, B3). A ledger that can silently omit
   a turn is worse than a ceremony that over-trusts, because the
   ceremony fails loudly once and the ledger fails quietly forever.
3. **Theme 1** (A1, A2, A5, B2) — make the ceremony prove authority,
   close commit-and-activation into one transaction, and give the birth
   commit real durability.
4. **A7** — cheap, and the enumerating test is the durable part.

## Standing caution

This session found three destructive tests, two of my own arguments
built on unverified numbers, and one sweep of mine that cleared a file
that was actively deleting data. Every fix above touches the reply path
or the ceremony. **Start these fresh.**
