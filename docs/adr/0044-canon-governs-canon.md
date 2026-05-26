# 0044 — Canon Governs Canon

**Status:** Accepted
**Date:** 2026-05-26

## Context

During the 2026-05-26 memory-canon repair, a session-start snapshot claimed
four covenant memories existed, and `MEMORY.md` indexed them. The filesystem
did not contain the files. The repair was reconstruction with explicit
provenance, followed by indexing as reconstructed, not a retroactive claim that
the files had always existed.

This was the same shape already witnessed at lower layers: Slice 1's seam
refused caller-supplied meaningfulness, and Slice 2's canary discipline refused
observation that mutated substrate.

## Decision

The integrity canon applies recursively to canon management itself: evidence
first, witnessed verdict second, provenance forever.

## Consequences

- Snapshots, memories, docs, specs, and agent statements are claims until
  checked against witnesses.
- When claim and witness disagree, the witness governs.
- Repairs preserve provenance rather than smoothing over gaps.
- Memory entries for new disciplines are written only after witnessed seal, not
  merely after intended design.

If reversed, Maez's canon could become self-authorizing prose: a claim that
says it was always true because the current text says so.

## References

- Governance: Decision 39 in
  [`BETA_ARCHITECTURE_DECISIONS.md`](../governance/BETA_ARCHITECTURE_DECISIONS.md)
- Memory canon: `feedback_canon_governs_canon_witness_before_claim`
- Related: ADR 0041, ADR 0043
