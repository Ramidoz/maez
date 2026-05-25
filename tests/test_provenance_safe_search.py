from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import patch


class ProvenanceSafeSearchTests(unittest.TestCase):
    def test_third_party_refusal_blocks_at_egress_when_construction_bypassed(self):
        from core.egress.fetch_for_curiosity import (
            ProvenancedQuery,
            fetch_for_curiosity,
        )
        from core.policies.exceptions import SubjectBoundaryRefused
        from core.policies.third_party_subject_gate import SubjectKind

        diagnostics: list[dict] = []
        query = ProvenancedQuery(
            bond_id="private_owner",
            query_text="search for a named person from the owner's life",
            subject_kind=SubjectKind.NAMED_THIRD_PARTY,
            subject_ref="person:unconsented",
        )

        with patch("core.egress.external_fetch.fetch_text") as fetch_text:
            with self.assertRaises(SubjectBoundaryRefused):
                fetch_for_curiosity(
                    bond_id="private_owner",
                    query=query,
                    diagnostic_sink=diagnostics.append,
                )

        fetch_text.assert_not_called()
        self.assertEqual(diagnostics[0]["event_type"], "SUBJECT_BOUNDARY_REFUSED")
        self.assertEqual(diagnostics[0]["refusal_kind"], "named_third_party")
        self.assertNotIn("person:unconsented", repr(diagnostics[0]))
        self.assertNotIn("private_owner", repr(diagnostics[0]))

    def test_unknown_subject_kind_defaults_to_refusal(self):
        from core.egress.fetch_for_curiosity import (
            ProvenancedQuery,
            fetch_for_curiosity,
        )
        from core.policies.exceptions import SubjectBoundaryRefused
        from core.policies.third_party_subject_gate import SubjectKind

        diagnostics: list[dict] = []
        query = ProvenancedQuery(
            bond_id="private_owner",
            query_text="ambiguous public-looking query",
            subject_kind=SubjectKind.UNKNOWN,
        )

        with patch("core.egress.external_fetch.fetch_text") as fetch_text:
            with self.assertRaises(SubjectBoundaryRefused):
                fetch_for_curiosity(
                    bond_id="private_owner",
                    query=query,
                    diagnostic_sink=diagnostics.append,
                )

        fetch_text.assert_not_called()
        self.assertEqual(diagnostics[0]["event_type"], "SUBJECT_BOUNDARY_REFUSED")
        self.assertEqual(diagnostics[0]["refusal_kind"], "unknown_subject")

    def test_cross_bond_query_refused_before_fetch(self):
        from core.egress.fetch_for_curiosity import (
            ProvenancedQuery,
            fetch_for_curiosity,
        )
        from core.policies.exceptions import CrossBondAccessError
        from core.policies.third_party_subject_gate import SubjectKind

        diagnostics: list[dict] = []
        query = ProvenancedQuery(
            bond_id="other_bond",
            query_text="weather in chicago",
            subject_kind=SubjectKind.PUBLIC_TOPIC,
        )

        with patch("core.egress.external_fetch.fetch_text") as fetch_text:
            with self.assertRaises(CrossBondAccessError):
                fetch_for_curiosity(
                    bond_id="private_owner",
                    query=query,
                    diagnostic_sink=diagnostics.append,
                )

        fetch_text.assert_not_called()
        self.assertEqual(diagnostics[0]["event_type"], "CROSS_BOND_ACCESS_REFUSED")
        self.assertNotIn("private_owner", repr(diagnostics[0]))
        self.assertNotIn("other_bond", repr(diagnostics[0]))

    def test_public_topic_fetches_through_wrapper(self):
        from core.egress.fetch_for_curiosity import (
            ProvenancedQuery,
            fetch_for_curiosity,
        )
        from core.policies.third_party_subject_gate import SubjectKind

        query = ProvenancedQuery(
            bond_id="private_owner",
            query_text="weather in chicago",
            subject_kind=SubjectKind.PUBLIC_TOPIC,
        )

        with patch("core.egress.external_fetch.fetch_text", return_value="ok") as fetch_text:
            result = fetch_for_curiosity(bond_id="private_owner", query=query)

        self.assertEqual(result, "ok")
        _, kwargs = fetch_text.call_args
        self.assertEqual(kwargs["fetch_type"], "web_search")
        self.assertEqual(kwargs["caller"], "curiosity_probe")
        self.assertIn("weather%20in%20chicago", kwargs["url"])

        from core.egress.external_fetch import build_fetch_registry

        build_fetch_registry().require_fetch_type(kwargs["fetch_type"])

    def test_drive_layer_no_alias_import_of_fetch_text(self):
        roots = [
            Path("core/evolution/drive_driven_curiosity.py"),
            *Path("core/policies").glob("*.py"),
        ]
        violations: list[str] = []
        for root in roots:
            tree = ast.parse(root.read_text(encoding="utf-8"))
            aliases: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module == "core.egress.external_fetch":
                        for alias in node.names:
                            if alias.name == "fetch_text":
                                violations.append(f"{root}: direct fetch_text import")
                    if node.module == "core.egress":
                        for alias in node.names:
                            if alias.name == "external_fetch":
                                aliases.add(alias.asname or alias.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "core.egress.external_fetch":
                            aliases.add(alias.asname or alias.name.split(".")[-1])
                elif isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "fetch_text":
                        violations.append(f"{root}: fetch_text call")
                    if (
                        isinstance(func, ast.Attribute)
                        and func.attr == "fetch_text"
                        and isinstance(func.value, ast.Name)
                        and func.value.id in aliases
                    ):
                        violations.append(f"{root}: aliased fetch_text call")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
