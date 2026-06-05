# Parked follow-up: GitHub v1 ingest — body-side idempotency (close the mid-admission crash window)

**Date:** 2026-06-04
**Status:** CLOSED 2026-06-04 — fixed by branch `github-v1-ingest-idempotency-hardening`, merged locally at `32fb5d0`. The accepted residual is no longer open.
**Severity:** very low (sub-second window, manual one-shot, supersede-able duplicate, no leak/corruption).

## Original residual

`github_v1.run_ingest` admits the fact in this order: `admit_repo_count_to_body(...)` (writes the body row via `MemoryManager.store`, returns a new `memory_id`) → `store.mark_admitted(ingest_record_id, body_memory_id)` (durable). The durable `promotion_state` guard covers a crash **after staging, before admission** (retry finishes — the case the owner named). It does **not** cover a crash **mid-admission**: after `memory.store` returns but before `mark_admitted` persists, the body row exists with `promotion_state` still `pending`, so a retry re-admits → a **second** body row (a duplicate "N repos" observation).

## Closure

The hardening changes `run_ingest` to resume `store.oldest_pending()` before any GitHub fetch or fresh batch admission. On resume, Maez either:
- finds the already-written owner-account body row by strict `source_ref` + `egress_origin_class="owner_account_context"` lookup and only marks the staged record admitted; or
- admits from the already-staged count, preserving the original `ingest_record_id` and `fetch_batch_id`, with no `/user` re-fetch.

The lookup fails closed: if raw memory cannot answer whether the body row exists, the ingest raises and the staged record remains pending for a clean retry. `MemoryManager.store` was not changed.

Witnesses:
- crash after stage → retry resumes from staged count, no re-fetch, one body write;
- crash after body write before `mark_admitted` → retry marks the existing body id admitted, no second body write;
- `created_at` migration sets existing rows to `updated_at` and `oldest_pending()` orders by `(created_at, ingest_record_id)`;
- content-free result includes only the new `resumed` boolean, never count/login/token.

## Why it was parked, not blocking

- The window is sub-second on a deliberate one-shot owner trigger; the outcome is a duplicate *observation*, supersede-able via the traceability `source_ref` — not corruption, not a leak, not a covenant violation.
- The owner's explicit "no double-write" bar (crash *after staging, before admission*) **is** met; this is a narrower sub-case.

## The fix that landed

Body admission is now **idempotent keyed on `ingest_record_id`/`source_ref`**
without changing `MemoryManager.store`: `run_ingest` checks for an existing
owner-account row by `github.s2:<ingest_record_id>` before re-admitting a
pending record. If it exists, the staging row is marked admitted with that
existing body id. If it does not exist, the pending row is admitted from the
staged count. The acceptance test simulates a crash *between* `memory.store`
and `mark_admitted`, then retries, and proves exactly one body row.

## Provenance

GitHub v1 ingest-trigger review (2026-06-04). Codex implemented durable `promotion_state` idempotency; Claude review found the mid-admission sub-window; owner accepted the residual and parked the hardening rather than hold the merge or over-engineer for a near-impossible scenario.
