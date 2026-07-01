# Jetson Face-Facts v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** The Jetson eye emits per-frame face **geometry** (`jetson_face_facts.v0`), and a new host intake validates → writes a content-light receipt → **drops** it. No identity conclusion, no present/absent verdict, no durable store, no behavior. Brain-side meaning is a separate birth-gated slice.

**Architecture:** Mirror the witnessed Slice-A presence intake, with two differences: (1) a richer per-frame contract carrying a `faces` list of embeddings; (2) the intake **drops** the payload (no store) because durable retention is birth-gated. The edge reuses the B1a detector/embedder to produce facts.

**Tech Stack:** Python 3.10; host tests `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest); Flask host `skills/web_interface.py`; lazy TensorRT/cv2 on the edge; existing `_jetson_device_auth_ok()` + `X-Maez-Jetson-Token` + `MAEZ_JETSON_DEVICE_TOKEN`.

**Spec:** `docs/superpowers/specs/2026-07-01-jetson-face-facts-v1-design.md` (@cccd2b5).

**Load-bearing line (from the spec):** *Face-facts are internal perceptual facts, not conclusions; Maez may retain and forget them only through its ordinary salience, coherence, immune, and lived-memory machinery.* The eye reports **detections**, never absence.

---

## File Structure

Create:

| Path | Responsibility |
| --- | --- |
| `core/body/jetson_face_facts.py` | Pure `jetson_face_facts.v0` contract validator (strict key-set, frame + face level, cross-field consistency). No I/O. |
| `devices/jetson_presence/jetson_presence/face_facts.py` | Pure packet builder (detections+embeddings → the contract dict). Edge emit + run mode reuse it. |
| `tests/test_jetson_face_facts_contract.py` | Contract validator tests. |
| `tests/test_jetson_face_facts_packet.py` | Pure packet-builder tests. |
| `tests/test_jetson_face_facts_intake.py` | Host intake endpoint tests (mirror `tests/test_jetson_presence_intake.py` harness). |
| `tests/test_jetson_face_facts_guards.py` | Structural guards: no durable store, no absence wording, no consumer, no edge identity/track store. |

Modify:

| Path | Change |
| --- | --- |
| `skills/web_interface.py` | Add `POST /api/v1/perception/jetson/face_facts`: flag-gate → auth → validate → content-light receipt → **drop**. No store. No consumer. |
| `devices/jetson_presence/jetson_presence/run.py` | Add a `--face-facts` bounded run mode (edge emit loop). Default B0 unchanged. |
| `devices/jetson_presence/jetson_presence/config.py` | Add the face-facts intake path + flag/enable field (env override). |

Do **not** modify: `core/body/jetson_presence.py` or the presence intake (mark vestigial, don't retire). No daemon, prompt, heartbeat, cockpit, or any Maez behavior consumer.

---

## Task 1: `jetson_face_facts.v0` contract validator (host-TDD)

**Files:** Create `core/body/jetson_face_facts.py`, `tests/test_jetson_face_facts_contract.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_jetson_face_facts_contract.py
import unittest

from core.body.jetson_face_facts import (
    EMBEDDING_DIM,
    SCHEMA_VERSION,
    face_count,
    parse_face_facts,
)


def _face(**over):
    f = {"embedding": [0.0] * EMBEDDING_DIM, "det_score": 0.98, "box": [1, 2, 3, 4], "track_id": None}
    f.update(over)
    return f


def _frame(**over):
    p = {
        "schema_version": SCHEMA_VERSION,
        "model_id": "buffalo_s/scrfd_500m+w600k_mbf",
        "sensor_state": "available",
        "frame_quality": "good",
        "ts": "2026-07-01T12:00:00Z",
        "faces": [_face()],
    }
    p.update(over)
    return p


class ContractTests(unittest.TestCase):
    def test_valid_frame_with_face_parses(self):
        self.assertIsNotNone(parse_face_facts(_frame()))

    def test_zero_detections_is_valid(self):
        # "detector found zero faces this frame" — a fact about detections, NOT absence.
        self.assertIsNotNone(parse_face_facts(_frame(faces=[])))

    def test_curtained_and_error_must_have_empty_faces(self):
        self.assertIsNotNone(parse_face_facts(_frame(sensor_state="curtained", faces=[])))
        self.assertIsNotNone(parse_face_facts(_frame(sensor_state="error", faces=[])))
        self.assertIsNone(parse_face_facts(_frame(sensor_state="curtained", faces=[_face()])))

    def test_extra_frame_key_rejected(self):
        self.assertIsNone(parse_face_facts({**_frame(), "room_occupancy": 1}))

    def test_extra_face_key_rejected(self):
        self.assertIsNone(parse_face_facts(_frame(faces=[_face(name="rohit")])))

    def test_missing_model_id_rejected(self):
        bad = _frame(); del bad["model_id"]
        self.assertIsNone(parse_face_facts(bad))

    def test_unknown_schema_version_rejected(self):
        self.assertIsNone(parse_face_facts(_frame(schema_version="jetson_face_facts.v9")))

    def test_bad_enum_rejected(self):
        self.assertIsNone(parse_face_facts(_frame(sensor_state="present")))
        self.assertIsNone(parse_face_facts(_frame(frame_quality="great")))

    def test_wrong_embedding_dim_rejected(self):
        self.assertIsNone(parse_face_facts(_frame(faces=[_face(embedding=[0.0] * 10)])))

    def test_bad_box_rejected(self):
        self.assertIsNone(parse_face_facts(_frame(faces=[_face(box=[1, 2, 3])])))

    def test_track_id_null_or_str_only(self):
        self.assertIsNotNone(parse_face_facts(_frame(faces=[_face(track_id="t7")])))
        self.assertIsNone(parse_face_facts(_frame(faces=[_face(track_id=7)])))

    def test_face_count_helper(self):
        self.assertEqual(face_count(_frame(faces=[_face(), _face()])), 2)
        self.assertEqual(face_count(_frame(faces=[])), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run → FAIL** (`ModuleNotFoundError`).
Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_face_facts_contract -v`

- [ ] **Step 3: Implement**

```python
# core/body/jetson_face_facts.py
"""jetson_face_facts.v0 contract: pure per-frame face-geometry validation.

No I/O. The Jetson eye emits perceptual FACTS (detections + embeddings), never
conclusions. `faces: []` means "the detector found zero faces in this frame" — a fact
about detections, NOT "no one is here." Absence is a brain inference over many facts,
never an eye claim. This module is the single place that decides a packet is well-formed.
"""
from __future__ import annotations

SCHEMA_VERSION = "jetson_face_facts.v0"
EMBEDDING_DIM = 512

_SENSOR_STATES = frozenset({"available", "curtained", "error"})
_FRAME_QUALITIES = frozenset({"good", "low", "unknown"})
_ALLOWED_FRAME_KEYS = frozenset(
    {"schema_version", "model_id", "sensor_state", "frame_quality", "ts", "faces"}
)
_ALLOWED_FACE_KEYS = frozenset({"embedding", "det_score", "box", "track_id"})

_Number = (int, float)


def _valid_face(face: object) -> bool:
    if not isinstance(face, dict) or set(face.keys()) != _ALLOWED_FACE_KEYS:
        return False
    emb = face["embedding"]
    if not isinstance(emb, list) or len(emb) != EMBEDDING_DIM:
        return False
    if not all(isinstance(x, _Number) and not isinstance(x, bool) for x in emb):
        return False
    if not isinstance(face["det_score"], _Number) or isinstance(face["det_score"], bool):
        return False
    box = face["box"]
    if not isinstance(box, list) or len(box) != 4:
        return False
    if not all(isinstance(v, _Number) and not isinstance(v, bool) for v in box):
        return False
    tid = face["track_id"]
    if tid is not None and not isinstance(tid, str):
        return False
    return True


def parse_face_facts(raw: object) -> dict | None:
    """Validate a raw payload into the contract dict, or None if malformed."""
    if not isinstance(raw, dict) or set(raw.keys()) != _ALLOWED_FRAME_KEYS:
        return None
    if raw.get("schema_version") != SCHEMA_VERSION:
        return None
    if not isinstance(raw.get("model_id"), str) or not raw["model_id"].strip():
        return None
    if raw.get("sensor_state") not in _SENSOR_STATES:
        return None
    if raw.get("frame_quality") not in _FRAME_QUALITIES:
        return None
    ts = raw.get("ts")
    if not isinstance(ts, str) or not ts.strip():
        return None
    faces = raw.get("faces")
    if not isinstance(faces, list):
        return None
    if not all(_valid_face(f) for f in faces):
        return None
    # Cross-field consistency: the eye can only report detected faces when it was
    # actually looking. curtained/error means it wasn't/couldn't -> no faces.
    if raw["sensor_state"] != "available" and faces:
        return None
    return raw


def face_count(reading: dict) -> int:
    """Number of detected faces this frame. NOT a presence/absence verdict."""
    return len(reading.get("faces", []))
```

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(face-facts): jetson_face_facts.v0 contract validator (strict, geometry-only)`

---

## Task 2: host intake — validate → content-light receipt → drop (host-TDD)

**Files:** Modify `skills/web_interface.py`; Create `tests/test_jetson_face_facts_intake.py` (mirror the fixture harness of `tests/test_jetson_presence_intake.py` — Flask test client, flag env, `X-Maez-Jetson-Token`, `get_secret` patching)

- [ ] **Step 1: Write the failing tests** — mirror `tests/test_jetson_presence_intake.py`'s client/flag/token setup, asserting the face-facts endpoint. Cases (use that file's exact auth/flag fixture approach):
  - flag off (`MAEZ_JETSON_FACE_FACTS_SHADOW` unset) → **404**.
  - flag on, no / wrong `X-Maez-Jetson-Token` → **401**.
  - flag on, valid token, extra frame key (e.g. `room_occupancy`) → **400**.
  - flag on, valid token, well-formed 1-face packet → **200** `{"ok": true, ...}`.
  - flag on, valid token, `faces: []` available/good → **200**, and the logged receipt shows `face_count=0`.
  - **Receipt is content-light:** capture the log record; assert it contains `model_id`/`sensor_state`/`frame_quality`/`face_count` and does **NOT** contain any embedding float value, nor the substrings `owner_absent`/`room_empty`/`no_one_here`.
  - **No store:** assert no durable face-facts store object/file is created (there is no `_JETSON_FACE_FACTS_STORE`; the payload is dropped).

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_face_facts_intake -v` → FAIL (route missing).

- [ ] **Step 2: Add the enable flag** to `core/body/jetson_face_facts.py`:

```python
def jetson_face_facts_shadow_enabled() -> bool:
    """Default-off shadow flag. Off = the endpoint behaves as if it does not exist."""
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_JETSON_FACE_FACTS_SHADOW")
```

- [ ] **Step 3: Implement the endpoint** in `skills/web_interface.py`, mirroring `api_jetson_presence_intake` (near it). NOTE the differences: new contract, **no store (drop)**, new content-light receipt, new flag. Reuse the existing `_jetson_device_auth_ok()`.

```python
from core.body.jetson_face_facts import (
    face_count,
    jetson_face_facts_shadow_enabled,
    parse_face_facts,
)


def _jetson_write_face_facts_receipt(reading, *, received_at: float) -> None:
    """Content-light receipt = a single log line. No embedding values, no absence verdict.

    face_count is a count of DETECTIONS this frame, never owner_absent/room_empty/no_one_here.
    No persistent file, no store: the payload is dropped after this line. Durable retention
    is birth-gated, through Maez's own salience/lived-memory machinery, not here.
    """
    n = face_count(reading)
    # Content-light sha: model/state/quality/count/ts only — NEVER the embeddings.
    summary = f"{reading['model_id']}|{reading['sensor_state']}|{reading['frame_quality']}|{n}|{reading['ts']}".encode()
    logger.info(
        "jetson_face_facts_intake schema=%s model_id=%s sensor_state=%s frame_quality=%s face_count=%d content_sha=%s received_at=%.3f",
        "jetson_face_facts.v0",
        reading["model_id"],
        reading["sensor_state"],
        reading["frame_quality"],
        n,
        hashlib.sha256(summary).hexdigest()[:16],
        received_at,
    )


@app.route("/api/v1/perception/jetson/face_facts", methods=["POST"])
def api_jetson_face_facts_intake():
    # Behaviorally unavailable when off: behaves as if the endpoint does not exist.
    if not jetson_face_facts_shadow_enabled():
        return jsonify({"ok": False, "error": "not found"}), 404
    if not _jetson_device_auth_ok():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    reading = parse_face_facts(body)
    if reading is None:
        return jsonify({"ok": False, "error": "invalid face_facts"}), 400
    received_at = time.time()
    # v1: validate -> content-light receipt -> DROP. No store; retention is birth-gated.
    _jetson_write_face_facts_receipt(reading, received_at=received_at)
    return jsonify({"ok": True, "received_at": received_at, "face_count": face_count(reading)})
```

- [ ] **Step 4: Run → PASS.** Also run `tests.test_jetson_presence_intake` to confirm the presence intake is untouched.
- [ ] **Step 5: Commit** `feat(face-facts): host intake — validate, content-light receipt, drop (no store)`

---

## Task 3: edge packet-builder (pure, host-TDD)

**Files:** Create `devices/jetson_presence/jetson_presence/face_facts.py`, `tests/test_jetson_face_facts_packet.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_jetson_face_facts_packet.py
import unittest

import tests._jetson_edge_path  # noqa: F401
from core.body.jetson_face_facts import parse_face_facts
from jetson_presence import face_facts


class PacketBuildTests(unittest.TestCase):
    def _one(self):
        return face_facts.build_packet(
            model_id="buffalo_s/scrfd_500m+w600k_mbf",
            sensor_state="available",
            frame_quality="good",
            ts="2026-07-01T12:00:00Z",
            faces=[([0.0] * 512, 0.98, [1, 2, 3, 4], "t1")],
        )

    def test_built_packet_passes_the_host_contract(self):
        self.assertIsNotNone(parse_face_facts(self._one()))

    def test_zero_faces_packet_is_valid(self):
        pkt = face_facts.build_packet(
            model_id="m", sensor_state="available", frame_quality="good",
            ts="T", faces=[],
        )
        self.assertEqual(pkt["faces"], [])
        self.assertIsNotNone(parse_face_facts({**pkt, "model_id": "buffalo_s/scrfd_500m+w600k_mbf"}))

    def test_curtained_forces_empty_faces(self):
        # a builder called curtained must not carry faces (contract would reject)
        pkt = face_facts.build_packet(
            model_id="m", sensor_state="curtained", frame_quality="unknown",
            ts="T", faces=[([0.0] * 512, 0.9, [1, 2, 3, 4], None)],
        )
        self.assertEqual(pkt["faces"], [])

    def test_track_id_optional_null(self):
        pkt = face_facts.build_packet(
            model_id="m", sensor_state="available", frame_quality="good",
            ts="T", faces=[([0.0] * 512, 0.9, [1, 2, 3, 4], None)],
        )
        self.assertIsNone(pkt["faces"][0]["track_id"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement**

```python
# devices/jetson_presence/jetson_presence/face_facts.py
"""Pure builder for jetson_face_facts.v0 packets + the edge emit target.

Geometry only. No identity, no absence verdict. The device run loop (run.py) captures,
detects, embeds, calls build_packet, posts, and forgets. This module holds the pure,
host-testable packet shape so the wire format is validated on the host.
"""
from __future__ import annotations

SCHEMA_VERSION = "jetson_face_facts.v0"


def build_packet(*, model_id, sensor_state, frame_quality, ts, faces):
    """faces: iterable of (embedding_list, det_score, box_list, track_id_or_None).

    When the eye was not looking (sensor_state != 'available'), faces are dropped:
    curtained/error carry an empty list, by construction.
    """
    if sensor_state != "available":
        face_dicts = []
    else:
        face_dicts = [
            {
                "embedding": [float(x) for x in emb],
                "det_score": float(score),
                "box": [float(v) for v in box],
                "track_id": (str(tid) if tid is not None else None),
            }
            for emb, score, box, tid in faces
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "model_id": model_id,
        "sensor_state": sensor_state,
        "frame_quality": frame_quality,
        "ts": ts,
        "faces": face_dicts,
    }
```

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(face-facts): pure edge packet-builder (contract-valid by construction)`

---

## Task 4: edge run mode `--face-facts` (device; build-time internals)

**Files:** Modify `devices/jetson_presence/jetson_presence/config.py`, `run.py`

Interface (bodies device-built, reusing B1a + B0; lazy cv2/TensorRT):
- `config.py`: add `face_facts_intake_path` (default `/api/v1/perception/jetson/face_facts`) + `face_facts_frames` (bounded) with env overrides, mirroring existing fields.
- `run.py`: add `--face-facts` bounded mode. Per frame: check curtain (curtained → build_packet(sensor_state="curtained", faces=[]) → post → continue); else capture → `frame_quality` → SCRFD detect → for each face ArcFace embed (RAM) → `build_packet(sensor_state="available", ...)` → post to the face-facts endpoint with `X-Maez-Jetson-Token` → **forget** (no state kept beyond an in-memory, restart-reset track counter). Default B0 path unchanged.

**Hard constraints (structural, guarded in Task 5):**
- **track_id is in-memory only, session-local, reset every run** — never persisted, never a file. Simplest v1: emit `track_id=None` (defer real tracking); if any smoothing is added it lives only in a local variable.
- No durable write of any embedding, crop, frame, or identity/track store on the edge.
- Emits ONLY to the face-facts endpoint; no other network.

- [ ] **Step 1:** implement on device; keep the structural guards (Task 5) green.
- [ ] **Step 2:** host guards + packet/contract suites still pass.
- [ ] **Step 3: Commit** `feat(face-facts): edge --face-facts bounded emit mode (reuses B1a, forgets each frame)`

---

## Task 5: structural guards (host-TDD, probe-proven)

**Files:** Create `tests/test_jetson_face_facts_guards.py`

- [ ] **Step 1: Write the guards** (probe-proven, like the b1a guards):

```python
# tests/test_jetson_face_facts_guards.py
import ast
import pathlib
import tempfile
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[1]
_EDGE = _REPO / "devices" / "jetson_presence" / "jetson_presence"
_CONTRACT = _REPO / "core" / "body" / "jetson_face_facts.py"
_WEB = _REPO / "skills" / "web_interface.py"

# The eye/intake must never encode an absence VERDICT. face_count is fine (a detection count).
_ABSENCE_TOKENS = ("owner_absent", "room_empty", "no_one_here", "nobody_present", "room_occupancy")
_WRITE_TOKENS = (
    "imwrite", "VideoWriter", "imencode", "write_bytes", ".tofile(", ".save(", "np.save",
    "'wb'", '"wb"', "'w+b'", '"w+b"', "'wb+'", '"wb+"', "'ab'", '"ab"', "'a+b'", '"a+b"',
)


def _face_facts_edge_sources():
    for name in ("face_facts.py",):
        p = _EDGE / name
        if p.exists():
            yield p


class NoAbsenceVerdictTests(unittest.TestCase):
    def test_contract_and_edge_name_no_absence_verdict(self):
        offenders = []
        srcs = [_CONTRACT] + list(_face_facts_edge_sources())
        for p in srcs:
            src = p.read_text(encoding="utf-8")
            for tok in _ABSENCE_TOKENS:
                if tok in src:
                    offenders.append(f"{p.name}: {tok}")
        self.assertEqual(offenders, [])

    def test_probe_would_trip(self):
        planted = "owner_present = 'owner_absent'\n"
        self.assertTrue(any(t in planted for t in _ABSENCE_TOKENS))


class NoEdgeDurableStoreTests(unittest.TestCase):
    def test_edge_face_facts_writes_no_embedding_track_or_frame(self):
        offenders = []
        for p in _face_facts_edge_sources():
            src = p.read_text(encoding="utf-8")
            for tok in _WRITE_TOKENS:
                if tok in src:
                    offenders.append(f"{p.name}: {tok}")
        self.assertEqual(offenders, [])

    def test_probe_write_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            probe = pathlib.Path(tmp) / "face_facts.py"
            probe.write_text("open(p, 'wb').write(embedding_bytes)\n", encoding="utf-8")
            src = probe.read_text(encoding="utf-8")
            self.assertTrue(any(t in src for t in _WRITE_TOKENS))


class NoConsumerTests(unittest.TestCase):
    def test_intake_receipt_fn_calls_no_behavior(self):
        # The face-facts receipt/handler must not reach into prompt/heartbeat/memory promotion.
        src = _WEB.read_text(encoding="utf-8")
        block = src[src.index("_jetson_write_face_facts_receipt"):]
        block = block[: block.index("@app.route", block.index("api_jetson_face_facts_intake"))]
        for bad in ("fresh_moment_receipts", "heartbeat", "promote", "record(", "prompt"):
            self.assertNotIn(bad, block, f"face-facts intake must not call {bad}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run → PASS** (contract + edge clean; probes demonstrate the guards catch violations).
Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_jetson_face_facts_guards -v`
- [ ] **Step 3: Commit** `test(face-facts): structural guards — no absence verdict / no edge store / no consumer`

---

## Task 6: host regression + device witness runbook + STOP

- [ ] **Step 1: Full face-facts + jetson regression host suite**
```bash
/home/rohit/maez/.venv/bin/python -B -W ignore::ResourceWarning -m unittest \
  tests.test_jetson_face_facts_contract tests.test_jetson_face_facts_packet \
  tests.test_jetson_face_facts_intake tests.test_jetson_face_facts_guards \
  tests.test_jetson_presence_intake tests.test_jetson_edge_no_frame_write -v
```
Expected: all PASS (presence intake untouched).
- [ ] **Step 2: Ruff** on the new files → `All checks passed!`
- [ ] **Step 3: `git diff --check`** clean; scope under `core/body/jetson_face_facts.py`, `devices/jetson_presence/`, `skills/web_interface.py`, `tests/test_jetson_face_facts_*`.
- [ ] **Step 4: STOP** at the review gate. Hand to Codex cross-lane. Device witnesses are the owner's.

---

## On-device witnesses (owner-run, after review/merge)

Host flag on: `MAEZ_JETSON_FACE_FACTS_SHADOW=1`, token provisioned. Deploy source-only; run on Jetson:

1. **Owner in view:** `python3 -m jetson_presence.run --face-facts --loops 1` → host receipt `jetson_face_facts_intake schema=jetson_face_facts.v0 model_id=... sensor_state=available frame_quality=good face_count=N ...` (N≥1), embedding never in the log.
2. **Covered / no-face frame** (lens covered or no face in view — a claim about **detections**, not the room): `face_count=0`, `sensor_state=available`, and the receipt shows no `owner_absent`/`room_empty`/`no_one_here`.
3. **Curtain:** `sensor_state=curtained`, `faces:[]`, camera released/reopenable.
4. **Fail-closed:** flag off → 404; bad/no token → 401; a packet with an extra key → 400.
5. **Privacy witness:** clear `__pycache__`, `PYTHONDONTWRITEBYTECODE=1` → no `.jpg/.png/.npy` frame/crop/embedding written on the edge; no durable face-facts store host-side; no `track_id` file.

---

## Self-Review

**Spec coverage:** new contract + strict validator (Task 1); intake validate→receipt→drop (Task 2); edge emitter reusing B1a (Tasks 3–4); guards for no-durable-store / no-absence-wording / no-consumer / no-edge-track-store (Task 5); device witness incl. covered/no-face→`faces:[]` at detector-output level (witness §2). `model_id` + `frame_quality` load-bearing (Task 1 required fields). Supersede-not-retire: presence intake untouched (Tasks 2, 6). ✓

**Placeholder scan:** host-testable tasks (1,2,3,5) are complete RED-first code; Task 4 is device-internals (interface + witness), honest for a hardware emit loop. Task 2's intake tests reference the witnessed presence-intake test harness for the Flask/flag/token fixture (an existing, proven pattern) rather than re-deriving it.

**Type consistency:** `parse_face_facts(raw)->dict|None`, `face_count(reading)->int`, `build_packet(*, model_id, sensor_state, frame_quality, ts, faces)->dict`, `jetson_face_facts_shadow_enabled()->bool`, `_jetson_write_face_facts_receipt(reading, *, received_at)`, endpoint `api_jetson_face_facts_intake` — consistent across tasks. `faces` entries are `(embedding, det_score, box, track_id)` tuples into `build_packet`, dicts on the wire.
