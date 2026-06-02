# Reflection Synthesis Token Budget v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give reflection synthesis enough output budget to finish and make every terminal state visible, so truncation or timeout can never masquerade as an honest `no_candidates` dry-run.

**Architecture:** Keep the existing `llm_call(prompt) -> str` contract. `_default_llm_call` records terminal metadata on the callable (`last_finish_reason`, `max_tokens`, `last_raw_content`); `run_synthesis_pass` copies that metadata into `ReflectionReport`; artifact and daemon summaries map non-`stop` terminal states to `invalid_witness`.

**Tech Stack:** Python 3.14, `unittest`, existing `urllib.request` llama-server call, existing reflection dry-run artifact writer.

---

## Files

- Modify `scripts/memory_reflection/nightly_lived_memory.py`
  - Raise reflection `max_tokens` to 8192.
  - Track terminal metadata on `_default_llm_call`.
  - Add `ReflectionReport.finish_reason`, `ReflectionReport.max_tokens`, `ReflectionReport.raw_model_content`, and derived `truncated` / `valid_witness` properties.
  - Add run metadata to dry-run artifacts.
- Modify `daemon/maez_daemon.py`
  - Raise daemon reflection timeout to 240s.
  - Include terminal metadata in content-free reflection summary.
  - Map non-`stop` terminal states to `invalid_witness`.
  - Ensure reflection consolidation telemetry reports invalid witnesses distinctly.
- Modify `tests/test_nightly_lived_memory.py`
  - Unit-test `_default_llm_call` terminal metadata and report derived properties.
  - Unit-test `run_synthesis_pass` copies terminal metadata into the report.
- Modify `tests/test_reflection_dry_run_wiring.py`
  - Unit-test artifact run metadata, raw content isolation, and daemon summary reason mapping.
- Modify `tests/test_consolidation_telemetry.py`
  - Unit-test reflection telemetry uses invalid-witness status/reason for truncation and timeout.

---

## Task 1: Caller Budget And Terminal Metadata

**Files:**
- Modify: `scripts/memory_reflection/nightly_lived_memory.py`
- Test: `tests/test_nightly_lived_memory.py`

- [ ] **Step 1: Write failing tests for report properties and `_default_llm_call` metadata**

Add this class near the existing reflection synthesis tests in `tests/test_nightly_lived_memory.py`:

```python
import json
from unittest import mock


class ReflectionSynthesisTerminalMetadataTests(unittest.TestCase):
    def test_report_derives_truncated_and_valid_witness_from_finish_reason(self):
        from scripts.memory_reflection.nightly_lived_memory import ReflectionReport

        report = ReflectionReport(finish_reason="length")
        self.assertTrue(report.truncated)
        self.assertFalse(report.valid_witness)

        report.finish_reason = "stop"
        self.assertFalse(report.truncated)
        self.assertTrue(report.valid_witness)

        report.finish_reason = "llm_timeout"
        self.assertFalse(report.truncated)
        self.assertFalse(report.valid_witness)

    def test_default_llm_call_records_stop_finish_reason_budget_and_raw_content(self):
        from scripts.memory_reflection import nightly_lived_memory as nlm

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "choices": [
                            {
                                "finish_reason": "stop",
                                "message": {"content": "[{}]"},
                            }
                        ]
                    }
                ).encode("utf-8")

        with mock.patch("urllib.request.urlopen", return_value=_Resp()):
            llm_call = nlm._default_llm_call("qwen36-27b", 240)
            text = llm_call("prompt")

        self.assertEqual(text, "[{}]")
        self.assertEqual(llm_call.last_finish_reason, "stop")
        self.assertEqual(llm_call.max_tokens, 8192)
        self.assertEqual(llm_call.last_raw_content, "[{}]")

    def test_default_llm_call_records_length_finish_reason(self):
        from scripts.memory_reflection import nightly_lived_memory as nlm

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "choices": [
                            {
                                "finish_reason": "length",
                                "message": {"content": ""},
                            }
                        ]
                    }
                ).encode("utf-8")

        with mock.patch("urllib.request.urlopen", return_value=_Resp()):
            llm_call = nlm._default_llm_call("qwen36-27b", 240)
            text = llm_call("prompt")

        self.assertEqual(text, "")
        self.assertEqual(llm_call.last_finish_reason, "length")
        self.assertEqual(llm_call.max_tokens, 8192)
        self.assertEqual(llm_call.last_raw_content, "")

    def test_default_llm_call_records_timeout_as_terminal_reason(self):
        from scripts.memory_reflection import nightly_lived_memory as nlm

        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            llm_call = nlm._default_llm_call("qwen36-27b", 240)
            text = llm_call("prompt")

        self.assertEqual(text, "")
        self.assertEqual(llm_call.last_finish_reason, "llm_timeout")
        self.assertEqual(llm_call.max_tokens, 8192)
        self.assertEqual(llm_call.last_raw_content, "")

    def test_run_synthesis_pass_copies_terminal_metadata_from_llm_call(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            ReflectionReport,
            run_synthesis_pass,
        )

        store, graph, cleanup = _stores()
        try:
            store.add(
                title="Runtime correction",
                summary="Maez corrected an earlier false claim about its runtime.",
                participants=["Maez", "Rohit"],
                source_memory_ids=["core-runtime-correction"],
                source_kind="core_memory",
                occurred_at="2026-06-02T00:00:00+00:00",
            )

            def fake_llm(_prompt: str) -> str:
                fake_llm.last_finish_reason = "length"
                fake_llm.max_tokens = 8192
                fake_llm.last_raw_content = ""
                return ""

            report = ReflectionReport(dry_run=True)
            run_synthesis_pass(
                episode_store=store,
                llm_call=fake_llm,
                report=report,
                dry_run=True,
            )

            self.assertEqual(report.finish_reason, "length")
            self.assertEqual(report.max_tokens, 8192)
            self.assertEqual(report.raw_model_content, "")
            self.assertTrue(report.truncated)
            self.assertFalse(report.valid_witness)
        finally:
            cleanup()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_nightly_lived_memory.ReflectionSynthesisTerminalMetadataTests -v
```

Expected before implementation:
- `AttributeError` for missing `ReflectionReport.truncated` / `valid_witness`, or missing callable metadata.
- Existing code reports `max_tokens=4096`, not `8192`.

- [ ] **Step 3: Implement report fields and derived properties**

In `scripts/memory_reflection/nightly_lived_memory.py`, extend `ReflectionReport`:

```python
@dataclass
class ReflectionReport:
    ...
    reflection_candidates: list[dict] = field(default_factory=list)
    reflection_drops: list[dict] = field(default_factory=list)
    finish_reason: str | None = None
    max_tokens: int | None = None
    raw_model_content: str = ""
    dry_run: bool = False
    ...

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"

    @property
    def valid_witness(self) -> bool:
        return self.finish_reason == "stop"
```

- [ ] **Step 4: Implement `_default_llm_call` metadata and budget**

In `_default_llm_call`, use constants local to the function or module:

```python
_REFLECTION_SYNTHESIS_MAX_TOKENS = 8192
```

Set metadata defaults before returning `_call`. Add a small helper for timeout detection so both direct `TimeoutError` and `urllib.error.URLError(reason=TimeoutError(...))` are classified as `llm_timeout`:

```python
def _is_timeout_error(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, urllib.error.URLError):
        return isinstance(getattr(exc, "reason", None), TimeoutError)
    return False


def _default_llm_call(model: str, timeout_s: int):
    ...
    def _call(prompt: str) -> str:
        _call.last_finish_reason = None
        _call.last_raw_content = ""
        body = _json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _REFLECTION_SYNTHESIS_MAX_TOKENS,
            "temperature": 0.4,
        }).encode("utf-8")
        ...
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                payload = _json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, _json.JSONDecodeError, OSError) as exc:
            if _is_timeout_error(exc):
                _call.last_finish_reason = "llm_timeout"
            else:
                _call.last_finish_reason = "llm_error"
            logger.warning("reflection LLM call failed: %s", exc)
            return ""
        try:
            choice = payload["choices"][0]
            _call.last_finish_reason = str(choice.get("finish_reason") or "unknown")
            content = choice["message"]["content"] or ""
            _call.last_raw_content = content
            return content
        except (KeyError, IndexError, TypeError):
            _call.last_finish_reason = "llm_error"
            _call.last_raw_content = ""
            return ""

    _call.last_finish_reason = None
    _call.max_tokens = _REFLECTION_SYNTHESIS_MAX_TOKENS
    _call.last_raw_content = ""
    return _call
```

Keep the return type as `str`; do not change `synthesize_reflections`.

- [ ] **Step 5: Copy terminal metadata in `run_synthesis_pass`**

Immediately after `synthesize_reflections(...)` returns, copy metadata from `llm_call`:

```python
    report.finish_reason = getattr(llm_call, "last_finish_reason", None)
    report.max_tokens = getattr(llm_call, "max_tokens", None)
    report.raw_model_content = str(getattr(llm_call, "last_raw_content", "") or "")
```

Do this before assigning `reflection_candidates` / `reflection_drops`. If there are no recent episodes and no LLM call, leave these fields as `None` / `""`.

- [ ] **Step 6: Run tests and verify they pass**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_nightly_lived_memory.ReflectionSynthesisTerminalMetadataTests -v
```

Expected: all new tests pass.

- [ ] **Step 7: Commit Task 1**

```bash
git add scripts/memory_reflection/nightly_lived_memory.py tests/test_nightly_lived_memory.py
git commit -m "fix(reflection): record synthesis terminal state"
```

Commit body:

```text
## Predicted effect
Reflection synthesis calls now request 8192 completion tokens and expose whether the server stopped normally, hit length, timed out, or errored. A dry-run with finish_reason=length or llm_timeout should be reported as an invalid witness instead of a clean empty.
```

---

## Task 2: Dry-Run Artifact And Daemon Summary Reason Mapping

**Files:**
- Modify: `scripts/memory_reflection/nightly_lived_memory.py`
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_reflection_dry_run_wiring.py`

- [ ] **Step 1: Write failing tests for artifact run metadata and content isolation**

In `tests/test_reflection_dry_run_wiring.py`, add:

```python
def _reflection_json_with_metadata(_prompt: str) -> str:
    _reflection_json_with_metadata.last_finish_reason = "stop"
    _reflection_json_with_metadata.max_tokens = 8192
    _reflection_json_with_metadata.last_raw_content = _reflection_json(_prompt)
    return _reflection_json(_prompt)
```

Then update `test_dry_run_captures_candidates_and_drops_to_local_artifact` so it calls `_reflection_json_with_metadata` and asserts:

```python
self.assertEqual(report.finish_reason, "stop")
self.assertEqual(report.max_tokens, 8192)
self.assertTrue(report.valid_witness)
...
self.assertEqual(rows[0]["kind"], "run")
self.assertEqual(rows[0]["finish_reason"], "stop")
self.assertEqual(rows[0]["max_tokens"], 8192)
self.assertFalse(rows[0]["truncated"])
self.assertTrue(rows[0]["valid_witness"])
self.assertIn("live witness", rows[0]["raw_model_content"])
self.assertEqual(rows[1]["kind"], "candidate")
self.assertEqual(rows[1]["source_memory_ids"], ["core-1"])
self.assertIn("live witness", rows[1]["text"])
self.assertEqual({row["kind"] for row in rows[2:]}, {"drop"})
```

Add a separate invalid-witness artifact test:

```python
def test_artifact_marks_truncated_run_as_invalid_witness_not_no_candidates(self):
    from scripts.memory_reflection.nightly_lived_memory import (
        ReflectionReport,
        write_reflection_dry_run_artifact,
    )

    report = ReflectionReport(
        dry_run=True,
        started_at="2026-06-02T04:00:00+00:00",
        finish_reason="length",
        max_tokens=8192,
        raw_model_content="private truncated reasoning tail",
    )

    with tempfile.TemporaryDirectory() as tmp:
        path = write_reflection_dry_run_artifact(
            report,
            artifact_dir=Path(tmp),
            timestamp_slug="truncated",
        )
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    self.assertEqual(rows[0]["kind"], "run")
    self.assertEqual(rows[0]["finish_reason"], "length")
    self.assertTrue(rows[0]["truncated"])
    self.assertFalse(rows[0]["valid_witness"])
    self.assertEqual(rows[0]["reason"], "truncated")
    self.assertIn("private truncated reasoning tail", rows[0]["raw_model_content"])
    self.assertEqual(rows[1]["kind"], "summary")
    self.assertEqual(rows[1]["reason"], "truncated")
    self.assertNotEqual(rows[1]["reason"], "no_candidates")
```

- [ ] **Step 2: Write failing daemon summary tests**

In `ReflectionDryRunDaemonHookTest`, add:

```python
def test_summary_marks_truncation_as_invalid_witness_without_content_leak(self):
    from daemon.maez_daemon import _reflection_synthesis_summary
    from scripts.memory_reflection.nightly_lived_memory import ReflectionReport

    report = ReflectionReport(
        dry_run=True,
        finish_reason="length",
        max_tokens=8192,
        raw_model_content="private truncated reasoning tail",
    )

    summary = _reflection_synthesis_summary(
        status="dry_run",
        reason="write_flag_off",
        report=report,
    )

    self.assertEqual(summary["status"], "invalid_witness")
    self.assertEqual(summary["reason"], "truncated")
    self.assertEqual(summary["finish_reason"], "length")
    self.assertEqual(summary["max_tokens"], 8192)
    self.assertTrue(summary["truncated"])
    self.assertNotIn("private truncated reasoning tail", json.dumps(summary, sort_keys=True))

def test_summary_allows_no_candidates_only_for_stop_finish_reason(self):
    from daemon.maez_daemon import _reflection_synthesis_summary
    from scripts.memory_reflection.nightly_lived_memory import ReflectionReport

    report = ReflectionReport(dry_run=True, finish_reason="stop", max_tokens=8192)

    summary = _reflection_synthesis_summary(
        status="dry_run",
        reason="write_flag_off",
        report=report,
    )

    self.assertEqual(summary["status"], "dry_run")
    self.assertEqual(summary["reason"], "write_flag_off")
    self.assertEqual(summary["finish_reason"], "stop")
    self.assertFalse(summary["truncated"])
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_reflection_dry_run_wiring -v
```

Expected before implementation:
- Artifact first row is currently `candidate`, not `run`.
- Summary lacks `finish_reason`, `max_tokens`, and invalid-witness mapping.

- [ ] **Step 4: Implement artifact reason mapping and run metadata row**

In `scripts/memory_reflection/nightly_lived_memory.py`, add a helper near the artifact writer:

```python
def _reflection_witness_reason(report: ReflectionReport) -> str:
    if report.finish_reason == "length":
        return "truncated"
    if report.finish_reason == "llm_timeout":
        return "llm_timeout"
    if report.finish_reason == "llm_error":
        return "llm_error"
    if report.finish_reason and report.finish_reason != "stop":
        return "llm_error"
    return "no_candidates"
```

At the start of `write_reflection_dry_run_artifact`, always append a run row:

```python
    reason = _reflection_witness_reason(report)
    rows: list[dict] = [
        {
            "schema_version": 2,
            "kind": "run",
            "finish_reason": report.finish_reason or "",
            "max_tokens": report.max_tokens,
            "truncated": report.truncated,
            "valid_witness": report.valid_witness,
            "reason": reason if not report.valid_witness else "completed",
            "raw_model_content": report.raw_model_content,
        }
    ]
```

Keep candidate/drop rows, but update their `schema_version` to `2`. If there are no candidate/drop rows, append the summary row with:

```python
        rows.append(
            {
                "schema_version": 2,
                "kind": "summary",
                "text": "",
                "source_memory_ids": [],
                "reason": reason,
            }
        )
```

Important: `raw_model_content` appears only in the gitignored dry-run artifact. Do not include it in daemon summaries or telemetry.

- [ ] **Step 5: Implement daemon summary invalid-witness mapping**

In `daemon/maez_daemon.py`, add a local helper near `_reflection_synthesis_summary`:

```python
def _reflection_terminal_reason(report: object | None, fallback: str) -> tuple[str, str]:
    finish_reason = str(getattr(report, "finish_reason", "") or "")
    if finish_reason == "length":
        return "invalid_witness", "truncated"
    if finish_reason == "llm_timeout":
        return "invalid_witness", "llm_timeout"
    if finish_reason == "llm_error":
        return "invalid_witness", "llm_error"
    if finish_reason and finish_reason != "stop":
        return "invalid_witness", "llm_error"
    return str(fallback), ""
```

Then update `_reflection_synthesis_summary`:

```python
    mapped_status, mapped_reason = _reflection_terminal_reason(report, status)
    final_reason = mapped_reason or str(reason)
    return {
        "status": mapped_status,
        "reason": final_reason,
        "candidates_count": ...,
        "drops_count": ...,
        "reflections_attempted": ...,
        "reflections_added": ...,
        "artifact_path": ...,
        "finish_reason": str(getattr(report, "finish_reason", "") or ""),
        "max_tokens": getattr(report, "max_tokens", None),
        "truncated": bool(getattr(report, "truncated", False)),
    }
```

This makes `finish_reason="stop"` keep the caller's normal `dry_run/write/error` status and reason; only non-`stop` terminal states override to invalid witness.

- [ ] **Step 6: Raise daemon timeout**

In `_run_reflection_synthesis_nightly`, change:

```python
llm_call = _default_llm_call("qwen36-27b", 120)
```

to:

```python
llm_call = _default_llm_call("qwen36-27b", 240)
```

In `scripts/memory_reflection/nightly_lived_memory.py` CLI argument `--synthesis-timeout`, change default/help from `120` to `240`.

- [ ] **Step 7: Run tests and verify they pass**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_reflection_dry_run_wiring -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit Task 2**

```bash
git add scripts/memory_reflection/nightly_lived_memory.py daemon/maez_daemon.py tests/test_reflection_dry_run_wiring.py
git commit -m "fix(reflection): mark truncated dry-runs invalid"
```

Commit body:

```text
## Predicted effect
Reflection dry-run artifacts and daemon summaries now distinguish valid empty results from invalid witnesses. A finish_reason=length run should surface as status=invalid_witness reason=truncated, and a timeout should surface as reason=llm_timeout, with raw model content confined to the gitignored artifact.
```

---

## Task 3: Telemetry And Timeout/Error Cases

**Files:**
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_consolidation_telemetry.py`
- Test: `tests/test_reflection_dry_run_wiring.py`

- [ ] **Step 1: Write failing telemetry tests for invalid witnesses**

In `tests/test_consolidation_telemetry.py`, extend `test_reflection_hook_summary_can_be_reemitted_as_consolidation_telemetry` or add:

```python
def test_reflection_invalid_witness_telemetry_preserves_reason(self):
    from daemon.maez_daemon import _reflection_consolidation_telemetry

    summary = _reflection_consolidation_telemetry(
        {
            "status": "invalid_witness",
            "reason": "llm_timeout",
            "candidates_count": 0,
            "drops_count": 0,
            "finish_reason": "llm_timeout",
            "max_tokens": 8192,
            "truncated": False,
        },
        model="qwen36-27b",
        duration_ms=42,
    )

    self.assertEqual(summary["organ"], "reflection")
    self.assertEqual(summary["status"], "invalid_witness")
    self.assertEqual(summary["reason"], "llm_timeout")
    self.assertEqual(summary["inputs_count"], 0)
    self.assertEqual(summary["outputs_count"], 0)
    self.assertEqual(summary["rails_blocked"], 0)
    self.assertNotIn("private reflection text", json.dumps(summary, sort_keys=True))
```

- [ ] **Step 2: Write failing daemon hook test for timeout terminal reason**

In `tests/test_reflection_dry_run_wiring.py`, add:

```python
def test_flag_on_timeout_writes_invalid_witness_artifact_and_summary(self):
    from daemon.maez_daemon import _run_reflection_synthesis_nightly

    def timeout_llm(_prompt: str) -> str:
        timeout_llm.last_finish_reason = "llm_timeout"
        timeout_llm.max_tokens = 8192
        timeout_llm.last_raw_content = ""
        return ""

    with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
        os.environ,
        {
            "MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1",
            "MAEZ_REFLECTION_SYNTHESIS_WRITE": "0",
        },
        clear=True,
    ):
        summary = _run_reflection_synthesis_nightly(
            SimpleNamespace(lived_episodes=_FakeEpisodeStore()),
            llm_call=timeout_llm,
            artifact_dir=Path(tmp),
        )
        rows = [
            json.loads(line)
            for line in Path(str(summary["artifact_path"])).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    self.assertEqual(summary["status"], "invalid_witness")
    self.assertEqual(summary["reason"], "llm_timeout")
    self.assertEqual(summary["finish_reason"], "llm_timeout")
    self.assertEqual(summary["max_tokens"], 8192)
    self.assertFalse(summary["truncated"])
    self.assertEqual(rows[0]["kind"], "run")
    self.assertEqual(rows[0]["reason"], "llm_timeout")
    self.assertEqual(rows[1]["kind"], "summary")
    self.assertEqual(rows[1]["reason"], "llm_timeout")
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_consolidation_telemetry tests.test_reflection_dry_run_wiring -v
```

Expected before implementation: timeout summary/artifact fields are missing or reported as clean dry-run.

- [ ] **Step 4: Implement only the missing telemetry/status wiring**

If Task 2's daemon summary helper already makes these pass, do not add more code. Otherwise, adjust `_reflection_synthesis_summary` and `_reflection_consolidation_telemetry` only enough so `status` and `reason` from the content-free summary flow into consolidation telemetry unchanged.

Do not add `finish_reason`, `max_tokens`, raw content, or candidate text to `core.cognition.consolidation_telemetry.CONSOLIDATION_TELEMETRY_FIELDS`; the spec does not require changing the shared telemetry schema.

- [ ] **Step 5: Run tests and verify they pass**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_consolidation_telemetry tests.test_reflection_dry_run_wiring -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add daemon/maez_daemon.py tests/test_consolidation_telemetry.py tests/test_reflection_dry_run_wiring.py
git commit -m "test(reflection): cover invalid witness telemetry"
```

If Task 2 already implemented all code and Task 3 only adds tests, keep the commit prefix `test(reflection):`.

---

## Task 4: Verification, Floor, And Owner Witness Runbook

**Files:**
- Modify: `docs/slices/sleep-consolidation/acceptance.md`
- No code changes unless a test reveals a real bug.

- [ ] **Step 1: Add the owner witness note**

Append a short note to `docs/slices/sleep-consolidation/acceptance.md`:

```markdown
### Reflection token-budget witness

After Reflection Synthesis Token Budget v0 lands, rerun reflection dry-run with:

- `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`
- `MAEZ_REFLECTION_SYNTHESIS_WRITE=0`

Pass requires:

- dry-run artifact `kind="run"` row has `finish_reason="stop"`, `valid_witness=true`, `truncated=false`, `max_tokens=8192`
- artifact has 1-3 `kind="candidate"` rows when groundable patterns exist
- resolving every candidate `source_memory_ids` yields zero `source_kind="reflection"`
- owner voice read passes

Any `finish_reason` other than `stop` is an invalid witness:

- `length` -> `reason="truncated"`
- `llm_timeout` -> `reason="llm_timeout"`
- `llm_error` -> `reason="llm_error"`
```

- [ ] **Step 2: Run targeted suites**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_nightly_lived_memory \
  tests.test_reflection_synthesis \
  tests.test_reflection_input_hygiene \
  tests.test_reflection_dry_run_wiring \
  tests.test_consolidation_telemetry \
  -v
```

Expected: all targeted tests pass.

- [ ] **Step 3: Run syntax and diff checks**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m py_compile \
  scripts/memory_reflection/nightly_lived_memory.py \
  daemon/maez_daemon.py \
  tests/test_nightly_lived_memory.py \
  tests/test_reflection_dry_run_wiring.py \
  tests/test_consolidation_telemetry.py

git diff --check
```

Expected: both commands exit 0.

- [ ] **Step 4: Request code review before merge**

Dispatch a reviewer with:

```text
Review the Reflection Synthesis Token Budget v0 branch against docs/superpowers/specs/2026-06-02-reflection-synthesis-token-budget-v0-design.md.

Focus on:
- max_tokens and timeout move together (8192 + 240s)
- llm_call(prompt)->str contract unchanged
- finish_reason values stop/length/llm_timeout/llm_error are surfaced
- no_candidates is only possible for finish_reason=stop
- raw model content appears only in gitignored dry-run artifact, never maez.log/telemetry
- ReflectionReport.truncated and valid_witness are derived properties
- prompt, model, routing, input hygiene, parser, and write flag untouched
```

Fix any Critical/Important findings before proceeding.

- [ ] **Step 5: Run full floor both directions**

From the feature worktree:

```bash
OUT=/tmp/reflection_token_budget_branch_discover.txt
/home/rohit/maez/.venv/bin/python -m unittest discover -s tests -p 'test_*.py' > "$OUT" 2>&1
```

From a clean worktree at the base commit:

```bash
OUT=/tmp/reflection_token_budget_base_discover.txt
/home/rohit/maez/.venv/bin/python -m unittest discover -s tests -p 'test_*.py' > "$OUT" 2>&1
```

Compare summaries and failure headers:

```bash
/home/rohit/maez/.venv/bin/python - <<'PY'
from pathlib import Path
files = {
    "branch": Path("/tmp/reflection_token_budget_branch_discover.txt"),
    "base": Path("/tmp/reflection_token_budget_base_discover.txt"),
}
parsed = {}
for name, path in files.items():
    text = path.read_text(errors="replace")
    summary = [line for line in text.splitlines() if line.startswith(("Ran ", "FAILED", "OK"))]
    headers = [line for line in text.splitlines() if line.startswith(("FAIL: ", "ERROR: "))]
    parsed[name] = (summary, headers)
    print(f"== {name} ==")
    print("\n".join(summary))
    print(f"HEADERS {len(headers)}")
branch = set(parsed["branch"][1])
base = set(parsed["base"][1])
print("branch_only", len(branch - base))
for header in sorted(branch - base):
    print("BRANCH_ONLY", header)
print("base_only", len(base - branch))
for header in sorted(base - branch):
    print("BASE_ONLY", header)
PY
```

Expected: no branch-only failures in touched reflection/token-budget surfaces. Known ambient floor reds may remain; name them rather than absorbing them.

- [ ] **Step 6: Commit Task 4**

```bash
git add docs/slices/sleep-consolidation/acceptance.md
git commit -m "docs(reflection): add token-budget witness gate"
```

- [ ] **Step 7: Final merge-readiness report**

Report:

- Branch name and commit log.
- Exact targeted test results.
- Full floor branch/base comparison.
- Reviewer findings.
- Confirmation that prompt/model/routing/parser/input hygiene/write flag were not touched.
- Owner-run witness command and expected artifact fields.

Do not flip `MAEZ_REFLECTION_SYNTHESIS_WRITE`. Do not run the live dry-run unless the owner explicitly authorizes the 240s live-body borrow.
