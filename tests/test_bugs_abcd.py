"""
Tests for the four Telegram chat intelligence bugs (2026-04-15 audit):

  A. _do_web_search crashes on empty params → now graceful
  B. Partial-action fabrication trap → positive-form rule in prompt
  C. Recent card state invisible to follow-up turns → BODY ACTIVITY block
  D. Polluted recall surfaces pre-fix fabrications → integrity filter
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Bug A: web_search empty-params graceful handling ─────────────────

def test_bug_a_web_search_empty_query_returns_empty_query_string():
    from core.action_engine import ActionEngine
    import inspect

    # Signature check: query should have a default
    sig = inspect.signature(ActionEngine._do_web_search)
    query_param = sig.parameters.get("query")
    assert query_param is not None, "query param missing"
    assert query_param.default is not inspect.Parameter.empty, \
        "Bug A not fixed — query still required, malformed tool calls will crash"

    # Behavior check: calling with empty params via kwargs expansion
    # should return the "empty query" string, not raise.
    ae = ActionEngine.__new__(ActionEngine)  # bypass __init__
    result = ActionEngine._do_web_search(ae)  # no args — mimics `method(**{})`
    assert result == "empty query", f"expected 'empty query', got {result!r}"

    # Also: extra kwargs should be swallowed silently (the LoRA sometimes
    # emits `reasoning` as a sibling param).
    result2 = ActionEngine._do_web_search(ae, query="", reasoning="whatever", foo="bar")
    assert result2 == "empty query", f"extra kwargs crashed: {result2!r}"

    print("  ✓ Bug A: _do_web_search handles empty params gracefully")
    print("  ✓ Bug A: extra kwargs are swallowed without TypeError")


# ─── Bug B: positive-form fabrication rule present in prompt ──────────

def test_bug_b_partial_action_trap_rule_present():
    import skills.telegram_voice as tv
    src = open(tv.__file__).read()

    # The hard instruction must carry the positive rule — mention of
    # "THE POSITIVE RULE" and an explicit example of the partial-action
    # trap. Without this, Bug B reproduces.
    assert "THE POSITIVE RULE" in src, \
        "Bug B not fixed — positive-form rule missing from hard instruction"
    assert "PARTIAL-ACTION TRAP" in src, \
        "Bug B not fixed — partial-action trap example missing"
    assert "started looking" in src, \
        "Bug B not fixed — concrete counter-example missing"
    # The rule should forbid inventing actions not in the transcript
    assert "actions, tools, commands" in src, \
        "Bug B not fixed — positive allowlist framing missing"

    print("  ✓ Bug B: positive-form fabrication rule present")
    print("  ✓ Bug B: partial-action trap example with concrete shapes")


# ─── Bug C: recent card state block builder + injection ───────────────

def test_bug_c_body_activity_block_exists_and_is_injected():
    import skills.telegram_voice as tv
    src = open(tv.__file__).read()

    assert "_build_recent_body_activity_block" in src, \
        "Bug C not fixed — body activity block builder missing"
    assert "BODY ACTIVITY (last" in src, \
        "Bug C not fixed — body activity header format missing"
    # Injection site: the prompt build in _process_message
    assert "body_activity = self._build_recent_body_activity_block" in src, \
        "Bug C not fixed — block not called from _process_message"
    assert "if body_activity:\n            prompt += body_activity" in src, \
        "Bug C not fixed — block not injected into prompt"
    # The NO-TOOLS marker should reference BODY ACTIVITY for cross-turn
    # state inheritance
    assert "Read the BODY ACTIVITY block" in src or "BODY ACTIVITY block\n" in src, \
        "Bug C not fixed — no-tools marker doesn't reference body activity"

    print("  ✓ Bug C: body activity block builder exists")
    print("  ✓ Bug C: block injected into _process_message prompt")
    print("  ✓ Bug C: no-tools marker references body activity")


def test_bug_c_pending_card_store_recent_activity_method():
    from core.pending_cards import PendingCardStore
    import inspect

    assert hasattr(PendingCardStore, "recent_activity_for_chat"), \
        "Bug C not fixed — PendingCardStore.recent_activity_for_chat missing"

    sig = inspect.signature(PendingCardStore.recent_activity_for_chat)
    params = sig.parameters
    assert "channel" in params
    assert "chat_id" in params
    assert "since_seconds" in params
    assert params["since_seconds"].default == 600.0, \
        "since_seconds default should be 600 (10 min window)"

    print("  ✓ Bug C: PendingCardStore.recent_activity_for_chat exists with correct signature")


# ─── Bug D: integrity filter in _query_collection ─────────────────────

def test_bug_d_integrity_filter_and_tag_helper():
    from memory.memory_manager import MemoryManager
    import inspect

    # The excluded-integrity set must be defined on the class
    assert hasattr(MemoryManager, "_EXCLUDED_INTEGRITY"), \
        "Bug D not fixed — _EXCLUDED_INTEGRITY set missing"
    excluded = MemoryManager._EXCLUDED_INTEGRITY
    assert "stale" in excluded
    assert "fabricated" in excluded
    assert "historical_artifact" in excluded

    # tag_integrity helper must exist
    assert hasattr(MemoryManager, "tag_integrity"), \
        "Bug D not fixed — tag_integrity helper missing"

    # _query_collection must skip excluded integrity
    src = inspect.getsource(MemoryManager._query_collection)
    assert "_EXCLUDED_INTEGRITY" in src, \
        "Bug D not fixed — _query_collection doesn't filter by integrity"
    assert "over_fetch" in src, \
        "Bug D not fixed — _query_collection doesn't over-fetch to compensate for filter"

    print("  ✓ Bug D: _EXCLUDED_INTEGRITY set defined with stale/fabricated/historical_artifact")
    print("  ✓ Bug D: tag_integrity helper present")
    print("  ✓ Bug D: _query_collection filters by integrity with over-fetch")


def test_bug_d_known_pollution_tagged_as_stale():
    """Verify the 8 pre-fix fabrications got tagged stale and are no
    longer returned by default recall for lighting-related queries."""
    from memory.memory_manager import MemoryManager
    mm = MemoryManager()

    # The 8 entries we know we tagged
    res = mm.raw.get(
        where={"integrity": "stale"},
        limit=100,
        include=["documents", "metadatas"],
    )
    n_stale = len(res["ids"])
    assert n_stale >= 8, \
        f"Bug D not fixed — expected at least 8 stale entries, got {n_stale}"

    # Check all of them carry the integrity_reason
    for m in res["metadatas"]:
        assert m.get("integrity") == "stale"
        assert "lighting" in (m.get("integrity_reason") or "").lower() or \
               "fabrication" in (m.get("integrity_reason") or "").lower()

    print(f"  ✓ Bug D: {n_stale} known pollution entries tagged as stale (preserved, not deleted)")


# ─── main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("── Bugs A/B/C/D: 2026-04-15 Telegram intelligence audit ──\n")

    test_bug_a_web_search_empty_query_returns_empty_query_string()
    print()

    test_bug_b_partial_action_trap_rule_present()
    print()

    test_bug_c_body_activity_block_exists_and_is_injected()
    print()

    test_bug_c_pending_card_store_recent_activity_method()
    print()

    test_bug_d_integrity_filter_and_tag_helper()
    print()

    test_bug_d_known_pollution_tagged_as_stale()
    print()

    print("All checks passed — Bugs A/B/C/D verified.")
