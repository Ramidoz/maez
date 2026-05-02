# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""5x.F.A — cycle-scoped recall-context bag (helpers).

The daemon accumulates a per-cycle bag of recalled memory IDs +
their ``trust_tier`` so action handlers in the same cycle can
check whether any untrusted entry was in scope. F.B (next slice)
uses the bag to downgrade ``_do_update_baseline`` writes when the
LLM's reasoning had untrusted material in its prompt.

This module is the helper layer:

  - ``make_empty()`` constructs a fresh bag at cycle start.
  - ``capture(bag, recalled)`` mutates the bag with a
    ``recall_for_cycle`` result (the three-tier core/daily/raw
    dict).
  - ``tier_for(bag, mid)`` reads a memory ID's captured tier.
  - ``has_untrusted(bag)`` is the boolean F.B will check.

Critical exclusions (per user's design constraint at the close of
5x.F design conversation):

  - **Ambient** (phone/weather/active-window) is NOT recall.
    It's live state injected into the prompt via a different
    path (``ambient_prompt_block``). Mixing ambient into the
    bag would blur the meaning of the gate.

  - **Lived-recall episode IDs** (from
    ``build_lived_recall_brief``) live in SQLite, not Chroma,
    and have no reliable ``trust_tier`` lookup. Including them
    would require fake tiers; the user explicitly forbade that.

Both are excluded BY CONSTRUCTION: ``capture`` only reads the
``core`` / ``daily`` / ``raw`` keys of the supplied dict, which
match ``recall_for_cycle``'s return shape. Anything else in the
input dict is ignored.

Behavior change: NONE. F.A only builds the substrate; nothing
reads ``has_untrusted`` yet.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _entry(mid: str, tier: str | None = None) -> dict:
    """Build a recalled-memory-shaped dict matching what
    ``recall_for_cycle`` returns from the live MemoryManager."""
    meta: dict = {}
    if tier is not None:
        meta["trust_tier"] = tier
    return {"id": mid, "content": f"content for {mid}", "metadata": meta}


class MakeEmptyTests(unittest.TestCase):
    def test_empty_bag_has_empty_ids_and_tiers(self):
        from core.memory.cycle_recall_context import make_empty
        bag = make_empty()
        self.assertEqual(bag["ids"], set())
        self.assertEqual(bag["tiers_by_id"], {})

    def test_two_empty_bags_are_independent(self):
        """Distinct calls to make_empty must NOT share underlying
        containers — otherwise a reset between cycles would leak
        prior cycle's state."""
        from core.memory.cycle_recall_context import make_empty
        a = make_empty()
        b = make_empty()
        a["ids"].add("raw-1")
        a["tiers_by_id"]["raw-1"] = "lived"
        self.assertEqual(b["ids"], set())
        self.assertEqual(b["tiers_by_id"], {})


class CaptureTests(unittest.TestCase):
    def test_capture_records_ids_and_tiers_across_three_tiers(self):
        from core.memory.cycle_recall_context import capture, make_empty
        bag = make_empty()
        recalled = {
            "core": [_entry("core-1", "lived")],
            "daily": [_entry("daily-1", "observed")],
            "raw": [_entry("raw-1", "untrusted")],
        }
        capture(bag, recalled)
        self.assertEqual(
            bag["ids"], {"core-1", "daily-1", "raw-1"},
        )
        self.assertEqual(bag["tiers_by_id"]["core-1"], "lived")
        self.assertEqual(bag["tiers_by_id"]["daily-1"], "observed")
        self.assertEqual(bag["tiers_by_id"]["raw-1"], "untrusted")

    def test_capture_accumulates_across_multiple_calls(self):
        """A single cycle may invoke recall_for_cycle once today, but
        future versions might recall multiple times. Capture must
        accumulate, not replace."""
        from core.memory.cycle_recall_context import capture, make_empty
        bag = make_empty()
        capture(bag, {
            "core": [_entry("core-1", "lived")],
            "daily": [],
            "raw": [],
        })
        capture(bag, {
            "core": [],
            "daily": [],
            "raw": [_entry("raw-1", "untrusted")],
        })
        self.assertEqual(bag["ids"], {"core-1", "raw-1"})
        self.assertEqual(bag["tiers_by_id"]["raw-1"], "untrusted")
        self.assertEqual(bag["tiers_by_id"]["core-1"], "lived")

    def test_capture_handles_untagged_entries_as_unknown(self):
        """Pre-5x.A legacy entries carry no ``trust_tier``. Capture
        them as ``"unknown"`` so the tiers_by_id dict carries an
        explicit signal rather than a missing key. This matches the
        5x.D.A ``_ancestor_tier_label`` semantics."""
        from core.memory.cycle_recall_context import capture, make_empty
        bag = make_empty()
        capture(bag, {
            "core": [],
            "daily": [],
            "raw": [_entry("raw-old", tier=None)],
        })
        self.assertIn("raw-old", bag["ids"])
        self.assertEqual(bag["tiers_by_id"]["raw-old"], "unknown")

    def test_capture_handles_empty_recalled_dict(self):
        from core.memory.cycle_recall_context import capture, make_empty
        bag = make_empty()
        capture(bag, {"core": [], "daily": [], "raw": []})
        self.assertEqual(bag["ids"], set())
        self.assertEqual(bag["tiers_by_id"], {})

    def test_capture_handles_partial_recalled_dict(self):
        """``recall_for_cycle`` always returns all three tiers, but a
        future caller might pass only a subset. ``capture`` must not
        crash on missing keys."""
        from core.memory.cycle_recall_context import capture, make_empty
        bag = make_empty()
        capture(bag, {"raw": [_entry("raw-1", "lived")]})  # no core/daily
        self.assertEqual(bag["ids"], {"raw-1"})
        self.assertEqual(bag["tiers_by_id"]["raw-1"], "lived")

    def test_capture_skips_entries_missing_id(self):
        """Defensive: a malformed entry without an `id` key shouldn't
        poison the bag with None or crash."""
        from core.memory.cycle_recall_context import capture, make_empty
        bag = make_empty()
        capture(bag, {
            "core": [],
            "daily": [],
            "raw": [{"content": "no id"}, _entry("raw-ok", "lived")],
        })
        self.assertEqual(bag["ids"], {"raw-ok"})


class ExclusionContractTests(unittest.TestCase):
    """The most load-bearing tests in F.A. Verify ambient and
    lived-recall structurally cannot enter the bag, since the
    user-pinned design depends on the bag meaning 'memory-derived
    prompt context only.'"""

    def test_capture_ignores_ambient_key(self):
        """Ambient is structurally separate from recall. ``capture``
        only reads core/daily/raw; if a future caller mistakenly
        passes ambient into the dict, it must be ignored."""
        from core.memory.cycle_recall_context import capture, make_empty
        bag = make_empty()
        capture(bag, {
            "core": [],
            "daily": [],
            "raw": [],
            # Synthetic ambient-shaped data — must NOT enter the bag.
            "ambient": [
                {"id": "ambient-weather",
                 "content": "rainy",
                 "metadata": {"trust_tier": "untrusted"}},
            ],
        })
        self.assertNotIn("ambient-weather", bag["ids"])
        self.assertNotIn("ambient-weather", bag["tiers_by_id"])

    def test_capture_ignores_lived_recall_episode_key(self):
        """Lived-recall episode IDs (``ep-...``) live in SQLite, not
        Chroma, and have no reliable trust_tier lookup. Including
        them would require fake tiers. ``capture`` ignores any
        non-recall-tier dict key including a hypothetical
        ``lived_episodes``."""
        from core.memory.cycle_recall_context import capture, make_empty
        bag = make_empty()
        capture(bag, {
            "core": [],
            "daily": [],
            "raw": [],
            "lived_episodes": [
                {"id": "ep-abc123", "content": "x", "metadata": {}},
            ],
        })
        self.assertNotIn("ep-abc123", bag["ids"])

    def test_capture_ignores_renamed_recall_like_keys(self):
        """The strict tier-key allowlist (``core``/``daily``/``raw``)
        is the structural exclusion. A future caller that
        well-meaningly passes a renamed-but-shaped key (e.g.
        ``raw_2026`` after a hypothetical schema bump) must NOT
        sneak entries into the bag — the constant tuple is the
        single source of truth, and this test locks the contract
        so a future rename has to consciously update the constant
        rather than getting away with passing the old name."""
        from core.memory.cycle_recall_context import capture, make_empty
        bag = make_empty()
        capture(bag, {
            "raw_2026": [_entry("raw-renamed", "untrusted")],
            "core_v2": [_entry("core-renamed", "lived")],
            "raw_archive": [_entry("raw-archived", "untrusted")],
        })
        self.assertEqual(bag["ids"], set())
        self.assertEqual(bag["tiers_by_id"], {})

    def test_module_does_not_import_chromadb_or_memory_manager(self):
        """Same isolation contract as ``baseline_observations``: this
        helper must NOT couple to Chroma or MemoryManager. The bag is
        a daemon-state object; coupling here would invert the
        dependency direction. AST parse rather than text grep."""
        import ast
        path = (_REPO / "core" / "memory" / "cycle_recall_context.py")
        self.assertTrue(path.exists())
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden = {"chromadb", "memory.memory_manager"}
        leaked: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name == f or alias.name.startswith(f + ".")
                           for f in forbidden):
                        leaked.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if any(mod == f or mod.startswith(f + ".")
                       for f in forbidden):
                    leaked.append(mod)
        self.assertEqual(leaked, [], f"forbidden imports: {leaked}")


class TierForTests(unittest.TestCase):
    def test_tier_for_returns_captured_tier(self):
        from core.memory.cycle_recall_context import (
            capture, make_empty, tier_for,
        )
        bag = make_empty()
        capture(bag, {"raw": [_entry("raw-1", "untrusted")]})
        self.assertEqual(tier_for(bag, "raw-1"), "untrusted")

    def test_tier_for_returns_none_for_unknown_id(self):
        from core.memory.cycle_recall_context import make_empty, tier_for
        bag = make_empty()
        self.assertIsNone(tier_for(bag, "raw-never-captured"))


class HasUntrustedTests(unittest.TestCase):
    def test_has_untrusted_true_when_any_entry_is_untrusted(self):
        from core.memory.cycle_recall_context import (
            capture, has_untrusted, make_empty,
        )
        bag = make_empty()
        capture(bag, {
            "core": [_entry("core-1", "lived")],
            "daily": [_entry("daily-1", "observed")],
            "raw": [_entry("raw-1", "untrusted")],
        })
        self.assertTrue(has_untrusted(bag))

    def test_has_untrusted_false_when_no_entry_is_untrusted(self):
        from core.memory.cycle_recall_context import (
            capture, has_untrusted, make_empty,
        )
        bag = make_empty()
        capture(bag, {
            "core": [_entry("core-1", "lived")],
            "daily": [_entry("daily-1", "observed")],
            "raw": [_entry("raw-1", "covenant")],
        })
        self.assertFalse(has_untrusted(bag))

    def test_has_untrusted_false_for_empty_bag(self):
        from core.memory.cycle_recall_context import has_untrusted, make_empty
        self.assertFalse(has_untrusted(make_empty()))

    def test_has_untrusted_ignores_unknown_legacy_entries(self):
        """Legacy entries (tier='unknown') do NOT trigger
        has_untrusted — same non-degrading semantics as
        ``_worst_known_tier`` in 5x.D.A. Mass legacy material in
        cycle scope must NOT cause every baseline to downgrade."""
        from core.memory.cycle_recall_context import (
            capture, has_untrusted, make_empty,
        )
        bag = make_empty()
        capture(bag, {
            "raw": [_entry("raw-old-1"), _entry("raw-old-2")],
        })
        self.assertFalse(has_untrusted(bag))

    def test_has_untrusted_true_when_unknown_and_untrusted_mixed(self):
        """The complement of the legacy-non-degrading rule: legacy
        entries must NOT mask a real untrusted entry. F.B's
        downgrade-on-any-untrusted contract depends on this — a
        cycle's recall scope mixing pre-5x.A legacy raw rows with
        a single fresh reddit row must still trigger downgrade."""
        from core.memory.cycle_recall_context import (
            capture, has_untrusted, make_empty,
        )
        bag = make_empty()
        capture(bag, {
            "raw": [
                _entry("raw-legacy-1"),
                _entry("raw-legacy-2"),
                _entry("raw-reddit", "untrusted"),
                _entry("raw-legacy-3"),
            ],
        })
        self.assertTrue(has_untrusted(bag))


class DaemonWiringSmokeTests(unittest.TestCase):
    """Sanity check that the daemon-side wiring is intact: ``__init__``
    creates an empty bag, the helper functions can be imported from
    where the daemon imports them, and the ``capture`` call in the
    cycle-recall path mutates the bag without raising.

    Skips constructing a full ``MaezDaemon`` (heavy dependencies);
    instead asserts the wiring symbols and the bag-shape invariant
    via grep + helper-call composition. F.B will add an end-to-end
    test once it adds the consumer in `_do_update_baseline`."""

    def test_daemon_imports_cycle_recall_context_helpers(self):
        """The daemon source imports `make_empty` and `capture` from
        the helper module. Tightens the contract so a future refactor
        that splits out the helper into a different module will fire
        this test rather than break wiring silently."""
        path = _REPO / "daemon" / "maez_daemon.py"
        src = path.read_text(encoding="utf-8")
        self.assertIn("from core.memory.cycle_recall_context import", src)
        self.assertIn("make_empty", src)
        self.assertIn("capture", src)

    def test_daemon_resets_bag_at_cycle_top(self):
        """The reset is a load-bearing invariant — without it, prior
        cycles' untrusted IDs would persist into a clean cycle and
        F.B would over-downgrade. Locks the cycle-top reset by
        asserting both the import and the assignment land inside the
        ``while self.running`` block."""
        path = _REPO / "daemon" / "maez_daemon.py"
        src = path.read_text(encoding="utf-8")
        # Find the _loop method and confirm the reset assignment is
        # present after the cycle marker.
        loop_idx = src.find("def _loop(self):")
        self.assertGreater(loop_idx, 0, "_loop method missing")
        cycle_marker_idx = src.find("--- Cycle %d ---", loop_idx)
        self.assertGreater(cycle_marker_idx, 0, "cycle marker missing")
        reset_idx = src.find(
            "self._cycle_recall_context = _crc_empty()",
            cycle_marker_idx,
        )
        self.assertGreater(
            reset_idx, cycle_marker_idx,
            "cycle-top reset of recall context bag missing",
        )

    def test_daemon_captures_after_recall_for_cycle(self):
        """The capture call must run BETWEEN `recall_for_cycle` and
        `format_for_prompt` — populating after recall lets F.B see
        the same scope the LLM saw, populating before format keeps
        the prompt path unchanged."""
        path = _REPO / "daemon" / "maez_daemon.py"
        src = path.read_text(encoding="utf-8")
        recall_idx = src.find("self.memory.recall_for_cycle(context_query)")
        self.assertGreater(recall_idx, 0)
        capture_idx = src.find("_crc_capture(", recall_idx)
        self.assertGreater(
            capture_idx, recall_idx,
            "capture must come AFTER recall_for_cycle",
        )
        format_idx = src.find(
            "self.memory.format_for_prompt(recalled)", recall_idx,
        )
        self.assertGreater(format_idx, capture_idx,
                           "format_for_prompt must come AFTER capture")


if __name__ == "__main__":
    unittest.main()
