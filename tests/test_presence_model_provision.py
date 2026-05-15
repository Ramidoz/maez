import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts import provision_presence_model
from skills import presence_perception


class FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self):
        return self._data


class PresenceModelProvisionTests(unittest.TestCase):
    def test_model_constants_match_presence_runtime_path(self):
        self.assertEqual(
            Path(presence_perception.MODEL_PATH).name,
            provision_presence_model.MODEL_FILENAME,
        )
        self.assertEqual(
            "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f",
            provision_presence_model.MODEL_SHA256,
        )

    def test_provision_writes_verified_model_bytes(self):
        payload = b"fake-tflite-model"
        expected_sha = hashlib.sha256(payload).hexdigest()

        def fake_urlopen(_url, timeout):
            self.assertEqual(30, timeout)
            return FakeResponse(payload)

        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "blaze_face.tflite"
            written = provision_presence_model.provision_model(
                model_path=model_path,
                expected_sha256=expected_sha,
                urlopen=fake_urlopen,
            )

            self.assertEqual(model_path, written)
            self.assertEqual(payload, model_path.read_bytes())

    def test_provision_rejects_hash_mismatch(self):
        def fake_urlopen(_url, timeout):
            return FakeResponse(b"wrong-model")

        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "blaze_face.tflite"
            with self.assertRaises(provision_presence_model.ModelHashError):
                provision_presence_model.provision_model(
                    model_path=model_path,
                    expected_sha256="0" * 64,
                    urlopen=fake_urlopen,
                )
            self.assertFalse(model_path.exists())

    def test_provision_rejects_non_https_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "blaze_face.tflite"
            with self.assertRaises(provision_presence_model.ModelProvisionError):
                provision_presence_model.provision_model(
                    model_path=model_path,
                    url="http://example.invalid/model.tflite",
                    urlopen=lambda _url, timeout: FakeResponse(b"unused"),
                )

    def test_provision_rejects_oversized_payload(self):
        payload = b"x" * 8

        def fake_urlopen(_url, timeout):
            return FakeResponse(payload)

        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "blaze_face.tflite"
            with self.assertRaises(provision_presence_model.ModelProvisionError):
                provision_presence_model.provision_model(
                    model_path=model_path,
                    expected_sha256=hashlib.sha256(payload).hexdigest(),
                    max_bytes=4,
                    urlopen=fake_urlopen,
                )
            self.assertFalse(model_path.exists())

    def test_provision_rejects_symlink_target(self):
        payload = b"fake-tflite-model"

        def fake_urlopen(_url, timeout):
            return FakeResponse(payload)

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "actual.tflite"
            target.write_bytes(b"old")
            model_path = Path(tmp) / "blaze_face.tflite"
            model_path.symlink_to(target)
            with self.assertRaises(provision_presence_model.ModelProvisionError):
                provision_presence_model.provision_model(
                    model_path=model_path,
                    expected_sha256=hashlib.sha256(payload).hexdigest(),
                    urlopen=fake_urlopen,
                )

    def test_provision_final_file_is_not_group_or_world_writable(self):
        payload = b"fake-tflite-model"

        def fake_urlopen(_url, timeout):
            return FakeResponse(payload)

        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "blaze_face.tflite"
            provision_presence_model.provision_model(
                model_path=model_path,
                expected_sha256=hashlib.sha256(payload).hexdigest(),
                urlopen=fake_urlopen,
            )

            self.assertFalse(model_path.with_suffix(".tflite.tmp").exists())
            self.assertEqual(0, model_path.stat().st_mode & 0o022)

    def test_existing_valid_model_is_permission_hardened_before_return(self):
        payload = b"fake-tflite-model"
        expected_sha = hashlib.sha256(payload).hexdigest()

        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "blaze_face.tflite"
            model_path.write_bytes(payload)
            model_path.chmod(0o666)

            provision_presence_model.provision_model(
                model_path=model_path,
                expected_sha256=expected_sha,
                urlopen=lambda _url, timeout: self.fail("valid model should not download"),
            )

            self.assertEqual(0, model_path.stat().st_mode & 0o022)


if __name__ == "__main__":
    unittest.main()
