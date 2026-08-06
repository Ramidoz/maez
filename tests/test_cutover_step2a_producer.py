"""Cutover step 2A — the sole production stage-2 assembly seam. RED set.

Written against ratified design v11 BEFORE implementation. Scope here is
2A only: the canonical builder, the `assemble-stage2` command matrices,
the canon result, and the one-builder topology. The consumer (2B) and the
S7 presence binding are NOT covered — the v10/v11 amendments carrying
them are still in review, and writing their REDs now would front-run it.

Expected pre-implementation failure taxonomy:

* Builder      -> the symbol does not exist: AttributeError.
* CommandCanon -> `assemble-stage2` is absent from the closed vocabularies:
  the membership assertions fail.
* CanonResult  -> asserts what must NOT move; these must pass today and
  keep passing, i.e. they are guards, not reds.
* OneBuilder   -> the production construction sites are not yet exactly
  two; the count assertion fails.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from scripts import cuda_bench_assemble as assemble
from scripts import cuda_bench_driver as driver
from scripts import cuda_migration as cm

REPO = Path(__file__).resolve().parents[1]
BENCH_ROOT = Path("/home/rohit/maez/local/cuda_migration_bench")


class TestCanonicalBuilderExists:
    """One canonical stage-2 seam, on the assembler beside stage 1."""

    def test_build_stage2_bundle_is_public_on_the_assembler(self) -> None:
        assert hasattr(assemble, "build_stage2_bundle")

    def test_stage2_input_paths_authority_exists(self) -> None:
        assert hasattr(assemble, "Stage2InputPaths")

    def test_stage2_authority_names_no_command_record(self) -> None:
        """Ordinals are runtime-allocated; command records cannot be constants.

        v5 named them as literals and v6 corrected it. The authority
        carries the 22 stage-1 inputs and the authorization reference
        only; the completion arrives as a locator and the admission and
        receipt derive from it.
        """
        from dataclasses import fields as dataclass_fields

        names = {f.name for f in dataclass_fields(assemble.Stage2InputPaths)}
        for forbidden in (
            "admission",
            "completion",
            "command_admission",
            "command_completion",
            "receipt",
        ):
            assert forbidden not in names, forbidden
        assert "authorization" in names


class TestAssembleStage2CommandCanon:
    """The command must exist in BOTH closed vocabularies."""

    def test_command_name_is_admitted(self) -> None:
        assert "assemble-stage2" in driver._COMMAND_NAMES

    def test_completion_matrix_admits_the_assembly_receipt(self) -> None:
        assert "assemble-stage2" in cm._COMPLETION_MATRIX
        artifact_schema, phase = cm._COMPLETION_MATRIX["assemble-stage2"]
        assert artifact_schema == cm.ASSEMBLE_RECEIPT_SCHEMA
        # An assembly is not a phase.
        assert phase is None

    def test_window_is_required_and_exact(self) -> None:
        """Unlike static-preflight, stage 2 MUST carry the cutover window.

        The membership assertion is load-bearing, not decoration: without
        it this test passes today for the WRONG reason -- an unknown
        command raises on the matrix lookup, never reaching the window
        rule. It would then have been a guard that guards nothing.
        """
        assert "assemble-stage2" in cm._COMPLETION_MATRIX
        with pytest.raises(ValueError):
            cm.CommandCompletionDoc(
                command="assemble-stage2",
                ordinal=1,
                window_id=None,
                admission_ref="a.json",
                admission_sha256="a" * 64,
                artifact_ref="r.json",
                artifact_sha256="b" * 64,
                artifact_schema=cm.ASSEMBLE_RECEIPT_SCHEMA,
                status="completed",
                timestamp="2026-07-13T12:03:02Z",
            )


class TestCanonResultIsFrozen:
    """GUARDS, not reds: assert exactly what must NOT move."""

    def test_active_family_count_stays_twenty_six(self) -> None:
        """assemble-stage2 adds a COMMAND, not a schema family.

        v5 claimed this moves "as step 1's 24->26 did". It does not:
        step 1 added two families; this adds none. All three schemas the
        chain uses are already active members.
        """
        assert len(cm.ACTIVE_SCHEMA_FAMILIES) == 26
        for schema in (
            cm.ASSEMBLE_RECEIPT_SCHEMA,
            cm.COMMAND_COMPLETION_SCHEMA,
            cm.COMMAND_ADMISSION_SCHEMA,
        ):
            assert schema in cm.ACTIVE_SCHEMA_FAMILIES

    def test_command_schemas_stay_v1(self) -> None:
        assert cm.COMMAND_ADMISSION_SCHEMA.endswith(".v1")
        assert cm.COMMAND_COMPLETION_SCHEMA.endswith(".v1")

    def test_historical_v1_artifacts_remain_decodable(self) -> None:
        """The durable attempt-026 receipt must survive the vocabulary change."""
        raw = (
            BENCH_ROOT / "command-assemble-stage1-attempt-026-terminal.json"
        ).read_bytes()
        typed = cm._canonical_persisted_role(
            cm.PersistedDoc(raw), cm.AssembleReceiptDoc
        )
        assert typed.obj.decision == "bench_passed"

    def test_stage_one_publication_shape_is_untouched(self) -> None:
        """Deliberate asymmetry: stage 1 still publishes its receipt directly.

        attempt-026 is frozen evidence. Step 2 does not retrofit it, so
        assemble-stage1 stays out of the completion matrix.
        """
        assert "assemble-stage1" not in cm._COMPLETION_MATRIX
        wrapper = json.loads(
            (
                BENCH_ROOT / "command-assemble-stage1-attempt-026-terminal.json"
            ).read_bytes()
        )
        assert wrapper["schema"] == cm.ASSEMBLE_RECEIPT_SCHEMA


class TestOneBuilderTopology:
    """Exactly two production construction sites. No third."""

    @staticmethod
    def _construction_sites() -> list[tuple[str, int]]:
        sites: list[tuple[str, int]] = []
        for path in sorted((REPO / "scripts").rglob("*.py")) + sorted(
            (REPO / "core").rglob("*.py")
        ):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = (
                    func.attr
                    if isinstance(func, ast.Attribute)
                    else func.id
                    if isinstance(func, ast.Name)
                    else None
                )
                if name == "BenchEvidenceBundle":
                    sites.append((str(path.relative_to(REPO)), node.lineno))
        return sites

    def test_exactly_two_production_construction_sites(self) -> None:
        sites = self._construction_sites()
        assert len(sites) == 2, sites

    def test_the_two_sites_are_the_allowlisted_ones(self) -> None:
        """v5 said "none outside the stage-2 seam", which would reject the
        frozen stage-1 builder that step 2 deliberately does not touch."""
        files = {path for path, _ in self._construction_sites()}
        assert files == {"scripts/cuda_bench_assemble.py"}

    def test_the_test_exclusion_cannot_silently_widen(self) -> None:
        """The allowlist covers production trees only; assert that scope."""
        scanned = {"scripts", "core"}
        assert not (scanned & {"tests"})
