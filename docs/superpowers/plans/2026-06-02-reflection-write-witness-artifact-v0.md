# Reflection Write-Mode Witness Artifact v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Give every persisted nightly reflection a gitignored, owner-eyes receipt (`logs/reflection_writes/`) with the exact episode id, text, citations, and provenance — best-effort, never able to disturb what was already kept.

**Architecture:** Capture the persisted episode ids on `ReflectionReport`; add a dedicated `write_reflection_write_artifact` writer (run row + `persisted_reflection` rows, no candidates/drops); call it best-effort in the hook's write branch with a truthful `artifact_path` (set only on a confirmed receipt). Pure observability — no change to reflection behavior, the dream, or the camera.

**Tech Stack:** Python, `unittest` (`.venv/bin/python -m unittest`, **NOT pytest**), `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-06-02-reflection-write-witness-artifact-v0-design.md`

**Lane:** owner picks Codex vs inline (owner leans inline). Cross-verify: ids out of `maez.log`/telemetry; receipt failure keeps `status=write`; truthful `artifact_path`.

---

## Task 1: Capture persisted episode ids on the report (TDD)

**Files:**
- Modify: `scripts/memory_reflection/nightly_lived_memory.py` (`ReflectionReport`, `run_synthesis_pass`)
- Test: `tests/test_reflection_dry_run_wiring.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_reflection_dry_run_wiring.py` (top-level, near the existing fakes):

```python
class _WritingFakeEpisodeStore(_FakeEpisodeStore):
    """Like _FakeEpisodeStore but add() PERSISTS (returns a known id) so write-mode
    paths can be exercised. The base fake's add() raises (dry-run guard)."""

    def add(self, *args, **kwargs):
        self.add_calls.append((args, kwargs))
        return f"ep-written-{len(self.add_calls)}"


class ReflectionPersistedIdsTest(unittest.TestCase):
    def test_run_synthesis_pass_captures_persisted_episode_ids(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            ReflectionReport, run_synthesis_pass,
        )
        store = _WritingFakeEpisodeStore()
        report = ReflectionReport(dry_run=False)
        run_synthesis_pass(
            episode_store=store, llm_call=_reflection_json_with_metadata,
            report=report, dry_run=False,
        )
        # One reflection cites the valid id and is persisted; ids captured in order.
        self.assertEqual(report.reflections_added, 1)
        self.assertEqual(report.persisted_episode_ids, ["ep-written-1"])

    def test_dry_run_leaves_persisted_ids_empty(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            ReflectionReport, run_synthesis_pass,
        )
        report = ReflectionReport(dry_run=True)
        run_synthesis_pass(
            episode_store=_FakeEpisodeStore(), llm_call=_reflection_json_with_metadata,
            report=report, dry_run=True,
        )
        self.assertEqual(report.persisted_episode_ids, [])
```

- [ ] **Step 2: Run to verify FAIL**

Run: `.venv/bin/python -m unittest tests.test_reflection_dry_run_wiring.ReflectionPersistedIdsTest -v`
Expected: **FAIL** — `ReflectionReport` has no `persisted_episode_ids` attribute (`AttributeError`).

- [ ] **Step 3: Add the field**

In `scripts/memory_reflection/nightly_lived_memory.py`, add to `ReflectionReport` (after `reflection_drops`):

```python
    persisted_episode_ids: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Capture ids in `run_synthesis_pass`**

In `run_synthesis_pass`, where it persists (currently `new_ids = persist_reflections(...); report.reflections_added = len(new_ids)`), add the capture:

```python
    new_ids = persist_reflections(refls, episode_store=episode_store)
    report.reflections_added = len(new_ids)
    report.persisted_episode_ids = list(new_ids)
```

(Only reached when `not dry_run` and `refls` is non-empty — so dry-run/no-input leaves it the default `[]`.)

- [ ] **Step 5: Run to verify PASS**

Run: `.venv/bin/python -m unittest tests.test_reflection_dry_run_wiring.ReflectionPersistedIdsTest -v`
Expected: **PASS**.

- [ ] **Step 6: Commit**

```bash
git add scripts/memory_reflection/nightly_lived_memory.py tests/test_reflection_dry_run_wiring.py
git commit -m "feat(reflection): capture persisted episode ids on ReflectionReport

run_synthesis_pass now records report.persisted_episode_ids = new_ids
(was discarded; only the count was kept). Internal report state for the
write receipt; NOT surfaced in the content-free maez.log summary."
```

---

## Task 2: Write receipt + hook wiring (TDD)

**Files:**
- Modify: `scripts/memory_reflection/nightly_lived_memory.py` (new `write_reflection_write_artifact`)
- Modify: `daemon/maez_daemon.py` (`_run_reflection_synthesis_nightly` write branch)
- Test: `tests/test_reflection_dry_run_wiring.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_reflection_dry_run_wiring.py`:

```python
class ReflectionWriteReceiptTest(unittest.TestCase):
    def _drive_write_hook(self, tmp, store=None):
        from daemon.maez_daemon import _run_reflection_synthesis_nightly
        with mock.patch.dict(os.environ, {
            "MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1",
            "MAEZ_REFLECTION_SYNTHESIS_WRITE": "1",
        }, clear=False):
            return _run_reflection_synthesis_nightly(
                SimpleNamespace(lived_episodes=store or _WritingFakeEpisodeStore()),
                llm_call=_reflection_json_with_metadata,
                artifact_dir=Path(tmp),
            )

    def test_write_mode_drops_persisted_reflection_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = self._drive_write_hook(tmp)
        self.assertEqual(summary["status"], "write")
        files = list(Path(tmp).glob("*.jsonl"))
        self.assertEqual(len(files), 1)
        rows = [json.loads(l) for l in files[0].read_text().splitlines() if l.strip()]
        kinds = [r["kind"] for r in rows]
        self.assertEqual(kinds[0], "run")
        self.assertEqual(rows[0]["status"], "write")
        self.assertEqual(rows[0]["reflections_added"], 1)
        persisted = [r for r in rows if r["kind"] == "persisted_reflection"]
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0]["episode_id"], "ep-written-1")
        self.assertIn("live witness", persisted[0]["text"])
        self.assertEqual(persisted[0]["source_memory_ids"], ["core-1"])
        self.assertEqual(persisted[0]["authorship"], "reflection_synthesis")
        self.assertEqual(persisted[0]["memory_voice"], "maez_self")
        self.assertNotIn("candidate", kinds)
        self.assertNotIn("drop", kinds)

    def test_episode_ids_not_in_content_free_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = self._drive_write_hook(tmp)
        blob = json.dumps(summary, sort_keys=True)
        self.assertNotIn("ep-written-1", blob)
        self.assertNotIn("live witness", blob)  # no reflection text either

    def test_receipt_failure_keeps_write_success(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "scripts.memory_reflection.nightly_lived_memory.write_reflection_write_artifact",
            side_effect=OSError("disk full"),
        ):
            summary = self._drive_write_hook(tmp)
        self.assertEqual(summary["status"], "write")  # NOT error — DB is truth
        self.assertEqual(summary.get("artifact_path", ""), "")  # truthful: no receipt

    def test_zero_persisted_writes_no_receipt_and_empty_artifact_path(self):
        class _EmptyStore(_WritingFakeEpisodeStore):
            def list_active(self):
                return []  # no input -> no reflections -> nothing persisted
        with tempfile.TemporaryDirectory() as tmp:
            summary = self._drive_write_hook(tmp, store=_EmptyStore())
        self.assertEqual(list(Path(tmp).glob("*.jsonl")), [])
        self.assertEqual(summary.get("artifact_path", ""), "")
```

- [ ] **Step 2: Run to verify FAIL**

Run: `.venv/bin/python -m unittest tests.test_reflection_dry_run_wiring.ReflectionWriteReceiptTest -v`
Expected: **FAIL** — `write_reflection_write_artifact` doesn't exist; the write branch writes no receipt and sets no `artifact_path`.

- [ ] **Step 3: Implement the receipt writer**

In `scripts/memory_reflection/nightly_lived_memory.py`, add near `write_reflection_dry_run_artifact`:

```python
def write_reflection_write_artifact(
    report: ReflectionReport,
    *,
    artifact_dir: Path | None = None,
    timestamp_slug: str | None = None,
) -> Path:
    """Receipt of what was DURABLY persisted this write pass (owner-eyes, gitignored).

    Distinct from the dry-run artifact: a run row + one persisted_reflection row per
    persisted episode id (no candidate/drop rows). Caller writes this best-effort
    AFTER persist; a failure here must never undo the durable write.
    """
    root = artifact_dir or (_REPO_ROOT / "logs" / "reflection_writes")
    root.mkdir(parents=True, exist_ok=True)
    slug = timestamp_slug or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = root / f"{slug}.jsonl"
    rows: list[dict] = [
        {
            "schema_version": 1,
            "kind": "run",
            "finish_reason": report.finish_reason or "",
            "max_tokens": report.max_tokens,
            "truncated": report.truncated,
            "valid_witness": report.valid_witness,
            "reflections_added": report.reflections_added,
            "status": "write",
        }
    ]
    ids = list(report.persisted_episode_ids or [])
    candidates = list(report.reflection_candidates or [])
    for i, episode_id in enumerate(ids):
        candidate = candidates[i] if i < len(candidates) else {}
        rows.append(
            {
                "schema_version": 1,
                "kind": "persisted_reflection",
                "episode_id": str(episode_id),
                "text": str(candidate.get("text") or ""),
                "source_memory_ids": list(candidate.get("source_memory_ids") or []),
                "authorship": "reflection_synthesis",
                "memory_voice": "maez_self",
                "status": "write",
            }
        )
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    return path
```

- [ ] **Step 4: Wire the hook's write branch**

In `daemon/maez_daemon.py` `_run_reflection_synthesis_nightly`: import the new writer alongside `write_reflection_dry_run_artifact`, and in the write branch (the `else` of `if dry_run:` — currently `status="write"`/`reason="persist_enabled"` with no receipt) add the best-effort, truthful-path receipt:

```python
    status = "write"
    reason = "persist_enabled"
    if dry_run:
        # ... existing dry-run artifact block (unchanged) ...
        status = "dry_run"
        reason = "write_flag_off"
    elif report.reflections_added >= 1:
        # Persist already happened in run_synthesis_pass. Receipt is best-effort:
        # set artifact_path ONLY on a confirmed write; a failure must not undo or
        # error-out the durable memory.
        try:
            artifact_path = write_reflection_write_artifact(report, artifact_dir=artifact_dir)
        except Exception as exc:
            logger.warning("reflection write receipt failed: %s", type(exc).__name__)
```

Ensure `write_reflection_write_artifact` is added to the function-local import from `scripts.memory_reflection.nightly_lived_memory` (next to `write_reflection_dry_run_artifact`). `artifact_path` is already initialized to `None` above the `if dry_run:` and flows into `_reflection_synthesis_summary(..., artifact_path=artifact_path)` — so it stays `None`/empty on 0-persisted or receipt failure (truthful), and the content-free summary keeps only counts + path.

- [ ] **Step 5: Run to verify PASS**

Run: `.venv/bin/python -m unittest tests.test_reflection_dry_run_wiring.ReflectionWriteReceiptTest -v`
Expected: **all PASS** — receipt written with the `persisted_reflection` row + episode id; no ids/text in the summary; receipt failure keeps `status="write"` with empty `artifact_path`; 0-persisted writes no receipt.

- [ ] **Step 6: Commit**

```bash
git add scripts/memory_reflection/nightly_lived_memory.py daemon/maez_daemon.py tests/test_reflection_dry_run_wiring.py
git commit -m "feat(reflection): write-mode witness receipt (logs/reflection_writes)

Every persisted nightly reflection now gets a gitignored owner-eyes
receipt: a run row + one persisted_reflection row per episode (id, text,
citations, provenance), no candidate/drop rows. Best-effort strictly
after persist — a receipt failure logs a content-free warning and keeps
status=write (the DB is truth). artifact_path is set only on a confirmed
receipt (empty for 0-persisted or failure). Episode ids stay out of
maez.log/telemetry. Lands on next restart; no reflection/dream/camera
behavior change."
```

---

## Task 3: Regression

- [ ] **Step 1: Reflection/daemon suites green**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_reflection_dry_run_wiring \
  tests.test_nightly_lived_memory \
  tests.test_consolidation_telemetry \
  tests.test_reflection_synthesis \
  -v
```

Expected: all PASS — the dry-run path and its artifact are unchanged; only the write branch gained a receipt.

- [ ] **Step 2: Floor both directions**

Run: `.venv/bin/python -m unittest discover -s tests 2>&1 | grep -E "^(Ran|FAILED|OK)"`
Expected: within ±2 of the `main` base (ambient families); no new deterministic reflection failure.

---

## Self-Review

- **Spec coverage:** §2a ids capture → Task 1; §2b writer (separate dir, persisted_reflection rows, no drops, >=1 only) → Task 2 Step 3 + `test_write_mode_drops_persisted_reflection_receipt` + `test_zero_persisted_writes_no_receipt`; §2c best-effort-after-persist + truthful artifact_path → Task 2 Step 4 + `test_receipt_failure_keeps_write_success`; §3 ids/text out of summary → `test_episode_ids_not_in_content_free_summary`. Non-goals (no dry-run change, no behavior change, no .gitignore edit) — respected.
- **Placeholder scan:** none — full writer, hook edit, and five tests are concrete.
- **Type consistency:** `ReflectionReport.persisted_episode_ids: list[str]`; `write_reflection_write_artifact(report, *, artifact_dir=None, timestamp_slug=None) -> Path`; `_WritingFakeEpisodeStore.add -> "ep-written-N"`; `reflection_candidates[i]` ↔ `persisted_episode_ids[i]` (aligned at persist time); `_run_reflection_synthesis_nightly(daemon, *, llm_call=, artifact_dir=)`. All match the live code read before planning.
- **One risk:** index-pairing `persisted_episode_ids[i]` ↔ `reflection_candidates[i]` assumes `persist_reflections` returns ids in candidate order with no middle skips — true in practice (every parsed reflection has valid evidence, so none is skipped; `store.add` failures are rare and best-effort). A middle skip would mis-pair text on an anomalous night; acceptable for a v0 receipt.
