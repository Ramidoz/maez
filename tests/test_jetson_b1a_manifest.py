import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import tests._jetson_edge_path  # noqa: F401
from jetson_presence.b1a import manifest as man

SETUP_SCRIPT = Path(__file__).resolve().parents[1] / "devices" / "jetson_presence" / "setup_models.sh"


class ManifestSchemaTests(unittest.TestCase):
    def test_source_pack_has_required_fields_and_truthful_license(self):
        pack = man.load_manifest()["source_pack"]
        self.assertTrue({"name", "url", "sha256", "license"} <= set(pack))
        self.assertTrue(pack["url"].endswith(".zip"))  # models ship as a zip pack
        # the MODEL license must be stated truthfully, not inherited from the MIT code:
        self.assertIn("non-commercial", pack["license"].lower())

    def test_real_manifest_has_required_fields_per_model(self):
        m = man.load_manifest()  # default path = devices/jetson_presence/models/manifest.json
        self.assertIn("models", m)
        self.assertGreaterEqual(len(m["models"]), 2)  # detector + embedding
        required = {"name", "role", "member", "sha256", "input_shape", "precision", "engine_path"}
        for entry in m["models"]:
            self.assertTrue(required <= set(entry), f"missing fields in {entry.get('name')}")
            self.assertTrue(entry["member"].endswith(".onnx"))  # extracted from the pack
        roles = {e["role"] for e in m["models"]}
        self.assertEqual(roles, {"detector", "embedding"})
        names = {e["name"] for e in m["models"]}
        self.assertTrue(any("scrfd" in n.lower() for n in names))
        self.assertTrue(any("arcface" in n.lower() or "w600k" in n.lower() for n in names))

    def test_precision_is_explicit_fp32_or_fp16(self):
        for entry in man.load_manifest()["models"]:
            self.assertIn(entry["precision"], ("fp32", "fp16"))

    def test_shipped_manifest_is_locked_with_real_digests(self):
        # We ship REAL pinned hashes measured from the official immutable release,
        # not PENDING sentinels — the device build verifies against these, so there
        # is no trust-on-first-use window.
        self.assertTrue(man.hashes_locked(man.load_manifest()))

    def test_trtexec_shape_args_come_from_manifest_shapes(self):
        entries = {entry["role"]: entry for entry in man.load_manifest()["models"]}

        self.assertEqual(man.trtexec_shape_arg(entries["detector"]), "input.1:1x3x640x640")
        self.assertEqual(man.trtexec_shape_arg(entries["embedding"]), "input.1:1x3x112x112")
        self.assertEqual(
            man.trtexec_shape_arg(entries["embedding"], input_name="data"),
            "data:1x3x112x112",
        )

    def test_setup_build_passes_manifest_shape_to_trtexec(self):
        setup = SETUP_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('f"--shapes={man.trtexec_shape_arg(entry)}"', setup)


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
            with open(p, "wb") as f:
                f.write(data)
            self.assertTrue(man.verify_sha256(p, hashlib.sha256(data).hexdigest()))

    def test_verify_sha256_false_on_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "f.bin")
            with open(p, "wb") as f:
                f.write(b"hello-model")
            self.assertFalse(man.verify_sha256(p, "0" * 64))


if __name__ == "__main__":
    unittest.main()
