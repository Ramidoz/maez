# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""GitHub nightly publish — 2026-04-24 README-overwrite regression.

For weeks, `skills.github_publish.GitHubPublisher.publish_nightly`
had been regenerating README.md from a hardcoded template at 23:00
CDT every night, wiping out deliberate voice work (grandmother
framing, Stand-from-JoJo framing, launch-prep polish). The template
also carried the role-label leak ("Built By: the owner") that the
same-day voice fix had just closed elsewhere. Log witnesses:

  2026-04-11 23:00:07 [GITHUB] Published — Update docs: reflect
                                new agent architecture and task progress
  2026-04-23 23:00:11 [GITHUB] Published — Update docs: reflect
                                new modular agent architecture

These tests lock the removal in so a future refactor can't silently
reintroduce the autonomous README regeneration."""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class WriteReadmeRemoved(unittest.TestCase):
    def test_write_readme_method_is_gone(self):
        from skills.github_publish import GitHubPublisher
        self.assertFalse(
            hasattr(GitHubPublisher, "_write_readme"),
            "_write_readme was re-introduced on GitHubPublisher — "
            "see 2026-04-24 voice-regression note in github_publish.py",
        )


class PublishNightlyDoesNotStageReadme(unittest.TestCase):
    """publish_nightly must not stage README.md via `git add`.

    Inspects the source of `publish_nightly` directly. A source-level
    regression guard is the right shape here — a behavioral test
    would need to mock subprocess, the GitHub REST API, the LLM
    client, and the filesystem; all of that mocking is more code
    than the guard protects. The hardcoded git-add list is the exact
    thing we're locking down, so source inspection is authoritative."""

    def test_source_has_no_readme_staging(self):
        from skills.github_publish import GitHubPublisher
        src = inspect.getsource(GitHubPublisher.publish_nightly)
        self.assertNotIn(
            "'README.md'", src,
            "publish_nightly stages README.md — that path was removed "
            "2026-04-24 after weeks of autonomous voice-overwrites. "
            "If you have a good reason to re-enable, route README "
            "through handle_message + audit_assistant_text, do not "
            "regenerate from a hardcoded template.",
        )
        self.assertNotIn(
            '"README.md"', src,
            "publish_nightly stages README.md (double-quoted form).",
        )

    def test_source_has_no_write_readme_call(self):
        # Assert no invocation — bare token matches (comments mentioning
        # the historical method for context are fine; a function call
        # like `self._write_readme()` or `GitHubPublisher._write_readme`
        # is the regression we block).
        from skills.github_publish import GitHubPublisher
        src = inspect.getsource(GitHubPublisher.publish_nightly)
        self.assertNotIn("_write_readme(", src)
        self.assertNotIn("self._write_readme", src)


class GeneratedCommitMessageDoesNotClaimReadme(unittest.TestCase):
    """The nightly commit-message prompt used to tell the LLM to
    describe 'updating README.md, PROGRESS_PUBLIC.md, and soul.md'.
    README.md is no longer touched — the prompt must not claim it
    is, or the committed message will misdescribe the change."""

    def test_prompt_does_not_mention_readme(self):
        from skills.github_publish import GitHubPublisher
        src = inspect.getsource(GitHubPublisher._generate_commit_message)
        # Prompt string is embedded in the source; scan line-by-line.
        prompt_lines = [
            line for line in src.splitlines()
            if "README.md" in line and "#" not in line.split("README.md")[0]
        ]
        # Comments mentioning README.md in the change rationale are
        # allowed; only live prompt-string references are rejected.
        live_refs = [
            line for line in prompt_lines
            if "'" in line or '"' in line
        ]
        self.assertEqual(
            [l for l in live_refs if "README.md" in l
                                   and ("'" in l or '"' in l)
                                   and "#" not in l[:l.index("README.md")]],
            [],
            "Commit-message prompt still instructs the LLM to "
            "describe README.md changes.",
        )


if __name__ == "__main__":
    unittest.main()
