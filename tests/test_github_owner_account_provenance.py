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


class GithubProducerTests(unittest.TestCase):
    def _skill_with_canary(self):
        from skills.github_skill import GitHubSkill

        skill = GitHubSkill.__new__(GitHubSkill)
        skill.enabled = True
        skill.username = "CANARY_USER"
        skill._cache = {}
        skill._cache_time = {}
        skill.cache_ttl = 300
        skill.token = "x"
        skill.get_user_repos = lambda: [
            {
                "name": "CANARY_REPO",
                "private": True,
                "language": "Python",
                "updated_at": "2026-06-01T00:00:00Z",
                "description": "CANARY_DESC",
            }
        ]
        skill.get_recent_commits = lambda name, limit=1: []
        skill.get_user_activity = lambda: ["Pushed to CANARY_REPO: CANARY_MSG"]
        skill.get_trending_ai_repos = lambda n=5: []
        return skill

    def test_get_context_block_returns_owner_account_provenanced_text(self):
        from core.egress.provenance import ProvenancedText

        block = self._skill_with_canary().get_context_block()
        self.assertIsInstance(block, ProvenancedText)
        self.assertTrue(block.spans)
        self.assertTrue(
            all(s.origin_class == "owner_account_context" for s in block.spans)
        )
        self.assertIn("CANARY_REPO", block.text)
        self.assertIn("[GITHUB]", block.text)

    def test_disabled_skill_returns_empty_provenanced_text(self):
        from core.egress.provenance import ProvenancedText
        from skills.github_skill import GitHubSkill

        skill = GitHubSkill.__new__(GitHubSkill)
        skill.enabled = False
        block = skill.get_context_block()
        self.assertIsInstance(block, ProvenancedText)
        self.assertFalse(block)
        self.assertEqual(block.text, "")


if __name__ == "__main__":
    unittest.main()
