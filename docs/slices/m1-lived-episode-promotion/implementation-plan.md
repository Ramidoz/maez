# M1 Lived-Episode Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** Build the default-disabled M1 organ that promotes eligible audited
bonded Telegram exchanges into `lived_episodes.db` without widening TRF.

**Architecture:** Add a small pure module under `core/memory/` that owns marker
detection, pending-window state, idempotency, structural summary construction,
promotion, and staleness health. Wire the daemon only at two seams: after
`store_telegram(...)` returns a raw source ID, and during daemon-cycle flush.
Expose staleness health through `/health`.

**Tech Stack:** Python stdlib, SQLite, existing `EpisodeStore`, daemon Flask
health endpoint, `unittest`.

---

### Task 1: Pure M1 Promotion Module

**Files:**
- Create: `core/memory/m1_lived_episode_promotion.py`
- Test: `tests/test_m1_lived_episode_promotion.py`

- [x] **Step 1: Write failing unit tests**

Cover owner-authored marker promotion, marker negatives, structural-only
summary, no raw transcript text, pending-window persistence, idempotency
exact/subset/partial-overlap behavior, staleness ok/warn/alarm/empty/
unavailable, and default-disabled config.

- [x] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_m1_lived_episode_promotion
```

Expected: import failure for `core.memory.m1_lived_episode_promotion`.

- [x] **Step 3: Implement module**

Provide:

- `M1Config`
- `M1PromotionStore`
- `M1LivedEpisodePromoter`
- `build_structural_summary(...)`
- `biography_staleness_health(...)`

The module stores source IDs/timestamps only in sidecar state. It writes
episodes through `EpisodeStore.add(...)` with `source_kind="telegram_exchange"`,
`authorship="bonded_dialogue"`, and `memory_voice="mixed_owner_maez"`.

- [x] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_m1_lived_episode_promotion
```

Expected: all tests pass.

### Task 2: Daemon Wiring

**Files:**
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_m1_daemon_wiring.py`

- [x] **Step 1: Write failing source-wiring tests**

Pin:

- daemon initializes an M1 promoter;
- `handle_message()` captures `store_telegram(...)` return value;
- M1 promotion call occurs after audit and after `store_telegram(...)`;
- daemon-cycle flush calls M1 without owner activity;
- `/health` includes lived-episode staleness fields;
- M1 wiring is default-disabled.

- [x] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_m1_daemon_wiring
```

Expected: source-wiring assertions fail because no M1 seam exists yet.

- [x] **Step 3: Wire daemon**

Initialize `self.m1_promoter`, call `consider_audited_exchange(...)` after
`store_telegram(...)`, call daemon-cycle flush near cycle start, and merge
`staleness_health()` into `/health`. All M1 calls are best-effort and
fail-neutral.

- [x] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_m1_daemon_wiring tests.test_m1_lived_episode_promotion
```

Expected: all tests pass.

### Task 3: Regression Guard Set

**Files:**
- Modify: `tests/test_temporal_recall_fragment_guard.py` if needed
- Modify: `tests/test_nightly_lived_memory.py` if needed

- [x] **Step 1: Add or extend tests**

Pin no TRF widening, no reflection synthesis over `telegram_exchange`, no
private-thought reads, and no generic title surfaced mechanically.

- [x] **Step 2: Verify focused suite**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_m1_lived_episode_promotion \
  tests.test_m1_daemon_wiring \
  tests.test_temporal_recall_fragment_guard \
  tests.test_nightly_lived_memory \
  tests.test_memory_integrity_invariant
```

Expected: all tests pass.

### Task 4: Verification And Commit

- [x] **Step 1: Run doc/code verification**

```bash
git diff --check
grep -nE 'ghp_|github_pat_|PAT|token' .git/config || true
```

- [ ] **Step 2: Commit behavior-changing implementation**

Commit message must include a `## Predicted effect` section and the explicit
operator waiver for same-session implementation after Decision 25 / ADR 0030.
