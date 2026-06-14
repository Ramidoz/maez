"""Layer A2 regression guard — empty-success stays filtered.

Task 0 (@d1d51cf) proved:
- external_sources.py:752-757 converts whitespace-ok reads to EMPTY (non-SUCCESS)
- external_sources.py:446-454 converts raw-empty reads to EMPTY (non-SUCCESS)
- merge.py:362 (_accepted_fresh_blocks) drops all non-SUCCESS branches

Therefore no empty-text FreshBlock can ever reach the render seam.
These three tests LOCK that invariant.  No production code was changed.
"""

from __future__ import annotations

import time
import unittest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_nonsuccess_status():
    """Return the first ExternalBranchStatus member that is not SUCCESS."""
    from core.dispatcher.spec import ExternalBranchStatus

    for member in ExternalBranchStatus:
        if member is not ExternalBranchStatus.SUCCESS:
            return member
    raise RuntimeError("ExternalBranchStatus has no non-SUCCESS member")  # pragma: no cover


def _fresh_block(source, text="real evidence"):
    from core.dispatcher.external_sources import FreshBlock
    from core.dispatcher.spec import FreshnessClass

    return FreshBlock(
        source=source,
        text=text,
        retrieval_timestamp="2026-06-14T00:00:00Z",
        freshness=FreshnessClass.LIVE_FETCH,
        prompt_cost=len(text),
        egress_diagnostic_id="diag-a2-guard",
    )


def _branch(source, status, *, blocks=(), completed_at=None):
    from core.dispatcher.external_sources import ExternalBranchResult

    return ExternalBranchResult(
        branch_id=f"a2-guard:{source.value}",
        fanout_generation_id="a2-gen",
        source=source,
        status=status,
        blocks=tuple(blocks),
        completed_at=completed_at if completed_at is not None else (time.time() - 1.0),
    )


def _fanout(*branches, sealed_at=None):
    from core.dispatcher.external_sources import ExternalFanoutResult

    _sealed = sealed_at if sealed_at is not None else time.time()
    return ExternalFanoutResult(
        fanout_generation_id="a2-gen",
        sealed_at=_sealed,
        branch_results=tuple(branches),
        fresh_blocks=(),
        availability_limitations=(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class LayerA2RegressionGuard(unittest.TestCase):
    """Regression guard: empty/non-SUCCESS paths never reach the render seam."""

    def test_nonsuccess_branch_is_dropped_from_fresh_blocks(self):
        """A non-SUCCESS branch produces NO accepted fresh blocks."""
        from core.dispatcher.merge import _accepted_fresh_blocks
        from core.dispatcher.spec import ExternalBranchStatus, ExternalSource

        non_success = _first_nonsuccess_status()

        # Give the branch a FreshBlock anyway — it must still be dropped.
        blk = _fresh_block(ExternalSource.WEB_SEARCH, text="should be invisible")
        br = _branch(ExternalSource.WEB_SEARCH, non_success, blocks=(blk,))
        fanout = _fanout(br)

        result = _accepted_fresh_blocks(fanout)

        self.assertEqual(
            result,
            (),
            f"Expected no accepted blocks from a {non_success!r} branch, "
            f"got {result!r}",
        )

    def test_no_accepted_block_has_empty_text(self):
        """Every block returned by _accepted_fresh_blocks has non-empty .text.strip().

        Invariant: upstream guards (external_sources.py:752-757 + :446-454) convert
        empty/whitespace reads to EMPTY (non-SUCCESS), and _accepted_fresh_blocks
        drops non-SUCCESS branches, so the empty text can never appear in the result.
        """
        from core.dispatcher.merge import _accepted_fresh_blocks
        from core.dispatcher.spec import ExternalBranchStatus, ExternalSource

        real_block = _fresh_block(ExternalSource.WEB_SEARCH, text="some real fetched content")
        br = _branch(ExternalSource.WEB_SEARCH, ExternalBranchStatus.SUCCESS, blocks=(real_block,))
        fanout = _fanout(br)

        accepted = _accepted_fresh_blocks(fanout)

        self.assertGreater(
            len(accepted),
            0,
            "Expected at least one accepted block from a SUCCESS branch",
        )
        for blk in accepted:
            self.assertTrue(
                blk.text.strip(),
                f"Accepted FreshBlock has empty .text.strip(): {blk!r}",
            )

    def test_all_failed_surfaces_honest_no_fresh_summary(self):
        """format_no_fresh_summary includes 'no fresh evidence available' and the source name."""
        from core.dispatcher.merge import format_no_fresh_summary
        from core.dispatcher.spec import ExternalBranchStatus, ExternalSource

        non_success = _first_nonsuccess_status()
        source = ExternalSource.WEB_SEARCH
        br = _branch(source, non_success)
        fanout = _fanout(br)

        summary = format_no_fresh_summary(fanout)

        self.assertIn(
            "no fresh evidence available",
            summary,
            f"Expected 'no fresh evidence available' in summary, got: {summary!r}",
        )
        self.assertIn(
            source.value,
            summary,
            f"Expected source name {source.value!r} in summary, got: {summary!r}",
        )


if __name__ == "__main__":
    unittest.main()
