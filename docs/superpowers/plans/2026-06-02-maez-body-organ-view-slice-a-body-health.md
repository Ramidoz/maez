# Maez Body / Organ View Slice A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a content-free `body` object to the local `/health` endpoint so the future organ dashboard can show Maez's real organ state without reading env vars, logs, or private artifacts in the browser.

**Architecture:** Slice A is backend-only. `EpisodeStore` gains one aggregate count helper; `MaezDaemon` gains a `_body_health(...)` projection that composes existing `/health` values, env flags, episode counts, and an observational served-model alias into a read-only organ map. `/health` includes that map additively, reusing already-computed health subdicts so tiles do not double-read sensors.

**Tech Stack:** Python 3, Flask `/health` in `daemon/maez_daemon.py`, SQLite-backed `core.memory.episodes.EpisodeStore`, `unittest` with source-level and helper-level tests.

---

## Files

- Modify: `core/memory/episodes.py`
  - Add `counts_by_status_and_source_kind()` for content-free episode totals.
- Modify: `daemon/maez_daemon.py`
  - Add `_env_flag(...)`, `_safe_episode_body_counts(...)`, and `MaezDaemon._body_health(...)`.
  - Wire `"body": self._body_health(...)` into `/health`.
- Modify: `skills/web_interface.py`
  - Strip `body` from public/debug daemon-health projections so the organ view stays local-only.
- Modify: `tests/test_lived_memory_schema.py`
  - Add one schema-store test for aggregate episode counts.
- Create: `tests/test_maez_body_organ_view.py`
  - Add helper-level and source-level tests for `/health.body`.

---

### Task 1: Episode Aggregate Counts

**Files:**
- Modify: `core/memory/episodes.py`
- Test: `tests/test_lived_memory_schema.py`

- [ ] **Step 1: Write the failing count test**

Append this test class to `tests/test_lived_memory_schema.py`:

```python
class EpisodeStoreBodyCounts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(delete=False)
        self._tmp.close()
        self.store = EpisodeStore(self._tmp.name)

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def _add(self, *, source_kind: str) -> str:
        return self.store.add(
            title=f"{source_kind} title",
            summary=f"{source_kind} summary",
            participants=["Maez"],
            source_memory_ids=[f"mem-{source_kind}"],
            source_kind=source_kind,
        )

    def test_counts_by_status_and_source_kind_are_aggregate_only(self):
        active_reflection = self._add(source_kind="reflection")
        self._add(source_kind="core_memory")
        retired = self._add(source_kind="reflection")
        self.store.supersede(retired, reason="test retirement")

        counts = self.store.counts_by_status_and_source_kind()

        self.assertEqual(counts["total"], 3)
        self.assertEqual(counts["active"], 2)
        self.assertEqual(counts["superseded"], 1)
        self.assertEqual(counts["by_status"], {"active": 2, "superseded": 1})
        self.assertEqual(counts["by_source_kind"], {"core_memory": 1, "reflection": 2})
        self.assertEqual(counts["reflection"], 2)
        self.assertNotIn(active_reflection, repr(counts))
        self.assertNotIn(retired, repr(counts))
        self.assertNotIn("reflection summary", repr(counts))
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_lived_memory_schema.EpisodeStoreBodyCounts
```

Expected: `AttributeError: 'EpisodeStore' object has no attribute 'counts_by_status_and_source_kind'`.

- [ ] **Step 3: Implement the count helper**

Add this method to `core/memory/episodes.py` after `active_count_and_newest_time()`:

```python
    def counts_by_status_and_source_kind(self) -> dict:
        """Return content-free aggregate counts for body/health surfaces."""
        with closing(self._connect()) as c:
            rows = c.execute(
                "SELECT status, source_kind, COUNT(*) AS n "
                "FROM episodes GROUP BY status, source_kind"
            ).fetchall()
        by_status: dict[str, int] = {}
        by_source_kind: dict[str, int] = {}
        total = 0
        for row in rows:
            status = str(row["status"] or "unknown")
            source_kind = str(row["source_kind"] or "unknown")
            n = int(row["n"] or 0)
            total += n
            by_status[status] = by_status.get(status, 0) + n
            by_source_kind[source_kind] = by_source_kind.get(source_kind, 0) + n
        return {
            "total": total,
            "active": by_status.get("active", 0),
            "superseded": by_status.get("superseded", 0),
            "reflection": by_source_kind.get("reflection", 0),
            "by_status": by_status,
            "by_source_kind": by_source_kind,
        }
```

- [ ] **Step 4: Run the count test and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_lived_memory_schema.EpisodeStoreBodyCounts
```

Expected: `OK`.

---

### Task 2: Content-Free Body Health Projection

**Files:**
- Modify: `daemon/maez_daemon.py`
- Modify: `skills/web_interface.py`
- Create: `tests/test_maez_body_organ_view.py`

- [ ] **Step 1: Write the failing body projection tests**

Create `tests/test_maez_body_organ_view.py`:

```python
from __future__ import annotations

import json
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _read(path: str) -> str:
    return (_REPO / path).read_text(encoding="utf-8")


def _method_body(src: str, method_name: str) -> str:
    pattern = re.compile(rf"^    def {re.escape(method_name)}\(", re.MULTILINE)
    match = pattern.search(src)
    if match is None:
        raise AssertionError(f"method not found: {method_name}")
    start = match.start()
    next_method = re.search(r"^    def \w+\(", src[start + 1 :], re.MULTILINE)
    end = start + 1 + next_method.start() if next_method else len(src)
    return src[start:end]


class _CountingEpisodes:
    def counts_by_status_and_source_kind(self):
        return {
            "total": 4,
            "active": 3,
            "superseded": 1,
            "reflection": 2,
            "by_status": {"active": 3, "superseded": 1},
            "by_source_kind": {"core_memory": 1, "reflection": 2, "followup_doc": 1},
        }


class BodyHealthProjectionTests(unittest.TestCase):
    def test_body_health_reports_organs_without_content(self):
        import daemon.maez_daemon as md

        daemon = SimpleNamespace(
            boot_time="2026-06-02T16:03:00+00:00",
            cycle_count=42,
            lived_episodes=_CountingEpisodes(),
            dream=object(),
        )
        env = {
            "MAEZ_CYCLE_DOORMAN_ENABLED": "1",
            "MAEZ_CYCLE_FOCUSED_ENABLED": "1",
            "MAEZ_REFLECTION_SYNTHESIS_ENABLED": "1",
            "MAEZ_REFLECTION_SYNTHESIS_WRITE": "1",
            "MAEZ_REFLECTION_SYNTHESIS_MAX_REFLECTIONS": "1",
            "MAEZ_RECALL_TRIAD_ENABLED": "0",
        }

        with mock.patch.dict(os.environ, env, clear=True), mock.patch(
            "daemon.maez_daemon.served_model_alias", return_value="qwen36-27b"
        ):
            body = md.MaezDaemon._body_health(
                daemon,
                camera_presence={
                    "mode": "observe",
                    "sensor_state": "available",
                    "presence_state": "present",
                    "confidence_bucket": "high",
                    "enabled_until": "2026-06-03T12:00:00-05:00",
                    "last_observed_at": "2026-06-02T16:06:00-05:00",
                },
                memory_stats={"raw": 10, "daily": 2, "core": 5, "total": 17},
                reasoning_loop={
                    "stage": "self_reflection",
                    "cycle_age_seconds": 7,
                    "stage_age_seconds": 2,
                    "cycle_stalled": False,
                },
                system={
                    "cpu_percent": 12.5,
                    "ram_percent": 44.0,
                    "gpu_percent": 30,
                    "gpu_temp_c": 55,
                },
            )

        self.assertEqual(
            set(body),
            {
                "schema_version",
                "eyes",
                "memory",
                "brain",
                "body",
                "heartbeat",
                "attention",
                "cycle_mind",
                "stomach",
                "dreaming",
                "recall",
                "covenant_perimeter",
            },
        )
        self.assertEqual(body["schema_version"], "maez_body.v0")
        self.assertEqual(body["eyes"]["presence_state"], "present")
        self.assertEqual(body["memory"]["reflection"], 2)
        self.assertEqual(body["memory"]["episodes_active"], 3)
        self.assertEqual(body["memory"]["episodes_superseded"], 1)
        self.assertEqual(body["brain"]["configured_model"], md.MODEL)
        self.assertEqual(body["brain"]["served_model_alias"], "qwen36-27b")
        self.assertTrue(body["attention"]["enabled"])
        self.assertTrue(body["cycle_mind"]["enabled"])
        self.assertEqual(body["stomach"]["max_reflections"], 1)
        self.assertFalse(body["recall"]["enabled"])
        self.assertEqual(body["recall"]["mode"], "legacy")
        self.assertFalse(body["covenant_perimeter"]["screen_vision_enabled"])
        self.assertTrue(body["covenant_perimeter"]["never_delete_memory"])
        encoded = json.dumps(body, sort_keys=True)
        self.assertNotIn("private reflection text", encoded)
        self.assertNotIn("ep-", encoded)
        self.assertNotIn("source_memory_ids", encoded)
        self.assertNotIn("summary", encoded)

    def test_body_health_fails_closed_to_unknown_counts(self):
        import daemon.maez_daemon as md

        class BrokenEpisodes:
            def counts_by_status_and_source_kind(self):
                raise RuntimeError("private db unavailable")

        daemon = SimpleNamespace(cycle_count=1, lived_episodes=BrokenEpisodes(), dream=None)

        with mock.patch.dict(os.environ, {}, clear=True), mock.patch(
            "daemon.maez_daemon.served_model_alias", return_value="llamacpp:unknown"
        ):
            body = md.MaezDaemon._body_health(
                daemon,
                camera_presence={},
                memory_stats={"raw": 0, "daily": 0, "core": 0, "total": 0},
                reasoning_loop={},
                system={},
            )

        self.assertEqual(body["memory"]["episode_counts_state"], "unknown")
        self.assertEqual(body["memory"]["episode_counts_error_class"], "RuntimeError")
        self.assertEqual(body["memory"]["episodes_active"], 0)
        self.assertEqual(body["brain"]["served_model_alias"], "llamacpp:unknown")


class BodyHealthWiringTests(unittest.TestCase):
    def test_health_route_adds_body_from_existing_subdicts(self):
        body = _method_body(_read("daemon/maez_daemon.py"), "_run_health_server")

        self.assertIn('"body": self._body_health(', body)
        self.assertIn("camera_presence=_camera_presence", body)
        self.assertIn("memory_stats=_memory_stats", body)
        self.assertIn("reasoning_loop=_reasoning_loop", body)
        self.assertIn("system=_system", body)

    def test_public_web_state_strips_body_projection(self):
        web_src = _read("skills/web_interface.py")
        route = web_src.split('@app.route("/api/maez-state")', 1)[1].split(
            "@app.route(",
            1,
        )[0]

        self.assertIn('daemon_health.pop("camera_presence", None)', route)
        self.assertIn('daemon_health.pop("body", None)', route)

    def test_debug_services_strips_body_projection(self):
        web_src = _read("skills/web_interface.py")
        route = web_src.split('@app.route("/api/debug/services")', 1)[1].split(
            "@app.route(",
            1,
        )[0]

        self.assertIn('daemon_health.pop("body", None)', route)
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_maez_body_organ_view
```

Expected: failures because `MaezDaemon._body_health` does not exist, `/health` does not wire `"body"`, and the public web projections do not strip `"body"`.

- [ ] **Step 3: Add imports and helper functions**

In `daemon/maez_daemon.py`, add this import near the existing routing imports:

```python
from core.routing.recall_stack_config import resolve_recall_stack
```

Add this import near the existing `served_model_alias` use if it is not already module-level:

```python
from core.routing.llm_client import served_model_alias
```

Add these top-level helpers after `_cycle_doorman_enabled()`:

```python
def _env_flag(name: str, *, environ: object | None = None) -> bool:
    env = os.environ if environ is None else environ
    return (env.get(name, "") or "").strip().lower() in {"1", "true", "yes", "on"}


def _safe_episode_body_counts(episode_store: object | None) -> dict[str, object]:
    if episode_store is None:
        return {
            "episode_counts_state": "unknown",
            "episode_counts_error_class": "missing_store",
            "episodes_total": 0,
            "episodes_active": 0,
            "episodes_superseded": 0,
            "reflection": 0,
        }
    try:
        counts = episode_store.counts_by_status_and_source_kind()
        return {
            "episode_counts_state": "available",
            "episodes_total": int(counts.get("total", 0) or 0),
            "episodes_active": int(counts.get("active", 0) or 0),
            "episodes_superseded": int(counts.get("superseded", 0) or 0),
            "reflection": int(counts.get("reflection", 0) or 0),
        }
    except Exception as exc:
        return {
            "episode_counts_state": "unknown",
            "episode_counts_error_class": type(exc).__name__,
            "episodes_total": 0,
            "episodes_active": 0,
            "episodes_superseded": 0,
            "reflection": 0,
        }
```

- [ ] **Step 4: Add the daemon body projection**

Add this method to `MaezDaemon` near the existing health helper methods, before `_camera_presence_health()`:

```python
    def _body_health(
        self,
        *,
        camera_presence: dict,
        memory_stats: dict,
        reasoning_loop: dict,
        system: dict,
    ) -> dict:
        """Content-free organ map for the local owner dashboard."""
        episode_counts = _safe_episode_body_counts(getattr(self, "lived_episodes", None))
        recall_config = resolve_recall_stack()
        reflection_enabled = _reflection_synthesis_enabled()
        reflection_write = _reflection_synthesis_write_enabled()
        try:
            reflection_max = _reflection_synthesis_max_reflections()
        except Exception:
            reflection_max = 3
        return {
            "schema_version": "maez_body.v0",
            "eyes": {
                "mode": camera_presence.get("mode", "unknown"),
                "sensor_state": camera_presence.get("sensor_state", "unknown"),
                "presence_state": camera_presence.get("presence_state", "unknown"),
                "confidence_bucket": camera_presence.get("confidence_bucket", "unknown"),
                "enabled_until": camera_presence.get("enabled_until"),
                "last_observed_at": camera_presence.get("last_observed_at"),
            },
            "memory": {
                "raw": int(memory_stats.get("raw", 0) or 0),
                "daily": int(memory_stats.get("daily", 0) or 0),
                "core": int(memory_stats.get("core", 0) or 0),
                "total": int(memory_stats.get("total", 0) or 0),
                **episode_counts,
            },
            "brain": {
                "configured_model": MODEL,
                "served_model_alias": served_model_alias(default=MODEL, timeout_s=0.25),
            },
            "body": {
                "cpu_percent": system.get("cpu_percent"),
                "ram_percent": system.get("ram_percent"),
                "gpu_percent": system.get("gpu_percent"),
                "gpu_temp_c": system.get("gpu_temp_c"),
            },
            "heartbeat": {
                "cycle_count": int(getattr(self, "cycle_count", 0) or 0),
                "stage": reasoning_loop.get("stage", "unknown"),
                "cycle_age_seconds": reasoning_loop.get("cycle_age_seconds"),
                "stage_age_seconds": reasoning_loop.get("stage_age_seconds"),
                "cycle_stalled": bool(reasoning_loop.get("cycle_stalled", False)),
            },
            "attention": {
                "enabled": _cycle_doorman_enabled(),
                "activity_state": "not_yet_wired",
            },
            "cycle_mind": {
                "enabled": _cycle_focused_enabled(),
                "activity_state": "not_yet_wired",
            },
            "stomach": {
                "reflection_enabled": reflection_enabled,
                "write_enabled": reflection_write,
                "max_reflections": int(reflection_max),
                "activity_state": "not_yet_wired",
            },
            "dreaming": {
                "available": getattr(self, "dream", None) is not None,
                "activity_state": "not_yet_wired",
            },
            "recall": {
                "enabled": bool(recall_config.triad_on),
                "mode": recall_config.mode.value,
                "reason": recall_config.reason,
            },
            "covenant_perimeter": {
                "never_delete_memory": True,
                "local_only": True,
                "public_exposure": False,
                "screen_vision_enabled": _env_flag("MAEZ_SCREEN_PERCEPTION"),
            },
        }
```

- [ ] **Step 5: Wire `/health.body` without double-reading sensors**

In `_run_health_server.health()`, replace the inline `return jsonify({...})` setup with named subdicts and add the body field:

```python
        @app.route("/health")
        def health():
            snap = perception_snapshot()
            gpu = snap.get("gpu") or {}
            _memory_stats = self.memory.memory_stats()
            _reasoning_loop = self._cycle_heartbeat_health()
            _camera_presence = self._camera_presence_health()
            _system = {
                "cpu_percent": snap["cpu"]["percent"],
                "ram_percent": snap["ram"]["percent"],
                "gpu_percent": gpu.get("utilization_pct"),
                "gpu_temp_c": gpu.get("temperature_c"),
            }
            return jsonify(
                {
                    "status": "alive",
                    "model": MODEL,
                    "boot_time": self.boot_time,
                    "cycle_count": self.cycle_count,
                    "last_cycle": self.last_cycle_time,
                    "reasoning_loop": _reasoning_loop,
                    "metacognitive_watchdog": self._watchdog_health(),
                    "uptime_seconds": int(
                        time.time() - datetime.fromisoformat(self.boot_time).timestamp()
                    ),
                    "memory": _memory_stats,
                    "lived_episodes": {
                        "staleness": self._m1_staleness_health(),
                        "m1": self._m1_status_health(),
                    },
                    "calendar": self._calendar_health(),
                    "camera_presence": _camera_presence,
                    "credentials": _credential_health(),
                    "temporal_spine": temporal_spine_health(),
                    "clinical_boundary": clinical_boundary_health(),
                    "voice_continuity": self._voice_continuity_health(),
                    "successor_governance": successor_governance_health(),
                    "system": _system,
                    "body": self._body_health(
                        camera_presence=_camera_presence,
                        memory_stats=_memory_stats,
                        reasoning_loop=_reasoning_loop,
                        system=_system,
                    ),
                }
            )
```

- [ ] **Step 6: Strip body from web daemon-health projections**

Add this line to `skills/web_interface.py` inside `api_maez_state()`, immediately after the existing `daemon_health.pop("camera_presence", None)`:

```python
    daemon_health.pop("body", None)
```

Add the same line to `skills/web_interface.py` inside `api_debug_services()`, immediately after `daemon_health = dict(_daemon_health())`:

```python
    daemon_health.pop("body", None)
```

- [ ] **Step 7: Run the body tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_maez_body_organ_view
```

Expected: `OK`.

---

### Task 3: Regression And Commit

**Files:**
- Verify only.

- [ ] **Step 1: Run targeted backend suites**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_maez_body_organ_view \
  tests.test_lived_memory_schema.EpisodeStoreBodyCounts \
  tests.test_camera_presence_v1_daemon_adapter \
  tests.test_reflection_dry_run_wiring.ReflectionMaxReflectionsDialTest \
  tests.test_consolidation_telemetry
```

Expected: all selected tests pass.

- [ ] **Step 2: Run the full floor and name ambient failures**

Run:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tee /tmp/maez-body-slice-a-floor.log
tail -20 /tmp/maez-body-slice-a-floor.log
```

Expected: no new body/health/episode-count failures. If the known ambient floor is still red, record the failure/error families in the handoff instead of absorbing them into this slice.

- [ ] **Step 3: Review the diff for scope**

Run:

```bash
git diff -- core/memory/episodes.py daemon/maez_daemon.py skills/web_interface.py tests/test_lived_memory_schema.py tests/test_maez_body_organ_view.py
```

Expected: only aggregate count helper, body health projection, `/health.body` wire, public/debug strip lines, and tests. No frontend changes in Slice A. No controls. No content text or episode ids in health.

- [ ] **Step 4: Commit Slice A**

Run:

```bash
git add core/memory/episodes.py daemon/maez_daemon.py skills/web_interface.py tests/test_lived_memory_schema.py tests/test_maez_body_organ_view.py
git commit -m "feat(body-ui): expose content-free organ health" -m "Add a local-only /health.body projection for the Maez Body / Organ View v0. The projection reports organ flags, live sensor state, aggregate memory counts, and observational model identity without exposing memory text, reflection text, or episode ids. Public web daemon-health projections strip the body object." -m "## Predicted effect
After the daemon is restarted, GET /health on 127.0.0.1:11435 includes a body.schema_version=maez_body.v0 object. It shows camera eyes as observe/present while the camera is live, reflection stomach as enabled/write/max=1, recall as off/legacy, and memory episode counts as aggregate numbers only. Existing /health consumers continue to work because the field is additive."
```

---

## Self-Review

- Spec coverage: Slice A implements the backend `body` object, content-free organ map, local `/health` contract, public strip guard, recall-off visibility, reflection/dream/cycle/doorman flags, and aggregate memory counts. Slice B frontend and v0.1 activity are intentionally out of scope.
- Placeholder scan: no TODO/TBD placeholders; every test and code addition is spelled out.
- Type consistency: `counts_by_status_and_source_kind()` returns the keys consumed by `_safe_episode_body_counts()`; `_body_health(...)` receives named subdicts that `_run_health_server.health()` computes once.
- Review correction: the brain tile does not trust `/health.model` alone. It reports `configured_model` plus `served_model_alias(...)` observation so stale labels do not become dashboard truth.
