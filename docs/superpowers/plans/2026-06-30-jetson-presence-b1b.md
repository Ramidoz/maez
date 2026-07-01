# Jetson Presence B1b Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add owner-gated enrollment and bounded live recognition on the Jetson so the edge producer can send honest `present` / `absent` / `unknown` `jetson_presence.v0` labels through the existing Slice-A doorway, without adding any downstream Maez behavior.

**Architecture:** B1b adds three pure-ish edge modules (`decision.py`, `enrollment.py`, `recognition.py`) and extends `run.py` with an explicit bounded `--recognize` path. The host doorway, contract, store, and receipts are unchanged. The owner profile is a Jetson-local restricted plaintext JSON file; frames/crops remain RAM-only; non-owner candidates are discarded before decision inputs.

**Tech Stack:** Python 3.10 on Jetson, host tests via `/home/rohit/maez/.venv/bin/python -B -m unittest`, lazy OpenCV/TensorRT imports, existing `b1a` detector/embedder/matcher, existing `emitter.post_label`, existing `jetson_presence.v0` host contract.

**Spec:** `docs/superpowers/specs/2026-06-30-jetson-presence-b1b-design.md` (`0fd246f`).

---

## File Structure

Create:

| Path | Responsibility |
| --- | --- |
| `devices/jetson_presence/jetson_presence/decision.py` | Pure label decision: thresholds, reliable-window allowlist, confidence buckets, occupancy non-leak. No I/O. |
| `devices/jetson_presence/jetson_presence/enrollment.py` | Owner-gated profile ceremony helpers: calibration, profile JSON load/save, interactive CLI. The only code allowed to write the biometric profile. |
| `devices/jetson_presence/jetson_presence/recognition.py` | Frame-to-owner-evidence summarizer. Uses detector/embedder injected or lazily built; discards non-owner candidates before decision. No network, no disk writes. |
| `tests/test_jetson_b1b_decision.py` | Pure decision-rule tests, including occupancy non-leak at label layer. |
| `tests/test_jetson_b1b_enrollment.py` | Calibration/profile/interactive gate tests. |
| `tests/test_jetson_b1b_recognition.py` | Owner-evidence aggregation tests, including non-owner mismatch discarded. |
| `tests/test_jetson_b1b_run.py` | `run --recognize` integration tests with injected fakes. |
| `tests/test_jetson_b1b_structural_guards.py` | AST no-emitter-import guard, profile-write-shape guard, dynamic no-write recognition witness, and planted-probe guard tests. |

Modify:

| Path | Change |
| --- | --- |
| `devices/jetson_presence/jetson_presence/config.py` | Add profile/model/window config fields with env overrides. |
| `devices/jetson_presence/jetson_presence/run.py` | Add `--recognize` bounded path; default B0 path unchanged. |
| `devices/jetson_presence/.gitignore` | Add owner profile runtime artifact names if the default profile path can appear under the deploy dir. |

Do **not** modify host intake, daemon heartbeat, prompts, cockpit, or any Maez felt-behavior consumer.

## Constants Locked By This Plan

These constants go in `decision.py` or `enrollment.py` and are asserted by tests:

```python
MIN_USABLE_OWNER_EMBEDDINGS = 10
TARGET_OWNER_EMBEDDINGS = 24
MAX_OWNER_INTRA_P95 = 0.55
PRESENT_MARGIN = 0.05
PRESENT_THRESHOLD_CAP = 0.62
AMBIGUITY_MARGIN = 0.10
AMBIGUOUS_THRESHOLD_CAP = 0.72

RECOGNITION_WINDOW_FRAMES = 8
MIN_RELIABLE_FRAMES = 6
MIN_WINDOW_DURATION_SECONDS = 0.50
RECOGNITION_FRAME_INTERVAL_SECONDS = 0.10

DEFAULT_PROFILE_PATH = "~/.local/state/maez-jetson/owner_profile.json"
PROFILE_SCHEMA_VERSION = "jetson_owner_profile.v0"
DISTANCE_AGGREGATION = "min_to_any_ref"
```

`sys.stdin.isatty()` plus confirmation phrase is an accident guard, not an agent-proof security boundary. The real gate is physical owner presence in front of the camera plus the covenant that agents do not run enrollment.

---

## Task 1: `decision.py` — Pure Decision Rule

**Files:**
- Create: `devices/jetson_presence/jetson_presence/decision.py`
- Create: `tests/test_jetson_b1b_decision.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jetson_b1b_decision.py
import dataclasses
import unittest

import tests._jetson_edge_path  # noqa: F401
from jetson_presence import decision


class DecisionRuleTests(unittest.TestCase):
    def _thresholds(self):
        return decision.Thresholds(
            owner_intra_p95=0.35,
            present_threshold=0.40,
            ambiguous_threshold=0.50,
        )

    def _window(self, **overrides):
        data = {
            "camera_open": True,
            "frame_health": "good",
            "exposure_blur": "good",
            "model_loaded": True,
            "enrollment_available": True,
            "reliable_frames": 8,
            "window_duration_s": 0.8,
        }
        data.update(overrides)
        return decision.WindowSignals(**data)

    def test_window_input_table_is_closed(self):
        fields = set(decision.WindowSignals.__dataclass_fields__)
        self.assertEqual(
            fields,
            {
                "camera_open",
                "frame_health",
                "exposure_blur",
                "model_loaded",
                "enrollment_available",
                "reliable_frames",
                "window_duration_s",
            },
        )

    def test_strong_owner_match_is_present(self):
        label = decision.decide_label(
            ts="T",
            window=self._window(),
            evidence=decision.OwnerEvidence(best_distance=0.31),
            thresholds=self._thresholds(),
        )
        self.assertEqual((label["sensor_state"], label["owner_present"]), ("available", "present"))
        self.assertIn(label["confidence"], {"medium", "high"})

    def test_ambiguous_owner_evidence_is_unknown_low(self):
        label = decision.decide_label(
            ts="T",
            window=self._window(),
            evidence=decision.OwnerEvidence(best_distance=0.45),
            thresholds=self._thresholds(),
        )
        self.assertEqual((label["sensor_state"], label["owner_present"], label["confidence"]), ("available", "unknown", "low"))

    def test_reliable_window_without_owner_evidence_is_absent(self):
        label = decision.decide_label(
            ts="T",
            window=self._window(),
            evidence=decision.OwnerEvidence(),
            thresholds=self._thresholds(),
        )
        self.assertEqual((label["sensor_state"], label["owner_present"]), ("available", "absent"))
        self.assertIn(label["confidence"], {"medium", "high"})

    def test_empty_and_non_owner_populated_window_inputs_are_byte_identical(self):
        empty = self._window()
        non_owner_populated = self._window()
        self.assertEqual(dataclasses.asdict(empty), dataclasses.asdict(non_owner_populated))

    def test_empty_and_discarded_non_owner_windows_are_byte_identical(self):
        empty = decision.decide_label(
            ts="T",
            window=self._window(),
            evidence=decision.OwnerEvidence(),
            thresholds=self._thresholds(),
        )
        discarded_non_owner = decision.decide_label(
            ts="T",
            window=self._window(),
            evidence=decision.OwnerEvidence(),
            thresholds=self._thresholds(),
        )
        self.assertEqual(empty, discarded_non_owner)

    def test_unknown_confidence_is_fixed_low_for_degraded_states(self):
        cases = [
            self._window(camera_open=False),
            self._window(model_loaded=False),
            self._window(enrollment_available=False),
            self._window(frame_health="bad"),
            self._window(exposure_blur="bad"),
            self._window(reliable_frames=3),
        ]
        for window in cases:
            with self.subTest(window=window):
                label = decision.decide_label(
                    ts="T",
                    window=window,
                    evidence=decision.OwnerEvidence(),
                    thresholds=self._thresholds(),
                )
                self.assertEqual(label["owner_present"], "unknown")
                self.assertEqual(label["confidence"], "low")

    def test_conflict_is_unknown(self):
        label = decision.decide_label(
            ts="T",
            window=self._window(),
            evidence=decision.OwnerEvidence(best_distance=0.31, conflict=True),
            thresholds=self._thresholds(),
        )
        self.assertEqual((label["owner_present"], label["confidence"]), ("unknown", "low"))

    def test_label_has_exact_contract_keys_and_no_raw_distance(self):
        label = decision.decide_label(
            ts="T",
            window=self._window(),
            evidence=decision.OwnerEvidence(best_distance=0.31),
            thresholds=self._thresholds(),
        )
        self.assertEqual(set(label), {"owner_present", "confidence", "sensor_state", "ts", "schema_version"})
        self.assertNotIn("distance", label)
        self.assertNotIn("candidate_count", label)

    def test_constants_are_locked(self):
        self.assertEqual(decision.RECOGNITION_WINDOW_FRAMES, 8)
        self.assertEqual(decision.MIN_RELIABLE_FRAMES, 6)
        self.assertEqual(decision.MIN_WINDOW_DURATION_SECONDS, 0.50)
        self.assertEqual(decision.RECOGNITION_FRAME_INTERVAL_SECONDS, 0.10)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1b_decision -v
```

Expected: FAIL with `ImportError` or missing `jetson_presence.decision`.

- [ ] **Step 3: Implement minimal decision module**

```python
# devices/jetson_presence/jetson_presence/decision.py
"""B1b pure owner-presence decision logic.

No I/O. No frames, crops, embeddings, candidates, or non-owner signals cross this
module boundary. Non-owner candidates must be discarded by recognition before a
WindowSignals + OwnerEvidence pair is constructed.
"""
from __future__ import annotations

from dataclasses import dataclass

from jetson_presence.labels import SCHEMA_VERSION

RECOGNITION_WINDOW_FRAMES = 8
MIN_RELIABLE_FRAMES = 6
MIN_WINDOW_DURATION_SECONDS = 0.50
RECOGNITION_FRAME_INTERVAL_SECONDS = 0.10

GOOD = "good"


@dataclass(frozen=True)
class Thresholds:
    owner_intra_p95: float
    present_threshold: float
    ambiguous_threshold: float


@dataclass(frozen=True)
class WindowSignals:
    camera_open: bool
    frame_health: str
    exposure_blur: str
    model_loaded: bool
    enrollment_available: bool
    reliable_frames: int
    window_duration_s: float


@dataclass(frozen=True)
class OwnerEvidence:
    # Aggregated owner-like evidence for the current reliable window.
    # Empty/non-owner-only windows leave best_distance unset.
    best_distance: float | None = None
    # True only when a single frame saw more than one strong owner-like face.
    conflict: bool = False


def unknown_label(sensor_state: str, ts: str) -> dict:
    return _label(owner_present="unknown", confidence="low", sensor_state=sensor_state, ts=ts)


def decide_label(*, ts: str, window: WindowSignals, evidence: OwnerEvidence, thresholds: Thresholds) -> dict:
    if not window.camera_open:
        return unknown_label("unavailable", ts)
    if not window.enrollment_available:
        return unknown_label("unenrolled", ts)
    if not window.model_loaded:
        return unknown_label("error", ts)
    if window.frame_health != GOOD or window.exposure_blur != GOOD:
        return unknown_label("available", ts)

    if evidence.conflict:
        return unknown_label("available", ts)
    if evidence.best_distance is not None:
        distance = evidence.best_distance
        if distance <= thresholds.present_threshold:
            return _label(
                owner_present="present",
                confidence=_present_confidence(distance, window=window, thresholds=thresholds),
                sensor_state="available",
                ts=ts,
            )
        if distance <= thresholds.ambiguous_threshold:
            return unknown_label("available", ts)
    if _reliable_window(window):
        return _label(owner_present="absent", confidence=_absent_confidence(window), sensor_state="available", ts=ts)
    return unknown_label("available", ts)


def _reliable_window(window: WindowSignals) -> bool:
    return (
        window.reliable_frames >= MIN_RELIABLE_FRAMES
        and window.window_duration_s >= MIN_WINDOW_DURATION_SECONDS
        and window.frame_health == GOOD
        and window.exposure_blur == GOOD
        and window.model_loaded
        and window.enrollment_available
        and window.camera_open
    )


def _present_confidence(distance: float, *, window: WindowSignals, thresholds: Thresholds) -> str:
    margin = thresholds.present_threshold - distance
    if margin >= 0.10 and window.reliable_frames >= RECOGNITION_WINDOW_FRAMES:
        return "high"
    if margin >= 0.03 and window.reliable_frames >= MIN_RELIABLE_FRAMES:
        return "medium"
    return "low"


def _absent_confidence(window: WindowSignals) -> str:
    if window.reliable_frames >= RECOGNITION_WINDOW_FRAMES and window.window_duration_s >= 0.75:
        return "high"
    if _reliable_window(window):
        return "medium"
    return "low"


def _label(*, owner_present: str, confidence: str, sensor_state: str, ts: str) -> dict:
    return {
        "owner_present": owner_present,
        "confidence": confidence,
        "sensor_state": sensor_state,
        "ts": ts,
        "schema_version": SCHEMA_VERSION,
    }
```

- [ ] **Step 4: Run test to verify GREEN**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1b_decision -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/jetson_presence/decision.py tests/test_jetson_b1b_decision.py
git commit -m "feat(jetson-b1b): pure owner-presence decision rule"
```

---

## Task 2: `enrollment.py` — Calibration + Profile JSON

**Files:**
- Create: `devices/jetson_presence/jetson_presence/enrollment.py`
- Create: `tests/test_jetson_b1b_enrollment.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jetson_b1b_enrollment.py
import json
import os
import stat
import tempfile
import unittest
from unittest import mock

import numpy as np

import tests._jetson_edge_path  # noqa: F401
from jetson_presence import enrollment


def _unit(angle: float):
    return np.asarray([np.cos(angle), np.sin(angle)], dtype=np.float32)


class EnrollmentCalibrationTests(unittest.TestCase):
    def test_distance_aggregation_is_min_to_any_ref(self):
        refs = [_unit(0.0), _unit(0.5), _unit(1.0)]
        candidate = _unit(0.48)
        d = enrollment.min_distance_to_references(candidate, refs)
        self.assertLess(d, enrollment.cosine_distance(candidate, refs[0]))
        self.assertAlmostEqual(d, enrollment.cosine_distance(candidate, refs[1]), places=6)

    def test_calibration_uses_leave_one_out_min_to_any_ref(self):
        refs = [_unit(i * 0.01) for i in range(enrollment.MIN_USABLE_OWNER_EMBEDDINGS)]
        profile = enrollment.build_profile(refs, created_at="T")
        self.assertEqual(profile["distance_aggregation"], "min_to_any_ref")
        self.assertEqual(profile["schema_version"], "jetson_owner_profile.v0")
        self.assertLessEqual(profile["thresholds"]["present_threshold"], enrollment.PRESENT_THRESHOLD_CAP)
        self.assertLessEqual(profile["thresholds"]["ambiguous_threshold"], enrollment.AMBIGUOUS_THRESHOLD_CAP)
        self.assertEqual(len(profile["embeddings"]), enrollment.MIN_USABLE_OWNER_EMBEDDINGS)

    def test_rejects_too_few_embeddings(self):
        refs = [_unit(0.0) for _ in range(enrollment.MIN_USABLE_OWNER_EMBEDDINGS - 1)]
        with self.assertRaisesRegex(ValueError, "too few usable"):
            enrollment.build_profile(refs, created_at="T")

    def test_rejects_too_wide_owner_distribution(self):
        refs = [_unit(i * 0.8) for i in range(enrollment.MIN_USABLE_OWNER_EMBEDDINGS)]
        with self.assertRaisesRegex(ValueError, "too wide"):
            enrollment.build_profile(refs, created_at="T")

    def test_profile_write_is_restricted_json(self):
        refs = [_unit(i * 0.01) for i in range(enrollment.MIN_USABLE_OWNER_EMBEDDINGS)]
        profile = enrollment.build_profile(refs, created_at="T")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state", "owner_profile.json")
            enrollment.save_profile(profile, path)
            self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            self.assertEqual(loaded["distance_aggregation"], "min_to_any_ref")

    def test_noninteractive_enrollment_refuses(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(SystemExit):
                enrollment.require_interactive_owner_confirmation(phrase="I AM ROHIT AND I AM ENROLLING MY FACE")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1b_enrollment -v
```

Expected: FAIL with missing `jetson_presence.enrollment`.

- [ ] **Step 3: Implement calibration/profile helpers**

```python
# devices/jetson_presence/jetson_presence/enrollment.py
"""Owner-gated B1b enrollment helpers.

The only durable biometric write in B1b is the restricted JSON owner profile.
Frames and crops are never persisted; the CLI ceremony is owner-run on the Jetson.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys

import numpy as np

from jetson_presence import decision

PROFILE_SCHEMA_VERSION = "jetson_owner_profile.v0"
DISTANCE_AGGREGATION = "min_to_any_ref"
DEFAULT_PROFILE_PATH = "~/.local/state/maez-jetson/owner_profile.json"

MIN_USABLE_OWNER_EMBEDDINGS = 10
TARGET_OWNER_EMBEDDINGS = 24
MAX_OWNER_INTRA_P95 = 0.55
PRESENT_MARGIN = 0.05
PRESENT_THRESHOLD_CAP = 0.62
AMBIGUITY_MARGIN = 0.10
AMBIGUOUS_THRESHOLD_CAP = 0.72


def cosine_distance(a, b) -> float:
    arr_a = np.asarray(a, dtype=np.float32)
    arr_b = np.asarray(b, dtype=np.float32)
    na = float(np.linalg.norm(arr_a))
    nb = float(np.linalg.norm(arr_b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    cos = float(np.clip(np.dot(arr_a, arr_b) / (na * nb), -1.0, 1.0))
    return 1.0 - cos


def min_distance_to_references(candidate, references) -> float:
    refs = list(references)
    if not refs:
        return math.inf
    return min(cosine_distance(candidate, ref) for ref in refs)


def leave_one_out_min_distances(embeddings) -> list[float]:
    refs = [np.asarray(e, dtype=np.float32) for e in embeddings]
    out = []
    for idx, emb in enumerate(refs):
        others = refs[:idx] + refs[idx + 1 :]
        out.append(min_distance_to_references(emb, others))
    return out


def percentile(values, q: float) -> float:
    vals = sorted(float(v) for v in values)
    if not vals:
        raise ValueError("cannot percentile empty values")
    pos = (len(vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def build_profile(embeddings, *, created_at: str) -> dict:
    refs = [np.asarray(e, dtype=np.float32) for e in embeddings]
    if len(refs) < MIN_USABLE_OWNER_EMBEDDINGS:
        raise ValueError(f"too few usable owner embeddings: {len(refs)} < {MIN_USABLE_OWNER_EMBEDDINGS}")
    owner_intra_p95 = percentile(leave_one_out_min_distances(refs), 0.95)
    if owner_intra_p95 > MAX_OWNER_INTRA_P95:
        raise ValueError(f"owner enrollment distribution too wide: p95={owner_intra_p95:.4f}")
    present_threshold = min(owner_intra_p95 + PRESENT_MARGIN, PRESENT_THRESHOLD_CAP)
    ambiguous_threshold = min(present_threshold + AMBIGUITY_MARGIN, AMBIGUOUS_THRESHOLD_CAP)
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "created_at": created_at,
        "distance_aggregation": DISTANCE_AGGREGATION,
        "thresholds": {
            "owner_intra_p95": owner_intra_p95,
            "present_threshold": present_threshold,
            "ambiguous_threshold": ambiguous_threshold,
        },
        "embeddings": [np.asarray(e, dtype=np.float32).tolist() for e in refs],
    }


def thresholds_from_profile(profile: dict) -> decision.Thresholds:
    t = profile["thresholds"]
    return decision.Thresholds(
        owner_intra_p95=float(t["owner_intra_p95"]),
        present_threshold=float(t["present_threshold"]),
        ambiguous_threshold=float(t["ambiguous_threshold"]),
    )


def load_profile(path: str | os.PathLike | None = None) -> dict | None:
    p = Path(path or DEFAULT_PROFILE_PATH).expanduser()
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as fh:
        profile = json.load(fh)
    if profile.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ValueError(f"unknown owner profile schema: {profile.get('schema_version')!r}")
    if profile.get("distance_aggregation") != DISTANCE_AGGREGATION:
        raise ValueError(f"unsupported distance aggregation: {profile.get('distance_aggregation')!r}")
    return profile


def save_profile(profile: dict, path: str | os.PathLike | None = None) -> Path:
    p = Path(path or DEFAULT_PROFILE_PATH).expanduser()
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(p.parent, 0o700)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, sort_keys=True)
        fh.write("\n")
    os.chmod(p, 0o600)
    return p


def require_interactive_owner_confirmation(*, phrase: str) -> None:
    if not sys.stdin.isatty():
        raise SystemExit("Enrollment requires an interactive owner terminal.")
    print("This will create a Jetson-local biometric owner profile.")
    print("Agents must not run this ceremony. Rohit must be physically present.")
    typed = input(f"Type exactly {phrase!r} to continue: ")
    if typed != phrase:
        raise SystemExit("Enrollment confirmation phrase did not match.")
```

- [ ] **Step 4: Run test to verify GREEN**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1b_enrollment -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/jetson_presence/enrollment.py tests/test_jetson_b1b_enrollment.py
git commit -m "feat(jetson-b1b): owner profile calibration and restricted JSON store"
```

---

## Task 3: `recognition.py` — Owner Evidence, Non-Owner Discard

**Files:**
- Create: `devices/jetson_presence/jetson_presence/recognition.py`
- Create: `tests/test_jetson_b1b_recognition.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_jetson_b1b_recognition.py
import unittest

import numpy as np

import tests._jetson_edge_path  # noqa: F401
from jetson_presence import enrollment, recognition


def _unit(angle: float):
    return np.asarray([np.cos(angle), np.sin(angle)], dtype=np.float32)


class _FakeEmbedder:
    def __init__(self, vectors):
        self._vectors = list(vectors)

    def embed(self, face):
        return self._vectors.pop(0), 1.0


class RecognitionSummaryTests(unittest.TestCase):
    def _profile(self):
        return enrollment.build_profile([_unit(i * 0.01) for i in range(enrollment.MIN_USABLE_OWNER_EMBEDDINGS)], created_at="T")

    def test_no_detection_and_non_owner_mismatch_are_identical(self):
        profile = self._profile()
        none = recognition.summarize_detections(
            frame=np.zeros((10, 10, 3), dtype=np.uint8),
            detections=[],
            embedder=_FakeEmbedder([]),
            profile=profile,
        )
        non_owner = recognition.summarize_detections(
            frame=np.zeros((10, 10, 3), dtype=np.uint8),
            detections=[((0, 0, 5, 5), 0.99)],
            embedder=_FakeEmbedder([_unit(2.5)]),
            profile=profile,
        )
        self.assertEqual(none, non_owner)
        self.assertIsNone(none.best_distance)
        self.assertFalse(none.conflict)

    def test_owner_like_distance_is_kept(self):
        profile = self._profile()
        evidence = recognition.summarize_detections(
            frame=np.zeros((10, 10, 3), dtype=np.uint8),
            detections=[((0, 0, 5, 5), 0.99)],
            embedder=_FakeEmbedder([_unit(0.02)]),
            profile=profile,
        )
        self.assertIsNotNone(evidence.best_distance)
        self.assertLess(evidence.best_distance, profile["thresholds"]["ambiguous_threshold"])
        self.assertFalse(evidence.conflict)

    def test_two_strong_owner_like_faces_are_preserved_for_conflict(self):
        profile = self._profile()
        evidence = recognition.summarize_detections(
            frame=np.zeros((10, 10, 3), dtype=np.uint8),
            detections=[((0, 0, 5, 5), 0.99), ((0, 0, 5, 5), 0.98)],
            embedder=_FakeEmbedder([_unit(0.01), _unit(0.02)]),
            profile=profile,
        )
        self.assertTrue(evidence.conflict)
        self.assertIsNotNone(evidence.best_distance)

    def test_frame_quality_good_and_bad(self):
        self.assertEqual(recognition.frame_quality(np.ones((20, 20, 3), dtype=np.uint8) * 120), ("good", "good"))
        self.assertEqual(recognition.frame_quality(None), ("bad", "bad"))
        self.assertEqual(recognition.frame_quality(np.zeros((20, 20, 3), dtype=np.uint8)), ("bad", "bad"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1b_recognition -v
```

Expected: FAIL with missing `jetson_presence.recognition`.

- [ ] **Step 3: Implement recognition helpers**

```python
# devices/jetson_presence/jetson_presence/recognition.py
"""B1b frame recognition helpers.

This module returns owner-like evidence only. Far non-owner mismatches are
discarded before decision inputs are assembled.
"""
from __future__ import annotations

import numpy as np

from jetson_presence import decision, enrollment
from jetson_presence.b1a.detector import crop_face


def frame_quality(frame) -> tuple[str, str]:
    if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
        return ("bad", "bad")
    arr = np.asarray(frame)
    if arr.size == 0:
        return ("bad", "bad")
    mean = float(arr.mean())
    std = float(arr.std())
    if mean < 8.0 or mean > 247.0 or std < 2.0:
        return ("bad", "bad")
    return ("good", "good")


def summarize_detections(*, frame, detections, embedder, profile: dict) -> decision.OwnerEvidence:
    refs = [np.asarray(v, dtype=np.float32) for v in profile.get("embeddings", [])]
    thresholds = enrollment.thresholds_from_profile(profile)
    owner_like_distances = []
    strong_distances = []
    for box, _score in detections:
        face = crop_face(frame, box)
        if getattr(face, "size", 0) == 0:
            continue
        vec, _latency_ms = embedder.embed(face)
        distance = enrollment.min_distance_to_references(vec, refs)
        if distance <= thresholds.ambiguous_threshold:
            owner_like_distances.append(float(distance))
        if distance <= thresholds.present_threshold:
            strong_distances.append(float(distance))
    return decision.OwnerEvidence(
        best_distance=min(owner_like_distances) if owner_like_distances else None,
        conflict=len(strong_distances) > 1,
    )


def summarize_frame(*, frame, detector, embedder, profile: dict, score_threshold: float):
    detections, detector_ms = detector.detect(frame, score_threshold=score_threshold)
    return summarize_detections(frame=frame, detections=detections, embedder=embedder, profile=profile), detector_ms
```

- [ ] **Step 4: Run test to verify GREEN**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1b_recognition -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/jetson_presence/recognition.py tests/test_jetson_b1b_recognition.py
git commit -m "feat(jetson-b1b): summarize owner evidence and discard non-owner mismatches"
```

---

## Task 4: `run.py` Recognition Path + Config

**Files:**
- Modify: `devices/jetson_presence/jetson_presence/config.py`
- Modify: `devices/jetson_presence/jetson_presence/run.py`
- Modify: `tests/test_jetson_edge_config.py`
- Modify: `tests/test_jetson_edge_run.py`
- Create: `tests/test_jetson_b1b_run.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_jetson_edge_config.py`:

```python
    def test_b1b_recognition_defaults(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = config.load_config()
            self.assertEqual(cfg.owner_profile_path, "~/.local/state/maez-jetson/owner_profile.json")
            self.assertEqual(cfg.detector_engine_path, "models/det_500m.fp32.engine")
            self.assertEqual(cfg.embedding_engine_path, "models/w600k_mbf.fp32.engine")
            self.assertEqual(cfg.recognition_window_frames, 8)
            self.assertEqual(cfg.min_reliable_frames, 6)
            self.assertEqual(cfg.min_window_duration_seconds, 0.50)
            self.assertEqual(cfg.recognition_frame_interval_seconds, 0.10)
```

Create `tests/test_jetson_b1b_run.py`:

```python
import unittest
from unittest import mock

import tests._jetson_edge_path  # noqa: F401
from jetson_presence import decision, run


class _FakeCamera:
    def __init__(self, frames):
        self.frames = list(frames)
        self.opened = False
        self.released = False

    def open(self):
        self.opened = True
        return True

    def read_frame(self):
        if not self.frames:
            return False, None
        return True, self.frames.pop(0)

    def release(self):
        self.released = True


class RunRecognizeTests(unittest.TestCase):
    def _cfg(self):
        return mock.Mock(
            owner_profile_path="profile.json",
            detector_engine_path="det.engine",
            embedding_engine_path="emb.engine",
            recognition_window_frames=3,
            min_reliable_frames=2,
            min_window_duration_seconds=0.0,
            recognition_frame_interval_seconds=0.0,
            host_url="http://host",
            intake_path="/intake",
            token="token",
            curtain_sentinel="/curtain",
        )

    def test_pre_enroll_emits_unenrolled_unknown(self):
        emitted = []
        with (
            mock.patch.object(run.enrollment, "load_profile", return_value=None),
            mock.patch.object(run, "_is_curtained", return_value=False),
        ):
            label = run._run_recognition_cycle(cfg=self._cfg(), camera=_FakeCamera([object()]), emit=emitted.append)
        self.assertEqual((label["sensor_state"], label["owner_present"], label["confidence"]), ("unenrolled", "unknown", "low"))
        self.assertEqual(emitted, [label])

    def test_curtain_emits_curtained_without_opening_camera(self):
        emitted = []
        cam = _FakeCamera([object()])
        with mock.patch.object(run, "_is_curtained", return_value=True):
            label = run._run_recognition_cycle(cfg=self._cfg(), camera=cam, emit=emitted.append)
        self.assertFalse(cam.opened)
        self.assertTrue(cam.released)
        self.assertEqual((label["sensor_state"], label["owner_present"]), ("curtained", "unknown"))

    def test_recognition_uses_decision_and_releases_camera(self):
        emitted = []
        cam = _FakeCamera([object(), object(), object()])
        profile = {
            "thresholds": {"owner_intra_p95": 0.35, "present_threshold": 0.4, "ambiguous_threshold": 0.5},
            "embeddings": [[1.0, 0.0]],
        }
        expected = decision.decide_label(
            ts="T",
            window=decision.WindowSignals(True, "good", "good", True, True, 3, 0.0),
            evidence=decision.OwnerEvidence(best_distance=0.2),
            thresholds=decision.Thresholds(0.35, 0.4, 0.5),
        )
        with (
            mock.patch.object(run.enrollment, "load_profile", return_value=profile),
            mock.patch.object(run.enrollment, "thresholds_from_profile", return_value=decision.Thresholds(0.35, 0.4, 0.5)),
            mock.patch.object(run.recognition, "frame_quality", return_value=("good", "good")),
            mock.patch.object(run.recognition, "summarize_frame", return_value=(decision.OwnerEvidence(best_distance=0.2), 1.0)),
            mock.patch.object(run, "_is_curtained", return_value=False),
            mock.patch.object(run, "_now_ts", return_value="T"),
            mock.patch.object(run.time, "sleep", lambda s: None),
        ):
            label = run._run_recognition_cycle(cfg=self._cfg(), camera=cam, emit=emitted.append)
        self.assertEqual(label, expected)
        self.assertEqual(emitted, [expected])
        self.assertTrue(cam.released)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_config tests.test_jetson_b1b_run -v
```

Expected: FAIL on missing config fields / missing `_run_recognition_cycle`.

- [ ] **Step 3: Implement config fields**

Update `EdgeConfig` and `load_config()` in `config.py`:

```python
@dataclass(frozen=True)
class EdgeConfig:
    host_url: str
    intake_path: str
    token: str
    curtain_sentinel: str
    device_index: int
    cadence_seconds: float
    owner_profile_path: str
    detector_engine_path: str
    embedding_engine_path: str
    recognition_window_frames: int
    min_reliable_frames: int
    min_window_duration_seconds: float
    recognition_frame_interval_seconds: float
```

Add these fields to the return value:

```python
        owner_profile_path=os.environ.get("MAEZ_JETSON_OWNER_PROFILE", "~/.local/state/maez-jetson/owner_profile.json"),
        detector_engine_path=os.environ.get("MAEZ_JETSON_DETECTOR_ENGINE", "models/det_500m.fp32.engine"),
        embedding_engine_path=os.environ.get("MAEZ_JETSON_EMBEDDING_ENGINE", "models/w600k_mbf.fp32.engine"),
        recognition_window_frames=int(os.environ.get("MAEZ_JETSON_RECOGNITION_FRAMES", "8")),
        min_reliable_frames=int(os.environ.get("MAEZ_JETSON_MIN_RELIABLE_FRAMES", "6")),
        min_window_duration_seconds=float(os.environ.get("MAEZ_JETSON_MIN_WINDOW_DURATION_SECONDS", "0.50")),
        recognition_frame_interval_seconds=float(os.environ.get("MAEZ_JETSON_RECOGNITION_FRAME_INTERVAL_SECONDS", "0.10")),
```

- [ ] **Step 4: Implement bounded recognition path in `run.py`**

Add imports:

```python
from jetson_presence import decision, enrollment, recognition
from jetson_presence.b1a.detector import Detector
from jetson_presence.b1a.embedding import Embedder
```

Add:

```python
def _run_recognition_cycle(*, cfg, camera, emit, detector=None, embedder=None):
    ts = _now_ts()
    if _is_curtained(cfg.curtain_sentinel):
        camera.release()
        label = decision.unknown_label("curtained", ts)
        emit(label)
        return label

    profile = enrollment.load_profile(cfg.owner_profile_path)
    if profile is None:
        label = decision.unknown_label("unenrolled", ts)
        emit(label)
        return label

    thresholds = enrollment.thresholds_from_profile(profile)
    detector = detector or Detector(cfg.detector_engine_path)
    embedder = embedder or Embedder(cfg.embedding_engine_path)
    if not camera.open():
        label = decision.unknown_label("unavailable", ts)
        emit(label)
        camera.release()
        return label

    reliable_frames = 0
    best_distances = []
    conflict_seen = False
    frame_health = "bad"
    exposure_blur = "bad"
    start = time.perf_counter()
    try:
        for idx in range(cfg.recognition_window_frames):
            ok, frame = camera.read_frame()
            if ok:
                fh, eb = recognition.frame_quality(frame)
                if fh == "good" and eb == "good":
                    reliable_frames += 1
                    frame_health, exposure_blur = "good", "good"
                    evidence, _det_ms = recognition.summarize_frame(
                        frame=frame,
                        detector=detector,
                        embedder=embedder,
                        profile=profile,
                        score_threshold=0.5,
                    )
                    if evidence.conflict:
                        conflict_seen = True
                    if evidence.best_distance is not None:
                        best_distances.append(evidence.best_distance)
            if idx + 1 < cfg.recognition_window_frames:
                time.sleep(cfg.recognition_frame_interval_seconds)
    finally:
        camera.release()

    elapsed = time.perf_counter() - start
    window = decision.WindowSignals(
        camera_open=True,
        frame_health=frame_health,
        exposure_blur=exposure_blur,
        model_loaded=True,
        enrollment_available=True,
        reliable_frames=reliable_frames,
        window_duration_s=elapsed,
    )
    label = decision.decide_label(
        ts=ts,
        window=window,
        evidence=decision.OwnerEvidence(
            best_distance=min(best_distances) if best_distances else None,
            conflict=conflict_seen,
        ),
        thresholds=thresholds,
    )
    emit(label)
    return label
```

Add CLI flag:

```python
    g.add_argument("--recognize", action="store_true", help="run bounded B1b recognition cycle(s)")
```

Then in the loop:

```python
            if args.recognize:
                _run_recognition_cycle(
                    cfg=cfg,
                    camera=camera,
                    emit=lambda label: post_label(cfg.host_url, cfg.intake_path, token=cfg.token, label=label),
                )
            else:
                _run_one_cycle(cfg=cfg, camera=camera)
```

- [ ] **Step 5: Run tests to verify GREEN**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_edge_config tests.test_jetson_edge_run tests.test_jetson_b1b_run -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add devices/jetson_presence/jetson_presence/config.py devices/jetson_presence/jetson_presence/run.py tests/test_jetson_edge_config.py tests/test_jetson_edge_run.py tests/test_jetson_b1b_run.py
git commit -m "feat(jetson-b1b): bounded recognition run path"
```

---

## Task 5: Structural Guards — Import Boundary + No-Write Witnesses

**Files:**
- Create: `tests/test_jetson_b1b_structural_guards.py`
- Modify only if needed: `devices/jetson_presence/.gitignore`

- [ ] **Step 1: Write the failing guard tests**

```python
# tests/test_jetson_b1b_structural_guards.py
import ast
import os
import pathlib
import tempfile
import unittest
from contextlib import contextmanager
from unittest import mock

import tests._jetson_edge_path  # noqa: F401

_PKG = pathlib.Path(__file__).resolve().parents[1] / "devices" / "jetson_presence" / "jetson_presence"
_B1B_NO_EMIT = ("decision.py", "recognition.py", "enrollment.py")
_FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "urllib.request",
    "http",
    "http.client",
    "jetson_presence.emitter",
    "emitter",
    "config",
    "jetson_presence.config",
}
_HOST_LITERALS = ("X-Maez-Jetson-Token", "/api/v1/presence", "MAEZ_JETSON_DEVICE_TOKEN")
_BINARY_OR_IMAGE_WRITE_TOKENS = (
    "imwrite",
    "VideoWriter",
    "imencode",
    "write_bytes",
    ".tofile(",
    ".save(",
    "np.save",
    "numpy.save",
    "'wb'",
    '"wb"',
    "'w+b'",
    '"w+b"',
    "'rb+'",
    '"rb+"',
    "'r+b'",
    '"r+b"',
    "'ab'",
    '"ab"',
)


def _imported_names(src: str):
    tree = ast.parse(src)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if base:
                names.add(base)
                names.add(base.split(".")[0])
            for alias in node.names:
                names.add(alias.name)
                if base:
                    names.add(f"{base}.{alias.name}")
    return names


def _scan_import_offenders(paths):
    offenders = []
    for path in paths:
        src = pathlib.Path(path).read_text(encoding="utf-8")
        imported = _imported_names(src)
        for bad in _FORBIDDEN_IMPORTS & imported:
            offenders.append(f"{pathlib.Path(path).name}: imports {bad}")
        for lit in _HOST_LITERALS:
            if lit in src:
                offenders.append(f"{pathlib.Path(path).name}: names {lit}")
    return offenders


@contextmanager
def _watch_file_writes():
    import builtins

    writes = []
    real_open = builtins.open
    real_path_open = pathlib.Path.open

    def _is_write_mode(mode: str) -> bool:
        return any(c in mode for c in "wax") or "+" in mode

    def _open(path, mode="r", *args, **kwargs):
        if _is_write_mode(mode):
            writes.append((str(path), mode))
        return real_open(path, mode, *args, **kwargs)

    def _path_open(path, mode="r", *args, **kwargs):
        if _is_write_mode(mode):
            writes.append((str(path), mode))
        return real_path_open(path, mode, *args, **kwargs)

    with mock.patch("builtins.open", _open), mock.patch.object(pathlib.Path, "open", _path_open):
        yield writes


class B1bStructuralGuardTests(unittest.TestCase):
    def test_import_guard_full_scan_trips_on_planted_emitter_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            probe = pathlib.Path(tmp) / "decision.py"
            probe.write_text("from jetson_presence import emitter\n", encoding="utf-8")
            offenders = _scan_import_offenders([probe])
        self.assertEqual(offenders, ["decision.py: imports emitter"])

    def test_decision_recognition_enrollment_import_no_emitter_or_network(self):
        offenders = _scan_import_offenders(_PKG / name for name in _B1B_NO_EMIT)
        self.assertEqual(offenders, [])

    def test_profile_write_shape_is_text_json_not_binary_or_image(self):
        src = (_PKG / "enrollment.py").read_text(encoding="utf-8")
        self.assertIn("json.dump", src)
        self.assertIn('open(p, "w", encoding="utf-8")', src)
        for tok in _BINARY_OR_IMAGE_WRITE_TOKENS:
            self.assertNotIn(tok, src)

    def test_recognition_modules_have_no_binary_or_image_writes(self):
        offenders = []
        for name in ("recognition.py", "decision.py", "run.py"):
            src = (_PKG / name).read_text(encoding="utf-8")
            for tok in _BINARY_OR_IMAGE_WRITE_TOKENS:
                if tok in src:
                    offenders.append(f"{name}: {tok}")
        self.assertEqual(offenders, [])

    def test_run_recognize_cycle_writes_no_files(self):
        from jetson_presence import decision, run

        class FakeCamera:
            def __init__(self):
                self.released = False
            def open(self):
                return True
            def read_frame(self):
                return True, object()
            def release(self):
                self.released = True

        cfg = mock.Mock(
            owner_profile_path="profile.json",
            detector_engine_path="det.engine",
            embedding_engine_path="emb.engine",
            recognition_window_frames=1,
            min_reliable_frames=1,
            min_window_duration_seconds=0.0,
            recognition_frame_interval_seconds=0.0,
            curtain_sentinel="/curtain",
        )
        profile = {
            "thresholds": {"owner_intra_p95": 0.35, "present_threshold": 0.4, "ambiguous_threshold": 0.5},
            "embeddings": [[1.0, 0.0]],
        }
        cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmp, _watch_file_writes() as writes:
                os.chdir(tmp)
                with (
                    mock.patch.object(run, "_is_curtained", return_value=False),
                    mock.patch.object(run.enrollment, "load_profile", return_value=profile),
                    mock.patch.object(run.enrollment, "thresholds_from_profile", return_value=decision.Thresholds(0.35, 0.4, 0.5)),
                    mock.patch.object(run.recognition, "frame_quality", return_value=("good", "good")),
                    mock.patch.object(run.recognition, "summarize_frame", return_value=(decision.OwnerEvidence(), 1.0)),
                ):
                    run._run_recognition_cycle(cfg=cfg, camera=FakeCamera(), emit=lambda label: None)
        finally:
            os.chdir(cwd)
        self.assertEqual(writes, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify RED if any guard gap exists**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1b_structural_guards -v
```

Expected before any cleanup: either PASS if prior tasks already satisfy the guards, or FAIL on exact offending import/write shape. If it passes immediately, the planted `test_import_guard_full_scan_trips_on_planted_emitter_import` still proves the same full scan used by the real guard catches the forbidden shape.

- [ ] **Step 3: Fix any exact offenders**

Allowed:

- `run.py` may import `emitter.post_label` / host config.
- `enrollment.py` may use `open(p, "w", encoding="utf-8")` and `json.dump`.

Forbidden:

- `decision.py`, `recognition.py`, `enrollment.py` importing emitter/config/network.
- Binary/image/vector writes in recognition code.
- Profile writes from `run --recognize`.

- [ ] **Step 4: Run guard tests to verify GREEN**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1b_structural_guards -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_jetson_b1b_structural_guards.py devices/jetson_presence/.gitignore
git commit -m "test(jetson-b1b): structural guards for recognition boundary"
```

---

## Task 6: Enrollment CLI Ceremony

**Files:**
- Modify: `devices/jetson_presence/jetson_presence/enrollment.py`
- Modify: `tests/test_jetson_b1b_enrollment.py`

- [ ] **Step 1: Add failing CLI tests**

Append:

```python
class EnrollmentCliTests(unittest.TestCase):
    def test_cli_rejects_non_positive_frame_count(self):
        with self.assertRaises(SystemExit):
            enrollment.build_parser().parse_args(["--frames", "0"])

    def test_cli_defaults_are_owner_local(self):
        args = enrollment.build_parser().parse_args([])
        self.assertEqual(args.profile_path, "~/.local/state/maez-jetson/owner_profile.json")
        self.assertEqual(args.frames, enrollment.TARGET_OWNER_EMBEDDINGS)
```

- [ ] **Step 2: Run RED**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1b_enrollment -v
```

Expected: FAIL on missing `build_parser`.

- [ ] **Step 3: Implement CLI parser and enrollment main**

Add to `enrollment.py`:

```python
def build_parser():
    import argparse

    class _PositiveInt(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            value = int(values)
            if value < 1:
                parser.error(f"{option_string} must be >= 1")
            setattr(namespace, self.dest, value)

    parser = argparse.ArgumentParser(description="Owner-run Jetson B1b enrollment ceremony.")
    parser.add_argument("--frames", action=_PositiveInt, default=TARGET_OWNER_EMBEDDINGS)
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--detector-engine", default="models/det_500m.fp32.engine")
    parser.add_argument("--embedding-engine", default="models/w600k_mbf.fp32.engine")
    parser.add_argument("--profile-path", default=DEFAULT_PROFILE_PATH)
    parser.add_argument("--score-threshold", type=float, default=0.5)
    return parser
```

Add the device-only `main()` after the parser:

```python
def main(argv=None) -> int:
    import cv2
    from datetime import datetime, timezone

    from jetson_presence.b1a.detector import Detector, crop_face
    from jetson_presence.b1a.embedding import Embedder

    args = build_parser().parse_args(argv)
    require_interactive_owner_confirmation(phrase="I AM ROHIT AND I AM ENROLLING MY FACE")
    detector = Detector(args.detector_engine)
    embedder = Embedder(args.embedding_engine)
    cap = cv2.VideoCapture(args.device_index)
    if not cap.isOpened():
        raise SystemExit(f"camera open failed: index {args.device_index}")
    embeddings = []
    try:
        while len(embeddings) < args.frames:
            ok, frame = cap.read()
            if not ok:
                continue
            detections, _det_ms = detector.detect(frame, score_threshold=args.score_threshold)
            if not detections:
                continue
            face = crop_face(frame, detections[0][0])
            if getattr(face, "size", 0) == 0:
                continue
            vec, _emb_ms = embedder.embed(face)
            embeddings.append(vec)
            print(f"captured_embedding={len(embeddings)}/{args.frames}")
    finally:
        cap.release()
    profile = build_profile(embeddings, created_at=datetime.now(timezone.utc).isoformat())
    path = save_profile(profile, args.profile_path)
    print(f"profile_written={path}")
    print(f"owner_intra_p95={profile['thresholds']['owner_intra_p95']:.4f}")
    print(f"present_threshold={profile['thresholds']['present_threshold']:.4f}")
    print(f"ambiguous_threshold={profile['thresholds']['ambiguous_threshold']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run GREEN**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1b_enrollment -v
```

- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/jetson_presence/enrollment.py tests/test_jetson_b1b_enrollment.py
git commit -m "feat(jetson-b1b): owner-run enrollment CLI"
```

---

## Task 7: Focused Regression + Device Witness Runbook

**Files:**
- No code unless verification finds an issue.
- Create: `docs/handoffs/2026-06-30-jetson-presence-b1b-handoff.md`

- [ ] **Step 1: Run focused host suite**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_jetson_b1b_decision \
  tests.test_jetson_b1b_enrollment \
  tests.test_jetson_b1b_recognition \
  tests.test_jetson_b1b_run \
  tests.test_jetson_b1b_structural_guards \
  tests.test_jetson_edge_config \
  tests.test_jetson_edge_run \
  tests.test_jetson_edge_loop \
  tests.test_jetson_edge_no_frame_write \
  tests.test_jetson_b1a_no_post \
  tests.test_jetson_b1a_no_crop_write \
  tests.test_jetson_presence_contract \
  tests.test_jetson_presence_intake \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run lint/shell checks**

```bash
/home/rohit/maez/.venv/bin/ruff check devices/jetson_presence/jetson_presence tests/test_jetson_b1b_*.py tests/test_jetson_edge_*.py tests/test_jetson_presence_*.py
bash -n devices/jetson_presence/setup_models.sh devices/jetson_presence/deploy.sh
git diff --check
```

Expected: all clean.

- [ ] **Step 3: Deploy to Jetson**

```bash
MAEZ_JETSON_SSH=rohit@192.168.40.27 \
MAEZ_JETSON_DEST=/home/rohit/maez-jetson \
bash devices/jetson_presence/deploy.sh
```

Expected: source deploy only; no profile/model artifacts copied from host.

- [ ] **Step 4: Pre-enrollment witness**

On main host, ensure Slice-A doorway flag/token/tunnel are in the same posture used for B0 if you want POST receipts. Then on Jetson:

```bash
cd /home/rohit/maez-jetson
PYTHONDONTWRITEBYTECODE=1 MAEZ_JETSON_DEVICE_TOKEN="$MAEZ_JETSON_DEVICE_TOKEN" \
python3 -m jetson_presence.run --recognize --loops 1
```

Expected host receipt: `sensor_state=unenrolled owner_present=unknown`.

- [ ] **Step 5: Owner enrollment witness**

Owner runs this interactively on Jetson. Agents must not run it.

```bash
cd /home/rohit/maez-jetson
PYTHONDONTWRITEBYTECODE=1 python3 -m jetson_presence.enrollment --frames 24 --device-index 0
```

Expected:

- prompts for exact confirmation phrase;
- writes one profile under `~/.local/state/maez-jetson/owner_profile.json`;
- profile mode `0600`, parent dir `0700`;
- printed thresholds within caps;
- no `.jpg`, `.png`, `.npy`, `.npz`, or crop/frame artifacts created.

- [ ] **Step 6: Bounded recognition witnesses**

Owner present:

```bash
cd /home/rohit/maez-jetson
PYTHONDONTWRITEBYTECODE=1 MAEZ_JETSON_DEVICE_TOKEN="$MAEZ_JETSON_DEVICE_TOKEN" \
python3 -m jetson_presence.run --recognize --loops 1
```

Expected host receipt: `sensor_state=available owner_present=present` or, if the enrollment threshold is too conservative, `owner_present=unknown` with no action taken. If it is `unknown`, do not widen thresholds manually; review enrollment quality.

Owner gone / approved empty view:

```bash
cd /home/rohit/maez-jetson
PYTHONDONTWRITEBYTECODE=1 MAEZ_JETSON_DEVICE_TOKEN="$MAEZ_JETSON_DEVICE_TOKEN" \
python3 -m jetson_presence.run --recognize --loops 1
```

Expected host receipt after a reliable empty window: `sensor_state=available owner_present=absent`.

Curtain:

```bash
touch /run/maez/jetson_curtain
cd /home/rohit/maez-jetson
PYTHONDONTWRITEBYTECODE=1 MAEZ_JETSON_DEVICE_TOKEN="$MAEZ_JETSON_DEVICE_TOKEN" \
python3 -m jetson_presence.run --recognize --loops 1
rm -f /run/maez/jetson_curtain
```

Expected: `sensor_state=curtained owner_present=unknown`, camera released/reopenable.

- [ ] **Step 7: Write handoff**

Create `docs/handoffs/2026-06-30-jetson-presence-b1b-handoff.md` with:

- commit range;
- focused test counts;
- structural guard status;
- device witness status;
- explicit "no downstream consumer added";
- residual false-present/liveness note;
- B2 and Slice C deferred.

- [ ] **Step 8: Commit handoff**

```bash
git add docs/handoffs/2026-06-30-jetson-presence-b1b-handoff.md
git commit -m "docs(jetson-b1b): handoff bounded recognition witness"
```

---

## Plan Self-Review

**Spec coverage:**

- Send-not-act boundary: Task 4 only sends through existing emitter; no host consumer files touched; Task 7 handoff records no consumer.
- Reliable-window input allowlist: Task 1 dataclass field test and empty-vs-non-owner-populated input equality.
- Non-leak at input and label: Task 1 closed input fields + byte-identical input/label tests; Task 3 non-owner mismatch discarded before decision.
- Threshold calibration: Task 2 leave-one-out min-to-any calibration, constants, reject-too-wide.
- Biometric at rest: Task 2 restricted JSON mode; Task 5 profile-write-shape guard.
- Interactive owner enrollment: Task 2 non-interactive refusal; Task 6 owner-run CLI.
- Confidence composite: Task 1 present/absent bucket tests and no raw distance in label.
- Conflict: Task 1 single-frame simultaneous strong owner-like faces -> unknown; Task 4 aggregates conflict as a boolean across the window, not by sample count.
- Freshness two-layer: unchanged host contract; Task 7 explicitly does not claim B2 staleness.
- Residual risk/liveness: Task 7 handoff must restate; no Slice-C consumer added.

**Completeness scan:** no unresolved fill-in tasks. Device witness commands are concrete, but the owner-present/owner-gone witnesses depend on the physical scene; failures are interpreted rather than papered over.

**Type consistency:**

- `Thresholds(owner_intra_p95, present_threshold, ambiguous_threshold)` used across decision/enrollment/run.
- `WindowSignals(camera_open, frame_health, exposure_blur, model_loaded, enrollment_available, reliable_frames, window_duration_s)` matches the closed allowlist.
- `OwnerEvidence(best_distance: float | None, conflict: bool)` is the only evidence passed to decision; `best_distance` is the minimum owner-like distance across the window, while `conflict` can only be set by a single frame with multiple strong owner-like faces.
- Profile schema uses `distance_aggregation="min_to_any_ref"` and thresholds matching `Thresholds`.

## Execution Handoff

Plan stops before implementation. Recommended execution: subagent-driven task-by-task, with Codex reviewing after Task 5 before any device enrollment. Owner alone runs Task 7 Step 5 enrollment.
