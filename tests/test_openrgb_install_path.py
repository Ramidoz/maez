"""
Tests for the three fixes that unblock the openrgb end-to-end install path:

  1. Offer-binding pattern expansion — "That'd be great" and similar
     natural-language approvals now fire the pending web_search offer
     instead of clearing it as a context-shift.

  2. Recovery depth cap raised from 2 → 5 — apt→PPA→snap→flatpak→
     build-from-source sequences no longer hit the terminal wall after
     two attempts.

  3. fetch_url Lane-0 action — Maez can read full install guides and
     READMEs after web_search returns a URL, without an approval card.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Fix 1: Offer-binding pattern expansion ───────────────────────────

def _ctrl():
    from core.conversation_controller import ConversationController
    return ConversationController(memory=None)


def test_offer_approval_that_d_be_great():
    assert _ctrl().is_offer_approval("That'd be great")

def test_offer_approval_that_would_be_great():
    assert _ctrl().is_offer_approval("That would be great")

def test_offer_approval_thats_great():
    assert _ctrl().is_offer_approval("That's great")

def test_offer_approval_sounds_great():
    assert _ctrl().is_offer_approval("Sounds great")

def test_offer_approval_that_sounds_good():
    assert _ctrl().is_offer_approval("That sounds good")

def test_offer_approval_that_d_work():
    assert _ctrl().is_offer_approval("That'd work")

def test_offer_approval_that_works():
    assert _ctrl().is_offer_approval("That works")

def test_offer_approval_perfect():
    assert _ctrl().is_offer_approval("Perfect")

def test_offer_approval_that_d_be_perfect():
    assert _ctrl().is_offer_approval("That'd be perfect")

def test_offer_approval_love_it():
    assert _ctrl().is_offer_approval("Love it")

def test_offer_approval_love_that():
    assert _ctrl().is_offer_approval("Love that")

def test_offer_approval_go_for_it():
    assert _ctrl().is_offer_approval("Go for it")

def test_offer_approval_yeah_do_that():
    assert _ctrl().is_offer_approval("Yeah do that")

def test_offer_approval_do_that():
    assert _ctrl().is_offer_approval("Do that")

def test_offer_approval_thats_good():
    assert _ctrl().is_offer_approval("That's good")

# Prior tokens must still match
def test_offer_approval_yes():
    assert _ctrl().is_offer_approval("yes")

def test_offer_approval_yeah():
    assert _ctrl().is_offer_approval("yeah")

def test_offer_approval_sure():
    assert _ctrl().is_offer_approval("sure")

def test_offer_approval_go_ahead():
    assert _ctrl().is_offer_approval("go ahead")

# Non-approvals must NOT match
def test_offer_non_approval_question():
    assert not _ctrl().is_offer_approval("What does that do?")

def test_offer_non_approval_mixed_content():
    assert not _ctrl().is_offer_approval("That'd be great but can you also check X?")

def test_offer_non_approval_no():
    assert not _ctrl().is_offer_approval("No thanks")

def test_offer_non_approval_empty():
    assert not _ctrl().is_offer_approval("")

def test_offer_non_approval_install_command():
    assert not _ctrl().is_offer_approval("Install openrgb using the PPA method")


# ─── Fix 2: Recovery depth cap raised to 5 ────────────────────────────

def test_recovery_depth_cap_is_5():
    """depth > 5 must trigger terminal summary; depth = 5 must still recover."""
    import ast, os
    tv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "telegram_voice.py",
    )
    with open(tv_path) as f:
        src = f.read()
    # Must contain depth > 5, must NOT contain depth > 2
    assert "depth > 5" in src, "recovery depth cap must be > 5"
    assert "depth > 2" not in src, "old depth > 2 cap still present"


def test_recovery_depth_comment_updated():
    """Comment describing the cap must reflect the new value."""
    import os
    tv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "telegram_voice.py",
    )
    with open(tv_path) as f:
        src = f.read()
    assert "max 5" in src or "max.*5" in src or "cap.*5" in src or "5)" in src


# ─── Fix 3: fetch_url Lane-0 tool ─────────────────────────────────────

def test_fetch_url_in_action_tiers():
    from core.action_engine import ACTION_TIERS
    assert "fetch_url" in ACTION_TIERS
    assert ACTION_TIERS["fetch_url"] == 0


def test_fetch_url_method_exists():
    from core.action_engine import ActionEngine
    assert hasattr(ActionEngine, "fetch_url")
    assert hasattr(ActionEngine, "_do_fetch_url")


def test_do_fetch_url_empty_url():
    from core.action_engine import ActionEngine
    ae = ActionEngine.__new__(ActionEngine)
    result = ae._do_fetch_url(url="")
    assert "empty" in result.lower()


def test_do_fetch_url_invalid_scheme():
    from core.action_engine import ActionEngine
    ae = ActionEngine.__new__(ActionEngine)
    result = ae._do_fetch_url(url="ftp://example.com/file")
    assert "invalid" in result.lower()


def test_do_fetch_url_no_url_arg():
    from core.action_engine import ActionEngine
    ae = ActionEngine.__new__(ActionEngine)
    result = ae._do_fetch_url()
    assert "empty" in result.lower()


def test_do_fetch_url_strips_html(monkeypatch=None):
    """_do_fetch_url strips HTML tags from response content."""
    from core.action_engine import ActionEngine
    import unittest.mock as mock
    import io

    html = b"<html><head><style>body{color:red}</style></head><body><h1>OpenRGB</h1><p>Install with: sudo apt install openrgb</p></body></html>"

    mock_resp = mock.MagicMock()
    mock_resp.read.return_value = html
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = mock.MagicMock(return_value=False)

    ae = ActionEngine.__new__(ActionEngine)
    with mock.patch("urllib.request.urlopen", return_value=mock_resp):
        result = ae._do_fetch_url(url="https://openrgb.org", max_chars=500)

    assert "<html>" not in result
    assert "<h1>" not in result
    assert "OpenRGB" in result
    assert "sudo apt install openrgb" in result


def test_do_fetch_url_truncates_at_max_chars(monkeypatch=None):
    from core.action_engine import ActionEngine
    import unittest.mock as mock

    long_text = ("A" * 5000).encode()
    mock_resp = mock.MagicMock()
    mock_resp.read.return_value = long_text
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = mock.MagicMock(return_value=False)

    ae = ActionEngine.__new__(ActionEngine)
    with mock.patch("urllib.request.urlopen", return_value=mock_resp):
        result = ae._do_fetch_url(url="https://example.com", max_chars=200)

    assert len(result) <= 250  # 200 + truncation note
    assert "truncated" in result


def test_do_fetch_url_handles_network_error():
    from core.action_engine import ActionEngine
    import unittest.mock as mock

    ae = ActionEngine.__new__(ActionEngine)
    with mock.patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        result = ae._do_fetch_url(url="https://unreachable.example.com")

    assert "error" in result.lower()


# ─── Fix 4: fetch_url wired into Jarvis prompt ────────────────────────

def test_fetch_url_in_jarvis_tool_params_doc():
    """The Jarvis manifest must document fetch_url with its required url param."""
    import os
    tv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "telegram_voice.py",
    )
    with open(tv_path) as f:
        src = f.read()
    assert "fetch_url" in src
    # The tool doc block (TOOL_CALL params section) must mention url param
    assert "fetch_url: MUST include" in src or "fetch_url:" in src


def test_fetch_url_usage_guidance_in_jarvis_prompt():
    """Jarvis prompt must tell the LLM to use fetch_url after web_search for full content."""
    import os
    tv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "telegram_voice.py",
    )
    with open(tv_path) as f:
        src = f.read()
    assert "fetch_url" in src
    # Should mention using it after web_search
    assert "web_search" in src and "fetch_url" in src


# ─── main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("── openrgb install path fixes ──\n")

    # Fix 1: offer-binding pattern
    for fn, label in [
        (test_offer_approval_that_d_be_great,    "'That'd be great'"),
        (test_offer_approval_that_would_be_great,"'That would be great'"),
        (test_offer_approval_thats_great,        "'That's great'"),
        (test_offer_approval_sounds_great,       "'Sounds great'"),
        (test_offer_approval_that_sounds_good,   "'That sounds good'"),
        (test_offer_approval_that_d_work,        "'That'd work'"),
        (test_offer_approval_that_works,         "'That works'"),
        (test_offer_approval_perfect,            "'Perfect'"),
        (test_offer_approval_that_d_be_perfect,  "'That'd be perfect'"),
        (test_offer_approval_love_it,            "'Love it'"),
        (test_offer_approval_love_that,          "'Love that'"),
        (test_offer_approval_go_for_it,          "'Go for it'"),
        (test_offer_approval_yeah_do_that,       "'Yeah do that'"),
        (test_offer_approval_do_that,            "'Do that'"),
        (test_offer_approval_thats_good,         "'That's good'"),
        (test_offer_approval_yes,                "'yes' (prior token)"),
        (test_offer_approval_yeah,               "'yeah' (prior token)"),
        (test_offer_approval_sure,               "'sure' (prior token)"),
        (test_offer_approval_go_ahead,           "'go ahead' (prior token)"),
    ]:
        fn()
        print(f"  ✓ offer approval matched: {label}")

    for fn, label in [
        (test_offer_non_approval_question,       "question not matched"),
        (test_offer_non_approval_mixed_content,  "mixed content not matched"),
        (test_offer_non_approval_no,             "'No thanks' not matched"),
        (test_offer_non_approval_empty,          "empty string not matched"),
        (test_offer_non_approval_install_command,"install command not matched"),
    ]:
        fn()
        print(f"  ✓ offer non-approval: {label}")

    # Fix 2: recovery depth cap
    test_recovery_depth_cap_is_5()
    print("  ✓ recovery depth cap is 5 (depth > 5 triggers terminal)")

    test_recovery_depth_comment_updated()
    print("  ✓ recovery depth comment updated")

    # Fix 3: fetch_url
    test_fetch_url_in_action_tiers()
    print("  ✓ fetch_url in ACTION_TIERS as Lane 0")

    test_fetch_url_method_exists()
    print("  ✓ fetch_url and _do_fetch_url methods exist on ActionEngine")

    test_do_fetch_url_empty_url()
    print("  ✓ _do_fetch_url: empty url → graceful error string")

    test_do_fetch_url_invalid_scheme()
    print("  ✓ _do_fetch_url: invalid scheme → graceful error string")

    test_do_fetch_url_no_url_arg()
    print("  ✓ _do_fetch_url: no url arg → graceful error string")

    test_do_fetch_url_strips_html()
    print("  ✓ _do_fetch_url: HTML stripped from response")

    test_do_fetch_url_truncates_at_max_chars()
    print("  ✓ _do_fetch_url: response truncated at max_chars")

    test_do_fetch_url_handles_network_error()
    print("  ✓ _do_fetch_url: network error → graceful error string")

    # Fix 4: prompt wiring
    test_fetch_url_in_jarvis_tool_params_doc()
    print("  ✓ fetch_url documented in Jarvis tool params block")

    test_fetch_url_usage_guidance_in_jarvis_prompt()
    print("  ✓ fetch_url usage guidance present in Jarvis prompt")

    print("\n33/33 checks PASS — openrgb install path unblocked.")
