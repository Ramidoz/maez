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
