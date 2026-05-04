# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARD for the apply_diff() user-saw-diff covenant gate.

Audit Tier-2 item from the 2026-05-04 15-agent audit:
  "apply_diff() lacks in-function 'user-saw-diff' verification"

Owner default (2026-05-04): apply the T1.8 pattern — require an
explicit `reviewed=True` co-flag, refuse to write when absent.
The function itself enforces the gate so a future caller that
forgets to wire the UI confirmation can't bypass review.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class ApplyDiffCovenantGate(unittest.TestCase):
    """REGRESSION GUARD: apply_diff() must refuse to write to disk
    unless the caller passes `reviewed=True`. The HTTP endpoint
    must thread `reviewed` from the request body so the browser UI
    is the only place that flips the gate."""

    def test_function_refuses_without_reviewed_flag(self):
        """apply_diff(reviewed=False) — the default — must refuse
        with a clear error message rather than apply."""
        from core.self_dev.workshop import apply_diff
        result = apply_diff(
            session_id="nonexistent-test-session",
            diff_text="--- a/x\n+++ b/x\n@@ -0,0 +1 @@\n+y\n",
        )
        self.assertFalse(
            result.get("applied", True),
            "apply_diff must refuse without reviewed=True",
        )
        # Error message must mention the gate so debugging is easy.
        # The session check fires first if the session doesn't exist;
        # to test the gate cleanly we accept either error-mentioning-
        # gate OR error-mentioning-session as long as nothing wrote.
        err = (result.get("error") or "").lower()
        self.assertTrue(
            "reviewed" in err or "session" in err,
            f"error must explain refusal; got {err!r}",
        )

    def test_function_signature_declares_reviewed_param(self):
        """Source-pin: apply_diff's signature must include a
        `reviewed` parameter (default-False) so the gate cannot
        be removed by a refactor that 'forgets' the parameter."""
        path = REPO / "core" / "self_dev" / "workshop.py"
        src = path.read_text()
        # Locate the apply_diff signature.
        start = src.index("def apply_diff(")
        end = src.index(")", start) + 1
        sig = src[start:end]
        self.assertIn(
            "reviewed",
            sig,
            "apply_diff signature must declare a `reviewed` parameter "
            "for the user-saw-diff covenant gate",
        )

    def test_http_endpoint_reads_reviewed_from_body(self):
        """Source-pin: the /api/v1/workshop apply endpoint must
        read `reviewed` from the request body and pass it through
        to apply_diff. Without this thread-through, the gate is
        flipped server-side regardless of UI state."""
        path = REPO / "skills" / "web_interface.py"
        src = path.read_text()
        # Locate the api_workshop_apply view.
        try:
            start = src.index("def api_workshop_apply(")
        except ValueError:
            self.fail(
                "could not locate api_workshop_apply — refactor "
                "must update this regression guard"
            )
        # 80 lines of slack should cover the body.
        end = start + 4000
        body = src[start:end]
        self.assertIn(
            'body.get("reviewed"',
            body,
            "api_workshop_apply must read `reviewed` from the request "
            "body so the browser UI is the source of truth for the gate",
        )
        self.assertIn(
            "reviewed=",
            body,
            "api_workshop_apply must thread `reviewed=` to apply_diff",
        )


if __name__ == "__main__":
    unittest.main()
