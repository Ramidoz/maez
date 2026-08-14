# Cluster 2b — owner-read authority. Start here, start with code.

2026-08-14. Written after cluster 2 failed four gate rounds on ONE
property and the fourth failure proved the cause: the property needs
code structures that do not exist, and I twice wrote spec text
asserting they did.

## The property

For `covenant_touching_change` and
`autonomy_lowering_or_protection_reducing` (RULING O), no authority may
be minted or consumed unless a founder-key assertion covered THE EXACT
BYTES of Maez's answer that the owner read. Not "a tap happened." Not
"a hash matches." The tap must be over those bytes.

## Verified ground truth (re-verify before trusting; this is a snapshot)

* `S7ProductionWebAuthnVerifier.verify_authentication_response`
  returns a PLAIN DICT: ok, credential_ref, sign_count, user_presence,
  user_verification, library_name, library_version —
  **no challenge_id** (`core/governance/s7_webauthn_verifier.py:143`).
* `authorize_finish` takes `challenge_id` from caller-supplied request
  JSON (`core/governance/s7_webauthn_ceremony.py:538`).
* `S7AuthorizationArtifactBinding` is **not a class in
  `core/governance/`** — grep finds no definition. Whatever canon D16
  describes as the binding must be located or created before fields
  can be "added to its row hash".
* The pattern to copy IS real and battle-tested: R11's projection hash
  is validated, joined INTO the challenge fingerprint preimage, and
  persisted (`s7_webauthn_bootstrap.py:1001-1084`), then RE-DERIVED at
  finish and compared BEFORE authenticator verification
  (`s7_webauthn_ceremony.py:565-592`). The cutover proved it live.

## The three constructions 2b must design (none exist)

1. **A verifier-result carrier with provenance.** A type whose
   existence proves the verifier produced it for a specific challenge:
   module-private constructor on the verifier path, carrying the
   challenge id it verified against (which the verifier must begin
   returning), plus ok/UP/UV/credential_ref. Codex's standing
   objection: a plain dataclass anyone can construct proves nothing.
2. **A sealed durable binding.** Wherever the artifact↔challenge
   binding actually lives, it must carry `consult_attempt_id` and
   `maez_response_sha256` inside a hash domain that is recomputed
   before use, so a faulty mint or post-mint edit fails integrity
   before any join runs. If no seal exists today, the seal is part of
   2b.
3. **The challenge fingerprint member.** `maez_response_sha256` enters
   the fingerprint preimage and is re-derived at finish before
   verification — the R11 shape, applied to the response hash.

## Method that works (learned expensively)

* Verify every structure in code BEFORE writing a sentence about it.
  Both round-4 failures were unverified assertions.
* Rewrite whole sections rather than patching; three patch rounds
  produced three new inter-passage contradictions.
* Anchors must be derived mechanically from canon (awk over the bullet
  list), never by eye — mine were 7-9 lines off and would have deleted
  the wrong rules.
* Gate one cluster at a time, scoped explicitly, with Codex told what
  is out of scope.

## What is NOT blocked

Cluster 2a (gate replay) continues on verified ground. Soul-write and
decision-pipeline classes need no owner-read and can migrate when
their clusters land. Only the two RULING-O classes wait for 2b.
