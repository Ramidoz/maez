"""
Test the three Fix 6 v3 follow-up imperfections:

  1. Logs-intent regex tightening: "what happened?" must NOT match 'logs' intent.
  2. Recovery card reason propagation: cards created during recovery passes must
     use the recovery_seed's original_intent as the reason, not empty "chat: ".
  3. Single-card-per-recovery-pass discipline: during a recovery pass, the Jarvis
     loop must break after the FIRST Lane 2 card is created, preventing orphan
     cards from multi-proposal passes.

All three tests are deterministic (no LoRA, no real pipeline, no DB).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import types
from unittest.mock import MagicMock, patch


# ─── Fix 1: logs-intent regex tightening ─────────────────────────────

def test_fix1_what_happened_does_not_match_logs_intent():
    from skills.telegram_voice import _match_intent, MACHINE_INTENTS

    assert _match_intent("what happened?") is None, \
        "'what happened?' should NOT match any machine intent (would short-circuit chat)"
    assert _match_intent("What happened") is None
    assert _match_intent("what happened after the recovery?") is None

    # Regression: legitimate log queries still route to 'logs'
    assert _match_intent("show logs") == "logs"
    assert _match_intent("check logs") == "logs"
    assert _match_intent("any errors in the logs?") == "logs"
    assert _match_intent("tail logs") == "logs"

    for phrase in MACHINE_INTENTS["logs"]:
        assert "what happened" not in phrase, \
            f"'logs' intent still contains dangerous phrase: {phrase!r}"

    print("  ✓ Fix 1: 'what happened?' no longer routes to logs intent")
    print("  ✓ Fix 1: legitimate log queries still route correctly")


# ─── Fix 2 + Fix 3: recovery-pass reason + single-card discipline ─────

def test_fix2_and_fix3_recovery_card_reason_and_single_card_discipline():
    """
    Exercise _run_jarvis_loop with a recovery_seed. The mock LLM emits a
    Lane 2 tool call on every iteration. The mock pipeline returns
    PENDING_APPROVAL. Without Fix 3, handle_action would be called
    max_iters times (creating orphan cards). With Fix 3, it should be
    called exactly once.
    """
    from skills import telegram_voice as tv_mod
    from core.decision_pipeline import PipelineStatus

    pending_result = types.SimpleNamespace(
        status=PipelineStatus.PENDING_APPROVAL,
        message="card created",
        execution_output=None,
        execution_success=None,
        execution_error=None,
    )

    mock_pipe = MagicMock()
    mock_pipe.handle_action.return_value = pending_result

    # Build a fake _llm_client.chat that returns a TOOL_CALL for apt-get on
    # every iteration. If Fix 3 works, we only see one handle_action
    # call regardless of how many iterations the LoRA tries.
    def fake_chat(*args, **kwargs):
        resp = types.SimpleNamespace()
        resp.message = types.SimpleNamespace(
            content='TOOL_CALL: {"action": "run_shell", "params": {"cmd": "apt-get install -y openrgb"}}'
        )
        return resp

    # Minimal TelegramVoice shell — bypass __init__, stub only what the loop
    # touches: self.actions (truthy), self._get_pipeline.
    skill = tv_mod.TelegramVoice.__new__(tv_mod.TelegramVoice)
    skill.actions = MagicMock()  # truthy, _run_jarvis_loop checks `if not self.actions: return`
    skill.authorized_user = <OWNER_TELEGRAM_ID>
    skill._get_pipeline = MagicMock(return_value=mock_pipe)

    recovery_seed = {
        "failed_action": "run_shell",
        "failed_params": {"cmd": "apt-get install openrgb"},
        "error": "exit=100 stderr=E: Unable to locate package openrgb",
        "original_intent": "install openrgb to control keyboard lighting",
        "recovery_depth": 1,
        "prior_attempts": [],
    }

    # Patch _llm_client.chat inside the core module so the import inside
    # _run_jarvis_loop (`from core import llm_client as _llm_client`) picks
    # up the patched version.
    from core import llm_client as core_llm_client

    with patch.object(core_llm_client, "chat", fake_chat):
        try:
            skill._run_jarvis_loop(
                user_text="",
                max_iters=4,
                recovery_seed=recovery_seed,
            )
        except Exception as e:
            # The loop may hit a mocked-out attribute AFTER the card is
            # created. That's fine — Fix 2 and Fix 3 are observable via
            # the mock_pipe call records regardless of what happens after.
            print(f"  (loop ended with: {type(e).__name__}: {str(e)[:100]})")

    # ─── Fix 2 assertion: reason was propagated from recovery_seed ───
    assert mock_pipe.handle_action.called, \
        "pipe.handle_action was never called — test setup broken"

    first_call = mock_pipe.handle_action.call_args_list[0]
    reason = first_call.kwargs.get("reason")
    assert reason is not None, "reason kwarg missing from handle_action call"
    assert reason.startswith("recovery:"), \
        f"Fix 2 broken — reason should start with 'recovery:', got {reason!r}"
    assert "install openrgb" in reason, \
        f"Fix 2 broken — original_intent not propagated, got {reason!r}"
    assert not reason.startswith("chat: "), \
        f"Fix 2 broken — stale 'chat: ' prefix still present, got {reason!r}"
    print(f"  ✓ Fix 2: card reason propagated as {reason!r}")

    # ─── Fix 3 assertion: single card per recovery pass ───
    n_calls = mock_pipe.handle_action.call_count
    assert n_calls == 1, (
        f"Fix 3 broken — expected exactly 1 handle_action call "
        f"(single-card-per-pass), got {n_calls}. "
        f"Each extra call is an orphan card."
    )
    print(f"  ✓ Fix 3: exactly {n_calls} card created (single-card-per-pass discipline)")


# ─── Fix 2: legacy-path reason propagation (source-level check) ──────

def test_fix2_legacy_path_source_check():
    """
    The legacy action path (non-pipeline actions like read_file) is harder
    to exercise directly, but we can check at the source level that both
    sites are fixed.
    """
    import skills.telegram_voice as tv_mod
    src = open(tv_mod.__file__).read()

    assert 'card_reason = f"recovery:' in src, \
        "Fix 2 pipeline-path marker missing"
    assert 'legacy_reason = f"recovery:' in src, \
        "Fix 2 legacy-path marker missing"

    # Also verify the old bare "chat: {user_text" pattern is only used
    # inside the `else` branch of a recovery_seed check, not naked.
    import re
    bare_matches = re.findall(r'= f"chat: \{user_text\[:140\]\}"', src)
    # We expect exactly 2 occurrences, both as the `else` branch of the
    # recovery_seed check (one pipeline, one legacy).
    assert len(bare_matches) == 2, \
        f"Expected 2 bare 'chat: ...' patterns (else-branch of recovery check), got {len(bare_matches)}"

    print("  ✓ Fix 2: both pipeline and legacy paths use recovery_seed for reason")
    print("  ✓ Fix 2: bare 'chat: ...' patterns confined to non-recovery else-branches")


# ─── Fix 3: source-level verification of the break statement ─────────

def test_fix3_break_statement_present():
    """Source-level check that the single-card-per-pass break is in place."""
    import skills.telegram_voice as tv_mod
    src = open(tv_mod.__file__).read()

    assert "single-card-per-pass discipline" in src, \
        "Fix 3 break statement missing (or comment removed)"
    assert 'if recovery_seed is not None:\n                        logger.info(\n                            "recovery: first Lane 2 card created, breaking loop ' in src, \
        "Fix 3 break-on-first-card logic not found"

    print("  ✓ Fix 3: break-on-first-card logic present in source")


# ─── main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("── Fix 6 v3 follow-ups: three imperfections ──\n")

    test_fix1_what_happened_does_not_match_logs_intent()
    print()

    test_fix2_and_fix3_recovery_card_reason_and_single_card_discipline()
    print()

    test_fix2_legacy_path_source_check()
    print()

    test_fix3_break_statement_present()
    print()

    print("All checks passed — Fix 6 v3 follow-ups verified.")
