# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""GitHub Limb v0.1 — owner-account provenance survives to the egress chokepoint.

The producer (github_skill) must emit ProvenancedText(owner_account_context),
and that span must reach the real subscription-proxy path and be refused (403,
adapter not called). No "tag then flatten": the witness is the door refusing it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class OwnerAccountFactoryTests(unittest.TestCase):
    def test_factory_emits_owner_account_context_span_not_downgraded(self):
        from core.egress.provenance import ProvenancedText

        pt = ProvenancedText.owner_account_context(
            "private repo: secret-thing",
            source_ref="github:user_repos",
        )
        self.assertEqual(len(pt.spans), 1)
        span = pt.spans[0]
        self.assertEqual(span.origin_class, "owner_account_context")
        self.assertFalse(span.redaction_allowed)
        self.assertEqual(span.text, "private repo: secret-thing")
        self.assertEqual(pt.text, "private repo: secret-thing")


if __name__ == "__main__":
    unittest.main()
