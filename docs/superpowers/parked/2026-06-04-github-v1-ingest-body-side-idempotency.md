# Parked follow-up: GitHub v1 ingest — body-side idempotency (close the mid-admission crash window)

**Date:** 2026-06-04
**Status:** PARKED hardening follow-up — non-blocking. Owner-accepted the residual at GitHub v1 ingest-trigger review; merge proceeded.
**Severity:** very low (sub-second window, manual one-shot, supersede-able duplicate, no leak/corruption).

## The residual

`github_v1.run_ingest` admits the fact in this order: `admit_repo_count_to_body(...)` (writes the body row via `MemoryManager.store`, returns a new `memory_id`) → `store.mark_admitted(ingest_record_id, body_memory_id)` (durable). The durable `promotion_state` guard covers a crash **after staging, before admission** (retry finishes — the case the owner named). It does **not** cover a crash **mid-admission**: after `memory.store` returns but before `mark_admitted` persists, the body row exists with `promotion_state` still `pending`, so a retry re-admits → a **second** body row (a duplicate "N repos" observation).

## Why it's parked, not blocking

- The window is sub-second on a deliberate one-shot owner trigger; the outcome is a duplicate *observation*, supersede-able via the traceability `source_ref` — not corruption, not a leak, not a covenant violation.
- The owner's explicit "no double-write" bar (crash *after staging, before admission*) **is** met; this is a narrower sub-case.

## The fix (when done deliberately)

Make the body admission **idempotent keyed on `ingest_record_id`/`source_ref`**, so a re-admit is a no-op:
- **Option A — deterministic body id:** `MemoryManager.store` accepts an explicit id (e.g. `id=f"github.s2.body:{ingest_record_id}"`) and upserts by it, so re-admitting writes the same row. Requires a small `store` signature/upsert change.
- **Option B — check-before-admit:** a `MemoryManager` "exists by `source_ref`" lookup (or an index on the metadata `source_ref`); `run_ingest` skips the body write if a row for `github.s2:<ingest_record_id>` already exists.
- Acceptance: a test that simulates a crash *between* `memory.store` and `mark_admitted` (e.g., raise after the body write, then retry) produces **exactly one** body row.

## Provenance

GitHub v1 ingest-trigger review (2026-06-04). Codex implemented durable `promotion_state` idempotency; Claude review found the mid-admission sub-window; owner accepted the residual and parked the hardening rather than hold the merge or over-engineer for a near-impossible scenario.
