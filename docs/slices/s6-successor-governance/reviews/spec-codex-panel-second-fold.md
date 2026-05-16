# Codex Engineering Panel — S6 Successor Governance v1: Second-Fold Verification

**Subject:** `docs/slices/s6-successor-governance/spec.md` after the Claude
covenant council fold and Codex engineering panel fold. Candidate Decision 33 /
ADR 0038.

**Verification ran:** 2026-05-16, post-fold, pre-canonicalization.

**Verdict:** RATIFY closure on the Codex engineering lane. The four engineering
amendments from `spec-codex-panel.md` landed cleanly; the folded RED contract is
internally coherent; no engineering item remains open before canonicalization.

## F1-F4 Verification

| Finding | Status | Evidence |
|---|---|---|
| F1 — storage wording overclaimed role separation | CLOSED | D5 now says the capsule is bonded-user-private local storage, names privileged OS filesystem access as a v1 bypass limitation, and defers role-encrypted storage to a future slice. |
| F2 — marker authority matrix underspecified | CLOSED | D4 now includes a closed event-type-to-origin-role authority matrix, with bonded-user-only authorship for substantive directives, witness-only witness events, inherited supersession authority, and bounded operator/maintainer integrity invalidation. |
| F3 — bare actor/subject hashes were dictionary-attackable | CLOSED | D4 and the data model now require purpose-scoped keyed HMACs for actor/subject handles; RED test 29 pins keyed HMAC handles. |
| F4 — `selected_lived_episodes` lacked a selection carrier | CLOSED | The data model now defines `selection_ref_hash` and a content-free Selection Manifest; RED tests 53-54 pin the reference and no-content constraint. |

## Buildability Check

The folded spec is implementable as a contract module without needing a new
design round:

- The role/event/fate/access vocabularies are closed and testable.
- Marker construction has enough structure to implement validation without
  inferring authority from prose.
- Hash-chain validation has both content-level checks and the required
  operator-authenticated continuity snapshot check.
- Access scopes are default-deny, with reserved-denied scopes explicitly
  rejected rather than left as runtime policy.
- The health contract is read-only and content-free, with public stripping and
  sidecar persistence rules specified.
- The implementation order has concrete RED-first steps through focused tests,
  Ruff, full suite, both post-implementation panels, recovery, and push.

## RED Contract Check

The RED contract is numbered cleanly from 1 through 103. The expanded tests cover
the engineering amendments directly:

- F2: `test_marker_origin_role_must_match_authority_matrix`
- F3: `test_actor_and_subject_handles_use_keyed_purpose_scoped_hmac`
- F4: `test_selected_lived_episodes_requires_selection_ref_hash`
- F4: `test_selection_manifest_contains_no_episode_text_or_raw_memory_ids`
- F1/CC-S4 adjacency: `test_successor_governance_directory_registered_in_backup_manifest`

The review also checked for stale dangerous strings in the folded spec:

- `maez_prefers_dissolution` appears only in explicit rejection/removal contexts.
- No folded-spec references remain to `mapped safely`, `if health is wired`,
  `if implemented`, `owner/operator-private`, `operator-private selection`,
  `subject_handle_hash`, `actor_handle_hash`, or `bonded_user_subject_hash`.

## Non-Blocking Notes

S6 still has expected v1 limitations, but they are named rather than hidden:

- local bonded-user-private storage does not stop a privileged OS operator from
  reading files;
- validation snapshots cannot defeat a raw privileged rewrite of every capsule
  file plus the snapshot;
- S6 v1 validates successor-governance grammar, but does not activate
  succession or unlock archives;
- no v1 path is grandmother-compatible.

These are not engineering blockers because the spec states them as limitations
and the implementation order does not depend on pretending they are solved.

## Verdict

RATIFY closure on the Codex engineering lane. With the Claude covenant
second-fold also at RATIFY closure, S6 is clear for canonicalization as Decision
33 / ADR 0038.

Plain English: the folded S6 spec is buildable now. The paperwork has a clear
grammar, the signatures say exactly who can author what, low-entropy human
handles are not exposed as guessable hashes, selective memory access has a
content-free selection pointer, and the tests name the walls the implementation
must build. The design is ready to become law before code starts.
