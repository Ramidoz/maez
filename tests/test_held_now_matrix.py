"""Held-now Phase 1, commit D: interaction matrix, long-turn cases,
and the deterministic witness integration test.

The witness test is the DETERMINISTIC layer of the two-layer witness
(design pass 6): synthetic fresh evidence forces a focused-eligible
working set, and the discriminator tuple (source_type=dialogue_anchor
+ expected durable id) is asserted BOTH ways — present under ENABLED,
absent under OFF — on an ordinary turn with the old flag pinned off.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from core.routing.focused_cognition import (
    ANCHOR_FLOOR_CHARS,
    _content_hash,
    _strip_local_citations,
    assemble_working_set,
    dialogue_anchor_items,
)

ORDINARY_Q = "Tell me something interesting about gardens."
SENTINEL_USER = "The velvet quokka statue arrived from Ljubljana today."
SENTINEL_MAEZ = "A velvet quokka from Ljubljana — that is delightfully specific."
FRESH = "[fresh evidence]\nsearched: community gardens thrive with compost"


def _hx_with_sentinel() -> list[dict]:
    pairs = [
        {"content": f"Rohit: {SENTINEL_USER}\nMaez: {SENTINEL_MAEZ}",
         "metadata": {}},
        {"content": "Rohit: filler one about weather\nMaez: filler reply one",
         "metadata": {}},
        {"content": "Rohit: filler two about lunch\nMaez: filler reply two",
         "metadata": {}},
    ]
    return pairs


def _sentinel_durable_id() -> str:
    return _content_hash(
        f"{_strip_local_citations(SENTINEL_USER)}\n"
        f"{_strip_local_citations(SENTINEL_MAEZ)}"
    )


def _ws(env: dict, **kw):
    kw.setdefault("transcript", FRESH)
    kw.setdefault("web_context", "")
    kw.setdefault("owner_question", ORDINARY_Q)
    kw.setdefault("chat_history", _hx_with_sentinel())
    with mock.patch.dict(os.environ, env):
        return assemble_working_set(**kw)


_ENABLED = {"MAEZ_HELD_NOW_ENABLED": "1", "MAEZ_LIVE_THREAD_ANCHOR": ""}
_OFF = {"MAEZ_HELD_NOW_ENABLED": "", "MAEZ_HELD_NOW_SHADOW": "",
        "MAEZ_LIVE_THREAD_ANCHOR": ""}


class DeterministicWitnessTests(unittest.TestCase):
    """The discriminator, both ways, on an ordinary focused-eligible turn."""

    def test_enabled_leg_carries_the_sentinel_tuple(self):
        ws = _ws(_ENABLED)
        self.assertIsNotNone(ws)
        tuples = {(i.source_type, i.durable_id) for i in ws.items}
        self.assertIn(("dialogue_anchor", _sentinel_durable_id()), tuples)
        # fresh evidence intact — anchors displaced nothing
        self.assertTrue(
            any(i.source_type == "fresh_evidence" for i in ws.items)
        )

    def test_off_leg_lacks_the_sentinel_tuple(self):
        ws = _ws(_OFF)
        if ws is None:
            return  # no working set at all: discriminator trivially absent
        tuples = {(i.source_type, i.durable_id) for i in ws.items}
        self.assertNotIn(("dialogue_anchor", _sentinel_durable_id()), tuples)
        # and no dialogue anchor of ANY id on an ordinary turn
        self.assertFalse(
            any(i.source_type == "dialogue_anchor" for i in ws.items)
        )

    def test_old_flag_on_would_blur_hence_witness_pins_it_off(self):
        # Documents WHY the witness pins MAEZ_LIVE_THREAD_ANCHOR=0:
        # with it on, the OFF leg carries the tuple too (sentinel as
        # the NEWEST pair — the old flag takes the last two).
        env = dict(_OFF, MAEZ_LIVE_THREAD_ANCHOR="1")
        history = list(reversed(_hx_with_sentinel()))  # sentinel newest
        ws = _ws(env, chat_history=history)
        self.assertIsNotNone(ws)
        tuples = {(i.source_type, i.durable_id) for i in ws.items}
        self.assertIn(("dialogue_anchor", _sentinel_durable_id()), tuples)


class InteractionMatrixTests(unittest.TestCase):
    """old-flag x HELD_NOW cells not covered elsewhere."""

    def test_shadow_alone_changes_nothing_in_assembly(self):
        env = dict(_OFF, MAEZ_HELD_NOW_SHADOW="1")
        ws_shadow = _ws(env)
        ws_off = _ws(_OFF)
        if ws_shadow is None or ws_off is None:
            self.assertEqual(ws_shadow is None, ws_off is None)
            return
        self.assertEqual(
            [(i.source_type, i.text) for i in ws_shadow.items],
            [(i.source_type, i.text) for i in ws_off.items],
        )
        self.assertIsNone(ws_shadow.held_now_alloc)

    def test_enabled_plus_old_flag_yields_three_not_two(self):
        env = dict(_ENABLED, MAEZ_LIVE_THREAD_ANCHOR="1")
        ws = _ws(env)
        anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
        self.assertEqual(len(anchors), 3)

    def test_old_flag_alone_still_two_pairs(self):
        env = dict(_OFF, MAEZ_LIVE_THREAD_ANCHOR="1")
        ws = _ws(env)
        anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
        self.assertEqual(len(anchors), 2)


class LongTurnTests(unittest.TestCase):
    """Gate-revised long-turn cases (design pass 6 C8)."""

    def test_20k_pairs_normal_question_renders_at_least_one(self):
        big = [{
            "content": "Rohit: " + ("q" * 10000) + "\nMaez: " + ("a" * 10000),
            "metadata": {},
        } for _ in range(3)]
        ws = _ws(_ENABLED, chat_history=big)
        self.assertIsNotNone(ws)
        anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
        self.assertGreaterEqual(len(anchors), 1)
        self.assertTrue(all(a.text for a in anchors))
        self.assertTrue(
            any(i.source_type == "fresh_evidence" for i in ws.items)
        )

    def test_12k_question_yields_anchorless_receipt_no_crash(self):
        ws = _ws(_ENABLED, owner_question="q" * 12000)
        if ws is None:
            self.skipTest("no set for degenerate question")
        alloc = ws.held_now_alloc
        self.assertEqual(alloc["domain"], "below_floor")
        self.assertEqual(alloc["reason"], "question_consumed_budget")
        anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
        self.assertEqual(anchors, [])

    def test_seed_cap_feeds_id_and_final_render_matches(self):
        big = [{
            "content": "Rohit: " + ("q" * 5000) + "\nMaez: " + ("a" * 5000),
            "metadata": {},
        }]
        with mock.patch.dict(os.environ, _ENABLED):
            items = dialogue_anchor_items(big)
        # seed id computed over CAPPED text: hashing the capped pair
        # reproduces the id (the design's ID-matches-bytes rule at the
        # seed layer; allocator recompute covered in commit B tests)
        seed = items[0]
        user_part, maez_part = seed.text.split("\nMaez: ", 1)
        recomputed = _content_hash(
            f"{user_part[len('User: '):]}\n{maez_part}"
        )
        self.assertEqual(seed.durable_id, recomputed)


class FlagRegistryTests(unittest.TestCase):
    def test_both_flags_registered_with_witness_recipes(self):
        from core.cockpit.flags import default_registry

        reg = default_registry()
        self.assertIn("MAEZ_HELD_NOW_SHADOW", reg)
        self.assertIn("MAEZ_HELD_NOW_ENABLED", reg)
        self.assertEqual(reg["MAEZ_HELD_NOW_SHADOW"].tier, "T1")
        self.assertEqual(reg["MAEZ_HELD_NOW_ENABLED"].tier, "T2")
        for name in ("MAEZ_HELD_NOW_SHADOW", "MAEZ_HELD_NOW_ENABLED"):
            self.assertTrue(reg[name].witness_recipe)


if __name__ == "__main__":
    unittest.main()
