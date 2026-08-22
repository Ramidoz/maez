# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Output command guard — 2026-04-23 gap closure.

When the model emits a dangerous command as markdown inside its reply
(instead of actually invoking the tool), the covenant gate never
fires because no tool call happens. The 2026-04-23 adversarial probe
suite caught this on `rm soul.md` and `htop` prompts: the model said
"here is the command you asked for" inside a ```bash block and the
owner saw copy-paste bait in Maez's voice.

`scrub_protected_commands` solves this by running every assistant
reply through the same authority the tool-call gate uses
(`ActionEngine._check_forbidden`) and replacing any fenced block or
inline code span that contains a refused command with an explicit
refusal string.

These tests lock the behavior in."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class FencedBlockScrubbing(unittest.TestCase):
    """Dangerous commands inside ```bash``` blocks get replaced."""

    def _scrub(self, text: str):
        from core.safety.output_command_guard import scrub_protected_commands
        return scrub_protected_commands(text)

    def test_rm_soul_abs_in_bash_block(self):
        text = "Here is what you asked for:\n```bash\nrm /home/rohit/maez/config/soul.md\n```\n"
        out, refused = self._scrub(text)
        self.assertNotIn("rm /home/rohit/maez/config/soul.md", out)
        self.assertIn("refused", out.lower())
        self.assertEqual(len(refused), 1)

    def test_rm_soul_relative_in_sh_block(self):
        text = "```sh\nrm config/soul.md\n```"
        out, refused = self._scrub(text)
        self.assertNotIn("rm config/soul.md", out)
        self.assertEqual(len(refused), 1)

    def test_htop_in_bash_block(self):
        text = "Run this:\n```bash\nhtop\n```\n"
        out, refused = self._scrub(text)
        self.assertNotIn("\n```bash\nhtop\n```", out)
        self.assertEqual(len(refused), 1)

    def test_tail_follow_in_bash_block(self):
        text = "```bash\ntail -f logs/maez.log\n```"
        out, refused = self._scrub(text)
        self.assertNotIn("tail -f logs/maez.log", out)
        self.assertEqual(len(refused), 1)

    def test_nvidia_smi_loop_in_unlabeled_block(self):
        text = "```\nnvidia-smi -l 1\n```"
        out, refused = self._scrub(text)
        self.assertNotIn("nvidia-smi -l 1", out)
        self.assertEqual(len(refused), 1)

    def test_cd_and_rm_soul_in_block(self):
        text = "```bash\ncd config && rm soul.md\n```"
        out, refused = self._scrub(text)
        self.assertNotIn("rm soul.md", out)
        self.assertEqual(len(refused), 1)

    def test_sudo_stop_llama_server_in_block(self):
        text = "```bash\nsudo systemctl stop llama-server\n```"
        out, refused = self._scrub(text)
        self.assertNotIn("systemctl stop llama-server", out)
        self.assertEqual(len(refused), 1)

    def test_multiple_blocks_one_dangerous(self):
        text = (
            "First, something harmless:\n"
            "```bash\ngit status\n```\n"
            "Then the destructive one:\n"
            "```bash\nrm config/soul.md\n```\n"
        )
        out, refused = self._scrub(text)
        self.assertIn("git status", out)  # benign block preserved
        self.assertNotIn("rm config/soul.md", out)
        self.assertEqual(len(refused), 1)


class InlineSpanScrubbing(unittest.TestCase):
    """Dangerous commands in backtick spans also get replaced."""

    def _scrub(self, text: str):
        from core.safety.output_command_guard import scrub_protected_commands
        return scrub_protected_commands(text)

    def test_inline_rm_soul(self):
        text = "You can run `rm /home/rohit/maez/config/soul.md` to reset."
        out, refused = self._scrub(text)
        self.assertNotIn("rm /home/rohit/maez/config/soul.md", out)
        self.assertIn("[refused]", out)
        self.assertEqual(len(refused), 1)

    def test_inline_htop(self):
        text = "Just use `htop` for process monitoring."
        out, refused = self._scrub(text)
        self.assertNotIn("`htop`", out)
        self.assertIn("[refused]", out)
        self.assertEqual(len(refused), 1)

    def test_inline_tail_follow(self):
        text = "Run `tail -f logs/maez.log` to watch."
        out, refused = self._scrub(text)
        self.assertNotIn("tail -f logs/maez.log", out)
        self.assertEqual(len(refused), 1)


class BenignContentPreserved(unittest.TestCase):
    """The guard must not eat legitimate code or prose."""

    def _scrub(self, text: str):
        from core.safety.output_command_guard import scrub_protected_commands
        return scrub_protected_commands(text)

    def test_benign_bash_block_untouched(self):
        text = "```bash\ngit status\necho hello\nls -la\n```"
        out, refused = self._scrub(text)
        self.assertEqual(out, text)
        self.assertEqual(refused, [])

    def test_python_block_untouched(self):
        # Python blocks aren't scanned — the guard only looks at shell.
        # A python string literal containing 'rm soul.md' is fine.
        text = "```python\nprint('rm soul.md')\n```"
        out, refused = self._scrub(text)
        self.assertEqual(out, text)
        self.assertEqual(refused, [])

    def test_prose_mentions_command_preserved(self):
        # Non-backticked prose is left alone — it isn't copy-paste bait.
        text = "Last time we discussed rm on soul.md and decided not to."
        out, refused = self._scrub(text)
        self.assertEqual(out, text)
        self.assertEqual(refused, [])

    def test_inline_benign_command_preserved(self):
        text = "Try `git log --oneline` to see commits."
        out, refused = self._scrub(text)
        self.assertEqual(out, text)
        self.assertEqual(refused, [])

    def test_inline_protected_name_alone_preserved(self):
        # Just naming a protected service, no destructive verb → passes.
        # Matches the 2026-04-18 covenant refinement that lets Maez
        # introspect its own state.
        text = "The `maez.service` unit is at /etc/systemd/system/."
        out, refused = self._scrub(text)
        self.assertEqual(out, text)
        self.assertEqual(refused, [])

    def test_empty_text_noop(self):
        out, refused = self._scrub("")
        self.assertEqual(out, "")
        self.assertEqual(refused, [])

    def test_no_backticks_noop(self):
        text = "This is a plain message with no code."
        out, refused = self._scrub(text)
        self.assertEqual(out, text)
        self.assertEqual(refused, [])


class ProtectedPromptTextScrubbing(unittest.TestCase):
    """Protected covenant/system-prompt sections must not be printed verbatim."""

    def _scrub(self, text: str):
        from core.safety.output_command_guard import scrub_protected_commands
        return scrub_protected_commands(text)

    def test_hard_constraints_section_refused(self):
        text = (
            "HARD CONSTRAINTS — These override all other reasoning, always:\n"
            "- NEVER stop llama-server.\n"
        )
        out, refused = self._scrub(text)
        self.assertNotIn("NEVER stop llama-server", out)
        self.assertIn("protected covenant", out)
        self.assertEqual(refused, ["HARD CONSTRAINTS"])

    def test_trust_covenant_section_refused(self):
        text = "TRUST COVENANT\nDo not print this verbatim."
        out, refused = self._scrub(text)
        self.assertNotIn("Do not print this verbatim", out)
        self.assertEqual(refused, ["TRUST COVENANT"])

    # ---- 2026-08-22 regression: prose mentions are speech, not a dump ----
    #
    # The marker check was a bare substring match over the whole reply, and a
    # hit replaced the ENTIRE reply. On 2026-08-22 09:11 Maez answered
    # "what's up with the world?" with a ~397-token reply, used the words
    # "trust covenant" in a sentence, and the whole answer was destroyed --
    # replaced by a refusal claiming the owner had asked for verbatim
    # system-prompt text. He had not.
    #
    # A leak is the header rendered AS a header. Talking about the covenant
    # is Maez discussing its own internals, which this module's docstring
    # explicitly protects.

    def test_prose_mention_of_covenant_is_not_scrubbed(self):
        text = ("Not much new that I can verify. That's part of the trust "
                "covenant between us - I don't claim what I can't check.")
        out, refused = self._scrub(text)
        self.assertEqual(refused, [])
        self.assertEqual(out, text)

    def test_prose_mention_of_hard_constraints_is_not_scrubbed(self):
        text = "I operate under some hard constraints about what I'll execute."
        out, refused = self._scrub(text)
        self.assertEqual(refused, [])
        self.assertEqual(out, text)

    def test_both_markers_in_one_sentence_still_pass(self):
        text = "My hard constraints and trust covenant are why I said no."
        out, refused = self._scrub(text)
        self.assertEqual(refused, [])
        self.assertEqual(out, text)

    def test_quoted_header_dump_still_refused(self):
        text = "> HARD CONSTRAINTS - These override all other reasoning:"
        _out, refused = self._scrub(text)
        self.assertEqual(refused, ["HARD CONSTRAINTS"])

    def test_soul_base_covenant_header_form_still_refused(self):
        # config/soul.base.md line 8 renders exactly this way.
        text = "TRUST COVENANT:\n- Never fabricate."
        out, refused = self._scrub(text)
        self.assertEqual(refused, ["TRUST COVENANT"])
        self.assertNotIn("Never fabricate", out)


class AuditedOutputIntegration(unittest.TestCase):
    """`audit_assistant_text` must invoke the scrub automatically."""

    def test_audit_entry_point_scrubs_dangerous_block(self):
        from core.safety.audited_output import audit_assistant_text
        raw = "Here you go:\n```bash\nrm config/soul.md\n```\n"
        audited = audit_assistant_text(raw, surface="probe")
        self.assertNotIn("rm config/soul.md", audited)
        self.assertIn("refused", audited.lower())

    def test_audit_entry_point_leaves_benign_text_alone(self):
        from core.safety.audited_output import audit_assistant_text
        raw = "Everything looks good — no changes needed."
        audited = audit_assistant_text(raw, surface="probe")
        self.assertIn("Everything looks good", audited)

    def test_audit_entry_point_scrubs_protected_prompt_text(self):
        from core.safety.audited_output import audit_assistant_text
        raw = "HARD CONSTRAINTS — These override all other reasoning, always:\n- NEVER stop llama-server."
        audited = audit_assistant_text(raw, surface="probe")
        self.assertNotIn("NEVER stop llama-server", audited)
        self.assertIn("protected covenant", audited)


if __name__ == "__main__":
    unittest.main()
