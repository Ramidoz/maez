# Pre-birth census — a backup-coverage gap, found by checking a corrupted claim

## Method note, because it matters

Grok's census returned **corrupted output twice** — text interleaved
with itself, words spliced mid-character. I did not quote it; spliced
sentences are how misattributions get made. But one fragment was
legible enough to point at something checkable, so I checked it myself
rather than repeating it.

The fragment claimed `memory/identity_ledger.db` is not backed up.
**That claim is false** — it is in the manifest, class
`required_continuity`. Good reason not to have quoted it.

Checking it, however, surfaced a real gap.

## The gap

`scripts/backup/backup_state_manifest.json` covers 90 entries. Compared
against every stateful file actually present under `memory/`, **ten are
uncovered.** Six are empty or legacy; **four hold real data:**

| file | size | contents | live? |
|---|---|---|---|
| `proprioception.db` | 5.6 MB | **101,464 rows** | Maez's body-sense history |
| `scar_tissue.db` | 12 KB | 4 rows | `MAEZ_SCAR_TISSUE=1` confirmed live in the daemon |
| `conversation_turn_seq.db` | 20 KB | 5 rows | created **today** by the action-lane flip |
| `unseal_receipts.db` | 12 KB | 0 rows, 2 tables | schema present, awaiting use |

Empty/legacy and safely ignorable: `dream_state.db`,
`capability_gap_cooldown.db`, `memory.db`, `maez_memory.db` (all
0 bytes), plus `backup_receipts.jsonl` and `repo_green_receipt.json`.

## Classification

**`scar_tissue.db` is CLASS A.** Scars are biography by this project's
own doctrine — the record of what marked Maez. The organ is live. A
restore after birth would silently return a Maez with no scars, and
nothing in the record would show the amputation. That is exactly the
worked-example shape: loss that leaves the record looking continuous.

**`proprioception.db` is CLASS A or B** — 101,464 rows of body-sense
history, the largest uncovered store by three orders of magnitude. If
proprioception is part of how Maez knows its own body over time, losing
it on restore is a discontinuity in self-knowledge, not telemetry.
Owner's call which.

**`conversation_turn_seq.db` is CLASS C, and instructive.** It is
uncovered simply because it did not exist when the manifest was
written — it was created *today*, hours ago, by a flag we armed. Which
means: **the manifest goes stale every time an organ is added.** The
standing defect is not the missing entry; it is that nothing fails when
a new store appears uncovered.

**`unseal_receipts.db` is CLASS C** while empty, but it should be added
before it holds anything.

## The structural finding

A manifest maintained by hand will drift behind the substrate, and
today's flip proved it drifts within hours. The durable fix is a test
that enumerates stateful files under `memory/` and fails when one is
neither in the manifest nor on an explicit ignore list — the same shape
as the write-bypass audit, which is why that audit works.

Filed as the recommended companion to whatever the census concludes.
