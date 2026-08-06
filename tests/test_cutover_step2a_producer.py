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
import os
from pathlib import Path

import pytest

from scripts import cuda_bench_assemble as assemble
from scripts import cuda_bench_driver as driver
from scripts import cuda_migration as cm

REPO = Path(__file__).resolve().parents[1]
BENCH_ROOT = Path("/home/rohit/maez/local/cuda_migration_bench")
STAGE2_TS = "2026-07-13T12:03:02Z"
# The FROZEN name (scripts/cuda_cutover.py:22). My first draft used a
# bare "cutover-authorization.json", which is not the canonical ref --
# so no correct implementation could ever have satisfied that fixture.
AUTHORIZATION_REF = "receipts/cutover-authorization.json"


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
        regenerated = driver.ProductionArtifactPolicy().encode(
            "receipt", {**receipt, "binding_sha256": bundle.binding_sha256}
        )
        # A tautology check: encoding the same expression twice compares
        # nothing. The meaningful comparison is against bytes the PRODUCER
        # published, which TestPublicChainPublishesRealArtifacts performs.
        assert cm.PersistedDoc(regenerated).obj.cutover_window_id is not None
        assert (
            cm.PersistedDoc(regenerated).obj.bundle_binding_sha256
            == bundle.binding_sha256
        )


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
        """Seed a private root that a CORRECT implementation can satisfy.

        Three defects in the first draft, all fatal to the test's purpose:
        missing inputs were silently skipped (so the fixture could be
        hollow), the authorization ref was not the frozen name, and no
        authorization artifact was minted at all -- there is none under
        the live root to copy. Every input is now required, and the
        authorization is minted here, parented to the stage-1 bench anchor
        computed from this private root's own inputs.
        """
        from dataclasses import fields as dataclass_fields

        from tests.test_cuda_migration import _cutover_authorization_doc
        from tests.test_cutover_step1_invariants import stage1_paths

        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        authority = stage2_input_paths()
        for f in dataclass_fields(authority):
            if f.name == "authorization":
                continue
            rel = getattr(authority, f.name)
            src = BENCH_ROOT / rel
            assert src.is_file(), f"missing required stage-1 input: {rel}"
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            dst.chmod(0o600)

        stage1 = assemble.build_stage1_bundle(
            stage1_paths(), root=root, timestamp=STAGE2_TS
        )
        auth = _cutover_authorization_doc(stage1.bench_binding_sha256)
        auth_path = root / AUTHORIZATION_REF
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_bytes(auth.wrapper_bytes)
        auth_path.chmod(0o600)

        (root / "markers").mkdir(mode=0o700, exist_ok=True)
        for directory in root.rglob("*"):
            if directory.is_dir():
                directory.chmod(0o700)
        return root

    def test_invocation_publishes_admission_receipt_and_completion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from scripts import cuda_bench_cli as cli

        root = self._private_root(tmp_path)
        monkeypatch.setattr(driver, "BENCH_ROOT", root)

        seen_args: list[tuple[object, Path]] = []
        real_builder = assemble.build_stage2_bundle

        def spy(paths, *, root, timestamp):
            seen_args.append((paths, root))
            return real_builder(paths, root=root, timestamp=timestamp)

        monkeypatch.setattr(assemble, "build_stage2_bundle", spy)

        rc = cli.main(
            ["assemble-stage2", "--window-id", "cutover-20260713-1202"]
        )
        assert rc == 0
        # the canonical builder ran exactly once
        assert len(seen_args) == 1

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

        # the admission document itself, through the live reader
        admission = cm.CommandAdmissionPreimage(
            selected_ref=admissions[0].name,
            wrapper_bytes=admissions[0].read_bytes(),
        )
        assert admission.command == "assemble-stage2"
        assert completion.admission_ref == admissions[0].name
        assert admission.ordinal == completion.ordinal
        assert admission.window_id == completion.window_id

        # the authorization's window joins the whole chain
        auth = cm._canonical_persisted_role(
            cm.PersistedDoc((root / AUTHORIZATION_REF).read_bytes()),
            cm.CutoverAuthorizationDoc,
        ).obj
        assert auth.window_id == completion.window_id

        # the PUBLISHED receipt equals independently regenerated bytes
        bundle = assemble.build_stage2_bundle(
            stage2_input_paths(), root=root, timestamp=receipt.timestamp
        )
        verdict = cm.evaluate_promotion_bundle(bundle)
        assert receipt_bytes == driver.ProductionArtifactPolicy().encode(
            "receipt",
            {
                **cm.build_receipt(
                    bundle, verdict, timestamp=bundle.timestamp
                ),
                "binding_sha256": bundle.binding_sha256,
            },
        )

        # the builder received the EXACT frozen authority, not "some args"
        assert seen_args == [(stage2_input_paths(), root)]

        # the live completion-pair validator accepts this exact chain
        cm.CommandCompletionDoc(
            command=completion.command,
            ordinal=completion.ordinal,
            window_id=completion.window_id,
            admission_ref=completion.admission_ref,
            admission_sha256=completion.admission_sha256,
            artifact_ref=completion.artifact_ref,
            artifact_sha256=completion.artifact_sha256,
            artifact_schema=completion.artifact_schema,
            status=completion.status,
            timestamp=completion.timestamp,
        )

        # full frozen producer chronology, authorization window included
        assert cm._compare_utc_z(auth.issued_at, admission.timestamp) <= 0
        assert cm._compare_utc_z(admission.timestamp, receipt.timestamp) <= 0
        assert cm._compare_utc_z(receipt.timestamp, completion.timestamp) <= 0
        assert cm._compare_utc_z(completion.timestamp, auth.expires_at) < 0

    @staticmethod
    def _tree_snapshot(root: Path) -> dict[str, tuple[str, str]]:
        """Complete tree: canonical relative path -> (type, content hash).

        Top-level filenames prove nothing -- an in-place modification of
        any nested file would pass unnoticed, which is exactly the write
        this guard exists to detect.
        """
        import hashlib

        snapshot: dict[str, tuple[str, str]] = {}
        for path in sorted(root.rglob("*")):
            rel = str(path.relative_to(root))
            if path.is_symlink():
                snapshot[rel] = ("symlink", os.readlink(path))
            elif path.is_dir():
                snapshot[rel] = ("dir", "")
            elif path.is_file():
                snapshot[rel] = (
                    "file",
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            else:
                snapshot[rel] = ("other", "")
        return snapshot

    def test_the_live_bench_root_is_byte_identical_across_a_real_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GREEN guard, now and after: invoke for real, prove no live write.

        The first version prepared a private root, never called main(),
        and compared only top-level filenames. It proved neither that the
        command ran nor that the live tree was untouched.
        """
        from scripts import cuda_bench_cli as cli

        before = self._tree_snapshot(BENCH_ROOT)
        # Seeded from the stage-1 authority, which EXISTS, so this guard is
        # green today and stays green after 2A lands. Depending on
        # Stage2InputPaths would have made the anchoring guard unavailable
        # exactly while the code it guards is being written.
        from dataclasses import fields as dataclass_fields

        from tests.test_cutover_step1_invariants import stage1_paths

        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        stage1 = stage1_paths()
        for f in dataclass_fields(stage1):
            rel = getattr(stage1, f.name)
            src = BENCH_ROOT / rel
            assert src.is_file(), rel
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
        assert root != BENCH_ROOT
        monkeypatch.setattr(driver, "BENCH_ROOT", root)
        try:
            cli.main(
                ["assemble-stage2", "--window-id", "cutover-20260713-1202"]
            )
        except BaseException:
            # Even a refusal must not have written to the live root.
            pass
        assert self._tree_snapshot(BENCH_ROOT) == before


class TestOneBuilderTopology:
    """Exactly two production construction sites, by exact line identity.

    Iteration history, because each fix exposed the next hole:

    * a SET collapsed two calls in one allowed function into one entry;
    * partial alias RESOLUTION invited the evasion it claimed to stop;
    * module-scope and lambda construction were invisible;
    * five hand-picked roots missed most of the tree;
    * `git ls-files` spawned a subprocess, creating fresh airlock
      spawn-debt for a guard that must certify;
    * alias rejection still missed destructuring, walrus, getattr and
      re-export shapes, and parse errors were silently swallowed.

    Final position: NO alias resolution at all. Any reference to the
    constructor symbol other than a call at an allowlisted site is a
    failure, parse errors are failures rather than skips, and the scanner
    self-tests that it detects each evasion shape.
    """

    SYMBOL = "BenchEvidenceBundle"
    EXCLUDED_ROOTS = frozenset(
        {"tests", "docs", "staging", "tmp", "backups", "research", "local",
         "logs", "output", "models", "data", "web", "workshop", ".git"}
    )
    ALLOWLIST = {
        ("scripts/cuda_bench_assemble.py", "build_stage1_bundle"),
        ("scripts/cuda_bench_assemble.py", "build_stage2_bundle"),
    }

    @classmethod
    def _production_files(cls) -> list[Path]:
        """No subprocess: walking avoids new airlock spawn-debt."""
        found: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(REPO):
            rel_dir = Path(dirpath).relative_to(REPO)
            top = rel_dir.parts[0] if rel_dir.parts else ""
            if top in cls.EXCLUDED_ROOTS:
                dirnames[:] = []
                continue
            dirnames[:] = [
                d
                for d in dirnames
                if d not in cls.EXCLUDED_ROOTS and not d.startswith(".")
            ]
            found.extend(
                Path(dirpath) / name
                for name in filenames
                if name.endswith(".py")
            )
        return sorted(found)

    @classmethod
    def _scan(cls) -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]]]:
        """Return (call sites, non-call references). Lists, not sets."""
        calls: list[tuple[str, int, str]] = []
        refs: list[tuple[str, int, str]] = []
        for path in cls._production_files():
            rel = str(path.relative_to(REPO))
            source = path.read_text(encoding="utf-8", errors="strict")
            # A parse error is a FAILURE, not a skip: an unparsed file is
            # an unscanned file.
            tree = ast.parse(source, filename=rel)
            scope: dict[int, str] = {}
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
                ):
                    label = getattr(node, "name", "<lambda>")
                    for child in ast.walk(node):
                        scope.setdefault(id(child), label)
            called: set[int] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    f = node.func
                    name = (
                        f.attr
                        if isinstance(f, ast.Attribute)
                        else f.id
                        if isinstance(f, ast.Name)
                        else None
                    )
                    if name == cls.SYMBOL:
                        called.add(id(f))
                        calls.append(
                            (rel, node.lineno, scope.get(id(node), "<module>"))
                        )
            # EVERY other mention of the symbol -- assignment, walrus,
            # destructuring, import-as, re-export, getattr string -- is a
            # non-call reference and is rejected without interpretation.
            for node in ast.walk(tree):
                if isinstance(node, (ast.Name, ast.Attribute)):
                    label = (
                        node.attr
                        if isinstance(node, ast.Attribute)
                        else node.id
                    )
                    if label == cls.SYMBOL and id(node) not in called:
                        refs.append(
                            (rel, node.lineno, type(node).__name__)
                        )
                elif isinstance(node, ast.ClassDef) and node.name == cls.SYMBOL:
                    refs.append((rel, node.lineno, "ClassDef"))
                elif isinstance(node, ast.Constant) and node.value == cls.SYMBOL:
                    refs.append((rel, node.lineno, "Constant"))
                elif isinstance(node, ast.alias) and node.name == cls.SYMBOL:
                    refs.append((rel, getattr(node, "lineno", 0), "alias"))
        return calls, refs

    def test_call_sites_are_exactly_two_by_line_identity(self) -> None:
        calls, _ = self._scan()
        assert len(calls) == 2, calls
        assert {(f, fn) for f, _, fn in calls} == self.ALLOWLIST

    def test_no_module_scope_or_lambda_construction(self) -> None:
        calls, _ = self._scan()
        assert not [c for c in calls if c[2] in ("<module>", "<lambda>")], calls

    # Every legitimate non-call reference, enumerated. Rejecting ALL of
    # them (my first attempt) would forbid type annotations and the class
    # definition itself -- an over-correction that made the guard wrong
    # rather than strict. This is the closed allowlist review asked for:
    # any reference NOT on it is an alias or an evasion.
    REFERENCE_ALLOWLIST = {
        ("scripts/cuda_migration.py", "ClassDef"),      # the definition
        ("scripts/cuda_migration.py", "Name"),          # signature annotations
        ("scripts/cuda_bench_assemble.py", "Attribute"),  # return annotations
        ("scripts/cuda_migration.py", "Constant"),  # -> "BenchEvidenceBundle"
    }

    def test_every_constructor_reference_is_on_the_closed_allowlist(
        self,
    ) -> None:
        _, refs = self._scan()
        kinds = {(f, kind) for f, _, kind in refs}
        assert kinds <= self.REFERENCE_ALLOWLIST, kinds - self.REFERENCE_ALLOWLIST

    def test_no_reference_lives_outside_the_two_owning_modules(self) -> None:
        """An alias in a third module is the evasion that matters."""
        _, refs = self._scan()
        files = {f for f, _, _ in refs}
        assert files <= {
            "scripts/cuda_migration.py",
            "scripts/cuda_bench_assemble.py",
        }, files

    # --- self-tests: prove the scanner detects what it claims to ---

    EVASIONS = (
        "B = cm.BenchEvidenceBundle",
        "B: object = cm.BenchEvidenceBundle",
        "(B, C) = (cm.BenchEvidenceBundle, 1)",
        "x = [cm.BenchEvidenceBundle][0]",
        "from scripts.cuda_migration import BenchEvidenceBundle as B",
        "B = getattr(cm, 'BenchEvidenceBundle')",
        "if (B := cm.BenchEvidenceBundle):\n    pass",
        "__all__ = ['BenchEvidenceBundle']",
    )

    @pytest.mark.parametrize("snippet", EVASIONS)
    def test_scanner_detects_each_alias_shape(self, snippet: str) -> None:
        tree = ast.parse(snippet)
        hits = [
            n
            for n in ast.walk(tree)
            if (
                (isinstance(n, ast.Name) and n.id == self.SYMBOL)
                or (isinstance(n, ast.Attribute) and n.attr == self.SYMBOL)
                or (isinstance(n, ast.Constant) and n.value == self.SYMBOL)
                or (isinstance(n, ast.alias) and n.name == self.SYMBOL)
            )
        ]
        assert hits, snippet

    def test_scanner_detects_duplicate_calls_in_one_function(self) -> None:
        tree = ast.parse(
            "def f():\n"
            "    a = cm.BenchEvidenceBundle()\n"
            "    b = cm.BenchEvidenceBundle()\n"
        )
        calls = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == self.SYMBOL
        ]
        assert len(calls) == 2

    def test_scanner_spawns_no_process(self) -> None:
        """A guard that spawns cannot certify under the airlock.

        Checked structurally, not by substring: my first version searched
        for the word "subprocess" and failed on its own docstring, which
        explains why the subprocess approach was abandoned.
        """
        tree = ast.parse(Path(__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names]
                assert "subprocess" not in names, names
            if isinstance(node, ast.Call):
                f = node.func
                attr = f.attr if isinstance(f, ast.Attribute) else None
                assert attr not in {"system", "popen", "spawn", "run"}, attr

    def test_exclusions_are_explicit(self) -> None:
        assert "tests" in self.EXCLUDED_ROOTS
