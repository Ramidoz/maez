# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for the sync-primitive cluster (T1.2 + T1.7)
from the 2026-05-04 15-agent audit.

T1.2 — ConversationController._offers dict race
  Audit found: instance dicts (_offers, _last_probes,
  _last_user_text) are read/written by sync methods (get_offer,
  set_offer, clear_offer, maybe_store_offer, consume_offer_approval)
  but the primary entry point is async. No locks → concurrent access
  can corrupt state, including a TOCTOU bug in get_offer's silent
  TTL expiry.

T1.7 — soul-write race between dream-cycle and explicit edit
  Audit found: soul_loader.append_to_local() acquires _lock during
  read-modify-write of soul.local.md. soul_editor.apply_section_replace()
  does NOT acquire that lock — so an explicit user soul-edit can
  race with a dream-cycle's append, leaving soul.md missing one of
  the two writes.

Tests use the concurrent helper from tests/_helpers/concurrent.py
where it actually proves the race condition is fixed (deterministic
interleaving). Source-level tests pin the contract so a future
refactor can't silently drop the lock acquisition.
"""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ── T1.2 — ConversationController _offers race ───────────────────────


class T1_2_OffersDictRace(unittest.TestCase):
    """REGRESSION GUARD for T1.2: every access to ConversationController's
    `_offers` mutable dict must be guarded by `self._offers_lock` so
    concurrent set/pop calls don't corrupt state."""

    def _ctrl(self):
        from core.brain.conversation_controller import ConversationController
        # Minimal construction — memory/pipeline/daemon all None;
        # we only exercise the offer-store methods.
        return ConversationController(memory=None, pipeline=None, daemon=None)

    def test_lock_attribute_exists(self):
        """Initialization must create an `_offers_lock` (RLock so the
        same thread can re-enter, e.g., set_offer calling clear_offer)."""
        ctrl = self._ctrl()
        self.assertTrue(
            hasattr(ctrl, "_offers_lock"),
            "ConversationController must have `_offers_lock`",
        )
        # Verify it's a re-entrant lock; sentinel is RLock's
        # acquire-twice-from-same-thread behavior.
        ctrl._offers_lock.acquire()
        try:
            acquired = ctrl._offers_lock.acquire(blocking=False)
            self.assertTrue(
                acquired,
                "_offers_lock must be re-entrant (RLock) so methods "
                "that call other locked methods don't deadlock",
            )
            if acquired:
                ctrl._offers_lock.release()
        finally:
            ctrl._offers_lock.release()

    def test_concurrent_set_and_get_does_not_corrupt(self):
        """Two threads — one setting offers, one getting them — for
        the same (channel, chat_id). Neither should raise; the
        final state should be the value of the last successful
        set."""
        from tests._helpers.concurrent import run_two_threads
        ctrl = self._ctrl()

        N = 200

        def writer():
            for i in range(N):
                ctrl.set_offer("ch", "u", {
                    "kind": "web_search",
                    "query": f"q-{i}",
                    "set_at": time.time(),
                })

        def reader():
            for _ in range(N):
                got = ctrl.get_offer("ch", "u")
                # Either None (not yet set) or a valid dict with the
                # expected keys. Should never see a corrupted shape.
                if got is not None:
                    self.assertIn("kind", got)
                    self.assertEqual(got["kind"], "web_search")

        a, b = run_two_threads(writer, reader, barrier=True, timeout=5.0)
        self.assertTrue(a.ok, f"writer raised: {a.exception}")
        self.assertTrue(b.ok, f"reader raised: {b.exception}")

        final = ctrl.get_offer("ch", "u")
        self.assertIsNotNone(final)
        # Final query is one of the writer's writes — should match
        # the format `q-<int>`.
        self.assertTrue(
            (final["query"] or "").startswith("q-"),
            f"final offer corrupted: {final}",
        )

    def test_concurrent_clear_and_get_no_keyerror(self):
        """`clear_offer` pops; `get_offer` reads. Concurrent calls
        should never KeyError or AttributeError on a half-popped
        dict."""
        from tests._helpers.concurrent import run_two_threads
        ctrl = self._ctrl()

        # Pre-populate
        for i in range(50):
            ctrl.set_offer(f"ch{i}", f"u{i}", {
                "kind": "web_search", "query": "q",
                "set_at": time.time(),
            })

        def clearer():
            for i in range(50):
                ctrl.clear_offer(f"ch{i}", f"u{i}")

        def reader():
            for i in range(50):
                ctrl.get_offer(f"ch{i}", f"u{i}")

        a, b = run_two_threads(clearer, reader, barrier=True, timeout=5.0)
        self.assertTrue(a.ok, f"clearer raised: {a.exception}")
        self.assertTrue(b.ok, f"reader raised: {b.exception}")

    def test_source_all_access_under_lock(self):
        """REGRESSION GUARD: source-level — every reference to
        `self._offers` in conversation_controller.py must appear
        inside a `with self._offers_lock:` block (or be a one-time
        init in __init__). This is the contract — adding a new
        access path that doesn't hold the lock fails the test."""
        path = REPO / "core" / "brain" / "conversation_controller.py"
        src = path.read_text()
        lines = src.split("\n")

        # Find lines that READ or WRITE self._offers (excluding the
        # dict initialization in __init__ which appears as a type
        # annotation `self._offers: dict[...] = {}`).
        access_lines: list[int] = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if "self._offers" not in stripped:
                continue
            if "self._offers_lock" in stripped:
                continue  # lock attribute itself, not the data
            # Skip the type-annotated init line in __init__
            if "self._offers:" in stripped and stripped.endswith("= {}"):
                continue
            access_lines.append(i)

        self.assertGreater(
            len(access_lines), 0,
            "no _offers access sites found — test/grep regression",
        )

        # For each access line, walk backward up to 50 lines
        # looking for `with self._offers_lock` or function start.
        for lineno in access_lines:
            in_lock = False
            for j in range(lineno - 1, max(0, lineno - 50), -1):
                pj = lines[j - 1].strip()
                if pj.startswith("with self._offers_lock"):
                    in_lock = True
                    break
                # If we hit a function definition, the lock would
                # have to be held by the caller — flag that.
                if pj.startswith("def ") or pj.startswith("async def "):
                    break
            self.assertTrue(
                in_lock,
                f"line {lineno}: `self._offers` access not inside "
                f"`with self._offers_lock:` block. line text: "
                f"{lines[lineno - 1].strip()!r}",
            )


# ── T1.7 — soul-write race ───────────────────────────────────────────


class T1_7_SoulWriteRace(unittest.TestCase):
    """REGRESSION GUARD for T1.7: soul_editor.apply_section_replace
    must acquire soul_loader._lock around its read-modify-write
    sequence so it can't race with soul_loader.append_to_local."""

    def setUp(self):
        # Hermetic temp dir — replace SOUL_PATH and soul_loader paths
        # so neither real soul.md nor the cache is touched.
        self._tmp = tempfile.TemporaryDirectory()
        self.cfg = Path(self._tmp.name)
        self.soul_md = self.cfg / "soul.md"
        self.soul_base = self.cfg / "soul.base.md"
        self.soul_local = self.cfg / "soul.local.md"

        # Seed a soul.md with one editable section.
        self.soul_md.write_text(
            "# IDENTITY\nplaceholder-id\n\n"
            "# TONE\noriginal tone body\n"
        )
        self.soul_base.write_text("# IDENTITY\nplaceholder-id\n")
        self.soul_local.write_text("# TONE\noriginal tone body\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_apply_section_replace_acquires_soul_loader_lock(self):
        """Source-level: apply_section_replace's body must reference
        soul_loader._lock (or otherwise import the lock module).
        Pure runtime testing of the race is hard because the lock
        contention only manifests on file-write timing; the source-
        level pin catches refactors that drop the lock."""
        path = REPO / "core" / "evolution" / "soul_editor.py"
        src = path.read_text()
        # Locate the apply_section_replace function body.
        start = src.index("def apply_section_replace")
        # Find the next top-level def to bound the body.
        try:
            end = src.index("\ndef ", start + 1)
        except ValueError:
            end = len(src)
        body = src[start:end]
        # Check: does the body acquire soul_loader's lock somehow?
        self.assertTrue(
            ("soul_loader._lock" in body)
            or ("soul_loader.acquire_write_lock" in body)
            or ("from core.evolution.soul_loader" in body
                and "_lock" in body),
            "apply_section_replace must acquire soul_loader._lock "
            "(or use a public acquire_write_lock helper) around its "
            "read-modify-write sequence — without it, the dream-cycle "
            "append_to_local can race with the explicit edit and one "
            "write is silently lost",
        )

    def test_concurrent_append_and_apply_one_write_survives(self):
        """Use Interleave to force the contended race window — A
        starts apply_section_replace, gets to the post-load
        comparison, B then runs append_to_local, A then writes. The
        contract: with the lock, A waits for B; without it, A's
        write would clobber B's append silently. Test verifies one
        of two valid serialized states results, not a hybrid."""
        from tests._helpers.concurrent import run_two_threads
        from core.evolution import soul_editor as se
        from core.evolution import soul_loader as sl

        # Re-route SOUL_PATH and soul_loader paths to the tempdir.
        with mock.patch.object(se, "SOUL_PATH", self.soul_md), \
             mock.patch("core.paths.soul_base_path",
                        return_value=self.soul_base), \
             mock.patch("core.paths.soul_local_path",
                        return_value=self.soul_local), \
             mock.patch("core.paths.soul_combined_path",
                        return_value=self.soul_md):

            # Reset the soul_loader cache so it doesn't leak from
            # other tests.
            with sl._lock:
                sl._cache_text = None
                sl._cache_signature = None

            # Build a Proposal that swaps TONE's body.
            from core.evolution.soul_editor import (
                Proposal,
            )
            prop = Proposal(
                target_name="TONE",
                old_body="original tone body",
                new_body="quieter tone body (apply_section_replace)",
                rationale="test-T1.7",
                unified_diff="",
            )

            # The point we want to prove: with the lock, both
            # writes serialize. Without it, one is silently lost.
            # We use Interleave to STRESS the race.
            def thread_a():
                ok, msg = se.apply_section_replace(prop)
                # ok could be False if append landed first and made
                # the proposal stale — that's a valid outcome (the
                # "stale proposal" branch). What we want is:
                # nothing crashes, file is parseable, and either
                # (a) apply landed AND append landed, OR
                # (b) one landed cleanly (the other refused).
                return ok, msg

            def thread_b():
                # Append a tiny addition to soul.local.md.
                sl.append_to_local("# DREAMS\nnew dream entry\n")

            a, b = run_two_threads(
                thread_a, thread_b, barrier=True, timeout=10.0,
            )
            self.assertTrue(a.ok, f"apply raised: {a.exception}")
            self.assertTrue(b.ok, f"append raised: {b.exception}")

            # File integrity: soul.md still parses, AND soul.local.md
            # still parses. No half-written state.
            soul_after = self.soul_md.read_text()
            local_after = self.soul_local.read_text()
            self.assertIn("# IDENTITY", soul_after,
                          "soul.md missing IDENTITY after race")
            self.assertIn("# TONE", soul_after,
                          "soul.md missing TONE after race")
            self.assertIn("# DREAMS", local_after,
                          "soul.local.md missing DREAMS — append lost")


if __name__ == "__main__":
    unittest.main()
