# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARD: every Telegram reply must go through the
honesty-audit gate, or be explicitly allowlisted with a reason.

The 15-agent audit (2026-05-04) found 13+ ``reply_text(...)`` call
sites in skills/telegram_voice.py that bypass
``_audit_telegram_reply()``. The honesty guard exists to scrub
canary leakage, redact destructive shell narration, and block
fabricated self-claims before they reach the owner. Any reply
that skips it is a hole.

This test is the regression guard. AST-walks
skills/telegram_voice.py, enumerates every ``reply_text``
call, and asserts each is either:

  (A) inside a function that also calls
      ``_audit_telegram_reply`` (presence-of-audit heuristic), OR

  (B) explicitly listed in ``_AUDIT_BYPASS_ALLOWLIST`` with a
      documented reason.

Failure mode: a future code change adds a new ``reply_text``
in a function that doesn't audit. The test fails loudly. The
author then either routes through audit or adds an allowlist
entry with a reason.

The allowlist is intentionally explicit and documented — adding
an entry is a deliberate act, not an accident.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ── Allowlist — explicit bypasses with documented reason ────────────
#
# Format: (function_name, reason). Initially populated from the
# 2026-05-04 audit's 15-agent run. Future audits should walk this
# down — every entry is technical debt waiting for either an audit
# route or a documented reason.
#
# Functions whose ENTIRE body is allowlist-bypassed (control-flow
# replies, command responses, error messages — content is
# author-controlled, not LLM-generated). The audit gate is cheap
# and idempotent; over time we should route everything through it
# regardless. Until then, this list is the contract.

_AUDIT_BYPASS_ALLOWLIST: dict[str, str] = {
    # Slash-command handlers — replies are author-written control
    # flow (status text, confirmations, list renderings, error
    # messages). Not LLM-generated. The audit gate IS cheap and
    # idempotent; over time we should route everything through it
    # regardless. Until then, this list is the contract — adding
    # entries is a deliberate documented act, not an accident.
    # Future cleanup: route through audit, remove allowlist entry.
    "_handle_status": "/status — author-written status text",
    "_handle_cancel": "/cancel — author-written confirmation",
    "_handle_approve": "/approve — author-written confirmation",
    "_handle_pending": "/pending — author-written list rendering",
    "_handle_git": "/git — author-written git status",
    "_handle_disk": "/disk — author-written df-h rendering",
    "_handle_analyze": "/analyze — author-written analysis output",
    "_handle_approve_cleanup": "/approve_cleanup — author-written confirm",
    "_handle_trust": "/trust — author-written trust-tier rendering",
    "_handle_login": "/login — author-written auth confirm",
    "_handle_promote": "/promote — author-written promotion confirm",
    "_handle_approve_evolution": "/approve_evolution — author-written confirm",
    "_handle_reject_evolution": "/reject_evolution — author-written confirm",
    "_handle_evolution_log": "/evolution_log — author-written log rendering",
    # Codex audit 2026-05-04: removed from allowlist and promoted to
    # _AUDIT_REQUIRED_FUNCTIONS — these handlers render Maez-generated
    # content (insight, unified_diff, proposed_new_body, candidate
    # rationale, weakness, evidence) and were a residual T1.13 hole.
    #   _handle_dreams, _handle_edit_proposals, _handle_show_edit,
    #   _handle_train_proposals, _handle_show_train,
    #   _handle_proposals, _handle_show
    "_handle_apply_dream": "/apply_dream — author-written confirmation",
    "_handle_reject_dream": "/reject_dream — author-written confirmation",
    "_handle_apply_edit": "/apply_edit — author-written apply confirm",
    "_handle_reject_edit": "/reject_edit — author-written reject confirm",
    "_handle_approve_train": "/approve_train — author-written confirm",
    "_handle_reject_train": "/reject_train — author-written confirm",
    "_handle_adapter_status": "/adapter_status — author-written adapter-state rendering",
    "_handle_rollback_adapter": "/rollback_adapter — author-written confirm",
    "_handle_apply": "/apply — author-written apply confirm",
    "_handle_reject": "/reject — author-written reject confirm",
    "_handle_cog_analyze": "/cog_analyze — author-written cognition analysis",
    "_handle_help": "/help — static help text",
    "_handle_builder_enter": "/builder_enter — author-written mode-toggle confirm",
    "_handle_builder_exit": "/builder_exit — author-written mode-toggle confirm",
    # Card-rendering helper. The card's plain_english was already
    # audited at card-creation time (decision_pipeline + audited_output).
    "_send_card_message": "card render — content audited at card-creation time",
}


# Functions where REPLY-BY-REPLY auditing is required. Every
# ``reply_text`` inside these MUST be on a path where
# ``_audit_telegram_reply`` was called somewhere in the function
# body. Patched in this commit (T1.13).

_AUDIT_REQUIRED_FUNCTIONS: set[str] = {
    # The 4 functions the 2026-05-04 audit named as honesty-guard-
    # bypassing. Each must call `_audit_telegram_reply` somewhere
    # in its body (presence-of-audit heuristic).
    #
    # _handle_message and _process_message are NOT in this list
    # because they delegate to inner functions where the actual
    # audit happens; the AST heuristic doesn't cross function
    # boundaries. They're covered transitively by
    # `test_every_reply_site_is_audited_or_allowlisted` instead.
    #
    # Plus 7 dynamic-content renderers added by the Codex 2026-05-04
    # audit. These render Maez-generated content (insight,
    # unified_diff, proposed_new_body, candidate rationale,
    # weakness, evidence) — exactly the surface the honesty guard
    # is for. Were previously allowlisted as "author-written" which
    # is wrong: the proposal/candidate text is Maez output.
    "_handle_dreams",
    "_handle_edit_proposals",
    "_handle_show_edit",
    "_handle_train_proposals",
    "_handle_show_train",
    "_handle_proposals",
    "_handle_show",
    "_try_dream_proposal_intent",
    "_try_web_search_intent",
    "_try_offer_binding_intent",
    "_try_proposal_intent",
}


def _walk_function_calls(func_node: ast.FunctionDef | ast.AsyncFunctionDef):
    """Yield every Call node inside this function's body."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            yield node


def _is_reply_text_call(call: ast.Call) -> bool:
    """True iff this Call is `<obj>.reply_text(...)` where the
    attribute chain ends in `.reply_text`."""
    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    return func.attr == "reply_text"


def _calls_audit_helper(func_node) -> bool:
    """True iff this function's body contains a call to
    ``_audit_telegram_reply``."""
    for call in _walk_function_calls(func_node):
        if isinstance(call.func, ast.Name) and call.func.id == "_audit_telegram_reply":
            return True
        if (isinstance(call.func, ast.Attribute)
                and call.func.attr == "_audit_telegram_reply"):
            return True
    return False


def _find_enclosing_function(tree: ast.AST, target: ast.Call):
    """Return the innermost FunctionDef / AsyncFunctionDef that
    contains ``target``, or None if at module level."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target:
                    # Find the *innermost* enclosing function.
                    inner = node
                    for sub in ast.walk(node):
                        if (isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                                and sub is not node):
                            for child2 in ast.walk(sub):
                                if child2 is target:
                                    inner = sub
                                    break
                    return inner
    return None


class TelegramReplyAuditCoverage(unittest.TestCase):
    """REGRESSION GUARD for T1.13: enumerate every reply_text site
    in skills/telegram_voice.py and assert each is audited or
    explicitly allowlisted."""

    @classmethod
    def setUpClass(cls):
        path = REPO / "skills" / "telegram_voice.py"
        cls.source = path.read_text()
        cls.tree = ast.parse(cls.source)
        cls.path = path

    def test_every_reply_site_is_audited_or_allowlisted(self):
        """The contract: every `reply_text` call must be inside a
        function that audits, OR inside a function on the
        allowlist with a reason. New unaudited sites = test fails.
        """
        violations: list[tuple[int, str]] = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            if not _is_reply_text_call(node):
                continue
            enclosing = _find_enclosing_function(self.tree, node)
            if enclosing is None:
                # Module-level reply (extremely unusual)
                violations.append((node.lineno, "<module-level>"))
                continue
            fname = enclosing.name
            if _calls_audit_helper(enclosing):
                continue
            if fname in _AUDIT_BYPASS_ALLOWLIST:
                continue
            violations.append((node.lineno, fname))

        if violations:
            msg = (
                "Found unaudited Telegram reply paths. Either route "
                "through `_audit_telegram_reply()` or add the "
                "function to `_AUDIT_BYPASS_ALLOWLIST` in this test "
                "with a documented reason.\n\nViolations:"
            )
            for lineno, fname in violations:
                msg += f"\n  line {lineno}: function {fname!r}"
            self.fail(msg)

    def test_required_functions_actually_audit(self):
        """REGRESSION GUARD for T1.13 patch: the 4+ functions the
        2026-05-04 audit named as honesty-guard-bypassing must call
        `_audit_telegram_reply` in their body. Otherwise the patch
        regressed."""
        seen: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in _AUDIT_REQUIRED_FUNCTIONS:
                    seen.add(node.name)
                    self.assertTrue(
                        _calls_audit_helper(node),
                        f"function {node.name!r} is required to call "
                        f"`_audit_telegram_reply` per T1.13 — patch "
                        f"regressed",
                    )
        # Sanity check: the functions we assert about should exist.
        # _process_message and _handle_message are large functions
        # that may have moved or been renamed. Tolerate one or two
        # missing — focus is on the audit-flagged trio.
        critical = {
            "_try_dream_proposal_intent",
            "_try_web_search_intent",
            "_try_offer_binding_intent",
            "_try_proposal_intent",
        }
        self.assertTrue(
            critical.issubset(seen),
            f"critical audit-required functions missing from "
            f"telegram_voice.py: {critical - seen}",
        )

    def test_allowlist_entries_are_documented(self):
        """Every allowlist entry must have a non-empty reason
        string. Adding an entry without a reason is exactly the
        kind of accident this test exists to prevent."""
        for fname, reason in _AUDIT_BYPASS_ALLOWLIST.items():
            self.assertIsInstance(fname, str)
            self.assertTrue(
                fname,
                "allowlist function name must be non-empty",
            )
            self.assertIsInstance(reason, str)
            self.assertGreater(
                len(reason.strip()), 10,
                f"allowlist entry {fname!r} has trivial reason "
                f"{reason!r} — provide actual context",
            )


if __name__ == "__main__":
    unittest.main()
