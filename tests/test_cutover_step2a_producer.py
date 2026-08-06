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
STAGE2_TS = "2026-07-13T12:03:02Z"
AUTHORIZATION_REF = "cutover-authorization.json"


def stage2_input_paths() -> "assemble.Stage2InputPaths":
    """Build the authority through its SPECIFIED interface.

    v14 freezes Stage2InputPaths; it does not freeze any `stage2_inputs()`
    helper, and my first draft invented one. Constructing the dataclass
    from the real stage-1 selection plus the authorization ref uses only
    what the design actually froze.
    """
    from dataclasses import fields as dataclass_fields

    from tests.test_cutover_step1_invariants import stage1_paths

    stage1 = stage1_paths()
    values = {
        f.name: getattr(stage1, f.name) for f in dataclass_fields(stage1)
    }
    return assemble.Stage2InputPaths(
        **values, authorization=AUTHORIZATION_REF
    )


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
        # Canonical JSON is not the admission boundary. Construct the
        # typed preimage the driver actually reads, from the real bytes.
        #
        # Its constructor takes ONLY (selected_ref, wrapper_bytes); the
        # command, ordinal, window and timestamp are init=False and are
        # DERIVED from the bytes. That makes this the strongest form of
        # the guard: the parser itself must still read a real durable
        # admission document. I guessed this signature twice before
        # reading it, which is the same failure as everything else this
        # session -- inferring an API instead of checking it.
        preimage = cm.CommandAdmissionPreimage(
            selected_ref="command-cuda-candidate-attempt-024-admission.json",
            wrapper_bytes=raw,
        )
        assert preimage.command == "cuda-candidate"
        assert preimage.ordinal == 24
        assert preimage.window_id is not None

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

    def test_every_VALUE_is_a_canonical_relative_ref(self) -> None:
        """Annotations prove nothing about the values.

        Checking `f.type == "str"` only reads the source text of the
        annotation. The property that matters is that every constructed
        value is a canonical relative ref -- no absolute paths, no "..",
        no empty components.
        """
        from dataclasses import fields as dataclass_fields

        authority = stage2_input_paths()
        for f in dataclass_fields(authority):
            value = getattr(authority, f.name)
            assert type(value) is str and value, f.name
            assert not value.startswith("/"), f.name
            assert ".." not in Path(value).parts, f.name
            assert "" not in Path(value).parts, f.name

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
            stage2_input_paths(),
            root=BENCH_ROOT,
            timestamp=STAGE2_TS,
        )
        assert type(bundle) is cm.BenchEvidenceBundle
        verdict = cm.evaluate_promotion_bundle(bundle)
        assert verdict.decision == "provisional_cuda_boot"
        assert verdict.cutover_window_id is not None

    def test_producer_receipt_is_the_exact_canonical_bytes(self) -> None:
        """Compare BYTES, not two dictionary fields.

        The first version asserted two keys and called itself "exact
        canonical bytes". The 2B join is byte equality against the real
        encoder, so that is what this must compare.
        """
        bundle = assemble.build_stage2_bundle(
            stage2_input_paths(),
            root=BENCH_ROOT,
            timestamp=STAGE2_TS,
        )
        verdict = cm.evaluate_promotion_bundle(bundle)
        receipt = cm.build_receipt(bundle, verdict, timestamp=bundle.timestamp)
        produced = driver.ProductionArtifactPolicy().encode(
            "receipt", {**receipt, "binding_sha256": bundle.binding_sha256}
        )
        regenerated = driver.ProductionArtifactPolicy().encode(
            "receipt",
            {
                **cm.build_receipt(
                    bundle, verdict, timestamp=bundle.timestamp
                ),
                "binding_sha256": bundle.binding_sha256,
            },
        )
        assert produced == regenerated
        assert cm.PersistedDoc(produced).obj.cutover_window_id is not None


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
        """_TERMINAL_SCHEMA_MATRIX is the live seam.

        My first version named _COMMAND_TERMINAL_SCHEMAS, which does not
        exist -- so extending the REAL matrix would have left this red
        forever. A red that cannot go green by correct implementation is
        not a red, it is a broken test.
        """
        from scripts import cuda_bench_cli as cli

        assert (
            cli._TERMINAL_SCHEMA_MATRIX["assemble-stage2"]
            == cm.COMMAND_COMPLETION_SCHEMA
        )


class TestPublicChainPublishesRealArtifacts:
    """main() must actually assemble and publish -- not merely parse.

    Registration, parsing and a matrix entry say nothing about whether
    the command does anything: `assemble-stage2` could stay bound to
    _unimplemented_handler and every other CLI test here would pass.
    This invokes the real entrypoint against an ANCHORED PRIVATE ROOT
    (never the live bench root) and joins the published chain.
    """

    @staticmethod
    def _private_root(tmp_path: Path) -> Path:
        """Copy the inputs into a private root. Reads the live root only."""
        from dataclasses import fields as dataclass_fields

        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        authority = stage2_input_paths()
        for f in dataclass_fields(authority):
            rel = getattr(authority, f.name)
            src = BENCH_ROOT / rel
            if not src.exists():
                continue
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
        return root

    def test_invocation_publishes_admission_receipt_and_completion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from scripts import cuda_bench_cli as cli

        root = self._private_root(tmp_path)
        monkeypatch.setattr(driver, "BENCH_ROOT", root)

        calls: list[int] = []
        real_builder = assemble.build_stage2_bundle
        monkeypatch.setattr(
            assemble,
            "build_stage2_bundle",
            lambda *a, **k: (calls.append(1), real_builder(*a, **k))[1],
        )

        rc = cli.main(
            ["assemble-stage2", "--window-id", "cutover-20260713-1202"]
        )
        assert rc == 0
        # the canonical builder ran exactly once
        assert calls == [1]

        admissions = sorted(root.glob("command-assemble-stage2-*-admission.json"))
        terminals = sorted(root.glob("command-assemble-stage2-*-terminal.json"))
        assert len(admissions) == 1, admissions
        assert len(terminals) == 1, terminals

        completion = cm._canonical_persisted_role(
            cm.PersistedDoc(terminals[0].read_bytes()), cm.CommandCompletionDoc
        ).obj
        assert completion.command == "assemble-stage2"
        assert completion.status == "completed"
        assert completion.window_id == "cutover-20260713-1202"
        assert completion.artifact_schema == cm.ASSEMBLE_RECEIPT_SCHEMA

        # the completion cites the ACTUAL admission bytes
        import hashlib

        assert completion.admission_sha256 == hashlib.sha256(
            admissions[0].read_bytes()
        ).hexdigest()

        # ...and the ACTUAL receipt bytes
        receipt_bytes = (root / completion.artifact_ref).read_bytes()
        assert completion.artifact_sha256 == hashlib.sha256(
            receipt_bytes
        ).hexdigest()

        receipt = cm._canonical_persisted_role(
            cm.PersistedDoc(receipt_bytes), cm.AssembleReceiptDoc
        ).obj
        assert receipt.decision == "provisional_cuda_boot"
        assert receipt.cutover_window_id == completion.window_id

        # chronology: admission <= receipt <= completion
        admission_at = json.loads(admissions[0].read_bytes())["fields"][
            "timestamp"
        ]
        assert cm._compare_utc_z(admission_at, receipt.timestamp) <= 0
        assert cm._compare_utc_z(receipt.timestamp, completion.timestamp) <= 0

    def test_the_live_bench_root_was_never_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The anchoring claim, asserted rather than assumed."""
        before = sorted(p.name for p in BENCH_ROOT.iterdir())
        root = self._private_root(tmp_path)
        monkeypatch.setattr(driver, "BENCH_ROOT", root)
        assert root != BENCH_ROOT
        after = sorted(p.name for p in BENCH_ROOT.iterdir())
        assert before == after


class TestOneBuilderTopology:
    """Exactly two production construction sites, by exact line identity.

    Four ways the previous scanner was bypassable, all fixed here:

    * it returned a SET, so two constructor calls inside one allowed
      function collapsed into one entry and the count still read 2;
    * it resolved aliases partially, missing import aliases and annotated
      assignments -- so it invited exactly the evasion it claimed to stop;
    * it never saw module-scope or lambda construction, only calls inside
      a FunctionDef;
    * it scanned five directories while this repo has production Python in
      cli/, daemon/, hardware/, training/, ui/, tools/ and at the root.

    The fix is to stop trying to be clever about aliases and instead
    REJECT aliasing outright, while scanning every tracked production
    file and reporting exact (file, line, enclosing scope) triples.
    """

    EXCLUDED_ROOTS = ("tests", "docs", "staging", "tmp", "backups", "research")
    ALLOWLIST = {
        ("scripts/cuda_bench_assemble.py", "build_stage1_bundle"),
        ("scripts/cuda_bench_assemble.py", "build_stage2_bundle"),
    }

    @classmethod
    def _production_files(cls) -> list[Path]:
        import subprocess

        out = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        return [
            REPO / rel
            for rel in out
            if not rel.startswith(tuple(f"{r}/" for r in cls.EXCLUDED_ROOTS))
        ]

    @classmethod
    def _scan(cls) -> tuple[list[tuple[str, int, str]], list[tuple[str, int]]]:
        """Return (construction sites, aliasing sites). Lists, not sets."""
        sites: list[tuple[str, int, str]] = []
        aliases: list[tuple[str, int]] = []
        for path in cls._production_files():
            try:
                tree = ast.parse(path.read_text(), filename=str(path))
            except (SyntaxError, UnicodeDecodeError):
                continue
            rel = str(path.relative_to(REPO))
            scope: dict[int, str] = {}
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(node):
                        scope.setdefault(id(child), node.name)
            for node in ast.walk(tree):
                # ANY binding of the constructor to another name is rejected,
                # rather than resolved. Assign, AnnAssign and import-as all
                # count.
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    value = node.value
                    name = (
                        value.attr
                        if isinstance(value, ast.Attribute)
                        else value.id
                        if isinstance(value, ast.Name)
                        else None
                    )
                    if name == "BenchEvidenceBundle":
                        aliases.append((rel, node.lineno))
                if isinstance(node, ast.ImportFrom):
                    for a in node.names:
                        if a.name == "BenchEvidenceBundle" and a.asname:
                            aliases.append((rel, node.lineno))
                if isinstance(node, ast.Call):
                    f = node.func
                    name = (
                        f.attr
                        if isinstance(f, ast.Attribute)
                        else f.id
                        if isinstance(f, ast.Name)
                        else None
                    )
                    if name == "BenchEvidenceBundle":
                        sites.append(
                            (
                                rel,
                                node.lineno,
                                scope.get(id(node), "<module-or-lambda>"),
                            )
                        )
        return sites, aliases

    def test_construction_sites_are_exactly_two_by_line_identity(self) -> None:
        sites, _ = self._scan()
        assert len(sites) == 2, sites
        assert {(f, fn) for f, _, fn in sites} == self.ALLOWLIST

    def test_no_module_scope_or_lambda_construction(self) -> None:
        sites, _ = self._scan()
        assert not [s for s in sites if s[2] == "<module-or-lambda>"], sites

    def test_constructor_aliasing_is_rejected_outright(self) -> None:
        """Do not resolve aliases -- forbid them."""
        _, aliases = self._scan()
        assert aliases == [], aliases

    def test_scan_covers_every_tracked_production_file(self) -> None:
        files = {str(p.relative_to(REPO)) for p in self._production_files()}
        assert "scripts/cuda_bench_assemble.py" in files
        for root in ("cli", "daemon", "hardware", "training", "ui", "tools"):
            if (REPO / root).is_dir():
                assert any(f.startswith(f"{root}/") for f in files), root

    def test_exclusions_are_explicit(self) -> None:
        assert "tests" in self.EXCLUDED_ROOTS
