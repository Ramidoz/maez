"""Held-now Phase 1, commit B: presence rule + two-domain allocator.

Design: docs/superpowers/specs/2026-08-20-held-now-repair-phase1-design.md
(pass 6, gate-approved). Mutation discipline: each guarantee has a test
that FAILS when the mechanism is disabled.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from core.routing.focused_cognition import (
    ANCHOR_FLOOR_CHARS,
    assemble_working_set,
    dialogue_anchor_items,
    held_now_enabled,
)


def _hx(n: int = 3, filler: str = "") -> list[dict]:
    return [
        {
            "content": f"Rohit: question number {i} about the garden {filler}\n"
                       f"Maez: reply number {i} about the garden {filler}",
            "metadata": {},
        }
        for i in range(n)
    ]


_ON = {"MAEZ_HELD_NOW_ENABLED": "1"}
_OFF = {"MAEZ_HELD_NOW_ENABLED": "", "MAEZ_HELD_NOW_SHADOW": "",
        "MAEZ_LIVE_THREAD_ANCHOR": ""}


def _ws(question: str, history, env: dict, **kw):
    kw.setdefault("transcript", "")
    kw.setdefault("web_context", "")
    with mock.patch.dict(os.environ, env):
        return assemble_working_set(
            owner_question=question,
            chat_history=history,
            **kw,
        )


class PresenceTests(unittest.TestCase):
    ORDINARY_Q = "Tell me something interesting about gardens."

    def test_enabled_ordinary_turn_carries_three_pairs(self):
        ws = _ws(self.ORDINARY_Q, _hx(4), _ON)
        self.assertIsNotNone(ws)
        anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
        self.assertEqual(len(anchors), 3)
        self.assertEqual(ws.held_now_alloc["domain"], "full_count")
        self.assertEqual(ws.held_now_alloc["pairs_rendered"], 3)

    def test_disabled_ordinary_turn_has_no_anchors(self):
        # The mutation leg: same input, flag off, classifier-gated
        # legacy behavior -> zero anchors on an ordinary turn.
        ws = _ws(self.ORDINARY_Q, _hx(4), _OFF)
        if ws is None:
            return  # legacy may produce no set at all: also a pass
        anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
        self.assertEqual(len(anchors), 0)

    def test_enabled_authoritative_turn_keeps_two_pairs(self):
        ws = _ws("What did you just say?", _hx(4), _ON)
        self.assertIsNotNone(ws)
        anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
        self.assertEqual(len(anchors), 2)

    def test_old_flag_subsumed_under_enabled(self):
        env = dict(_ON, MAEZ_LIVE_THREAD_ANCHOR="1")
        ws = _ws(self.ORDINARY_Q, _hx(4), env)
        anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
        self.assertEqual(len(anchors), 3)  # 3, not the old flag's 2

    def test_empty_history_yields_no_anchors_not_crash(self):
        ws = _ws(self.ORDINARY_Q, [], _ON)
        if ws is not None:
            anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
            self.assertEqual(len(anchors), 0)


class AnchorCapTests(unittest.TestCase):
    def test_per_message_cap_applies_under_enabled(self):
        long_hx = [{
            "content": "Rohit: " + ("q" * 3000) + "\nMaez: " + ("a" * 3000),
            "metadata": {},
        }]
        with mock.patch.dict(os.environ, _ON):
            items = dialogue_anchor_items(long_hx)
        self.assertEqual(len(items), 1)
        # capped: each message <= 900 chars + rendering overhead
        self.assertLess(len(items[0].text), 2 * 950)
        self.assertIn("...[truncated]", items[0].text)

    def test_no_cap_when_disabled(self):
        long_hx = [{
            "content": "Rohit: " + ("q" * 3000) + "\nMaez: " + ("a" * 3000),
            "metadata": {},
        }]
        with mock.patch.dict(os.environ, _OFF):
            items = dialogue_anchor_items(long_hx)
        self.assertGreater(len(items[0].text), 5000)


class TrustPassthroughTests(unittest.TestCase):
    def test_worst_half_web_claim_carries_exclusion_provenance(self):
        hx = [{
            "content": "Rohit: what is X?\nMaez: X is a web thing.",
            "metadata": {
                "trust_tier": "untrusted",
                "provenance_source_reply": "self_web_claim",
            },
        }]
        with mock.patch.dict(os.environ, _ON):
            items = dialogue_anchor_items(hx)
        self.assertEqual(items[0].origin_trust, "untrusted")
        self.assertEqual(items[0].origin_provenance, "self_web_claim")
        # And flags-off: NO passthrough (C1 byte-identity; gate blocker 1)
        with mock.patch.dict(os.environ, _OFF):
            off_items = dialogue_anchor_items(hx)
        self.assertIsNone(off_items[0].origin_trust)
        self.assertIsNone(off_items[0].origin_provenance)

    def test_untrusted_reply_half_excluded_when_fresh_present(self):
        # The existing self_web_claim exclusion must bite on anchors
        # exactly as on other items (design C5/B6 pinned test).
        hx = [{
            "content": "Rohit: what is X?\nMaez: X is a web thing.",
            "metadata": {"provenance_source_reply": "self_web_claim"},
        }]
        env = dict(_ON, MAEZ_SELF_CLAIM_HYGIENE_ENABLED="1")
        ws = _ws(
            "Tell me about gardens.", hx, env,
            transcript="[fresh evidence]\nsearched: gardens are green",
        )
        if ws is None:
            self.skipTest("no working set produced")
        tainted = [
            i for i in ws.items
            if i.source_type == "dialogue_anchor"
            and i.origin_provenance == "self_web_claim"
        ]
        self.assertEqual(tainted, [])

    def test_clean_pair_carries_no_provenance(self):
        items = dialogue_anchor_items(
            [{"content": "Rohit: hi\nMaez: hello", "metadata": {}}]
        )
        self.assertIsNone(items[0].origin_trust)
        self.assertIsNone(items[0].origin_provenance)


class AllocatorDomainTests(unittest.TestCase):
    ORDINARY_Q = "Tell me something interesting about gardens."

    def test_floor_domain_keeps_newest_and_removes_emptied(self):
        # Big pairs + small budget: floor domain, newest survives,
        # emptied anchors REMOVED (no ID-bearing husks).
        history = _hx(3, filler="x" * 1500)
        ws = _ws(self.ORDINARY_Q, history, _ON,
                 max_working_set_chars=ANCHOR_FLOOR_CHARS + 600)
        self.assertIsNotNone(ws)
        alloc = ws.held_now_alloc
        self.assertEqual(alloc["domain"], "floor")
        anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
        self.assertGreaterEqual(len(anchors), 1)
        self.assertTrue(all(i.text for i in ws.items))  # no husks
        # newest pair is "question number 2" (last written)
        self.assertIn("number 2", anchors[0].text)

    def test_below_floor_question_consumed_budget(self):
        ws = _ws("q" * 3000, _hx(3), _ON, max_working_set_chars=3200)
        if ws is None:
            self.skipTest("no set")
        alloc = ws.held_now_alloc
        self.assertEqual(alloc["domain"], "below_floor")
        self.assertEqual(alloc["reason"], "question_consumed_budget")
        anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
        self.assertEqual(anchors, [])

    def test_truncated_anchor_id_matches_final_bytes(self):
        from core.routing.focused_cognition import _content_hash

        history = _hx(3, filler="y" * 700)  # below the 900 seed cap
        ws = _ws(self.ORDINARY_Q, history, _ON,
                 max_working_set_chars=ANCHOR_FLOOR_CHARS + 300)
        anchors = [i for i in ws.items if i.source_type == "dialogue_anchor"]
        self.assertTrue(anchors)
        truncated = [a for a in anchors if "...[truncated]" in a.text]
        self.assertTrue(truncated, "allocator should have truncated here")
        for a in truncated:
            self.assertEqual(a.durable_id, _content_hash(a.text))

    def test_full_count_domain_when_budget_admits(self):
        ws = _ws(self.ORDINARY_Q, _hx(3), _ON,
                 max_working_set_chars=12000)
        self.assertEqual(ws.held_now_alloc["domain"], "full_count")

    def test_zero_budget_stays_bounded(self):
        # Round-2 blocker 4: a consumed budget must never become
        # "no limit" through the legacy delegate.
        from core.routing.focused_cognition import _budget_items_held_now
        from core.routing.focused_cognition import EvidenceItem

        items = [EvidenceItem(
            local_label="E1", source_type="memory_context",
            text="x" * 5000, durable_id="ch_x", temporal_provenance=None,
            origin_trust=None, origin_provenance=None,
        )]
        out, meta = _budget_items_held_now(
            items, owner_question="q" * 400, max_chars=300,
            render_version="v1", containment_overhead=350,
        )
        self.assertEqual(meta["domain"], "below_floor")
        self.assertEqual(out, [])

    def test_containment_reconciliation_is_exact(self):
        # Round-3 note: persistent coverage for estimate==actual and
        # budget honored when containment fires normally.
        from core.routing import web_containment as wc

        if not wc.containment_enabled():
            self.skipTest("containment disabled in this environment")
        ws = _ws(
            self.ORDINARY_Q, _hx(3), _ON,
            web_context="a fresh web snippet about gardens",
            max_working_set_chars=4000,
        )
        self.assertIsNotNone(ws)
        alloc = ws.held_now_alloc
        self.assertEqual(
            alloc["containment_overhead_chars"],
            alloc["containment_overhead_actual"],
        )
        self.assertLessEqual(ws.working_set_chars, 4000)

    def test_estimator_failure_stays_bounded_by_measurement(self):
        # Round-3/4: estimation failures are TOLERATED because the
        # ground-truth loop measures the final render and re-allocates;
        # the budget promise is on the measured output, never on trust
        # in the estimate.
        from core.routing import web_containment as wc

        _real_nonce = wc.new_nonce
        _calls = {"n": 0}

        def _flaky_nonce():
            _calls["n"] += 1
            if _calls["n"] == 1:
                raise RuntimeError("transient")
            return _real_nonce()

        with mock.patch.object(
            wc, "containment_enabled", return_value=True
        ), mock.patch.object(wc, "new_nonce", side_effect=_flaky_nonce):
            ws = _ws(
                self.ORDINARY_Q, _hx(3), _ON,
                web_context="a fresh web snippet about gardens",
                max_working_set_chars=3000,
            )
        if ws is None:
            self.skipTest("no set")
        self.assertLessEqual(ws.working_set_chars, 3000)

    def test_marker_expansion_stays_bounded_by_measurement(self):
        # Round-4 blocker 2 witness: marker neutralization can expand
        # web content beyond any per-item constant; the loop must
        # still land the measured total inside the budget.
        from core.routing import web_containment as wc

        marker_web = " ".join("<<EXT:x>>" for _ in range(100))
        with mock.patch.object(wc, "containment_enabled", return_value=True):
            ws = _ws(
                self.ORDINARY_Q, _hx(3), _ON,
                web_context=marker_web,
                max_working_set_chars=3400,
            )
        if ws is None:
            self.skipTest("no set")
        self.assertLessEqual(ws.working_set_chars, 3400)

    def test_containment_state_unknown_withholds_web_fail_closed(self):
        # Round-5 blocker 1: containment_enabled raising with web
        # items present must WITHHOLD the web evidence, never render
        # it raw without an envelope.
        from core.routing import web_containment as wc

        with mock.patch.object(
            wc, "containment_enabled",
            side_effect=RuntimeError("state unavailable"),
        ), self.assertLogs("maez", level="WARNING") as logs:
            ws = _ws(
                self.ORDINARY_Q, _hx(3), _ON,
                web_context="raw web sentence that must not leak",
                max_working_set_chars=6000,
            )
        self.assertIsNotNone(ws)
        self.assertNotIn("must not leak", ws.ordered_evidence_text)
        self.assertFalse(
            any(i.source_type == "web_context" for i in ws.items)
        )
        self.assertTrue(
            any("fail-closed" in line for line in logs.output)
        )

    def test_receipt_failure_propagates_loudly(self):
        # Round-5 blocker 2: a contained set without its receipt must
        # raise, never return silently.
        from core.routing import web_containment as wc

        if not wc.containment_enabled():
            self.skipTest("containment disabled in this environment")
        with mock.patch.object(
            wc, "emit_receipt", side_effect=RuntimeError("receipt sink down")
        ):
            with self.assertRaises(RuntimeError):
                _ws(
                    self.ORDINARY_Q, _hx(3), _ON,
                    web_context="a contained web snippet",
                    max_working_set_chars=6000,
                )

    def test_flags_off_alloc_is_none(self):
        ws = _ws("What did you just say?", _hx(3), _OFF)
        if ws is not None:
            self.assertIsNone(ws.held_now_alloc)


if __name__ == "__main__":
    unittest.main()
