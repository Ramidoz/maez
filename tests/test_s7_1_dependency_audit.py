"""S7.1 WebAuthn dependency posture tests."""

from __future__ import annotations

import unittest
from pathlib import Path
import tomllib


class S71DependencyAuditTests(unittest.TestCase):
    def _pyproject(self):
        return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    def test_018_webauthn_extra_is_optional_not_core_runtime(self):
        project = self._pyproject()["project"]
        core_deps = "\n".join(project["dependencies"])

        self.assertNotIn("webauthn", core_deps.lower())
        self.assertIn("s7-webauthn", project["optional-dependencies"])

    def test_019_s7_webauthn_extra_uses_reviewed_bounded_webauthn_version(self):
        extra = self._pyproject()["project"]["optional-dependencies"]["s7-webauthn"]

        self.assertEqual(extra, ["webauthn>=2.7.1,<2.8"])

    def test_020_all_extra_includes_reviewed_s7_webauthn_extra(self):
        all_extra = self._pyproject()["project"]["optional-dependencies"]["all"]

        self.assertTrue(any("s7-webauthn" in entry for entry in all_extra))

    def test_023_dependency_audit_records_license_security_and_transitives(self):
        text = Path(
            "docs/slices/s7.1-local-webauthn-ceremony/dependency-audit.md"
        ).read_text(encoding="utf-8")

        for required in (
            "webauthn 2.7.1",
            "BSD-3-Clause",
            "OSV query on 2026-05-18: 0 known vulnerabilities",
            "pyasn1>=0.6.2",
            "cbor2>=5.6.5",
            "cryptography>=44.0.2",
            "pyOpenSSL>=25.0.0",
            "fido2 2.2.0",
            "not selected",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
