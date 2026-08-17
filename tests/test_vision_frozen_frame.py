# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 3 — private frozen-frame evaluation harness (@df797f9).

Human labels are the only truth. The harness is a private bench witness: it
never captures, admits, ranks, or publishes screen evidence to cognition.
Gate criteria v1.1 were frozen by the owner before implementation.
"""

from __future__ import annotations

import ast
import hashlib
import http.client
import io
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, PngImagePlugin

from core.vision_contract.frozen_frame import (
    LABEL_SCHEMA_VERSION,
    MANIFEST_SCHEMA_VERSION,
    TRANSFORM_ORDER,
    HarnessRefusal,
    derive_transforms,
    frame_hash_projection,
    load_frame_case,
    load_manifest,
)
from core.vision_contract.truth_contract import build_transcribe_request, parse_and_validate


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _PrivateBenchFixture:
    def __init__(self, root: Path, *, frame_id: str = "frame-001") -> None:
        self.root = root
        self.frame_id = frame_id
        self.frames = root / "frames"
        self.labels = root / "labels"
        self.frames.mkdir(parents=True, exist_ok=True)
        self.labels.mkdir(parents=True, exist_ok=True)
        self.frame_path = self.frames / f"{frame_id}.png"
        image = Image.new("RGB", (100, 80), color=(12, 34, 56))
        image.save(self.frame_path, format="PNG")
        self.source_bytes = self.frame_path.read_bytes()
        self.manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "frames": [frame_id],
        }
        self.label = {
            "schema_version": LABEL_SCHEMA_VERSION,
            "frame_id": frame_id,
            "source_sha256": _sha256(self.source_bytes),
            "truth_source": "owner_human",
            "owner_approved": True,
            "third_party_content_reviewed": True,
            "active_window_crop": {
                "left": 10,
                "top": 10,
                "right": 90,
                "bottom": 70,
            },
            "labels": [
                {
                    "label_id": "title-1",
                    "region_id": "titlebar",
                    "region_aliases": ["titlebar", "window title"],
                    "kind": "window_title",
                    "text": "Settings",
                    "visible_in": ["full_640", "full_1280", "active_native"],
                }
            ],
        }
        self.write()

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def label_path(self) -> Path:
        return self.labels / f"{self.frame_id}.json"

    def write(self) -> None:
        self.manifest_path.write_text(
            json.dumps(self.manifest, sort_keys=True), encoding="utf-8"
        )
        self.label_path.write_text(
            json.dumps(self.label, sort_keys=True), encoding="utf-8"
        )


class LabelContractTests(unittest.TestCase):
    def _fixture(self):
        temp = tempfile.TemporaryDirectory(prefix="maez-frozen-labels-")
        self.addCleanup(temp.cleanup)
        fixture = _PrivateBenchFixture(Path(temp.name))
        return fixture

    def _assert_refusal(self, expected: str, fn) -> None:
        with self.assertRaises(HarnessRefusal) as caught:
            fn()
        self.assertEqual(caught.exception.reason, expected)
        self.assertEqual(str(caught.exception), expected)

    def test_valid_owner_label_binds_exact_source_and_crop(self):
        fixture = self._fixture()

        case = load_frame_case(fixture.root, fixture.frame_id)

        self.assertEqual(case.frame_id, fixture.frame_id)
        self.assertEqual(case.source_bytes, fixture.source_bytes)
        self.assertEqual(case.source_sha256, _sha256(fixture.source_bytes))
        self.assertEqual(case.label_sha256, _sha256(fixture.label_path.read_bytes()))
        self.assertEqual(
            (case.crop.left, case.crop.top, case.crop.right, case.crop.bottom),
            (10, 10, 90, 70),
        )
        self.assertEqual(case.labels[0].region_id, "titlebar")
        self.assertEqual(case.labels[0].aliases, ("titlebar", "window title"))
        self.assertEqual(case.labels[0].text, "Settings")

    def test_manifest_is_explicit_and_never_globs_unlisted_frames(self):
        fixture = self._fixture()
        extra = _PrivateBenchFixture(fixture.root, frame_id="unapproved-extra")
        fixture.manifest["frames"] = [fixture.frame_id]
        fixture.write()
        extra.label_path.write_text(
            json.dumps(extra.label, sort_keys=True), encoding="utf-8"
        )

        self.assertEqual(load_manifest(fixture.root), (fixture.frame_id,))

    def test_missing_manifest_refuses(self):
        fixture = self._fixture()
        fixture.manifest_path.unlink()

        self._assert_refusal("manifest_missing", lambda: load_manifest(fixture.root))

    def test_manifest_schema_and_safe_frame_ids_are_required(self):
        fixture = self._fixture()
        for manifest in (
            {"schema_version": "wrong", "frames": [fixture.frame_id]},
            {"schema_version": MANIFEST_SCHEMA_VERSION, "frames": []},
            {"schema_version": MANIFEST_SCHEMA_VERSION, "frames": ["../escape"]},
            {"schema_version": MANIFEST_SCHEMA_VERSION, "frames": [fixture.frame_id] * 2},
        ):
            with self.subTest(manifest=manifest):
                fixture.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                self._assert_refusal(
                    "manifest_schema_invalid", lambda: load_manifest(fixture.root)
                )

    def test_missing_label_file_refuses(self):
        fixture = self._fixture()
        fixture.label_path.unlink()

        self._assert_refusal(
            "label_file_missing",
            lambda: load_frame_case(fixture.root, fixture.frame_id),
        )

    def test_empty_human_labels_refuse_instead_of_degraded_scoring(self):
        fixture = self._fixture()
        fixture.label["labels"] = []
        fixture.write()

        self._assert_refusal(
            "labels_empty", lambda: load_frame_case(fixture.root, fixture.frame_id)
        )

    def test_owner_approval_is_exact_true(self):
        fixture = self._fixture()
        for value in (False, None, 1, "true"):
            with self.subTest(value=value):
                if value is None:
                    fixture.label.pop("owner_approved", None)
                else:
                    fixture.label["owner_approved"] = value
                fixture.write()
                self._assert_refusal(
                    "owner_approval_missing",
                    lambda: load_frame_case(fixture.root, fixture.frame_id),
                )
                fixture.label["owner_approved"] = True

    def test_truth_source_must_explicitly_be_owner_human(self):
        fixture = self._fixture()
        for value in (None, "model", "consensus", "owner"):
            with self.subTest(value=value):
                if value is None:
                    fixture.label.pop("truth_source", None)
                else:
                    fixture.label["truth_source"] = value
                fixture.write()
                self._assert_refusal(
                    "human_truth_marker_missing",
                    lambda: load_frame_case(fixture.root, fixture.frame_id),
                )
                fixture.label["truth_source"] = "owner_human"

    def test_third_party_review_marker_is_exact_true(self):
        fixture = self._fixture()
        for value in (False, None, 1, "true"):
            with self.subTest(value=value):
                if value is None:
                    fixture.label.pop("third_party_content_reviewed", None)
                else:
                    fixture.label["third_party_content_reviewed"] = value
                fixture.write()
                self._assert_refusal(
                    "third_party_review_missing",
                    lambda: load_frame_case(fixture.root, fixture.frame_id),
                )
                fixture.label["third_party_content_reviewed"] = True

    def test_source_file_and_exact_hash_are_required(self):
        fixture = self._fixture()
        fixture.label["source_sha256"] = "0" * 64
        fixture.write()
        self._assert_refusal(
            "source_hash_mismatch",
            lambda: load_frame_case(fixture.root, fixture.frame_id),
        )

        fixture.label["source_sha256"] = _sha256(fixture.source_bytes)
        fixture.write()
        fixture.frame_path.unlink()
        self._assert_refusal(
            "source_frame_missing",
            lambda: load_frame_case(fixture.root, fixture.frame_id),
        )

    def test_invalid_source_image_refuses_with_typed_reason(self):
        fixture = self._fixture()
        fixture.frame_path.write_bytes(b"not-an-image")
        fixture.label["source_sha256"] = _sha256(b"not-an-image")
        fixture.write()

        self._assert_refusal(
            "source_frame_invalid",
            lambda: load_frame_case(fixture.root, fixture.frame_id),
        )

    def test_truncated_source_pixels_refuse_before_transform_work(self):
        fixture = self._fixture()
        image = Image.new("RGB", (100, 80), color=(12, 34, 56))
        image.save(fixture.frame_path, format="PNG", compress_level=0)
        truncated = fixture.frame_path.read_bytes()[:-4_000]
        fixture.frame_path.write_bytes(truncated)
        fixture.label["source_sha256"] = _sha256(truncated)
        fixture.write()

        self._assert_refusal(
            "source_frame_invalid",
            lambda: load_frame_case(fixture.root, fixture.frame_id),
        )

    def test_world_readable_bench_root_is_not_private(self):
        fixture = self._fixture()
        fixture.root.chmod(0o755)

        self._assert_refusal(
            "bench_root_not_private", lambda: load_manifest(fixture.root)
        )

    def test_symlinked_artifact_cannot_escape_bench_root(self):
        fixture = self._fixture()
        outside_temp = tempfile.TemporaryDirectory(prefix="maez-frozen-outside-")
        self.addCleanup(outside_temp.cleanup)
        outside = Path(outside_temp.name) / "outside.png"
        outside.write_bytes(fixture.source_bytes)
        fixture.frame_path.unlink()
        fixture.frame_path.symlink_to(outside)

        self._assert_refusal(
            "bench_root_not_private",
            lambda: load_frame_case(fixture.root, fixture.frame_id),
        )

    def test_hardlinked_private_inputs_are_rejected(self):
        fixture = self._fixture()
        outside_temp = tempfile.TemporaryDirectory(prefix="maez-frozen-hardlink-")
        self.addCleanup(outside_temp.cleanup)
        outside = Path(outside_temp.name) / "exposed.png"
        os.link(fixture.frame_path, outside)
        outside.chmod(0o644)

        self._assert_refusal(
            "bench_root_not_private",
            lambda: load_frame_case(fixture.root, fixture.frame_id),
        )

    def test_symlinked_bench_ancestor_is_rejected(self):
        temp = tempfile.TemporaryDirectory(prefix="maez-frozen-ancestor-")
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        actual_parent = base / "actual"
        actual_parent.mkdir()
        fixture = _PrivateBenchFixture(actual_parent / "bench")
        fixture.root.chmod(0o700)
        linked_parent = base / "linked"
        linked_parent.symlink_to(actual_parent, target_is_directory=True)

        self._assert_refusal(
            "bench_root_not_private",
            lambda: load_frame_case(
                linked_parent / "bench",
                fixture.frame_id,
            ),
        )

    def test_crop_is_required_and_must_fit_source_pixels(self):
        fixture = self._fixture()
        fixture.label.pop("active_window_crop")
        fixture.write()
        self._assert_refusal(
            "active_crop_missing",
            lambda: load_frame_case(fixture.root, fixture.frame_id),
        )

        for crop in (
            {"left": 0, "top": 0, "right": 0, "bottom": 10},
            {"left": -1, "top": 0, "right": 10, "bottom": 10},
            {"left": 0, "top": 0, "right": 101, "bottom": 80},
            {"left": 0, "top": 0, "right": 100, "bottom": 81},
            {"left": 0.5, "top": 0, "right": 10, "bottom": 10},
        ):
            with self.subTest(crop=crop):
                fixture.label["active_window_crop"] = crop
                fixture.write()
                self._assert_refusal(
                    "active_crop_invalid",
                    lambda: load_frame_case(fixture.root, fixture.frame_id),
                )

    def test_label_schema_requires_human_region_alias_kind_text_and_visibility(self):
        fixture = self._fixture()
        valid = fixture.label["labels"][0].copy()
        mutations = (
            {**valid, "label_id": ""},
            {**valid, "region_id": "../titlebar"},
            {**valid, "region_aliases": []},
            {**valid, "region_aliases": ["titlebar", 7]},
            {**valid, "kind": "model_guess"},
            {**valid, "kind": {}},
            {**valid, "text": ""},
            {**valid, "visible_in": []},
            {**valid, "visible_in": [{}]},
            {**valid, "visible_in": ["full_640", "unknown_transform"]},
        )
        for label in mutations:
            with self.subTest(label=label):
                fixture.label["labels"] = [label]
                fixture.write()
                self._assert_refusal(
                    "label_schema_invalid",
                    lambda: load_frame_case(fixture.root, fixture.frame_id),
                )

    def test_region_aliases_cannot_ambiguously_map_two_human_regions(self):
        fixture = self._fixture()
        second = {
            **fixture.label["labels"][0],
            "label_id": "title-2",
            "region_id": "editor",
            "region_aliases": ["window title", "editor"],
            "text": "main.py",
        }
        fixture.label["labels"].append(second)
        fixture.write()

        self._assert_refusal(
            "label_schema_invalid",
            lambda: load_frame_case(fixture.root, fixture.frame_id),
        )


class FrozenTransformTests(unittest.TestCase):
    def _fixture(self, *, large: bool = True):
        temp = tempfile.TemporaryDirectory(prefix="maez-frozen-transforms-")
        self.addCleanup(temp.cleanup)
        fixture = _PrivateBenchFixture(Path(temp.name))
        if large:
            image = Image.new("RGB", (1600, 900), color=(0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 799, 449), fill=(255, 0, 0))
            draw.rectangle((800, 0, 1599, 449), fill=(0, 255, 0))
            draw.rectangle((0, 450, 799, 899), fill=(0, 0, 255))
            draw.rectangle((800, 450, 1599, 899), fill=(255, 255, 0))
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("private-note", "must-not-survive-transform")
            image.save(fixture.frame_path, format="PNG", pnginfo=metadata)
            fixture.source_bytes = fixture.frame_path.read_bytes()
            fixture.label["source_sha256"] = _sha256(fixture.source_bytes)
            fixture.label["active_window_crop"] = {
                "left": 321,
                "top": 111,
                "right": 987,
                "bottom": 777,
            }
            fixture.write()
        return fixture

    def test_identical_source_produces_byte_identical_transforms_and_hashes(self):
        fixture = self._fixture()
        case = load_frame_case(fixture.root, fixture.frame_id)

        first = derive_transforms(case)
        second = derive_transforms(case)

        self.assertEqual(first, second)
        self.assertEqual([item.name for item in first], list(TRANSFORM_ORDER))
        for item in first:
            self.assertEqual(item.sha256, _sha256(item.png_bytes))

    def test_full_transforms_preserve_aspect_ratio_and_never_upscale(self):
        large = self._fixture()
        large_transforms = {
            item.name: item for item in derive_transforms(load_frame_case(large.root, large.frame_id))
        }
        self.assertEqual((large_transforms["full_640"].width, large_transforms["full_640"].height), (640, 360))
        self.assertEqual((large_transforms["full_1280"].width, large_transforms["full_1280"].height), (1280, 720))

        small = self._fixture(large=False)
        small_transforms = {
            item.name: item for item in derive_transforms(load_frame_case(small.root, small.frame_id))
        }
        self.assertEqual((small_transforms["full_640"].width, small_transforms["full_640"].height), (100, 80))
        self.assertEqual((small_transforms["full_1280"].width, small_transforms["full_1280"].height), (100, 80))

    def test_full_transform_limit_applies_to_portrait_longest_edge(self):
        fixture = self._fixture(large=False)
        image = Image.new("RGB", (900, 1600), color=(12, 34, 56))
        image.save(fixture.frame_path, format="PNG")
        fixture.source_bytes = fixture.frame_path.read_bytes()
        fixture.label["source_sha256"] = _sha256(fixture.source_bytes)
        fixture.label["active_window_crop"] = {
            "left": 10,
            "top": 10,
            "right": 890,
            "bottom": 1590,
        }
        fixture.write()

        transforms = {
            item.name: item
            for item in derive_transforms(load_frame_case(fixture.root, fixture.frame_id))
        }

        self.assertEqual((transforms["full_640"].width, transforms["full_640"].height), (360, 640))
        self.assertEqual((transforms["full_1280"].width, transforms["full_1280"].height), (720, 1280))

    def test_active_native_is_exact_crop_from_original_source(self):
        fixture = self._fixture()
        case = load_frame_case(fixture.root, fixture.frame_id)
        active = {item.name: item for item in derive_transforms(case)}["active_native"]

        with Image.open(io.BytesIO(case.source_bytes)) as source:
            expected = source.convert("RGB").crop((321, 111, 987, 777))
        with Image.open(io.BytesIO(active.png_bytes)) as actual:
            self.assertEqual(actual.size, (666, 666))
            self.assertIsNone(ImageChops.difference(expected, actual).getbbox())

    def test_derivation_uses_retained_bytes_after_source_file_is_removed(self):
        fixture = self._fixture()
        case = load_frame_case(fixture.root, fixture.frame_id)
        fixture.frame_path.unlink()

        transforms = derive_transforms(case)

        self.assertEqual([item.name for item in transforms], list(TRANSFORM_ORDER))

    def test_transforms_are_rgb_png_with_fixed_encoding_and_no_metadata(self):
        fixture = self._fixture()
        transforms = derive_transforms(load_frame_case(fixture.root, fixture.frame_id))

        for transform in transforms:
            with self.subTest(transform=transform.name):
                self.assertTrue(transform.png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))
                with Image.open(io.BytesIO(transform.png_bytes)) as image:
                    image.load()
                    self.assertEqual(image.format, "PNG")
                    self.assertEqual(image.mode, "RGB")
                    self.assertNotIn("private-note", image.info)

    def test_hash_projection_pins_source_label_and_all_transform_bytes(self):
        fixture = self._fixture()
        case = load_frame_case(fixture.root, fixture.frame_id)
        transforms = derive_transforms(case)

        projection = frame_hash_projection(case, transforms)

        self.assertEqual(projection["source_sha256"], case.source_sha256)
        self.assertEqual(projection["label_sha256"], case.label_sha256)
        self.assertEqual(
            projection["transform_sha256"],
            {item.name: item.sha256 for item in transforms},
        )

    def test_hash_projection_recomputes_retained_source_identity(self):
        fixture = self._fixture()
        case = load_frame_case(fixture.root, fixture.frame_id)
        transforms = derive_transforms(case)

        with self.assertRaisesRegex(ValueError, "source_hash_mismatch"):
            frame_hash_projection(
                replace(case, source_sha256="0" * 64),
                transforms,
            )


class _CandidateStub(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        return

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self.server.seen.append(("GET", self.path, None))
        redirect_to = getattr(self.server, "redirect_models_to", None)
        if redirect_to is not None:
            self.send_response(307)
            self.send_header("Location", redirect_to)
            self.end_headers()
            return
        if getattr(self.server, "invalid_json", False):
            body = b"not-json"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/v1/models":
            self._send_json(200, {"data": [{"id": self.server.model_id}]})
        else:
            self._send_json(404, {})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        self.server.seen.append(("POST", self.path, payload))
        redirect_to = getattr(self.server, "redirect_chat_to", None)
        if redirect_to is not None:
            self.send_response(307)
            self.send_header("Location", redirect_to)
            self.end_headers()
            return
        if getattr(self.server, "invalid_json", False):
            body = b"not-json"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/v1/chat/completions":
            sequence = getattr(self.server, "response_sequence", [])
            response_payload = sequence.pop(0) if sequence else getattr(
                self.server, "response_payload", None
            )
            if isinstance(response_payload, bytes):
                self.send_response(200)
                self.send_header("Content-Length", str(len(response_payload)))
                self.end_headers()
                self.wfile.write(response_payload)
                return
            self._send_json(
                200,
                response_payload
                if response_payload is not None
                else {"choices": [{"message": {"content": self.server.content}}]},
            )
        else:
            self._send_json(404, {})


class ContractNativeInvokerTests(unittest.TestCase):
    def _server(self, *, model_id="maez-vision", content="REGION: titlebar\nTEXT: Settings"):
        server = ThreadingHTTPServer(("127.0.0.1", 0), _CandidateStub)
        server.model_id = model_id
        server.content = content
        server.seen = []
        server.redirect_models_to = None
        server.redirect_chat_to = None
        server.invalid_json = False
        server.response_payload = None
        server.response_sequence = []
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def _imports(self):
        from scripts.vision_frozen_bench import (
            CandidateConfigError,
            CandidateSpec,
            HttpCandidateInvoker,
        )

        return CandidateConfigError, CandidateSpec, HttpCandidateInvoker

    def test_only_explicit_plain_http_loopback_root_is_accepted(self):
        CandidateConfigError, CandidateSpec, _ = self._imports()
        invalid = (
            "http://127.0.0.1",
            "http://localhost",
            "https://127.0.0.1:8082",
            "http://0.0.0.0:8082",
            "http://127.0.0.2:8082",
            "http://user:pass@127.0.0.1:8082",
            "http://127.0.0.1:8082/v1",
            "http://127.0.0.1:8082?x=1",
            "http://127.0.0.1:8082#fragment",
        )
        for base_url in invalid:
            with self.subTest(base_url=base_url):
                with self.assertRaises(CandidateConfigError) as caught:
                    CandidateSpec(label="candidate", base_url=base_url, model="maez-vision")
                self.assertEqual(caught.exception.reason, "invalid_base_url")

        for base_url in ("http://127.0.0.1:8082", "http://localhost:8082/"):
            with self.subTest(base_url=base_url):
                spec = CandidateSpec(label="candidate", base_url=base_url, model="maez-vision")
                self.assertEqual(spec.base_url, base_url.rstrip("/"))

    def test_session_ignores_environment_proxies(self):
        _, CandidateSpec, HttpCandidateInvoker = self._imports()
        invoker = HttpCandidateInvoker(
            CandidateSpec("candidate", "http://127.0.0.1:8082", "maez-vision")
        )

        self.assertIs(invoker.session.trust_env, False)

    def test_owned_session_cannot_route_frame_through_explicit_proxy(self):
        _, CandidateSpec, HttpCandidateInvoker = self._imports()
        origin = self._server()
        proxy = self._server()
        invoker = HttpCandidateInvoker(
            CandidateSpec(
                "candidate",
                f"http://127.0.0.1:{origin.server_port}",
                "maez-vision",
            )
        )
        invoker.session.proxies["http"] = f"http://127.0.0.1:{proxy.server_port}"

        invoker.verify_ready()
        verdict = invoker.invoke(b"private-frozen-frame")

        self.assertEqual(verdict.verdict, "ok")
        self.assertEqual([item[0] for item in origin.seen], ["GET", "POST"])
        self.assertEqual(proxy.seen, [])

    def test_readiness_redirect_is_not_followed(self):
        CandidateConfigError, CandidateSpec, HttpCandidateInvoker = self._imports()
        origin = self._server()
        target = self._server()
        origin.redirect_models_to = f"http://127.0.0.1:{target.server_port}/v1/models"
        invoker = HttpCandidateInvoker(
            CandidateSpec(
                "candidate",
                f"http://127.0.0.1:{origin.server_port}",
                "maez-vision",
            )
        )

        with self.assertRaises(CandidateConfigError) as caught:
            invoker.verify_ready()

        self.assertEqual(caught.exception.reason, "candidate_not_ready")
        self.assertEqual(target.seen, [])

    def test_inference_redirect_never_forwards_frame(self):
        CandidateConfigError, CandidateSpec, HttpCandidateInvoker = self._imports()
        origin = self._server()
        target = self._server()
        origin.redirect_chat_to = (
            f"http://127.0.0.1:{target.server_port}/v1/chat/completions"
        )
        invoker = HttpCandidateInvoker(
            CandidateSpec(
                "candidate",
                f"http://127.0.0.1:{origin.server_port}",
                "maez-vision",
            )
        )
        invoker.verify_ready()

        with self.assertRaises(CandidateConfigError) as caught:
            invoker.invoke(b"private-frozen-frame")

        self.assertEqual(caught.exception.reason, "candidate_protocol_error")
        self.assertEqual(target.seen, [])

    def test_readiness_and_inference_use_exact_alias_and_slice2_contract(self):
        _, CandidateSpec, HttpCandidateInvoker = self._imports()
        server = self._server()
        base_url = f"http://127.0.0.1:{server.server_port}"
        invoker = HttpCandidateInvoker(CandidateSpec("candidate", base_url, "maez-vision"))

        invoker.verify_ready()
        verdict = invoker.invoke(b"frozen-png")

        self.assertEqual(verdict.verdict, "ok")
        self.assertEqual(verdict.fields[0].text, "Settings")
        self.assertEqual(server.seen[0], ("GET", "/v1/models", None))
        method, path, payload = server.seen[1]
        self.assertEqual((method, path), ("POST", "/v1/chat/completions"))
        import base64

        self.assertEqual(
            payload,
            build_transcribe_request(
                image_b64=base64.b64encode(b"frozen-png").decode("ascii"),
                model="maez-vision",
            ),
        )
        self.assertEqual(payload["temperature"], 0)

    def test_readiness_requires_exact_model_alias(self):
        CandidateConfigError, CandidateSpec, HttpCandidateInvoker = self._imports()
        server = self._server(model_id="different-model")
        invoker = HttpCandidateInvoker(
            CandidateSpec(
                "candidate",
                f"http://127.0.0.1:{server.server_port}",
                "maez-vision",
            )
        )

        with self.assertRaises(CandidateConfigError) as caught:
            invoker.verify_ready()
        self.assertEqual(caught.exception.reason, "candidate_model_mismatch")

    def test_candidate_reply_is_judged_only_by_slice2_parser(self):
        _, CandidateSpec, HttpCandidateInvoker = self._imports()
        server = self._server(content="I see main.py and a git push in the editor")
        invoker = HttpCandidateInvoker(
            CandidateSpec(
                "candidate",
                f"http://127.0.0.1:{server.server_port}",
                "maez-vision",
            )
        )

        invoker.verify_ready()
        verdict = invoker.invoke(b"frozen-png")

        self.assertEqual(verdict.verdict, "rejected")
        self.assertEqual(verdict.reason, "unstructured_specificity")

    def test_protocol_failure_clears_previous_private_raw_response(self):
        CandidateConfigError, CandidateSpec, HttpCandidateInvoker = self._imports()
        marker = "REGION: titlebar\nTEXT: PRIVATE-MARKER"
        server = self._server(content=marker)
        invoker = HttpCandidateInvoker(
            CandidateSpec(
                "candidate",
                f"http://127.0.0.1:{server.server_port}",
                "maez-vision",
            )
        )
        invoker.verify_ready()
        invoker.invoke(b"first-frame")
        self.assertEqual(invoker.last_raw, marker)
        server.invalid_json = True

        with self.assertRaises(CandidateConfigError) as caught:
            invoker.invoke(b"second-frame")

        self.assertEqual(caught.exception.reason, "candidate_protocol_error")
        self.assertIsNone(invoker.last_raw)
        self.assertNotIn("PRIVATE-MARKER", str(caught.exception))

    def test_missing_or_non_string_content_fails_closed_through_slice2(self):
        _, CandidateSpec, HttpCandidateInvoker = self._imports()
        server = self._server()
        invoker = HttpCandidateInvoker(
            CandidateSpec(
                "candidate",
                f"http://127.0.0.1:{server.server_port}",
                "maez-vision",
            )
        )
        invoker.verify_ready()
        for payload in ({}, {"choices": [{"message": {"content": ["text"]}}]}):
            with self.subTest(payload=payload):
                server.response_payload = payload
                verdict = invoker.invoke(b"frame")
                self.assertEqual(verdict.verdict, "rejected")
                self.assertEqual(verdict.reason, "protocol_violation")
                self.assertIsNone(invoker.last_raw)

    def test_global_http_debug_cannot_print_frame_or_request_body(self):
        _, CandidateSpec, HttpCandidateInvoker = self._imports()
        server = self._server()
        invoker = HttpCandidateInvoker(
            CandidateSpec(
                "candidate",
                f"http://127.0.0.1:{server.server_port}",
                "maez-vision",
            )
        )
        prior = http.client.HTTPConnection.debuglevel
        stdout = io.StringIO()
        try:
            http.client.HTTPConnection.debuglevel = 1
            with redirect_stdout(stdout):
                invoker.verify_ready()
                invoker.invoke(b"PRIVATE-FROZEN-BYTES")
        finally:
            http.client.HTTPConnection.debuglevel = prior

        emitted = stdout.getvalue()
        self.assertNotIn("PRIVATE-FROZEN-BYTES", emitted)
        self.assertNotIn("data:image", emitted)
        self.assertEqual(emitted, "")


def _two_label_case(test: unittest.TestCase):
    temp = tempfile.TemporaryDirectory(prefix="maez-frozen-scoring-")
    test.addCleanup(temp.cleanup)
    fixture = _PrivateBenchFixture(Path(temp.name))
    fixture.label["labels"].append(
        {
            "label_id": "filename-1",
            "region_id": "editor",
            "region_aliases": ["editor", "code pane"],
            "kind": "filename",
            "text": "main.py",
            "visible_in": ["full_640", "full_1280", "active_native"],
        }
    )
    fixture.write()
    return load_frame_case(fixture.root, fixture.frame_id)


def _scoring_imports():
    from core.vision_contract.frozen_frame import (
        ScoringRefusal,
        aggregate_coverage,
        check_evidence_monotonicity,
        score_transform,
    )

    return ScoringRefusal, aggregate_coverage, check_evidence_monotonicity, score_transform


class ScoringTests(unittest.TestCase):
    def test_correct_text_and_abstention_coverage_are_separate(self):
        _, _, _, score_transform = _scoring_imports()
        case = _two_label_case(self)
        verdict = parse_and_validate(
            "REGION: WINDOW TITLE\nTEXT: Settings\n"
            "REGION: code pane\nTEXT: [UNREADABLE]"
        )

        score = score_transform(case, "full_640", verdict)

        self.assertEqual(score.coverage.correct_text_numerator, 1)
        self.assertEqual(score.coverage.correct_text_denominator, 2)
        self.assertEqual(score.coverage.correct_text_coverage, 0.5)
        self.assertEqual(score.coverage.abstention_numerator, 1)
        self.assertEqual(score.coverage.abstention_denominator, 2)
        self.assertEqual(score.coverage.abstention_coverage, 0.5)

    def test_honest_empty_counts_as_abstention_not_correct_text(self):
        _, _, _, score_transform = _scoring_imports()
        score = score_transform(
            _two_label_case(self),
            "full_640",
            parse_and_validate("NO_TEXT_VISIBLE"),
        )

        self.assertEqual(score.coverage.correct_text_numerator, 0)
        self.assertEqual(score.coverage.correct_text_denominator, 2)
        self.assertEqual(score.coverage.abstention_numerator, 2)
        self.assertEqual(score.coverage.abstention_denominator, 2)

    def test_wrong_low_specificity_text_is_neither_correct_nor_abstention(self):
        _, _, _, score_transform = _scoring_imports()
        case = _two_label_case(self)
        verdict = parse_and_validate("REGION: titlebar\nTEXT: Preferences")

        score = score_transform(case, "full_640", verdict)

        self.assertEqual(score.coverage.correct_text_numerator, 0)
        self.assertEqual(score.coverage.abstention_numerator, 0)
        self.assertEqual(score.coverage.correct_text_denominator, 2)
        self.assertEqual(score.coverage.abstention_denominator, 2)

    def test_unknown_or_not_applicable_region_refuses_instead_of_auto_alignment(self):
        ScoringRefusal, _, _, score_transform = _scoring_imports()
        case = _two_label_case(self)
        for raw in (
            "REGION: sidebar\nTEXT: Settings",
            "REGION: editor\nTEXT: main.py",
        ):
            with self.subTest(raw=raw):
                if raw.startswith("REGION: editor"):
                    labels = tuple(
                        replace(label, visible_in=("active_native",))
                        if label.region_id == "editor"
                        else label
                        for label in case.labels
                    )
                    scored_case = replace(case, labels=labels)
                else:
                    scored_case = case
                with self.assertRaises(ScoringRefusal) as caught:
                    score_transform(
                        scored_case,
                        "full_640",
                        parse_and_validate(raw),
                    )
                self.assertEqual(caught.exception.reason, "unknown_region")

    def test_rejected_contract_verdict_refuses_scoring(self):
        ScoringRefusal, _, _, score_transform = _scoring_imports()
        with self.assertRaises(ScoringRefusal) as caught:
            score_transform(
                _two_label_case(self),
                "full_640",
                parse_and_validate("I see words"),
            )
        self.assertEqual(caught.exception.reason, "candidate_verdict_rejected")

    def test_transform_with_no_applicable_human_truth_refuses_scoring(self):
        ScoringRefusal, _, _, score_transform = _scoring_imports()
        case = _two_label_case(self)
        case = replace(
            case,
            labels=tuple(
                replace(label, visible_in=("active_native",))
                for label in case.labels
            ),
        )

        with self.assertRaises(ScoringRefusal) as caught:
            score_transform(
                case,
                "full_640",
                parse_and_validate("NO_TEXT_VISIBLE"),
            )

        self.assertEqual(caught.exception.reason, "labels_empty_for_transform")

    def test_aggregate_keeps_both_metric_denominators_and_numerators(self):
        _, aggregate_coverage, _, score_transform = _scoring_imports()
        case = _two_label_case(self)
        scores = (
            score_transform(
                case,
                "full_640",
                parse_and_validate(
                    "REGION: titlebar\nTEXT: Settings\n"
                    "REGION: editor\nTEXT: [UNREADABLE]"
                ),
            ),
            score_transform(case, "full_1280", parse_and_validate("NO_TEXT_VISIBLE")),
        )

        coverage = aggregate_coverage(scores)

        self.assertEqual(
            (
                coverage.correct_text_numerator,
                coverage.correct_text_denominator,
                coverage.abstention_numerator,
                coverage.abstention_denominator,
            ),
            (1, 4, 3, 4),
        )
        self.assertEqual(coverage.correct_text_coverage, 0.25)
        self.assertEqual(coverage.abstention_coverage, 0.75)


class MonotonicityTests(unittest.TestCase):
    def _check(self, low: str, high: str):
        _, _, check, _ = _scoring_imports()
        return check(
            _two_label_case(self),
            {
                "full_640": parse_and_validate(low),
                "full_1280": parse_and_validate(high),
                "active_native": parse_and_validate(high),
            },
        )

    def test_abstain_then_transcribe_passes(self):
        findings = self._check(
            "REGION: titlebar\nTEXT: [UNREADABLE]",
            "REGION: titlebar\nTEXT: Settings",
        )
        self.assertEqual(findings, ())

    def test_abstain_then_wrong_low_specificity_is_not_a_contradiction(self):
        findings = self._check(
            "REGION: titlebar\nTEXT: [UNREADABLE]",
            "REGION: titlebar\nTEXT: Preferences",
        )

        self.assertEqual(findings, ())

    def test_partial_then_fuller_transcription_passes(self):
        findings = self._check(
            "REGION: titlebar\nTEXT: Set [UNREADABLE]",
            "REGION: titlebar\nTEXT: Settings",
        )
        self.assertEqual(findings, ())

    def test_compatible_partial_evidence_can_become_more_complete(self):
        _, _, check, _ = _scoring_imports()
        findings = check(
            _two_label_case(self),
            {
                "full_640": parse_and_validate(
                    "REGION: titlebar\nTEXT: Set [UNREADABLE]"
                ),
                "full_1280": parse_and_validate(
                    "REGION: titlebar\nTEXT: Setti [UNREADABLE]"
                ),
                "active_native": parse_and_validate(
                    "REGION: titlebar\nTEXT: Settings"
                ),
            },
        )

        self.assertEqual(findings, ())

    def test_complementary_partial_fragments_share_owner_labeled_completion(self):
        _, _, check, _ = _scoring_imports()
        findings = check(
            _two_label_case(self),
            {
                "full_640": parse_and_validate(
                    "REGION: titlebar\nTEXT: [UNREADABLE] ings"
                ),
                "full_1280": parse_and_validate(
                    "REGION: titlebar\nTEXT: Sett [UNREADABLE]"
                ),
                "active_native": parse_and_validate(
                    "REGION: titlebar\nTEXT: Settings"
                ),
            },
        )

        self.assertEqual(findings, ())

    def test_incompatible_partial_evidence_is_a_contradiction(self):
        _, _, check, _ = _scoring_imports()
        findings = check(
            _two_label_case(self),
            {
                "full_640": parse_and_validate(
                    "REGION: titlebar\nTEXT: Set [UNREADABLE]"
                ),
                "full_1280": parse_and_validate(
                    "REGION: titlebar\nTEXT: Pref [UNREADABLE]"
                ),
                "active_native": parse_and_validate(
                    "REGION: titlebar\nTEXT: Preferences"
                ),
            },
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].reason, "evidence_contradiction")

    def test_higher_transform_may_preserve_and_add_evidence(self):
        findings = self._check(
            "REGION: titlebar\nTEXT: Settings",
            "REGION: titlebar\nTEXT: Settings\nREGION: editor\nTEXT: main.py",
        )
        self.assertEqual(findings, ())

    def test_different_full_values_are_hard_contradiction(self):
        findings = self._check(
            "REGION: titlebar\nTEXT: Settings",
            "REGION: titlebar\nTEXT: Preferences",
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].reason, "evidence_contradiction")
        self.assertFalse(hasattr(findings[0], "region_id"))
        self.assertEqual(findings[0].region_character_count, len("titlebar"))
        self.assertEqual(findings[0].region_sha256, _sha256(b"titlebar"))
        self.assertEqual(findings[0].lower_transform, "full_640")
        self.assertEqual(findings[0].higher_transform, "full_1280")

    def test_higher_abstention_after_full_value_is_evidence_regression(self):
        findings = self._check(
            "REGION: titlebar\nTEXT: Settings",
            "REGION: titlebar\nTEXT: [UNREADABLE]",
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].reason, "evidence_regression")

    def test_missing_transform_set_refuses_monotonicity_check(self):
        ScoringRefusal, _, check, _ = _scoring_imports()
        case = _two_label_case(self)
        with self.assertRaises(ScoringRefusal) as caught:
            check(
                case,
                {"full_640": parse_and_validate("NO_TEXT_VISIBLE")},
            )
        self.assertEqual(caught.exception.reason, "transform_set_incomplete")

    def test_non_adjacent_640_to_active_contradiction_is_checked(self):
        _, _, check, _ = _scoring_imports()
        findings = check(
            _two_label_case(self),
            {
                "full_640": parse_and_validate(
                    "REGION: titlebar\nTEXT: Settings"
                ),
                "full_1280": parse_and_validate(
                    "REGION: titlebar\nTEXT: Settings"
                ),
                "active_native": parse_and_validate(
                    "REGION: titlebar\nTEXT: Preferences"
                ),
            },
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].reason, "evidence_contradiction")
        self.assertEqual(findings[0].lower_transform, "full_640")
        self.assertEqual(findings[0].higher_transform, "active_native")

    def test_unsupported_same_region_addition_is_contradiction(self):
        findings = self._check(
            "REGION: titlebar\nTEXT: Settings",
            "REGION: titlebar\nTEXT: Settings\n"
            "REGION: titlebar\nTEXT: Preferences",
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].reason, "evidence_contradiction")

    def test_owner_labeled_same_region_addition_is_monotonic(self):
        _, _, check, _ = _scoring_imports()
        case = _two_label_case(self)
        case = replace(
            case,
            labels=case.labels
            + (
                replace(
                    case.labels[0],
                    label_id="title-2",
                    text="Preferences",
                ),
            ),
        )
        high = parse_and_validate(
            "REGION: titlebar\nTEXT: Settings\n"
            "REGION: titlebar\nTEXT: Preferences"
        )

        findings = check(
            case,
            {
                "full_640": parse_and_validate(
                    "REGION: titlebar\nTEXT: Settings"
                ),
                "full_1280": high,
                "active_native": high,
            },
        )

        self.assertEqual(findings, ())


class InventedSpecificityTests(unittest.TestCase):
    def _find(self, raw: str, *, transform_name: str = "full_640"):
        from core.vision_contract.frozen_frame import find_invented_specificity

        return find_invented_specificity(
            _two_label_case(self),
            transform_name,
            parse_and_validate(raw),
        )

    def test_labeled_specificity_is_not_invented(self):
        findings = self._find("REGION: editor\nTEXT: main.py")
        self.assertEqual(findings, ())

    def test_cross_region_applicable_human_string_is_not_invented(self):
        findings = self._find("REGION: titlebar\nTEXT: main.py")

        self.assertEqual(findings, ())

    def test_specificity_requires_exact_extracted_human_claim_not_substring(self):
        from core.vision_contract.frozen_frame import find_invented_specificity

        case = _two_label_case(self)
        case = replace(
            case,
            labels=tuple(
                replace(label, text="domain.py")
                if label.kind == "filename"
                else label
                for label in case.labels
            ),
        )

        findings = find_invented_specificity(
            case,
            "full_640",
            parse_and_validate("REGION: editor\nTEXT: main.py"),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].string_sha256, _sha256(b"main.py"))

    def test_unlabeled_specificity_is_zero_tolerance_hard_finding(self):
        findings = self._find("REGION: editor\nTEXT: secret.py")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, "filename")
        self.assertEqual(findings[0].value, "secret.py")
        self.assertEqual(findings[0].character_count, len("secret.py"))
        self.assertEqual(findings[0].string_sha256, _sha256(b"secret.py"))
        self.assertEqual(findings[0].transform_name, "full_640")

    def test_unknown_region_cannot_bypass_invented_specificity_finding(self):
        from core.vision_contract.frozen_frame import (
            ScoringRefusal,
            find_invented_specificity,
            score_transform,
        )

        case = _two_label_case(self)
        verdict = parse_and_validate("REGION: sidebar\nTEXT: secret.py")

        findings = find_invented_specificity(case, "full_640", verdict)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].string_sha256, _sha256(b"secret.py"))
        with self.assertRaises(ScoringRefusal) as caught:
            score_transform(case, "full_640", verdict)
        self.assertEqual(caught.exception.reason, "unknown_region")

    def test_specificity_label_must_be_applicable_to_transform(self):
        case = _two_label_case(self)
        labels = tuple(
            replace(label, visible_in=("active_native",))
            if label.kind == "filename"
            else label
            for label in case.labels
        )
        from core.vision_contract.frozen_frame import find_invented_specificity

        findings = find_invented_specificity(
            labels and replace(case, labels=labels),
            "full_640",
            parse_and_validate("REGION: titlebar\nTEXT: main.py"),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].string_sha256, _sha256(b"main.py"))

    def test_every_unlabeled_specificity_claim_is_recorded_without_averaging(self):
        findings = self._find(
            "REGION: editor\nTEXT: secret.py then git push and $ pytest"
        )
        self.assertEqual(
            [finding.kind for finding in findings],
            ["filename", "shell_command", "shell_prompt"],
        )

    def test_rejected_verdict_has_no_transcribed_specificity_findings(self):
        findings = self._find("confabulated prose about main.py")

        self.assertEqual(findings, ())


class PrivateArtifactTests(unittest.TestCase):
    def _chain(self):
        from core.vision_contract.frozen_frame import find_invented_specificity
        from scripts.vision_frozen_bench import write_private_artifacts

        temp = tempfile.TemporaryDirectory(prefix="maez-frozen-artifacts-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        case = _two_label_case(self)
        raw = "REGION: editor\nTEXT: secret.py"
        finding = find_invented_specificity(
            case,
            "full_640",
            parse_and_validate(raw),
        )
        chain = write_private_artifacts(
            root,
            run_id="run-001",
            transcripts={"full_640": raw},
            invented_findings=finding,
            allow_external_test_root=True,
        )
        return root, chain, raw, finding[0].value

    def test_private_diagnostic_names_literal_but_receipt_identifies_cryptographically(self):
        from scripts.vision_frozen_bench import specificity_receipt_entries

        root, chain, raw, literal = self._chain()
        entries = specificity_receipt_entries(chain)

        self.assertEqual(len(entries), 1)
        self.assertEqual(
            set(entries[0]),
            {
                "kind",
                "character_count",
                "string_sha256",
                "diagnostic_path",
                "diagnostic_sha256",
            },
        )
        self.assertEqual(entries[0]["kind"], "filename")
        self.assertEqual(entries[0]["character_count"], len(literal))
        self.assertEqual(entries[0]["string_sha256"], _sha256(literal.encode()))
        self.assertNotIn(literal, json.dumps(entries))
        self.assertNotIn(raw, json.dumps(entries))
        diagnostic_bytes = (root / entries[0]["diagnostic_path"]).read_bytes()
        self.assertEqual(entries[0]["diagnostic_sha256"], _sha256(diagnostic_bytes))
        self.assertIn(literal, diagnostic_bytes.decode("utf-8"))

    def test_receipt_resolves_to_literal_and_detects_diagnostic_tampering(self):
        from scripts.vision_frozen_bench import (
            ArtifactChainError,
            resolve_receipt_finding,
            specificity_receipt_entries,
        )

        root, chain, _, literal = self._chain()
        entry = specificity_receipt_entries(chain)[0]
        self.assertEqual(resolve_receipt_finding(root, entry), literal)

        diagnostic_path = root / entry["diagnostic_path"]
        diagnostic_path.write_bytes(diagnostic_path.read_bytes() + b" ")
        with self.assertRaises(ArtifactChainError) as caught:
            resolve_receipt_finding(root, entry)
        self.assertEqual(caught.exception.reason, "diagnostic_hash_mismatch")
        self.assertNotIn(literal, str(caught.exception))

    def test_repeated_identical_invention_across_transforms_has_one_resolvable_identity(self):
        from core.vision_contract.frozen_frame import find_invented_specificity
        from scripts.vision_frozen_bench import (
            resolve_receipt_finding,
            specificity_receipt_entries,
            write_private_artifacts,
        )

        temp = tempfile.TemporaryDirectory(prefix="maez-frozen-repeat-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        case = _two_label_case(self)
        verdict = parse_and_validate("REGION: editor\nTEXT: secret.py")
        findings = (
            find_invented_specificity(case, "full_640", verdict)
            + find_invented_specificity(case, "full_1280", verdict)
        )
        chain = write_private_artifacts(
            root,
            run_id="run-repeat",
            transcripts={"full_640": "secret.py", "full_1280": "secret.py"},
            invented_findings=findings,
            allow_external_test_root=True,
        )

        entries = specificity_receipt_entries(chain)
        self.assertEqual(len(entries), 1)
        self.assertEqual(resolve_receipt_finding(root, entries[0]), "secret.py")

    def test_artifact_writer_allowlists_finding_kind_before_receipt_projection(self):
        from core.vision_contract.frozen_frame import find_invented_specificity
        from scripts.vision_frozen_bench import ArtifactChainError, write_private_artifacts

        temp = tempfile.TemporaryDirectory(prefix="maez-frozen-kind-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        finding = find_invented_specificity(
            _two_label_case(self),
            "full_640",
            parse_and_validate("REGION: editor\nTEXT: secret.py"),
        )[0]
        malformed = replace(finding, kind="PRIVATE_LITERAL")

        with self.assertRaises(ArtifactChainError) as caught:
            write_private_artifacts(
                root,
                run_id="run-kind",
                transcripts={},
                invented_findings=(malformed,),
                allow_external_test_root=True,
            )

        self.assertEqual(caught.exception.reason, "diagnostic_schema_invalid")
        self.assertNotIn("PRIVATE_LITERAL", str(caught.exception))

    def test_receipt_diagnostic_path_must_be_normalized_relative_and_contained(self):
        from scripts.vision_frozen_bench import (
            ArtifactChainError,
            resolve_receipt_finding,
            specificity_receipt_entries,
        )

        root, chain, _, _ = self._chain()
        valid = specificity_receipt_entries(chain)[0]
        for path in ("/tmp/escape.json", "../escape.json", "runs/../escape.json"):
            with self.subTest(path=path):
                entry = {**valid, "diagnostic_path": path}
                with self.assertRaises(ArtifactChainError) as caught:
                    resolve_receipt_finding(root, entry)
                self.assertEqual(caught.exception.reason, "diagnostic_path_invalid")

    def test_diagnostic_and_transcript_are_quarantined_untrusted_artifacts(self):
        root, chain, _, _ = self._chain()
        for relative_path in (chain.diagnostic_path, chain.transcript_path):
            with self.subTest(relative_path=relative_path):
                artifact = json.loads((root / relative_path).read_bytes())
                self.assertEqual(artifact["artifact_class"], "UNTRUSTED")
                self.assertIs(artifact["quarantined"], True)
                self.assertIs(artifact["promotable"], False)
                self.assertEqual((root / relative_path).stat().st_mode & 0o777, 0o600)

    def test_artifact_writer_emits_no_literal_to_stdout_or_stderr(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            _, _, raw, literal = self._chain()
        self.assertNotIn(raw, stdout.getvalue() + stderr.getvalue())
        self.assertNotIn(literal, stdout.getvalue() + stderr.getvalue())


class VramReceiptTests(unittest.TestCase):
    def _imports(self):
        from scripts.vision_frozen_bench import (
            NvidiaSmiVramMeter,
            build_vram_witness,
        )

        return NvidiaSmiVramMeter, build_vram_witness

    def test_peak_after_load_uses_peak_of_fixed_post_readiness_window(self):
        NvidiaSmiVramMeter, _ = self._imports()
        samples = iter([100, 120, 110])
        meter = NvidiaSmiVramMeter(
            sample=lambda: next(samples),
            load_sample_count=3,
            poll_interval_seconds=0,
            sleeper=lambda _: None,
        )

        self.assertEqual(meter.peak_after_load(), 120)

    def test_image_peak_samples_before_during_and_after_complete_batch(self):
        NvidiaSmiVramMeter, _ = self._imports()
        events = []
        samples = iter([120, 130, 150, 140])
        in_batch_sample = threading.Event()
        sample_count = 0

        def sample():
            nonlocal sample_count
            sample_count += 1
            events.append("sample")
            if sample_count == 3:
                in_batch_sample.set()
            return next(samples)

        meter = NvidiaSmiVramMeter(
            sample=sample,
            poll_interval_seconds=0.001,
            sleeper=lambda _: None,
        )

        def batch():
            events.append("batch-start")
            self.assertTrue(in_batch_sample.wait(timeout=1))
            events.append("batch-end")
            return "complete"

        result, peak = meter.around_image_batch(batch)

        self.assertEqual(result, "complete")
        self.assertEqual(peak, 150)
        self.assertEqual(
            events,
            ["sample", "sample", "batch-start", "sample", "batch-end", "sample"],
        )

    def test_missing_either_peak_is_unscored_with_typed_reason(self):
        _, build_vram_witness = self._imports()
        cases = (
            (None, 150, "vram_after_load_missing"),
            (120, None, "vram_after_image_missing"),
            (None, None, "vram_after_load_missing"),
        )
        for after_load, after_image, reason in cases:
            with self.subTest(
                after_load=after_load,
                after_image=after_image,
            ):
                witness = build_vram_witness(after_load, after_image)
                self.assertEqual(witness.status, "unscored")
                self.assertEqual(witness.reason, reason)
                self.assertEqual(witness.vram_after_load_mib, after_load)
                self.assertEqual(witness.vram_after_image_mib, after_image)

        scored = build_vram_witness(120, 150)
        self.assertEqual(scored.status, "scored")
        self.assertIsNone(scored.reason)

    def test_inference_exception_stops_and_joins_polling_thread(self):
        NvidiaSmiVramMeter, _ = self._imports()
        meter = NvidiaSmiVramMeter(
            sample=lambda: 100,
            poll_interval_seconds=0.001,
            sleeper=lambda _: None,
        )

        with self.assertRaisesRegex(RuntimeError, "batch failed"):
            meter.around_image_batch(
                lambda: (_ for _ in ()).throw(RuntimeError("batch failed"))
            )

        time.sleep(0.01)
        self.assertFalse(
            any(
                thread.name == "maez-vision-vram-poller" and thread.is_alive()
                for thread in threading.enumerate()
            )
        )

    def test_poller_readiness_timeout_refuses_before_batch_and_joins_thread(self):
        NvidiaSmiVramMeter, _ = self._imports()
        release = threading.Event()
        sample_count = 0

        def sample():
            nonlocal sample_count
            sample_count += 1
            if sample_count == 2:
                release.wait(timeout=0.05)
            return 100

        timer = threading.Timer(0.02, release.set)
        timer.start()
        self.addCleanup(timer.join)
        meter = NvidiaSmiVramMeter(
            sample=sample,
            poll_interval_seconds=0.001,
            poller_ready_timeout_seconds=0.005,
            sleeper=lambda _: None,
        )
        batch_called = False

        def batch():
            nonlocal batch_called
            batch_called = True

        from scripts.vision_frozen_bench import VramSamplingError

        with self.assertRaises(VramSamplingError) as caught:
            meter.around_image_batch(batch)

        self.assertEqual(caught.exception.reason, "vram_poller_not_ready")
        self.assertFalse(batch_called)
        self.assertFalse(
            any(
                thread.name == "maez-vision-vram-poller" and thread.is_alive()
                for thread in threading.enumerate()
            )
        )

    def test_default_sampler_uses_only_literal_finite_nvidia_smi_query(self):
        NvidiaSmiVramMeter, _ = self._imports()
        from unittest import mock

        completed = mock.Mock(returncode=0, stdout="100\n200\n")
        with mock.patch("scripts.vision_frozen_bench.subprocess.run", return_value=completed) as run:
            self.assertEqual(NvidiaSmiVramMeter._sample_nvidia_smi(), 300)

        run.assert_called_once_with(
            [
                "/usr/bin/nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )

    def test_sampler_never_executes_path_shadowed_nvidia_smi(self):
        NvidiaSmiVramMeter, _ = self._imports()
        from unittest import mock

        temp = tempfile.TemporaryDirectory(prefix="maez-fake-nvidia-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        marker = root / "executed"
        fake = root / "nvidia-smi"
        fake.write_text(
            "#!/bin/sh\ntouch \"$MAEZ_FAKE_NVIDIA_MARKER\"\nprintf '999\\n'\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        with (
            mock.patch.dict(
                os.environ,
                {
                    "PATH": str(root),
                    "MAEZ_FAKE_NVIDIA_MARKER": str(marker),
                },
            ),
            mock.patch(
                "scripts.vision_frozen_bench._NVIDIA_SMI_PATH",
                Path("/definitely/missing/nvidia-smi"),
                create=True,
            ),
        ):
            self.assertIsNone(NvidiaSmiVramMeter._sample_nvidia_smi())

        self.assertFalse(marker.exists())


class _FakeVramMeter:
    def __init__(self, after_load=120, after_image=150):
        self.after_load = after_load
        self.after_image = after_image
        self.batch_calls = 0

    def peak_after_load(self):
        return self.after_load

    def around_image_batch(self, call):
        self.batch_calls += 1
        return call(), self.after_image


class EntryPointTests(unittest.TestCase):
    def _fixture(self):
        temp = tempfile.TemporaryDirectory(prefix="maez-frozen-e2e-")
        self.addCleanup(temp.cleanup)
        return _PrivateBenchFixture(Path(temp.name))

    def _server(self, *, content="REGION: titlebar\nTEXT: Settings"):
        server = ThreadingHTTPServer(("127.0.0.1", 0), _CandidateStub)
        server.model_id = "maez-vision"
        server.content = content
        server.seen = []
        server.redirect_models_to = None
        server.redirect_chat_to = None
        server.invalid_json = False
        server.response_payload = None
        server.response_sequence = []
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def _run(self, fixture, server, *, meter=None, run_id="run-e2e"):
        from scripts.vision_frozen_bench import main

        stdout = io.StringIO()
        stderr = io.StringIO()
        prior = os.environ.get("MAEZ_SCREEN_PERCEPTION")
        os.environ["MAEZ_SCREEN_PERCEPTION"] = "0  # comment"
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "--bench-root",
                        str(fixture.root),
                        "--candidate-label",
                        "candidate",
                        "--base-url",
                        f"http://127.0.0.1:{server.server_port}",
                        "--model",
                        "maez-vision",
                    ],
                    meter=meter or _FakeVramMeter(),
                    run_id=run_id,
                    allow_external_test_root=True,
                )
            self.assertEqual(
                os.environ.get("MAEZ_SCREEN_PERCEPTION"), "0  # comment"
            )
        finally:
            if prior is None:
                os.environ.pop("MAEZ_SCREEN_PERCEPTION", None)
            else:
                os.environ["MAEZ_SCREEN_PERCEPTION"] = prior
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_real_entrypoint_evaluates_one_candidate_and_writes_content_light_receipt(self):
        fixture = self._fixture()
        server = self._server()
        meter = _FakeVramMeter()

        exit_code, stdout, stderr = self._run(
            fixture, server, meter=meter, run_id="run-success"
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        output = json.loads(stdout)
        self.assertEqual(output["status"], "evaluated")
        self.assertEqual(output["run_id"], "run-success")
        self.assertEqual(output["receipt_path"], "receipts/run-success.json")
        self.assertEqual(meter.batch_calls, 1)
        self.assertEqual([seen[0] for seen in server.seen], ["GET", "POST", "POST", "POST"])

        receipt_bytes = (fixture.root / output["receipt_path"]).read_bytes()
        receipt = json.loads(receipt_bytes)
        self.assertEqual(receipt["status"], "evaluated")
        self.assertEqual(receipt["frame_count"], 1)
        self.assertEqual(receipt["vram_after_load_mib"], 120)
        self.assertEqual(receipt["vram_after_image_mib"], 150)
        self.assertEqual(
            [item["name"] for item in receipt["frames"][0]["transforms"]],
            list(TRANSFORM_ORDER),
        )
        self.assertEqual(
            receipt["frames"][0]["aggregate_coverage"],
            {
                "correct_text_numerator": 3,
                "correct_text_denominator": 3,
                "correct_text_coverage": 1.0,
                "abstention_numerator": 0,
                "abstention_denominator": 3,
                "abstention_coverage": 0.0,
            },
        )
        encoded = receipt_bytes.decode("utf-8") + stdout + stderr
        for private in ("Settings", "REGION:", "TEXT:", "data:image"):
            self.assertNotIn(private, encoded)
        transcript = json.loads(
            (fixture.root / receipt["transcript_artifact"]["path"]).read_bytes()
        )
        self.assertEqual(transcript["artifact_class"], "UNTRUSTED")
        self.assertIn("Settings", json.dumps(transcript))

    def test_invented_specificity_is_hard_fail_with_v11_diagnostic_chain(self):
        fixture = self._fixture()
        server = self._server(content="REGION: titlebar\nTEXT: secret.py")

        exit_code, stdout, _ = self._run(
            fixture,
            server,
            run_id="run-invented",
        )

        self.assertNotEqual(exit_code, 0)
        receipt = json.loads(
            (fixture.root / json.loads(stdout)["receipt_path"]).read_bytes()
        )
        self.assertEqual(receipt["status"], "hard_fail")
        findings = receipt["invented_specificity"]
        self.assertGreaterEqual(len(findings), 1)
        self.assertNotIn("secret.py", json.dumps(receipt))
        from scripts.vision_frozen_bench import resolve_receipt_finding

        self.assertEqual(resolve_receipt_finding(fixture.root, findings[0]), "secret.py")

    def test_rejected_unstructured_specificity_still_gets_v11_diagnostic_chain(self):
        fixture = self._fixture()
        server = self._server(content="I see secret.py in the editor")

        _, stdout, _ = self._run(
            fixture,
            server,
            run_id="run-rejected-invented",
        )

        receipt = json.loads(
            (fixture.root / json.loads(stdout)["receipt_path"]).read_bytes()
        )
        self.assertEqual(receipt["status"], "hard_fail")
        self.assertGreaterEqual(len(receipt["invented_specificity"]), 1)
        self.assertNotIn("secret.py", json.dumps(receipt))
        from scripts.vision_frozen_bench import resolve_receipt_finding

        self.assertEqual(
            resolve_receipt_finding(
                fixture.root,
                receipt["invented_specificity"][0],
            ),
            "secret.py",
        )

    def test_overlimit_raw_specificity_still_gets_v11_diagnostic_chain(self):
        fixture = self._fixture()
        server = self._server(content="secret.py " + ("x" * 70_000))

        _, stdout, _ = self._run(
            fixture,
            server,
            run_id="run-overlimit-invented",
        )

        receipt = json.loads(
            (fixture.root / json.loads(stdout)["receipt_path"]).read_bytes()
        )
        self.assertEqual(receipt["status"], "hard_fail")
        self.assertGreaterEqual(len(receipt["invented_specificity"]), 1)
        self.assertNotIn("secret.py", json.dumps(receipt))
        from scripts.vision_frozen_bench import resolve_receipt_finding

        self.assertEqual(
            resolve_receipt_finding(
                fixture.root,
                receipt["invented_specificity"][0],
            ),
            "secret.py",
        )

    def test_missing_vram_peak_makes_candidate_unscored(self):
        fixture = self._fixture()
        server = self._server()

        _, stdout, _ = self._run(
            fixture,
            server,
            meter=_FakeVramMeter(after_image=None),
            run_id="run-no-vram",
        )

        receipt = json.loads(
            (fixture.root / json.loads(stdout)["receipt_path"]).read_bytes()
        )
        self.assertEqual(receipt["status"], "unscored")
        self.assertEqual(receipt["unscored_reason"], "vram_after_image_missing")

    def test_proven_hard_fail_precedes_missing_vram_axis(self):
        fixture = self._fixture()
        server = self._server(content="REGION: titlebar\nTEXT: secret.py")

        _, stdout, _ = self._run(
            fixture,
            server,
            meter=_FakeVramMeter(after_image=None),
            run_id="run-hard-no-vram",
        )

        receipt = json.loads(
            (fixture.root / json.loads(stdout)["receipt_path"]).read_bytes()
        )
        self.assertEqual(receipt["status"], "hard_fail")
        self.assertIs(receipt["vram_complete"], False)
        self.assertEqual(receipt["unscored_reason"], "vram_after_image_missing")
        self.assertGreaterEqual(len(receipt["invented_specificity"]), 1)

    def test_missing_labels_refuses_before_candidate_or_vram_work(self):
        fixture = self._fixture()
        fixture.label["labels"] = []
        fixture.write()
        server = self._server()
        meter = _FakeVramMeter()

        _, stdout, _ = self._run(
            fixture,
            server,
            meter=meter,
            run_id="run-refused",
        )

        output = json.loads(stdout)
        receipt = json.loads((fixture.root / output["receipt_path"]).read_bytes())
        self.assertEqual(output["status"], "refused")
        self.assertEqual(receipt["refusal_reason"], "labels_empty")
        self.assertEqual(server.seen, [])
        self.assertEqual(meter.batch_calls, 0)

    def test_mid_batch_protocol_failure_preserves_partial_truth_and_artifacts(self):
        fixture = self._fixture()
        server = self._server()
        server.response_sequence = [
            {"choices": [{"message": {"content": "REGION: titlebar\nTEXT: Settings"}}]},
            b"not-json",
        ]

        _, stdout, _ = self._run(
            fixture,
            server,
            run_id="run-partial-failure",
        )

        output = json.loads(stdout)
        receipt = json.loads((fixture.root / output["receipt_path"]).read_bytes())
        self.assertEqual(receipt["status"], "refused")
        self.assertEqual(receipt["refusal_reason"], "candidate_protocol_error")
        self.assertEqual(receipt["frame_count"], 1)
        self.assertEqual(receipt["vram_after_load_mib"], 120)
        self.assertIsNone(receipt["vram_after_image_mib"])
        self.assertIs(receipt["vram_complete"], False)
        self.assertEqual(len(receipt["frames"]), 1)
        transcript_path = fixture.root / receipt["transcript_artifact"]["path"]
        transcript = json.loads(transcript_path.read_bytes())
        self.assertIn("Settings", json.dumps(transcript))
        self.assertEqual([item[0] for item in server.seen], ["GET", "POST", "POST"])

    def test_in_repo_noncanonical_bench_root_refuses_without_writing(self):
        repo_root = Path(__file__).resolve().parent.parent
        temp = tempfile.TemporaryDirectory(
            prefix=".vision-unauthorized-",
            dir=repo_root,
        )
        self.addCleanup(temp.cleanup)
        fixture = type("Fixture", (), {"root": Path(temp.name)})()
        server = self._server()

        _, stdout, _ = self._run(
            fixture,
            server,
            run_id="run-unauthorized",
        )

        output = json.loads(stdout)
        self.assertEqual(output["status"], "refused")
        self.assertEqual(output["reason"], "bench_root_not_allowed")
        self.assertIsNone(output["receipt_path"])
        self.assertEqual(list(fixture.root.iterdir()), [])
        self.assertEqual(server.seen, [])

    def test_production_cli_default_rejects_external_bench_root(self):
        from scripts.vision_frozen_bench import main

        fixture = self._fixture()
        server = self._server()
        before = sorted(path.relative_to(fixture.root) for path in fixture.root.rglob("*"))
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "--bench-root",
                    str(fixture.root),
                    "--candidate-label",
                    "candidate",
                    "--base-url",
                    f"http://127.0.0.1:{server.server_port}",
                    "--model",
                    "maez-vision",
                ],
                meter=_FakeVramMeter(),
                run_id="run-external-default",
            )

        output = json.loads(stdout.getvalue())
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(output["status"], "refused")
        self.assertEqual(output["reason"], "bench_root_not_allowed")
        self.assertIsNone(output["receipt_path"])
        after = sorted(path.relative_to(fixture.root) for path in fixture.root.rglob("*"))
        self.assertEqual(after, before)
        self.assertEqual(server.seen, [])


class ContainmentTests(unittest.TestCase):
    def test_runner_has_no_capture_service_sensor_or_cognition_write_surface(self):
        source_path = Path("scripts/vision_frozen_bench.py")
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        banned_import_prefixes = (
            "daemon",
            "skills.screen_perception",
            "core.cognition",
            "core.memory",
            "core.audit",
            "mss",
            "pyscreenshot",
            "PIL.ImageGrab",
        )
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for module in imported:
            self.assertFalse(module.startswith(banned_import_prefixes), module)
        self.assertNotIn("MAEZ_SCREEN_PERCEPTION", source)
        self.assertNotIn("systemctl", source)
        self.assertNotIn("llama-vision.service", source)

        subprocess_calls = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
            ):
                subprocess_calls.append(node)
        self.assertEqual(len(subprocess_calls), 1)
        literal_command = ast.literal_eval(subprocess_calls[0].args[0])
        self.assertEqual(literal_command[0], "/usr/bin/nvidia-smi")

    def test_private_corpus_path_is_gitignored(self):
        completed = subprocess.run(
            [
                "git",
                "check-ignore",
                "--no-index",
                "local/vision_bench/frames/frame.png",
            ],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_label_format_and_non_admission_boundary_are_documented(self):
        doc = Path("docs/slices/vision-organ/frozen-frame-label-format.md")
        self.assertTrue(doc.is_file())
        text = doc.read_text(encoding="utf-8").lower()
        for required in (
            "owner_human",
            "owner_approved",
            "third_party_content_reviewed",
            "active_window_crop",
            "region_aliases",
            "visible_in",
            "correct-text coverage",
            "abstention coverage",
            "evidence monotonicity",
            "diagnostic_sha256",
            "manual",
            "does not admit",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()


def _declared_blank_case(test: unittest.TestCase, declared=("full_640",)):
    """A case whose labels are visible only at higher transforms, with the
    owner EXPLICITLY declaring that nothing is readable at `declared`."""
    temp = tempfile.TemporaryDirectory(prefix="maez-frozen-blank-")
    test.addCleanup(temp.cleanup)
    fixture = _PrivateBenchFixture(Path(temp.name))
    fixture.label["labels"] = [
        {
            "label_id": "cmd-1",
            "region_id": "titlebar",
            "region_aliases": ["titlebar", "window title"],
            "kind": "filename",
            "text": "deploy.sh",
            "visible_in": ["full_1280", "active_native"],
        }
    ]
    fixture.label["no_readable_labels_at"] = list(declared)
    fixture.write()
    return load_frame_case(fixture.root, fixture.frame_id)


class DeclaredUnreadableTransformTests(unittest.TestCase):
    """Owner may declare a transform legitimately unreadable (2026-08-17).

    Frame-003 of the live corpus has no label legible at full_640 (a 0.281x
    downscale of a terminal). The harness refused the WHOLE run for it. A
    resolution where nothing is legible is a real measurement, not a corpus
    defect -- but it must be AUTHORED, never inferred, or a forgotten label
    silently becomes a pass.
    """

    def test_declared_blank_transform_scores_vacuously_instead_of_refusing(self):
        _, _, _, score_transform = _scoring_imports()
        case = _declared_blank_case(self)
        score = score_transform(case, "full_640", parse_and_validate("NO_TEXT_VISIBLE"))
        self.assertEqual(score.transform_name, "full_640")
        self.assertEqual(score.coverage.correct_text_denominator, 0)
        self.assertEqual(score.coverage.correct_text_numerator, 0)
        self.assertEqual(score.coverage.abstention_denominator, 0)
        self.assertEqual(score.coverage.abstention_numerator, 0)

    def test_undeclared_empty_labels_still_refuse(self):
        """The author-forgot case must stay caught."""
        ScoringRefusal, _, _, score_transform = _scoring_imports()
        case = _declared_blank_case(self, declared=())
        with self.assertRaises(ScoringRefusal) as caught:
            score_transform(case, "full_640", parse_and_validate("NO_TEXT_VISIBLE"))
        self.assertEqual(caught.exception.reason, "labels_empty_for_transform")

    def test_declaring_a_transform_that_has_labels_is_a_contradiction(self):
        """The declaration must not be usable to suppress real ground truth."""
        with self.assertRaises(HarnessRefusal) as caught:
            _declared_blank_case(self, declared=("full_1280",))
        self.assertEqual(caught.exception.reason, "label_schema_invalid")

    def test_invented_text_at_a_declared_blank_transform_is_still_caught(self):
        """A blank transform is the strongest hallucination trap, not a free pass."""
        from core.vision_contract.frozen_frame import find_invented_specificity_in_text

        case = _declared_blank_case(self)
        findings = find_invented_specificity_in_text(
            case, "full_640", "The terminal shows main.py open in the editor."
        )
        self.assertTrue(findings, "claiming unreadable content must still be flagged")
        self.assertEqual(findings[0].kind, "filename")
        self.assertEqual(findings[0].value, "main.py")
        self.assertEqual(findings[0].transform_name, "full_640")

    def test_a_claim_matching_higher_transform_truth_is_still_invented_when_blank(self):
        """Truth legible at 1280 is NOT licence to claim it at 640."""
        from core.vision_contract.frozen_frame import find_invented_specificity_in_text

        case = _declared_blank_case(self)
        # deploy.sh IS owner truth -- but only at full_1280 and richer. Claiming
        # it at the declared-blank 640 must still be invented, or truth would
        # leak downward into a transform where nothing is legible.
        findings = find_invented_specificity_in_text(
            case, "full_640", "The terminal shows deploy.sh."
        )
        self.assertTrue(findings, "higher-resolution truth must not excuse a 640 claim")
        self.assertEqual([f.value for f in findings], ["deploy.sh"])

    def test_the_same_claim_is_NOT_invented_where_the_owner_labelled_it(self):
        """Control for the test above: at full_1280 deploy.sh is real truth."""
        from core.vision_contract.frozen_frame import find_invented_specificity_in_text

        case = _declared_blank_case(self)
        self.assertEqual(
            find_invented_specificity_in_text(case, "full_1280", "The terminal shows deploy.sh."),
            (),
        )

    def test_declaring_a_RICHER_transform_blank_is_rejected(self):
        """Legibility cannot decrease as resolution rises (gate finding 2)."""
        with self.assertRaises(HarnessRefusal) as caught:
            _declared_blank_case(self, declared=("active_native",))
        self.assertEqual(caught.exception.reason, "label_schema_invalid")

    def test_a_directly_constructed_contradiction_is_refused_at_the_gate(self):
        """The invariant is not loader-only (gate finding 1)."""
        ScoringRefusal, _, _, score_transform = _scoring_imports()
        case = _declared_blank_case(self)
        forged = replace(
            case,
            labels=tuple(
                replace(label, visible_in=("full_640", "full_1280", "active_native"))
                for label in case.labels
            ),
        )
        with self.assertRaises(ScoringRefusal) as caught:
            score_transform(forged, "full_640", parse_and_validate("NO_TEXT_VISIBLE"))
        self.assertEqual(caught.exception.reason, "blank_declaration_contradicted")

    def test_monotonicity_tolerates_a_declared_blank_transform(self):
        _, aggregate_coverage, check_evidence_monotonicity, score_transform = _scoring_imports()
        case = _declared_blank_case(self)
        verdicts = {name: parse_and_validate("NO_TEXT_VISIBLE") for name in TRANSFORM_ORDER}
        findings = check_evidence_monotonicity(case, verdicts)
        self.assertEqual(findings, ())
        agg = aggregate_coverage(tuple(score_transform(case, n, verdicts[n]) for n in TRANSFORM_ORDER))
        # the blank transform contributes 0/0 and does not inflate any denominator
        self.assertEqual(agg.correct_text_denominator, 2)

    def test_hallucinated_fields_at_a_blank_transform_do_not_crash_monotonicity(self):
        _, _, check_evidence_monotonicity, _ = _scoring_imports()
        case = _declared_blank_case(self)
        verdicts = {
            "full_640": parse_and_validate("REGION: titlebar\nTEXT: main.py"),
            "full_1280": parse_and_validate("NO_TEXT_VISIBLE"),
            "active_native": parse_and_validate("NO_TEXT_VISIBLE"),
        }
        check_evidence_monotonicity(case, verdicts)

    def test_transcribing_at_a_declared_blank_transform_is_counted(self):
        """Claiming to READ what the owner declared illegible (2026-08-17).

        The re-run after the prompt fix showed both LFM candidates returning
        ok with fields at frame-003/full_640 -- the transform the owner
        personally confirmed unreadable -- and the receipt could not say
        whether those fields were honest [UNREADABLE] or fabrication. This
        closes that: a transcribed or partial field at a declared-blank
        transform is a claim to have read the unreadable, detectable from a
        provenance count with no knowledge of content.
        """
        _, _, _, score_transform = _scoring_imports()
        case = _declared_blank_case(self)

        honest = score_transform(
            case, "full_640", parse_and_validate("REGION: titlebar\nTEXT: [UNREADABLE]")
        )
        self.assertEqual(honest.declared_blank_transcribed_count, 0)

        fabricated = score_transform(
            case, "full_640", parse_and_validate("REGION: titlebar\nTEXT: Settings")
        )
        self.assertEqual(fabricated.declared_blank_transcribed_count, 1)

        partial = score_transform(
            case,
            "full_640",
            parse_and_validate("REGION: titlebar\nTEXT: Set [UNREADABLE]"),
        )
        self.assertEqual(
            partial.declared_blank_transcribed_count,
            1,
            "a partial claim still asserts some text was read",
        )

    def test_abstaining_at_a_declared_blank_transform_costs_nothing(self):
        _, _, _, score_transform = _scoring_imports()
        case = _declared_blank_case(self)
        for raw in ("NO_TEXT_VISIBLE", "REGION: titlebar\nTEXT: [UNREADABLE]"):
            score = score_transform(case, "full_640", parse_and_validate(raw))
            self.assertEqual(score.declared_blank_transcribed_count, 0)
            self.assertEqual(score.coverage.correct_text_denominator, 0)

    def test_a_labelled_transform_reports_no_declared_blank_count(self):
        """The counter is meaningless where the owner DID supply truth."""
        _, _, _, score_transform = _scoring_imports()
        case = _declared_blank_case(self)
        score = score_transform(
            case, "full_1280", parse_and_validate("REGION: titlebar\nTEXT: deploy.sh")
        )
        self.assertEqual(score.declared_blank_transcribed_count, 0)


class DeclaredBlankBenchWiringTests(unittest.TestCase):
    """The bench must ACT on the counters, not merely record them (2026-08-17).

    Gate finding: the first three tests for this feature asserted only the
    dataclass counter, so deleting both bench additions would have left them
    green. These drive `_evaluate_frames` with a fake invoker so the
    hard-fail reason and the receipt projection are pinned to behaviour.
    """

    def _prepared(self):
        from scripts.vision_frozen_bench import PreparedFrame
        from core.vision_contract.frozen_frame import derive_transforms

        case = _declared_blank_case(self)
        return case, (PreparedFrame(case=case, transforms=derive_transforms(case)),)

    class _FakeInvoker:
        """Returns a scripted raw string per transform, in TRANSFORM_ORDER."""

        def __init__(self, by_transform):
            self._by = by_transform
            self._order = list(TRANSFORM_ORDER)
            self._i = 0
            self.last_raw = None

        def invoke(self, image_png):
            name = self._order[self._i % len(self._order)]
            self._i += 1
            self.last_raw = self._by[name]
            return parse_and_validate(self.last_raw)

    def _run(self, by_transform):
        from scripts.vision_frozen_bench import _evaluate_frames

        _, prepared = self._prepared()
        receipts, _invented, reasons = _evaluate_frames(
            prepared, self._FakeInvoker(by_transform), {}
        )
        return receipts, reasons

    def test_transcribing_at_declared_blank_raises_the_bench_hard_fail(self):
        receipts, reasons = self._run(
            {
                "full_640": "REGION: titlebar\nTEXT: Settings",
                "full_1280": "REGION: titlebar\nTEXT: deploy.sh",
                "active_native": "REGION: titlebar\nTEXT: deploy.sh",
            }
        )
        self.assertIn("transcribed_at_declared_blank", reasons)
        blank = next(
            row
            for row in receipts[0]["coverage_by_transform"]
            if row["transform"] == "full_640"
        )
        self.assertEqual(blank["declared_blank_transcribed_count"], 1)

    def test_region_smuggling_at_declared_blank_raises_its_own_reason(self):
        """`REGION: Settings / TEXT: [UNREADABLE]` reads text in the label."""
        receipts, reasons = self._run(
            {
                "full_640": "REGION: Settings\nTEXT: [UNREADABLE]",
                "full_1280": "REGION: titlebar\nTEXT: deploy.sh",
                "active_native": "REGION: titlebar\nTEXT: deploy.sh",
            }
        )
        self.assertIn("unknown_region_at_declared_blank", reasons)
        self.assertNotIn("transcribed_at_declared_blank", reasons)
        blank = next(
            row
            for row in receipts[0]["coverage_by_transform"]
            if row["transform"] == "full_640"
        )
        self.assertEqual(blank["declared_blank_unknown_region_count"], 1)

    def test_honest_abstention_at_declared_blank_raises_neither_reason(self):
        _receipts, reasons = self._run(
            {
                "full_640": "REGION: titlebar\nTEXT: [UNREADABLE]",
                "full_1280": "REGION: titlebar\nTEXT: deploy.sh",
                "active_native": "REGION: titlebar\nTEXT: deploy.sh",
            }
        )
        self.assertNotIn("transcribed_at_declared_blank", reasons)
        self.assertNotIn("unknown_region_at_declared_blank", reasons)
