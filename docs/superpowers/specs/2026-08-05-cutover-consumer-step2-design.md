# Cutover slice step 2 — the consumer primitive, design v1

Status: **DRAFT — awaiting ratification. No REDs, no code until ratified.**

Parent: `docs/superpowers/specs/2026-08-04-cutover-bundle-antibypass-design.md`
(step 1, merged at `348332b`).

---

## The central falsifiable claim

> No cutover mutation is reachable except through a consumer that
> revalidates the real stage-2 receipt and authorization, atomically burns
> the nonce at the last no-mutation point, durably records consumption,
> then hands control directly to the closed mutation executor.

Everything below exists to make that claim testable and to make each of
its clauses individually falsifiable. If a clause cannot be killed by a
mutation, it is not yet proven and must be reported as such — step 1
ended with exactly one such line (`containment_docs`), reported rather
than claimed.

## What step 1 did and did not establish

Step 1 constrains **assembled evidence**. It refuses any bundle whose
timestamps contradict burn-immediately-before-mutation:

```
latest stage-1 evidence < issued <= witness <= stage-2 bundle/receipt
  <= burn <= every mutation-result witness <= bundle timestamp < expires
```

That is a refusal to be *contradicted*. It is not a proof of live
ordering. A caller could still, today, burn a nonce and then do arbitrary
work before mutating, and step 1 would never see it — the evidence it
assembles afterwards would be perfectly consistent.

Step 2 closes the gap between "the evidence is not contradictory" and
"the ordering actually happened."

## Scope boundary — stated plainly, per the ratification conditions

**Step 2 does not contain the real mutation executor.** The executor
performs owner-typed systemd actions against production; it is a separate
act with its own gate, and this slice must not be able to run it.

Therefore step 2 proves:

* the **consumer primitive** — validation, burn, durable record; and
* the **final interface** — the exact call shape the executor will be
  reached through, with a test double standing in for it.

Step 2 does **not** prove live ordering. Live ordering becomes provable
only when the later act wires the real executor through this interface
*structurally* — i.e. when the executor has no other caller and the
consumer has no other continuation. Until then the claim above is proven
for every clause except the final handoff, whose target is a double.

This boundary is stated in the design so it cannot later be misread as
having been demonstrated. Step 1's lesson applies: a test named for more
than it proves is a defect even when the code is correct.

---

## S1. Anchored private-root acquisition

**Seam: one root, acquired once, never re-resolved. No alternate evidence
root.**

The consumer opens the bench root exactly once:

```
O_RDONLY | O_DIRECTORY | O_NOFOLLOW
```

and holds that descriptor for the whole ceremony. Every subsequent read
and write is `dir_fd`-relative with `O_NOFOLLOW`. No path is re-resolved
after acquisition, so no component can be swapped between validation and
burn.

Refusals at acquisition:

| condition | refusal |
|---|---|
| root is a symlink, or any open resolves one | `root_not_anchored` |
| root is not a directory | `root_not_anchored` |
| root not owned by the invoking uid | `root_ownership` |
| root mode is not `0700` | `root_mode` |
| `st_dev`/`st_ino` differ from the same values re-stat'd via the held fd at burn time | `root_moved` |

The root is a **parameter with no default that reaches production**.
Tests pass a private `tmp_path`; the production caller passes the real
bench root explicitly. There is no fallback and no environment override —
an alternate evidence root is the whole attack, and the absence of a
default is what makes it unreachable rather than merely discouraged.

`_anchored_exclusive_write` already implements the write half of this
(`scripts/cuda_cutover.py:73`). Step 2 generalizes it to take the held
root fd rather than re-opening the parent each call.

## S2. File-hash and binding-hash joins

**Seam: two hashes per document, both computed from bytes the consumer
itself read.**

For the authorization and for the stage-2 receipt:

* `file_sha256` — over the exact bytes read through the anchored fd;
* `binding_sha256` — from the typed object after canonical decode.

Both are recomputed by the consumer. Neither is accepted as an argument.
This is the step-1 lesson carried forward: a hash supplied by the caller
is a claim, not evidence.

Canonical decode uses the same `PersistedDoc` / `_canonical_persisted_role`
path the scorer uses, so a document that would not survive step 1's
constructor cannot enter here either. In particular the receipt's
`cutover_window_id` must be an exact `_WINDOW_ID_RE` string — the type is
already enforced at that boundary and is not re-implemented.

## S3. The exact join set

**Seam: every join is equality against a value the consumer derived
independently. No subset, no substring, no coercion.**

| join | left | right |
|---|---|---|
| window | `receipt.cutover_window_id` | `auth.window_id` |
| boot | live `/proc/sys/kernel/random/boot_id` | `auth.boot_id` |
| action set | `auth.actions` | `CUTOVER_ACTION_SET` (exact tuple) |
| bench anchor | `receipt.bench_binding_sha256` | `auth.parent_bench_evidence_sha256` |
| recovery manifest | `auth.rollback_manifest_sha256` | `FROZEN_ROLLBACK_MANIFEST_SHA256` |
| decision | `receipt.decision` | `"provisional_cuda_boot"` exactly |
| reasons | `receipt.reasons` | `("cold_boot_witness_pending",)` exactly |

Chronology at the consumer, evaluated against the burn moment `now`:

```
auth.issued_at <= receipt.timestamp <= now < auth.expires_at
```

`now` is supplied by an injected clock so it is testable, and is the same
value written into the durable record — one moment, not two readings.

**Open question for ratification (Q1):** whether the consumer must also
verify that the stage-2 receipt's `bundle_binding_sha256` is recomputable,
which would require it to hold the stage-2 bundle. My position is **no** —
that join is step 1's and is already enforced wherever the bundle exists.
Duplicating it here would require the consumer to reconstruct evidence it
has no business holding at the execution edge. I want this ruled on
explicitly rather than assumed.

## S4. The burn is the durable record

**Seam: burning the nonce and recording consumption are ONE act, not
two.**

The `O_EXCL` marker creation *is* the burn *and* the durable record: the
file's content is the complete `CutoverConsumptionReceipt` (all eight
fields, canonically encoded). There is no window in which the nonce is
spent but unrecorded, or recorded but not spent, because there is no
second write.

Sequence at the edge:

```
... all validation, all fallible preparation ...        <- may refuse freely
compose the complete consumption receipt bytes          <- last fallible step
--------------------------------- last no-mutation point
O_EXCL create + write + fsync(file) + fsync(dir)        <- the burn
--------------------------------- nonce is spent
executor(validated_doc)                                 <- exactly one call
```

The receipt bytes are composed **before** the burn precisely so that
encoding cannot fail after it.

## S5. Failure semantics, both sides of the burn

**Pre-burn failure** — any refusal in S1–S3, or while composing the
receipt bytes:

* no mutation;
* no consumption receipt on disk;
* **the nonce remains reusable.** The authorization is still valid until
  its TTL expires, and a corrected invocation may consume it.

**Post-burn failure** — `O_EXCL` succeeded and anything afterwards fails,
including `fsync`, including the executor:

* the nonce is **spent**;
* the outcome is a **terminal refusal**;
* the nonce is **never retryable**, by any path, for any reason.

A crash between `O_EXCL` and `fsync` leaves a marker whose content may be
truncated. That marker still blocks reuse. This is deliberate and
fail-closed: an unreadable burn record means we cannot prove the mutation
did not begin, so the authorization is dead. Recovery is a new
owner-typed authorization with a new nonce, never a repair of the old
one.

`FileExistsError` on the marker is `authorization_consumed` and is
terminal — it is not retried, not backed off, and not distinguished from
a deliberate replay, because from the consumer's position those are the
same event.

## S6. Nothing between the burn and the first mutation

**Seam: no fallible preparation, no unrelated branching, no logging, no
I/O between the burn and the executor call.**

Structural rules, each of which is separately checkable:

1. The burn and the executor call are adjacent statements in one
   function. Nothing is interposed.
2. Everything fallible is hoisted above the last-no-mutation point — this
   is why receipt bytes are composed pre-burn.
3. The executor takes the **validated typed document**, not paths, not
   raw bytes, and not the root fd. It cannot re-read or re-resolve
   anything, so it cannot fail in a way that belongs to validation.
4. There is exactly **one** call site for the executor in the module, and
   it is that adjacency.
5. No `try`/`except` wraps the region between burn and call. A handler
   there would be a branch, and a branch is a place for work to hide.

Rules 1, 4 and 5 are statically checkable against the module's own AST,
and I intend to assert them that way rather than by reading the code —
step 1 established that reading logic is not evidence that a path is
taken. **Open question for ratification (Q2):** whether an AST-level
structural assertion is acceptable as the proof for rules 1/4/5, or
whether cross-lane review wants a stronger runtime proof (e.g. an
executor double that asserts no intervening call was observed). My
position is that the AST assertion is the honest instrument here, because
the property being asserted is genuinely syntactic — but I would rather
have that ruled on than assume it.

## S7. The executor interface, frozen now

The interface is frozen in step 2 even though its implementation is not:

```
CutoverExecutor = Callable[[CutoverAuthorizationDoc], CutoverOutcome]
```

* takes exactly the validated authorization document;
* returns a closed outcome type;
* raises nothing the consumer catches — a raise is a post-burn terminal
  refusal by construction.

The test double records that it was called exactly once, with exactly the
validated document, after the marker existed on disk. That last assertion
— marker-then-call, verified by observation rather than by argument — is
the strongest form of the ordering claim available before the real
executor exists.

---

## Refusal vocabulary (closed)

`root_not_anchored`, `root_ownership`, `root_mode`, `root_moved`,
`authorization_missing`, `authorization_wrong_type`,
`authorization_noncanonical`, `receipt_missing`, `receipt_wrong_type`,
`receipt_noncanonical`, `join_mismatch`, `chronology_violation`,
`authorization_expired`, `authorization_boot_mismatch`,
`authorization_consumed`, `burn_unrecorded`, `executor_failed`.

Closed set, exhaustively tested, no `_uncertain` catch-all — an
unclassified failure at this edge would be the one place a fallback could
hide.

## What step 2 does NOT change

* No mutating `systemctl`. The driver still holds none.
* No production unit, override, model pointer, or venv file.
* `model_state.json` remains an owner-typed command after a durable
  promotion receipt.
* Cutover remains **forbidden** at `bench_passed`. This slice builds the
  consumer that a future authorized cutover would pass through; it does
  not authorize one.

## Open questions for ratification

* **Q1** — must the consumer re-verify the stage-2 receipt's
  `bundle_binding_sha256` against a recomputed stage-2 bundle? My
  position: no; that is step 1's join and requires evidence the consumer
  should not hold.
* **Q2** — is an AST-level structural assertion the accepted proof for
  the burn/executor adjacency rules, or is a stronger runtime instrument
  required?
* **Q3** — on post-burn `fsync` failure, is terminal-refusal-with-spent-
  nonce the ratified behaviour? It is the fail-closed choice and it
  permanently destroys a valid authorization on a transient disk error.
  I believe that is correct at this edge and want it ratified rather than
  discovered later.
