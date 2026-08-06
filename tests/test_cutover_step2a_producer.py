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

    def test_historical_assembly_receipt_remains_decodable(self) -> None:
        """Named for what it reads: attempt-026's ASSEMBLY RECEIPT.

        The previous name claimed "historical v1 artifacts" generally
        while reading exactly one document kind. Admission and completion
        compatibility are proven separately below -- an overclaiming test
        name is a defect even when the assertion is sound.
        """
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


class TestHistoricalCommandDocsRemainDecodable:
    """The command-vocabulary change must not orphan real command records.

    Separate from the assembly-receipt guard: these are different schemas
    written by a different path, and only real bytes off disk prove it.
    """

    def test_real_admission_document_stays_canonical(self) -> None:
        """Admission is NOT a PersistedDoc role -- assert what is true.

        My first version called PersistedDoc on it and failed with
        persisted_schema_unknown. That was the test being wrong about the
        system, not a finding: admission documents are canonical wrappers
        the driver reads directly, not typed persisted roles. The real
        compatibility property is that their canonical encoding is stable.
        """
        raw = (
            BENCH_ROOT / "command-cuda-candidate-attempt-024-admission.json"
        ).read_bytes()
        wrapper = json.loads(raw)
        assert wrapper["schema"] == cm.COMMAND_ADMISSION_SCHEMA
        assert cm._canonical_wrapper_bytes(wrapper) == raw

    def test_real_completion_document_decodes(self) -> None:
        raw = (
            BENCH_ROOT / "command-cuda-candidate-attempt-024-terminal.json"
        ).read_bytes()
        wrapper = json.loads(raw)
        assert wrapper["schema"] == cm.COMMAND_COMPLETION_SCHEMA
        typed = cm._canonical_persisted_role(
            cm.PersistedDoc(raw), cm.CommandCompletionDoc
        )
        assert typed.obj.command == "cuda-candidate"
        assert typed.obj.status == "completed"


class TestStage2InputPathsIsExact:
    """The authority is an exact field set, not merely missing bad names."""

    EXPECTED = (
        # the 22 stage-1 inputs, verbatim from Stage1ArtifactPaths
        "control_packet",
        "candidate_packet",
        "static_admission",
        "static_completion",
        "control_admission",
        "control_completion",
        "candidate_admission",
        "candidate_completion",
        "window_authorization",
        "continuation",
        "window_consumption",
        "continuation_consumption",
        "control_containment_before",
        "control_containment_after",
        "candidate_containment_before",
        "candidate_containment_after",
        "bench_identity",
        "runtime_identity",
        "static_preflight",
        "quality",
        "owner_voice",
        "rollback",
        # plus exactly one more
        "authorization",
    )

    def test_field_set_is_exactly_twenty_three(self) -> None:
        """The negative-name test could pass with required fields ABSENT."""
        from dataclasses import fields as dataclass_fields

        names = tuple(
            f.name for f in dataclass_fields(assemble.Stage2InputPaths)
        )
        assert names == self.EXPECTED

    def test_every_field_is_a_relative_str(self) -> None:
        from dataclasses import fields as dataclass_fields

        for f in dataclass_fields(assemble.Stage2InputPaths):
            assert f.type in ("str", str), (f.name, f.type)

    def test_stage_one_inputs_match_stage_one_authority_verbatim(self) -> None:
        """Drift between the two authorities is silent corruption."""
        from dataclasses import fields as dataclass_fields

        stage1 = tuple(
            f.name for f in dataclass_fields(assemble.Stage1ArtifactPaths)
        )
        stage2 = tuple(
            f.name for f in dataclass_fields(assemble.Stage2InputPaths)
        )
        assert stage2[: len(stage1)] == stage1


class TestProducerBehaviour:
    """Names and matrices prove nothing. The producer must MINT a permit."""

    def test_build_stage2_bundle_yields_provisional_cuda_boot(self) -> None:
        """The whole point of 2A: a real stage-2 permit from real inputs.

        Symbol-existence REDs pass the moment a stub is written. This one
        only passes when the producer genuinely assembles a stage-2 bundle
        that the PUBLIC evaluator scores as provisional_cuda_boot.
        """
        bundle = assemble.build_stage2_bundle(
            assemble.stage2_inputs(),
            root=BENCH_ROOT,
            timestamp="2026-07-13T12:03:02Z",
        )
        assert type(bundle) is cm.BenchEvidenceBundle
        verdict = cm.evaluate_promotion_bundle(bundle)
        assert verdict.decision == "provisional_cuda_boot"
        assert verdict.cutover_window_id is not None

    def test_producer_receipt_is_the_exact_canonical_bytes(self) -> None:
        """One timestamp, one receipt, byte-exact -- the 2B join depends on it."""
        bundle = assemble.build_stage2_bundle(
            assemble.stage2_inputs(),
            root=BENCH_ROOT,
            timestamp="2026-07-13T12:03:02Z",
        )
        verdict = cm.evaluate_promotion_bundle(bundle)
        receipt = cm.build_receipt(bundle, verdict, timestamp=bundle.timestamp)
        assert receipt["cutover_window_id"] == verdict.cutover_window_id
        assert receipt["bundle_binding_sha256"] == bundle.binding_sha256


class TestPublicCommandChain:
    """The command must be reachable and publish a real chain."""

    def test_command_is_publicly_dispatchable(self) -> None:
        from scripts import cuda_bench_cli as cli

        assert "assemble-stage2" in cli.PUBLIC_COMMANDS

    def test_parser_accepts_the_command_and_its_arguments(self) -> None:
        from scripts import cuda_bench_cli as cli

        parser = cli.build_parser()
        args = parser.parse_args(
            ["assemble-stage2", "--window-id", "cutover-20260713-1202"]
        )
        assert args.command == "assemble-stage2"

    def test_terminal_schema_is_the_completion_document(self) -> None:
        from scripts import cuda_bench_cli as cli

        assert (
            cli._COMMAND_TERMINAL_SCHEMAS["assemble-stage2"]
            == cm.COMMAND_COMPLETION_SCHEMA
        )


class TestOneBuilderTopology:
    """Exactly two production construction sites, named by function.

    Counting literal `BenchEvidenceBundle(...)` calls under two
    directories is too weak: it misses an alias (`B = cm.BenchEvidenceBundle`
    then `B(...)`) and it misses any production root outside those two
    directories. This walks every production tree and reports the
    ENCLOSING FUNCTION of each site, so the allowlist names what is
    allowed rather than merely counting.
    """

    PRODUCTION_ROOTS = ("scripts", "core", "api", "memory", "tools")
    ALLOWLIST = {
        ("scripts/cuda_bench_assemble.py", "build_stage1_bundle"),
        ("scripts/cuda_bench_assemble.py", "build_stage2_bundle"),
    }

    @classmethod
    def _sites(cls) -> set[tuple[str, str]]:
        found: set[tuple[str, str]] = set()
        for root in cls.PRODUCTION_ROOTS:
            base = REPO / root
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.py")):
                tree = ast.parse(path.read_text(), filename=str(path))
                # every name bound to the constructor, including aliases
                aliases = {"BenchEvidenceBundle"}
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign) and isinstance(
                        node.value, (ast.Attribute, ast.Name)
                    ):
                        target = (
                            node.value.attr
                            if isinstance(node.value, ast.Attribute)
                            else node.value.id
                        )
                        if target in aliases:
                            for t in node.targets:
                                if isinstance(t, ast.Name):
                                    aliases.add(t.id)
                for fn in ast.walk(tree):
                    if not isinstance(
                        fn, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
                        continue
                    for node in ast.walk(fn):
                        if not isinstance(node, ast.Call):
                            continue
                        f = node.func
                        name = (
                            f.attr
                            if isinstance(f, ast.Attribute)
                            else f.id
                            if isinstance(f, ast.Name)
                            else None
                        )
                        if name in aliases:
                            found.add(
                                (str(path.relative_to(REPO)), fn.name)
                            )
        return found

    def test_construction_sites_are_exactly_the_allowlist(self) -> None:
        assert self._sites() == self.ALLOWLIST

    def test_no_third_production_site_exists(self) -> None:
        extra = self._sites() - self.ALLOWLIST
        assert not extra, extra

    def test_the_allowlist_names_both_canonical_builders(self) -> None:
        """v5 forbade every site outside the stage-2 seam, which would have
        rejected the frozen stage-1 builder step 2 must not touch."""
        functions = {fn for _, fn in self.ALLOWLIST}
        assert functions == {"build_stage1_bundle", "build_stage2_bundle"}

    def test_production_scan_excludes_tests_deliberately(self) -> None:
        assert "tests" not in self.PRODUCTION_ROOTS
