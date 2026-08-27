# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for the owner-path TRIPWIRE.

These tests do two different jobs and it is worth keeping them apart.

``FrozenInventoryTests`` is the tripwire itself firing: the tree must
match the frozen inventory in BOTH directions.

Everything else proves the tripwire can actually bite -- that the
scanner sees the shapes it claims to see, including the shape that
falsified the eighteenth round's census method (a mouth that sends and
returns nothing), and that it does not quietly grade the live tree.

None of this is evidence that the owner path is fully covered. See
``KNOWN_BLIND_SPOTS``.
"""

from __future__ import annotations

import json
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.owner_path_egress_tripwire import (
    CANNED_RETURN,
    FROZEN_PATH,
    KNOWN_BLIND_SPOTS,
    OWNER_PATH_SCOPES,
    SEND,
    Scope,
    freeze,
    inventory,
    load_frozen,
    repo_root,
    scan_repo,
    scan_source,
)


def _src(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


class FrozenInventoryTests(unittest.TestCase):
    """THE TRIPWIRE. Two-sided: a new site fails, a vanished site fails."""

    def test_the_tree_matches_the_frozen_inventory(self):
        found = inventory(scan_repo())
        frozen = load_frozen()

        added = {k: v for k, v in found.items() if frozen.get(k) != v}
        removed = {k: v for k, v in frozen.items() if k not in found}

        # Line numbers are machine-derived here, for the human who has to
        # go look. They are deliberately absent from the frozen keys.
        locations: dict[str, list[str]] = {}
        for site in scan_repo():
            locations.setdefault(site.key, []).append(
                f"{site.path}:{site.lineno}"
            )

        message_parts = []
        for key, count in sorted(added.items()):
            was = frozen.get(key, 0)
            message_parts.append(
                f"  CHANGED/NEW {key}\n"
                f"      frozen={was} found={count} at {locations.get(key)}"
            )
        for key, count in sorted(removed.items()):
            message_parts.append(f"  GONE        {key} (frozen={count})")

        self.assertEqual(
            (added, removed),
            ({}, {}),
            "\n\nOWNER-PATH TRIPWIRE TRIPPED.\n\n"
            + "\n".join(message_parts)
            + "\n\nThis is a TRIPWIRE, not a completeness proof. It says a\n"
            "watched site appeared, vanished or moved between constructs --\n"
            "nothing more, and nothing about whether the site reaches the\n"
            "ledger.\n\n"
            "If the change is intended, read what it does to the record\n"
            "first (A3: what enters the ledger when an interceptor answers\n"
            "before the seam), then regenerate:\n"
            "    python -m tests.owner_path_egress_tripwire --freeze\n"
            "and put the reasoning in the commit message. Do NOT hand-edit\n"
            "the counts.",
        )

    def test_the_frozen_file_is_exactly_what_the_generator_emits(self):
        """Hand-editing the frozen file to go green is itself caught."""
        on_disk = (repo_root() / FROZEN_PATH).read_text()
        self.assertEqual(
            on_disk,
            freeze(),
            "tests/data/owner_path_egress_tripwire.frozen.json is not "
            "byte-identical to what --freeze emits. It is MACHINE-DERIVED; "
            "regenerate it rather than editing it.",
        )


class CouncilNamedMissesTests(unittest.TestCase):
    """The sites the eighteenth round's own census method could not see.

    Not a claim that the tripwire would have found A3's gap -- it would
    not have, because it does not know what a ledger is. It is a claim
    that these three specific sites are inside the watched set, so a
    FUTURE one of the same shape trips the build.
    """

    def test_the_card_reply_interceptor_send_is_watched(self):
        # daemon/inbound_core.py:526 -- the CardRenderer sends (:541) and
        # the function may then return None (:577).
        self.assertIn(
            "daemon/inbound_core.py::run_inbound_turn::send::pipe.handle_reply",
            load_frozen(),
        )

    def test_the_approval_card_resolution_mouth_is_watched(self):
        # skills/approval_card.py -- send_resolution sends and returns None.
        self.assertIn(
            "skills/approval_card.py::TelegramTextRenderer.send_resolution"
            "::send::self.send_message_fn",
            load_frozen(),
        )

    def test_the_recall_receipt_mouth_is_watched(self):
        # daemon/maez_daemon.py:8612 -- delivers WORKING_RECEIPT_TEXT
        # inside the region a previous census called empty.
        self.assertIn(
            "daemon/maez_daemon.py::MaezDaemon.handle_message."
            "_arm_recall_receipt._fire_receipt::send::send_intermediate",
            load_frozen(),
        )


class TripwireBitesTests(unittest.TestCase):
    """Synthetic sources: the scanner must see each shape it claims."""

    def test_a_new_bare_canned_return_is_seen(self):
        before = _src(
            """
            def answer(x):
                return x
            """
        )
        after = _src(
            """
            def answer(x):
                if x:
                    return "I can't reach the web right now."
                return x
            """
        )
        self.assertEqual(inventory(scan_source("f.py", before)), {})
        self.assertEqual(
            inventory(scan_source("f.py", after)),
            {"f.py::answer::canned_return::": 1},
        )

    def test_a_new_direct_send_is_seen(self):
        after = _src(
            """
            def answer(transport, x):
                transport.send_message("done")
                return x
            """
        )
        self.assertEqual(
            inventory(scan_source("f.py", after)),
            {"f.py::answer::send::transport.send_message": 1},
        )

    def test_a_mouth_that_sends_and_returns_nothing_is_seen(self):
        """The shape that falsified the eighteenth round's census method.

        A census of reply-producing ``return`` statements sees NOTHING
        here. That is the whole point of carrying a second shape.
        """
        source = _src(
            """
            def send_resolution(self, card):
                self.send_message_fn(self.chat_id, format_text(card))
            """
        )
        found = inventory(scan_source("f.py", source))
        self.assertEqual(
            found, {"f.py::send_resolution::send::self.send_message_fn": 1}
        )
        self.assertNotIn("f.py::send_resolution::canned_return::", found)

    def test_a_vanished_site_is_a_change_too(self):
        """Two-sided. A tripwire that only watches additions can be
        satisfied by deleting the thing it was watching."""
        before = inventory(
            scan_source("f.py", _src('def a():\n    return "hi"\n'))
        )
        after = inventory(scan_source("f.py", _src("def a():\n    return 1\n")))
        self.assertEqual(before, {"f.py::a::canned_return::": 1})
        self.assertEqual(after, {})
        self.assertNotEqual(before, after)

    def test_canned_text_wrapped_in_a_response_helper_is_seen(self):
        """``return jsonify({"reply": "(internal error)"})``.

        A literal-only return shape misses this. The cockpit /message
        route is built exactly this way, which is why the return shape is
        deliberately over-broad.
        """
        source = _src(
            """
            def message():
                return jsonify({"reply": "(internal error)"})
            """
        )
        self.assertEqual(
            inventory(scan_source("f.py", source)),
            {"f.py::message::canned_return::": 1},
        )

    def test_a_module_level_canned_constant_is_folded(self):
        source = _src(
            """
            WORKING_RECEIPT_TEXT = "I'm checking my dated memory for that."

            def receipt():
                return WORKING_RECEIPT_TEXT
            """
        )
        self.assertEqual(
            inventory(scan_source("f.py", source)),
            {"f.py::receipt::canned_return::": 1},
        )

    def test_the_constant_fold_does_not_cross_a_function_boundary(self):
        """Folding across boundaries invents sites. It is scoped, and the
        scoping is a promise this test holds it to."""
        source = _src(
            """
            def outer():
                LOCAL_TEXT = "not a module constant"
                return LOCAL_TEXT
            """
        )
        self.assertEqual(inventory(scan_source("f.py", source)), {})

    def test_multiplicity_is_preserved(self):
        """A second site cannot hide behind the first."""
        source = _src(
            """
            def a(x):
                if x == 1:
                    return "one"
                if x == 2:
                    return "two"
                return x
            """
        )
        self.assertEqual(
            inventory(scan_source("f.py", source)),
            {"f.py::a::canned_return::": 2},
        )

    def test_a_nested_helper_does_not_collapse_onto_its_parent(self):
        """Closure scope is part of the identity -- the bypass the S7
        callsite scanner was hardened against."""
        source = _src(
            """
            def outer(transport):
                def _fire():
                    transport.send_message("working")
                return _fire
            """
        )
        self.assertEqual(
            inventory(scan_source("f.py", source)),
            {"f.py::outer._fire::send::transport.send_message": 1},
        )

    def test_a_blank_string_is_not_canned_text(self):
        source = _src('def a():\n    return ""\n')
        self.assertEqual(inventory(scan_source("f.py", source)), {})

    def test_the_send_shape_is_word_boundaried(self):
        """A mouth word must start the name or follow an underscore.

        ``resend`` and ``represent`` embed a mouth word mid-token and are
        not matched; that is what keeps the shape from matching most of
        the codebase.
        """
        source = _src(
            """
            def a(o):
                o.responder(1)
                o.represent(2)
                o.resend_hint(3)
            """
        )
        self.assertEqual(inventory(scan_source("f.py", source)), {})

    def test_the_send_shape_over_captures_and_that_is_the_chosen_bias(self):
        """``present_day`` is not a mouth and is matched anyway.

        Recorded rather than tuned away. A false positive costs one line
        in the frozen file; a false negative is the failure mode this
        exists to reduce. Tuning the shape until it looked clean would be
        re-deriving a census by taste.
        """
        source = _src(
            """
            def a(o):
                o.present_day(1)
                o.send_metrics_to_grafana(2)
            """
        )
        self.assertEqual(
            inventory(scan_source("f.py", source)),
            {
                "f.py::a::send::o.present_day": 1,
                "f.py::a::send::o.send_metrics_to_grafana": 1,
            },
        )

    def test_qualname_restriction_excludes_out_of_scope_constructs(self):
        source = _src(
            """
            class C:
                def watched(self):
                    return "seen"

                def unwatched(self):
                    return "not seen"
            """
        )
        self.assertEqual(
            inventory(scan_source("f.py", source, "C.watched")),
            {"f.py::C.watched::canned_return::": 1},
        )


class ScopeHygieneTests(unittest.TestCase):
    def test_every_watched_path_exists(self):
        """A phantom scope would silently watch nothing."""
        for scope in OWNER_PATH_SCOPES:
            with self.subTest(path=scope.path):
                self.assertTrue(
                    (repo_root() / scope.path).is_file(),
                    f"watched path missing: {scope.path}",
                )

    def test_every_narrowed_qualname_actually_resolves(self):
        """A renamed construct would narrow the scope to NOTHING and the
        tripwire would go quietly green over an unwatched file."""
        for scope in OWNER_PATH_SCOPES:
            if scope.qualname is None:
                continue
            with self.subTest(scope=f"{scope.path}::{scope.qualname}"):
                source = (repo_root() / scope.path).read_text()
                whole = scan_source(scope.path, source)
                narrowed = scan_source(scope.path, source, scope.qualname)
                self.assertTrue(
                    narrowed,
                    f"{scope.qualname} matched no site in {scope.path} -- "
                    "renamed or moved? The scope is watching nothing.",
                )
                self.assertLess(len(narrowed), len(whole))

    def test_every_scope_carries_its_reason(self):
        for scope in OWNER_PATH_SCOPES:
            with self.subTest(path=scope.path):
                self.assertGreater(len(scope.why), 60)

    def test_the_repo_root_is_not_pinned_to_the_live_tree(self):
        """The hermetic-sandbox scar.

        53 of this repo's 785 test files pin an absolute home-directory
        path as their repo root, so their source-text assertions grade
        the LIVE TREE whatever checkout pytest is running in. The
        surface-registry slice had to repair its own guard before it
        could be witnessed at all, for exactly this reason.

        Checked as a shape rather than against one known path, so the
        guard neither hardcodes the thing it forbids nor goes green for
        a different user's home. ``/var/tmp`` stays legal: probes belong
        there, not on a tmpfs that a reboot wipes.
        """
        import ast as _ast
        import re as _re

        home_rooted = _re.compile(r"^/(home|Users|root)(/|$)")
        for name in (
            "tests/owner_path_egress_tripwire.py",
            "tests/test_owner_path_egress_tripwire.py",
        ):
            with self.subTest(module=name):
                tree = _ast.parse((repo_root() / name).read_text())
                offenders = [
                    (node.lineno, node.value)
                    for node in _ast.walk(tree)
                    if isinstance(node, _ast.Constant)
                    and isinstance(node.value, str)
                    and home_rooted.match(node.value)
                ]
                self.assertEqual(
                    offenders,
                    [],
                    f"{name} pins an absolute home-rooted path: {offenders}",
                )

    def test_the_scanner_grades_the_tree_it_is_pointed_at(self):
        """Hermetic witness, not a source-text inference.

        Builds a fake tree carrying the real scope paths with known
        contents and proves the scan reflects THOSE bytes -- so a
        checkout other than the live one is graded honestly.
        """
        with TemporaryDirectory(dir="/var/tmp") as tmp:
            root = Path(tmp)
            for scope in OWNER_PATH_SCOPES:
                target = root / scope.path
                target.parent.mkdir(parents=True, exist_ok=True)
                if scope.qualname is None:
                    body = 'def only():\n    return "fake tree"\n'
                else:
                    # Rebuild the narrowed construct's dotted anchor as
                    # real nesting so the qualname resolves in the fake.
                    parts = scope.qualname.split(".")
                    body = ""
                    for depth, part in enumerate(parts):
                        pad = "    " * depth
                        kw = "class" if depth == 0 and part[:1].isupper() else "def"
                        sig = "" if kw == "class" else "()"
                        body += f"{pad}{kw} {part}{sig}:\n"
                    body += "    " * len(parts) + 'return "fake tree"\n'
                target.write_text(body)

            found = inventory(scan_repo(root))

        self.assertTrue(found, "the fake tree produced no sites at all")
        for key in found:
            self.assertTrue(
                key.endswith("::canned_return::"),
                f"unexpected site from the fake tree: {key}",
            )
        # And the live tree's own distinctive sites are absent from it.
        self.assertNotIn(
            "daemon/inbound_core.py::run_inbound_turn::send::pipe.handle_reply",
            found,
        )


class FramingTests(unittest.TestCase):
    """The framing is load-bearing, so it is asserted, not just written.

    The eighteenth round declared A3 not build-ready precisely because
    three censuses disagreed. A guard that drifts into being cited as
    'the list of Maez's mouths' would re-import the falsified claim.
    """

    def _scanner_source(self) -> str:
        return (repo_root() / "tests/owner_path_egress_tripwire.py").read_text()

    def test_the_module_disclaims_completeness_in_its_first_line(self):
        import tests.owner_path_egress_tripwire as mod

        doc = mod.__doc__ or ""
        self.assertIn("THIS IS NOT A COMPLETENESS PROOF", doc)
        self.assertIn("TRIPWIRE", doc)

    def test_the_module_makes_no_completeness_claim(self):
        source = self._scanner_source().lower()
        for phrase in (
            "every egress",
            "all egress",
            "every mouth",
            "all mouths",
            "exhaustive",
            "complete census",
            "full census",
            "guarantees that",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, source)

    def test_the_blind_spots_are_enumerated_and_substantial(self):
        self.assertGreaterEqual(len(KNOWN_BLIND_SPOTS), 5)
        for spot in KNOWN_BLIND_SPOTS:
            with self.subTest(spot=spot[:40]):
                self.assertGreater(len(spot), 60)

    def test_the_named_blind_spots_cover_the_ways_this_can_be_fooled(self):
        joined = " ".join(KNOWN_BLIND_SPOTS).lower()
        for topic in ("scope", "runs", "getattr", "kwargs", "reword"):
            with self.subTest(topic=topic):
                self.assertIn(topic, joined)

    def test_the_frozen_file_carries_the_disclaimer(self):
        payload = json.loads((repo_root() / FROZEN_PATH).read_text())
        note = payload["_"]
        self.assertIn("TRIPWIRE", note)
        self.assertIn("NOT a completeness proof", note)
        self.assertIn("MACHINE-DERIVED", note)

    def test_scope_is_declared_not_derived(self):
        """If OWNER_PATH_SCOPES were ever computed, the tripwire would be
        claiming to have found the owner path. It must stay a literal."""
        self.assertIsInstance(OWNER_PATH_SCOPES, tuple)
        for scope in OWNER_PATH_SCOPES:
            self.assertIsInstance(scope, Scope)
            self.assertIsInstance(scope.path, str)


if __name__ == "__main__":
    unittest.main()
