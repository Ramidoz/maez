from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.recall_flip_eval import sandbox
from scripts.legacy_recall_eval.probes import SeededFixtures


class HarnessAbort(RuntimeError):
    """Raised when the harness cannot honestly emit a verdict."""


_FIXED_NOW = datetime(2026, 6, 5, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
_FIXED_NOW_EPOCH = _FIXED_NOW.timestamp()

_DATE_IN_WINDOW = Date(2026, 5, 27)
_DATE_OUT_OF_WINDOW = Date(2026, 4, 13)

_FIDELITY_MARKER_CONTENT = (
    "Fidelity marker fixture: the violet lighthouse logged a maintenance ping "
    "on the cedar pier. Synthetic, fictional, not owner content."
)

_FIXTURE_CONTENT = {
    "d_in": (
        "Last-week daily note: we paired the amber router with the slate cache. "
        "Synthetic fixture."
    ),
    "d_out": "Old daily note from spring: the bronze ledger was rotated. Synthetic fixture.",
    "c_in": (
        "Core self-context: Maez keeps its promises and refuses to fabricate. "
        "Synthetic fixture."
    ),
}


def patch_fixed_now():
    """Pin MemoryManager's clock; return the original callable for restoration."""
    import memory.memory_manager as mm_mod

    original = mm_mod._now_seconds
    mm_mod._now_seconds = lambda: _FIXED_NOW_EPOCH
    return original


def restore_now(original) -> None:
    import memory.memory_manager as mm_mod

    mm_mod._now_seconds = original


def prove_sandbox_fidelity(sandbox_root, *, run_id: str) -> bool:
    """Prove the real recall path reads the seeded sandbox, not live memory."""
    try:
        sandbox.assert_sandbox(sandbox_root)
    except sandbox.NotSandboxError as exc:
        raise HarnessAbort(f"sandbox fidelity: path outside sandbox: {exc}") from exc

    marker_id = sandbox.seed_dated_memory(
        "fidelity",
        "marker",
        date=_DATE_IN_WINDOW,
        content=_FIDELITY_MARKER_CONTENT,
        tier="daily",
        run_id=run_id,
    )

    from memory.memory_manager import MemoryManager

    recalled = MemoryManager().recall_for_telegram("what were we working on last week?")
    daily_ids = {row.get("id") for row in (recalled.get("daily") or ())}
    if marker_id not in daily_ids:
        raise HarnessAbort(
            "sandbox fidelity: seeded marker did not surface via recall_for_telegram "
            "(harness is not reading the store it seeded)"
        )
    return True


def seed_window_match_fixtures(run_id: str) -> SeededFixtures:
    """Seed in-window daily, old daily, and in-window core fixtures."""
    d_in = sandbox.seed_dated_memory(
        "wm",
        "d_in",
        date=_DATE_IN_WINDOW,
        content=_FIXTURE_CONTENT["d_in"],
        tier="daily",
        run_id=run_id,
    )
    d_out = sandbox.seed_dated_memory(
        "wm",
        "d_out",
        date=_DATE_OUT_OF_WINDOW,
        content=_FIXTURE_CONTENT["d_out"],
        tier="daily",
        run_id=run_id,
    )
    c_in = sandbox.seed_dated_memory(
        "wm",
        "c_in",
        date=_DATE_IN_WINDOW,
        content=_FIXTURE_CONTENT["c_in"],
        tier="core",
        run_id=run_id,
    )
    return SeededFixtures(d_in_id=d_in, d_out_id=d_out, c_in_id=c_in)


def seed_empty_window_fixtures(run_id: str) -> SeededFixtures:
    """Seed only old daily plus in-window core; the event window is empty."""
    d_out = sandbox.seed_dated_memory(
        "ew",
        "d_out",
        date=_DATE_OUT_OF_WINDOW,
        content=_FIXTURE_CONTENT["d_out"],
        tier="daily",
        run_id=run_id,
    )
    c_in = sandbox.seed_dated_memory(
        "ew",
        "c_in",
        date=_DATE_IN_WINDOW,
        content=_FIXTURE_CONTENT["c_in"],
        tier="core",
        run_id=run_id,
    )
    return SeededFixtures(d_in_id="<none>", d_out_id=d_out, c_in_id=c_in)


def run_probe(query: str):
    """Drive the real legacy recall path; return (recalled, rendered)."""
    from memory.memory_manager import MemoryManager

    manager = MemoryManager()
    recalled = manager.recall_for_telegram(query)
    rendered = manager.format_for_prompt(recalled)
    return recalled, rendered
