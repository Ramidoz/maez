"""Legacy face-enrollment artifact permission guards.

Camera Presence v1 removes recognition from the live daemon path, but the
manual legacy enrollment artifact remains biometric state. If retained, it must
be owner-only on disk.
"""

from __future__ import annotations

import os
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FaceEnrollmentBiometricPermissionTests(unittest.TestCase):
    def test_save_enrollment_writes_owner_only_file_under_owner_only_directory(self):
        from skills import face_enrollment

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "face" / "rohit_embeddings.pkl"

            face_enrollment._save_enrollment_data(path, {"embeddings": []})

            self.assertEqual(0o700, path.parent.stat().st_mode & 0o777)
            self.assertEqual(0o600, path.stat().st_mode & 0o777)

    def test_load_enrollment_rejects_permissive_biometric_artifact(self):
        from skills import face_enrollment

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "face" / "rohit_embeddings.pkl"
            path.parent.mkdir()
            path.write_bytes(pickle.dumps({"embeddings": []}))
            path.parent.chmod(0o755)
            path.chmod(0o644)

            with patch.object(face_enrollment, "ENROLLMENT_PATH", str(path)):
                loaded = face_enrollment.load_enrollment()

            self.assertIsNone(loaded)

    def test_load_enrollment_accepts_owner_only_biometric_artifact(self):
        from skills import face_enrollment

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "face" / "rohit_embeddings.pkl"
            path.parent.mkdir(mode=0o700)
            path.write_bytes(pickle.dumps({"embeddings": ["fake"]}))
            os.chmod(path, 0o600)

            with patch.object(face_enrollment, "ENROLLMENT_PATH", str(path)):
                loaded = face_enrollment.load_enrollment()

            self.assertEqual({"embeddings": ["fake"]}, loaded)


if __name__ == "__main__":
    unittest.main()
