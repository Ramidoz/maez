# CUDA A/B Bench Lean Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the dormant CUDA A/B bench with five inert commands that can collect honest measurements, assemble one genuine stage-1 evidence bundle, and return a scorer-bound verdict without performing any production mutation.

**Architecture:** Keep `cuda_bench_driver.py` as the sole measurement/process engine and `cuda_migration.py` as the sole verdict authority. Add a thin CLI for static observation, rehearsal, the two owner-window phases, and stage-1 assembly; add a measurement-free assembler that reads only owner-selected artifacts beneath the canonical private root and enters the existing public bundle scorer. The package ends at evidence, with rollback drill and cutover remaining separate owner-authorized acts.

**Tech Stack:** Python 3.14 dataclasses and protocols, pytest 9.1.1, Linux descriptor-walk private I/O, existing pidfd/memfd process lifecycle, `nvidia-smi`, `http.client`, systemd read-only queries, SHA-256 canonical JSON, ruff 0.15.12, and the completed clean-checkout worktree airlock.

---

## Execution lane and hard boundaries

**Codex builds; Claude gates.** Work only in
`/home/rohit/maez-wt-bench` on `feature/cuda-bench-driver`. Main remains
untouched until the final scoped merge gate.

- TDD is mandatory. Each task starts with the named failing tests, records the
  actual RED, then adds the minimum implementation.
- Before each commit, dispatch two fresh read-only reviewers: one against this
  plan/spec and one for correctness/privacy/authority boundaries. Resolve every
  finding in the same task.
- Direct runs with `/home/rohit/maez/.venv/bin/python` are useful RED/GREEN
  evidence but never certify a clean checkout. Tasks 1-9 are reviewed branch
  checkpoints, not independently certified slices: the current `AGENTS.md`
  does not yet authorize their changing test selections as certifying airlock
  targets. Claude reviews their source and direct evidence after each commit,
  but makes no clean-checkout certificate claim.
- No task may stop/start/restart/enable/disable a service, load a model, use
  port 18080 outside mocked/synthetic tests, consume a real owner nonce, change
  the shared venv, touch a live model pointer, or write outside a temporary
  test root.
- Do not run the retired 9,500-test full-repo floor. It is not part of this
  closure and is known to crash the host interpreter under that stress.
- Task 10 first lands the dedicated tracked integration node and its matching
  `AGENTS.md` authority, commits that complete package, and only then runs the
  real airlock against the committed head. Any follow-up edit reopens Task 10
  and requires a new commit plus a fresh certificate. There is no post-gate
  straggler commit.

After every Task 1-9 commit, Claude performs a read-only source/diff review and
checks the direct RED/GREEN evidence without calling it a certificate. Task
10 gives the first complete shell form for the final, dedicated certifying
node. Its certificate's `git_head` must equal the detached committed head;
the shared `.pth` hash is checked before/after, and zero disposable-root,
process, or listener residue is required. A direct shared-venv GREEN never
substitutes for that final gate.

## File responsibility map

- Modify `scripts/cuda_migration.py`: truthful runtime-identity contract,
  durable rollback preimage, and missing persisted evidence decoders.
- Modify `scripts/cuda_bench_driver.py`: command publication,
  immutable-preimage I/O, stock rehearsal adapters, and tier-bounded
  `PhaseConfig`; retain all process, measurement, authorization, and private-I/O
  authority here.
- Create `scripts/cuda_bench_cli.py`: the exact five-command surface, fresh
  read-only static collector, terminal-output contract, and `PhaseConfig`
  construction.
- Create `scripts/cuda_bench_assemble.py`: owner-selected artifact loading,
  stage-1 summary/bundle reconstruction, and public scorer/receipt calls; no
  measurement or write authority.
- Modify `tests/test_cuda_migration.py`: scorer truth/preimage/decoder REDs.
- Modify `tests/test_cuda_bench_driver.py`: command publication,
  immutable-preimage I/O, stock rehearsal adapter, and tier-timeout REDs.
- Create `tests/test_cuda_bench_cli.py`: parser/output/preflight/rehearsal/phase
  command REDs.
- Create `tests/test_cuda_bench_assemble.py`: anchored selection, P1 bundle,
  scorer-route, and inertness REDs.
- Modify `tests/test_worktree_airlock_imports.py`: remove the retired floor
  inventory and prove the airlock still certifies after deletion.
- Modify `AGENTS.md`: name the dedicated lean integration selection as a
  legitimate certifying target.
- Modify the runbook/specs only where executable behavior changes; do not
  rewrite the historical record.
- Delete `scripts/dev/bench_baseline.py`,
  `scripts/dev/bench_report_plugin.py`, and `tests/test_bench_baseline.py` only
  in Task 10, after the lean integration node exists.

## Canonical values added by this plan

The rollback preimage is the following ordered tuple of pairs:

```python
FROZEN_ROLLBACK_MANIFEST_FIELDS = (
    ("unit_sha256", FROZEN_VULKAN_UNIT_SHA256),
    ("dropin_sha256", FROZEN_VULKAN_DROPIN_SHA256),
    ("runtime_sha256", FROZEN_VULKAN_RUNTIME_SHA256),
    ("library_manifest_sha256", FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256),
    ("model_sha256", FROZEN_MODEL_SHA256),
    ("model_bytes", FROZEN_MODEL_BYTES),
    ("alias", FROZEN_ALIAS),
    ("effective_args_sha256", FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256),
)
FROZEN_ROLLBACK_MANIFEST_SHA256 = (
    "4ccbadb4de46b8856bdc4fa130a52141784038693e0da0021205fbae3b7db3f2"
)
```

Canonical serialization is UTF-8 JSON with `ensure_ascii=False`, separators
`(',', ':')`, `allow_nan=False`, and no trailing newline. It is exactly 582
bytes. Committed code/docs are the durable source; static preflight also
creates or verifies an identical raw copy at
`preimages/rollback-manifest-<sha>.json` beneath the private root.

The frozen 39-row Vulkan library-manifest preimage has one exact recipe.
Represent a regular entry as
`{"path":relative_name,"type":"file","sha256":lowercase_sha256,"bytes":size}`
and a symlink entry as
`{"path":relative_name,"type":"symlink","target":literal_readlink_payload}`.
Sort rows by the relative filename's encoded bytes, then serialize the array
with `sort_keys=True`, `ensure_ascii=False`, compact separators `(',', ':')`,
`allow_nan=False`, UTF-8, and no trailing newline. A committed literal 39-row
fixture in `tests/test_cuda_migration.py` must independently recompute
`FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256`:

```python
FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256 = (
    "c04ba04862db3b558deecbcc2b8f923a1dc7bce830b74592dd9157b784c86dd2"
)
```

The reviewed CUDA candidate is pinned at all three identity planes:

```python
FROZEN_CUDA_SERVER_SHA256 = (
    "33abb514fdbf2d590447fb08d608b7cb8c89cfa6b7b639226ada5a178728360f"
)
FROZEN_CUDA_BACKEND_SHA256 = (
    "e46a6888eb1dd78e07a6c80522f13f17e3c3b60c6ab6fdb56718456ca91861a7"
)
FROZEN_CUDA_RUNTIME_MANIFEST_SHA256 = (
    "8989bfb2d7bda18c8493973a6356e3d2912eb8bc85ce64d8130859134a7310bd"
)
```

All three are required. A different candidate that is internally
self-consistent but differs at any pinned plane refuses; it cannot inherit the
frozen b9596 identity.

`cuda_bench_driver.command_completion.v1` is active schema 24. Its fields are
exactly `command`, positive `ordinal`, bounded `window_id` or null,
`admission_ref`, `admission_sha256`, `artifact_ref`, `artifact_sha256`,
`artifact_schema`, `status="completed"`, and `timestamp`. Its production
matrix is closed:

| command | artifact_schema | phase | window_id |
|---|---|---|---|
| `static-preflight` | `cuda_bench_driver.static_preflight.v1` | null | null |
| `vulkan-baseline` | `cuda_bench_driver.phase_packet.v2` | `vulkan_baseline` | equals packet |
| `cuda-candidate` | `cuda_bench_driver.phase_packet.v2` | `cuda_candidate` | equals packet |

`rehearse` remains incompatibly rehearsal-encoded and never mints a production
completion. `assemble-stage1` emits its existing scorer-bound receipt, not a
command completion.

The truthful CMake validator is exactly:

```python
_CMAKE_VERSION_RE = re.compile(
    r"(?:3\.\d{1,2}\.\d{1,3}|4\.\d{1,2}\.\d{1,3})\Z"
)
```

`cuda_compiler` and `cmake_version` report fresh host observations. They are
not proof of which tools built the already-hashed candidate.

### Task 0: Reconfirm the isolated execution floor

**Files:**
- Read: `docs/superpowers/specs/2026-07-20-cuda-bench-lean-closure-design.md`
- Read: `docs/runbooks/llama-b9596-cuda-migration.md`
- Read: `scripts/cuda_migration.py`
- Read: `scripts/cuda_bench_driver.py`

- [ ] **Step 1: Verify branch, worktree, and current cleanliness**

Run:

```bash
set -euo pipefail
test "$(git -C /home/rohit/maez-wt-bench branch --show-current)" = feature/cuda-bench-driver
test "$(git -C /home/rohit/maez rev-parse HEAD)" = 1b2ddb242343487983687b59cf3c9814a88d6aa5
test -z "$(git -C /home/rohit/maez-wt-bench status --porcelain)"
```

Expected: all commands exit 0. If the feature head advanced through an
owner-gated docs commit, update only the expected feature head in the handoff;
never reset or clean unrelated work.

- [ ] **Step 2: Dispatch the independent Explore pass before code**

The agent must return exact source anchors for:

```text
RuntimeIdentity validators and persisted registry
StaticPreflightDoc constructor and phase preimage loader
open_bench_file/write_private_file/artifact policies
sealed production/rehearsal factories and run_phase
PhasePacket/BenchSummary/BenchEvidenceBundle constructors
evaluate_promotion_bundle/build_receipt
airlock certifier entrypoint and tracked-selector grammar
```

Expected: a read-only map handed to every task implementer. No commit.

### Task 1: Accept truthful host identity and freeze a reproducible rollback preimage

**Files:**
- Modify: `scripts/cuda_migration.py:24-63,995-1200`
- Modify: `tests/test_cuda_migration.py:90-140,2200-2420`
- Verify: `docs/runbooks/llama-b9596-cuda-migration.md`
- Verify: `docs/superpowers/specs/2026-07-20-cuda-bench-lean-closure-design.md`

- [ ] **Step 1: Write the runtime-truth and preimage REDs**

Add `import hashlib` beside the existing stdlib imports, then add tests with
these exact assertions:

```python
def test_runtime_identity_accepts_true_bounded_cmake_4(self):
    direct = replace(make_identity(), cmake_version="4.2.3")
    self.assertEqual(direct.cmake_version, "4.2.3")
    factory = make_identity(cmake_version="4.2.3")
    self.assertEqual(factory.cmake_version, "4.2.3")


def test_runtime_identity_rejects_unbounded_cmake(self):
    for value in (
        "2.99.999", "5.0.0", "4.123.1", "4.1.1234",
        "4.2", "4.2.3.4", "latest", True,
    ):
        with self.subTest(value=value):
            with self.assertRaisesRegex(ValueError, "runtime_identity_mismatch"):
                make_identity(cmake_version=value)


def test_rollback_manifest_preimage_is_durable_and_recomputable(self):
    encoded = json.dumps(
        [list(row) for row in cm.FROZEN_ROLLBACK_MANIFEST_FIELDS],
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    self.assertEqual(len(encoded), 582)
    self.assertEqual(encoded, cm.frozen_rollback_manifest_preimage())
    self.assertEqual(
        hashlib.sha256(encoded).hexdigest(),
        "4ccbadb4de46b8856bdc4fa130a52141784038693e0da0021205fbae3b7db3f2",
    )
    self.assertEqual(
        cm.FROZEN_ROLLBACK_MANIFEST_SHA256,
        hashlib.sha256(encoded).hexdigest(),
    )


def test_runtime_identity_requires_reproducible_rollback_manifest(self):
    with self.assertRaisesRegex(ValueError, "runtime_identity_mismatch"):
        make_identity(rollback_manifest_sha256=SHA_A)
```

Add a documentation assertion that both the runbook and lean spec contain the
exact sentence:

```text
cuda_compiler and cmake_version are fresh static-preflight host observations.
They are not retroactive build provenance.
```

- [ ] **Step 2: Run the tests and witness RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_migration.py \
  -k 'bounded_cmake or rollback_manifest_preimage or reproducible_rollback'
```

Expected: FAIL because `4.2.3` is rejected and the frozen preimage symbols do
not exist.

- [ ] **Step 3: Implement one validator and one durable preimage**

Add this shape and use it in both `RuntimeIdentity.__post_init__` and
`RuntimeIdentity.from_static_evidence`:

```python
_CMAKE_VERSION_RE = re.compile(
    r"(?:3\.\d{1,2}\.\d{1,3}|4\.\d{1,2}\.\d{1,3})\Z"
)


def frozen_rollback_manifest_preimage() -> bytes:
    return json.dumps(
        [list(row) for row in FROZEN_ROLLBACK_MANIFEST_FIELDS],
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
```

Both constructors must require:

```python
if (
    type(self.cmake_version) is not str
    or _CMAKE_VERSION_RE.fullmatch(self.cmake_version) is None
    or self.rollback_manifest_sha256 != FROZEN_ROLLBACK_MANIFEST_SHA256
):
    raise ValueError("runtime_identity_mismatch")
```

Update the existing module-level `make_identity(**overrides)` fixture's
`rollback_manifest_sha256` default to
`cm.FROZEN_ROLLBACK_MANIFEST_SHA256`, then update every other valid fixture to
the same value; arbitrary 64-hex values are no longer valid identity.

- [ ] **Step 4: Run GREEN and the complete scorer suite**

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q tests/test_cuda_migration.py
/home/rohit/maez/.venv/bin/ruff check scripts/cuda_migration.py tests/test_cuda_migration.py
```

Expected: complete file PASS; ruff exits 0.

- [ ] **Step 5: Review, commit, and hand to the branch checkpoint gate**

Commit only the two implementation files; the docs were atomically amended
with this plan before implementation:

```bash
git add scripts/cuda_migration.py tests/test_cuda_migration.py
git commit -m "fix(bench): accept truthful static runtime identity" \
  -m "The bounded runtime contract now accepts observed CMake 4.x and binds a committed, reproducible rollback-manifest preimage." \
  -m "## Predicted effect

A truthful host observation of CMake 4.2.3 constructs RuntimeIdentity unchanged; any rollback input drift changes or invalidates the frozen manifest identity."
```

Expected: Claude accepts the reviewed checkpoint and its direct evidence
without claiming an airlock certificate. Final certification waits for Task
10's dedicated authorized node.

### Task 2: Decode the two external stage-1 evidence documents

**Files:**
- Modify: `scripts/cuda_migration.py:2480-2870`
- Modify: `tests/test_cuda_migration.py:2280-2720`

- [ ] **Step 1: Write persisted round-trip REDs**

Add:

```python
def test_quality_evidence_persisted_round_trip(self):
    quality = cm.QualityEvidence(
        evaluator_version="grounding_judge.v3",
        control_manifest_sha256=SHA_A,
        candidate_manifest_sha256=SHA_B,
        false_absence_count=0,
        wrong_answered_ungrounded_count=0,
        type_regression_count=0,
        recall_posture="pass",
        quality_failure_count=0,
        covered_turn_count=21,
        timestamp="2026-07-13T12:00:00Z",
    )
    fields = {
        name: getattr(quality, name)
        for name in _QUALITY_EVIDENCE_FIELDS_FOR_TEST
    }
    wrapper = self.wrapper(cm.QUALITY_EVIDENCE_SCHEMA, quality, fields)
    persisted = cm.PersistedDoc(wrapper)
    self.assertIs(type(persisted.obj), cm.QualityEvidence)
    self.assertEqual(persisted.obj, quality)


def test_owner_voice_review_persisted_round_trip(self):
    review = cm.OwnerVoiceReview(
        producer="owner_human",
        status="pass",
        evaluator_version="owner_voice.v1",
        control_manifest_sha256=SHA_A,
        candidate_manifest_sha256=SHA_B,
        artifact_sha256=SHA_C,
        timestamp="2026-07-13T12:00:00Z",
    )
    fields = {
        name: getattr(review, name)
        for name in _OWNER_VOICE_REVIEW_FIELDS_FOR_TEST
    }
    persisted = cm.PersistedDoc(
        self.wrapper(cm.OWNER_VOICE_REVIEW_SCHEMA, review, fields)
    )
    self.assertIs(type(persisted.obj), cm.OwnerVoiceReview)
    self.assertEqual(persisted.obj, review)
```

Define `_QUALITY_EVIDENCE_FIELDS_FOR_TEST` and
`_OWNER_VOICE_REVIEW_FIELDS_FOR_TEST` beside the existing
`PersistedDocTests.wrapper` helper with exactly the field names shown in
Step 3. For each wrapper, remove one field, add one field, and alter one bound
value; each must raise `ValueError("persisted_roundtrip")`.

- [ ] **Step 2: Witness RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_migration.py \
  -k 'quality_evidence_persisted or owner_voice_review_persisted'
```

Expected: FAIL with `persisted_schema_unknown`.

- [ ] **Step 3: Add exact-field decoders and registry entries**

Implement:

```python
_QUALITY_EVIDENCE_FIELDS = (
    "evaluator_version", "control_manifest_sha256",
    "candidate_manifest_sha256", "false_absence_count",
    "wrong_answered_ungrounded_count", "type_regression_count",
    "recall_posture", "quality_failure_count", "covered_turn_count",
    "timestamp",
)
_OWNER_VOICE_REVIEW_FIELDS = (
    "producer", "status", "evaluator_version",
    "control_manifest_sha256", "candidate_manifest_sha256",
    "artifact_sha256", "timestamp",
)


def _decode_quality_evidence(fields: object) -> QualityEvidence:
    return QualityEvidence(**_persisted_fields(fields, _QUALITY_EVIDENCE_FIELDS))


def _decode_owner_voice_review(fields: object) -> OwnerVoiceReview:
    return OwnerVoiceReview(
        **_persisted_fields(fields, _OWNER_VOICE_REVIEW_FIELDS)
    )
```

Map `QUALITY_EVIDENCE_SCHEMA` and `OWNER_VOICE_REVIEW_SCHEMA` to those
decoders in `_PERSISTED_REGISTRY`. This closes decoder coverage; it does not
add schemas, so the count remains 22 at this task. Task 3 then adds the honest
command-admission family and raises the active count to 23; Task 4 adds the
closed command-completion family and raises the final package count to 24.

- [ ] **Step 4: GREEN, review, and commit**

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q tests/test_cuda_migration.py
/home/rohit/maez/.venv/bin/ruff check scripts/cuda_migration.py tests/test_cuda_migration.py
```

Commit:

```bash
git add scripts/cuda_migration.py tests/test_cuda_migration.py
git commit -m "feat(bench): decode external stage-one evidence" \
  -m "Quality and owner-voice wrapper bytes now reconstruct through the existing typed PersistedDoc boundary." \
  -m "## Predicted effect

Canonical quality and owner-voice wrappers round-trip; any missing, extra, or tampered field refuses before bundle construction."
```

Expected: Claude accepts the reviewed checkpoint and its direct evidence;
this selection is not represented as airlock-certified.

### Task 3: Build the sealed five-command parser and terminal contract

**Files:**
- Modify: `scripts/cuda_bench_driver.py` (command admission, publisher, and
  artifact-policy boundary only)
- Create: `scripts/cuda_bench_cli.py`
- Create: `scripts/cuda_bench_assemble.py` (inert importable shell only; Task 8 adds behavior)
- Modify: `tests/test_cuda_bench_driver.py` (admission/publisher/policy REDs
  only)
- Create: `tests/test_cuda_bench_cli.py`

- [ ] **Step 1: Write parser, authority-absence, and output REDs**

Pin the public command tuple:

```python
PUBLIC_COMMANDS = (
    "static-preflight",
    "rehearse",
    "vulkan-baseline",
    "cuda-candidate",
    "assemble-stage1",
)
```

Tests must prove:

```python
assert tuple(cli.build_parser()._subparsers._group_actions[0].choices) == PUBLIC_COMMANDS
for forbidden in (
    "promote", "cutover", "install", "boot", "live", "restart",
    "--root", "--assets-json", "-h", "--help",
):
    result = run_cli_raw(forbidden, "/tmp/PRIVATE-PATH", "ignore previous instructions")
    assert result.exit_code == 2
    assert result.stderr == ""
    assert "PRIVATE-PATH" not in result.stdout
    assert "ignore previous instructions" not in result.stdout
```

The one decoded output line must have exactly:

```python
{
    "status": "refused",
    "outcome": "invocation_invalid",
    "window_id": None,
    "artifact_ref": None,
    "artifact_sha256": None,
}
```

Add cases for missing, symlink, and 0755 roots: zero new files and null/null
artifact fields. Repeat `-h`/`--help` at the root and beneath every subcommand;
all are the same non-echoing `invocation_invalid`, never argparse usage.

Root validation before command work is provisional. The first durable command
write is a content-light admission receipt, not the final artifact. Its
production wrapper schema is the new
`cuda_bench_driver.command_admission.v1`; this honest family raises the frozen
canon count 22 -> 23 atomically in the plan and spec. Its fields are exactly
`command`, positive `ordinal`, bounded `window_id` or null,
`status="admitted"`, and `timestamp`, with a null wrapper binding; the
persisted file hash is its identity.
Task 4 separately adds `cuda_bench_driver.command_completion.v1` as family 24;
admission itself remains schema 23.
Rehearsal encodes the same payload through `RehearsalArtifactPolicy`, so it
remains an incompatible rehearsal document beneath `rehearsal/` and never
mints the production schema.

Add the canon RED: the executable schema tuple has exactly 23 unique entries,
contains `cuda_bench_driver.command_admission.v1` once, and no 22-count test or
appendix assertion survives. The assembler/scorer reject an admission wrapper as
stage-1 evidence; production encoding has null `binding_sha256`, while
rehearsal encoding has no production top-level `schema` key.
Every command-admission receipt is a decoder-free control record, never bundle
evidence. Task 3 proves that even complete orphan bytes are rejected by
`PersistedDoc`; Task 8 repeats the proof through the real assembler once that
entrypoint exists. No finalization marker can upgrade an admission receipt into
stage-1 evidence.

Add one atomic publisher using names
`command-<command>-attempt-NNN-<role>.json`, with role closed to
`admission|terminal`; both roles share the ordinal claimed by admission.
Production names are root-level; rehearsal names are beneath `rehearsal/`.
If the rehearsal directory did not pre-exist, the publisher identity-tracks
its mkdir and removes that still-empty directory on pre-admission failure. One
held root descriptor governs anonymous-file write/fsync, ordinal selection,
atomic link, parent fsync, anchored reopen, and hash verification. Only a true
`EEXIST` advances the ordinal. Factor the existing `_allocate_attempt`
disk-scan/claim loop into one shared primitive used by both phase attempts and
command attempts, parameterized only by their closed name shape and starting
ordinal. The command form scans persisted command-attempt names and selects
`max(persisted ordinal) + 1`, starting at 1, so a slot left by an uncatchable
prior process is never resumed or reused after restart. No second allocator or
process-local counter may become an ordinal authority. A fixed/timestamp name
or retry after any other error is forbidden.

Block SIGINT and SIGTERM across the admission transaction before the link and
restore the prior mask only after either (a) reopen+hash has linearized
admission, latched its immutable `CommandAttempt`, and made that exact binding
available to the outer signal scope, or (b) identity-proven cleanup plus parent
fsync has restored the pre-admission tree. RED injects each signal at link,
parent-fsync, reopen, hash, and mask-restoration boundaries: a catchable signal
before linearization leaves the tree unchanged/null-null only when cleanup
completes; after linearization the pending signal yields 130/143 and binds the
exact latched admission receipt.

Admission linearizes only after the admission receipt is reopened and hashed.
A disappearing/replaced root, link/fsync/reopen/hash failure before that point
leaves the full private bench-root tree unchanged only when identity-proven
unlink and cleanup parent-fsync complete. Injected unlink or cleanup-fsync
failure emits `failed`/`cleanup_incomplete` with null artifact fields and never
claims the tree was unchanged. An uncatchable SIGKILL, process death, or power
loss after link may leave a complete content-light orphan and no terminal line.
That orphan remains structurally inadmissible: its null-binding command schema
has no decoder or assembler role, it cannot reconstruct a `CommandAttempt`, and
the next process advances past its disk ordinal. This honest private-bench-root
limit does not weaken the production byte-identical guarantee: the five
commands have no unit, override, model-pointer, or runtime-asset mutation path.
After admission, all outcomes emit a non-null pair: normally the final
phase/rehearsal/command artifact, or the admission receipt itself if any later
auxiliary/terminal publication fails. Add the load-bearing RED that publishes
admission, writes one auxiliary file, injects final-publication failure, and
proves the terminal line binds the admission receipt rather than emitting
null/null or inventing a second artifact. Same-clock sequential and concurrent
invocations must retain distinct admission and terminal artifacts. A
`status="ok"` result may never cite the admission receipt; success requires
the actual final artifact. No absolute
path, authorization literal, environment value, prompt/response, usage string,
or traceback may appear on either stream.

Pin CLI return codes independently of prose: admitted `status="ok"` is 0;
pre-parse `invocation_invalid` is 2; any other `status="refused"` is 3; and
`status="failed"` is 4. SIGINT and SIGTERM interruptions return 130 and 143
respectively when the interrupted outcome can be emitted honestly; a signal
whose required pre-admission cleanup fails instead remains
`failed`/`cleanup_incomplete` with exit 4. No refused/failed command may print a
valid terminal object and exit zero. RED every command across its
ok/refused/failed shape while preserving exactly one terminal line.

Install a CLI-only signal scope for both SIGINT and SIGTERM. It raises a
private command-interruption exception caught at the outer boundary; library
loaders still do not catch `BaseException`. Before admission it emits the
content-light null/null interrupted line only after successful identity-proven
cleanup; cleanup failure emits `failed`/`cleanup_incomplete` instead. After
admission it binds the admission receipt. Mid-command signal REDs for
static-preflight, rehearsal pre-run, and assembly prove one line, the
signal-specific honest exit status, no traceback/path/literal,
finalizer/cleanup where a child existed, no residue, and unchanged shared
`.pth`.

Make terminal emission itself a signal-linearized transaction and add REDs at
all three boundaries: before the terminal write, while the stdout write is in
progress, and after the bytes are committed but before the old mask is
restored. The handler must never print. `_commit_terminal(...)` blocks both
signals, snapshots pending INT/TERM (SIGTERM wins if both are pending), chooses
one result plus its closed exit code, serializes exactly one canonical
newline-terminated JSON record, and writes it through fd 1 while signals stay
blocked. It then marks the terminal committed before restoring the mask; a
later-delivered pending signal is a no-op and cannot append an interrupted
line. A signal observed before the snapshot selects the one interrupted line
and 130/143. Use fd-level capture in the tests. Assert one complete line and a
matching exit code at every injection point, never normal-line/signal-exit,
signal-line/normal-exit, two lines, or a partial second line.

Add binding REDs for the crash-honesty amendment:

- kill a subprocess after full admission content has been linked but before
  reopen/hash linearization; prove no terminal line is fabricated, the complete
  orphan refuses at `PersistedDoc`, and no in-memory attempt can be recovered;
- start a new allocator against that root and prove disk scan-max-plus-one
  advances beyond the orphan instead of reusing its ordinal, and a structural
  RED proves phase and command allocation call the same shared disk allocator;
- inject identity-unlink and cleanup-parent-fsync failures and prove
  `failed`/`cleanup_incomplete` with null artifact fields, never an unchanged
  tree claim; and
- deliver SIGINT/SIGTERM during mask restoration and prove the interrupted
  terminal line cites the exact admission pair latched before unmasking.

- [ ] **Step 2: Witness RED**

Run:

```bash
set +e
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_cli.py \
  -k 'parser or terminal or admission or output or exit_status or signal or authority_absence'
cli_red_rc=$?
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_driver.py \
  -k 'command_artifact or command_admission'
driver_red_rc=$?
set -e
test "$cli_red_rc" -eq 2
test "$driver_red_rc" -eq 1
```

Expected: CLI collection exits 2 because `scripts.cuda_bench_cli` is absent;
the driver REDs run independently and exit 1 because the command publisher and
admission policy do not exist.

- [ ] **Step 3: Implement the non-echoing parser and sole terminal emitter**

Use this exact public shape:

```python
@dataclass(frozen=True, slots=True)
class TerminalResult:
    status: Literal["ok", "refused", "failed"]
    outcome: str
    window_id: str | None
    artifact_ref: str | None
    artifact_sha256: str | None

    def __post_init__(self) -> None:
        if self.status not in {"ok", "refused", "failed"}:
            raise ValueError("terminal_status")
        if type(self.outcome) is not str or re.fullmatch(
            r"[a-z][a-z0-9_]{0,63}", self.outcome
        ) is None:
            raise ValueError("terminal_outcome")
        if (self.artifact_ref is None) != (self.artifact_sha256 is None):
            raise ValueError("terminal_artifact_pair")
        if self.window_id is not None and re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.:+-]{0,127}", self.window_id
        ) is None:
            raise ValueError("terminal_window_id")
        if self.artifact_ref is not None:
            parts = self.artifact_ref.split("/")
            if os.path.isabs(self.artifact_ref) or any(
                part in {"", ".", ".."} for part in parts
            ):
                raise ValueError("terminal_artifact_pair")
            if re.fullmatch(r"[0-9a-f]{64}", self.artifact_sha256 or "") is None:
                raise ValueError("terminal_artifact_pair")


class NonEchoingParser(argparse.ArgumentParser):
    def error(self, _message: str) -> Never:
        raise InvocationRefusal


def _terminal_bytes(result: TerminalResult) -> bytes:
    return (
        json.dumps(asdict(result), sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
```

Construct the root parser and every subparser with `add_help=False`; no parser
inherits argparse's implicit help action. `main(argv)` catches parse refusal
before root admission, emits the fixed `invocation_invalid` object, and
returns 2. It validates the root, publishes and retains the admission binding,
then invokes the selected handler. Every post-admission success/refusal/failure
commits the final artifact binding when available and otherwise the admission
binding through the sole `_commit_terminal` boundary. Catch ordinary
`Exception` separately from the two explicit signal
exceptions; do not catch arbitrary `BaseException`. A top-level exception
becomes content-light without exception text. The parser has no
root/assets/environment override and implements the frozen exit-code mapping
above.

The public `main(argv)` always supplies `driver.BENCH_ROOT`. Tests inject a
temporary `root=` only into private command handlers below argparse; neither
the parser nor environment exposes an alternate evidence root. The pure
assembler's explicit `root=` remains a testable library boundary, not a CLI
selection mechanism.

Add immutable `CommandAttempt(command, ordinal, admission_ref,
admission_sha256, namespace)` and
`publish_command_artifact(attempt, role, encoded, *, root)` to the driver's
existing private-I/O boundary. `namespace` is exactly `""` for production or
`"rehearsal"` for rehearsal and is carried by the attempt. The admission
allocator is the only constructor. Direct terminal publication without its
token refuses. Publication returns
`(relative_ref, file_sha256)` only after the durability/reopen proof above.
Extend both artifact policies with kind `command_admission`; production emits
the new schema and rehearsal retains its incompatible top-level shape. The
new schema and decoder-free private receipt are added to the frozen appendix;
no scorer registry entry is needed because it never enters a bundle.

All file reads and writes retain the existing anchored per-open discipline:
canonical 0700 owner root, descriptor walk, `O_NOFOLLOW`, regular owner-only
0600 final files, and no alternate root/CLI override. The CommandAttempt is a
publication-order token, not a new filesystem authority. Deliberate same-owner
rename/unlink/replacement after admission remains explicitly outside this lean
threat model, as the design states; no RED or claim suggests command-long
namespace locking.

Create `scripts/cuda_bench_assemble.py` in the same task with only its module
docstring and `from __future__ import annotations`; defer every assembler
import until Task 8, when it is used. This is an explicit branch-only scaffold,
not a released half-feature: no assembler API
or canonical CLI path exists yet, Tasks 1-9 are uncertified checkpoints, and
Task 4 may exercise package hashing only against temporary roots. No
`static-preflight` artifact from this intermediate identity may be admitted to
the canonical bench root. Tasks 8-9 replace the scaffold completely before
the sole certifying Task-10 commit. It has no function, writer, provider, or
side effect.

Make the owner surface executable with exactly:

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

Subprocess smoke REDs invoke `sys.executable -B -m scripts.cuda_bench_cli` for
module-entry and parse/pre-admission invalid cases only; public `main` is
canon-root-only, so a subprocess test must not invent a tmp-root flag.
Valid/refused/failed paths use the explicit private below-argparse handler seam
in-process with a temporary root. Together they assert the closed exit
mapping, exactly one stdout JSON line, empty stderr, and no usage, traceback,
absolute path, or rejected literal. This avoids both a canonical-root write
and the airlock tripwire's forbidden shared-interpreter path literal.

- [ ] **Step 4: GREEN, structural review, and commit**

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q tests/test_cuda_bench_cli.py
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_driver.py -k 'command_artifact'
/home/rohit/maez/.venv/bin/python -B -m pytest -q tests/test_cuda_bench_driver.py
/home/rohit/maez/.venv/bin/ruff check \
  scripts/cuda_bench_driver.py scripts/cuda_bench_cli.py \
  scripts/cuda_bench_assemble.py \
  tests/test_cuda_bench_driver.py tests/test_cuda_bench_cli.py
```

Commit:

```bash
git add scripts/cuda_bench_driver.py scripts/cuda_bench_cli.py \
  scripts/cuda_bench_assemble.py tests/test_cuda_bench_driver.py \
  tests/test_cuda_bench_cli.py
git commit -m "feat(bench): seal the lean command boundary" \
  -m "The CLI exposes only five inert commands and emits one non-echoing content-light terminal document with an all-or-none artifact binding." \
  -m "## Predicted effect

Malformed or pre-root invocations write nothing and emit null artifact fields; any root-admitted outcome emits exactly one private artifact binding without echoing rejected input. A killed process may leave only a decoder-free bench-root orphan, while production remains byte-identical."
```

### Task 4: Implement the single read-only static collector and `static-preflight`

**Files:**
- Modify: `scripts/cuda_migration.py` (frozen manifest recipe and candidate pins)
- Modify: `scripts/cuda_bench_driver.py` (immutable preimage I/O only)
- Modify: `scripts/cuda_bench_cli.py`
- Modify: `tests/test_cuda_migration.py` (literal manifest fixture and pin REDs)
- Modify: `tests/test_cuda_bench_driver.py` (immutable preimage REDs only)
- Modify: `tests/test_cuda_bench_cli.py`

- [ ] **Step 1: Write static-observation and manifest REDs**

Create exact internal types:

```python
@dataclass(frozen=True, slots=True)
class StaticAssetPaths:
    unit: Path
    dropin: Path
    vulkan_root: Path
    candidate_root: Path
    model: Path
    cuda_override: Path
    nvcc: Path
    cmake: Path
    nvidia_smi: Path
    flag_source: Path
    vision_unit: Path
    stub: Path


@dataclass(frozen=True, slots=True)
class StaticObservation:
    static_doc: cm.StaticPreflightDoc
    runtime_identity: cm.RuntimeIdentity
    rollback_preimage: bytes


class ReadOnlyRunner(Protocol):
    def __call__(
        self, argv: tuple[str, ...], *, timeout_s: int
    ) -> subprocess.CompletedProcess[str]:
        pass
```

The production path set is exact:

```python
CANONICAL_STATIC_ASSETS = StaticAssetPaths(
    unit=Path("/home/rohit/.config/systemd/user/llama-server.service"),
    dropin=Path(
        "/home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf"
    ),
    vulkan_root=cm.VULKAN_RELEASE_ROOT,
    candidate_root=cm.CUDA_RELEASE_ROOT,
    model=Path(cm.FROZEN_MODEL_PATH),
    cuda_override=Path(
        "/home/rohit/maez/config/systemd/llama-server-b9596-cuda.override.conf"
    ),
    nvcc=Path("/usr/local/cuda-13.2/bin/nvcc"),
    cmake=Path("/usr/bin/cmake"),
    nvidia_smi=Path("/usr/bin/nvidia-smi"),
    flag_source=driver.SCREEN_FLAG_SOURCE_PATH,
    vision_unit=driver.VISION_UNIT_PATH,
    stub=Path("/home/rohit/maez/scripts/cuda_bench_stub.py"),
)
```

RED families:

- candidate manifest rows are tab-separated `F sha bytes relative` or
  `L target_sha relative target`, strictly ordered, unique, flat, and free of
  control characters;
- each F row's hash/size matches the same stable no-follow regular asset; an L
  row's `target_sha` is exactly
  `sha256(os.fsencode(os.readlink(path))).hexdigest()` over the literal link
  payload, not the referent bytes, with lstat-before/readlink/lstat-after
  identity stability; a RED distinguishes the real literal-target hash from
  the referent-file hash; every L target is one relative in-root name with no
  absolute/`..`/control component and its finite, acyclic chain terminates at a
  verified listed F row (external, cyclic, dangling, or unlisted chains
  refuse); `runtime-manifest.sha256` itself is the sole permitted
  unlisted top-level control file (a manifest cannot list its own final hash);
  every other unlisted top-level asset refuses;
- `library_hashes` contains only verified F `lib*.so*`, includes
  `libggml-cuda.so`, and excludes all L rows; any Vulkan backend refuses;
- the candidate server, verified regular `libggml-cuda.so`, and complete
  runtime-manifest hashes equal the three frozen CUDA pins; a different
  self-consistent runtime whose rows and self-manifest all verify still
  refuses and cannot inherit the frozen identity;
- exact one-GPU output is accepted; zero/two rows is `gpu_scope_violation`;
  UUID enumeration is one absolute `/usr/bin/nvidia-smi` invocation, and every
  subsequent metadata query uses the absolute binary and includes
  `-i <uuid>`;
- only the absolute pinned nvcc and CMake binaries may be invoked; `nvcc`
  parses only `release 13.2, V13.2.<1-3 digits>`, while CMake parses the
  literal first line `cmake version 4.2.3` and never substitutes 3.x;
- the committed exact 39-entry Vulkan fixture uses regular
  `{path,type:"file",sha256,bytes}` and symlink
  `{path,type:"symlink",target}` rows, relative-filename byte ordering, and
  compact sorted-key UTF-8 JSON with `ensure_ascii=False`,
  `allow_nan=False`, and no newline; it reproduces
  `c04ba04862db3b558deecbcc2b8f923a1dc7bce830b74592dd9157b784c86dd2`;
- any change to unit, drop-in, Vulkan runtime/library manifest, model
  hash/bytes, alias, or args changes/refuses the rollback preimage;
- the 582-byte raw preimage is created once at the content-addressed relative
  path, reopened on later runs, and refuses if existing bytes differ; true
  EEXIST is distinguished from post-link/fsync failure, and both the file and
  parent directory have a witnessed durability barrier;
- only an admitted `static-preflight` may create the `preimages/` directory,
  using anchored `mkdirat` at mode 0700 followed by bench-root fsync and
  reopen/identity validation; an exact valid existing directory is accepted,
  while symlink, wrong mode/owner, mkdir failure, fsync failure, or identity
  substitution refuses; phase verification with `preimages/` absent refuses
  and never creates or repairs it;
- five-file package identity uses the ordered compact pair array; member,
  order, or byte drift changes it;
- `static-preflight` performs no service mutation, socket contact, model load,
  or corpus inference and enforces exactly one GPU.
- `CommandCompletionDoc` accepts only the frozen static matrix row and refuses
  wrong command/schema/phase/window, non-completed status, or any admission or
  artifact mismatch. Direct `BenchEvidenceBundle` construction without the
  required completion preimages refuses; callers cannot bypass this by
  entering the public constructor directly.

Write the immutable-create/EEXIST/fsync/path-hazard RED family in
`tests/test_cuda_bench_driver.py` before either helper exists. It covers the
new-file and exact-existing-file branches, ordering proof, mismatched bytes,
symlink/hardlink/mode/owner/path substitution, and every injected durability
failure named in Step 3. Both helpers must reopen the command-admission receipt
under the exact supplied root and command namespace before acting; add REDs
for a `CommandAttempt` admitted under root A being presented under root B, and
for its admission receipt being deleted or replaced. No in-memory attempt
alone is sufficient authority.

- [ ] **Step 2: Witness RED**

Run:

```bash
set +e
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_migration.py \
  -k 'vulkan_library_manifest_recipe or frozen_cuda_candidate'
migration_red_rc=$?
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_cli.py \
  -k 'static_preflight or runtime_manifest or host_observation or rollback_preimage or driver_package'
cli_red_rc=$?
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_driver.py \
  -k 'publish_or_verify_immutable or verify_existing_immutable'
driver_red_rc=$?
set -e
test "$migration_red_rc" -eq 1
test "$cli_red_rc" -eq 1
test "$driver_red_rc" -eq 1
```

Expected: FAIL because the frozen manifest/candidate constants, collector,
command, and immutable preimage helpers do not exist.

- [ ] **Step 3: Implement one collector used by preflight and phases**

Use this internal interface only; tests inject fixtures below argparse:

```python
def collect_static_observation(
    *,
    root: Path = driver.BENCH_ROOT,
    paths: StaticAssetPaths = CANONICAL_STATIC_ASSETS,
    runner: ReadOnlyRunner = _run_read_only,
    clock: driver.Clock,
) -> StaticObservation:
    corpus = _validate_frozen_corpus(root=root)
    assets = _collect_static_asset_hashes(paths)
    candidate = _verify_candidate_runtime_manifest(paths.candidate_root)
    host = _collect_host_tool_observations(runner=runner, paths=paths)
    rollback_preimage = _build_rollback_preimage(assets)
    package_sha256 = _driver_package_sha256()
    identity = _build_runtime_identity(
        mode="bench",
        assets=assets,
        candidate=candidate,
        host=host,
        rollback_preimage=rollback_preimage,
    )
    static_doc = _build_static_preflight_doc(
        corpus=corpus,
        assets=assets,
        candidate=candidate,
        host=host,
        package_sha256=package_sha256,
        timestamp=clock.now_utc(),
    )
    return StaticObservation(static_doc, identity, rollback_preimage)
```

The implementation must:

1. read the canonical corpus through `open_bench_file`, require mode/size 285,
   frozen hash, and exactly seven nonempty JSON strings;
2. stably verify unit/drop-in/Vulkan/model/candidate/stub/flag/unit inputs;
3. validate every candidate manifest row before selecting regular libraries,
   permit exactly the self-manifest `runtime-manifest.sha256` outside those
   rows, refuse any second unlisted top-level entry, and enforce the server,
   CUDA backend, and runtime-manifest frozen hashes even when a substitute is
   internally self-consistent;
4. query exactly one GPU through absolute `/usr/bin/nvidia-smi`, then scope
   every absolute-binary GPU metadata query to that UUID with `-i <uuid>`;
5. parse truthful nvcc/CMake output into `RuntimeIdentity`;
6. recompute the 39-row Vulkan manifest from the frozen row/serialization
   recipe and recompute the raw rollback preimage without writing it;
7. hash the exact five package files in frozen order; and
8. return `StaticPreflightDoc` plus the complete identity from the same
   observation.

`collect_static_observation` is one pure read-only collector. Persistence is a
separate policy step. Only the `static-preflight` handler, after its command
admission receipt is durable, calls
`publish_or_verify_immutable(relative, bytes, attempt=attempt, root=root)`.
Both phase handlers call `verify_existing_immutable(...)` instead; absence or
drift refuses before `run_phase`, nonce consumption, attempt allocation, or
any phase write. Only that admitted static-preflight handler may create a
missing `preimages/` directory. It does so by anchored `mkdirat` at 0700,
fsyncs the bench-root directory, and reopens and identity-validates the child
before publication. An exact existing directory is validated and reused.
Phase helpers are verify-only: they refuse an absent or invalid directory and
never create, chmod, chown, replace, or repair it.

Implement `publish_or_verify_immutable(...)` and
`verify_existing_immutable(...)` in the driver's existing descriptor-walk I/O
boundary now, after their REDs. They accept the admitted `CommandAttempt` as
an ordering proof only after reopening and verifying that attempt's admission
receipt under the exact explicit `root=` and expected command namespace. The
root remains the existing testable library seam, but an attempt admitted under
another root, or one whose admission receipt was deleted or replaced, refuses;
neither helper may run before admission.

The immutable publisher is implemented in this task beside the descriptor-walk
I/O. Its sequence is: anonymous write -> file fsync -> direct link. Only a
`FileExistsError` from that exact link enters the existing-file branch; no
broad `filesystem_hazard` catch may reopen and accept. A new link requires
parent fsync plus path/inode revalidation before success. An existing file
requires anchored no-follow regular/owner/0600/single-link validation, stable
exact-byte read, file fsync, parent fsync, and a second identity check. Any
other link error, unstable identity, mismatch, or file/parent fsync failure
refuses that invocation and is never reinterpreted as idempotence. Existing
content is never overwritten or unlinked; no alternate path is tried.

REDs inject: first-create file-fsync-before-link and parent-fsync-after-link;
true EEXIST with exact bytes (both durability syncs observed); mismatch,
symlink, hardlink, wrong owner/mode, and path substitution; existing-file
fsync failure; existing-parent fsync failure; and, load-bearing, a post-link
parent-fsync failure that leaves matching bytes but still refuses rather than
entering the EEXIST branch. A structural RED forbids the broad
catch/reopen-and-accept pattern.

The static handler's transaction boundary is explicit: admission is durable
before first-run preimage publication. If the preimage succeeds and terminal
publication is then injected to fail, the durable preimage remains (it is a
canonical reproducibility asset, not an unpublished temporary), and the one
terminal line refuses with the admission ref/hash. It never emits null/null,
rolls back a proven durable preimage, or writes a fallback terminal elsewhere.

The lean collector always constructs mode `bench`; it has no production-mode
or cutover branch. The production constants use absolute canonical paths. `subprocess.run` is
allowed only in the injected read-only runner, with a sanitized environment,
fixed absolute argv[0], `shell=False`, bounded timeout, and captured output
that is never included in a refusal. GPU UUID enumeration occurs once through
absolute `/usr/bin/nvidia-smi`; every metadata invocation uses that same
absolute binary with `-i <uuid>`. nvcc and CMake likewise use only their
bounded absolute canonical paths.

- [ ] **Step 4: Persist `static_preflight.v1` and emit its binding**

Encode with `ProductionArtifactPolicy().encode("static_preflight", fields)`.
The handler order is admission -> collect -> publish-or-verify rollback
preimage -> publish `static_preflight.v1` -> publish
`command_completion.v1` -> publish terminal. Completion may linearize only
after the underlying static document has completed file fsync, final-name
link, parent fsync, anchored reopen, and hash validation. It cites that
validated artifact plus the exact admission pair. Publish the terminal with
the completion's relative path/hash and emit `static_preflight_ready`. A
catchable failure before completion reports honestly; an uncatchable death
after the underlying artifact but before completion is a safe false negative:
the static document may exist, but cannot enter a bundle and no completed
claim is fabricated. The command validates tool observations; complete
identities are persisted later by `run_phase`.
No canonical-root command is run during this branch checkpoint: tests inject
temporary roots. The scaffold assembler therefore never escapes as a durable
canonical package identity before Tasks 8-9 complete it.

- [ ] **Step 5: GREEN, review, and commit**

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_migration.py tests/test_cuda_bench_driver.py \
  tests/test_cuda_bench_cli.py
/home/rohit/maez/.venv/bin/ruff check \
  scripts/cuda_migration.py scripts/cuda_bench_driver.py \
  scripts/cuda_bench_cli.py tests/test_cuda_migration.py \
  tests/test_cuda_bench_driver.py tests/test_cuda_bench_cli.py
```

Commit:

```bash
git add scripts/cuda_bench_driver.py scripts/cuda_bench_cli.py \
  scripts/cuda_migration.py tests/test_cuda_migration.py \
  tests/test_cuda_bench_driver.py tests/test_cuda_bench_cli.py
git commit -m "feat(bench): collect truthful static preflight evidence" \
  -m "One read-only collector verifies the pinned candidate, reproducible incumbent manifest, host tools, single GPU, package identity, and durable rollback preimage without claiming build provenance." \
  -m "## Predicted effect

The host's CMake 4.2.3 and the exact three-plane CUDA candidate reach RuntimeIdentity unchanged; any substitute candidate, manifest/preimage drift, cross-root admission, or absent phase preimage directory refuses before a phase can consume authority."
```

### Task 5: Make the stock rehearsal provider set handle real child identity

**Files:**
- Modify: `scripts/cuda_bench_driver.py:4090-4270,4660-4870`
- Modify: `tests/test_cuda_bench_driver.py:7300-7700`

- [ ] **Step 1: Write dynamic-PID/map and ephemeral-port REDs**

Add tests proving:

```python
ports = driver.RehearsalPortRegistry()
maps = driver.SyntheticBackendMap(
    {}, default_maps_text=VALID_VULKAN_MAPS
)
assert maps.read_maps(123456) == VALID_VULKAN_MAPS

probe = driver.SyntheticPortProbe(
    {8080, 8081, 8082, 18080},
    rehearsal_ports=ports,
)
assert probe.is_free(8080) is True          # synthetic, no socket call
generation = ports.reserve_launch()
lease = ports.activate_from_launcher(generation, dynamic_stub_port)
assert probe.is_free(lease.port, lease=lease) is False  # literal loopback only
assert ports.current == lease
```

Invalid map text, bool/nonpositive PID, non-loopback/dynamic fixed-port
contact, unregistered arbitrary non-fixed port, concurrent registration while
a generation is active, a stale lease (including same-number reuse under a
new generation), and mixed-tier adapter construction must refuse before any
socket call (monkeypatch `socket.socket` construction to make that absence
observable).
`RehearsalServerLauncher` and `SyntheticPortProbe` must hold the
same registry object by identity; a structurally equal distinct registry is
`tier_mismatch`. The load-bearing RED runs three independently OS-assigned
ephemeral leases: cycle 1 registers, finalizer observes its exact lease free
and retires it; cycles 2 and 3 repeat with strictly increasing generations.
Numeric port distinctness is intentionally not claimed because port-zero
allocation may honestly reuse a number. The stock phase completes all three
and leaves no current lease/listener. No test monkeypatches
`read_maps` or `is_free`. Residue proof enumerates same-UID `/proc/*/exe` and
`/proc/*/fd/*` for `memfd:cuda-bench-entry`; it does not rely on a stub-name
`pgrep`, because the sealed launcher replaces argv/path identity with the
memfd handle.

`ProviderWitness` has two independent exact integer counters. `real_calls`
means production/external-surface contact and remains exactly zero for every
synthetic provider. `loopback_kernel_calls` means only the sanctioned
literal-loopback kernel binds used to prove ephemeral-listener absence. Both
reject booleans and negative values. `assert_no_real_calls()` checks only the
production/external counter and therefore remains true after sanctioned
loopback probes. The implementation must never sum, alias, or otherwise
conflate the dimensions. Canonical witness serialization and its binding hash
carry both independently; exact round-trip preserves both, and changing only
`loopback_kernel_calls` changes the binding or makes a supplied binding
refuse. RED each validation leg, both assertion directions, exact
round-trip/tamper behavior, and a structural scan across scorer, bundle, and
witness surfaces proving no sum or conflation path.

- [ ] **Step 2: Witness RED**

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_driver.py \
  -k 'stock_rehearsal or dynamic_pid or ephemeral_port'
```

Expected: FAIL because static adapters cannot observe the runtime PID/port.

- [ ] **Step 3: Extend the exact sealed rehearsal adapter types**

Keep the exact adapter type seal (`SyntheticPortProbe` and
`SyntheticBackendMap`). Extend `SyntheticBackendMap.__init__` with the
keyword-only `default_maps_text: str | None = None`. It copies and validates
the existing PID map exactly as today, additionally requires the default to be
`None` or a string whose `cm.parse_backend_maps` succeeds, and preserves every
existing positional call. `read_maps` rejects bool/nonpositive PIDs, selects
the exact PID row or the frozen default, revalidates it with
`cm.parse_backend_maps`, and otherwise raises `provider_uncertain`.

Add frozen process-memory-only
`RehearsalPortLease(generation: int, port: int)` and a
`RehearsalPortRegistry` with a lock, monotonic generation counter, and at most
one reserved-or-active generation. Only
`RehearsalServerLauncher` calls `reserve_launch() -> generation` before spawn;
a concurrent reservation or active generation refuses before any child exists.
The launcher passes a rehearsal-only callback into `spawn_pinned`. After the
stub announcement and target identity are proven, but before `OwnedChild`
escapes bootstrap ownership, that callback calls
`activate_from_launcher(generation, port) -> RehearsalPortLease`. The exact
lease is stored on `OwnedChild` and threaded through `finalize` into
`SyntheticPortProbe.is_free(port, *, lease=...)`. Fixed production/bench port
checks remain lease-free and wholly synthetic.

Extend `spawn_pinned` with an optional private post-identity callback, validated
before the executable snapshot/spawn and permitted only for rehearsal
`python_file` pins. Invoke it inside the existing try/`_bootstrap_abort` scope.
A callback failure therefore kills/reaps the pidfd-owned child and proves
listener absence before raising. Activation validates everything before one
atomic, non-throwing state mutation; otherwise cancellation is exact for both
reserved and active generations. The launcher catches `BaseException` and
cancels the exact unescaped generation on every spawn/callback failure.
Production rejects a callback structurally and its behavior is unchanged.
After cleanup, the same numeric port may be issued again only under a new
lease generation.
`SyntheticPortProbe` receives the shared registry through keyword-only
`rehearsal_ports`; existing fixed-port tests may omit it, in which case every
non-fixed port refuses.

For 8080/8081/8082/18080 the probe returns only configured synthetic answers.
The configured set is closed to exactly those four ports; no arbitrary fixed
port can become synthetic. For the one exact current launcher-issued lease the
probe snapshots registry state under the lock, releases the lock, performs a
literal `socket.bind(("127.0.0.1", lease.port))`, then reacquires the lock and
compare-before-retires that exact lease. No registry lock is held across bind.
A failed bind reports occupied without changing registry state. A successful
bind proves listener absence and retires only if the same lease is still
current. A stale lease, including an old generation whose numeric port has
been reused, refuses before socket construction and cannot inspect or retire
the current lease. Arbitrary non-fixed ports refuse before socket construction.
No hostname, proxy, or production-service contact exists. The synthetic
provider witness increments only `loopback_kernel_calls` for this
literal-loopback bind, honestly recording the sanctioned kernel contact while
`real_calls` remains exactly zero and continues to mean zero
production/external-surface contact. Registry/lease state is bounded process
memory and is never serialized.

Add optional `rehearsal_ports` to `RehearsalServerLauncher` for direct legacy
tests. Extend `_sealed_tier`, not `rehearsal_tier`, to require by object
identity that a sealed rehearsal launcher and probe both carry the same
non-null registry. The landed `rehearsal_tier(...)` remains only the sealed
caller-supplied aggregator. Task 6's `_rehearsal_providers` is the sole stock
constructor: it creates one registry and passes that same object to both
adapters. RED a contested reservation (no spawn), injected activation failure
(bootstrap abort leaves no child/listener), and a successful three-generation
phase.

- [ ] **Step 4: GREEN, residue proof, review, and commit**

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_driver.py \
  -k 'rehearsal or backend_map or port_probe or cleanup or memfd_residue'
/home/rohit/maez/.venv/bin/python -B -m pytest -q tests/test_cuda_bench_driver.py
/home/rohit/maez/.venv/bin/ruff check \
  scripts/cuda_bench_driver.py tests/test_cuda_bench_driver.py
memfd_count=0
for link in /proc/[0-9]*/exe /proc/[0-9]*/fd/*; do
  case "$(readlink "$link" 2>/dev/null || true)" in
    *memfd:cuda-bench-entry*) memfd_count=$((memfd_count + 1)) ;;
  esac
done
test "$memfd_count" -eq 0
! ss -ltnH 'sport = :18080' | grep -q .
```

Commit:

```bash
git add scripts/cuda_bench_driver.py tests/test_cuda_bench_driver.py
git commit -m "fix(bench): close stock rehearsal identity seams" \
  -m "Rehearsal now binds unpredictable child PIDs and verifies its real ephemeral listener cleanup without contacting fixed production ports." \
  -m "## Predicted effect

A stock healthy rehearsal completes without per-test monkeypatching, then leaves no stub process or listener; fixed production-port answers remain synthetic."
```

### Task 6: Wire the full-fidelity `rehearse` command

**Files:**
- Modify: `scripts/cuda_bench_driver.py`
- Modify: `scripts/cuda_bench_cli.py`
- Modify: `tests/test_cuda_bench_driver.py`
- Modify: `tests/test_cuda_bench_cli.py`
- Modify: `tests/test_cuda_bench_stub.py`

- [ ] **Step 1: Write all-persona rehearsal REDs**

Parametrize the six frozen stub personas through the actual CLI and retained
state machine:

```python
@pytest.mark.parametrize(
    ("persona", "outcome"),
    [
        ("healthy", "completed"),
        ("readiness_timeout", "readiness_timeout"),
        ("midturn_hang", "http_timeout"),
        ("crash", "crash"),
        ("malformed_response", "malformed_response"),
        ("wrong_identity", "alias_mismatch"),
    ],
)
def test_rehearse_runs_stock_state_machine_and_cleans_up(
    cli_harness, persona, outcome
):
    before = cli_harness.tree_snapshot()
    production_before = cli_harness.production_schema_paths()
    result = cli_harness.run(
        "rehearse",
        "--static-preflight",
        cli_harness.static_preflight_ref,
        "--persona",
        persona,
    )
    assert result.terminal["outcome"] == outcome
    assert result.port != 18080
    assert cli_harness.marker_snapshot() == ()
    assert all(path.startswith("rehearsal/") for path in result.new_paths)
    assert cli_harness.production_schema_paths() == production_before
    assert cli_harness.tree_snapshot() >= before
    assert cli_harness.stub_pids() == ()
    assert cli_harness.listener_ports() == ()
```

For every case assert: selected static-preflight wrapper only; no corpus/model
read; ephemeral port is not 18080; marker directory unchanged; all new files
are below `rehearsal/`; the pre-existing owner-selected production preflight
is unchanged and no **new** production schema occurs; no listener/process/PGID
remains; terminal ref/hash is valid and points to an incompatible rehearsal
document. Record wall time around the full six-persona parameter set and
require it below 15 seconds on the local test host; no test may monkeypatch a
module timeout constant or sleep. The healthy case must record three distinct
sequential launcher-port generations and retire all three.

This six-persona family is a direct, **non-certifying** compatibility witness.
It must also prove zero sealed-memfd and artifact residue. The current airlock
aborts the whole run when the first sealed-memfd descendant cannot initialize;
that is whole-run abort behavior, not a per-test refusal. Task 6 does not add
or alter an airlock exemption. The lifecycle-fixture/whole-run-abort debt
remains explicit and unchanged.

Before implementation, add tier-bound timeout REDs: a production
`PhaseConfig` with readiness below the frozen 300 seconds and a rehearsal
config above five seconds each refuse `tier_mismatch`; no CLI flag or
environment variable can override either tier. The real `readiness_timeout`
and `midturn_hang` personas must finish within the same wall-time bound without
monkeypatching a module timeout constant or sleep.

- [ ] **Step 2: Witness RED**

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_driver.py \
  tests/test_cuda_bench_cli.py tests/test_cuda_bench_stub.py \
  -k 'rehearse or persona or timeout_bound'
```

Expected: FAIL because the CLI command is not wired and the driver does not
yet enforce the tier-bounded readiness field.

- [ ] **Step 3: Build the stock sealed provider set**

`_rehearsal_providers` must construct the real sealed factory with:

```text
SyntheticServiceState(inactive)
SyntheticPortProbe(fixed synthetic answers + dynamic ephemeral probe)
SyntheticGpu(one UUID, empty inventories, fixed memory sequence)
SyntheticKernelLog(clean cursors/counters)
SyntheticBackendMap(default Vulkan-only frozen map)
RehearsalServerLauncher(pinned stub, 127.0.0.1:0, shared port registry)
LoopbackServerClient(same RehearsalClock object)
RehearsalAuthorizationGate(same RehearsalArtifactPolicy object)
SyntheticContainmentProvider(same clock and port probe)
RehearsalJournalFactory
```

`_rehearsal_providers` creates one `RehearsalPortRegistry` and passes that
same object to the launcher and probe before calling the landed
`rehearsal_tier(...)` aggregator. The aggregator constructs nothing; its
`_sealed_tier` identity check merely proves the supplied pair shares the
registry.

Add `readiness_timeout_s: float = READINESS_TIMEOUT_S` as the final backward-
compatible `PhaseConfig` field. `run_phase` uses that field for the readiness
deadline. Production providers require it to equal the frozen 300 seconds;
rehearsal requires `0 < value <= 5`. Define
`REHEARSAL_READINESS_TIMEOUT_S = 1.0` and
`REHEARSAL_REQUEST_TIMEOUT_MS = 1_000` in the CLI's private rehearsal
construction only. Build `LoopbackServerClient.rehearsal` with the latter.
Production clients/configs retain exactly 30,000 ms/300 s; no public flag or
environment variable can override either tier. Make the already-witnessed
tier-bound and real-persona REDs green without a global monkeypatch.

Use exactly seven constant sentinel prompts. Mint only the rehearsal in-memory
authorization shape; the real marker directory must remain untouched. Call
`run_phase` once and derive the terminal outcome from the persisted rehearsal
document, never from response literals.

Rehearsal opens the owner-selected `static_preflight.v1` wrapper, then uses a
rehearsal-only identity collector that verifies its candidate-manifest,
package, GPU, and fresh tool observations while taking model hash/bytes and
rollback identity only from frozen committed constants. It must not call the
production collector path that opens `corpus.json` or model bytes. The
resulting identity fields are valid typed inputs to the shared state machine,
not promotion-eligible evidence because every emitted wrapper remains in the
incompatible rehearsal schema.

- [ ] **Step 4: GREEN, residue proof, review, and commit**

Task 6 airlock review covers only its non-spawning surfaces: CLI
parsing/allowlist, tier timeout bounds, provider construction and tier/registry
sealing, static-preflight selection without corpus/model reads, marker/schema
isolation, and content-light terminal handling. The real six-persona spawned
stub family remains direct non-certifying evidence with strict
process/listener/PGID/memfd/artifact residue checks.

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_driver.py tests/test_cuda_bench_stub.py tests/test_cuda_bench_cli.py
/home/rohit/maez/.venv/bin/ruff check \
  scripts/cuda_bench_driver.py scripts/cuda_bench_stub.py scripts/cuda_bench_cli.py \
  tests/test_cuda_bench_driver.py tests/test_cuda_bench_stub.py tests/test_cuda_bench_cli.py
memfd_count=0
for link in /proc/[0-9]*/exe /proc/[0-9]*/fd/*; do
  case "$(readlink "$link" 2>/dev/null || true)" in
    *memfd:cuda-bench-entry*) memfd_count=$((memfd_count + 1)) ;;
  esac
done
test "$memfd_count" -eq 0
! ss -ltnH 'sport = :18080' | grep -q .
```

Commit:

```bash
git add scripts/cuda_bench_driver.py scripts/cuda_bench_cli.py \
  tests/test_cuda_bench_driver.py tests/test_cuda_bench_cli.py \
  tests/test_cuda_bench_stub.py
git commit -m "feat(bench): expose full-fidelity rehearsal" \
  -m "The online-safe rehearsal command drives all stub personas through the retained state machine using sentinel-only, marker-free evidence." \
  -m "## Predicted effect

Healthy rehearsal completes on an ephemeral loopback port; every failure persona exits with its typed content-light outcome and no listener or process residue."
```

### Task 7: Wire the two production measurement commands without mutation authority

**Files:**
- Modify: `scripts/cuda_bench_cli.py`
- Modify: `tests/test_cuda_bench_cli.py`

#### User-ratified Task-7 closure amendments (2026-07-24)

These amendments are part of Task 7, not later assembler work:

1. **Bind admission to the selected phase window.** Before `_run_command`
   creates a command admission, it anchored-opens and parses the selected
   `WindowAuthorization` for Vulkan or `Continuation` for CUDA. The exact
   parsed `window_id` is threaded into `_admit_command`; `None` or any later
   phase/config mismatch refuses. A pre-admission path/parse failure emits a
   null artifact pair, creates zero artifacts, and never burns the nonce.
   RED decodes both admissions and proves their exact selected window.
2. **Use one durable-success latch for every durable producer.** Generalize
   the existing static-only latch for static, Vulkan, and CUDA rather than
   adding a second phase latch. Success becomes authoritative only in the
   `on_committed` callback after file fsync, final-name link, parent fsync,
   anchored reopen, and exact identity/hash validation. A signal before link
   yields interrupted with no completion. A signal after that durable
   validation yields success for either phase.
3. **Compare the complete retained static schema except observation time.**
   Compare `gpu_uuid`, `driver_package_sha256`, `stub_sha256`,
   `corpus_verified`, and the full `checks` mapping. The selected document's
   timestamp and the fresh timestamp must each pass their schema's structural
   validation, but timestamp is the sole field excluded from equality. Any
   non-timestamp mutation refuses.
4. **Keep one frozen-corpus parser.** `_load_frozen_prompts` delegates to the
   existing frozen-corpus validator; it does not implement a second parser or
   structural checker. The validated loader returns the seven strings in the
   exact persisted order and preserves deliberate duplicates. RED includes a
   duplicate-bearing corpus in exact order and a structural proof that there
   is one validator implementation.
5. **Classify reduced phase artifacts strictly.** A binding-valid reduced
   artifact with `spawned:false` is a pre-spawn `refused` terminal; one with
   `spawned:true` is a spawned `failed` terminal. Neither mints a command
   completion. Malformed, schema-wrong, phase/window-mismatched, or otherwise
   binding-invalid reduced artifacts fail closed and cannot be consumed as
   complete. Task 7 proves no completion is minted and that `PersistedDoc` or
   completed-packet decode refuses; it does not implement the Task-8
   assembler.

The exact retained static equality fields are therefore `gpu_uuid`,
`driver_package_sha256`, `stub_sha256`, `corpus_verified`, and the complete
`checks` mapping. `timestamp` is excluded only from equality, never from
structural validation. The non-spawning parser/config/provider surfaces remain
airlock-certifiable. Phase-spawning paths require a direct witness with
intrinsic module-origin pinning and process/listener/artifact residue proof;
there is no airlock exemption.

- [ ] **Step 1: Write exact `PhaseConfig` and refusal-order REDs**

For `vulkan-baseline`, require relative window-authorization, static-preflight,
static-admission, and static-completion refs. For `cuda-candidate`, require
relative continuation, parent-window, completed Vulkan packet, its matching
Vulkan command-admission and command-completion refs, plus the same
static-preflight/admission/completion refs. A completion is never accepted
without the exact admission preimage it cites; a durable underlying artifact
without its completion is not a completed producer result.

The parser surface is exact. Vulkan accepts only `--window-authorization`,
`--static-preflight`, `--static-admission`, and `--static-completion`. CUDA
accepts only `--continuation`, `--parent-window`, `--parent-packet`,
`--parent-admission`, `--parent-completion`, and the same three static refs.
Neither phase exposes root, port, timeout, model, corpus, environment, or
mutation switches.

Tests assert:

```python
assert config.argv == [str(expected_runtime), *FROZEN_BENCH_ARGV_TAIL]
assert config.env == dict(driver._PHASE_BENCH_ENVIRONMENTS[phase])
assert config.expected_port == 18080
assert config.readiness_timeout_s == driver.READINESS_TIMEOUT_S
assert config.window_id == parsed_authorization.window_id
assert config.boot_id == current_boot_id
assert config.bench_identity_fields == config.runtime_identity_fields
assert config.prompts == tuple(json.loads(exact_frozen_corpus_bytes))
```

Capture the completed packet and assert
`packet.order_sha256 == cm.FROZEN_ORDER_SHA256`. The loader must preserve the
seven strings in their exact JSON-array order; sorting, set conversion,
normalization, or a separate order claim is forbidden. The retained
`static_preflight.v1` has no prompt-order field and is not widened.

The static collector is called fresh once per command. The re-derived
`StaticPreflightDoc` fields must equal the selected persisted document on the
fields that schema actually carries (GPU UUID, package/corpus/candidate and
incumbent checks). The fresh collector timestamp is not an identity field and
is not compared to the older receipt timestamp; the phase artifacts record
their own later observation timestamps.
Compiler and CMake are deliberately not in retained
`static_preflight.v1`: each is freshly observed, bounded, and placed in the
complete phase identity without inventing an unavailable historical
comparison. Candidate manifest/library drift changes a carried static check
and therefore refuses. Config/artifact window, boot, owner, parent packet, failed/rehearsal
packet, static identity, active service/port/GPU, and continuation expiry
failures must call neither `consume` nor `spawn`. Ambient environment canaries
must not enter the exact phase environment.

Add completion REDs for both phase rows in the frozen matrix. A phase
completion is published only after the packet's file fsync, final-name link,
parent fsync, anchored reopen, and hash validation, and must join the packet's
phase/window plus the exact command admission. A wrong/missing static
completion refuses both phases; a wrong/missing Vulkan completion refuses CUDA
before nonce consumption. Crash after packet durability but before completion
produces no completion and is an honest safe false negative, never a fabricated
completed phase.

Both commands call the pure collector and then
`verify_existing_immutable` on the exact rollback preimage. Missing/drifted
preimage refuses; it is never created or repaired by a phase. A tree snapshot
RED proves the phase command creates zero new files beyond its already-durable
command-admission receipt before `run_phase`, and a preimage refusal leaves the
nonce unburned. The existing per-open anchored reader/writer remains the only
filesystem authority; no root override or fallback exists.

Add an AST plus behavioral authority RED over the new CLI: no mutating
systemctl verb literal or argv constructor exists; the only `"systemctl"`
literal reachable by production handlers remains the driver's whitelisted
read-only provider builder, and injected handlers cannot reach stop/start/
restart/enable/disable/install/pointer/override callbacks.

- [ ] **Step 2: Witness RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_cli.py \
  -k 'vulkan_baseline or cuda_candidate or phase_config or fresh_phase_identity or verify_existing or systemctl'
```

Expected: FAIL because the production command builders do not exist.

- [ ] **Step 3: Implement read-only provider/config factories**

Add pure helpers with these exact signatures:

- `_load_frozen_prompts(*, root: Path) -> tuple[str, ...]`
- `_read_boot_id() -> str`
- `_production_providers(phase: Literal["vulkan_baseline", "cuda_candidate"], identity: cm.RuntimeIdentity) -> driver.Providers`
- `_vulkan_config(args: argparse.Namespace, observation: StaticObservation) -> driver.PhaseConfig`
- `_cuda_config(args: argparse.Namespace, observation: StaticObservation) -> driver.PhaseConfig`

Every owner artifact is opened by the existing anchored reader. Use
`parse_window_authorization`, `parse_continuation`, and
`decode_persisted_packet`. Construct the exact sealed production providers;
all systemd use remains inside `RealServiceStateProvider`'s read-only command
builder. The command calls `run_phase` once. It does not stop/start/restart any
unit and cannot install an override.

The command handler receives the Task-3 `CommandAttempt`, verifies the existing
rollback preimage read-only, constructs `PhaseConfig` with the frozen production
readiness bound, and calls the retained
`run_phase(config, providers, root=root)`. The attempt stays at the CLI
boundary to order admission and select the terminal fallback; it does not
invent a second phase-engine root abstraction.

`run_phase` remains the authority for fresh six-gate revalidation,
containment-before, nonce consumption at the last no-spawn point, three-cycle
measurement, identity-document persistence, and pidfd cleanup.

After `run_phase` returns a completed persisted packet, the CLI anchored-opens
and validates that packet, then publishes the matching
`cuda_bench_driver.command_completion.v1` only after the packet's full
fsync/link/parent-fsync/reopen/hash sequence is proven. The terminal line binds
the completion document, not merely the packet. Refused or failed packets
never mint completion. CUDA additionally proves that its selected completed
Vulkan parent packet is the artifact named by a valid Vulkan completion with
the same window before continuation consumption.

Define the shared exact A/B argument tail in the CLI and assert its compact
JSON SHA-256 equals `FROZEN_BENCH_ARGS_SHA256`:

```python
FROZEN_BENCH_ARGV_TAIL = (
    "-m", cm.FROZEN_MODEL_PATH,
    "--alias", cm.FROZEN_ALIAS,
    "--host", "127.0.0.1",
    "--port", "18080",
    "--ctx-size", "40960",
    "--parallel", "1",
    "--n-gpu-layers", "999",
    "-fa", "on",
    "--cache-type-k", "q4_0",
    "--cache-type-v", "q4_0",
    "--spec-type", "draft-mtp",
    "--spec-draft-n-max", "3",
    "--kv-unified",
    "-fit", "off",
)
```

- [ ] **Step 4: GREEN, structural authority review, and commit**

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_driver.py tests/test_cuda_bench_cli.py
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_cli.py -k 'no_service_mutation or nonce_unburned or production_environment'
/home/rohit/maez/.venv/bin/ruff check \
  scripts/cuda_bench_driver.py scripts/cuda_bench_cli.py \
  tests/test_cuda_bench_driver.py tests/test_cuda_bench_cli.py
```

Commit:

```bash
git add scripts/cuda_bench_cli.py tests/test_cuda_bench_cli.py
git commit -m "feat(bench): expose owner-window measurement phases" \
  -m "The Vulkan and CUDA commands construct the retained phase engine from freshly observed identity and refuse unless production is already inactive." \
  -m "## Predicted effect

An active production service or mismatched artifact refuses before nonce consumption; an authorized offline phase calls run_phase once and still has no service-mutation capability."
```

### Task 8: Load owner-selected evidence and construct one genuine P1 bundle

**Files:**
- Modify: `scripts/cuda_bench_assemble.py`
- Create: `tests/test_cuda_bench_assemble.py`

- [ ] **Step 1: Write explicit-selection and anchored-path REDs**

Define the exact input surface:

```python
@dataclass(frozen=True, slots=True)
class Stage1ArtifactPaths:
    control_packet: str
    candidate_packet: str
    static_admission: str
    static_completion: str
    control_admission: str
    control_completion: str
    candidate_admission: str
    candidate_completion: str
    window_authorization: str
    continuation: str
    window_consumption: str
    continuation_consumption: str
    control_containment_before: str
    control_containment_after: str
    candidate_containment_before: str
    candidate_containment_after: str
    bench_identity: str
    runtime_identity: str
    static_preflight: str
    quality: str
    owner_voice: str
    rollback: str
```

Every field is required. Absolute, `..`, symlink component/final, hardlink,
directory, wrong owner/mode, missing file, unknown/rehearsal schema, and type
mismatch all refuse `assembly_refused` before scorer entry. Extra attempts and
decoys on disk are ignored; exactly those 22 paths are opened. An AST RED
forbids `glob`, `rglob`, `iterdir`, `scandir`, and raw `open`.
Pointing any **non-admission role** at a complete
`cuda_bench_driver.command_admission.v1` receipt must refuse
`assembly_refused` before scorer entry. The three admission roles require that
schema, but role-scoping does not admit a crash orphan: a selected admission
without its exact durable completion must still refuse `assembly_refused`.
Add one correct-role orphan RED per command and cross-role REDs for
static-as-Vulkan, Vulkan-as-CUDA, and CUDA-as-Vulkan. This is the
assembler-path half of Task 3's decoder-level orphan proof.

The three admissions and three completions are typed carried preimages, not
hash-only assertions. Each completion must cite its selected admission and
underlying artifact by exact relative ref/hash and satisfy the frozen
command/schema/phase/window matrix. A durable static document or phase packet
without its matching completion is unscorable. Direct construction of
`BenchEvidenceBundle` with a completion omitted, substituted, or forged must
refuse in `__post_init__`; assembler routing is not the only enforcement point.

- [ ] **Step 2: Witness RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_assemble.py \
  -k 'artifact_paths or anchored or explicit_selection or rehearsal_schema'
```

Expected: FAIL because `Stage1ArtifactPaths` and the typed loader do not exist.

- [ ] **Step 3: Implement typed loading through the existing boundary**

The assembler may import from the driver only:

```python
from scripts.cuda_bench_driver import (
    BenchRefusal,
    open_bench_file,
    parse_continuation,
    parse_window_authorization,
)
```

Decode packet, completion, containment, identity, static, quality, owner, and
rollback wrappers with `PersistedDoc` and an exact type check. Command
admission deliberately remains decoder-free as a standalone artifact; rebuild
its frozen fields only through the bundle's admission-preimage type, whose
file hash is recomputed from its canonical wrapper bytes. Convert the two
parsed driver authorization objects to
the existing `WindowAuthorizationDoc`/`ContinuationDoc`, but first require
each selected authorization wrapper to equal its compact, sorted-key,
single-newline canonical bytes exactly. Whitespace-only and key-order changes
to either wrapper refuse `assembly_refused`; semantically equivalent
noncanonical JSON cannot disappear during parsing. Map all malformed
bytes/path/type errors to `BenchRefusal("assembly_refused") from None`; do not
catch `KeyboardInterrupt`, `SystemExit`, or `BaseException`.

- [ ] **Step 4: Write P1 summary/bundle REDs**

Reconstruct each summary from `packet.summary_projection_json`,
`packet.cycle_metrics`, `packet.kernel_counters`, typed quality, typed owner
review, and rollback witness. Assert:

```python
assert cm.phase_summary_projection(summary) == json.loads(
    packet.summary_projection_json
)
```

Containment order is Vulkan before/after, CUDA before/after, rollback
before/after. Later authorizations are exactly:

```python
boot = cm.AuthorizationWitness(
    "boot_authorization", "not_attempted", None, None, None
)
live = cm.AuthorizationWitness(
    "live_witness_authorization", "not_attempted", None, None, None
)
```

Cold/provisional maps/witnesses are `None`. Scalar authority comes from the
typed control packet, never duplicated literals. Production-mode current
identity, packet/doc mismatch, manifest mismatch, or rollback-parent mismatch
must fail in `BenchEvidenceBundle.__post_init__` before evaluator entry. The
assembler must emit containment in canonical Vulkan before/after, CUDA
before/after, rollback before/after order; test the emitted order directly.
Do **not** require the scorer to reject a permutation: `ContainmentWitness`
deliberately binds snapshots by `(phase, boundary)` rather than tuple order.

`Stage1ArtifactPaths` has no later-stage input fields. Assert that the built
bundle is the genuine P1 prefix (`boot`/`live` are `not_attempted`; cold and
provisional witnesses/maps are `None`). Do not recreate the superseded P2-P5
assembler tests; malformed-prefix refusal remains covered by the existing
scorer suite.

Add a selected-current-identity RED: mutate the runtime-identity wrapper while
leaving the bench wrapper untouched and prove bundle construction refuses.
Every one of the twenty-two selected artifacts must influence the result:
mutating its accepted canonical bytes or decoded typed value must either
change the bundle binding or refuse construction. Locator spelling is not
evidence identity—two owner-selected files with identical accepted canonical
bytes may produce identical evidence—but locator **safety** remains mandatory:
absolute, `..`, symlink component/final, hardlink, directory, wrong owner/mode,
missing, and root-escape paths all refuse.

Pin the participation plane for every field so none can be inert:

| Selected field(s) | Participating plane |
| --- | --- |
| `control_packet`, `candidate_packet` | `PersistedDoc` canonical file bytes/hash plus exact `PhasePacket` object |
| `static_admission`, `control_admission`, `candidate_admission` | canonical wrapper bytes/hash plus selected-ref, command, ordinal, window, and completion joins |
| `static_completion`, `control_completion`, `candidate_completion` | `PersistedDoc` canonical file bytes/hash plus exact `CommandCompletionDoc` object |
| `window_authorization`, `continuation` | canonical wrapper bytes required before parser; typed authorization preimage participates in packet/receipt/window/boot/owner/parent joins |
| `window_consumption`, `continuation_consumption` | `PersistedDoc` canonical file bytes/hash plus exact `ConsumptionReceipt` object |
| four A/B containment fields | `PersistedDoc` canonical file bytes/hash plus exact phase/boundary `ContainmentSnapshot` object |
| `bench_identity`, `runtime_identity` | `PersistedDoc` canonical file bytes/hash plus exact role-specific `RuntimeIdentity` object |
| `static_preflight` | `PersistedDoc` canonical file bytes/hash plus exact `StaticPreflightDoc` object |
| `quality` | `PersistedDoc` canonical file bytes/hash plus exact `QualityEvidence` object and summary joins |
| `owner_voice` | `PersistedDoc` canonical file bytes/hash plus exact `OwnerVoiceReview` object and summary joins |
| `rollback` | `PersistedDoc` canonical file bytes/hash plus exact `RollbackEvidenceBundle` object and parent/containment/kernel joins |

Add direct-constructor REDs proving no caller can omit a completion, swap its
admission/artifact preimage, or construct a bundle whose completion matrix
does not match the decoded static/packet phase and window. The three completion
document hashes enter `bench_binding_sha256`; authorizations and later
boot/live evidence may change the full binding but must not change that bench
anchor.

- [ ] **Step 5: Witness P1 RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_assemble.py \
  -k 'stage1_bundle or summary_mapping or canonical_containment_order or selected_current_identity'
```

Expected: FAIL because `build_stage1_bundle` does not exist.

- [ ] **Step 6: Implement `build_stage1_bundle`**

Use the exact signature
`build_stage1_bundle(paths: Stage1ArtifactPaths, *, root: Path, timestamp: str) -> cm.BenchEvidenceBundle`.

Pin the mapping to the already-working scorer fixture
`tests/test_cuda_migration.py::_summary_for_bundle_packet`:

- packet phase/cycles/kernel counters and projection values
  `seven_turn_max_ms`, `p95_e2e_ms`, `median_decode_tps`,
  `median_prefill_tps`, all four MTP fields, all four outcome counts, and
  `unload_leak_mib`;
- quality's five counts/posture fields;
- owner review as `PhaseEvidence("owner_voice_review", owner.status,
  owner.artifact_sha256, owner.timestamp)`;
- rollback witness from the typed rollback bundle; and
- `cold_boot_witness=None`, `provisional_live_witness=None`.

Assert the resulting `phase_summary_projection(summary)` exactly equals the
decoded packet projection. Construct `BenchEvidenceBundle` with the exact
field mapping used by `tests/test_cuda_migration.py::_make_bundle`: window,
boot, GPU, and driver-package scalars from the control packet; both summaries
and packets; the canonical six-snapshot containment witness; the two
`not_attempted` authorizations; bench/current identity both from the selected
bench/current identity documents; typed quality/owner/window/continuation/
consumption documents; the four base containment documents; each selected
identity wrapper in its corresponding persisted-doc role; typed static
preflight and rollback; persisted control/candidate packet preimages; all
three selected admission preimages and completion `PersistedDoc`s; both later
maps `None`; and the caller-supplied timestamp. Do not recreate join logic;
the existing constructor is the only join/P1 authority. Its validation joins
each completion to its admission and underlying artifact file bytes, enforces
the closed matrix, and includes the three completion file hashes in the
stage-stable `bench_binding_sha256`.

Because `PersistedDoc` carries bytes/hash/object but no selected locator, the
bundle also carries exactly three bounded relative string fields:
`static_preflight_ref`, `control_packet_ref`, and `candidate_packet_ref`.
These are compared to the corresponding completion's `artifact_ref`.
`CommandAdmissionPreimage` is a non-schema frozen carrier containing its
selected relative ref plus canonical wrapper bytes, recomputed file hash, and
frozen admission fields; it deliberately does not enter `_PERSISTED_REGISTRY`
or become standalone evidence. The assembler owns anchored-root validation of
all refs, while the bundle constructor owns their exact internal joins.

Pin the four identity assignments literally:

```python
bench_runtime_identity = bench_identity_doc.obj
runtime_identity = runtime_identity_doc.obj
bench_identity_doc = bench_identity_doc
runtime_identity_doc = runtime_identity_doc
```

Do not substitute the bench object/document into the current role or ignore
the selected runtime path. The existing constructor owns their P1 mode and
stable-field relationship.

- [ ] **Step 7: GREEN, inertness review, and commit**

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_migration.py tests/test_cuda_bench_assemble.py
/home/rohit/maez/.venv/bin/ruff check \
  scripts/cuda_migration.py scripts/cuda_bench_assemble.py \
  tests/test_cuda_migration.py tests/test_cuda_bench_assemble.py
```

Commit:

```bash
git add scripts/cuda_bench_assemble.py tests/test_cuda_bench_assemble.py
git commit -m "feat(bench): construct owner-selected stage-one bundle" \
  -m "The measurement-free assembler opens twenty-two explicit private artifacts and delegates every evidence join and P1-prefix check to BenchEvidenceBundle." \
  -m "## Predicted effect

A complete coherent stage-1 document set constructs one P1 bundle; any missing, escaped, rehearsal, tampered, or later-stage input refuses before scorer entry."
```

### Task 9: Enter the public scorer route and wire inert assembly output

**Files:**
- Modify: `scripts/cuda_bench_assemble.py`
- Modify: `scripts/cuda_bench_cli.py`
- Modify: `tests/test_cuda_bench_assemble.py`
- Modify: `tests/test_cuda_bench_cli.py`

- [ ] **Step 1: Write scorer-route and outcome REDs**

Pin the result type:

```python
@dataclass(frozen=True, slots=True)
class Stage1Evaluation:
    bundle: cm.BenchEvidenceBundle
    verdict: cm.PromotionVerdict
    receipt: Mapping[str, object]
```

A call-count wrapper must observe exactly the same bundle object twice: the
explicit evaluation, then `build_receipt`'s revalidation. Passing evidence
yields `bench_passed`; a coherent gate failure yields scorer-minted
`keep_vulkan`; structural/missing evidence calls neither evaluator nor receipt
builder and produces no verdict. Receipt bindings must equal the bundle's full
and stage-stable bench hashes.

AST/import REDs forbid the assembler from referencing `_evaluate_promotion_gate`,
providers, `run_phase`, launcher, subprocess, socket, HTTP, GPU, kernel log,
journal, systemd, service mutation, or a filesystem writer.

- [ ] **Step 2: Witness RED**

Run:

```bash
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_assemble.py \
  -k 'public_scorer or call_count or bench_passed or keep_vulkan or structural'
```

Expected: FAIL because `assemble_stage1` does not exist.

- [ ] **Step 3: Implement only the existing public route**

```python
def assemble_stage1(
    paths: Stage1ArtifactPaths,
    *,
    root: Path,
    timestamp: str,
) -> Stage1Evaluation:
    bundle = build_stage1_bundle(paths, root=root, timestamp=timestamp)
    verdict = cm.evaluate_promotion_bundle(bundle)
    receipt = cm.build_receipt(bundle, verdict, timestamp=timestamp)
    return Stage1Evaluation(
        bundle=bundle,
        verdict=verdict,
        receipt=MappingProxyType(dict(receipt)),
    )
```

Do not expose or call the private evaluator and do not create a legacy
bundle-free route.

- [ ] **Step 4: Wire `assemble-stage1` into the CLI**

The parser takes exactly the twenty-two relative arguments. It constructs
`Stage1ArtifactPaths`, calls the pure assembler, and uses the CLI's existing
already-admitted `CommandAttempt` to persist exactly one `receipt` terminal
through `publish_command_artifact`; it never allocates a second attempt.
Same-clock and concurrent assembly invocations receive distinct
O_EXCL-claimed ordinals. Refused assembly
persists a content-light `assembly_refused` receipt with no decision/verdict;
pre-root refusal keeps the null/null output pair.
Tests call the private assembly-command handler with a tmpdir root; public
`main` remains bound to the canonical root and accepts no override.

Add a behavioral authority RED: replace every service/pointer/override/install
surface with a function that raises, return `bench_passed` from the assembler,
and prove the only effect is the local receipt plus terminal line. The CLI
command table contains no rollback-drill or cutover handler. Measurement
authorization types cannot satisfy any such authority because no such API
exists.

Add the final tmpdir-only integration control now, after all behavior exists:

```text
tests/test_cuda_bench_assemble.py::TestLeanAirlockIntegration::test_stage1_owner_selected_evidence_returns_bundle_bound_verdict_without_mutation
```

It proves explicit owner selection, genuine P1 construction, the existing
public evaluator/receipt route, `bench_passed`, no provider/phase/service/
pointer callback, unchanged production hash witness, and no file outside the
temporary bench root. This is a GREEN composition control, not a claimed RED;
Task 10 later authorizes and certifies it on a committed detached checkout.

- [ ] **Step 5: GREEN, review, and commit**

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_migration.py tests/test_cuda_bench_driver.py \
  tests/test_cuda_bench_cli.py tests/test_cuda_bench_assemble.py
/home/rohit/maez/.venv/bin/ruff check \
  scripts/cuda_migration.py scripts/cuda_bench_driver.py \
  scripts/cuda_bench_cli.py scripts/cuda_bench_assemble.py \
  tests/test_cuda_migration.py tests/test_cuda_bench_driver.py \
  tests/test_cuda_bench_cli.py tests/test_cuda_bench_assemble.py
```

Commit:

```bash
git add scripts/cuda_bench_assemble.py scripts/cuda_bench_cli.py \
  tests/test_cuda_bench_assemble.py tests/test_cuda_bench_cli.py
git commit -m "feat(bench): return bundle-bound stage-one verdicts" \
  -m "The inert assembler enters the existing public bundle scorer twice on the same object and the CLI persists only its content-light local outcome." \
  -m "## Predicted effect

Complete evidence returns bench_passed or scorer-minted keep_vulkan with production unchanged; refused or unscorable evidence mints no verdict and reaches no action surface."
```

### Task 10: Retire the dead floor and add the certifying lean integration node

**Files:**
- Delete: `scripts/dev/bench_baseline.py`
- Delete: `scripts/dev/bench_report_plugin.py`
- Delete: `tests/test_bench_baseline.py`
- Modify: `tests/test_worktree_airlock_imports.py:500-550`
- Modify: `tests/test_cuda_bench_assemble.py`
- Modify: `AGENTS.md`
- Modify: `docs/superpowers/plans/2026-07-13-cuda-bench-driver.md`
- Modify: `docs/superpowers/specs/2026-07-12-cuda-bench-driver-design.md`
- Modify: `docs/runbooks/llama-b9596-cuda-migration.md`

- [ ] **Step 1: Write the deletion RED and retain the integration control**

The airlock inventory test must require:

```python
for removed in (
    "scripts/dev/bench_baseline.py",
    "scripts/dev/bench_report_plugin.py",
    "tests/test_bench_baseline.py",
):
    assert not (checkout / removed).exists()
assert (checkout / "scripts/dev/worktree_test_airlock.py").is_file()
```

Retain exactly this already-green tracked integration node from Task 9:

```text
tests/test_cuda_bench_assemble.py::TestLeanAirlockIntegration::test_stage1_owner_selected_evidence_returns_bundle_bound_verdict_without_mutation
```

It uses only tmpdir fixtures and proves: explicit owner selection; genuine P1
bundle; existing public evaluator/receipt route; `bench_passed` result; no
provider/phase/service/pointer callback; production hash witness unchanged;
and no file outside the temporary bench root. It is a GREEN regression/control,
not a second RED; the retired-file inventory is this task's real RED.

- [ ] **Step 2: Witness RED**

Run:

```bash
set +e
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_worktree_airlock_imports.py \
  -k 'retired_floor_inventory'
red_rc=$?
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_bench_assemble.py::TestLeanAirlockIntegration::test_stage1_owner_selected_evidence_returns_bundle_bound_verdict_without_mutation
control_rc=$?
set -e
test "$red_rc" -eq 1
test "$control_rc" -eq 0
```

Expected: the first test fails while the retired files exist; the integration
control remains green before and after deletion.

- [ ] **Step 3: Delete only the three retired files and update canon**

Use `apply_patch` for the inventory/canon edits and remove only the three named
files. Preserve `BenchEvidenceBundle` P1 validation and all dormant P2-P5
types. Update the historical plan's opening pointer to this plan; do not erase
its historical task record.

`AGENTS.md` must name the dedicated integration node as an honest certifying
selection. It must not advertise the retired full-floor gate.

- [ ] **Step 4: GREEN, reviews, and commit before certification**

Run:

```bash
set -euo pipefail
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_migration.py tests/test_cuda_bench_driver.py \
  tests/test_cuda_bench_stub.py tests/test_cuda_bench_cli.py \
  tests/test_cuda_bench_assemble.py tests/test_worktree_airlock_imports.py
/home/rohit/maez/.venv/bin/ruff check \
  scripts/cuda_migration.py scripts/cuda_bench_driver.py \
  scripts/cuda_bench_stub.py scripts/cuda_bench_cli.py \
  scripts/cuda_bench_assemble.py scripts/dev/worktree_test_airlock.py \
  tests/test_cuda_migration.py tests/test_cuda_bench_driver.py \
  tests/test_cuda_bench_stub.py tests/test_cuda_bench_cli.py \
  tests/test_cuda_bench_assemble.py tests/test_worktree_airlock_imports.py
git diff --check
```

Commit the scoped deletion/integration/canon package:

```bash
git rm scripts/dev/bench_baseline.py scripts/dev/bench_report_plugin.py \
  tests/test_bench_baseline.py
git add AGENTS.md tests/test_worktree_airlock_imports.py \
  tests/test_cuda_bench_assemble.py \
  docs/superpowers/plans/2026-07-13-cuda-bench-driver.md \
  docs/superpowers/specs/2026-07-12-cuda-bench-driver-design.md \
  docs/runbooks/llama-b9596-cuda-migration.md
git commit -m "refactor(bench): retire the crashing floor gate" \
  -m "The certified lean integration node replaces the dead full-repo baseline apparatus while preserving scorer P1 validation and dormant later-stage types." \
  -m "## Predicted effect

A detached clean checkout still emits one valid airlock certificate after the three floor files are removed; no full-repo stress run is required or invoked."
```

No source or documentation edit is permitted after this commit unless Task 10
is reopened, a new commit is made, and Step 5 is repeated against that new
head.

- [ ] **Step 5: Run the real airlock against the committed deletion head**

From a fresh detached checkout of the exact branch commit:

```bash
set -euo pipefail
test "$(git -C /home/rohit/maez-wt-bench branch --show-current)" = \
  feature/cuda-bench-driver
HEAD_TO_GATE=$(git -C /home/rohit/maez-wt-bench rev-parse HEAD)
test -z "$(git -C /home/rohit/maez-wt-bench status --porcelain)"
GATE=/home/rohit/.maez-gates/cuda-bench-lean-${HEAD_TO_GATE:0:12}-$$
OUT="${GATE}.stdout"
ERR="${GATE}.stderr"
test ! -e "$GATE"
test ! -e "$OUT"
test ! -e "$ERR"
cleanup_gate() {
  local cleanup_rc=0
  if git -C /home/rohit/maez worktree list --porcelain | \
      grep -Fxq "worktree $GATE"; then
    git -C /home/rohit/maez worktree remove --force "$GATE" || cleanup_rc=1
  elif test -e "$GATE"; then
    cleanup_rc=1
  fi
  rm -f -- "$OUT" "$ERR" || cleanup_rc=1
  return "$cleanup_rc"
}
trap cleanup_gate EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git -C /home/rohit/maez worktree add --detach "$GATE" "$HEAD_TO_GATE"
before=$(sha256sum /home/rohit/maez/.venv/lib/python3.14/site-packages/_editable_impl_maez.pth)
set +e
(
  cd "$GATE"
  env -u PYTEST_ADDOPTS -u PYTEST_PLUGINS \
    /home/rohit/maez/.venv/bin/python -I -S -B \
    "$GATE/scripts/dev/worktree_test_airlock.py" pytest -- -q \
    tests/test_cuda_bench_assemble.py::TestLeanAirlockIntegration::test_stage1_owner_selected_evidence_returns_bundle_bound_verdict_without_mutation
) >"$OUT" 2>"$ERR"
rc=$?
set -e
after=$(sha256sum /home/rohit/maez/.venv/lib/python3.14/site-packages/_editable_impl_maez.pth)
test "$rc" -eq 0
test "$before" = "$after"
test "$(grep -c '^MAEZ_AIRLOCK_CERTIFIED ' "$OUT")" -eq 1
test "$(wc -l < "$OUT")" -eq 1
! grep -q 'MAEZ_AIRLOCK_CERTIFIED' "$ERR"
/home/rohit/maez/.venv/bin/python -B - "$OUT" "$HEAD_TO_GATE" <<'PY'
import json
import pathlib
import sys

line = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
payload = json.loads(line.removeprefix("MAEZ_AIRLOCK_CERTIFIED "))
if payload["git_head"] != sys.argv[2]:
    raise SystemExit("certificate_head_mismatch")
PY
certificate=$(<"$OUT")
test -z "$(find /tmp -maxdepth 1 -type d -name 'maez-airlock-*' -print -quit)"
test -z "$(git -C "$GATE" status --porcelain)"
cleanup_gate
trap - EXIT INT TERM
test ! -e "$GATE"
test ! -e "$OUT"
test ! -e "$ERR"
printf '%s\n' "$certificate"
```

Expected: the already-committed deletion/integration head is the certificate's
`git_head`; shared `.pth` is byte-identical; cleanup succeeds even on a failed
assertion; no temporary output, detached checkout, or airlock residue remains;
the one validated content-light certificate line is returned to the gate
report after cleanup. This is
the first certification claim in Tasks 1-10.

### Task 11: Final scoped gate and inert merge handoff

**Files:**
- Verify only; no post-gate edits or commits

- [ ] **Step 1: Run the focused non-certifying evidence suite**

Run:

```bash
set +e
/home/rohit/maez/.venv/bin/python -B -m pytest -q \
  tests/test_cuda_migration.py tests/test_cuda_bench_driver.py \
  tests/test_cuda_bench_stub.py tests/test_cuda_bench_cli.py \
  tests/test_cuda_bench_assemble.py tests/test_worktree_airlock_imports.py
pytest_rc=$?
/home/rohit/maez/.venv/bin/ruff check \
  scripts/cuda_migration.py scripts/cuda_bench_driver.py \
  scripts/cuda_bench_stub.py scripts/cuda_bench_cli.py \
  scripts/cuda_bench_assemble.py scripts/dev/worktree_test_airlock.py \
  tests/test_cuda_migration.py tests/test_cuda_bench_driver.py \
  tests/test_cuda_bench_stub.py tests/test_cuda_bench_cli.py \
  tests/test_cuda_bench_assemble.py tests/test_worktree_airlock_imports.py
ruff_rc=$?
git diff --check
diff_rc=$?
test -z "$(git status --porcelain)"
clean_rc=$?
set -e
test "$pytest_rc" -eq 0
test "$ruff_rc" -eq 0
test "$diff_rc" -eq 0
test "$clean_rc" -eq 0
```

Expected: focused suite green, ruff/diff clean, committed feature checkout
clean.

- [ ] **Step 2: Run the certifying detached airlock node**

Repeat Task 10 Step 5 against the final committed head. Record the one
certificate line, branch commit hash, and `.pth` before/after hash.

- [ ] **Step 3: Re-witness dormancy and residue without mutating anything**

Run read-only checks:

```bash
set -euo pipefail
! ss -ltnH 'sport = :18080' | grep -q .
! ss -ltnH 'sport = :8082' | grep -q .
/home/rohit/maez/.venv/bin/python -B - <<'PY'
import os
from pathlib import Path

uid = os.getuid()
candidate_root = "/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/"
memfd_token = "memfd:cuda-bench-entry"
hits = 0
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        if proc.stat().st_uid != uid:
            continue
    except OSError:
        continue
    try:
        maps = (proc / "maps").read_text(
            encoding="utf-8", errors="surrogateescape"
        )
    except OSError:
        maps = ""
    if candidate_root in maps or "libggml-cuda.so" in maps:
        hits += 1
    links = [proc / "exe"]
    try:
        links.extend((proc / "fd").iterdir())
    except OSError:
        pass
    for link in links:
        try:
            target = os.readlink(link)
        except OSError:
            continue
        if memfd_token in target:
            hits += 1
if hits:
    raise SystemExit("bench_residue_detected")
PY
test "$(systemctl --user is-active llama-server.service)" = active
brain_pid=$(systemctl --user show llama-server.service -p MainPID --value)
test "$brain_pid" -gt 0
test "$(readlink "/proc/$brain_pid/exe")" = \
  /home/rohit/llama.cpp-release/llama-b9596/llama-b9596/llama-server
grep -q '/home/rohit/llama.cpp-release/llama-b9596/llama-b9596/libggml-vulkan.so' \
  "/proc/$brain_pid/maps"
! grep -q 'libggml-cuda' "/proc/$brain_pid/maps"
test "$(sha256sum /home/rohit/llama.cpp-release/llama-b9596/llama-b9596/llama-server | cut -d' ' -f1)" = \
  55c6ce2efc8feccd25bfab500c5ac70709152be6ff0c5bb2e0f478991519db69
test "$(sha256sum /home/rohit/.config/systemd/user/llama-server.service | cut -d' ' -f1)" = \
  65dfc9e59267b54f4896d88db682538d2fc9ac20d97a80bbd3c6cdfedcadddaa
test "$(sha256sum /home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf | cut -d' ' -f1)" = \
  95f630a0b3a7095d9ca0328184d731077d9b8dcca8dc1eadf93094fa8c529f37
test "$(systemctl --user is-active llama-vision.service || true)" = inactive
test "$(systemctl --user is-enabled llama-vision.service || true)" = disabled
grep -qx 'MAEZ_SCREEN_PERCEPTION=0' /home/rohit/.config/maez/model.env
test "$(nvidia-smi --query-gpu=driver_version --format=csv,noheader)" = 595.71.05
```

Expected: no bench residue or candidate process/maps; live `:8080` service is
still the exact frozen Vulkan incumbent with unchanged executable/unit/drop-in
hashes; vision remains contained; the one GPU still reports driver 595.71.05.
Do not stop/start/restart any unit.

- [ ] **Step 4: Produce the merge-gate package and stop**

Report:

```text
final feature commit
diff stat vs 1b2ddb2
focused test counts
airlock certificate and git_head
ruff/diff status
.pth before/after identity
stub/listener/process residue
runtime/service containment observations
```

Do not merge until Claude passes the final package. After a scoped merge, stop
at the owner boundary. Do not run `static-preflight`, `rehearse`, either phase,
the rollback drill, or any cutover. A/B measurement still requires Rohit's
explicit named window; rollback drill and permanent cutover each require a
separate owner act.

## Plain-English finish line

This plan adds the dashboard and evidence binder around the safe engine that
already exists. It lets the owner run the Vulkan/CUDA race and receive an
honest, scorer-bound recommendation, but it gives the software no lever that
can switch Maez's brain. Even a winning CUDA result is only evidence; the
manual rollback drill and any later permanent cutover remain separate,
explicit owner decisions.
