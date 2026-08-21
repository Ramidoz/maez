import unittest
from unittest import mock
from pathlib import Path

from core.routing.cancellable_brain_call import BrainPreempted


class PreemptPropagationTest(unittest.TestCase):
    def test_audit_summarizer_does_not_swallow_brain_preempted(self):
        from core.cognition import audit

        with mock.patch.object(audit.llm_client, "chat", side_effect=BrainPreempted):
            with self.assertRaises(BrainPreempted):
                audit._summarize("payload", "nonce")

    def test_audit_judge_does_not_swallow_brain_preempted(self):
        from core.cognition import audit

        with mock.patch.object(audit.llm_client, "chat", side_effect=BrainPreempted):
            with self.assertRaises(BrainPreempted):
                audit._judge("summary", "payload", "nonce")

    def test_grounding_judge_does_not_convert_preempt_to_unavailable(self):
        from core.cognition import grounding_judge

        with (
            mock.patch.object(grounding_judge, "_JUDGE_BASE_URL", ""),
            mock.patch.object(grounding_judge._llm_client, "chat", side_effect=BrainPreempted),
        ):
            with self.assertRaises(BrainPreempted):
                grounding_judge.judge(
                    text="answer",
                    signals_present=[],
                    signals_absent=[],
                    few_shots=[],
                )

    def test_wondering_cycle_does_not_turn_preempt_into_empty_string(self):
        from daemon import wondering_cycle

        with mock.patch.object(wondering_cycle._llm_client, "chat", side_effect=BrainPreempted):
            with self.assertRaises(BrainPreempted):
                wondering_cycle._call_llm("system", "user", 8, "m")

    def test_daemon_reasoning_model_preempt_yields_cycle_without_optional_brain_work(self):
        """The reasoning call must yield the cycle on preempt.

        Anchored on the AST `try` that wraps ``self._reason(...)``, not
        on a text slice between two stage markers. The previous form
        sliced from the ``reasoning_model`` marker to the
        ``threshold_alerts`` marker, but those markers appear in the
        OPPOSITE order in the file, so the slice was always empty and
        every assertion below ran against ``""``. The guard it is
        supposed to protect was therefore unguarded (found 2026-08-21
        during the pre-restart baseline audit; inversion predates
        bf8621f).
        """
        import ast

        src = (
            Path(__file__).resolve().parents[1] / "daemon" / "maez_daemon.py"
        ).read_text()
        tree = ast.parse(src)

        def _wraps_reason(node: "ast.Try") -> bool:
            return any(
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "_reason"
                for stmt in node.body
                for sub in ast.walk(stmt)
            )

        guards = [
            n for n in ast.walk(tree) if isinstance(n, ast.Try) and _wraps_reason(n)
        ]
        self.assertEqual(
            len(guards), 1, "expected exactly one try wrapping self._reason(...)"
        )
        guard = guards[0]

        handlers = [
            h.type.id
            for h in guard.handlers
            if isinstance(h.type, ast.Name)
        ]
        self.assertIn(
            "BrainPreempted", handlers, "preempt must be caught at the reasoning call"
        )
        if "Exception" in handlers:
            self.assertLess(
                handlers.index("BrainPreempted"),
                handlers.index("Exception"),
                "a generic handler must not shadow BrainPreempted",
            )

        preempt_body = "\n".join(
            ast.get_source_segment(src, stmt) or ""
            for h in guard.handlers
            if isinstance(h.type, ast.Name) and h.type.id == "BrainPreempted"
            for stmt in h.body
        )
        self.assertIn("cycle_preempted = True", preempt_body)

        # And the flag must actually gate optional brain work downstream.
        loop = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and guard.lineno >= n.lineno
            and guard.end_lineno <= (n.end_lineno or 0)
            and n.name == "_loop"
        )
        loop_src = ast.get_source_segment(src, loop) or ""
        self.assertIn("if not cycle_preempted", loop_src)


if __name__ == "__main__":
    unittest.main()
