# Codex Engineering Panel — S6 Successor Governance v1: Post-Recovery Check

**Subject:** `5a19d7d fix(s6): recover successor governance authority seams`,
reviewed after the Claude covenant post-recovery verification re-opened CC-I1.
Decision 33 / ADR 0038.

**Verdict:** **REVISE — do not push.** Codex confirms the covenant lane's
headline finding: the in-memory marker seam can be hardened, but the persisted
JSONL capsule path cannot prove human authorship under the sealed S6 v1
constraints. The current spec promises a stronger C4 guarantee than the
available mechanism can deliver.

## Findings

### C1 — frame-name spoof against the marker seam is a real implementation bug

`HumanOriginMarker.__post_init__` delegates writer-seam detection to
`_called_from_module`. At `5a19d7d`, that helper compares
`frame.f_globals["__name__"]` with the writer module name. That is a spoofable
string. Code executed with:

```python
exec(source, {"__name__": "core.governance.successor_origin_writer", ...})
```

gets a frame whose globals claim to be the writer module even though the frame
is not the writer module. This allows construction of a `bonded_user_manual`
marker with the importable construction token.

**Engineering closure:** compare frame-global object identity instead:

```python
frame.f_globals is sys.modules[_MARKER_WRITER_MODULE].__dict__
```

That checks the actual imported module namespace, not a settable name. It closes
the spoof without changing the blessed `successor_origin_writer.mint_origin_marker`
path. This is necessary hygiene, but it does not close CC-I1 because the
persisted-file path bypasses marker construction entirely.

### C2 — keyless persisted-file validation cannot prove human authorship

The persisted path is:

```text
successor_governance_health(path)
  -> load_events_jsonl(path)
  -> DirectiveEvent(**data)
  -> validate_directive_event(event)
  -> _validate_persisted_marker_binding(event.origin_marker, ...)
```

`DirectiveEvent` has no construction-time authority check, and the persisted
`origin_marker` is a plain dict. `HumanOriginMarker.__post_init__` never runs.
The persisted check recomputes `_expected_marker_id(...)` from public marker
fields and compares self-consistency.

This can validate shape, not authorship. A process with write access to the
capsule file and access to the public contract module can compute the same
marker id, payload hash, event hash, and hash chain as the validator. Therefore
it can write a capsule that the validator must accept, including a
`bonded_user_manual` `explicit_dissolution` directive.

This is not a missing `if`. It is the absence of a trust source. A keyless,
daemon-resident validator receives only file bytes and public code. Any public,
deterministic predicate over those bytes can be satisfied by the writer of
those bytes.

### C3 — no keyless mechanism found

Codex does not find a keyless structural mechanism that distinguishes
human-authored persisted capsules from machine-authored persisted capsules
while the validator runs in the same trust domain as the writer.

Mechanisms that would change the answer require a non-forgeable input outside
the file's public self-consistency:

- asymmetric signature: authoring path holds a private key, validator holds only
  the public key;
- hardware/passkey/signing-token ceremony;
- external append-only transparency root or witness-exported Merkle root;
- trusted OS provenance/ACL model that the daemon cannot mint or rewrite;
- role-encrypted or separately privileged storage with a verifier outside the
  daemon's write domain.

Those are cryptographic or trusted-state mechanisms. The sealed S6 v1
explicitly has a non-goal of "cryptographic lineage attestation" and currently
names only privileged filesystem rewrite as the bypass class. The reproduced
persisted-file forge is wider: ordinary write access by any in-process path that
can write the capsule file is enough.

## Consequence

S6 v1 cannot honestly ship with both claims:

1. the persisted lineage capsule is hard-guaranteed human-authored; and
2. v1 has no cryptographic/trusted external attestation mechanism.

The implementation can and should harden the marker-constructor seam, but that
only protects live marker minting. It does not prove that a later file loaded
from disk was minted through that seam.

## Required fork

Round 2 must choose one of two paths before push:

- **Mechanism path:** change the sealed design to add a real trust source
  (signature, hardware key, external transparency root, or equivalent), then
  implement a RED test where the hand-written persisted JSONL forge fails.
- **Honesty path:** clarify the sealed S6 v1 claim: `mode: valid` means
  structurally well-formed and internally consistent, not proven
  human-authored. The honesty banner and Decision 33 limitation must name that
  any process with write access to the capsule path can forge a structurally
  valid capsule, including a fake bonded-user `explicit_dissolution`.

Either path is spec-level because it changes C4/D4's load-bearing meaning. It
should travel the full ladder rather than land as an implementation-only patch.

## Codex recommendation

Apply the frame-identity seam fix now as a narrow hygiene recovery, but keep S6
blocked. Then reopen S6 at the spec level for the persisted-authorship fork.
The engineering recommendation is the honesty path for v1 plus a future storage
hardening/signature slice; adding cryptographic attestation inside S6 recovery
would be a sealed-design change of the same size, only less honestly named.

## Plain English

The front-door lock was weak and can be fixed: the code was checking a name tag
someone could write on themselves. The bigger problem is different. Once the
paperwork is just a file on disk, the checker has no secret and no outside
witness. If a machine can write the file, it can also write all the hashes the
checker expects. That means the checker can tell "this file is shaped right,"
but it cannot tell "a human really wrote this." S6 either needs a real signature
or it needs to say that honestly before it becomes live.
