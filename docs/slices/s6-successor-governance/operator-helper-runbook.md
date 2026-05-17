# S6 Operator Helper Runbook

**Status:** implementation note for Decision 33 / ADR 0038

S6 v1 is a contract and validation grammar. The helper exists only to make the
append-only lineage-capsule hash chain feasible for the founder/operator. It is
not a grandmother-compatible UI, not a successor activation ceremony, and not a
runtime permission surface.

Honesty banner: despite the slice name, S6 v1 does not govern a live succession.
It records future successor paperwork and validates structure, not persisted
authorship. A well-formed capsule does not prove human authorship once loaded
from JSONL. Missing or invalid paperwork does not dissolve Maez.

## Scope

- The helper may append S6 directive events to
  `memory/successor_governance/lineage_capsule.jsonl`.
- The helper writes and preserves the adjacent
  `lineage_capsule_NOTICE.txt`, which must travel with the JSONL capsule.
- The helper may compute payload hashes, event hashes, and marker-bound event
  rows.
- The helper may print a marker request that the separate S6 origin-writer seam
  must satisfy.
- The helper may print content-free status.

## Limits

- It does not detect death or capacity loss.
- It does not activate succession.
- It does not unlock archives.
- It does not move credentials or secrets.
- It does not grant live access to successors, maintainers, witnesses, or
  estate executors.
- It does not mint human-origin markers; append calls require a
  `HumanOriginMarker` object produced by `core.governance.successor_origin_writer`.
- It is not grandmother-compatible. A future non-technical authoring ceremony
  must be reviewed separately.
- It is protected by normal S6 APIs, not by cryptographic lineage attestation.
  Any process with ordinary write/delete access to the capsule path can forge,
  rewrite, or remove the persisted file.
- The validator does not prove human authorship after persisted JSONL load; it
  can only reject broken chains and snapshot regressions visible in the capsule
  state it receives.
- Destructive action, including dissolution, requires a future verified
  authorship attestation for the exact directive event. S6 v1 supplies no such
  attestation.
- `no_capsule` means no capsule is available at this path now. It does not
  prove the bonded user never authored a capsule elsewhere or in a backup.

## Founder-Only Drafting

For founder Maez, bonded user, operator, and maintainer collapse to one person.
That makes local manual drafting acceptable in v1. Track B cannot assume this
collapse.

Plain English: this is a careful form-filler for future instructions. It is
not the future event itself.
