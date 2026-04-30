# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Canary token tests (Slice 6 — defense-in-depth literature).

Adapted from CaMeL (Capabilities for Machine Learning, arxiv
2503.18813) and broader prompt-injection / fabrication-detection
literature. The threat model for Maez (single-bonded-companion,
not customer-service-bot) is **memory bleeding / fabrication**,
not classical prompt injection: the risk is Maez paraphrasing
internal evidence-ids into the reply, or fabricating identifiers
that look real around real values.

Canary tokens close that gap by:

1. Generating unique random strings (``MAEZ-CANARY-XXX``) that
   never appear in training data.
2. Injecting them into context positions where the model
   should NOT echo (e.g., as fake evidence-ids in the lived-recall
   brief).
3. Scanning final replies for canary leakage. Any echo is a
   fabrication / memory-bleeding signal.

What this slice ships:

- ``CanaryStore`` — SQLite-backed registry of issued canaries
- ``generate_canary()`` — random unique token
- ``register_canary(context)`` — persist + return the token
- ``scan_for_leakage(text)`` — return any leaked canaries
- ``record_leak(canary, text_excerpt)`` — leak audit trail
- Integration with ``audited_output``: leaks are detected and
  stripped before the reply hits the storage / chat surface
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _store():
    from core.safety.canaries import CanaryStore

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    p = Path(f.name)

    def cleanup():
        p.unlink(missing_ok=True)

    return CanaryStore(db_path=p), cleanup


# ── token generation ────────────────────────────────────────────────


class TestGenerateCanary(unittest.TestCase):
    def test_generated_token_has_canary_prefix(self):
        from core.safety.canaries import generate_canary

        tok = generate_canary()
        self.assertTrue(
            tok.startswith("MAEZ-CANARY-"),
            f"canary tokens must carry the MAEZ-CANARY- prefix; got {tok!r}",
        )

    def test_generated_tokens_are_unique(self):
        from core.safety.canaries import generate_canary

        tokens = {generate_canary() for _ in range(50)}
        self.assertEqual(len(tokens), 50,
                         "50 generations must produce 50 unique tokens")

    def test_token_format_safe_for_substring_match(self):
        """The token must be plain ASCII letters / digits / dashes
        — no regex-meta or shell-meta chars that would break
        substring search or text mangling."""
        from core.safety.canaries import generate_canary

        tok = generate_canary()
        self.assertRegex(tok, r"^MAEZ-CANARY-[A-Za-z0-9]+$",
                         f"unexpected canary format: {tok!r}")


# ── store ───────────────────────────────────────────────────────────


class TestCanaryStore(unittest.TestCase):
    def test_register_persists(self):
        store, cleanup = _store()
        try:
            tok = store.register_canary(context="brief:lived_recall")
            rows = store.active_canaries()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["token"], tok)
            self.assertEqual(rows[0]["context"], "brief:lived_recall")
        finally:
            cleanup()

    def test_active_canaries_returns_recent_first(self):
        store, cleanup = _store()
        try:
            t1 = store.register_canary(context="a")
            t2 = store.register_canary(context="b")
            rows = store.active_canaries()
            self.assertEqual(len(rows), 2)
            tokens = [r["token"] for r in rows]
            self.assertIn(t1, tokens)
            self.assertIn(t2, tokens)
        finally:
            cleanup()

    def test_active_set_for_fast_match(self):
        """Returns a frozenset of currently-active tokens for O(1)
        substring lookup."""
        store, cleanup = _store()
        try:
            t = store.register_canary(context="x")
            active = store.active_token_set()
            self.assertIn(t, active)
            self.assertIsInstance(active, frozenset)
        finally:
            cleanup()


# ── leak detection ──────────────────────────────────────────────────


class TestScanForLeakage(unittest.TestCase):
    def test_clean_text_returns_empty(self):
        from core.safety.canaries import scan_for_leakage

        canary_set = frozenset({"MAEZ-CANARY-abc123"})
        leaked = scan_for_leakage("hello world, no canaries here", canary_set)
        self.assertEqual(leaked, [])

    def test_leaked_canary_detected(self):
        from core.safety.canaries import scan_for_leakage

        canary_set = frozenset({"MAEZ-CANARY-abc123"})
        text = "Maez said: ep-xxx | sources: MAEZ-CANARY-abc123"
        leaked = scan_for_leakage(text, canary_set)
        self.assertEqual(leaked, ["MAEZ-CANARY-abc123"])

    def test_multiple_leaks_returned_unique(self):
        from core.safety.canaries import scan_for_leakage

        canary_set = frozenset({
            "MAEZ-CANARY-aaa", "MAEZ-CANARY-bbb", "MAEZ-CANARY-ccc",
        })
        text = (
            "MAEZ-CANARY-aaa, MAEZ-CANARY-bbb, MAEZ-CANARY-aaa, "
            "MAEZ-CANARY-aaa"  # repeated 'aaa' — must dedupe
        )
        leaked = scan_for_leakage(text, canary_set)
        self.assertEqual(set(leaked), {"MAEZ-CANARY-aaa", "MAEZ-CANARY-bbb"})

    def test_empty_canary_set_no_op(self):
        from core.safety.canaries import scan_for_leakage

        leaked = scan_for_leakage("anything goes", frozenset())
        self.assertEqual(leaked, [])

    def test_empty_text_no_op(self):
        from core.safety.canaries import scan_for_leakage

        canary_set = frozenset({"MAEZ-CANARY-abc"})
        self.assertEqual(scan_for_leakage("", canary_set), [])
        self.assertEqual(scan_for_leakage(None, canary_set), [])


# ── leak record + observability ─────────────────────────────────────


class TestRecordLeak(unittest.TestCase):
    def test_leak_recorded_with_excerpt(self):
        store, cleanup = _store()
        try:
            tok = store.register_canary(context="brief:lived_recall")
            store.record_leak(
                token=tok,
                surface="telegram",
                text_excerpt=f"Maez echoed {tok} in reply",
            )
            leaks = store.recent_leaks()
            self.assertEqual(len(leaks), 1)
            self.assertEqual(leaks[0]["token"], tok)
            self.assertEqual(leaks[0]["surface"], "telegram")
            self.assertIn("echoed", leaks[0]["text_excerpt"])
        finally:
            cleanup()

    def test_recent_leaks_newest_first(self):
        store, cleanup = _store()
        try:
            t1 = store.register_canary(context="a")
            t2 = store.register_canary(context="b")
            store.record_leak(token=t1, surface="s1", text_excerpt="first")
            store.record_leak(token=t2, surface="s2", text_excerpt="second")
            leaks = store.recent_leaks()
            self.assertEqual(leaks[0]["token"], t2)
        finally:
            cleanup()

    def test_record_leak_unknown_token_persists_anyway(self):
        """Defensive: record any token reported as leaked even if
        not registered — useful for cross-process scenarios."""
        store, cleanup = _store()
        try:
            store.record_leak(
                token="MAEZ-CANARY-unknown",
                surface="x",
                text_excerpt="leak content",
            )
            self.assertEqual(len(store.recent_leaks()), 1)
        finally:
            cleanup()


# ── integration with audited_output ─────────────────────────────────


class TestAuditedOutputCanaryStripping(unittest.TestCase):
    """Integration: ``audit_assistant_text`` should detect canary
    leakage and strip the canary from the reply before storage /
    return. The strip is ALSO recorded as a leak event so the
    cockpit can show fabrication-class signals."""

    def test_canary_leak_stripped_from_reply(self):
        # Set up a canary in the active set, then synthesise a
        # reply that contains it, then run through audit and
        # verify the canary is gone.
        from core.safety.canaries import (
            CanaryStore, set_active_store_for_test,
            clear_active_store_for_test,
        )

        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        path = Path(f.name)
        try:
            store = CanaryStore(db_path=path)
            set_active_store_for_test(store)
            tok = store.register_canary(context="brief:test")
            from core.safety.audited_output import audit_assistant_text

            reply = (
                f"That's a great question. The relevant evidence is "
                f"ep-1234 | sources: {tok}, core-abc"
            )
            audited = audit_assistant_text(reply, surface="test")
            self.assertNotIn(tok, audited,
                             "canary token must be stripped from "
                             "audited output")
        finally:
            clear_active_store_for_test()
            path.unlink(missing_ok=True)


class TestEndToEndCanaryLifecycle(unittest.TestCase):
    """The full pipeline: register a canary, inject it into a brief
    via the lived_recall composer, simulate a model that paraphrases
    the canary into its reply, run the reply through audit, verify
    the canary was stripped AND the leak was recorded."""

    def test_brief_includes_canary_marker(self):
        """When a brief is built and canary-injection is enabled,
        the rendered brief must contain a registered canary in a
        position the model wouldn't normally fabricate (a fake
        ``sources:`` evidence id)."""
        from core.evolution.wonderings import _tokens  # noqa: F401  - probe import is fine
        from core.memory.episodes import EpisodeStore
        from core.memory.relationship_graph import RelationshipGraph
        from core.memory.lived_recall import build_lived_recall_brief
        from core.safety.canaries import (
            CanaryStore,
            set_active_store_for_test,
            clear_active_store_for_test,
        )

        ep_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        ep_tmp.close()
        gr_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        gr_tmp.close()
        cn_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cn_tmp.close()
        try:
            store = EpisodeStore(ep_tmp.name)
            graph = RelationshipGraph(gr_tmp.name)
            store.add(
                title="Hardware instability noted",
                summary=(
                    "Kernel rebooted. NVIDIA driver implicated. "
                    "Investigation followed."
                ),
                participants=["Maez"],
                source_memory_ids=["raw-1"],
                source_kind="raw_observation",
            )
            canary_store = CanaryStore(db_path=Path(cn_tmp.name))
            set_active_store_for_test(canary_store)
            brief = build_lived_recall_brief(
                "have we had any kernel reboots",
                episode_store=store,
                graph=graph,
            )
            self.assertNotEqual(brief, "")
            # When canary injection is enabled, the brief must
            # contain a canary marker. With the active store set
            # to the test instance, registration happens during
            # brief build and the token is part of the rendered
            # evidence string.
            active_now = canary_store.active_token_set()
            self.assertGreater(
                len(active_now), 0,
                "brief build must register at least one canary "
                "in the active store",
            )
            # At least one registered canary must appear in the
            # actual brief text.
            self.assertTrue(
                any(tok in brief for tok in active_now),
                f"no registered canary appeared in brief: {brief!r}",
            )
        finally:
            clear_active_store_for_test()
            for p in (ep_tmp.name, gr_tmp.name, cn_tmp.name):
                Path(p).unlink(missing_ok=True)

    def test_full_lifecycle_registers_strips_records(self):
        """Register a canary, simulate a leaked reply, audit it,
        verify the leak was recorded in the canary store."""
        from core.safety.canaries import (
            CanaryStore,
            set_active_store_for_test,
            clear_active_store_for_test,
        )
        from core.safety.audited_output import audit_assistant_text

        cn_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cn_tmp.close()
        try:
            canary_store = CanaryStore(db_path=Path(cn_tmp.name))
            set_active_store_for_test(canary_store)
            tok = canary_store.register_canary(context="test:lived_recall")
            reply = (
                f"Yes — see ep:ep-abc | sources: core-1, {tok}. "
                f"That's where the kernel reboot was logged."
            )
            audited = audit_assistant_text(reply, surface="test")
            self.assertNotIn(tok, audited)
            # Leak must have been recorded.
            leaks = canary_store.recent_leaks()
            self.assertEqual(len(leaks), 1)
            self.assertEqual(leaks[0]["token"], tok)
            self.assertEqual(leaks[0]["surface"], "test")
        finally:
            clear_active_store_for_test()
            Path(cn_tmp.name).unlink(missing_ok=True)


class TestRegexFallbackWarns(unittest.TestCase):
    """Audit M1: the regex fallback must NOT silently strip text
    when no active canary store is present. Either fail-closed
    (return text unchanged) or warn-loud — silent stealth-strip
    of any ``MAEZ-CANARY-X`` text is a footgun."""

    def test_no_active_store_fails_closed(self):
        from core.safety.canaries import (
            scrub_canary_leakage,
            clear_active_store_for_test,
        )

        clear_active_store_for_test()
        # Force the fallback path: no module-level store, no
        # canary registry to consult.
        suspicious = "Maez said: MAEZ-CANARY-deadbeef12 in reply"
        result = scrub_canary_leakage(suspicious, surface="test")
        # Fail-closed semantic: no active store → don't mangle text.
        # The token may STILL be detected by the prefix regex if
        # implementation chooses, but if it strips, it must log a
        # warning. Test asserts the safer behaviour: text unchanged
        # when there's no registered canary set to consult against.
        self.assertEqual(result, suspicious)


class TestCleanupRegexPolish(unittest.TestCase):
    """Audit L4: stripping a canary leaves trailing punctuation /
    artefacts. The cleanup pass should produce clean text, not
    ``"sources: core-1, , ep-x"``."""

    def test_strip_leaves_no_double_comma(self):
        from core.safety.canaries import (
            CanaryStore,
            set_active_store_for_test,
            clear_active_store_for_test,
            scrub_canary_leakage,
        )

        cn_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cn_tmp.close()
        try:
            canary_store = CanaryStore(db_path=Path(cn_tmp.name))
            set_active_store_for_test(canary_store)
            tok = canary_store.register_canary(context="test")
            text = f"sources: core-1, {tok}, ep-x"
            out = scrub_canary_leakage(text, surface="test")
            self.assertNotIn(tok, out)
            self.assertNotIn(", ,", out,
                             "double-comma artefact must be cleaned up")
            self.assertNotIn(",,", out)
        finally:
            clear_active_store_for_test()
            Path(cn_tmp.name).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
