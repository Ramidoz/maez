# Reflection Write-Mode Witness Artifact v0 — Design

**Date:** 2026-06-02
**Status:** Draft under review (owner review pending before plan/Codex)
**Scope (narrow, owner-set):** *Give every persisted nightly reflection a reviewable receipt.* In write mode the reflection hook persists episodes + emits content-free telemetry but writes **no contentful record** of what it kept. This adds a gitignored, owner-eyes receipt. Pure observability — no change to reflection behavior, the dream, or the camera.

---

## 1. The gap

In `_run_reflection_synthesis_nightly`, `write_reflection_dry_run_artifact` is called **only** inside `if dry_run:` (daemon:1786). So in write mode the night persists reflections to `lived_episodes.db` and logs content-free telemetry — but there's no reviewable record of *what* was kept except querying the store. And `run_synthesis_pass` discards the persisted episode ids (`new_ids = persist_reflections(...); report.reflections_added = len(new_ids)` — keeps the count, drops the ids).

---

## 2. The change (three pieces, observability only)

**(a) Capture the persisted episode ids.** Add `ReflectionReport.persisted_episode_ids: list[str]` (default empty). In `run_synthesis_pass`, set `report.persisted_episode_ids = list(new_ids)` after `persist_reflections`. This is **internal report state only** — it is NOT added to the content-free `maez.log` summary (episode ids are direct handles into Maez's memory; they belong in the owner-eyes receipt, not the public log).

**(b) A dedicated write receipt — different room, different name.** New `write_reflection_write_artifact(report, *, artifact_dir=None) -> Path` writing to **`logs/reflection_writes/<ts>.jsonl`** (separate from `reflection_dry_runs/`; gitignored by the existing `logs/*` rule). Rows:
- One `kind="run"` row: `finish_reason`, `max_tokens`, `truncated`, `valid_witness`, `reflections_added`, `status="write"` (run metadata; no reflection text, no `raw_model_content`).
- One `kind="persisted_reflection"` row **per kept reflection**: `episode_id` (from `persisted_episode_ids[i]`), `text`, `source_memory_ids`, `authorship="reflection_synthesis"`, `memory_voice="maez_self"`, `status="write"`. (Candidate[i] ↔ `persisted_episode_ids[i]` align in order.)
- **No `candidate` rows, no `drop` rows.** Dry-run artifacts *preview* candidates and record drops; the write receipt is *what was durably kept*. Different rooms. (A separate write-mode generation audit including drops can come later if wanted — not v0.)
- Written **only when `reflections_added >= 1`** — a receipt is for what was actually kept; an empty night is already recorded by content-free telemetry, so no empty receipt file.

**(c) Best-effort, strictly after persist (load-bearing).** The persist already happened inside `run_synthesis_pass` before the hook reaches the write branch. The hook then calls `write_reflection_write_artifact` best-effort: on any exception, log a **content-free** warning (`"reflection write receipt failed: <ExcType>"`) and **keep `status="write"` success**. Unlike the dry-run path (a failed artifact returns an error summary because nothing was kept), in write mode the reflection is already in Maez's selfhood — a jammed receipt printer must never undo or error-out what was durably kept. The DB is truth; the receipt is its receipt.

---

## 3. Two channels, unchanged

- **Contentful receipt** → gitignored `logs/reflection_writes/*.jsonl` (owner-eyes-only; reflection text + episode ids + citations + provenance).
- **Content-free** → `maez.log` summary keeps `reflections_added`/counts + the receipt **path**; it does **not** gain episode ids or reflection text.
- The dry-run path (`logs/reflection_dry_runs/`, candidates + drops) is **untouched**.

---

## 4. Tests

In `tests/test_reflection_dry_run_wiring.py` (the daemon-hook home):
- **Write mode writes a receipt:** drive `_run_reflection_synthesis_nightly` with write enabled + a fake `llm_call` returning a grounded reflection + a `_FakeEpisodeStore` that returns a known `add()` id; assert a `logs/reflection_writes/` file is created (temp `artifact_dir`), with a `kind="run"` row (`status="write"`) and a `kind="persisted_reflection"` row carrying the `episode_id`, `text`, `source_memory_ids`, and provenance. No `candidate`/`drop` rows.
- **Episode ids stay out of the content-free summary:** assert the daemon summary / `consolidation_telemetry` dict contains **no** episode id and **no** reflection text (extend the existing channel-wall assertion).
- **Receipt failure preserves write success:** patch `write_reflection_write_artifact` to raise; assert the hook still returns `status="write"` (not `error`), the warning is content-free, and durable persistence is unaffected.
- **0-persisted writes no receipt:** write mode with a fake returning `[]` → no `reflection_writes/` file.
- **`run_synthesis_pass` captures ids:** `report.persisted_episode_ids == new_ids` after a write pass; empty on dry-run/no-input.

---

## 5. Unchanged / non-goals

- **No reflection behavior change** — same prompt, grounding rail, dial, persist logic; the dream and camera are untouched. Pure receipt.
- **No drops in the receipt v0** (a generation audit is a separate later thing).
- **No episode ids or reflection text in `maez.log`/telemetry.**
- **No change to the dry-run artifact** or its dir.
- **Lands on next restart** — tonight's first ~3 AM write is reviewed via the store as already planned; every night after has a receipt.
- NOT a new `.gitignore` entry (`logs/*` already covers `logs/reflection_writes/`).
