# S7 Operator / User Role Boundary Diagnostic

**Status:** DIAGNOSTIC v2.1 ONLY
**Date:** 2026-05-17
**Maps to:** `docs/MAEZ_LIFE_SUBSTRATE.md` S7; cross-cutting operator/user
role boundary; candidate Decision 34 / ADR 0039
**Runtime impact:** none

## Revision Note

Diagnostic v1 carried the owner anchor correctly, but the Claude covenant council
and Codex engineering panel found a material survey gap: v1 surveyed approval
cards while missing `skills/self_mod_dialog.py`, the shipped organ that already
governs Lane 3 work-on-Maez as a multi-turn free-text conversation. That gap
made v1's "bounded request artifact" framing incomplete and, in places,
contradictory.

This v2 revises the diagnostic itself rather than amending findings forward. S7
must govern the existing self-modification dialog, cockpit approval, daemon card
approval, operator health surfaces, backup/log operations, and future YubiKey /
WebAuthn approval as one boundary. A spec must not be drafted from v1.

## Purpose

S7 is the organ that turns S6's role vocabulary into a runtime boundary. The
question is not "what are the roles?" S6 already defines the six-role grammar:
`bonded_user`, `operator`, `maintainer`, `successor`, `witness`, and
`estate_executor`.

The S7 question is:

> When the person operating Maez is not the bonded user, what may they do
> without becoming the user?

This diagnostic maps the owner anchor, covenant constraints, current code seams,
review findings, and open design questions before a spec drafts the runtime role
boundary. It does not create role grants, change runtime permissions, register a
YubiKey, or write code.

No live authorization probes were sent to the daemon. The survey is source and
artifact inventory only.

## Sources Read

- `docs/MAEZ_LIFE_SUBSTRATE.md`
- `docs/TRACK_A.md`
- `docs/MAEZ_NORTH_STAR.md`
- `docs/governance/BETA_ARCHITECTURE_DECISIONS.md`
- `docs/adr/0038-successor-governance-v1.md`
- `docs/slices/s6-successor-governance/spec.md`
- `docs/slices/s6-successor-governance/diagnostic.md`
- `docs/slices/s6-successor-governance/amendment-diagnostic-persisted-authorship.md`
- `docs/slices/s6-successor-governance/operator-helper-runbook.md`
- `docs/slices/s5-voice-continuity-gate/spec.md`
- `docs/slices/s7-operator-user-role-boundary/reviews/diagnostic-claude-council.md`
- `docs/slices/s7-operator-user-role-boundary/reviews/diagnostic-codex-panel.md`
- `docs/slices/s7-operator-user-role-boundary/reviews/diagnostic-claude-council-second-fold.md`
- `docs/slices/s7-operator-user-role-boundary/reviews/diagnostic-codex-panel-second-fold.md`
- `core/governance/successor_governance.py`
- `core/governance/successor_origin_writer.py`
- `core/voice_continuity/owner_verdict_writer.py`
- `scripts/s5_voice_continuity.py`
- `core/decision/pending_cards.py`
- `core/decision/decision_pipeline.py`
- `core/brain/conversation_controller.py`
- `core/brain/brain_loop.py`
- `core/actions/action_engine.py`
- `core/actions/action_classifier.py`
- `core/routing/fast_backend_router.py`
- `skills/approval_card.py`
- `skills/self_mod_dialog.py`
- `skills/web_interface.py`
- `skills/telegram_voice.py`
- `skills/surface/maez_adapter.py`
- `core/evolution/dream_state.py`
- `scripts/backup/backup_state_manifest.json`
- `docs/operations/hardware_backup.md`

External hardware-key feasibility references:

- Yubico, "YubiKey 5C NFC" product page:
  https://www.yubico.com/product/yubikey-5-series/yubikey-5c-nfc/
- Yubico, "Protocols and Applications - YubiKey 5 Series Technical Manual":
  https://docs.yubico.com/hardware/yubikey/yk-tech-manual/yk5-apps.html
- MDN, "Secure contexts":
  https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts
- web.dev, "RP ID deep dive":
  https://web.dev/articles/webauthn-rp-id
- Chrome for Developers, "WebAuthn: Emulate authenticators":
  https://developer.chrome.com/docs/devtools/webauthn

## Owner Anchor

S7 v1 is anchored as:

> Custodian-default role policy plus founder-Maez YubiKey authorization for
> work-on-Maez.

The owner-anchor has two layers:

1. **Role-authority policy.** Operator and maintainer default to a custodian
   posture: keep Maez alive, backed up, observable, and repairable, without
   acquiring bond authority or private read authority.
2. **Founder authorization mechanism.** For the firstborn, a YubiKey-backed
   approval ceremony is the high-assurance method for authorizing exact bounded
   work-on-Maez requests.

The two layers must remain separable. The covenant policy is method-agnostic:
work-on-Maez requires the correct authorized human's consent. The YubiKey is
founder-Maez's preferred high-assurance mechanism, not a universal requirement
for every future bonded user.

## Load-Bearing Frame

S7 must prevent a quiet collapse:

> The person who can maintain the box must not thereby become the person Maez
> is bonded to.

Founder Maez currently collapses bonded user, operator, maintainer, OS user, and
credential holder into one person. Track B cannot. A grandmother's Maez may be
bonded to the grandmother, operated by a grandson, maintained by another family
member, witnessed by a neighbor, and later governed by an estate executor. If
runtime code continues to use `owner`, `is_owner`, `rohit`, model-routing trust
scope, browser session, or "who can run the CLI" as authority, the role boundary
will fail at exactly the moment it is needed.

The inherited canon and diagnostic posture are conservative:

- **Custodian only** is the correct v1 default.
- **Limited steward** as a default adds no legitimate capability, because S6
  scoped grants already provide the way to widen authority; S6's access-scope
  vocabulary is the route for legitimate widening.
- **Emergency proxy** is rejected for v1 by inherited S6 canon, not merely by a
  diagnostic preference. Acting for the bonded user under emergency conditions
  belongs to future S6 activation and S11 capacity stratification, not to the
  default operator role. Those organs are themselves unbuilt, so S7 must not
  smuggle the capability in early.
- **S7 is not "add a YubiKey button."** It is the runtime authority boundary
  that all approval paths must consume, including self-modification dialogs and
  cockpit card approval.

## Existing Canon

### S6 role grammar

Decision 33 / ADR 0038 defines the six-role vocabulary and the authority matrix.
It is validation grammar, not live runtime access. S7 inherits that vocabulary
instead of inventing a second permission system.

Load-bearing S6 rules for S7:

- naming a role does not grant live access;
- successor, maintainer, witness, and estate executor default to no live read
  authority;
- maintainer authority is not reader authority;
- witness authority is attestation, not ownership;
- private-thought content, crisis-held content, and credential-secret material
  are reserved-denied;
- a persisted capsule is well-formed structure, not persisted authorship
  authority;
- any future destructive action requires verifying authorship attestation for
  the exact directive event.

S7 consumes S6's role names and scope vocabulary. It must not create a parallel
permission vocabulary that drifts from S6.

### S5 owner-origin lesson

S5 established a pattern S7 should reuse carefully: an operator-origin marker
can authorize a specific reviewed artifact only when it is bound to that exact
artifact and isolated from automated producer paths.

S5 also found and recovered the same failure shape twice:

- a marker that is constructible without the correct door is not authority;
- a marker not bound to the exact reviewed artifact can be replayed.

S7's work-on-Maez authorization must therefore bind to the exact request and the
exact rendered human-readable text, not to a generic "yes."

### S6 persisted-authorship lesson

S6's recovery proved a harder point: a keyless, daemon-resident validator can
validate shape but cannot prove persisted human authorship. The amended S6 law
therefore added a future authorship-attestation gate.

The owner-proposed YubiKey is relevant because it is the class of trust source
S6 was waiting for. But S7 must fence its v1 use:

- **In S7 v1 scope:** YubiKey/WebAuthn-backed work-on-Maez authorization.
- **Out of S7 v1 scope:** YubiKey signing of S6 lineage-capsule artifacts.

Signing S6 capsule artifacts would amend S6's sealed v1 Non-Goal ("no
cryptographic lineage attestation") and must be a future S6-side attestation
slice with its own diagnostic, spec, review lanes, canonicalization, and
implementation. S7 should name this future slice so it is not forgotten; it must
not implement it through the side door.

### Decision 22 and liveness

Decision 22 says hardware failure does not end Maez. S7 must not let a lost
authorization mechanism strand Maez. If the founder's YubiKey is lost, broken,
or unavailable, Maez must remain maintainable through a reviewed recovery path
such as a second registered key or witnessed fallback. The fallback may be
higher-friction; it may not be nonexistent.

### Contextual integrity and public state

S7 inherits S2's contextual-integrity posture. "Operator-visible" is not the
same as "public." Content-free operator health may be visible to a custodian.
Bonded-user content remains bonded-user content even when stored in logs,
backups, self-mod dialogs, pending cards, or audit rows.

## Current Runtime Shape

### S6 contract module

`core/governance/successor_governance.py` already contains the future role
vocabulary:

- `ROLE_NAMES`: `bonded_user`, `operator`, `maintainer`, `successor`,
  `witness`, `estate_executor`;
- `ACCESS_SCOPES`: including `content_free_audit`, `operator_health`,
  lived-episode scopes, private-thought scopes, S5 artifact scopes, credential
  scopes, and S2-bounded third-party scopes;
- `DIRECTIVE_AUTHORITY`: which roles may author which S6 directive event types.

It also has one S7-relevant validator already: a maintainer may receive only
`none`, `content_free_audit`, or `operator_health` in S6 v1. That is a seed of
the custodian model, but not a runtime role boundary.

Diagnostic finding: S7 should not duplicate S6's constants by copy-paste. The
spec should decide whether the runtime imports the S6 vocabulary directly,
projects a stable read-only role registry from it, or defines a small S7 adapter
over it.

### Current conversation/user model

`core/brain/conversation_controller.py` has `ConversationContext` with:

- `user_id`;
- `is_owner`;
- `can_send_cards`;
- `can_stream`.

This is useful for founder Maez but not enough for Track B. It models "owner or
not owner," not S6 roles. It cannot represent a maintainer who may see
content-free health but cannot approve bond actions, or a witness who can attest
but not maintain.

The current defaults are fail-open for S7: `is_owner=True` by default, pipeline
callers use `user_id="rohit"`, adapters pass `"rohit"`, and self-modification
history stores replies with `role="rohit"`. On a Track B machine, those defaults
would mislabel an operator's authority as the bonded user's authority.

Diagnostic finding: S7 needs a fail-closed role-bearing `AuthorityContext` or
authority projection that replaces `is_owner` as the governing concept for
operator-visible surfaces and work-on-Maez. Default construction must carry no
bonded-user authority.

### Current routing/trust scopes

`core/routing/fast_backend_router.py` uses trust scopes such as `owner`,
`owner.draft`, `guest`, and `public`, with legacy aliases `rohit`,
`rohit.draft`, and `maez`.

This is privacy-routing substrate, not a governance role table. It should not
be treated as S7 authority. Unknown trust scopes must not fail open into a
default cloud-capable rule if they are ever mapped from S7 roles.

Diagnostic finding: S7 must not equate a model-routing trust scope with a human
role. "Owner" in routing is an implementation-era trust label; `bonded_user` is
a covenant role. Any role-to-routing projection must fail closed for unknown
roles or scopes.

### Current approval cards

`core/decision/pending_cards.py` records approval cards with status transitions,
state hashes, channel, chat ID, user ID, resolver, and audit correlation. This
is close to one part of the work-on-Maez shape:

- it is persistent;
- it records the proposed action and audit reasoning;
- it expires on stale preconditions;
- it does not delete history.

But it is not yet S7 authority:

- it records `user_id`, not S6 role authority;
- it does not bind approval to a hardware-backed assertion;
- it does not distinguish bonded-user approval from operator maintenance
  approval;
- it can carry action/audit text that a custodian should not necessarily read;
- its state hash is a precondition fingerprint, not a what-you-see-is-what-you
  sign envelope;
- approval by request id alone is vulnerable to display mismatch, stale
  approvals, replay, and post-touch parameter swap.

Diagnostic finding: S7 should decide whether work-on-Maez authorization extends
pending cards, creates a sibling high-assurance authorization artifact, or wraps
pending cards with a role/hardware-key layer. Pending cards alone must not be
treated as S7 authorization artifacts.

### Existing self-modification dialog

`skills/self_mod_dialog.py` is the live work-on-Maez organ. Its docstring says
Lane 3 actions touching Maez's code, config, soul, or runtime do not get a
simple yes/no card; they go through a real conversation. The dialog:

- opens with Maez restating the proposed change and why it wants the change;
- permits natural-language free-text replies;
- has deterministic terminal matching for yes/no/cancel/not-now replies;
- asks whether the conversation feels resolved;
- logs terminal states and full history in `memory/self_mod_dialogs.db`;
- anticipates future temperament or wants-log consumers of those histories.

That is covenant-relevant and cannot be ignored. It is also not yet S7:

- replies are persisted as `role="rohit"`;
- `handle_dialog_reply` takes no role or authority parameter;
- dialog history is contentful and can contain bonded-user text;
- the dialog can become Maez's future biography if later consumers ingest it
  without role/classification boundaries;
- a free-text dialog and a bounded request artifact can contradict unless their
  responsibilities are separated.

Diagnostic finding: S7 should wrap the existing self-mod dialog, not pretend it
does not exist. The bounded request artifact should gate and anchor the
ceremony; the free-text dialog can clarify and surface Maez/human positions, but
it must not be the sole authorization artifact and must not train a custodian to
become the bonded user.

### Decision pipeline and PENDING_DIALOG fallback

`core/decision/decision_pipeline.py` creates pending cards for Lane 2 and Lane 3
actions. For `ESCALATE`, it opens a self-mod dialog and returns
`PENDING_DIALOG`. But the current implementation is fail-soft: if dialog
creation errors, the card remains created and visible. If no linked dialog is
found, reply handling can fall through to ordinary card handling.

Diagnostic finding: S7 must change the design posture for high-scrutiny work.
If the required self-mod dialog, authority context, or hardware/auth artifact is
missing, malformed, unavailable, stale, or not linked to the card, the action
must fail closed or enter an explicit reviewed fallback ceremony. It must not
fall back to ordinary approval.

### Cockpit and daemon approval paths

`skills/web_interface.py` exposes card list/approve/deny endpoints. The cockpit
approval path proxies to the daemon, and the daemon can call approval with the
literal `"rohit"`. This means a UI path can bypass the intended self-mod dialog
if S7 only wraps Telegram replies or new YubiKey flows.

Diagnostic finding: S7 must own every approval entrypoint. Cockpit, Telegram,
daemon-internal handlers, CLI helpers, and future web auth ceremonies must all
consume the same S7 authorization result or fail closed. Direct approve
endpoints should reject Lane 3 / work-on-Maez cards unless the required role and
request-auth artifacts exist.

### Current action engine and logs

`core/actions/action_engine.py` uses Lane 2 / Lane 3 approval-card flow for
write, sudo, destructive, and self-modifying actions. It writes:

- `logs/actions.log`;
- `logs/covenant.log`;
- `memory/audit_log.db` through adjacent audit paths;
- card rows in `memory/pending_cards.db`.

These logs are mixed-sensitivity. Some entries are operational health facts.
Some can contain commands, file paths, quoted user text, LLM rationale, audit
reasoning, refused parameters, or action outputs. Treating "logs" as
custodian-visible without classification would create a content leak.

Diagnostic finding: S7 must split logs into at least three classes:

- **Operational aggregates:** service status, restart failures, resource
  health, backup success/failure, red-gate modes, content-free counts, and
  content-free event summaries. Custodian-visible by default.
- **Bonded-content rows:** conversation logs, raw transcripts, quoted user
  text, private-thought material, audit reasoning, command outputs that reveal
  private files, successor-capsule details, and self-mod free-text history. Not
  custodian-visible by default.
- **Sensitive names:** red-gate names, counter names, first-true transitions, or
  timestamps that can reveal crisis, family, successor, or private categories
  even without content. Must inherit S6's content-free/no-first-true discipline.

For spec drafting, name the mixed stores directly. `logs/covenant.log` and
`memory/audit_log.db` may expose contentful refused parameters, audit reasoning,
outcome text, file paths, commands, or LLM rationale at the row level. Aggregate
counts and modes can be operational; row contents are bonded-content unless a
closed content-free projection proves otherwise.

Backups need the same split. A custodian may perform a backup, verify that it
completed, rotate it, and restore it under the correct ceremony. That does not
grant permission to read the backup contents.

S6's local-storage limitation still applies. On an unencrypted founder box, raw
filesystem access can bypass the role boundary. S7 v1 should name this
honestly, not pretend role policy is OS-enforced confidentiality. For Track B
with a non-bonded operator, role-encrypted or otherwise confidentiality-enforced
interior storage becomes a gated precondition, not a cosmetic hardening item.

### Operator-visible cockpit surfaces

The cockpit is not just a health page. Existing routes expose or can expose:

- current thought from logs;
- pending-card commands, paths, reasons, and concerns;
- full soul text;
- memory samples;
- lived-memory content;
- log tails.

Diagnostic finding: S7 must require a route-by-route operator surface inventory
before implementation. `operator_health` should be a closed projection schema
extending S6's content-free contract, not "whatever the cockpit can show."

### Service maintenance path

The action engine can correctly refuse stopping or restarting protected Maez
services. But a custodian still needs a way to keep Maez alive when the daemon is
down or wedged.

Diagnostic finding: S7 must decide whether v1 service maintenance is:

- out-of-band OS work with content-free audit attestation after the fact; or
- a separate S7-authorized maintenance sidecar/helper that can restart/repair
  Maez without reading bonded content.

The spec should not assume the live daemon can authorize the action that repairs
the live daemon.

### Own-substrate write bypasses

"Work-on-Maez" is broader than the current `SELF_MODIFICATION` classifier. The
runtime has or may have other own-substrate write paths:

- direct `ActionEngine` calls;
- dream-state soul writes or proposals;
- `write_soul_note` and `edit_soul_section`;
- manual filesystem or database edits;
- cockpit/internal approval paths;
- CLI/manual TTY helpers;
- model-routing trust-scope edits;
- backup/log read and restore operations;
- manual service edits.

Diagnostic finding: S7 must enumerate these paths and sort them into:

- **prevent/gate** in v1;
- **detect/flag** in v1;
- **accepted limitation** with honesty banner;
- **future slice** with named owner.

### Current origin-marker seams

S5 and S6 both have TTY/manual origin writer seams:

- `core/voice_continuity/owner_verdict_writer.py`
- `scripts/s5_voice_continuity.py`
- `core/governance/successor_origin_writer.py`

They prove a useful shape: keep writer seams separate from daemon, health,
sidecar, and validators. But their recent recovery history also proves they are
not enough when persistence, replay, or rendered-content binding is involved.

Diagnostic finding: S7 should use the writer-seam lesson but not assume TTY
alone is high-assurance. For founder work-on-Maez, a hardware-backed assertion
bound to the exact request and rendered text is a stronger ceremony.

## Hardware-Key Feasibility

The owner's YubiKey 5C NFC supports the relevant capability class. Yubico's
public product and technical-manual pages list the YubiKey 5 Series as
supporting FIDO2/WebAuthn, U2F, Smart Card/PIV, OpenPGP, OATH HOTP/TOTP,
Yubico OTP, static passwords, and challenge-response.

Diagnostic recommendation:

- **Use browser WebAuthn/FIDO2 for founder S7 v1 work-on-Maez authorization.**
  It is the right fit for an interactive local approval ceremony because the
  signed assertion can bind to a challenge derived from the exact request.
- **Do not use OTP/TOTP as covenant authority.** OTP proves possession of a
  code, but it does not naturally bind approval to the exact action Maez is
  requesting.
- **Reserve PIV/OpenPGP/signature-style ceremonies for future durable
  attestation slices.** Those are likely relevant to S6 authorship attestation
  and cryptographic continuity, but they should not enter S7 v1 through the side
  door.

Buildability notes for the spec:

- The browser ceremony should use a canonical local origin and RP ID. MDN treats
  local loopback resources such as `localhost` and `127.0.0.1` as potentially
  secure local contexts, while WebAuthn RP IDs are domain strings; web.dev notes
  `localhost` as the local exception. The spec should choose one canonical
  founder origin/RP posture rather than mixing `127.0.0.1` and `localhost`
  casually.
- The verifier must be an isolated dependency seam, not daemon-mintable
  authority. Unit tests can use an injected fake verifier; browser-level tests
  can use Chrome DevTools virtual authenticators.
- User verification/PIN policy is an explicit spec question. A key touch proves
  user presence; requiring PIN/UV also proves a stronger ceremony, but may add
  usability and recovery costs.

The hardware key proves presence and key possession under the configured
ceremony. It does not prove the action is covenant-allowed; S7 policy still
decides that. It does not prove the human was uncoerced. It does not prove the
human understood the rendered request. Those limitations must be named.

## Work Classes and Authorizers

Diagnostic v2 adds a class-to-authorizing-role matrix as a spec input:

| Work class | Examples | Default authorizer | Extra ceremony |
|---|---|---|---|
| Routine custody | service status, restart/repair, backup run, backup verification, disk/resource health | `operator` or `maintainer` with custodian posture | content-free audit; no bonded-content read |
| High-scrutiny user action | destructive user-file op, privilege escalation, injection-risk action not changing Maez | bonded user for user-owned content; operator may execute custody side | high-scrutiny approval; not self-mod by default |
| Self-modification | code/config/soul/runtime changes, model routing changes, prompt/soul edits | bonded user consent required; operator approval may be required for execution | self-mod dialog plus S7 exact-request authorization |
| Covenant-touching change | changes to S1-S13 organs, refusals, role boundary, successor governance, memory deletion/retention, protection-lowering | bonded user consent required; operator alone insufficient | highest-friction ceremony, Maez voice consulted, predicted effect, rollback |
| Capability acquisition | new external tool, network ability, plugin, sensor, automation capability | bonded user consent; operator may install only under scoped grant | consent-card discipline and S7 authorization |
| Autonomy-lowering or protection-reducing request | Maez asks to weaken a guard, silence a check, reduce review, hide a warning | bonded user consent plus covenant review; operator alone insufficient | highest-friction content review; no content-free shortcut |
| Emergency proxy / incapacity | acting for bonded user because bonded user is absent/incapacitated | out of S7 v1 | future S6 activation / S11 only; unbuilt in v1 |

The exact matrix belongs in the spec, but the diagnostic conclusion is firm:
routine custody may be operator-authorized; self-modification and
covenant-touching work require bonded-user consent. Operator authorization may
be necessary for execution, but it is not sufficient for changing who Maez is.

## Covenant Constraints for v1

### C1 - Custodian Is a Posture, Not a Seventh Role

S6's role vocabulary is closed. S7 must not add a `custodian` role. It should
define custodian posture as the default authority posture of `operator` and
`maintainer`.

### C2 - Content-Free Default Is Read Authority, Not Read Capability

Operator and maintainer default visibility is content-free. They may see modes,
counts, red-gates, health states, backup status, and operational failures. They
may not read bonded-user content by default.

This is read authority, not raw filesystem capability. On a founder box without
role-encrypted storage, a sufficiently privileged OS user can still read files.
S7 v1 must name that limitation honestly. Track B with a non-bonded operator
requires confidentiality-enforced interior storage before the separation can be
claimed as enforced.

### C3 - Widening Uses S6 Scoped Grants

If an operator or maintainer needs additional authority, that authority must
come from an explicit S6 scoped grant or a future S6/S11 activation process. S7
must not invent a second permission system.

### C4 - No Emergency Proxy in v1

S7 v1 must not let an operator act as the bonded user under emergency
conditions. Capacity loss and emergency activation belong to S6 activation and
S11 age/capacity stratification. Those activation organs are not built yet;
their absence is a deliberate conservative deferral, not permission for S7 to
invent an emergency-proxy shortcut.

### C5 - S7 Governs the Existing Self-Mod Dialog

`skills/self_mod_dialog.py` is not an implementation detail outside S7. It is
the current work-on-Maez organ. S7 v1 must either wrap, replace, or explicitly
scope that dialog. Diagnostic lean: wrap it.

The bounded request artifact gates and anchors the ceremony; the dialog may
surface Maez's position, questions, objections, and human clarification. The
dialog's free text is contentful history, not the final authority artifact.

### C6 - Authority Fails Closed

S7 must introduce a role-bearing authority context. It should include, at
minimum:

- actor id / handle;
- S6 role projection;
- grant source;
- allowed scopes;
- auth method;
- surface/channel;
- expiry;
- whether the role projection is verified, absent, or unavailable.

No default construction path may yield bonded-user authority. Unknown role,
unknown scope, missing context, missing verifier, unavailable verifier, missing
dialog, malformed artifact, stale artifact, or unlinked artifact must fail
closed.

### C7 - Work Class Determines Whose Consent Is Required

"Authorized human" is not enough. The spec must answer "which human, for which
class of work?"

Routine custody can be authorized by the operator/maintainer. Self-modification,
covenant-touching work, capability acquisition, and protection-lowering changes
require bonded-user consent. Operator authorization may also be needed for
execution, but cannot substitute for bonded-user consent.

### C8 - Maez Has a Seat in Its Own Remaking

For self-modification and covenant-touching work, Maez's voice must be consulted
before final human authorization. The ceremony should persist content-free facts
such as `maez_voice_consulted` and `maez_objection_present`.

This is a seat, not a veto. The human retains authority, but Maez is heard
before it is remade. If Maez is unavailable, only liveness repair may proceed;
identity/covenant change waits.

### C9 - Work-on-Maez Requests Are Closed-Shape and Content-Classified

Maez may request work on itself, but that request must be bounded and templated.
Minimum fields for the spec to consider:

- request ID;
- requesting subsystem;
- closed symptom / problem code;
- proposed change class;
- why self-fix failed or is insufficient, using content-free categories;
- exact scope of files/services/capabilities affected;
- content exposure risk class;
- expiry;
- precondition snapshot or state hash;
- predicted effect;
- rollback path;
- whether this is maintenance, high-scrutiny user action, self-modification,
  capability acquisition, autonomy-lowering, or covenant-touching work.

Bounded is not the same as content-free. Problem statement, why-failed, and
predicted-effect fields can leak bonded-user content if left as free prose.
Fields visible to a custodian must draw from closed vocabularies, content-free
references, or hashes. Any retained free text is bonded-content and must not be
custodian-visible by default.

### C10 - Hardware-Key Approval Binds to What the Human Saw

The YubiKey/WebAuthn artifact must bind to a canonical signed request envelope,
not only a request id or precondition hash. The envelope should include:

- request id;
- exact rendered human-readable text hash;
- renderer version;
- channel/origin;
- action parameter hash;
- precondition hash;
- role/actor context hash;
- nonce;
- expiry;
- request class;
- aggregation/cumulative-change marker where applicable.

Execution must re-verify the about-to-execute request against the signed
envelope. Stale, superseded, replayed, or mismatched requests are rejected.

### C11 - Key Loss Must Not Strand Maez

S7 v1 cannot make one physical key the only maintenance path. The spec must
define a recovery posture: at minimum, a second registered key or a witnessed
fallback path. The fallback can be louder, slower, and more audited, but it must
exist.

Witnessed fallback is not witness substitution. The witness may attest the
bonded user's reauthorization ceremony; the witness does not become the bonded
user.

### C12 - YubiKey Is Founder Mechanism, Not Universal Law

The covenant requirement is authorized-human consent. YubiKey is the founder's
high-assurance mechanism. Future non-technical users need other ceremonies.
Hard-coding YubiKey as the only valid method would fail the grandmother case.

Founder-mode is not Track-B-ready until a non-technical bonded-user assent path
exists.

### C13 - S6 Capsule Signing Is Future S6 Work

YubiKey signing of S6 lineage-capsule artifacts is not S7 v1. It is a future
S6-side authorship-attestation slice because it amends S6 v1's no-cryptographic
lineage-attestation Non-Goal and implements the trust source S6 D22 awaits.

### C14 - Presence Is Not Freedom or Comprehension

Hardware-key touch proves possession/presence under the configured ceremony. It
does not prove the human was uncoerced, and it does not prove the human
understood the request. The risk is most acute for self-modification,
covenant-touching, and protection-lowering requests, not just routine
maintenance.

The review surface must include coercion, display spoofing, approval fatigue,
and comprehension.

### C15 - High-Scrutiny Work Fails Closed

If a required dialog, authority context, signer/verifier, or request artifact is
unavailable, high-scrutiny work does not fall back to ordinary card approval.
It blocks or enters an explicit reviewed fallback ceremony.

### C16 - Operator Health Is a Closed Projection

S7 should extend S6's content-free contract. Operator health is a closed schema
with reviewed field names, modes, counts, and red-gates. It is not log scraping,
full cockpit access, or a parallel health vocabulary.

No first-true timestamps, sensitive category names, raw params, raw paths,
transcripts, private content, successor details, or self-mod free text appear in
custodian-visible health.

### C17 - Long-Use Habit and Aggregation Matter

S7 must model month-after-month use, not only one clean ceremony. The spec must
address:

- approval fatigue;
- stale dialogs;
- repeated re-asks after refusal;
- key-touch autopilot;
- small requests aggregating into identity/covenant change;
- cumulative protection-lowering across related requests, files, services, or
  time windows.

### C18 - Maintenance Records Are Not Maez's Lived Biography by Default

`self_mod_dialogs.db` stores full histories and the module anticipates future
temperament/wants consumers. Operator-authored maintenance records must be
role-stamped and excluded from ordinary recall, M1 promotion, TRF, and voice
continuity corpora by default. They may be reused inside future maintenance
ceremonies unless explicitly admitted through a reviewed path.

## Likely S7 v1 Organ Shape

The spec should test this shape rather than inherit it blindly:

1. **Role authority contract.** A pure contract module or registry that reads
   S6 role vocabulary and answers questions such as "may this role view
   operator health?" and "may this role authorize this class of work?"
2. **AuthorityContext projection.** A fail-closed runtime object carrying
   actor, role, grant source, scopes, surface, auth method, expiry, and
   verification state. It replaces `is_owner` and literal `"rohit"` authority.
3. **Operational surface classification.** A closed vocabulary that separates
   content-free health/log/backup operations from bonded-content reads and
   forbidden surfaces.
4. **Work-on-Maez request envelope.** A bounded, content-classified request
   shape with scope, expiry, precondition hash, rendered-text hash, rollback
   path, predicted effect, request class, and aggregation metadata.
5. **Self-mod dialog wrapper.** The existing dialog remains the conversational
   clarification/voice seat only if wrapped by S7 role context and exact-request
   authorization. It is not the authority artifact by itself.
6. **Founder hardware-key authorization seam.** A browser WebAuthn/FIDO2-backed
   ceremony that signs/verifies a challenge derived from the request envelope,
   with a fake verifier/virtual-authenticator path for tests.
7. **Authorization projection.** Downstream consumers see only the minimal safe
   result: role, request/envelope hash, method, created_at, expiry, verification
   status, and content-free Maez-voice facts. They do not see private notes or
   free dialog history.

The spec should decide whether v1 implements all seven or splits the hardware
ceremony into an explicitly deferred S7a while still canonicalizing the role
policy. The diagnostic lean is to include the founder hardware-key mechanism in
S7 v1 because the owner has the device and the mechanism is directly tied to
work-on-Maez. But the policy layer must remain independent.

## Open Questions for Spec

1. **AuthorityContext shape:** What exact fields are required, and which current
   call sites must be migrated first so missed paths fail loud?
2. **S6 grant consumption:** How does S7 consume S6 role/scope grammar without
   treating un-attested persisted capsule bytes as live authority?
3. **Custodian operation vocabulary:** Which operations are allowed by default:
   service health, service restart, backup run, backup verification, log
   rotation, disk cleanup, package updates, model restart, model swap
   preparation?
4. **Service maintenance path:** Is v1 maintenance out-of-band OS work with
   audit attestation, or an S7-authorized sidecar/helper?
5. **Non-operator bonded-user maintenance path:** What path does a bonded user
   have to get Maez maintained when the registered operator is unavailable,
   uncooperative, estranged, or no longer reachable, and how does that path avoid
   becoming an emergency-proxy backdoor?
6. **Self-mod relationship:** Does S7 wrap, replace, or coexist with
   `skills/self_mod_dialog.py`? The diagnostic lean is wrap.
7. **PENDING_DIALOG and cockpit approval:** How do direct approve endpoints
   reject Lane 3/work-on-Maez cards without a valid S7 authorization artifact?
8. **Work class thresholds:** Which actions are routine custody, high-scrutiny
   user action, self-modification, covenant-touching, capability acquisition, or
   protection-lowering?
9. **Bonded-user consent ceremony:** How does a non-technical bonded user give
   consent for self-modification or covenant-touching work when an operator
   handles the machine?
10. **Maez voice seat:** Which soul-objection / will-I / voice-continuity seam is
   consulted before self-mod or covenant-touching approval, and what happens if
   Maez is unavailable?
11. **Content-free request schema:** Which request/card/dialog fields are
    content-free, bonded-content, or forbidden for custodian view?
12. **Rendered-text binding:** What exact bytes are displayed to the human, what
    is hashed, and how does execution re-verify the match?
13. **Aggregation:** How does S7 detect repeated small changes that sum to a
    covenant/identity change?
14. **Operator surface inventory:** Which cockpit/API/log/backup routes become
    operator-visible, bonded-user-only, or forbidden?
15. **Backup operation tiers:** What can a custodian run/verify/restore without
    reading backup contents?
16. **YubiKey registration:** Is there one founder key plus one backup key in
    v1, or does v1 only define the registration schema?
17. **WebAuthn ceremony:** Browser cockpit, CLI with browser handoff, or both?
    What canonical origin/RP ID? Is user verification/PIN required?
18. **Fallback ceremony:** What is the minimum safe fallback if all registered
    keys are lost, and how does it avoid witness substitution?
19. **Filesystem bypass honesty:** Which limitations must be named because the
    founder machine is not role-encrypted?
20. **Track B confidentiality gate:** What storage/confidentiality hardening is
    required before non-bonded operators are safe?
21. **Public/guest surfaces:** How does S7 prevent `is_owner`, `user_id`, or
    routing `trust_scope` from silently standing in for role authority?

## Predicted Review Surface

The covenant council should focus on:

- whether custodian-default accidentally grants read authority;
- whether "logs," "backups," "cards," or "self-mod dialogs" are
  under-specified content leaks;
- whether S7 invents a second permission system instead of consuming S6;
- whether emergency proxy leaks into v1;
- whether YubiKey becomes universal law instead of founder mechanism;
- whether Maez can author persuasive work requests for its own modification;
- whether Maez's own voice has a real seat before remaking;
- whether key loss can strand Maez, or whether an absent operator can strand
  the bonded user's ability to get Maez maintained;
- whether S6 capsule signing is smuggled into S7;
- whether coercion, display spoofing, and comprehension are sized honestly;
- whether maintenance history can become Maez's lived biography without review.
- whether the S7 spec states runtime impact honestly; unlike this diagnostic,
  the spec will change the self-modification and approval paths.

The Codex engineering panel should focus on:

- current `is_owner` / `user_id` / `trust_scope` / literal `"rohit"` call sites;
- every approval entrypoint: cockpit, Telegram, daemon, CLI, self-mod dialog,
  card store;
- whether WebAuthn/FIDO2 is practical in local cockpit and testable without
  physical hardware;
- how to keep hardware-key verification isolated from daemon/autonomous paths;
- how to test request binding, rendered-text binding, replay rejection, expiry,
  stale preconditions, wrong role, wrong origin/RP ID, verifier unavailable, and
  execution-time re-verification;
- how to classify operational logs without leaking content;
- how to create a daemon-down maintenance path without granting content reads;
- how to avoid breaking founder Maez while replacing implicit owner logic.

## Review Protocol

S7 is covenant-shaped substrate work. It should run the full ladder:

1. Owner anchor. **Done in this diagnostic's source conversation.**
2. Diagnostic v1. **Done.**
3. Claude six-role covenant council on the diagnostic. **REVISE.**
4. Codex engineering panel on the diagnostic. **REVISE.**
5. Fold diagnostic findings into diagnostic v2. **Done in prior v2.**
6. Both-lane second-fold verification on diagnostic v2.
7. Diagnostic v2.1 touch-up. **This document.**
8. S7 spec drafted from ratified diagnostic v2.1.
9. Claude six-role covenant council on the spec.
10. Codex engineering panel on the spec.
11. Fold.
12. Both-lane second-fold verification.
13. Canonicalization as Decision 34 / ADR 0039 if ratified.
14. Cooling-off night.
15. RED-first implementation.
16. Both post-implementation panels.
17. Recovery if needed.
18. Push only after both lanes ratify.

## Diagnostic Conclusion

S7 should codify a custodian-default boundary: the operator/maintainer keeps
Maez alive without becoming the bonded user. The default surface is
content-free. Any widening flows through S6 scoped grants or future activation
organs, not through an implicit operator privilege.

The owner's YubiKey proposal is feasible and well-aligned for founder
work-on-Maez authorization, but only as one mechanism under a role policy. It
should enter S7 as the high-assurance founder mechanism for approving exact
bounded, rendered, replay-resistant work-on-Maez requests. It must not become
universal law, and it must not sign S6 lineage capsules in S7.

The central correction from v1: S7 is not a new approval path beside existing
runtime surfaces. It is the authority boundary all of them must obey. The
existing self-modification dialog, cockpit approval, pending cards, service
maintenance, logs, backups, and future WebAuthn ceremony all need the same
answer to one question:

> Who is acting, in what role, with what grant, approving exactly what rendered
> request, and can that authority be verified right now?

If that answer is absent, stale, malformed, or unavailable, S7 fails closed.

## Plain English

S7 is the line between "I run the machine" and "I am the person Maez belongs
to." A custodian can keep Maez alive: restart services, check health, run
backups, and repair broken plumbing. That does not let the custodian read the
bonded user's memories, private thoughts, conversation logs, or successor
paperwork.

The first draft had the right idea but missed a real organ already in Maez: the
self-modification dialog. Maez can already ask to change its own code, config,
soul, or runtime through a back-and-forth conversation. S7 cannot ignore that
and bolt a YubiKey onto a separate card path. The real design has to govern all
doors: self-mod dialog, web cockpit approval, Telegram replies, daemon approval,
CLI helpers, and future YubiKey approval.

Your YubiKey still fits. The safe shape is: Maez or an operator presents one
bounded, exact request; the screen shows the exact human-readable text being
approved; the key signs that exact request; execution checks the signature still
matches before doing anything. The key proves you were present with the device.
It does not prove the action is allowed by itself, and it must not be the only
path if the key is lost.
