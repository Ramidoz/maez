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

import ast
import json
import os
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.owner_path_egress_tripwire import (
    CANNED_RETURN,
    FROZEN_PATH,
    construct_qualnames,
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

    def test_the_frozen_file_is_byte_canonical_for_the_generator(self):
        """The frozen file must be exactly the generator's output bytes.

        What this catches is a NONCANONICAL edit -- wrong ordering,
        wrong indentation, a stray key, CRLF. It does NOT catch a human
        typing the byte-exact line the generator would have produced for
        a site that really exists; nothing textual can (Codex boundary
        walk, B5). The defence against that is the tree comparison
        above, which reads the actual source.

        Compared as BYTES. ``read_text()`` performs universal-newline
        translation, so a CRLF-rewritten frozen file would compare equal
        to the generator's LF output while the file on disk was not in
        fact what the generator emits -- a claim of byte-identity that
        was not byte-identity (Codex boundary walk, B5).
        """
        on_disk = (repo_root() / FROZEN_PATH).read_bytes()
        self.assertEqual(
            on_disk,
            freeze().encode("utf-8"),
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

    def test_the_web_owner_s4_early_return_is_watched(self):
        """The omission that mattered most (Codex boundary walk, B7).

        skills/web_interface.py returns the S4 crisis answer at :6807
        BEFORE submitting the owner's turn to the spool -- the same
        early-egress shape as inbound_core's S4 return, which the first
        roster watched while missing this one. Two rosters, two
        different answers: the second time in this arc that a scope list
        was found incomplete, which is the argument FOR the tripwire
        framing, not against it.
        """
        self.assertIn("skills/web_interface.py::chat::canned_return::", load_frozen())

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

    def test_canned_text_inside_a_lambda_body_is_seen(self):
        """A lambda has no Return node at all.

        Codex boundary walk, B2: a canned sentence behind a lambda was
        invisible to the return shape. The live tree really contains
        one -- skills/surface/maez_adapter.py wraps the card-reply mouth
        in ``lambda: pipe.handle_reply(..., channel="telegram_text")``.
        """
        source = _src(
            """
            def a(o):
                o.on_click(lambda: "canned from inside a lambda")
            """
        )
        found = inventory(scan_source("f.py", source))
        self.assertEqual(found.get("f.py::a::canned_return::"), 1)

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
        tripwire would go quietly green over an unwatched file.

        Checked by asking whether the construct EXISTS, not by comparing
        site counts. An earlier version asserted the narrowed scan found
        strictly fewer sites than the whole module, which is unsound: a
        scope whose construct happens to contain every site in its file
        is perfectly valid and would have gone red. It passed only by
        accident of the current tree. Emptiness is not checked either --
        a watched construct with no sites is honest, and the frozen
        inventory records that absence.
        """
        for scope in OWNER_PATH_SCOPES:
            if scope.qualname is None:
                continue
            with self.subTest(scope=f"{scope.path}::{scope.qualname}"):
                tree = ast.parse((repo_root() / scope.path).read_text(encoding="utf-8"))
                names = construct_qualnames(tree)
                # Only the near-misses: dumping every construct in a
                # 13k-line module is not a failure message anyone reads.
                tail = scope.qualname.rsplit(".", 1)[-1]
                nearby = sorted(
                    n for n in names if tail[:12] in n or n.endswith(tail)
                )[:8]
                self.assertIn(
                    scope.qualname,
                    names,
                    f"{scope.qualname} is not a construct in {scope.path} -- "
                    "renamed or moved? The scope is watching NOTHING, and "
                    "the tripwire would go quietly green over that file.\n"
                    f"Nearest constructs: {nearby}",
                )

    def test_a_scope_holding_every_site_in_its_file_is_still_valid(self):
        """The soundness case the old count-comparison got wrong.

        Codex's boundary walk produced it: a construct that happens to
        contain all of its file's sites is a perfectly good scope, and
        the previous ``narrowed < whole`` assertion would have failed it.
        """
        source = _src(
            """
            class C:
                def watched(self):
                    return "the only site in this file"
            """
        )
        whole = scan_source("f.py", source)
        narrowed = scan_source("f.py", source, "C.watched")
        self.assertEqual(len(narrowed), len(whole))
        self.assertIn("C.watched", construct_qualnames(ast.parse(source)))

    def test_a_renamed_construct_stops_resolving(self):
        source = _src(
            """
            class C:
                def renamed_away(self):
                    return "still here, under another name"
            """
        )
        names = construct_qualnames(ast.parse(source))
        self.assertIn("C.renamed_away", names)
        self.assertNotIn("C.watched", names)

    def test_the_declared_scope_roster_is_exactly_this(self):
        """Deleting a watched scope must be a deliberate, two-place act.

        Codex's boundary walk: drop a scope from OWNER_PATH_SCOPES,
        regenerate the frozen file, and every other check stays green --
        the sites simply stop being watched and the inventory honestly
        records the smaller world. Regeneration absorbs the deletion.
        So the roster is pinned HERE, in the test, where regeneration
        cannot reach it.
        """
        self.assertEqual(
            tuple((s.path, s.qualname) for s in OWNER_PATH_SCOPES),
            (
                ("daemon/inbound_core.py", None),
                ("skills/surface/maez_adapter.py", None),
                ("skills/telegram_voice.py", "TelegramVoice._process_message"),
                ("skills/approval_card.py", None),
                ("core/routing/recall_receipt.py", None),
                ("daemon/maez_daemon.py", "MaezDaemon.handle_message"),
                ("skills/web_interface.py", "chat"),
                ("skills/surface/telegram_adapter.py", None),
                (
                    "skills/surface/platform_base.py",
                    "BasePlatformAdapter._send_with_retry",
                ),
                ("core/brain/brain_loop.py", "_emit_search_progress"),
                ("cli/maez_chat.py", None),
                (
                    "skills/telegram_voice.py",
                    "TelegramVoice._send_card_message",
                ),
                ("skills/telegram_voice.py", "TelegramVoice.send_envelope"),
                (
                    "daemon/maez_daemon.py",
                    "MaezDaemon._run_health_server.message",
                ),
            ),
            "The watched-scope roster changed. Adding a scope is good and "
            "this list should follow it. REMOVING one narrows what the "
            "build watches and cannot be done by regenerating the frozen "
            "file -- say in the commit message why the path stopped "
            "mattering.",
        )

    def test_every_scope_carries_its_reason(self):
        for scope in OWNER_PATH_SCOPES:
            with self.subTest(path=scope.path):
                self.assertGreater(len(scope.why), 60)

    def test_freezing_survives_a_c_locale(self):
        """Codex boundary walk, B5: ``read_text()`` without an explicit
        encoding raised UnicodeDecodeError under LC_ALL=C PYTHONUTF8=0,
        so the tripwire crashed rather than reporting, on a machine
        configured differently from this one."""
        import subprocess
        import sys

        env = {
            "LC_ALL": "C",
            "LANG": "C",
            "PYTHONUTF8": "0",
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
        }
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; sys.path.insert(0, %r);"
                "from tests.owner_path_egress_tripwire import freeze;"
                "print(len(freeze()))" % str(repo_root()),
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(repo_root()),
        )
        self.assertEqual(
            proc.returncode, 0, f"freeze() failed under C locale:\n{proc.stderr}"
        )

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
                tree = _ast.parse((repo_root() / name).read_text(encoding="utf-8"))
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
        def _chain(qualname: str | None) -> str:
            if qualname is None:
                return 'def only():\n    return "fake tree"\n'
            # Rebuild the narrowed construct's dotted anchor as real
            # nesting so the qualname resolves in the fake.
            parts = qualname.split(".")
            body = ""
            for depth, part in enumerate(parts):
                pad = "    " * depth
                kw = "class" if depth == 0 and part[:1].isupper() else "def"
                sig = "" if kw == "class" else "()"
                body += f"{pad}{kw} {part}{sig}:\n"
            return body + "    " * len(parts) + 'return "fake tree"\n'

        # Scopes are grouped BY PATH before writing. Two scopes share
        # daemon/maez_daemon.py, and writing them one-per-scope made the
        # second clobber the first -- MaezDaemon.handle_message silently
        # contributed zero sites while this test still passed on the
        # aggregate (Codex boundary walk, B4).
        by_path: dict[str, list[Scope]] = {}
        for scope in OWNER_PATH_SCOPES:
            by_path.setdefault(scope.path, []).append(scope)

        with TemporaryDirectory(dir="/var/tmp") as tmp:
            root = Path(tmp)
            for path, scopes in by_path.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    "\n".join(_chain(s.qualname) for s in scopes)
                )

            found = inventory(scan_repo(root))
            # EVERY scope must contribute, or the witness is vacuous for
            # the ones that do not.
            for scope in OWNER_PATH_SCOPES:
                with self.subTest(scope=f"{scope.path}::{scope.qualname}"):
                    self.assertTrue(
                        scan_source(
                            scope.path,
                            (root / scope.path).read_text(encoding="utf-8"),
                            scope.qualname,
                        ),
                        "this scope produced no site in the fake tree, so "
                        "the hermetic witness proves nothing about it",
                    )

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

    def test_the_scanner_and_these_tests_resolve_the_same_repo(self):
        """The subtler form of the hermetic scar (Codex boundary walk, B4).

        ``repo_root()`` resolves from the SCANNER module's ``__file__``.
        Copy these tests into another checkout while the scanner still
        imports from the live tree, and the suite grades the LIVE tree
        while appearing to test the copy. The two roots must be bound.
        """
        self.assertEqual(
            Path(__file__).resolve().parents[1],
            repo_root(),
            "the test module and the scanner module resolve to DIFFERENT "
            "repository roots -- the scanner is being imported from a "
            "checkout other than the one holding these tests, so the "
            "results describe a tree nobody is looking at",
        )


class FramingTests(unittest.TestCase):
    """The framing is load-bearing, so it is asserted, not just written.

    The eighteenth round declared A3 not build-ready precisely because
    three censuses disagreed. A guard that drifts into being cited as
    'the list of Maez's mouths' would re-import the falsified claim.
    """

    def _scanner_source(self) -> str:
        return (repo_root() / "tests/owner_path_egress_tripwire.py").read_text(encoding="utf-8")

    def test_the_module_docstring_opens_by_disclaiming_completeness(self):
        """Checked against the opening paragraph, which the previous
        name claimed and did not inspect."""
        import tests.owner_path_egress_tripwire as mod

        doc = mod.__doc__ or ""
        opening = doc.split("\n\n", 2)[:2]
        self.assertIn(
            "THIS IS NOT A COMPLETENESS PROOF", "\n\n".join(opening)
        )
        self.assertIn("TRIPWIRE", doc)

    def test_the_module_avoids_a_denylist_of_completeness_phrases(self):
        """A DENYLIST, not a proof of absence.

        Passing means these particular phrasings are absent, not that no
        completeness claim can be made in words nobody thought of. The
        previous name asserted the stronger thing (Codex, B1)."""
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

    def test_the_named_blind_spots_are_exactly_these(self):
        """Pinned by topic, because a keyword spot-check let one be
        deleted silently.

        A mutation removing the COMPREHENSIONS AND DEFAULTS entry passed
        every other framing check: the count floor still held and the
        five sampled keywords all survived. Losing a NAMED blind spot is
        precisely the drift toward an implied completeness claim that
        the eighteenth round warned about, so the roster is pinned.
        Adding one trips this too -- that is intended; growing the list
        is healthy and should be a deliberate, visible edit.
        """
        topics = tuple(spot.split(".", 1)[0] for spot in KNOWN_BLIND_SPOTS)
        self.assertEqual(
            topics,
            (
                "SCOPE",
                "LIVENESS",
                "NAME SHAPE",
                "INDIRECTION",
                "COMPREHENSIONS AND DEFAULTS",
                "WORDING",
                "SEMANTICS",
                "NON-PYTHON MOUTHS",
            ),
        )

    def test_the_named_blind_spots_mention_the_known_evasions(self):
        """Keyword spot-check over the evasions already FOUND.

        The set of ways a syntactic scan can be fooled is not
        enumerable, so this cannot and does not claim coverage of it --
        the previous name did (Codex, B1)."""
        joined = " ".join(KNOWN_BLIND_SPOTS).lower()
        for topic in ("scope", "runs", "getattr", "kwargs", "reword"):
            with self.subTest(topic=topic):
                self.assertIn(topic, joined)

    def test_the_frozen_file_carries_the_disclaimer(self):
        payload = json.loads((repo_root() / FROZEN_PATH).read_text(encoding="utf-8"))
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
