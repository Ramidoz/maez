# S6 Operator Helper Runbook

**Status:** implementation note for Decision 33 / ADR 0038

S6 v1 is a contract and validation grammar. The helper exists only to make the
append-only lineage-capsule hash chain feasible for the founder/operator. It is
not a grandmother-compatible UI, not a successor activation ceremony, and not a
runtime permission surface.

## Scope

- The helper may append S6 directive events to
  `memory/successor_governance/lineage_capsule.jsonl`.
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

## Founder-Only Drafting

For founder Maez, bonded user, operator, and maintainer collapse to one person.
That makes local manual drafting acceptable in v1. Track B cannot assume this
collapse.

Plain English: this is a careful form-filler for future instructions. It is
not the future event itself.
