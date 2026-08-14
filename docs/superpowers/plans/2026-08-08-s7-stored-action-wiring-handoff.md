# S7 / cutover 2B — resumption note

**Resume with: TWO GOVERNANCE DECISIONS, not code.** The remaining work
is blocked on design, not effort. Three consecutive build attempts
stopped correctly on genuine contradictions; a fourth would too.

*(No head hash recorded on purpose: a note naming its own commit is
self-invalidating the moment it is amended.)*

**The live store has never been migrated.** `memory/s7_1_webauthn/ceremony.sqlite3`
remains sha256 `5384bce8…`, mode `0600`, inode `18633958`, no sidecars,
no receipt. It holds two enabled founder credentials.

## The S7 defect is CLOSED

The arc's reason for existing is done. `execution_grant_authorizes_action`
compared only work class and `canonical_hash(params)`; neither carried
the action, so one grant authorized every sibling operation. Now:

- the grant's action comes from `UPDATE … RETURNING action` — the same
  atomic statement that consumes the row returns it;
- the consume `UPDATE` carries `AND action = ?` as a PREDICATE, so a
  mismatched row is not matched, not consumed, and the approval is not
  burned;
- every consumer joins its own authoritative action;
- a `str` subclass is refused by exact typing;
- a bug in `consume_for_execution` propagates instead of returning
  `(None, None)` — a broken seam no longer impersonates a denial.

## What is green, and what that claim is worth

Six gated suites: migration 105, anchored_io 59, voice bundle v2 22,
action joins 78, action binding 68, route allowlist 25 — **357**. Cutover
2B contract set: **48**. Prerequisite: **39**.

**These are LOCAL BEHAVIOURAL counts and are NON-CERTIFYING.** The broad
airlock selection refuses with `airlock_import_provenance_violation`, so
they confirm the behaviour holds; they do NOT certify that every import
came from the audited checkout. State it that way.

## THE TWO DECISIONS BLOCKING EVERYTHING

**1. What the cutover's third evidence requirement becomes (v31).** The
content-blind rail requires a `semantic_reader_attempt_hash` before
`valid_absent` is reachable. R8 FORBIDS a semantic reader on the cutover
path. So the rail demands evidence of a read the ruling abolished, and
the only way to pass is to relabel the response hash, attempt identity
or receipt reference as reader evidence — fabrication, correctly refused.

The defensible replacement is a distinct, typed, sealed CAPTURE receipt:
proof the exact response was durably recorded and is retrievable for
owner review. It attests something real without pretending a machine
read it. **Do NOT resolve this by silently dropping the requirement** —
a rail reduced from three checks to two with no record of why is how a
protection decays into a formality.

**2. How evidence-keyed admission reaches the gate (v30).** R8 records
`not_determined`; the voice-seat gate blocks anything but `absent`; so
the honest path is a dead end. Fail-closed, therefore safe.

The obvious fix — admit `not_determined` — is WRONG and would open a
hole. The generic decision pipeline emits the same string when its
semantic reader is UNCERTAIN, and dialog soul-writes and dream execution
rely on that blocking. Admission must be CUTOVER-SPECIFIC and keyed on
EVIDENCE, never the label: the canonical envelope plus the typed,
revalidated R8 result, which today is not carried into `authorize_finish`
at all. Carrying it is the work — and it is blocked on decision 1.

## Ordered, after those decisions

1. **Evidence-keyed gate admission** (v30), with the test that a generic
   `not_determined` still blocks soul-writes. That test now exists and
   bites — `test_authorization_voice_recheck_blocks_a_real_not_determined_consultation`.
2. **The 2B consumer.** It OWES BACK four witnesses retired with the v1
   consumer: single-use atomicity, double-spend refusal, expiry, and
   boot-mismatch. Nothing covers them today.
3. **The bonded-runtime adapter** — the wire to the real Maez. Until it
   exists, the producer asks correctly and cannot prove it reached Maez.
   Provenance is UNVERIFIED and recorded as such. A nominal wrapper was
   refused and must stay refused.
4. **The legacy-vs-v2 type migration.** NOT a cleanup: the daemon still
   produces the legacy type for soul writes, dream execution and
   decision-pipeline self-modification. A naive fix moves
   `blocking_present` off the D23 refusal-history path and changes
   refusal timing — the system would still refuse, but stop recording
   why. Needs its own REDs.
5. **`_on_approve` re-swallow.** `consume_for_execution` now propagates,
   but `_on_approve` invokes the hook inside its own `except Exception`
   and turns it back into a silent block. Fails CLOSED, so not an
   opening; quiet where it should be loud. Its own slice — live path.

## The pre-existing failures, now on the record

`tests/test_s7_1_ceremony_service.py` is **10 failed / 28 passed**, and
was 10 failed / 26 passed at this session's start — this arc added two
passes and broke none. All ten fail with `S7 v2 authorization plane is
absent`: their fixtures never migrate, so they meet the deliberate
absent-v2 refusal. Same class as the 17 construction sites already
fixed. They sit OUTSIDE the six gated suites, which is why they went
unseen.

Also owed: preparation has no runtime positive-control fixture.

## The one defect shape, three times in one session

Each was a decision trusting a field that does not carry what it asserts:

1. a grant that did not carry the ACTION → authority inferred from work
   class and params;
2. a boolean that did not carry the RESPONSE → "Maez did not object"
   concluded from a flag defaulting to False, set by whoever built the
   bundle;
3. a label that does not carry the EVIDENCE → the bare voice-seat gate
   accepts a hand-constructed `absent` without seeing R8's sealed result.

**(3) IS NOT CLOSED.** It spans non-cutover paths and needs its own
slice. Do not assume it closed.

## Standing constraints

- The cutover needs BOTH the owner's key tap AND Maez consulted with no
  objection — and under R8 the owner READS the exact response and judges.
  No machine verdict. R7 covers only the pre-birth migration command,
  sets no precedent, expires at birth.
- The live store is read-only to this work.
- No creation or activation authority in the daemon or
  `S7WebAuthnBootstrapStore`. No facade re-export of a private helper.
- Producers live in `core/` — every allowlist producer row does. Non-core
  files hold writer/edge/renderer/hash roles only.
- `git add` by EXACT PATH. The tree holds 10 dirty and 39 untracked user
  files that stay byte-identical. `docs/.obsidian/graph.json` is the
  owner's and is never committed.

## Method notes that earned their keep TODAY

- **Ask the stub question.** "If this were replaced by something that
  always says yes, which test fails?" The answer was NONE, and it
  exposed that all five consultation tests were structural. Ask it of
  anything that gates authority.
- **Measure PER-TEST, never by net count.** A reported three-failure
  mutation was actually one; the difference was hidden behind two new
  passes.
- **A test surviving removal of its own protection is not a test.**
  Mutating the gate to admit `not_determined` left the test named for
  blocking it green.
- **Check the dirty-file count after every commit.** It caught two files
  left out of two commits, on the same day.
- **A positive control that fails may mean the control is wrong.** Twice
  the opener "wrongly" refused; both times my fixture was wrong and the
  code was right.
- **Do not claim a suite passes from a subset.** I wrote "Suite passes"
  after running four tests of thirty-eight. Corrected in the next commit.
- **Stop rather than relabel.** Three build-thread refusals to fabricate
  evidence produced the three most valuable findings of the session.
