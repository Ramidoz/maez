"""Law 1: no hardcoded opinions in the substrate.

Full-body audit: the fallback voice card named the owner's interests as
fact ("local AI, what's being built") -- a conclusion about the owner
baked into the prompt spine, still live on the fallback path and in the
continuity-fingerprint envelope. The card may shape HOW Maez speaks,
never WHAT the owner cares about.
"""

from __future__ import annotations


def test_voice_card_names_no_owner_interests():
    from core.routing.focused_cognition import _VOICE_CARD_TEXT

    for conclusion in ("local AI", "what's being built", "(", ")"):
        assert conclusion not in _VOICE_CARD_TEXT, conclusion
    # The structural intent survives: connect to evidence, not preset.
    assert "evidence" in _VOICE_CARD_TEXT
    assert "never a preset topic" in _VOICE_CARD_TEXT


def test_continuity_envelope_carries_no_owner_interest_conclusion():
    import inspect

    from core.continuity_fingerprint import envelope

    source = inspect.getsource(envelope)
    assert "local AI" not in source
    assert "what's being built" not in source


def test_no_owner_interest_premise_anywhere_in_owned_code():
    """Codex review: the retired premise survived verbatim in a validate
    harness the first regression didn't scan. Repo-wide now (owned code
    and prompts; vendored/docs excluded -- docs may QUOTE the scar)."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    offenders = []
    for root in ("core", "daemon", "skills", "scripts", "prompts", "config"):
        base = repo / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix not in {".py", ".md", ".json", ".txt"}:
                continue
            if "vendor" in path.parts or "node_modules" in path.parts:
                continue
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            if "local AI, what's being built" in text or (
                "local AI, the things being built" in text
            ):
                offenders.append(str(path.relative_to(repo)))
    assert offenders == [], offenders

