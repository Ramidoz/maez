"""maez-web managed unit: reachability for the S7 cockpit surface.

The S7 WebAuthn proof surface lives in skills/web_interface.py on loopback
127.0.0.1:11437. For the owner to ever reach the cockpit pointer, that surface
must run as a managed unit. This asserts:

  1. scripts/maez-web.template.service renders an ExecStart that launches the
     venv python on skills/web_interface.py, and is loopback/hardened.
  2. scripts/install.sh names maez-web.service alongside maez.service in the
     enable hints (so the installer tells the owner to enable it).

No real systemd is touched. We render the template with sed-style placeholder
substitution exactly as install.sh does, and read install.sh as text. A fake
systemctl is unnecessary because install.sh only EMITS the enable command as a
hint string; we assert on that intent string.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _render(template_text: str, *, home: str, user: str, uid: str) -> str:
    return (
        template_text.replace("__MAEZ_HOME__", home)
        .replace("__MAEZ_USER__", user)
        .replace("__MAEZ_UID__", uid)
    )


class MaezWebUnitTemplateTest(unittest.TestCase):
    def setUp(self):
        self.template_path = os.path.join(
            REPO_ROOT, "scripts", "maez-web.template.service"
        )
        self.install_path = os.path.join(REPO_ROOT, "scripts", "install.sh")

    def test_template_exists(self):
        self.assertTrue(
            os.path.isfile(self.template_path),
            "scripts/maez-web.template.service must exist",
        )

    def test_rendered_execstart_launches_web_interface_on_venv_python(self):
        with open(self.template_path, encoding="utf-8") as fh:
            rendered = _render(
                fh.read(),
                home="/fake/home/maez",
                user="fakeuser",
                uid="4242",
            )
        exec_lines = [
            ln.strip()
            for ln in rendered.splitlines()
            if ln.strip().startswith("ExecStart=")
        ]
        self.assertEqual(len(exec_lines), 1, "exactly one ExecStart expected")
        exec_line = exec_lines[0]
        self.assertIn("/fake/home/maez/.venv/bin/python", exec_line)
        self.assertIn("/fake/home/maez/skills/web_interface.py", exec_line)
        # No placeholders left unsubstituted.
        self.assertNotIn("__MAEZ_", rendered)

    def test_template_is_loopback_and_after_maez_service(self):
        with open(self.template_path, encoding="utf-8") as fh:
            text = fh.read()
        # Ordering: starts after the daemon.
        after = [
            ln for ln in text.splitlines() if ln.strip().startswith("After=")
        ]
        self.assertTrue(after, "After= ordering required")
        self.assertTrue(
            any("maez.service" in ln for ln in after),
            "maez-web must order After=maez.service",
        )
        # Loopback note / binding — the surface is bound to 127.0.0.1:11437 in
        # web_interface.py; the unit documents the loopback contract.
        self.assertIn("127.0.0.1:11437", text)

    def test_template_is_hardened(self):
        with open(self.template_path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("ProtectSystem=strict", text)
        self.assertIn("ProtectHome=read-only", text)
        self.assertIn("NoNewPrivileges=true", text)

    def test_install_sh_enables_maez_web_alongside_maez_service(self):
        with open(self.install_path, encoding="utf-8") as fh:
            install_text = fh.read()
        enable_lines = [
            ln
            for ln in install_text.splitlines()
            if "systemctl enable --now" in ln or "enable --now maez.service" in ln
        ]
        self.assertTrue(
            enable_lines, "install.sh must emit enable hints for maez.service"
        )
        for ln in enable_lines:
            self.assertIn(
                "maez-web.service",
                ln,
                f"enable hint must include maez-web.service: {ln!r}",
            )
            # maez.service still present (we added alongside, not replaced).
            self.assertTrue(
                re.search(r"\bmaez\.service\b", ln),
                f"maez.service must remain in the hint: {ln!r}",
            )


if __name__ == "__main__":
    unittest.main()
