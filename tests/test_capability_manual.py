# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability manual loader + validator tests (Step 1 of the
Decision-19/20 capability-acquisition pipeline arc).

Two test surfaces:

- Synthetic temp manuals exercising every validation rule in
  isolation. Hermetic — no dependence on the real manual content.
- The real manual at ``docs/maez_manual/`` — must load with zero
  errors so future contributors can't silently break the substrate.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── helpers ────────────────────────────────────────────────────────


def _entry_text(
    *,
    capability_id: str = "test-capability",
    title: str = "Test capability",
    status: str = "stable",
    gap_signals: list[str] | None = None,
    prerequisites: list[str] | None = None,
    external_prerequisites: list[str] | None = None,
    acquisition: str = "self-dev",
    covenant: dict | None = None,
    conflicts_with: list[str] | None = None,
    reference_papers: list[str] | None = None,
    implementation_files: list[str] | None = None,
    superseded_by: str | None = None,
    body: str = "# Test\n\nBody text.\n",
    extra: str = "",
) -> str:
    """Compose a valid front-matter + body string. Each kwarg
    overrides one part; the defaults are valid and the helper is
    used to build minimally-invalid variants by passing one bad
    field at a time."""
    if gap_signals is None:
        gap_signals = ["the user feels stuck on something"]
    if prerequisites is None:
        prerequisites = []
    if external_prerequisites is None:
        external_prerequisites = []
    if conflicts_with is None:
        conflicts_with = []
    if reference_papers is None:
        reference_papers = []
    if implementation_files is None:
        implementation_files = []
    if covenant is None:
        covenant = {
            "consent-card-required": True,
            "exact-phrase-ratification": False,
            "covenant-touch": "low",
        }

    lines = [
        "---",
        f"capability_id: {capability_id}",
        f"title: {title}",
        f"status: {status}",
        "gap_signals:",
    ]
    for g in gap_signals:
        lines.append(f"  - {json.dumps(g)}")
    lines.append("prerequisites:")
    for p in prerequisites:
        lines.append(f"  - {p}")
    lines.append("external_prerequisites:")
    for p in external_prerequisites:
        lines.append(f"  - {p}")
    lines.append(f"acquisition: {acquisition}")
    lines.append("covenant:")
    for k, v in covenant.items():
        # Quote strings so YAML 1.1's truthy values (yes/no/on/off)
        # don't silently convert when a test wants a literal string.
        if isinstance(v, bool):
            rendered = "true" if v else "false"
        elif isinstance(v, str):
            rendered = json.dumps(v)
        else:
            rendered = str(v)
        lines.append(f"  {k}: {rendered}")
    lines.append("conflicts_with:")
    for c in conflicts_with:
        lines.append(f"  - {c}")
    lines.append("reference_papers:")
    for r in reference_papers:
        lines.append(f"  - {json.dumps(r)}")
    lines.append("implementation_files:")
    for f in implementation_files:
        lines.append(f"  - {f}")
    if superseded_by is not None:
        lines.append(f"superseded_by: {superseded_by}")
    if extra:
        lines.append(extra)
    lines.append("---")
    lines.append(body)
    return "\n".join(lines) + "\n"


def _write_entry(root: Path, capability_id: str, **kwargs) -> Path:
    """Write an entry file under ``root/<capability_id>.md`` with
    the given overrides. Returns the path."""
    p = root / f"{capability_id}.md"
    p.write_text(
        _entry_text(capability_id=capability_id, **kwargs),
        encoding="utf-8",
    )
    return p


# ── load_capability (single file) ──────────────────────────────────


class TestLoadCapability(unittest.TestCase):
    def test_loads_valid_entry(self):
        from core.capability_manual import load_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = _write_entry(root, "alpha")
            entry = load_capability(p)
        self.assertEqual(entry.capability_id, "alpha")
        self.assertEqual(entry.title, "Test capability")
        self.assertEqual(entry.status, "stable")
        self.assertEqual(entry.acquisition, "self-dev")

    def test_preserves_body_markdown(self):
        from core.capability_manual import load_capability

        body = "# Heading\n\nFirst paragraph.\n\n## Subhead\n\nSecond.\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = _write_entry(root, "alpha", body=body)
            entry = load_capability(p)
        self.assertIn("# Heading", entry.body)
        self.assertIn("Second.", entry.body)

    def test_covenant_is_flat_dataclass(self):
        from core.capability_manual import load_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = _write_entry(root, "alpha")
            entry = load_capability(p)
        self.assertTrue(entry.covenant.consent_card_required)
        self.assertFalse(entry.covenant.exact_phrase_ratification)
        self.assertEqual(entry.covenant.covenant_touch, "low")


# ── filename / capability_id alignment ─────────────────────────────


class TestFilenameAlignment(unittest.TestCase):
    def test_filename_must_match_capability_id(self):
        from core.capability_manual import load_capability, validate_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Write file at <root>/wrong-name.md but front matter says alpha.
            p = root / "wrong-name.md"
            p.write_text(_entry_text(capability_id="alpha"))
            entry = load_capability(p)
            issues = validate_capability(entry)
        codes = [i.code for i in issues]
        self.assertIn("filename_mismatch", codes)
        # And it's an error, not a warning.
        for i in issues:
            if i.code == "filename_mismatch":
                self.assertEqual(i.severity, "error")


# ── required-field validation ─────────────────────────────────────


class TestRequiredFields(unittest.TestCase):
    def test_missing_capability_id_is_error(self):
        from core.capability_manual import (
            CapabilityManualError,
            load_capability,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "no-id.md"
            # Hand-craft front matter with missing capability_id.
            p.write_text(
                "---\n"
                "title: x\nstatus: stable\n"
                "gap_signals:\n  - 'x'\n"
                "prerequisites: []\nexternal_prerequisites: []\n"
                "acquisition: self-dev\n"
                "covenant:\n  consent-card-required: true\n"
                "  exact-phrase-ratification: false\n"
                "  covenant-touch: low\n"
                "conflicts_with: []\nreference_papers: []\n"
                "implementation_files: []\n"
                "---\nBody\n"
            )
            with self.assertRaises(CapabilityManualError):
                load_capability(p)

    def test_status_must_be_in_enum(self):
        from core.capability_manual import load_capability, validate_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = _write_entry(root, "alpha", status="invented-status")
            entry = load_capability(p)
            issues = validate_capability(entry)
        codes = [i.code for i in issues]
        self.assertIn("status_invalid", codes)

    def test_acquisition_must_be_in_enum(self):
        from core.capability_manual import load_capability, validate_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = _write_entry(root, "alpha", acquisition="invented")
            entry = load_capability(p)
            issues = validate_capability(entry)
        codes = [i.code for i in issues]
        self.assertIn("acquisition_invalid", codes)

    def test_gap_signals_cannot_be_empty(self):
        from core.capability_manual import load_capability, validate_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = _write_entry(root, "alpha", gap_signals=[])
            entry = load_capability(p)
            issues = validate_capability(entry)
        codes = [i.code for i in issues]
        self.assertIn("gap_signals_empty", codes)

    def test_gap_signals_strings_cannot_be_empty(self):
        from core.capability_manual import load_capability, validate_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = _write_entry(root, "alpha", gap_signals=["", "real one"])
            entry = load_capability(p)
            issues = validate_capability(entry)
        codes = [i.code for i in issues]
        self.assertIn("gap_signal_empty_string", codes)

    def test_covenant_touch_must_be_in_enum(self):
        from core.capability_manual import load_capability, validate_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = _write_entry(root, "alpha", covenant={
                "consent-card-required": True,
                "exact-phrase-ratification": False,
                "covenant-touch": "extreme",  # invalid
            })
            entry = load_capability(p)
            issues = validate_capability(entry)
        codes = [i.code for i in issues]
        self.assertIn("covenant_touch_invalid", codes)

    def test_consent_required_must_be_bool(self):
        from core.capability_manual import load_capability, validate_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = _write_entry(root, "alpha", covenant={
                "consent-card-required": "yes",  # not a bool
                "exact-phrase-ratification": False,
                "covenant-touch": "low",
            })
            entry = load_capability(p)
            issues = validate_capability(entry)
        codes = [i.code for i in issues]
        self.assertIn("consent_card_required_not_bool", codes)


# ── implementation_files ──────────────────────────────────────────


class TestImplementationFiles(unittest.TestCase):
    def test_existing_files_pass(self):
        from core.capability_manual import load_capability, validate_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "real_code.py").write_text("# stub\n")
            p = _write_entry(
                root, "alpha", status="stable",
                implementation_files=["real_code.py"],
            )
            entry = load_capability(p)
            # validator needs to know what root the paths are relative to
            issues = validate_capability(entry, repo_root=root)
        codes = [i.code for i in issues]
        self.assertNotIn("implementation_file_missing", codes)

    def test_missing_file_when_not_aspirational_is_error(self):
        from core.capability_manual import load_capability, validate_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = _write_entry(
                root, "alpha", status="stable",
                implementation_files=["nonexistent.py"],
            )
            entry = load_capability(p)
            issues = validate_capability(entry, repo_root=root)
        codes = [i.code for i in issues]
        self.assertIn("implementation_file_missing", codes)
        for i in issues:
            if i.code == "implementation_file_missing":
                self.assertEqual(i.severity, "error")

    def test_missing_file_when_aspirational_is_ignored(self):
        from core.capability_manual import load_capability, validate_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = _write_entry(
                root, "alpha", status="aspirational",
                implementation_files=["nonexistent.py"],
            )
            entry = load_capability(p)
            issues = validate_capability(entry, repo_root=root)
        codes = [i.code for i in issues]
        # Aspirational entries can list files that don't exist yet —
        # that's the whole point of the status.
        self.assertNotIn("implementation_file_missing", codes)


# ── manual-level checks (cross-entry) ─────────────────────────────


class TestManualCrossEntry(unittest.TestCase):
    def test_loads_full_manual(self):
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            _write_entry(root, "beta")
            result = load_manual(root)
        ids = sorted(e.capability_id for e in result.entries)
        self.assertEqual(ids, ["alpha", "beta"])
        self.assertEqual(result.errors, [])

    def test_duplicate_ids_are_errors(self):
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            # Write a second file with the SAME capability_id but
            # different filename. Filename-mismatch is one issue;
            # duplicate-id is the other.
            (root / "alpha-clone.md").write_text(
                _entry_text(capability_id="alpha", title="dupe"),
            )
            result = load_manual(root)
        codes = [i.code for i in result.errors]
        self.assertIn("duplicate_capability_id", codes)

    def test_internal_prereq_missing_is_warning(self):
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                prerequisites=["nonexistent-internal"],
            )
            result = load_manual(root)
        codes_w = [i.code for i in result.warnings]
        codes_e = [i.code for i in result.errors]
        self.assertIn("missing_internal_prerequisite", codes_w)
        self.assertNotIn("missing_internal_prerequisite", codes_e)

    def test_internal_prereq_present_is_silent(self):
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha", prerequisites=["beta"])
            _write_entry(root, "beta")
            result = load_manual(root)
        codes = [i.code for i in result.warnings + result.errors]
        self.assertNotIn("missing_internal_prerequisite", codes)

    def test_external_prereq_does_not_warn(self):
        """External prerequisites are shipped-in-code capabilities;
        the validator never expects them in the manual."""
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                external_prerequisites=["working-self"],
            )
            result = load_manual(root)
        codes = [i.code for i in result.warnings + result.errors]
        self.assertNotIn("missing_external_prerequisite", codes)
        self.assertNotIn("missing_internal_prerequisite", codes)

    def test_superseded_by_must_resolve(self):
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # An entry claiming to be superseded by something that
            # doesn't exist in the manual.
            _write_entry(
                root, "alpha", status="deprecated",
                superseded_by="ghost-id",
            )
            result = load_manual(root)
        codes = [i.code for i in result.errors]
        self.assertIn("superseded_by_unresolved", codes)

    def test_superseded_by_resolves_silently(self):
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha", status="deprecated",
                         superseded_by="beta")
            _write_entry(root, "beta")
            result = load_manual(root)
        codes = [i.code for i in result.errors]
        self.assertNotIn("superseded_by_unresolved", codes)


# ── find_by_id ─────────────────────────────────────────────────────


class TestFindById(unittest.TestCase):
    def test_returns_entry_when_present(self):
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            result = load_manual(root)
        entry = result.find_by_id("alpha")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.capability_id, "alpha")

    def test_returns_none_when_absent(self):
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            result = load_manual(root)
        self.assertIsNone(result.find_by_id("ghost"))


# ── real manual smoke ─────────────────────────────────────────────


class TestRealManualLoadsCleanly(unittest.TestCase):
    """Exit criterion: real manual loads with zero errors. Warnings
    are allowed but should be meaningful, not noise."""

    def test_real_manual_zero_errors(self):
        from core.capability_manual import load_manual

        result = load_manual(_REPO / "docs" / "maez_manual")
        msg_lines = [
            f"  {i.severity}: {i.code}: {i.message}"
            for i in result.errors + result.warnings
        ]
        self.assertEqual(
            result.errors, [],
            "real manual must load with zero errors. issues:\n"
            + "\n".join(msg_lines),
        )

    def test_real_manual_loads_three_seed_entries(self):
        from core.capability_manual import load_manual

        result = load_manual(_REPO / "docs" / "maez_manual")
        ids = {e.capability_id for e in result.entries}
        # Per docs/maez_manual/README.md, the three seed entries.
        for expected in (
            "recursive-context-engine",
            "multi-session-entity-linking",
            "temporal-arithmetic-at-recall",
        ):
            self.assertIn(expected, ids)


class TestAuditFixPins(unittest.TestCase):
    """Pins for the inline audit fixes so they can't silently
    revert: BOM tolerance, no-trailing-newline tolerance, malformed
    YAML, CLI exit codes, module-level find_by_id."""

    def test_loads_file_with_utf8_bom(self):
        from core.capability_manual import load_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "alpha.md"
            content = "﻿" + _entry_text(capability_id="alpha")
            p.write_text(content, encoding="utf-8")
            entry = load_capability(p)
        self.assertEqual(entry.capability_id, "alpha")

    def test_loads_file_without_trailing_newline(self):
        from core.capability_manual import load_capability

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "alpha.md"
            # Write with NO final newline.
            content = _entry_text(capability_id="alpha").rstrip("\n")
            p.write_text(content, encoding="utf-8")
            entry = load_capability(p)
        self.assertEqual(entry.capability_id, "alpha")

    def test_malformed_yaml_raises_capability_manual_error(self):
        from core.capability_manual import (
            CapabilityManualError, load_capability,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "broken.md"
            p.write_text(
                "---\n"
                "capability_id: x\n"
                "title: : :   ::\n"  # bogus YAML
                "---\nbody\n",
            )
            with self.assertRaises(CapabilityManualError):
                load_capability(p)

    def test_module_level_find_by_id(self):
        from core.capability_manual import find_by_id

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            entry = find_by_id("alpha", root=root)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.capability_id, "alpha")
            self.assertIsNone(find_by_id("ghost", root=root))


class TestCliExitCodes(unittest.TestCase):
    """Audit gap: CLI exit semantics weren't tested. Pin both
    paths so a future refactor can't break the contract."""

    def test_clean_manual_exits_zero(self):
        from core.infra.capability_manual_cli import main

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            rc = main(["validate", "--root", str(root), "--json"])
        self.assertEqual(rc, 0)

    def test_dirty_manual_exits_one(self):
        from core.infra.capability_manual_cli import main

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Filename / capability_id mismatch → error.
            (root / "wrong-name.md").write_text(
                _entry_text(capability_id="alpha"),
            )
            rc = main(["validate", "--root", str(root), "--json"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
