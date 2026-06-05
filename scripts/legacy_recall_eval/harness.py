from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.recall_flip_eval import sandbox


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
