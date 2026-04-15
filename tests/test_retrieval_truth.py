"""
Retrieval-truth attribution contract tests — Track A item #1.

These tests assert ATTRIBUTION SEMANTICS of the recalled-memory prompt
block, not any specific wrapper format. The contract is:

1. The block as a whole must frame its contents as PRIOR state, not
   present perception, in natural language the model can read.
2. Every recalled chunk must be enclosed in a structured envelope that
   carries (a) its tier, (b) an identifier, and (c) a temporal marker
   appropriate to the tier (date for daily, cycle/timestamp for raw,
   permanence marker for core).
3. Daily and raw chunks must surface a timestamp or date the model can
   attribute to. Core chunks must be marked permanent.
4. Each chunk's original content must survive verbatim (modulo the
   llm_client sanitizer).
5. There must be a closing instruction reminding the model not to
   restate recalled values as present fact — positioned AFTER the
   chunks (otherwise early tokens forget it).
6. Empty recall returns empty string.
7. The framing must not use the word "Recent" or any other word that
   blurs prior and present — specifically the phrase "=== Recent" from
   the pre-fix format must NOT appear, to prevent regression.

Reproducers these tests exist to prevent:
- Reproducer B (2026-04-15 cycle 7): model narrated "root partition is
  still at 43.3%" — a value from a yesterday daily summary — as
  present tense. Fixed by point (1) + (3) + (5).
- Reproducer A (2026-04-15 cycle 5): model echoed recalled raw chunk
  verbatim including a "[maez]" marker inside. Fixed by point (2) —
  raw chunks now have hard envelope boundaries that make the recalled
  region unambiguous.

Offline only. No LLM calls.
"""

import os
import re
import sys

sys.path.insert(0, "/home/rohit/maez")

from memory.memory_manager import MemoryManager  # noqa: E402


def _make_mgr() -> MemoryManager:
    """MemoryManager.format_for_prompt does not touch the DB; we can
    bypass __init__ entirely and call the method as a bound function."""
    return MemoryManager.__new__(MemoryManager)


def _fake_recalled() -> dict:
    return {
        "core": [
            {
                "id": "core-abc123",
                "content": "the owner's grandmother is the founding motivation for Maez.",
                "metadata": {},
            },
        ],
        "daily": [
            {
                "id": "daily-2026-04-14",
                "content": "Root partition at 43.3%, 44 actions executed.",
                "metadata": {"date": "2026-04-14"},
                "distance": 0.412,
            },
        ],
        "raw": [
            {
                "id": "raw-deadbeef",
                "content": (
                    "I noticed you're reviewing speed-depth-priority-fix logs. "
                    "[maez] Nothing urgent."
                ),
                "metadata": {"cycle": 2, "timestamp": "2026-04-15T00:30:21Z"},
                "distance": 0.873,
            },
        ],
    }


# ---------------------------------------------------------------------- #
# 1. Empty recall → empty string                                         #
# ---------------------------------------------------------------------- #

def test_empty_recall_returns_empty_string():
    mgr = _make_mgr()
    assert mgr.format_for_prompt({}) == ""
    assert mgr.format_for_prompt({"core": [], "daily": [], "raw": []}) == ""


# ---------------------------------------------------------------------- #
# 2. Prior-state framing at the block level                              #
# ---------------------------------------------------------------------- #

def test_block_is_framed_as_prior_state_not_present():
    mgr = _make_mgr()
    out = mgr.format_for_prompt(_fake_recalled())
    low = out.lower()

    # Some phrase in the opening frame must mark the block as prior
    # memory / not present. We accept several phrasings to avoid
    # over-coupling the test to one sentence, but at least one must
    # appear BEFORE the first chunk.
    opening_region = out.split("<RECALLED")[0].lower()
    assert any(
        phrase in opening_region
        for phrase in (
            "prior material",
            "prior memory",
            "not present observation",
            "not current perception",
            "not live perception",
        )
    ), "opening frame must declare the block as prior, not present"

    # Regression guard: the pre-fix format used "=== Recent Daily
    # Summaries ===" which is exactly the phrase that invited the
    # model to narrate yesterday's disk value as "still" present.
    assert "=== recent" not in low, (
        "the word 'Recent' blurs prior and present and caused Reproducer B; "
        "do not reintroduce it in the framing"
    )


# ---------------------------------------------------------------------- #
# 3. Every chunk has a structured envelope with tier + id + temporal     #
# ---------------------------------------------------------------------- #

_RECALL_RE = re.compile(
    r"<RECALLED(?P<attrs>[^>]*)>(?P<body>.*?)</RECALLED>",
    re.DOTALL,
)


def _parse_attrs(attr_str: str) -> dict[str, str]:
    return dict(re.findall(r'(\w+)="([^"]*)"', attr_str))


def test_every_chunk_has_envelope_with_tier_and_id():
    mgr = _make_mgr()
    out = mgr.format_for_prompt(_fake_recalled())
    matches = list(_RECALL_RE.finditer(out))
    assert len(matches) == 3, (
        f"expected one envelope per chunk (1 core + 1 daily + 1 raw), got {len(matches)}"
    )
    for m in matches:
        attrs = _parse_attrs(m.group("attrs"))
        assert "tier" in attrs, f"envelope missing tier attribute: {m.group(0)[:80]}"
        assert attrs["tier"] in ("core", "daily", "raw")
        assert "id" in attrs and attrs["id"], "envelope must carry an id"


def test_core_chunk_is_marked_permanent():
    mgr = _make_mgr()
    out = mgr.format_for_prompt(_fake_recalled())
    core_env = next(
        m for m in _RECALL_RE.finditer(out)
        if _parse_attrs(m.group("attrs")).get("tier") == "core"
    )
    attrs = _parse_attrs(core_env.group("attrs"))
    assert attrs.get("permanent") == "true", (
        "core memories must be marked permanent so the model knows "
        "they do not describe a moment in time"
    )


def test_daily_chunk_carries_date_for_attribution():
    mgr = _make_mgr()
    out = mgr.format_for_prompt(_fake_recalled())
    daily_env = next(
        m for m in _RECALL_RE.finditer(out)
        if _parse_attrs(m.group("attrs")).get("tier") == "daily"
    )
    attrs = _parse_attrs(daily_env.group("attrs"))
    assert attrs.get("date") == "2026-04-14", (
        "daily envelope must expose its date so any claim sourced from "
        "it can be attributed — this is what stops the '43.3% still' bug"
    )


def test_raw_chunk_carries_cycle_and_timestamp():
    mgr = _make_mgr()
    out = mgr.format_for_prompt(_fake_recalled())
    raw_env = next(
        m for m in _RECALL_RE.finditer(out)
        if _parse_attrs(m.group("attrs")).get("tier") == "raw"
    )
    attrs = _parse_attrs(raw_env.group("attrs"))
    assert attrs.get("cycle") == "2"
    assert attrs.get("timestamp", "").startswith("2026-04-15"), (
        "raw envelope must carry a timestamp so it can be attributed "
        "and so it is distinguishable from live perception"
    )


# ---------------------------------------------------------------------- #
# 4. Content fidelity — the chunk body survives verbatim                 #
# ---------------------------------------------------------------------- #

def test_chunk_content_survives_inside_envelope():
    mgr = _make_mgr()
    recalled = _fake_recalled()
    out = mgr.format_for_prompt(recalled)

    for mem in recalled["core"] + recalled["daily"] + recalled["raw"]:
        assert mem["content"] in out, (
            f"content fidelity lost for {mem['id']}: "
            f"{mem['content'][:40]!r} missing from formatted output"
        )


# ---------------------------------------------------------------------- #
# 5. Closing instruction positioned AFTER the chunks                     #
# ---------------------------------------------------------------------- #

def test_closing_instruction_after_chunks_not_before():
    mgr = _make_mgr()
    out = mgr.format_for_prompt(_fake_recalled())
    last_close = out.rfind("</RECALLED>")
    assert last_close != -1
    tail = out[last_close:].lower()
    # Tail must contain an explicit "do not restate as present" style
    # instruction. Accept several phrasings.
    assert any(
        phrase in tail
        for phrase in (
            "not present state",
            "not current",
            "do not restate",
            "ground any factual claim",
            "prior memory",
        )
    ), (
        "a reminder must follow the recalled chunks — the model needs a "
        "late-in-context nudge, not only one buried at the top"
    )


# ---------------------------------------------------------------------- #
# 6. Raw envelope boundaries are HARD — prevents Reproducer A            #
# ---------------------------------------------------------------------- #

def test_raw_chunk_does_not_leak_outside_envelope():
    """Reproducer A: a raw memory containing the literal string
    '[maez] I noticed...' was echoed by the model as if it were a new
    turn. The fix is that the recalled content must live strictly
    inside the envelope — if the envelope closes cleanly, the model
    sees a hard boundary and cannot confuse recalled text for a fresh
    speaker turn."""
    mgr = _make_mgr()
    out = mgr.format_for_prompt(_fake_recalled())

    # Find the raw envelope, confirm its body contains the poisoning
    # fragment, and confirm the poison does NOT appear outside any
    # RECALLED envelope.
    raw_envs = [
        m for m in _RECALL_RE.finditer(out)
        if _parse_attrs(m.group("attrs")).get("tier") == "raw"
    ]
    assert raw_envs
    poison = "[maez] Nothing urgent."
    assert poison in raw_envs[0].group("body")

    # Strip every RECALLED envelope and make sure the poison is gone
    # from the remainder.
    stripped = _RECALL_RE.sub("", out)
    assert poison not in stripped, (
        "recalled content leaked outside its envelope — Reproducer A "
        "will reappear"
    )


# ---------------------------------------------------------------------- #
# 7. Distance score is surfaced when available                           #
# ---------------------------------------------------------------------- #

def test_distance_score_surfaced_when_available():
    mgr = _make_mgr()
    out = mgr.format_for_prompt(_fake_recalled())
    # Daily and raw in our fixture both have distance set; core does not.
    envs = {
        _parse_attrs(m.group("attrs")).get("tier"): _parse_attrs(m.group("attrs"))
        for m in _RECALL_RE.finditer(out)
    }
    assert "distance" in envs["daily"]
    assert "distance" in envs["raw"]
    assert "distance" not in envs["core"]


# ---------------------------------------------------------------------- #
# 8. All three tiers produce DISTINCT framing                            #
# ---------------------------------------------------------------------- #

def test_tiers_are_distinguishable():
    mgr = _make_mgr()
    out = mgr.format_for_prompt(_fake_recalled())
    tiers = [
        _parse_attrs(m.group("attrs")).get("tier")
        for m in _RECALL_RE.finditer(out)
    ]
    assert set(tiers) == {"core", "daily", "raw"}, (
        "each tier must appear exactly once and be labeled distinctly "
        "so the model can weigh them differently"
    )


# ---------------------------------------------------------------------- #
# Harness                                                                #
# ---------------------------------------------------------------------- #

def _run_all() -> int:
    tests = [
        (name, obj) for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {name}: {type(e).__name__}: {e}")
        else:
            passed += 1
            print(f"PASS {name}")
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_run_all())
