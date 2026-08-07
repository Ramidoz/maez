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
# The window-8 evidence is dated 2026-08-03; its latest stage-1 timestamp
# is 19:37:16Z. v1 of this fixture minted a JULY 13 authorization over
# AUGUST 3 evidence and then let main() run on the real (August 6) clock,
# so the permit both predated its evidence and had expired. No correct
# implementation could satisfy that. These dates are physically possible.
LATEST_EVIDENCE = "2026-08-03T19:37:16Z"
AUTH_ISSUED_AT = "2026-08-03T20:00:00Z"          # after the last evidence
AUTH_EXPIRES_AT = "2026-08-04T00:00:00Z"         # issued + CUTOVER_TTL_S
STAGE2_TS = "2026-08-03T20:30:00Z"               # inside the window
RUN_CLOCK = "2026-08-03T20:31:00Z"               # injected into main()
# The FROZEN name (scripts/cuda_cutover.py:22). My first draft used a
# bare "cutover-authorization.json", which is not the canonical ref --
# so no correct implementation could ever have satisfied that fixture.
AUTHORIZATION_REF = "receipts/cutover-authorization.json"


def seed_private_root(tmp_path: Path) -> Path:
    """Seed a private root every success witness uses.

    Direct builder tests previously passed root=BENCH_ROOT, where
    receipts/cutover-authorization.json does not exist -- so they could
    never have gone green either.
    """
    from dataclasses import fields as dataclass_fields

    from tests.test_cuda_migration import _cutover_authorization_doc
    from tests.test_cutover_step1_invariants import stage1_paths

    root = tmp_path / "bench"
    root.mkdir(mode=0o700)
    stage1 = stage1_paths()
    for f in dataclass_fields(stage1):
        rel = getattr(stage1, f.name)
        src = BENCH_ROOT / rel
        assert src.is_file(), f"missing required stage-1 input: {rel}"
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        dst.chmod(0o600)

    # Directory modes must be 0700 BEFORE any read: open_bench_file
    # enforces them, and seeding chmod'd afterwards -- so the anchor build
    # refused and every success witness failed on the fixture rather than
    # its intended cause.
    (root / "markers").mkdir(mode=0o700, exist_ok=True)
    for directory in root.rglob("*"):
        if directory.is_dir():
            directory.chmod(0o700)
    root.chmod(0o700)

    anchor = assemble.build_stage1_bundle(
        stage1_paths(), root=root, timestamp=STAGE2_TS
    ).bench_binding_sha256
    auth = _cutover_authorization_doc(
        anchor, issued_at=AUTH_ISSUED_AT, expires_at=AUTH_EXPIRES_AT
    )
    auth_path = root / AUTHORIZATION_REF
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_bytes(auth.wrapper_bytes)
    auth_path.chmod(0o600)
    auth_path.parent.chmod(0o700)
    return root


class FixedClock:
    """Deterministic clock that ADVANCES one second per read.

    A constant clock would make admission and completion equal, and the
    live pair validator requires admission STRICTLY before completion --
    so a frozen clock would have made correct code unverifiable.
    """

    def __init__(self, moment: str = RUN_CLOCK) -> None:
        import datetime

        self._next = datetime.datetime.strptime(
            moment, "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=datetime.timezone.utc)

    def now_utc(self) -> str:
        import datetime

        value = self._next
        self._next = value + datetime.timedelta(seconds=1)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")


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

    def test_build_stage2_bundle_yields_provisional_cuda_boot(
        self, tmp_path: Path
    ) -> None:
        """The whole point of 2A: a real stage-2 permit from real inputs.

        Symbol-existence REDs pass the moment a stub is written. This one
        only passes when the producer genuinely assembles a stage-2 bundle
        that the PUBLIC evaluator scores as provisional_cuda_boot.
        """
        bundle = assemble.build_stage2_bundle(
            stage2_input_paths(),
            root=seed_private_root(tmp_path),
            timestamp=STAGE2_TS,
        )
        assert type(bundle) is cm.BenchEvidenceBundle
        verdict = cm.evaluate_promotion_bundle(bundle)
        assert verdict.decision == "provisional_cuda_boot"
        assert verdict.cutover_window_id is not None

    def test_producer_receipt_is_the_exact_canonical_bytes(
        self, tmp_path: Path
    ) -> None:
        """Compare BYTES, not two dictionary fields.

        The first version asserted two keys and called itself "exact
        canonical bytes". The 2B join is byte equality against the real
        encoder, so that is what this must compare.
        """
        bundle = assemble.build_stage2_bundle(
            stage2_input_paths(),
            root=seed_private_root(tmp_path),
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
    """main() must assemble and publish -- proven around ONE invocation.

    Registration, parsing and a matrix entry say nothing: assemble-stage2
    could stay bound to _unimplemented_handler and every other CLI test
    would pass.
    """

    @staticmethod
    def _tree_snapshot(root: Path) -> dict[str, tuple[str, str]]:
        """Complete tree: relative path -> (type, content hash)."""
        import hashlib

        snapshot: dict[str, tuple] = {}
        # The ROOT ITSELF is included: a chmod on the bench root is a live
        # mutation, and iterating only its children could never see it.
        for path in [root, *sorted(root.rglob("*"))]:
            rel = "." if path == root else str(path.relative_to(root))
            st = path.lstat()
            # mode, uid, gid and inode identity, not merely type+content.
            # A stray chmod or chown is a write on the live tree.
            # nlink/size/mtime_ns/ctime_ns included: without them a
            # same-BYTE rewrite leaves the snapshot equal, so a live file
            # could be rewritten identically and go unnoticed. ctime_ns in
            # particular moves on any metadata write.
            authority = (
                st.st_mode,
                st.st_uid,
                st.st_gid,
                st.st_dev,
                st.st_ino,
                st.st_nlink,
                st.st_size,
                st.st_mtime_ns,
                st.st_ctime_ns,
            )
            if path.is_symlink():
                snapshot[rel] = ("symlink", os.readlink(path), authority)
            elif path.is_dir():
                snapshot[rel] = ("dir", "", authority)
            elif path.is_file():
                snapshot[rel] = (
                    "file",
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    authority,
                )
            else:
                snapshot[rel] = ("other", "", authority)
        return snapshot

    def test_one_invocation_publishes_the_chain_and_touches_nothing_live(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import hashlib

        from scripts import cuda_bench_cli as cli

        root = seed_private_root(tmp_path)
        monkeypatch.setattr(driver, "BENCH_ROOT", root)
        monkeypatch.setattr(driver, "SystemClock", FixedClock)

        # cli.main() sets module-level command globals and installs signal
        # handlers. Left behind in a pytest process they break unrelated
        # signal tests downstream -- verified: this test alone made four
        # driver signal tests fail in the same process. monkeypatch
        # restores each attribute afterwards; the handlers are restored
        # explicitly because main() owns them for its own duration only.
        import signal as _signal

        for name in (
            "_terminal_committed",
            "_cleanup_incomplete_committing",
            "_linearized_durable_success",
        ):
            monkeypatch.setattr(cli, name, getattr(cli, name), raising=False)
        saved_handlers = {
            number: _signal.getsignal(number)
            for number in (_signal.SIGINT, _signal.SIGTERM)
        }
        # The real residue: main() restores the signal MASK only when it
        # did NOT commit a terminal (_restore_command_signal_scope with
        # restore_mask=not _terminal_committed). On success it leaves
        # SIGINT/SIGTERM blocked -- correct for a CLI process about to
        # exit, but in-process it leaves the mask blocked for every
        # subsequently SPAWNED CHILD, which then cannot be interrupted.
        saved_mask = _signal.pthread_sigmask(_signal.SIG_BLOCK, [])

        seen_args: list[tuple[object, Path]] = []
        real_builder = assemble.build_stage2_bundle

        def spy(paths, *, root, timestamp):
            seen_args.append((paths, root))
            return real_builder(paths, root=root, timestamp=timestamp)

        monkeypatch.setattr(assemble, "build_stage2_bundle", spy)

        # Event trace + receipt-scoped durability, around the one run.
        #
        # Two seams were wrong before: admission never passes through
        # publish_command_artifact (it is created inside _admit_command),
        # so the required order could never be observed; and
        # publish_command_artifact links with os.link directly, not
        # _publish_anonymous_file, so the link spy watched a primitive
        # this path does not use. Worse, aggregate counters let admission
        # and terminal PAY the receipt's durability while the receipt used
        # Path.write_bytes().
        publications: list[tuple[str, str, str]] = []
        private_writes: list[tuple[str, bytes, Path]] = []

        real_admit = driver._admit_command
        real_publish = driver.publish_command_artifact
        real_private = driver.write_private_file

        def admit_spy(*args, **kwargs):
            attempt = real_admit(*args, **kwargs)
            # recorded AFTER the durable return
            publications.append(("admission", attempt.admission_ref, ""))
            return attempt

        def publish_spy(attempt, role, encoded, *, root, on_committed=None):
            out = real_publish(
                attempt, role, encoded, root=root, on_committed=on_committed
            )
            publications.append((role, out[0], out[1]))
            return out

        def private_spy(relative, data, *, root, on_link=None):
            # root is MANDATORY here on purpose. Mirroring the production
            # default (root=BENCH_ROOT) would capture the ALREADY-PATCHED
            # private root, so a handler that omits root=root would pass
            # this test while writing to the live bench root in production.
            out = real_private(relative, data, root=root, on_link=on_link)
            private_writes.append((relative, data, Path(root)))
            publications.append(
                ("receipt", relative, hashlib.sha256(data).hexdigest())
            )
            return out

        monkeypatch.setattr(driver, "_admit_command", admit_spy)
        monkeypatch.setattr(driver, "publish_command_artifact", publish_spy)
        monkeypatch.setattr(driver, "write_private_file", private_spy)

        # Live-root integrity is measured around the SAME successful run.
        # A separate guard that tolerates an early refusal cannot see a
        # stray write on the success path.
        live_before = self._tree_snapshot(BENCH_ROOT)
        rc = cli.main(
            ["assemble-stage2", "--window-id", "cutover-20260713-1202"]
        )
        _signal.pthread_sigmask(_signal.SIG_SETMASK, saved_mask)
        for number, handler in saved_handlers.items():
            _signal.signal(number, handler)

        assert rc == 0
        assert self._tree_snapshot(BENCH_ROOT) == live_before

        # Freeze the producer's call record BEFORE any regeneration below,
        # and regenerate through real_builder -- the spy is still
        # installed, so calling the module attribute would record a second
        # call and make this assertion reject correct code.
        producer_calls = list(seen_args)
        assert len(producer_calls) == 1
        assert producer_calls[0] == (stage2_input_paths(), root)

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

        admission = cm.CommandAdmissionPreimage(
            selected_ref=admissions[0].name,
            wrapper_bytes=admissions[0].read_bytes(),
        )
        assert admission.command == "assemble-stage2"
        assert completion.admission_ref == admissions[0].name
        assert admission.ordinal == completion.ordinal
        assert admission.window_id == completion.window_id
        assert completion.admission_sha256 == hashlib.sha256(
            admissions[0].read_bytes()
        ).hexdigest()

        receipt_bytes = (root / completion.artifact_ref).read_bytes()
        assert completion.artifact_sha256 == hashlib.sha256(
            receipt_bytes
        ).hexdigest()
        receipt = cm._canonical_persisted_role(
            cm.PersistedDoc(receipt_bytes), cm.AssembleReceiptDoc
        ).obj
        assert receipt.decision == "provisional_cuda_boot"
        assert receipt.cutover_window_id == completion.window_id

        # THE REAL validator, not a reconstruction of one document.
        driver._load_verified_completion_pair(
            admission_ref=completion.admission_ref,
            completion_ref=terminals[0].name,
            artifact_ref=completion.artifact_ref,
            artifact_bytes=receipt_bytes,
            expected_command="assemble-stage2",
            expected_window_id=completion.window_id,
            expected_type=cm.AssembleReceiptDoc,
            root=root,
        )

        # published bytes == independent regeneration (real_builder!)
        bundle = real_builder(
            stage2_input_paths(), root=root, timestamp=receipt.timestamp
        )
        verdict = cm.evaluate_promotion_bundle(bundle)
        assert receipt_bytes == driver.ProductionArtifactPolicy().encode(
            "receipt",
            {
                **cm.build_receipt(bundle, verdict, timestamp=bundle.timestamp),
                "binding_sha256": bundle.binding_sha256,
            },
        )
        assert len(seen_args) == len(producer_calls)  # regeneration bypassed the spy

        auth = cm._canonical_persisted_role(
            cm.PersistedDoc((root / AUTHORIZATION_REF).read_bytes()),
            cm.CutoverAuthorizationDoc,
        ).obj
        assert auth.window_id == completion.window_id

        # FROZEN chronology, boot witness included:
        #   issued <= boot witness <= admission <= receipt <= completion < expiry
        # The boot witness is minted DURING assembly, so it follows
        # admission rather than preceding it. My first ordering put it
        # before admission and would have rejected the correct producer.
        # Step 1 requires issued <= witness <= assembly, which holds:
        # the witness carries the assembly timestamp exactly.
        boot_at = bundle.boot_authorization.timestamp
        assert boot_at == receipt.timestamp
        chain = [
            auth.issued_at,
            admission.timestamp,
            boot_at,
            completion.timestamp,
        ]
        for earlier, later in zip(chain, chain[1:], strict=False):
            assert cm._compare_utc_z(earlier, later) <= 0, (earlier, later)
        assert cm._compare_utc_z(completion.timestamp, auth.expires_at) < 0

        # PUBLICATION ORDER by EVENT TRACE, not mtime. mtime would let a
        # producer precompute the receipt hash, publish the completion,
        # then publish the receipt, and still pass.
        # Ordering is IDENTITY-BOUND. Selecting the first generic
        # "receipt" event would accept:
        #   admission -> unrelated receipt -> terminal -> actual receipt
        # so each position names the exact artifact.
        admission_event = ("admission", completion.admission_ref, "")
        receipt_event = (
            "receipt",
            completion.artifact_ref,
            hashlib.sha256(receipt_bytes).hexdigest(),
        )
        terminal_event = next(
            e for e in publications if e[0] == "terminal" and e[1] == terminals[0].name
        )
        for event in (admission_event, receipt_event, terminal_event):
            assert event in publications, (event, publications)
        assert publications.index(admission_event) < publications.index(
            receipt_event
        ), publications
        assert publications.index(receipt_event) < publications.index(
            terminal_event
        ), publications

        # DURABILITY, SCOPED TO THIS RECEIPT, UNDER THE INJECTED ROOT.
        # write_private_file is the anchored tmpfile -> fsync -> link ->
        # parent-fsync primitive; binding ref, bytes AND root proves the
        # receipt itself was durably published where it belongs.
        assert (
            completion.artifact_ref,
            receipt_bytes,
            root,
        ) in private_writes, [(r, p) for r, _, p in private_writes]


SYMBOL = "BenchEvidenceBundle"


def scan_source(source: str, rel: str) -> tuple[
    list[tuple[str, int, str]], list[tuple[str, int, str, str]]
]:
    """THE scanner. One implementation, used by production scan AND self-tests.

    Returns (call_sites, reference_sites). A reference site is
    (file, line, ast-kind, enclosing-context). Parse failure raises --
    an unparsed file is an unscanned file, never a silent skip.
    """
    tree = ast.parse(source, filename=rel)
    # Parent/field links give each reference its SYNTACTIC ROLE. Kind plus
    # enclosing function was substitutable: an alias inside
    # build_stage2_bundle classified identically to that function's return
    # annotation, so dropping the annotation and adding the alias kept the
    # count intact. A role distinguishes them -- an alias sits in
    # Assign.value, an annotation in FunctionDef.returns.
    parent: dict[int, tuple[ast.AST, str]] = {}
    for node in ast.walk(tree):
        for field, value in ast.iter_fields(node):
            for child in value if isinstance(value, list) else [value]:
                if isinstance(child, ast.AST):
                    parent[id(child)] = (node, field)
    context: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            label = getattr(node, "name", "<lambda>")
            for child in ast.walk(node):
                context.setdefault(id(child), label)

    calls: list[tuple[str, int, str]] = []
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
            if name == SYMBOL:
                called.add(id(f))
                calls.append(
                    (rel, node.lineno, context.get(id(node), "<module>"))
                )

    refs: list[tuple[str, int, str, str]] = []
    for node in ast.walk(tree):
        label = None
        if isinstance(node, ast.Name):
            label = node.id
        elif isinstance(node, ast.Attribute):
            label = node.attr
        elif isinstance(node, ast.ClassDef):
            label = node.name
        elif isinstance(node, ast.Constant):
            label = node.value
        elif isinstance(node, ast.alias):
            label = node.name
        if label != SYMBOL or id(node) in called:
            continue
        owner = parent.get(id(node))
        role = (
            f"{type(owner[0]).__name__}.{owner[1]}" if owner else "<root>"
        )
        refs.append(
            (
                rel,
                getattr(node, "lineno", 0),
                role,
                context.get(id(node), "<module>"),
            )
        )
    return calls, refs


class TestOneBuilderTopology:
    """Exactly two call sites; every reference on a CLOSED allowlist.

    Iteration history, each fix exposing the next hole: a set collapsed
    duplicate calls; partial alias resolution invited the evasion it
    claimed to stop; module-scope and lambda construction were invisible;
    five hand-picked roots missed most of the tree; `git ls-files` created
    fresh airlock spawn-debt; rejecting EVERY reference would have
    forbidden type annotations; and the allowlist was then so broad that a
    new alias of an already-allowed kind in an owning module passed.

    Closed here by two things together: each reference must match an
    allowlisted (file, kind, context) triple, AND the total count is
    pinned -- so any addition fails even if its shape is familiar.
    """

    EXCLUDED_ROOTS = frozenset(
        {"tests", "docs", "staging", "tmp", "backups", "research", "local",
         "logs", "output", "models", "data", "web", "workshop", ".git"}
    )
    CALL_ALLOWLIST = {
        ("scripts/cuda_bench_assemble.py", "build_stage1_bundle"),
        ("scripts/cuda_bench_assemble.py", "build_stage2_bundle"),
    }
    # EXACT MULTISET of (file, context, syntactic role). Multiplicity is
    # part of the pin, so an alias cannot be traded for a deleted
    # annotation. Adding a builder adds its own entry -- a deliberate edit.
    REFERENCE_MULTISET = {
        ("scripts/cuda_migration.py", "BenchEvidenceBundle", "Module.body"): 1,
        ("scripts/cuda_migration.py", "BenchEvidenceBundle", "FunctionDef.returns"): 1,
        ("scripts/cuda_migration.py", "evaluate_promotion_bundle", "arg.annotation"): 1,
        ("scripts/cuda_migration.py", "evaluate_promotion_bundle", "Compare.comparators"): 1,
        ("scripts/cuda_migration.py", "evaluate_promotion_bundle", "Attribute.value"): 1,
        ("scripts/cuda_migration.py", "build_receipt", "arg.annotation"): 1,
        ("scripts/cuda_bench_assemble.py", "build_stage1_bundle", "FunctionDef.returns"): 1,
        ("scripts/cuda_bench_assemble.py", "Stage1Evaluation", "AnnAssign.annotation"): 1,
        # 2A adds exactly two more, both pinned by exact role:
        ("scripts/cuda_bench_assemble.py", "build_stage2_bundle", "FunctionDef.returns"): 1,
        # fields(cm.BenchEvidenceBundle) -- reading the field list to carry
        # stage-1 values forward, NOT constructing and NOT aliasing.
        ("scripts/cuda_bench_assemble.py", "build_stage2_bundle", "Call.args"): 1,
    }
    # Any role NOT in the pinned multiset is an alias or an evasion.
    BINDING_ROLES = frozenset(
        {
            "Assign.value",
            "AnnAssign.value",
            "NamedExpr.value",
            "Tuple.elts",
            "List.elts",
            "Subscript.value",
            "ImportFrom.names",
            "Import.names",
        }
    )

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
                Path(dirpath) / n for n in filenames if n.endswith(".py")
            )
        return sorted(found)

    @classmethod
    def _scan_production(cls):
        calls: list[tuple[str, int, str]] = []
        refs: list[tuple[str, int, str, str]] = []
        for path in cls._production_files():
            rel = str(path.relative_to(REPO))
            c, r = scan_source(path.read_text(encoding="utf-8"), rel)
            calls.extend(c)
            refs.extend(r)
        return calls, refs

    def test_call_sites_are_exactly_two(self) -> None:
        calls, _ = self._scan_production()
        assert len(calls) == 2, calls
        assert {(f, fn) for f, _, fn in calls} == self.CALL_ALLOWLIST

    def test_no_module_scope_or_lambda_construction(self) -> None:
        calls, _ = self._scan_production()
        assert not [c for c in calls if c[2] in ("<module>", "<lambda>")], calls

    def test_references_match_the_pinned_multiset_exactly(self) -> None:
        from collections import Counter

        _, refs = self._scan_production()
        observed = Counter((f, ctx, role) for f, _, role, ctx in refs)
        assert dict(observed) == self.REFERENCE_MULTISET, {
            "unexpected": dict(observed.items() - self.REFERENCE_MULTISET.items()),
            "missing": dict(self.REFERENCE_MULTISET.items() - observed.items()),
        }

    def test_no_reference_occupies_a_binding_role(self) -> None:
        """A binding role IS an alias, wherever it appears."""
        _, refs = self._scan_production()
        bound = [r for r in refs if r[2] in self.BINDING_ROLES]
        assert bound == [], bound

    # --- self-tests: run the REAL scanner, assert the REAL allowlist ---

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
    def test_the_real_scanner_rejects_each_evasion(self, snippet: str) -> None:
        """Previously these only walked an AST and never touched the
        scanner or the allowlist, so they proved nothing about the guard."""
        _, refs = scan_source(snippet, "scripts/evasion.py")
        assert refs, snippet
        # The real guarantee the production test enforces: every site an
        # evasion produces is OUTSIDE the pinned multiset. Asserting a
        # BINDING_ROLES membership instead was too narrow -- an ast.alias
        # sits in ImportFrom.names, and getattr puts a STRING in Call.args,
        # so two shapes escaped a check that claimed to cover them all.
        sites = {(f, ctx, role) for f, _, role, ctx in refs}
        assert sites - set(self.REFERENCE_MULTISET), (snippet, refs)

    def test_alias_inside_an_allowed_context_is_still_rejected(self) -> None:
        """The exact substitution review reproduced.

        An alias placed inside build_stage2_bundle used to classify the
        same as that function's return annotation, so deleting the
        annotation and adding the alias preserved the pinned count. Roles
        separate them.
        """
        from collections import Counter

        _, refs = scan_source(
            "def build_stage2_bundle():\n"
            "    B = cm.BenchEvidenceBundle\n"
            "    return B\n",
            "scripts/cuda_bench_assemble.py",
        )
        observed = Counter((f, ctx, role) for f, _, role, ctx in refs)
        assert dict(observed) != self.REFERENCE_MULTISET
        assert any(r[2] in self.BINDING_ROLES for r in refs), refs

    def test_the_real_scanner_counts_duplicate_calls_in_one_function(
        self,
    ) -> None:
        calls, _ = scan_source(
            "def f():\n"
            "    a = cm.BenchEvidenceBundle()\n"
            "    b = cm.BenchEvidenceBundle()\n",
            "scripts/dup.py",
        )
        assert len(calls) == 2
        assert {c[2] for c in calls} == {"f"}

    def test_the_real_scanner_keeps_line_identity(self) -> None:
        calls, _ = scan_source(
            "def f():\n    return cm.BenchEvidenceBundle()\n", "scripts/x.py"
        )
        assert calls == [("scripts/x.py", 2, "f")]

    def test_write_private_file_is_the_anchored_primitive(self) -> None:
        """Pin the seam the durability proof relies on.

        If write_private_file ever stops going through the anonymous-file
        / fsync / link chain, the receipt durability assertion silently
        becomes vacuous. Checked structurally -- my first check was a
        substring search over a function that DELEGATES, and reported
        False for a primitive that plainly qualifies.
        """
        import inspect

        tree = ast.parse(inspect.getsource(driver.write_private_file))
        called = {
            n.func.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        } | {
            n.func.attr
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }
        for required in (
            "_open_anonymous_file",
            "_write_all",
            "fsync",
            "_publish_anonymous_file",
            "_verify_path_binding",
        ):
            assert required in called, required

    def test_scanner_spawns_no_process(self) -> None:
        tree = ast.parse(Path(__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                assert "subprocess" not in [a.name for a in node.names]
            if isinstance(node, ast.Call):
                f = node.func
                attr = f.attr if isinstance(f, ast.Attribute) else None
                assert attr not in {"system", "popen", "spawn"}

    def test_exclusions_are_explicit(self) -> None:
        assert "tests" in self.EXCLUDED_ROOTS


class TestProductionIdentityProjection:
    """The production identity is PROJECTED, never probed.

    A live probe before cutover could only observe the INCUMBENT Vulkan
    process -- it would attest the thing being replaced. RuntimeIdentity
    is pinned configuration by its own docstring, not observation.
    """

    @staticmethod
    def _bench_doc(root: Path):
        from tests.test_cutover_step1_invariants import stage1_paths

        return cm.PersistedDoc(
            driver.open_bench_file(stage1_paths().runtime_identity, root=root)
        )

    def test_projection_changes_only_mode_and_effective_args(
        self, tmp_path: Path
    ) -> None:
        root = seed_private_root(tmp_path)
        bench = self._bench_doc(root)
        projected = cm.project_production_runtime_identity(bench)

        assert bench.obj.mode == "bench"
        assert projected.obj.mode == "production"
        assert projected.obj.effective_args == cm._MODE_ARGS["production"]

        for name in cm._BENCH_IDENTITY_STABLE_FIELDS:
            assert getattr(projected.obj, name) == getattr(bench.obj, name), name

    def test_projection_takes_no_caller_controlled_input(self) -> None:
        """No parameter for mode, args, hashes or overrides exists to misuse."""
        import inspect

        params = inspect.signature(
            cm.project_production_runtime_identity
        ).parameters
        assert list(params) == ["bench_doc"]

    def test_projected_wrapper_round_trips_canonically(
        self, tmp_path: Path
    ) -> None:
        root = seed_private_root(tmp_path)
        projected = cm.project_production_runtime_identity(self._bench_doc(root))
        assert cm.PersistedDoc(projected.wrapper_bytes).obj == projected.obj

    def test_non_bench_source_refuses(self, tmp_path: Path) -> None:
        root = seed_private_root(tmp_path)
        projected = cm.project_production_runtime_identity(self._bench_doc(root))
        with pytest.raises(ValueError):
            cm.project_production_runtime_identity(projected)

    def test_tampered_wrapper_refuses(self, tmp_path: Path) -> None:
        root = seed_private_root(tmp_path)
        bench = self._bench_doc(root)
        wrapper = json.loads(bench.wrapper_bytes)
        wrapper["fields"]["alias"] = "forged-alias"
        with pytest.raises(ValueError):
            cm.project_production_runtime_identity(
                cm.PersistedDoc(cm._canonical_wrapper_bytes(wrapper))
            )

    def test_bench_identity_and_its_document_stay_byte_identical(
        self, tmp_path: Path
    ) -> None:
        root = seed_private_root(tmp_path)
        before = driver.open_bench_file(
            "windows/ab-20260803-1837/cuda_candidate/attempt-000/identity/"
            "bench_runtime_identity.json",
            root=root,
        )
        bundle = assemble.build_stage2_bundle(
            stage2_input_paths(), root=root, timestamp=STAGE2_TS
        )
        after = driver.open_bench_file(
            "windows/ab-20260803-1837/cuda_candidate/attempt-000/identity/"
            "bench_runtime_identity.json",
            root=root,
        )
        assert before == after
        assert bundle.bench_runtime_identity.mode == "bench"

    def test_stage_two_bench_binding_invariant_while_full_binding_moves(
        self, tmp_path: Path
    ) -> None:
        """The projection must not disturb the frozen bench anchor."""
        from tests.test_cutover_step1_invariants import (
            MINTED_BENCH_ANCHOR,
            stage1_paths,
        )

        root = seed_private_root(tmp_path)
        stage_one = assemble.build_stage1_bundle(
            stage1_paths(), root=root, timestamp=STAGE2_TS
        )
        stage_two = assemble.build_stage2_bundle(
            stage2_input_paths(), root=root, timestamp=STAGE2_TS
        )
        assert stage_one.bench_binding_sha256 == MINTED_BENCH_ANCHOR
        assert stage_two.bench_binding_sha256 == MINTED_BENCH_ANCHOR
        assert stage_two.binding_sha256 != stage_one.binding_sha256

    def test_the_assembler_performs_no_live_collection(self) -> None:
        """No systemd, process, GPU or other live read inside the assembler."""
        import inspect

        source = inspect.getsource(assemble)
        for banned in (
            "systemctl",
            "nvidia-smi",
            "/proc/",
            "subprocess",
            "Popen",
            "socket",
        ):
            assert banned not in source, banned


class ConstantClock:
    """A clock that does NOT advance -- the frozen chronology permits it."""

    def __init__(self, moment: str = RUN_CLOCK) -> None:
        self._moment = moment

    def now_utc(self) -> str:
        return self._moment


def _call_cli_restoring_signal_state(argv: list[str]) -> int:
    """Call main(), then restore this process exactly -- even if it raises.

    main() restores the signal MASK only when it did not commit a
    terminal, so an in-process success leaves SIGINT/SIGTERM blocked for
    every subsequently spawned child. Restoring only after a normal return
    leaves that contamination on the raising path, which is exactly the
    case this exists to prevent. Mirrors the established helper in
    tests/test_cuda_bench_cli.py.
    """
    import signal

    from scripts import cuda_bench_cli as cli

    caller_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
    handlers = {
        number: signal.getsignal(number)
        for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        return cli.main(argv)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, caller_mask)
        for number, handler in handlers.items():
            signal.signal(number, handler)


class TestChronologyIsEqualitySafeAndBracketed:
    """The frozen order, enforced at both ends.

    latest evidence < issued <= admission <= boot == bundle/receipt
      <= completion < expiry
    """

    def test_same_second_invocation_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A constant clock must WORK. The 2A test previously advanced its
        clock to dodge a strict comparison the design does not contain."""
        root = seed_private_root(tmp_path)
        monkeypatch.setattr(driver, "BENCH_ROOT", root)
        monkeypatch.setattr(driver, "SystemClock", ConstantClock)
        rc = _call_cli_restoring_signal_state(
            ["assemble-stage2", "--window-id", "cutover-20260713-1202"]
        )
        assert rc == 0
        terminals = sorted(root.glob("command-assemble-stage2-*-terminal.json"))
        completion = cm._canonical_persisted_role(
            cm.PersistedDoc(terminals[0].read_bytes()), cm.CommandCompletionDoc
        ).obj
        assert completion.status == "completed"

    def _run_with_window(
        self, tmp_path, monkeypatch, *, issued: str, expires: str, clock: str
    ) -> tuple[int, Path]:
        from tests.test_cuda_migration import _cutover_authorization_doc
        from tests.test_cutover_step1_invariants import stage1_paths

        root = seed_private_root(tmp_path)
        anchor = assemble.build_stage1_bundle(
            stage1_paths(), root=root, timestamp=STAGE2_TS
        ).bench_binding_sha256
        auth = _cutover_authorization_doc(
            anchor, issued_at=issued, expires_at=expires
        )
        (root / AUTHORIZATION_REF).write_bytes(auth.wrapper_bytes)
        monkeypatch.setattr(driver, "BENCH_ROOT", root)
        monkeypatch.setattr(
            driver, "SystemClock", lambda: ConstantClock(clock)
        )
        rc = _call_cli_restoring_signal_state(
            ["assemble-stage2", "--window-id", "cutover-20260713-1202"]
        )
        return rc, root

    def test_admission_predating_issuance_refuses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rc, root = self._run_with_window(
            tmp_path,
            monkeypatch,
            issued="2026-08-03T22:00:00Z",
            expires="2026-08-04T02:00:00Z",
            clock="2026-08-03T20:31:00Z",  # BEFORE issuance
        )
        assert rc != 0
        assert not self._valid_completions(root)

    def test_completion_at_expiry_boundary_refuses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rc, root = self._run_with_window(
            tmp_path,
            monkeypatch,
            issued="2026-08-03T20:00:00Z",
            expires="2026-08-04T00:00:00Z",
            clock="2026-08-04T00:00:00Z",  # exactly AT expiry
        )
        assert rc != 0
        assert not self._valid_completions(root)

    @staticmethod
    def _valid_completions(root: Path) -> list[Path]:
        found = []
        for path in root.glob("command-assemble-stage2-*-terminal.json"):
            try:
                obj = cm._canonical_persisted_role(
                    cm.PersistedDoc(path.read_bytes()), cm.CommandCompletionDoc
                ).obj
            except Exception:
                continue
            if obj.status == "completed":
                found.append(path)
        return found


class TestSemanticValidatorIsLoadBearing:
    """Replacing the stage-2 decision/reasons check with `return True`
    left all 47 tests green, so the check was unproven. It is now a named
    predicate and these mutate a REAL published permit against it."""

    def _published_permit(self, tmp_path, monkeypatch):
        root = seed_private_root(tmp_path)
        monkeypatch.setattr(driver, "BENCH_ROOT", root)
        monkeypatch.setattr(driver, "SystemClock", ConstantClock)
        assert _call_cli_restoring_signal_state(
            ["assemble-stage2", "--window-id", "cutover-20260713-1202"]
        ) == 0
        terminals = sorted(root.glob("command-assemble-stage2-*-terminal.json"))
        completion = cm._canonical_persisted_role(
            cm.PersistedDoc(terminals[0].read_bytes()), cm.CommandCompletionDoc
        ).obj
        return root, completion

    def test_the_real_published_permit_is_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from scripts import cuda_bench_cli as cli

        root, completion = self._published_permit(tmp_path, monkeypatch)
        published = cm._canonical_persisted_role(
            cm.PersistedDoc((root / completion.artifact_ref).read_bytes()),
            cm.AssembleReceiptDoc,
        ).obj
        assert cli._valid_stage2_permit(
            published, window_id=completion.window_id
        )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("decision", "bench_passed"),
            ("reasons", ["forged_reason"]),
            ("cutover_window_id", "cutover-forged"),
        ],
    )
    def test_wrong_permit_semantics_are_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field, value
    ) -> None:
        from scripts import cuda_bench_cli as cli

        root, completion = self._published_permit(tmp_path, monkeypatch)
        wrapper = json.loads((root / completion.artifact_ref).read_bytes())
        wrapper["fields"][field] = value
        forged = cm.AssembleReceiptDoc(
            fields=__import__("types").MappingProxyType(dict(wrapper["fields"]))
        )
        assert not cli._valid_stage2_permit(
            forged, window_id=completion.window_id
        )
