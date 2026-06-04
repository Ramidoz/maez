# GitHub v1 Ingest — Idempotency Hardening (B+: resume pending before new observation)

**Date:** 2026-06-04
**Status:** DRAFT for owner review → Codex implements / Claude reviews. Small contained hardening.
**Builds on:** the merged GitHub v1 ingest trigger (`github_v1.run_ingest`, `github_store` durable `promotion_state`/`body_memory_id`, `admit_repo_count_to_body`) and its **accepted residual** (`docs/superpowers/parked/2026-06-04-github-v1-ingest-body-side-idempotency.md`).

## 0. The residual + why naive B fails

The trigger admits in order `admit_repo_count_to_body` (writes the body row) → `store.mark_admitted` (durable). A crash **between** those two leaves the body row written but `promotion_state="pending"`. On retry it double-writes.

A naive "check `source_ref` before admit" does **not** fix this, because the route mints a **fresh `fetch_batch_id` per trigger** and `ingest_record_id = _ingest_record_id(fetch_batch_id, count, count_field)` — so a normal retry computes a **new** `ingest_record_id`, checks the *new* id's `source_ref` (absent), misses the *old* pending row, and double-writes as a "new observation." The fix must anchor to the **pending staged record**, not the current trigger's id.

## 1. B+ — `run_ingest` resumes pending before creating a new observation

```
run_ingest(*, limb_session, store, memory, fetch_batch_id):
    pending = store.oldest_pending()                  # promotion_state="pending", oldest by created_at
    if pending is not None:                            # RESUME — do not fetch, do not mint a new batch
        irid = pending.ingest_record_id
        source_ref = f"github.s2:{irid}"
        existing_id = memory_owner_account_row_id(memory, source_ref)   # the body row's id, or None
        if existing_id is not None:                            # body row already written pre-crash
            store.mark_admitted(irid, body_memory_id=existing_id)
            return {ok, ingest_record_id=irid, fetch_batch_id=pending.fetch_batch_id,
                    staged=True, admitted=False, state="admitted", resumed=True}
        body_memory_id = admit_repo_count_to_body(      # admit from the STAGED count (no re-fetch)
            memory=memory, repo_count=pending.repo_count, count_field=pending.count_field,
            ingest_record_id=irid, fetch_batch_id=pending.fetch_batch_id)
        store.mark_admitted(irid, body_memory_id=body_memory_id)
        return {ok, ingest_record_id=irid, fetch_batch_id=pending.fetch_batch_id,
                staged=True, admitted=True, state="admitted", resumed=True}
    # no pending → a NEW observation (the current behavior)
    repo_count = github_limb.fetch_repo_count(limb_session)
    staged = ingest_repo_count(user_response={"public_repos": repo_count}, store=store,
                               fetch_batch_id=fetch_batch_id)   # stage FIRST → pending
    irid = staged["ingest_record_id"]
    body_memory_id = admit_repo_count_to_body(memory=memory, repo_count=repo_count,
        count_field="public_repos", ingest_record_id=irid, fetch_batch_id=fetch_batch_id)
    store.mark_admitted(irid, body_memory_id=body_memory_id)
    return {ok, ingest_record_id=irid, fetch_batch_id=fetch_batch_id,
            staged=True, admitted=True, state="admitted", resumed=False}
```

**Key invariants:**
- A trigger does **at most one** of: resume-the-oldest-pending **or** create-a-new-observation — never both. (After a crash: trigger 1 resumes the interrupted observation; trigger 2, now clean, creates a fresh one. Two deliberate pulls — honest, not hidden.)
- A resume **admits from the staged `repo_count` already in the store** — it does **not** re-fetch `/user`, and it preserves the **original `ingest_record_id`** (so `source_ref` matches the pre-crash body row if one exists).
- Staging is durable and happens **before** admission, so a crash always leaves a recoverable pending record.

## 2. Components (contained — no change to shared `MemoryManager.store`)

1. **`core/information_limb/github_store.py` — add a `created_at` column + `oldest_pending() -> PendingRecord | None`.** `updated_at` is unstable for ordering (it moves on `mark_admitted`/upsert), so add a stable **`created_at`** column to `github_provider_mirror` (migration: `created_at = updated_at` for existing rows; bump `github_store_schema_version`). `oldest_pending()` returns the oldest `promotion_state="pending"` row ordered by **`(created_at, ingest_record_id)`** (deterministic tiebreak) with its `ingest_record_id`, `fetch_batch_id`, `repo_count`, `count_field` (the staged count is already persisted). `None` if no pending.
2. **A narrow read-only MemoryManager lookup** — `MemoryManager.owner_account_row_id_by_source_ref(source_ref) -> str | None`: returns the body row's `memory_id` only if a raw row exists with **both** `source_ref == …` **and** `egress_origin_class == "owner_account_context"` (so an accidental same-`source_ref` *generic* row cannot satisfy the body-side admit check), else `None`. A metadata query on the raw collection (`where={"source_ref": …, "egress_origin_class": "owner_account_context"}`), **read-only** — it does **not** touch `store()` / the write path. (If the chroma metadata filter is awkward, a minimal lookup is acceptable — but no write-path change, and both conditions must hold.)
3. **`core/information_limb/github_v1.py` — `run_ingest`** rewritten as §1 (resume-first).

## 3. Covenant rails (unchanged + sharpened)

- Still owner-gated, explicit, one fact, content-free (the result adds only the boolean `resumed`; never count/login/token).
- A resume is **not** a new observation — it completes the interrupted one, preserving its `ingest_record_id`/timestamp lineage; no fabricated "fresh" check time.
- No hidden delete/dedupe; supersede semantics via `source_ref` unchanged.
- Blast radius stays inside `github_store` + `github_v1` + one read-only MemoryManager helper.

## 4. Acceptance / hermetic tests

1. **Crash after admit, before mark_admitted → exactly one body row.** Simulate: `mark_admitted` raises (or is skipped) after the body write; the record is left `pending`; a *second* `run_ingest` (fresh `fetch_batch_id`) **resumes**, finds the existing `source_ref` row, `mark_admitted`s, and writes **no** second body row. Assert `memory.store` call_count == 1 across both runs; result `resumed=True, admitted=False`.
2. **Crash after stage, before admit → resume admits from the staged count.** Leave a `pending` record with no body row; a second `run_ingest` resumes, calls `admit` with `pending.repo_count` (assert it does **not** call `fetch_repo_count`), `mark_admitted`s; exactly one body row, same `ingest_record_id`.
3. **No pending → new observation** (current behavior): fetches, stages, admits, `resumed=False`.
4. **`oldest_pending` ordering**: with two pending records, the older one resumes first.
5. **Content-free**: the result/logs still expose only `{ok, ingest_record_id, fetch_batch_id, staged, admitted, state, resumed}` — never count/login/token.
6. **No `MemoryManager.store` signature change** (source-contract: the write path is untouched; only a read-only lookup is added).

## 5. Scope

**In:** the `github_store` `created_at` column + `oldest_pending`, the read-only `owner_account_row_id_by_source_ref` lookup (source_ref **and** owner_account_context), `run_ingest` resume-first rewrite, the hermetic crash-window tests, the external-fetch inventory re-check if `run_ingest`/daemon lines move.
**Out:** any change to `MemoryManager.store`; deterministic-body-id/upsert (Option A); multi-fact; scheduling; the `web_interface` lazy-init debt.

## 6. Plain-English

Today a daemon crash caught mid-admission could let the *next* trigger write the same fact twice (because each trigger invents a fresh batch id). The fix: before Maez fetches anything new, it first asks "did I leave a GitHub observation half-finished?" — if so it finishes *that* one (from what it already staged, same identity), and only starts a fresh observation when nothing is pending. One fact in, even across a crash.
