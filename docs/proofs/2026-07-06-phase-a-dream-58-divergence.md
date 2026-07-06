# Phase A Diagnosis — Dream Proposal #58 Divergence

**Date:** 2026-07-06  
**Scope:** Read-only diagnosis of the live store plus a future-path code fix.
The live `memory/dream_proposals.db` row was not edited.

## Finding

Dream proposal `#58` is an append-style proposal:

```text
id=58
created_at=2026-07-05 21:09:24 local
status=applied
applied_at=2026-07-05 21:58:22 local
proposal_type=append
target_section=NULL
```

At the same time, the soul files did not move at that timestamp:

```text
config/soul.md       mtime 2026-06-29 16:20:57
config/soul.base.md  mtime 2026-06-29 16:20:20
config/soul.local.md mtime 2026-06-29 16:20:48
```

## Root Cause

`DreamState.apply_proposal()` called `ActionEngine.write_soul_note()` and then
treated any non-`None` / non-`False` return value as success.

`ActionEngine.write_soul_note()` returns an `ActionResult`. A covenant/S7 refusal
is a truthy `ActionResult(success=False, error=...)`, so the old dream path could
mark a proposal as `applied` even when the soul write was refused.

This matches the observed live divergence: the proposal row says applied, while
the soul files show no write.

## Fix Boundary

The code path now checks `result.success is False` before marking a proposal
applied. Future refused soul writes leave the proposal pending and return
`soul write rejected ...`.

The existing live `#58` row is left untouched. Correcting historical status is a
data-repair / owner-approval question, not a mechanical code cleanup.
