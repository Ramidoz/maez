# GitHub v1 Ingest Trigger — minimal owner-gated (turn the blueprint into a lived organ)

**Date:** 2026-06-04
**Status:** DRAFT for owner review → Codex implements / Claude reviews. Light slice (the GitHub v1 limb + taint rail already exist + are merged).
**Builds on:** GitHub v1 S2-bounded ingest (`github_v1.py` `ingest_repo_count`/`admit_repo_count_to_body`, the staging store, the connector policy — all merged but with **no live trigger**), the v0 `github_limb` device-flow session, the hardened-loopback handoff (`/internal/limb/github/session` + `scripts/github_connect.py`).

## 0. Why

The merged GitHub v1 slice is hermetically complete but has **no production button**: nothing in the live daemon calls `ingest_repo_count`/`admit_repo_count_to_body`. This slice adds the minimal **owner-gated, explicit, one-shot** trigger so the one repo-count fact can be ingested live and witnessed (staging + raw-memory taint + content-free health + legacy block gone).

## 1. Components

1. **`core/information_limb/github_limb.py` — `fetch_repo_count(session) -> int`.** The GitHub HTTP boundary stays in the limb. Reads `GET /user` with the session's `read:user` token and returns **only `public_repos`** (an int); discards login/id/everything else. Fail-closed: non-200 / missing-field → raise (`GithubAuthError` or a typed error), never a fabricated count.

2. **`core/information_limb/github_v1.py` — `run_ingest(*, limb_session, store, memory, fetch_batch_id) -> dict`.** Orchestrator: `count = github_limb.fetch_repo_count(limb_session)` → `count_field="public_repos"` → `ingest_repo_count(...)` (policy → S2 envelope → staging upsert) → **idempotency guard** (see §3) → `admit_repo_count_to_body(...)` (raw memory, `owner_account_context`, traceability) → return a **content-free** dict (`{"ok", "ingest_record_id", "fetch_batch_id", "staged", "admitted"}`). Never returns the count, login, or token.

3. **Daemon route `POST /internal/limb/github/ingest`** — mirror `/internal/limb/github/session`'s hardened loopback: reject any `Origin`; constant-time compare of a **dedicated** `MAEZ_GITHUB_INGEST_TOKEN` (header `X-Maez-Github-Ingest`); **auth-before-action** (verify the secret before doing anything). **Gated**: reject (4xx, content-free) unless `GithubMode == V1` **and** `_GITHUB_LIMB.health()["state"] == "available"` **and** `self._github_store is not None`. On success: generate a fresh `fetch_batch_id`, call `github_v1.run_ingest(limb_session=_GITHUB_LIMB session, store=self._github_store, memory=self.memory, fetch_batch_id=...)`, return the content-free result.

4. **`scripts/github_ingest.py`** — explicit owner trigger (mirror `github_connect.py`): load `MAEZ_GITHUB_INGEST_TOKEN` via `load_secrets_for_process`, POST to the loopback route, print the content-free result. **No scheduler, no proactive ingest** — owner runs it deliberately.

5. **`core/infra/secrets.py`** — add `"MAEZ_GITHUB_INGEST_TOKEN"` to `SECRET_NAMES` (it matches the `TOKEN` marker, so without allowlisting it is scrubbed/unloadable — same fix as `MAEZ_GITHUB_HANDOFF_TOKEN`).

## 2. Auth / authority boundary (the owner's call)

A **dedicated** `MAEZ_GITHUB_INGEST_TOKEN`, NOT the handoff token. Rationale: session handoff only *opens the eye* (sets the in-memory limb token); ingest *writes account-derived memory*. Different authority levels — a leaked/over-used handoff key must not silently also grant "write owner-account memory." One more secret; clean trust boundary. The ingest route never accepts a session token in its body (it acts on the daemon's existing limb session) — so there is no token-bearing envelope to protect, only the action.

## 3. Idempotency (owner-required)

- `fetch_batch_id` is generated **fresh per trigger invocation** → each owner trigger is a separate, timestamped observation (allowed; the count may be re-checked over time).
- `ingest_record_id` is deterministic from `(fetch_batch_id, count, count_field)` (existing `_ingest_record_id`). Within one run / for one `ingest_record_id`:
  - the staging write is an **upsert keyed on `ingest_record_id`** (no duplicate staging row);
  - the body admission is **guarded by the staging record's promotion state** — if `ingest_record_id` is already admitted (S2 `promotion_state` set), `run_ingest` does **not** re-admit (returns `admitted=False`/already). One `ingest_record_id` ⇒ at most one body row.
- No hidden delete/dedupe policy; repeated triggers with new `fetch_batch_id` intentionally accumulate as distinct observations (supersede-able later via the traceability `source_ref`).

**Closed residual (2026-06-04):** the narrower mid-admission crash window found during review is closed by `github-v1-ingest-idempotency-hardening`. `run_ingest` now resumes the oldest pending staged record before any fetch, admits from the staged count, and marks an already-written owner-account body row admitted via strict `source_ref` + `owner_account_context` lookup. The closure record is `docs/superpowers/parked/2026-06-04-github-v1-ingest-body-side-idempotency.md`.

## 4. Covenant rails

- Owner-gated **explicit** trigger only; no scheduler / auto / proactive ingest (Calendar's rule).
- Reads via the **scoped `read:user`** limb token, never the broad PAT.
- **One fact per trigger** (the repo count); the existing policy/minimization gates still apply.
- **Content-free** response + logs: IDs + status only — never the count value, login, token, or raw provider body.
- Fail-closed: unauthed limb / non-V1 / missing store / fetch failure → reject or raise, no partial/fabricated write.

## 5. Hermetic tests (no live HTTP, no proxy)

- `fetch_repo_count`: 200 with `public_repos=7` + secret login → returns `7`, login never surfaced; non-200 / missing field → raises.
- `run_ingest`: mocked limb session + `fetch_repo_count` → stages + admits; assert the raw-memory row has `egress_origin_class="owner_account_context"` + `source_ref` traceability + honest "public repositories" wording; result content-free (no count/login).
- **Idempotency:** two `run_ingest` calls with the **same** `fetch_batch_id` → exactly **one** body row (second returns already-admitted); two calls with **different** `fetch_batch_id` → two rows.
- Route: bad/absent `MAEZ_GITHUB_INGEST_TOKEN` → reject + action not taken (auth-before-action, mirror the handoff `body_loader.assert_not_called` shape); `Origin` header → reject; non-V1 mode / unauthed limb / no store → reject (content-free).
- Secret loadable: `MAEZ_GITHUB_INGEST_TOKEN` in `SECRET_NAMES`.

## 6. Acceptance rules

1. Dedicated `MAEZ_GITHUB_INGEST_TOKEN` (allowlisted, loadable); the handoff token is **not** accepted by the ingest route.
2. Route is loopback-only, `Origin`-rejected, constant-time secret, **auth-before-action**, gated to `V1`+available-limb+store.
3. `fetch_repo_count` returns only the integer; login/id/token never logged or returned.
4. `run_ingest` stages + admits one fact with the taint + traceability + honest wording; result + logs content-free.
5. Idempotent per `ingest_record_id` (no double body-write in a run); repeated triggers = separate observations.
6. No scheduler / proactive path; `scripts/github_ingest.py` is the only trigger.

## 7. Scope

**In:** `fetch_repo_count`, `run_ingest`, the daemon ingest route, `scripts/github_ingest.py`, the `MAEZ_GITHUB_INGEST_TOKEN` allowlist, hermetic tests.
**Out:** scheduling/auto-ingest, retry/backoff, multi-fact, the `web_interface` lazy-init debt, standing up the proxy.

## 8. The live witness this unlocks (separate, after merge + a deliberate restart)

`MAEZ_GITHUB_MODE=v1` + `MAEZ_GITHUB_INGEST_TOKEN` set → restart → owner re-auths the limb (`github_connect.py`) → owner runs `github_ingest.py` once → verify: a staging row, **one** raw-memory row wearing `owner_account_context` with the `source_ref`, content-free `github_v1` health (staged_records≥1), and the legacy `[GITHUB]` block silenced (`signal_absence`).
