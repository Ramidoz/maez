# Jetson Presence B1a — Pipeline Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Prove on the real Orin that `SCRFD` detect + `ArcFace` embed (ONNX → TensorRT) runs, distinguishes the owner from an empty frame, has ONNX-vs-TensorRT parity, and is fast enough — non-live (prints only, never POSTs).

**Architecture:** A `b1a/` subpackage isolated from B0's live path. Pure logic (matcher, parity *metrics*, manifest verify) is host-TDD'd RED-first; the TensorRT *inference* (detector/embedding wrappers, `run_parity`, `spike`) is **device-only**, written build-time against the real model shapes and proven by owner-run device witnesses.

**Tech Stack:** Python 3.10; host tests `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest); device adds `onnx`, `onnxruntime` (ONNX reference), a TRT-inference binding (`pycuda`/`cuda-python`), `cv2` (V4L2), TensorRT 10.3 + `trtexec`. Reference ONNX detect/decode via the InsightFace SCRFD/ArcFace models.

**Spec:** `docs/superpowers/specs/2026-06-30-jetson-presence-b1a-spike-design.md` (@f466f03). B1a only; B1b (enrollment + decision rule + live emit) is its own slice.

**Covenant invariants:** no live non-owner ever; RAM-only owner reference by default; manifest-pinned models (sha/license); **no frames OR crops written** (RAM only); **structurally unable to POST** (`b1a/` imports nothing network); engine **precision explicit** (FP32 first); parity compared **after shared decode/NMS**.

---

## File Structure

```
devices/jetson_presence/
  deploy.sh
  setup_models.sh                 # NEW: beside deploy.sh, NOT in the package
  models/manifest.json            # NEW: tracked pins (name/url/sha256/license/input_shape/precision/engine_path)
  .gitignore                      # MODIFY: add *.onnx *.engine *.plan *.npz *.npy
  jetson_presence/
    b1a/
      __init__.py                 # NEW (empty)
      matcher.py                  # NEW pure: cosine distance + is_match   (host-TDD)
      parity.py                   # NEW pure metrics: iou/box_parity/embedding_parity (host-TDD)
                                  #   + run_parity(...) device-only (build-time)
      manifest.py                 # NEW: load manifest.json + verify_sha256 (host-TDD)
      detector.py                 # NEW: SCRFD TRT wrapper + shared decode/NMS (device; build-time internals)
      embedding.py                # NEW: ArcFace TRT wrapper (device; build-time internals)
      spike.py                    # NEW: CLI-only harness, no config.py import, no network (device run)
tests/
  test_jetson_b1a_matcher.py      # NEW host-TDD
  test_jetson_b1a_parity.py       # NEW host-TDD
  test_jetson_b1a_manifest.py     # NEW host-TDD
  test_jetson_b1a_no_post.py      # NEW host: static no-network guard over b1a/
  test_jetson_b1a_no_crop_write.py# NEW host: static no-frame/crop-write guard over b1a/
```

Host imports the package via the existing `tests/_jetson_edge_path.py` helper (`from jetson_presence.b1a import ...`).

---

## Task 1: `matcher.py` — pure cosine match (host-TDD)

**Files:** Create `devices/jetson_presence/jetson_presence/b1a/__init__.py` (empty), `b1a/matcher.py`; Create `tests/test_jetson_b1a_matcher.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_jetson_b1a_matcher.py
import unittest
import tests._jetson_edge_path  # noqa: F401
from jetson_presence.b1a import matcher


class MatcherTests(unittest.TestCase):
    def test_identical_vectors_distance_zero_and_match(self):
        v = [0.0, 1.0, 0.0, 0.0]
        self.assertAlmostEqual(matcher.cosine_distance(v, v), 0.0, places=6)
        self.assertTrue(matcher.is_match(matcher.cosine_distance(v, v), threshold=0.4))

    def test_orthogonal_vectors_distance_one_no_match(self):
        a = [1.0, 0.0]; b = [0.0, 1.0]
        self.assertAlmostEqual(matcher.cosine_distance(a, b), 1.0, places=6)
        self.assertFalse(matcher.is_match(matcher.cosine_distance(a, b), threshold=0.4))

    def test_random_dissimilar_vectors_no_match(self):
        a = [0.9, 0.1, 0.05, 0.0]; b = [-0.8, 0.2, 0.9, 0.3]
        self.assertFalse(matcher.is_match(matcher.cosine_distance(a, b), threshold=0.4))

    def test_threshold_boundary(self):
        self.assertTrue(matcher.is_match(0.39, threshold=0.4))
        self.assertFalse(matcher.is_match(0.40, threshold=0.4))  # strict <

    def test_zero_vector_is_safe_no_match(self):
        # a degenerate (all-zero) embedding must not crash and must not match
        d = matcher.cosine_distance([0.0, 0.0], [1.0, 0.0])
        self.assertFalse(matcher.is_match(d, threshold=0.4))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run → FAIL** (`ModuleNotFoundError: jetson_presence.b1a`).
Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1a_matcher -v`

- [ ] **Step 3: Implement**

```python
# devices/jetson_presence/jetson_presence/b1a/matcher.py
"""Pure cosine-distance match. No I/O, no models. The one fully host-testable
piece of the recognition logic. Distance in [0, 2]; match is distance < threshold."""
from __future__ import annotations

import math


def cosine_distance(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 1.0  # degenerate vector -> maximally dissimilar, never a match
    cos = max(-1.0, min(1.0, dot / (na * nb)))
    return 1.0 - cos


def is_match(distance: float, *, threshold: float) -> bool:
    return distance < threshold  # strict: at-threshold is NOT a match
```

- [ ] **Step 4: Run → PASS** (5 tests).
- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/jetson_presence/b1a/__init__.py devices/jetson_presence/jetson_presence/b1a/matcher.py tests/test_jetson_b1a_matcher.py
git commit -m "feat(jetson-b1a): pure cosine matcher + tests"
```

---

## Task 2: `parity.py` — pure parity metrics (host-TDD)

**Files:** Create `b1a/parity.py` (metrics only this task); Create `tests/test_jetson_b1a_parity.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_jetson_b1a_parity.py
import unittest
import tests._jetson_edge_path  # noqa: F401
from jetson_presence.b1a import parity


class IoUTests(unittest.TestCase):
    def test_identical_boxes_iou_one(self):
        self.assertAlmostEqual(parity.iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0, places=6)

    def test_disjoint_boxes_iou_zero(self):
        self.assertEqual(parity.iou((0, 0, 10, 10), (100, 100, 110, 110)), 0.0)

    def test_half_overlap(self):
        # boxes (0,0,10,10) and (5,0,15,10): inter=50, union=150 -> 1/3
        self.assertAlmostEqual(parity.iou((0, 0, 10, 10), (5, 0, 15, 10)), 1 / 3, places=4)


class BoxParityTests(unittest.TestCase):
    def test_pass_same_box_same_score(self):
        self.assertTrue(parity.box_parity((0, 0, 10, 10), 0.95, (0, 0, 10, 10), 0.951))

    def test_fail_low_iou(self):
        self.assertFalse(parity.box_parity((0, 0, 10, 10), 0.95, (5, 0, 15, 10), 0.95))

    def test_fail_score_drift(self):
        self.assertFalse(parity.box_parity((0, 0, 10, 10), 0.95, (0, 0, 10, 10), 0.90))


class EmbeddingParityTests(unittest.TestCase):
    def test_pass_identical_vectors(self):
        v = [0.1, 0.2, 0.3, 0.9]
        self.assertTrue(parity.embedding_parity(v, v))

    def test_fail_dissimilar_vectors(self):
        self.assertFalse(parity.embedding_parity([1.0, 0.0], [0.0, 1.0]))

    def test_pass_tiny_fp_jitter(self):
        a = [0.1, 0.2, 0.3, 0.9]
        b = [0.1000001, 0.2, 0.3, 0.8999999]
        self.assertTrue(parity.embedding_parity(a, b))  # FP32 jitter still > 0.999 cosine


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run → FAIL.**
Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1a_parity -v`

- [ ] **Step 3: Implement (metrics only; `run_parity` device fn added in Task 7)**

```python
# devices/jetson_presence/jetson_presence/b1a/parity.py
"""ONNX-vs-TensorRT parity. The METRICS here are pure + host-tested so 'within
tolerance' is an exact pass/fail. The device-only run_parity() (Task 7) runs the
real ONNX + TensorRT, applies the SAME decode/NMS, then calls these metrics.

Tolerances (FP32 engine; strict): detector IoU > 0.99 AND |score| < 0.01;
embedding cosine similarity > 0.999. If an FP16 engine misses these, that is a
real measured result (precision tradeoff), never a fuzzy override.
"""
from __future__ import annotations

import math

IOU_MIN = 0.99
SCORE_MAX_DIFF = 0.01
EMBED_COS_MIN = 0.999


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def box_parity(onnx_box, onnx_score, trt_box, trt_score) -> bool:
    return iou(onnx_box, trt_box) > IOU_MIN and abs(onnx_score - trt_score) < SCORE_MAX_DIFF


def _cosine_sim(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (na * nb)))


def embedding_parity(onnx_vec, trt_vec) -> bool:
    return _cosine_sim(onnx_vec, trt_vec) > EMBED_COS_MIN
```

- [ ] **Step 4: Run → PASS** (9 tests).
- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/jetson_presence/b1a/parity.py tests/test_jetson_b1a_parity.py
git commit -m "feat(jetson-b1a): pure parity metrics (IoU/box/embedding) + tests"
```

---

## Task 3: model manifest + `manifest.py` verify (host-TDD)

**Files:** Create `devices/jetson_presence/models/manifest.json`, `b1a/manifest.py`; Create `tests/test_jetson_b1a_manifest.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_jetson_b1a_manifest.py
import hashlib
import os
import tempfile
import unittest
import tests._jetson_edge_path  # noqa: F401
from jetson_presence.b1a import manifest as man


class ManifestSchemaTests(unittest.TestCase):
    def test_real_manifest_has_required_fields_per_model(self):
        m = man.load_manifest()  # default path = devices/jetson_presence/models/manifest.json
        self.assertIn("models", m)
        self.assertGreaterEqual(len(m["models"]), 2)  # detector + embedding
        required = {"name", "source_url", "sha256", "license", "input_shape", "precision", "engine_path"}
        for entry in m["models"]:
            self.assertTrue(required <= set(entry), f"missing fields in {entry.get('name')}")
        names = {e["name"] for e in m["models"]}
        self.assertTrue(any("scrfd" in n.lower() for n in names))
        self.assertTrue(any("arcface" in n.lower() or "w600k" in n.lower() for n in names))

    def test_precision_is_explicit_fp32_or_fp16(self):
        for entry in man.load_manifest()["models"]:
            self.assertIn(entry["precision"], ("fp32", "fp16"))


class HashLockTests(unittest.TestCase):
    def test_pending_manifest_is_not_locked(self):
        m = {"models": [{"sha256": man.PENDING}, {"sha256": "a" * 64}]}
        self.assertFalse(man.hashes_locked(m))

    def test_all_real_hashes_is_locked(self):
        m = {"models": [{"sha256": "a" * 64}, {"sha256": "b" * 64}]}
        self.assertTrue(man.hashes_locked(m))

    def test_empty_or_missing_sha_is_not_locked(self):
        self.assertFalse(man.hashes_locked({"models": [{"sha256": ""}]}))
        self.assertFalse(man.hashes_locked({"models": [{}]}))

    def test_malformed_digest_is_not_locked(self):
        self.assertFalse(man.hashes_locked({"models": [{"sha256": "abc123"}]}))   # too short
        self.assertFalse(man.hashes_locked({"models": [{"sha256": "z" * 64}]}))   # 64 chars, not hex


class VerifyShaTests(unittest.TestCase):
    def test_verify_sha256_true_on_match(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "f.bin")
            data = b"hello-model"
            open(p, "wb").write(data)
            self.assertTrue(man.verify_sha256(p, hashlib.sha256(data).hexdigest()))

    def test_verify_sha256_false_on_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "f.bin")
            open(p, "wb").write(b"hello-model")
            self.assertFalse(man.verify_sha256(p, "0" * 64))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run → FAIL.**
Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1a_manifest -v`

- [ ] **Step 3: Implement.** Create `manifest.json`. The sha256 ships as the sentinel `"PENDING_LOCK"` — we do NOT invent a hash we have not seen from a real download. The two-phase `setup_models.sh` (Task 5) computes the real hashes (`lock-hashes`), they get committed, and only then does `build` verify-and-compile. The host schema test checks the *fields exist*; `hashes_locked()` is the host-witnessed gate that proves no build is allowed while any hash is still `PENDING_LOCK`:

```json
{
  "schema": "jetson_b1a_models.v0",
  "models": [
    {
      "name": "scrfd_500m",
      "source_url": "https://github.com/deepinsight/insightface/releases/download/v0.7/scrfd_500m.onnx",
      "sha256": "PENDING_LOCK",
      "license": "MIT (InsightFace)",
      "input_shape": [1, 3, 640, 640],
      "precision": "fp32",
      "engine_path": "models/scrfd_500m.fp32.engine"
    },
    {
      "name": "arcface_w600k_r50",
      "source_url": "https://github.com/deepinsight/insightface/releases/download/v0.7/w600k_r50.onnx",
      "sha256": "PENDING_LOCK",
      "license": "MIT (InsightFace)",
      "input_shape": [1, 3, 112, 112],
      "precision": "fp32",
      "engine_path": "models/arcface_w600k_r50.fp32.engine"
    }
  ]
}
```

```python
# devices/jetson_presence/jetson_presence/b1a/manifest.py
"""Load + integrity-verify the tracked model manifest. The .onnx/.engine artifacts
themselves are gitignored, Jetson-local; this code + the JSON are the repo truth."""
from __future__ import annotations

import hashlib
import json
import os
import re

PENDING = "PENDING_LOCK"  # sentinel: no real hash pinned yet -> build must refuse
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

_DEFAULT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "models", "manifest.json")
)


def load_manifest(path: str = _DEFAULT) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def hashes_locked(manifest: dict) -> bool:
    """True only when every model carries a real-looking pinned digest: a 64-char
    lowercase hex sha256 (not empty, not the PENDING sentinel, not a malformed value).
    The two-phase setup refuses to build any engine while this is False."""
    models = manifest.get("models", [])
    if not models:
        return False
    return all(_SHA256_HEX.match((m.get("sha256") or "").lower()) for m in models)


def verify_sha256(file_path: str, expected_hex: str) -> bool:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest() == expected_hex.lower()
```

- [ ] **Step 4: Run → PASS.** The shipped `sha256: "PENDING_LOCK"` is correct-by-design: the schema test checks fields exist; `verify_sha256` is tested on synthetic files; `hashes_locked()` proves the unlocked manifest cannot pass the build gate. Real hashes are computed by `lock-hashes` on the device, then committed.
- [ ] **Step 5: Commit**

**Gitignore note (folded into THIS task):** the repo root `.gitignore` has an unanchored `models/` rule that prunes `devices/jetson_presence/models/` — so the tracked manifest would be silently ignored. This task's commit must also append to `devices/jetson_presence/.gitignore` a re-include block (verified with `git check-ignore`):

```gitignore
# B1a models: root .gitignore ignores any `models/`, which would also hide this
# device's TRACKED manifest. Re-include the dir, keep heavy artifacts Jetson-local:
!models/
models/*.onnx
models/*.engine
models/*.plan
models/*.npz
models/*.npy
```

```bash
git add devices/jetson_presence/models/manifest.json devices/jetson_presence/jetson_presence/b1a/manifest.py tests/test_jetson_b1a_manifest.py devices/jetson_presence/.gitignore
git commit -m "feat(jetson-b1a): model manifest + sha256 verify + hash-lock gate (manifest tracked, artifacts gitignored)"
```

---

## Task 4: structural guards — no-POST + no-crop-write over `b1a/` (host-TDD)

**Files:** Create `tests/test_jetson_b1a_no_post.py`, `tests/test_jetson_b1a_no_crop_write.py`

- [ ] **Step 1: Write both guards**

```python
# tests/test_jetson_b1a_no_post.py
# Structural, AST-based: b1a/ is local-only BY CONSTRUCTION. We assert on the parsed
# import graph (not blunt substrings), plus exact host token/url literals.
import ast
import os
import unittest

_B1A = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "devices", "jetson_presence", "jetson_presence", "b1a"))

# Modules b1a must never import: network stacks + B0 live-path modules.
_FORBIDDEN_IMPORTS = {
    "requests", "urllib", "urllib.request", "http", "http.client",
    "jetson_presence.emitter", "jetson_presence.config",
    "emitter", "config",  # relative `from . import emitter/config`
}
# Exact host token/url identifiers that must never appear as literals.
_FORBIDDEN_LITERALS = (
    "X-Maez-Jetson-Token", "/api/v1/presence", "MAEZ_JETSON_DEVICE_TOKEN",
)


def _imported_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name)
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if base:
                names.add(base)
                names.add(base.split(".")[0])
            for a in node.names:  # `from . import config` / `from jetson_presence import emitter`
                names.add(a.name)
                if base:
                    names.add(f"{base}.{a.name}")
    return names


class NoPostStructuralTests(unittest.TestCase):
    def test_b1a_imports_no_network_or_b0_live_modules(self):
        offenders = []
        for name in os.listdir(_B1A):
            if not name.endswith(".py"):
                continue
            src = open(os.path.join(_B1A, name), encoding="utf-8").read()
            imported = _imported_names(ast.parse(src, filename=name))
            for bad in _FORBIDDEN_IMPORTS & imported:
                offenders.append(f"{name}: imports {bad}")
        self.assertEqual(offenders, [], f"b1a is local-only by construction; found: {offenders}")

    def test_b1a_names_no_host_token_or_url(self):
        offenders = []
        for name in os.listdir(_B1A):
            if not name.endswith(".py"):
                continue
            src = open(os.path.join(_B1A, name), encoding="utf-8").read()
            for lit in _FORBIDDEN_LITERALS:
                if lit in src:
                    offenders.append(f"{name}: {lit}")
        self.assertEqual(offenders, [], f"b1a must not name host token/url: {offenders}")


if __name__ == "__main__":
    unittest.main()
```

```python
# tests/test_jetson_b1a_no_crop_write.py
# Frames AND crops are RAM-only. This matches B0's hardened guard
# (tests/test_jetson_edge_no_frame_write.py) token-for-token, extended to crops.
import os
import unittest

_B1A = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "devices", "jetson_presence", "jetson_presence", "b1a"))

_FORBIDDEN_WRITE = (
    "imwrite", "VideoWriter", "imencode", "write_bytes", ".tofile(", ".save(",
    "'wb'", '"wb"', "'w+b'", '"w+b"', "'wb+'", '"wb+"',
    "'r+'", '"r+"', "'r+b'", '"r+b"', "'rb+'", '"rb+"',
    "'ab'", '"ab"', "'a+b'", '"a+b"', "'ab+'", '"ab+"',
)


class NoCropWriteStructuralTests(unittest.TestCase):
    def test_b1a_writes_no_frames_or_crops(self):
        offenders = []
        for name in os.listdir(_B1A):
            if not name.endswith(".py"):
                continue
            src = open(os.path.join(_B1A, name), encoding="utf-8").read()
            for tok in _FORBIDDEN_WRITE:
                if tok in src:
                    offenders.append(f"{name}: {tok}")
        self.assertEqual(offenders, [], f"frames/crops are RAM-only; found: {offenders}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run → PASS now** (only `matcher.py`/`parity.py`/`manifest.py` exist, all clean). These guards stay green as the device files are added in Tasks 6–7; if a device task introduces a forbidden import/token, the guard goes RED and that file must be fixed. **There is no escape hatch:** `run_parity` returns its pass/fail in RAM (no `.npy` dumped anywhere), and `b1a/` writes zero image bytes by any open-mode. The `*.npy/*.npz` gitignore entries (Task 5) are defensive only — nothing in `b1a/` writes them.
Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1a_no_post tests.test_jetson_b1a_no_crop_write -v`
- [ ] **Step 3: Commit**

```bash
git add tests/test_jetson_b1a_no_post.py tests/test_jetson_b1a_no_crop_write.py
git commit -m "test(jetson-b1a): structural no-POST + no-crop-write guards over b1a/"
```

---

## Task 5: deploy path + `.gitignore` + two-phase `setup_models.sh`

**Files:** Modify `devices/jetson_presence/deploy.sh`, `devices/jetson_presence/.gitignore`; Create `devices/jetson_presence/setup_models.sh`

- [ ] **Step 1: Patch `deploy.sh` to also ship `setup_models.sh` + the tracked manifest.**
The current rsync (`deploy.sh:15-26`) allowlists `*.py` under `jetson_presence/` only — it would NOT copy `setup_models.sh` or `models/manifest.json`, and the device witnesses (setup → build) depend on both. Add a second rsync **after** the existing one (before the final `echo`s), with an allowlist that copies exactly those two and excludes every artifact:

```bash
# B1a: also deploy the model setup script + the TRACKED manifest (never the artifacts).
# The trailing `--exclude '*'` means ONLY the allowlisted paths cross; *.onnx/*.engine
# never match an --include, so they are structurally excluded.
rsync -av \
  --include 'setup_models.sh' \
  --include 'models/' \
  --include 'models/manifest.json' \
  --exclude '*' \
  "$HERE/" "$JETSON:$DEST/"
echo "Deployed setup_models.sh + models/manifest.json (artifacts excluded by allowlist)."
```

- [ ] **Step 2: `.gitignore` — already done in Task 3.** The artifact globs + the `!models/` re-include (so the tracked manifest survives the root `models/` prune) landed with the manifest commit. Nothing to add here; just confirm `git check-ignore devices/jetson_presence/models/scrfd_500m.onnx` reports ignored and `...manifest.json` does not.

- [ ] **Step 3: Write the two-phase `setup_models.sh`** (beside `deploy.sh`). **`lock-hashes` downloads + computes + records hashes and EXITS without compiling; `build` refuses unless every hash is locked, verifies each ONNX against its pinned hash, then compiles.** No engine is ever built from an unverified download (no TOFU):

```bash
# devices/jetson_presence/setup_models.sh
#!/usr/bin/env bash
# Two-phase, manifest-pinned model setup. Runs ON THE JETSON. Artifacts stay
# device-local (gitignored). Usage:
#   setup_models.sh deps         # install onnx/onnxruntime/pycuda/numpy
#   setup_models.sh lock-hashes  # download ONNX, compute sha256, write manifest, EXIT (no build)
#   setup_models.sh build        # REFUSE unless locked; verify each sha; THEN trtexec-compile
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS="$HERE/models"
PY="${PYTHON:-python3}"
# b1a/ helpers are importable from the deployed package root:
export PYTHONPATH="$HERE:${PYTHONPATH:-}"
export MODELS_DIR="$MODELS"
export TRTEXEC="${TRTEXEC:-/usr/src/tensorrt/bin/trtexec}"

cmd_deps() {
  echo "== ensure pip + inference deps =="
  "$PY" -m ensurepip --upgrade 2>/dev/null || true
  "$PY" -m pip install --user --upgrade onnx onnxruntime pycuda numpy 2>&1 | tail -2
}

# Phase 1: download each manifest model, compute its sha256, write it back. NO build.
cmd_lock_hashes() {
  echo "== download ONNX + compute sha256 (NO build) =="
  "$PY" - <<'PYEOF'
import hashlib
import json
import os
import urllib.request

mdir = os.environ["MODELS_DIR"]
mpath = os.path.join(mdir, "manifest.json")
with open(mpath, encoding="utf-8") as f:
    manifest = json.load(f)

for entry in manifest["models"]:
    onnx = os.path.join(mdir, entry["name"] + ".onnx")
    print(f"downloading {entry['name']} <- {entry['source_url']}")
    urllib.request.urlretrieve(entry["source_url"], onnx)
    h = hashlib.sha256()
    with open(onnx, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    entry["sha256"] = h.hexdigest()
    print(f"  sha256={entry['sha256']}")

with open(mpath, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
    f.write("\n")
print("manifest.json updated.")
PYEOF
  echo ">> Review the diff to models/manifest.json, then COMMIT the real hashes before 'build'."
}

# Phase 2: refuse unless locked, verify every sha, THEN trtexec-compile. No unverified engine.
cmd_build() {
  echo "== gate + verify + compile =="
  "$PY" - <<'PYEOF'
import os
import subprocess
import sys

from jetson_presence.b1a import manifest as man

mdir = os.environ["MODELS_DIR"]
trtexec = os.environ["TRTEXEC"]
manifest = man.load_manifest()

if not man.hashes_locked(manifest):
    sys.exit("REFUSING build: manifest still has unlocked hashes. Run lock-hashes + commit first.")

for entry in manifest["models"]:
    onnx = os.path.join(mdir, entry["name"] + ".onnx")
    if not man.verify_sha256(onnx, entry["sha256"]):
        sys.exit(f"REFUSING build: sha256 mismatch for {entry['name']}")
    print(f"verified {entry['name']}")

for entry in manifest["models"]:
    onnx = os.path.join(mdir, entry["name"] + ".onnx")
    engine = os.path.join(mdir, os.path.basename(entry["engine_path"]))
    cmd = [trtexec, f"--onnx={onnx}", f"--saveEngine={engine}"]
    if entry["precision"] == "fp16":
        cmd.append("--fp16")  # explicit; an FP16 parity miss is a real result, not an override
    print("building:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"  -> {engine}")

print("all engines built")
PYEOF
  echo "Done. Engines in $MODELS (gitignored). Run parity + spike to witness."
}

case "${1:-}" in
  deps) cmd_deps ;;
  lock-hashes) cmd_lock_hashes ;;
  build) cmd_build ;;
  *) echo "usage: setup_models.sh {deps|lock-hashes|build}" >&2; exit 2 ;;
esac
```

- [ ] **Step 4: Syntax-check both scripts (no device run here)**

Run: `bash -n devices/jetson_presence/deploy.sh devices/jetson_presence/setup_models.sh && echo "scripts syntax OK"`

- [ ] **Step 5: Commit**

```bash
git add devices/jetson_presence/deploy.sh devices/jetson_presence/setup_models.sh
git commit -m "feat(jetson-b1a): deploy manifest+setup, two-phase lock-hashes/build"
```

> **DEVICE-BUILD NOTE (Tasks 6–7):** the remaining files contain **TensorRT inference internals that depend on the real model output layout** and cannot be honestly pre-written blind. They are implemented **on the device against the pulled models**, using the InsightFace ONNX models as the decode reference. The plan fixes their *interfaces*, their *covenant constraints*, and their *device witnesses*; the implementer writes the bodies with the models in front of them and keeps the structural guards (Task 4) green.

---

## Task 6: `detector.py` + `embedding.py` (device inference; build-time internals)

**Files:** Create `b1a/detector.py`, `b1a/embedding.py`

**Interfaces to implement (bodies build-time on device):**
- `detector.py`: `class Detector` — `__init__(engine_path)` (lazy `import tensorrt`/binding); `detect(frame) -> list[(box, score)]` running TRT inference **then the shared SCRFD decode + NMS** (parity compares *post-decode*, per Codex). Expose the decode as `decode_scrfd(raw_outputs, input_shape) -> list[(box, score)]` so the same decode applies to ONNX and TRT outputs.
- `embedding.py`: `class Embedder` — `__init__(engine_path)`; `embed(face_crop_112x112) -> list[float]` (L2-normalized identity vector).

**Constraints:** lazy imports (host can import the module without TensorRT for the structural guards); **no frame/crop write** (guards from Task 4 stay green); no network; crops are NumPy arrays in RAM only.

- [ ] **Step 1:** implement the wrappers + the shared `decode_scrfd` on the device against the real SCRFD/ArcFace ONNX (use InsightFace's reference decode for correctness).
- [ ] **Step 2:** confirm the host structural guards still pass:
Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_b1a_no_post tests.test_jetson_b1a_no_crop_write -v` → PASS (lazy imports keep them host-importable; no forbidden tokens).
- [ ] **Step 3: Commit** `feat(jetson-b1a): SCRFD detector + ArcFace embedding TRT wrappers (lazy, no write)`

---

## Task 7: `run_parity` + `spike.py` (device; build-time internals)

**Files:** Modify `b1a/parity.py` (add `run_parity`); Create `b1a/spike.py`

**`run_parity(onnx_ref, trt_detector, trt_embedder, frame)`** (device): run the ONNX reference and the TRT engines on the **same in-RAM frame**, apply the **same decode**, then call the *pure* `box_parity` / `embedding_parity`. Return a structured pass/fail per model.

**`spike.py`** (CLI-only — `argparse`, NO `config.py` import, NO network): `--frames N`, `--device-index 0`. Flow: V4L2 capture → `Detector.detect` → crop most-confident face (RAM) → `Embedder.embed` → compare to the **RAM-only owner reference** captured at start → **print** `match? / distance / per-stage latency ms`. **RAM-only, no persistence: the reference embedding is captured at process start, held in memory, and discarded on exit. B1a does NOT implement `--keep-reference`** — persisting a biometric vector is the durable-enrollment concern, deferred to B1b's owner-gated ceremony. This honors spec R2's RAM-only default and keeps the no-write guard (Task 4) absolute (B0-strength). Never writes a frame/crop/embedding; never POSTs.

- [ ] **Step 1:** implement on device; keep structural guards green.
- [ ] **Step 2:** host guards still pass (Task 4 suites GREEN).
- [ ] **Step 3: Commit** `feat(jetson-b1a): run_parity + CLI-only spike harness (RAM-only ref, no emit)`

---

## Task 8: host regression + STOP at review gate

- [ ] **Step 1: Full b1a host suite**
Run:
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_jetson_b1a_matcher tests.test_jetson_b1a_parity tests.test_jetson_b1a_manifest \
  tests.test_jetson_b1a_no_post tests.test_jetson_b1a_no_crop_write -v
```
Expected: all PASS (matcher, parity metrics, manifest, both structural guards).
- [ ] **Step 2: Ruff** on `b1a/` + the b1a tests → `All checks passed!`
- [ ] **Step 3: `git diff --check`** clean; scope under `devices/jetson_presence/` + `tests/test_jetson_b1a_*`.
- [ ] **Step 4: STOP.** Do NOT deploy/run on device during the build. Hand to **Codex cross-lane**. The device witnesses below are the owner's.

---

## On-device witnesses (owner-run, after review/merge — NOT part of the host build)

1. **Deploy:** `bash devices/jetson_presence/deploy.sh` → confirm `setup_models.sh` **and** `models/manifest.json` arrive on the Jetson, and **no** `.onnx/.engine` artifact does (allowlist holds).
2. **Deps + lock-hashes (one-time):** `setup_models.sh deps`, then `setup_models.sh lock-hashes` → downloads ONNX, computes the real sha256, writes them into `manifest.json`. **Review the diff, commit the real hashes.** No engine built yet.
3. **Build (gated):** `setup_models.sh build` → first proves `hashes_locked` (refuses on any `PENDING_LOCK`), verifies each ONNX against its pinned sha (refuses on mismatch), then `trtexec`-compiles **FP32** engines. Confirm a tampered/unlocked manifest is *refused* (negative witness).
4. **Parity (R4):** run `run_parity` on a blank frame (→ no detection) and an owner frame (→ detection) → **box IoU > 0.99 & |score| < 0.01, embedding cosine > 0.999**. A miss on an FP16 engine is a real result, not an override.
5. **Spike:** `python3 -m jetson_presence.b1a.spike --frames 30`:
   - owner present → `match` (distance below threshold);
   - empty/covered → no-match / no detection;
   - per-stage + total **latency** printed (validates SCRFD+ArcFace, or signals MobileFaceNet fallback).
6. **Privacy witness:** clear `__pycache__`, run with `PYTHONDONTWRITEBYTECODE=1`, confirm **no `.jpg/.png/.npy` frame, crop, or embedding written** (B1a has no `--keep-reference`); the reference embedding lived in RAM only and is gone on exit.

---

## Self-Review

**Spec coverage:** SCRFD+ArcFace ONNX→TensorRT (Tasks 5–7, device); distinguishes owner-vs-empty (spike witness #5); latency (witness #5); **no live non-owner** (only owner/empty + random-vector matcher tests, Task 1); **RAM-only reference** (no `--keep-reference` in B1a; witness #6); **manifest** sha/license/precision (Tasks 3, 5); **engine parity post-decode** (Tasks 2, 6, 7, witness #4); **no frame/crop write** (Task 4 full-token guard + witness #6); **structural no-POST** (Task 4 AST guard); precision explicit FP32-first (Task 3 manifest). ✓

**Four-seam patch (Codex hold):** (1) `deploy.sh` now ships `setup_models.sh` + `models/manifest.json` via a second allowlisted rsync, artifacts excluded (Task 5 Step 1; witness #1). (2) No TOFU: two-phase `lock-hashes`→commit→`build`, with a host-witnessed `hashes_locked()` gate (requires a real-looking 64-char hex digest, not just non-empty) and a device refuse-if-unlocked + verify-each-sha gate. `setup_models.sh` is **concrete** — `lock-hashes` downloads+hashes+rewrites the manifest, `build` gates+verifies+`trtexec`-compiles per precision — not placeholder comments (Tasks 3, 5; witness #2–3; bash+python syntax validated). (3) No-crop-write guard restored to B0's full write-mode token set; the `.npy`-outside-`b1a/` escape hatch removed (`run_parity` is RAM-only); `--keep-reference` dropped from B1a (Task 4, Task 7). (4) No-POST guard is now AST import analysis + exact host-literal scan, not a blunt `"config"` substring (Task 4).

**Placeholder scan:** host-TDD tasks (1–4) are complete RED-first code. Tasks 6–7 are *intentionally interface+witness* (device-only inference internals written against real models) — flagged as the honest shape of a hardware spike, not a TODO. `sha256: "PENDING_LOCK"` is a correct-by-design sentinel gated by `hashes_locked()`, not a vague placeholder.

**Type consistency:** `cosine_distance`/`is_match(distance,*,threshold)`; `iou`/`box_parity(onnx_box,onnx_score,trt_box,trt_score)`/`embedding_parity(onnx_vec,trt_vec)`; `load_manifest(path)`/`hashes_locked(manifest)`/`verify_sha256(file_path,expected_hex)`; `PENDING`; `Detector.detect`/`decode_scrfd`; `Embedder.embed`; `run_parity` — consistent across tasks.
