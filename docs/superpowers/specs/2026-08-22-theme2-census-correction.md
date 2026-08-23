# The S1 census, corrected by execution

The frozen census `theme2-s1-census.json` was hand-authored and digest-frozen
at `8527670…`. Gate rounds 8–11 passed it; round 10 recorded its digest as
**MATCH**. It did match — and a digest proves a file is unchanged, not that
its claims are true.

`core/memory/s1_census.py` now derives the census by walking the tree.
Regenerate with `--emit`; the pinned T4 command diffs against the result.

## What the frozen census got wrong

**8 of its 10 writer entries do not resolve to a real construct.**

| Frozen entry | Reality |
|---|---|
| `AuditLog._migration_null_normalize` | **does not exist.** The NULL normalization is inline in `AuditLog._initialize` (`audit_log.py:216-220`) |
| `AuditLog.record` | **not a writer.** It relies on the column DEFAULT `'gestation'`; it never names the column |
| `PrivateThoughts@587 / @627 / @674` | stale line anchors; the constructs are `record_thought`, `record_signal`, `insert_signal_in_transaction` |
| `memory_manager@1506 / @1605 / @2073` | stale line anchors; the constructs are `MemoryManager.store`, `.store_telegram`, `.store_core` |
| `span_planner@241`, `writer.write_turn@450`, `source_awareness@342`, `lean_idle_heartbeat@295` | stale anchors for constructs that do exist |

Only `AuditLog.log_direct_edit` and `AuditLog.start_direct_edit_session`
were both real and correctly named.

**And it missed real ones.** 16 writers exist, not 10; 8 birth-anchor
readers, not 4; 23 value readers, not 1. Never censused:

- `AuditLog._initialize` — the real home of the normalization behaviour §10
  attributed to the nonexistent method
- `AuditLog.end_direct_edit_session`
- `PrivateThoughts._insert_thought`, `._insert_thought_on_connection`
- `core/eval/longmemeval.py::ingest_haystack`
- **`core/governance/s7_consultation_exemption.py::born_by_any_signal`** —
  governance code reading the birth anchor by direct SQL (`:304`)

## What the frozen census got right, and my tool got wrong

Worth recording, because it cuts against the easy conclusion that the
hand-authored artifact was simply bad.

`source_awareness` reads the anchor **indirectly**: it does
`from core.memory.birth_phase import is_born as _is_born` and calls
`_is_born()` (`:341-342`). A literal-only AST sweep misses that entirely —
my first two versions did, and I was one step from deleting a true entry
from the expectation. The hand-authored census had it right.

The tool now resolves birth_phase accessor calls **through import aliases**.
The frozen artifact caught the instrument, not only the reverse.

## Consequences

- **T4 was unrunnable.** Its expectation file disagreed with the codebase, so
  the pinned command could only ever exit 1.
- **T3's table is wrong in the same places.** Protocol §4 lists per-consumer
  outcomes for `AuditLog.record` (not a writer) and
  `_migration_null_normalize` (not a construct). §10's whole v4
  literalization of `_migration_null_normalize` describes real behaviour
  under a name that does not exist.
- The new digest is `7c42d51b92aec64934ce6b2e015767bebc81318d64ad3875222847604a353744`.

## Two entries deliberately left for the gate

Recorded in `_needs_adjudication` rather than silently resolved:

1. `private_thoughts.py::@1300/@1313/@1321` — caller sites inside that
   module's own in-module selftest block. Real `memory_phase=` passes, not
   production stamp sites. Kept, because over-inclusion is the safe
   direction for a census.
2. `core/eval/longmemeval.py::ingest_haystack` — a real writer in the
   evaluation harness, not on the reply path. Whether `core/eval` belongs in
   the S1 census roots is a scope question, not a fact question.

## The rule this establishes

The expectation is **derived and reviewed, never typed**. The guard against
that being circular is §5's two controls, and the tool is built to fail
both: a seeded writer must be named, a deleted expectation must be named.
`tests/test_s1_census.py` exercises both, plus the fixed point that the
census agrees with its own output.
