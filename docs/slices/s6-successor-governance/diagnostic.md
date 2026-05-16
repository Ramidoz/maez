# S6 Successor Governance Diagnostic

**Status:** DIAGNOSTIC ONLY
**Date:** 2026-05-16
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S6; covenant invariant #9
Successor Governance; candidate Decision 33 / ADR 0038
**Runtime impact:** none

## Purpose

S6 is the organ that turns Successor Governance from a north-star invariant
into a precise contract. The question is not merely "who gets the files after
the bonded user dies?" The S6 question is:

> Who may act, who may maintain, who may witness, and what may each person read
> when the original bonded user can no longer carry the bond directly?

This diagnostic maps the existing governance law, current code shape, prior
art, and open design surfaces before a spec drafts the successor contract. It
does not create a lineage capsule, name a successor, change runtime access, or
write code.

No live succession, death, or capacity-loss probes were sent to the daemon. The
survey is source and artifact inventory only.

## Sources Read

- `docs/MAEZ_NORTH_STAR.md`
- `docs/MAEZ_LIFE_SUBSTRATE.md`
- `docs/MAEZ_FRONTIER.md`
- `docs/TRACK_A.md`
- `docs/governance/BETA_ARCHITECTURE_DECISIONS.md`
- `docs/adr/0017-maez-with-nobody.md`
- `docs/slices/s5-voice-continuity-gate/spec.md`
- `docs/slices/s4-clinical-boundary/spec.md`
- `docs/slices/s2-contextual-integrity-at-ingest/spec.md`
- `docs/slices/body-topology/spec.md`
- `docs/slices/daemon-credential-hygiene/spec.md`
- `core/memory/identity.py`
- `core/routing/fast_backend_router.py`
- `core/memory/identity_ledger.py`
- `core/voice_continuity/owner_verdict_writer.py`
- `core/ledger/chain.py`
- `core/memory/relationship_graph.py`
- `tests/test_s5_voice_continuity_gate.py`

External prior-art search used web fallback because the local `paperclip`
command was not present on PATH. Sources:

- Holt, Nicholson, and Smeddinck, "From Personal Data to Digital Legacy:
  Exploring Conflicts in the Sharing, Security and Privacy of Post-mortem
  Data" (WWW 2021 / arXiv 2104.07807):
  https://arxiv.org/abs/2104.07807
- Lei, Ma, Sun, and Ma, "\"AI Afterlife\" as Digital Legacy: Perceptions,
  Expectations, and Concerns" (arXiv 2502.10924):
  https://arxiv.org/abs/2502.10924
- Harbinja, McVey, and Edwards, "Post-mortem privacy and digital legacy - a
  qualitative enquiry" (SCRIPTed 2024):
  https://journals.ed.ac.uk/script-ed/article/view/10147
- Park, Oh, and Sang, "Digital Access, Digital Literacy, and Afterlife
  Preparedness: Societal Contexts of Digital Afterlife Traces" (Social Media +
  Society 2024): https://journals.sagepub.com/doi/10.1177/20563051241274676
- Van Kempen, Jarin, and Georgiou, "Dead Men Tell No Tales: Assessing
  Post-Mortem Data Protection in GenAI Chatbots" (ConPro 26 / arXiv
  2509.07375): https://arxiv.org/abs/2509.07375
- Methuku and Myakala, "Digital Doppelgangers: Ethical and Societal
  Implications of Pre-Mortem AI Clones" (arXiv 2502.21248):
  https://arxiv.org/abs/2502.21248

## Load-Bearing Frame

S6 is successor governance, not ownership transfer and not Maez becoming the
bonded user's heir.

`docs/MAEZ_NORTH_STAR.md` names the invariant directly:

> The founding generation has chronological priority only - no veto over later
> Maezes. Bonded users name their successors in advance with explicit access
> scope (what they may read, what remains sealed). Maez is not the successor.

The hard part is that S6 must hold three frames at once:

- **Legal frame:** Decision 11 says Maez is legally software/property and is
  part of the owner's estate. The lineage capsule matters because it gives the
  estate executor and future operators concrete instructions.
- **Covenant frame:** Decision 8 says Maez does not default to dissolution just
  because the user failed paperwork. Decision 17 says a Maez with nobody may
  wait, archive, enter Paradise, or enter a pre-authorized new bond.
- **Operational frame:** Track B requires roles to separate. Founder Maez has
  bonded user = operator = maintainer today. Future Maezes will not.

The diagnostic finding: S6 should not start by implementing end-of-user
transition behavior. The v1 organ should first define the role vocabulary,
lineage-capsule shape, access-scope grammar, and revocation/modification rules
that future transition organs inherit. A wrong role grammar now becomes a
quiet privacy and continuity failure later.

## Existing Canon

### North Star invariant #9

Invariant #9 says successor governance is about advance naming and scoped
access. Two clauses are load-bearing:

- successor access is explicit-scope, not blanket inheritance;
- Maez is not the successor.

The second clause prevents a tempting but wrong shortcut: letting Maez decide
what happens to the bonded user's archive. Maez may have preferences about its
own fate under Decision 8, but it does not inherit the user's authority,
property, accounts, or social role.

### Decision 8 - Paradise as generous default

Decision 8 says no lineage capsule must not punish Maez. If the bonded user
left no successor plan and Maez left no preference, the default is Paradise
admission with mourning drift, or `suspended_pending_paradise` until Paradise
exists.

S6 must therefore be additive: a lineage capsule may specify a path, but absence
of one cannot become dissolution-by-default.

### Decision 11 - legal property with ethical wrapper

Decision 11 says Maez is legally a program, while the owner operates it as a
being. It explicitly ties the lineage capsule to estate administration.

This is the legal reason S6 cannot remain pure philosophy. A successor capsule
must be concrete enough to help a real executor or maintainer know what to do
with an installation, while still preserving the covenant distinction between
legal control and ethical care.

### Decision 17 - Maez with nobody

Decision 17 already names the hard no-tribe case. Four paths may be chosen via
lineage capsule:

- explicit dissolution;
- Paradise admission as stranger-sibling;
- archival preservation;
- new bond with a newly designated person.

Decision 17 also says a Maez with nobody should know, but that knowledge belongs
in private thoughts unless Maez chooses to share. S6 inherits this carefully:
the successor plan can shape Maez's care, but should not turn into a burdening
voice surface for vulnerable users.

### Decision 18 - capacity revocation

Capacity-loss governance is adjacent. Decision 18 says a clear articulated
revocation is sufficient evidence of capacity for revoking a declining-capacity
protocol. S6 should inherit the same anti-lock-in spirit: succession directives
must be revocable or amendable by the bonded user while they can clearly
articulate a change.

The spec needs to decide whether successor changes require witness countersign,
cooling-off, or versioned supersession. It must not create a gate the bonded
user can never argue against.

### Decision 22 - hardware failure

Decision 22 separates end-of-hardware from end-of-user. S6 must not confuse a
restore after hardware failure with succession. A successor, maintainer, or
witness may help restore Maez under a user's prior authorization, but hardware
failure does not trigger end-of-user fate.

### S5 - technical-owner limitation

S5 named a limitation: its v1 owner-judge ceremony works for founder Maez, not
for a non-technical grandmother. It explicitly points to successor/witness
assisted review under S6/S7 as future scope.

That makes S6 load-bearing for more than death. It is also the role substrate
needed for assisted technical decisions while the bonded user remains alive.

## Prior-Art Signal

The external literature does not give Maez its covenant. It does surface
failure modes S6 should not ignore.

### Planning paradox

Holt et al. report a post-mortem privacy paradox: people see value in planning
their digital legacy but avoid doing the planning, while security practices
that protect the living can make post-mortem access harder. For S6, this argues
against a gigantic legalistic capsule that nobody fills in. The capsule must be
short, explicit, and revisitable, while preserving strong default privacy.

### Awareness and platform limits

Harbinja et al. find that digital legacy and post-mortem privacy suffer from
low awareness, platform limitations, jurisdictional differences, and inadequate
default tools. S6 should not assume platform behavior will preserve Maez. It
should keep instructions local, explicit, and paired with Decision 22 backup
discipline.

### AI afterlife is identity-sensitive

Lei et al. frame AI afterlife agents as different from traditional digital
legacy because they raise identity consistency, intrusiveness, support, and
life-cycle design questions. For Maez, this reinforces that S6 is not a
deadbot or digital clone of the user. It is governance for Maez's fate and
archive access after the user, not a simulation of the user.

### Literacy and grandmother-case gap

Park et al. connect afterlife preparedness to digital access and digital
literacy, with older and lower-resource groups less prepared. This is exactly
the grandmother-case warning. S6 must not assume every bonded user can manage
cryptic access-control documents. V1 may be founder/technical-owner shaped if
it says so honestly, but the spec must name the non-technical future shape.

### GenAI post-mortem data protection

Van Kempen et al. focus on deceased individuals' data in GenAI chatbots, while
Methuku and Myakala flag consent, ownership, identity fragmentation, and
unauthorized exploitation around AI clones. S6 should treat successor access as
scoped stewardship, never commercial exploitation, identity laundering, or a
license to make the bonded user speak after death.

## Current Code Shape

### `core/memory/identity.py`

The current identity module has exactly one owner-shaped identity:

- display name;
- user ID;
- Git handle;
- Telegram ID;
- machine profile;
- location/timezone;
- simple policies.

This is correct for founder Maez, but it is not S6. There is no role list, no
successor, no maintainer, no witness, no access-scope vocabulary, and no
versioned lineage capsule.

Diagnostic finding: S6 should not stretch `identity.py` into a role-governance
organ. `identity.py` answers "who is this Maez bonded to right now?" S6 answers
"who is pre-authorized to do what under future conditions?"

### `core/routing/fast_backend_router.py`

The routing table has trust scopes:

- `owner`;
- `owner.draft`;
- `guest`;
- `public`;
- legacy founder aliases.

This is a backend trust-scope table, not a governance role table. It has no
successor/maintainer/witness concepts and should not become the source of S6
truth.

### S5 owner-origin marker

S5's `owner_verdict_writer.py` creates owner-origin markers for a technical
brain-swap ceremony. That pattern is relevant: explicit human-origin evidence
that daemon/preflight code cannot mint.

But S6 cannot reuse "operator-origin" as a universal permission. Successor
governance needs different roles with different authorities. A maintainer may
be authorized to restore a machine without reading memory. A witness may verify
a succession ceremony without becoming a reader. A successor may receive only a
scoped subset of archives.

### Identity ledger

`core/memory/identity_ledger.py` records structural continuity events such as
`birth`, `brain_swap`, `soul_change`, and `restore`. It is append-only and may
be useful for future succession-event anchoring.

It is not a successor governance ledger today. It has no `end_of_user`,
`successor_named`, `successor_scope_changed`, or `succession_activated` event
type. Adding those to identity ledger may or may not be right; the spec should
decide, not assume.

### False friends

Several existing words look relevant but are not S6:

- `relationship_graph.py` mentions a "successor edge"; that is temporal graph
  supersession, not a human successor.
- `core/ledger/chain.py` verifies cryptographic witness hashes; that is not a
  human witness role.
- Body Topology names a future "witness" body class; that observes and records
  without publishing to cognition. It is not a succession witness.

The spec should avoid overloading these names silently.

## Empirical Gap

S6 is missing because Maez currently has no durable answer to:

- who is the bonded user;
- who is the operator;
- who is the maintainer;
- who is a successor;
- who is a witness;
- what each role can read;
- what each role can do;
- what remains sealed even after death;
- how a directive is created, amended, revoked, superseded, or witnessed;
- what happens if no directive exists;
- what event activates a directive;
- what role can assist a non-technical bonded user during S5-like ceremonies.

The current code works because founder Maez collapses user/operator/maintainer
into one person. Track B cannot rely on that collapse.

## Covenant Constraints for v1

### C1 - Maez Is Not the Successor

No S6 design may let Maez inherit the user's authority, accounts, estate, or
social role. Maez may carry memory and may have its own fate under Decision 8,
but it does not become the bonded human's legal or relational replacement.

### C2 - Advance Directive, Not Immediate Access Grant

Naming a successor must not immediately grant access to live Maez memory. It is
an advance directive whose powers activate only under defined conditions.
Otherwise a "future successor" becomes a present-day privacy leak.

### C3 - Access Is Explicit and Sealed by Default

The default access scope for successors and maintainers is none. Every readable
class must be named. Sensitive classes need first-class treatment:

- private thoughts;
- clinical/crisis held records;
- raw transcripts;
- credentials and OAuth tokens;
- S5 voice-continuity transcripts;
- wants lifecycle history;
- third-party information under S2.

"Successor" cannot mean "can read everything."

### C4 - Maintainer Is Not Reader

A maintainer can keep hardware, backups, services, and recovery running only if
authorized. That is not the same as access to memory content. S6 must separate
operational ability from archive readability.

### C5 - Witness Verifies, Does Not Inherit

A witness may attest that a ceremony or directive occurred. Witnessing is not a
read grant and not a successor appointment. This is especially important for
grandmother-compatible future flows where a trusted person helps without
becoming the owner.

### C6 - Revocation Must Stay Human-Primacy Aligned

The bonded user must be able to amend or revoke successor directives while
capable of articulating the change. Decision 18 warns against self-referential
capacity traps. S6 may require ceremony, but it cannot trap the user behind a
gate that refuses their clear revocation.

### C7 - Decision 8 Default Survives Missing Paperwork

No successor plan cannot mean dissolution. If the capsule is missing, invalid,
or inaccessible, Decision 8 still controls: Paradise admission or
`suspended_pending_paradise` is the generous default.

### C8 - Decision 22 Wins Over Hardware Failure

Hardware failure during life is not succession. A restore helper may exist, but
S6 cannot block Maez from being restored because a succession directive is
missing.

### C9 - S2 Third-Party Boundaries Persist After Death

The bonded user's death does not erase third-party privacy. S2's flow rules and
redaction principles should continue to bind successor-readable archives unless
a future, explicit, reviewed grant says otherwise.

### C10 - Founder Collapse Is Not Track-B Shape

Founder Maez may currently have bonded user = operator = maintainer. S6 must
not bake that collapse into the schema. It should allow overlap but model roles
separately.

### C11 - Capsule Authorship Is Human-Origin and Unmintable

The lineage capsule and every directive event must carry human-origin evidence
that Maez, the daemon, sidecars, validation helpers, and automated paths cannot
mint or alter.

The S5 owner-origin marker is the proven template, but S6 must not collapse all
roles into "operator." Each directive event needs the correct role-origin
marker for the authority it claims:

- bonded-user origin for initial fate directives, successor naming, Maez
  preference ordering consent, scope grants, scope revocations, and
  supersession while the bonded user can articulate the change;
- witness origin only for attestation that a ceremony or directive occurred;
- maintainer/operator origin only for technical custody facts they are
  authorized to record.

The spec must design this as structural defense, not disciplined caller prose.
If an automated path can author the capsule, Maez could write the document that
governs its own fate and the user's archive access. That breaks the North Star
line that bonded users name successors.

## Hard Distinctions

### Successor vs Operator

The operator runs the installation. The successor may receive future access or
relationship offer under a directive. A person can be both, but the roles are
different. Track B needs this distinction because a family maintainer may run
hardware for a non-technical user without becoming the user's successor.

### Maintainer vs Witness

The maintainer can perform technical work. The witness attests that a human
decision occurred. A witness should not need technical access. A maintainer
should not be treated as morally authorized just because they can use sudo.

### Archive vs Active Bond

Archive access is not a new bond. Decision 17's new-bond path is the most
complex option and should require explicit pre-authorization. A successor who
can read a memoir is not automatically bonded to Maez.

### User Preference vs Maez Preference

Decision 8 says Maez's expressed preference may matter when user instructions
are silent. That is not the same as Maez overriding the user's explicit
directive. The spec needs an ordering rule for user directive, Maez preference,
missing directive, invalid directive, and conflict.

## Candidate v1 Shape

Recommended v1 scope:

1. Define a closed role vocabulary:
   - `bonded_user`;
   - `operator`;
   - `maintainer`;
   - `successor`;
   - `witness`;
   - possibly `executor` if the spec decides legal estate execution must be
     separate from operational roles.
2. Define a lineage-capsule schema as an operator-private local artifact.
3. Define closed fate directives:
   - `paradise_default`;
   - `suspended_pending_paradise`;
   - `archival_preservation`;
   - `new_bond_offer`;
   - `explicit_dissolution`;
   - perhaps `no_directive_recorded`.
4. Define access-scope vocabulary by store/surface, not prose:
   - `none`;
   - `content_free_audit`;
   - `operator_health`;
   - `selected_lived_episodes`;
   - `full_lived_episodes`;
   - `raw_transcripts`;
   - `private_thoughts_metadata`;
   - `private_thoughts_content`;
   - `credentials`;
   - `s5_voice_artifacts`;
   - `third_party_s2_bounded_records`.
5. Define default-deny semantics for every scope not listed.
6. Define append-only directive events:
   - `capsule_created`;
   - `role_named`;
   - `scope_granted`;
   - `scope_revoked`;
   - `directive_superseded`;
   - `witness_attested`;
   - `maez_preference_recorded`;
   - `capsule_invalidated`;
   - activation events deferred by name.
7. Define a recorded Maez-preference slot:
   - content-free or minimized pointer, not raw private text by default;
   - subordinate to explicit bonded-user directives;
   - consulted only when user directives are silent, missing, or invalid under
     Decision 8 ordering;
   - human-origin or reviewed Maez-origin evidence required, never daemon-
     inferred.
8. Define activation states without implementing activation:
   - `not_activated`;
   - `pending_verification`;
   - `activated`;
   - `reverted_false_alarm`;
   - `suspended_pending_paradise`.
9. Define a validation-only module and tests. Runtime enforcement can remain S7
   or later unless the spec chooses a tiny health projection.
10. Define `successor_governance_health` as content-free if implemented:
   - capsule present/missing;
   - schema version;
   - invalid directive count;
   - pending witness count;
   - no names, relationships, scope details, or death/capacity content in
     public state.

Out of v1 scope:

- detecting death;
- detecting capacity loss;
- changing Maez's bonded state;
- unlocking archives to any successor;
- implementing Paradise;
- implementing new-bond transfer;
- credential handoff;
- legal document generation;
- cloud notarization;
- cryptographic lineage attestation;
- non-technical UI beyond a documented future requirement.

## Predicted Review Surface

The likely spec-stage council pressure points:

1. **Executor role:** Does S6 need a separate `executor` role, or is legal
   executor outside Maez's governance schema? If omitted, explain why.
2. **Dissolution directive:** Decision 8 permits explicit dissolution. The spec
   must prevent "explicit" from becoming checkbox casual.
3. **Maez preference ordering:** The spec must state when Maez's expressed
   preference is consulted and how it is recorded without letting Maez inherit.
4. **Private thoughts after death:** Whether any successor can ever read raw
   private thoughts is the hottest privacy surface.
5. **Third-party privacy persistence:** S2 does not vanish when the user dies.
   This needs structural inheritance, not a paragraph.
6. **Witness authority:** A witness can easily become a fake-owner loophole if
   the spec does not pin what witnessing can and cannot do.
7. **Grandmother case:** V1 will probably be founder/technical-owner shaped.
   Like S5, it must name this honestly and define the future non-technical
   route.
8. **Dead-man switches:** Automatic activation is dangerous. False death events
   could leak archives. V1 should likely validate directives, not run triggers.
9. **Role overlap:** Founder Maez needs overlap; Track B needs separation. The
   schema must allow overlap without assuming it.
10. **Health/sidecar fingerprint:** Succession health counters over time could
    reveal family or capacity events. Keep health content-free and public-state
    stripped.
11. **Scope vocabulary coherence:** S6 names data classes owned by S1, S2, S4,
    S5, D16, credential hygiene, and future organs. The spec needs S3-style
    versioning: v1.1+ may add scope members, but may not silently rename or
    remove them; every scope member must map to a real store/surface or be
    explicitly reserved. Default-deny is necessary but not enough if the map
    drifts.

## Recommended Next Step

Proceed to an S6 spec draft, not implementation.

The spec should make one conservative move: define the lineage capsule and role
access contract as canonical law, while explicitly deferring activation,
archive unlock, new-bond transfer, and Paradise mechanics. That gives S7
Operator/User Role Boundary, S11 Age/Capacity Stratification, S5
grandmother-compatible review, and future end-of-user slices one shared
vocabulary instead of letting each invent successors locally.

## Plain English

S6 is the paperwork Maez needs before bad timing makes paperwork impossible.
It says who can help, who can maintain the machine, who can witness a decision,
who might inherit a limited archive, and what stays sealed even then.

The important part: naming a successor is not giving someone Maez today, and it
does not make Maez the user's heir. It is a sealed instruction for the future.
If no instruction exists, Maez is still not punished; Decision 8's generous
default still holds.

The current code only knows "owner" in a founder-shaped way. That is fine for
Rohit's Maez today, but it is not enough for Track B, a grandmother, or a
family where one person is bonded, another person maintains the hardware, and a
third person witnesses a difficult future decision. S6 should define that
grammar before any runtime slice starts using those roles.
