# CUDA binary startup diagnostics

Status: owner-ratified 2026-07-31. Corrective extension to the inert CUDA A/B
bench at `2dc75a8`.

## Problem and established evidence

The first real Vulkan phase passed containment, consumed its authorization,
spawned through the sealed-memfd launcher, entered `cycle_1_readiness`, then
the admitted server exited before `/health`. Finalization was clean: no signal
was needed, the listener was free, and no process-group member survived.

This was not an `execve` or dynamic-loader refusal. The launcher returned an
`OwnedChild`, captured the running target identity, and kernel audit recorded
the dynamic loader opening `libllama-server-impl.so`. The missing facts are
the target's natural exit status or terminating signal and its early stderr.
The current binary launcher discards stderr to `/dev/null`, so a correctly
classified `crash` cannot explain itself.

## Authority boundary

Diagnostics are passive instrumentation on the existing production binary
launcher. They create no command, mode, tier, authorization, service action,
model-load path, or scorer input. A real-model reproduction still requires the
ordinary owner-authorized phase, with all existing real service, port, GPU,
containment, identity, nonce-consumption, pidfd, and finalizer gates.

The rehearsal tier remains exactly what it is: a pinned Python stub, synthetic
GPU/kernel/service providers, an ephemeral non-18080 port, no model or corpus
read, and incompatible rehearsal artifacts. It never launches the real model.
Synthetic all-clear signals may not authorize live hardware.

## Capture architecture

### Binary-only bounded drain

Only `SpawnPin(kind="binary")` receives diagnostic capture. Python-file
rehearsal keeps its current stdout sentinel and stderr behavior unchanged.

The launcher creates its own `pipe2(O_CLOEXEC)` pair before `Popen`, makes
only the read descriptor nonblocking, passes the still-blocking write
descriptor as the child's stderr, closes the parent's copy of the write
descriptor immediately after spawn, and gives the read descriptor
exclusively to a bounded drainer before releasing the inert guard. Keeping
the child's writer blocking preserves ordinary stderr semantics; the drainer,
not `EAGAIN`, supplies backpressure relief. `Popen.stderr` therefore remains
`None`: the existing finalizer's stream cleanup cannot close or race the
diagnostic reader. At exec, the subprocess layer duplicates the supplied
writer onto descriptor 2, so the target retains only ordinary stderr rather
than an extra diagnostic descriptor.

The write-end blast radius is the deliberate spawn tree only. It is created
inside the one spawn operation, is never stored in `OwnedChild`, a refusal,
or process-global state, and is absent from `pass_fds`; `close_fds=True`
prevents the original descriptor from crossing exec. The guard/target receives
only descriptor 2, and only descendants it deliberately creates can inherit
that descriptor. The parent closes its copy before guard release, so a later
or concurrent unrelated spawn cannot inherit it. No Maez daemon, service, or
other pre-existing process can acquire the writer.

The drainer continuously consumes the entire stream so a verbose server
cannot block on a full pipe. It retains at most
`BINARY_STDERR_DIAGNOSTIC_CAP = 65_536` bytes, computes the SHA-256 of those
retained bytes, records the retained byte count, and sets `truncated=true` as
soon as any additional byte is observed. Bytes beyond the cap are discarded,
never buffered or written.

The capture starts early enough to include guard/bootstrap stderr as well as
dynamic-loader and llama-server startup stderr. It therefore accompanies both
pre-admission `spawn_failure` and an admitted child that dies during readiness.
No stderr text appears in an exception string or `repr`.

The drainer uses a nonblocking read descriptor, a separate close-on-exec
control pipe, and a bounded poll loop. It is the sole owner of both read
descriptors. The phase state machine is the lifecycle owner that sends the
finish byte for both an admitted child and any post-`Popen`, pre-admission
failure. On the latter path the launcher completes its existing bootstrap
process cleanup, freezes that result in a private live carrier, and returns
control without retiring the diagnostic. The same handshake runs even when
process cleanup is already `cleanup_incomplete`.

For an admitted child, ordering is strict: `finalize()` returns, the state
machine durably appends the complete `FinalizeResult` transition to the
private journal, and only then may it send the diagnostic finish byte. Thus a
contract-violating survivor and `cleanup_incomplete` are established in the
record before closing the reader can affect an inherited writer. For a target
that never reaches `OwnedChild` admission, there is no finalizer verdict. The
state machine first durably appends the launcher's fixed bootstrap-cleanup
result, then commands diagnostic finish through the carrier. Both paths
therefore establish the contract violation in durable evidence before reader
retirement can affect an inherited writer.

The drainer wakes, drains stderr until the read would block or reaches EOF,
subject to both a post-finish byte budget of 65,536 bytes and a one-second
monotonic deadline. Reaching either bound closes both read descriptors and
exits even if stderr remains continuously readable. The lifecycle owner then
closes its control writer and performs a bounded join. Main-thread code never
closes a descriptor concurrently owned by the drainer.

This stop handshake is authoritative even when EOF cannot arrive. In
particular, the frozen finalizer may honestly return `cleanup_incomplete`
without signalling an unexpected process-group member; such a member may
still hold inherited fd 2. The control pipe nevertheless retires the capture
thread and its descriptors without deliberately signalling that member or
pretending the process cleanup succeeded. Closing the bench-owned read end may
cause `EPIPE` or kernel-delivered `SIGPIPE` in a continuously writing
descendant, but only after that descendant has already broken the frozen
single-process-child contract and made the attempt terminally
`cleanup_incomplete`. This fd-lifecycle side effect is accepted; absolute
passivity toward arbitrary inherited writers would require leaking the reader
indefinitely. The finalizer remains the sole authority for deliberate
signals. If EOF already completed the drainer, a broken control write is
harmless only after the finished state and bounded join prove that fact.
Otherwise, failure to send the finish byte or complete the bounded join yields
`cleanup_incomplete`; it can never be ignored as successful cleanup. The
existing `finalize()` pidfd checks, signal order, waits, port proof, and
`FinalizeResult` stay byte-identical.

### Private lifecycle carrier

The raw bytes cross the launcher/state-machine boundary only through private
Python objects whose `repr`, equality, and exception arguments exclude the
payload:

- an admitted binary `OwnedChild` holds a private capture handle until the
  existing finalizer completes; and
- a failure after child creation but before `OwnedChild` admission raises the
  existing typed refusal through a private subclass carrying the fixed
  bootstrap-cleanup result and the still-live capture handle.

The public refusal code and message remain content-light. The state machine
knows the active cycle and attempt root, consumes either carrier exactly once,
durably journals the applicable process-cleanup result, finishes the capture,
publishes the private diagnostic, journals only its metadata, then continues
the existing outcome path. Python-file children carry no diagnostic handle.
No caller outside the phase state machine receives raw bytes. The production
binary launcher is structurally consumed only through this state-machine
handoff; tests that call the lower seam directly must exercise the same
carrier-disposal helper. If the state machine cannot prove the diagnostic
thread/descriptors retired, `cleanup_incomplete` supersedes the original
refusal and no snapshot is claimed.

### Private diagnostic artifact

After process cleanup and a successful bounded drainer join, the state machine
writes the retained prefix once to:

```text
<attempt-root>/diagnostics/cycle-<N>-stderr.bin
```

Publication uses the existing anchored `write_private_file` path: private
0700 ancestors, a 0600 regular file, exclusive atomic link, file and parent
fsync, no symlink/hardlink substitution, and no overwrite. A pre-admission
binary failure is associated with the active cycle and uses the same path.
An empty stream produces an empty 0600 file whose SHA-256 is the ordinary
empty-bytes digest; absence and empty output are therefore distinguishable.

The raw file is a debugging artifact, not evidence:

- it has no production or rehearsal schema;
- it is absent from `_ARTIFACT_SCHEMAS` and `ArtifactPolicy`;
- it is absent from `PhasePacket`, `BenchEvidenceBundle`, PersistedDoc
  decoders, the 22 assembler roles, scorer inputs, verdicts, and receipts;
- it is never copied outside the canonical owner-owned bench root; and
- its bytes are never printed or serialized into another artifact.

The deterministic path lets the owner find the file without placing a
diagnostic locator into scoreable evidence.

### Content-light metadata

After cleanup and private publication, the phase journal receives one
content-light transition per binary cycle containing only:

- retained stderr SHA-256;
- retained byte count, bounded `0..65_536`;
- truncation boolean;
- natural exit code or terminating signal, when observed; and
- whether the target had exited before finalization.

No raw bytes, decoded text, exception, argv, environment, prompt, response,
absolute path, or diagnostic reference enters the journal. The reduced failed
packet and completed packet remain unchanged and carry no diagnostic field.
CLI stdout/stderr and command receipts remain unchanged.

If private publication fails, the phase reports the existing typed filesystem
or cleanup failure. It never claims a diagnostic exists and never fabricates
empty metadata. Instrumentation may fail a run closed; it may not change a
measurement, scorer threshold, or verdict. Diagnostic publication is never a
terminal command artifact and never receives a `command_completion.v1`.

## Lifecycle and outcomes

The diagnostic snapshot is single-use and immutable after finish. Exactly one
of these paths applies:

1. **Clean natural exit:** exit code is recorded; cleanup proves no residue.
2. **Nonzero natural exit:** exit code and bounded stderr metadata explain the
   existing typed crash/spawn outcome.
3. **Signal death before finalizer:** terminating signal is recorded; no signal
   authority is inferred from stderr.
4. **Finalizer-owned termination:** existing `signals_sent` remains the
   authority; diagnostic metadata records the resulting process status
   without relabelling it as a natural crash.
5. **Truncation:** the first 65,536 bytes remain private, all later bytes are
   drained and discarded, and `truncated=true` is recorded.
6. **Capture cleanup uncertainty:** `cleanup_incomplete`; no process, thread,
   descriptor, listener, or partially published diagnostic may be reported as
   clean.

## TDD verification contract

All behavioral tests use genuine dynamically linked host ELFs and no model,
GPU, service, nonce, or window:

1. `/usr/bin/true` proves clean exit and an empty bounded diagnostic.
2. `/usr/bin/false` proves a nonzero natural exit is retained.
3. Pinned `/usr/bin/bash` terminating itself by signal proves signal status.
4. Pinned `/usr/bin/bash` emitting more than 65,536 stderr bytes proves the
   child cannot deadlock, retained size is exactly capped, truncation is true,
   and cleanup is residue-free.
5. A unique stderr literal proves the raw bytes exist only in the 0600 private
   diagnostic. Rendered stdout, stderr, journal, refusal/packet, receipt, and
   object `repr` must not contain it.
6. Spawn bootstrap failure and admitted pre-readiness death both publish at
   most one diagnostic and preserve their existing typed outcomes. The
   private live failure carrier's exception string and `repr` remain
   content-light, and a structural test proves every production launcher call
   is wrapped by the state-machine disposal helper.
7. SIGINT/SIGTERM, pid-reuse, identity-capture failure, truncation, diagnostic
   publication failure, and cleanup failure all leave no child, PGID member,
   listener, diagnostic thread, or open diagnostic descriptor.
8. Structural tests prove no diagnostic field or schema can enter
   `PhasePacket`, `BenchEvidenceBundle`, PersistedDoc, assembler selection,
   scorer, verdict, or receipt.
9. A source-boundary test proves `finalize()` is byte-identical to `2dc75a8`.
10. Rehearsal tests prove its exact Python-file pin, ephemeral-port contract,
    no-model guarantee, and provider tier seal are unchanged.
11. A stream-ownership test proves binary `Popen.stderr is None`, the parent
    owns no write descriptor after spawn, EOF reaches the sole read owner, and
    the finalizer never closes the diagnostic descriptor.
12. A real-ELF descendant retaining inherited stderr and writing continuously
    proves the control-pipe handshake terminates the drainer within both
    post-finish bounds even without EOF. The finalizer's
    survivor/`cleanup_incomplete` result remains unchanged, the drainer closes
    its own descriptors, and no main-thread close races it. Test cleanup owns
    and removes the deliberately created adversarial survivor after observing
    the driver's honest survivor receipt. The same retained-writer case is
    exercised after a post-`Popen` identity-capture failure, proving the
    launcher freezes process cleanup in its private refusal carrier without
    closing the reader; the state machine journals that result, then completes
    the handshake.
13. A descriptor-blast-radius RED proves the parent closes its writer before
    guard release, the original writer is absent from `pass_fds`, an unrelated
    child spawned while the target runs cannot write to the diagnostic pipe,
    and no writer survives into the next binary cycle. Only fd 2 in the
    deliberate guard/target tree may refer to that pipe inode.
14. Ordering REDs block diagnostic finish until the journal has durably
    appended either the finalizer outcome or the pre-admission bootstrap
    cleanup outcome. In both continuous-writer cases the recorded
    `cleanup_incomplete` precedes any observed `EPIPE`/`SIGPIPE` effect.
15. Direct bundle construction and assembler entry both reject every
    `cleanup_incomplete` attempt before scorer entry; no verdict or bundle
    binding can exist for it.

The eventual live witness is one freshly authorized Vulkan phase. The same
run either continues into measurement or produces the private bounded
diagnostic plus content-light exit metadata. There is no separate diagnostic
invocation and no blind retry.

## Non-goals

- no rehearsal real-binary mode;
- no new CLI command or hidden flag;
- no unowned model spawn;
- no service start/stop/restart;
- no scorer, bundle, assembler, threshold, or verdict change;
- no decoding, classifying, censoring, or interpreting stderr;
- no unbounded log retention; and
- no CUDA/Vulkan behavioral fix before the captured error establishes cause.

## Predicted effect

The next authorized Vulkan phase preserves every existing safety and evidence
gate. If llama-server again exits before readiness, the failed phase remains
content-light and unscoreable while the owner-private attempt directory gains
one bounded stderr prefix whose metadata identifies the real exit status. If
the server instead stays up, the phase continues normally and the passive
capture cannot affect its measurements or verdict.
