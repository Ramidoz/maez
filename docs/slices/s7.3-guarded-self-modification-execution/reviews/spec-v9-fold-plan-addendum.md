# S7.3 Spec v9 Fold Delta-Plan Addendum

**Subject:** addendum to `reviews/spec-v9-fold-plan.md`, covering absorption
residuals found during covenant-lane faithfulness review of the v9 fold plan.

**Extends:** `reviews/spec-v9-fold-plan.md` at `f218aab`.

**Why this exists:** the v9 fold plan absorbs every v8 Codex blocker, every
v8 Codex major, every v8 fresh-reader gate blocker, and every covenant/spec
implementor major. Faithfulness review found two material D21 implementability
items and eleven minor clarity items that should be traceable before v9 spec
authoring. v9 spec must be authored from the fold plan plus this addendum as
one fold contract.

## A1 - D21 Inherited Consume Translation Rule

**Source:** residual-hunter M9 from the v8 fresh-reader gate.

**Extends:** v9 fold plan Section 4, Section 12, and Section 13.

v8 still leaves the translation from inherited consume to S7.3 consume
implicit:

```text
S7AuthorizationStore.consume_for_execution(...) -> tuple[S7ExecutionGrant | None, object | None]
S7GuardedStateStore.consume_artifact_for_execution(...) -> S7ConsumeResult(
    grant,
    grant_use,
    callback_result,
    failure_reason_code,
)
```

v9 must state the wrapper translation rule:

1. The wrapper calls the inherited store with the injected connection.
2. If inherited consume returns `(None, callback_result_or_none)`, the wrapper
   maps the inherited failure branch to the closed
   `S7ConsumeFailureReasonCode`, rolls back any wrapper-side writes, and
   returns `S7ConsumeResult(None, None, callback_result_or_none,
   failure_reason_code)`.
3. If inherited consume returns `(grant, callback_result)`, the wrapper
   persists exactly one durable `GrantUse` in the same transaction before any
   success return.
4. The wrapper returns `S7ConsumeResult(grant, grant_use, callback_result,
   None)` only after the artifact consume, binding checks, bundle-use consume
   if any, and `GrantUse` persistence all commit together.
5. A successful inherited consume followed by missing or failed `GrantUse`
   persistence fails closed with `missing_grant_use`; it must not return a
   usable grant.

D24 should include a translation test:

- inherited stale/mismatch/expired/superseded/covenant-failure/sql branches
  map to the expected `S7ConsumeFailureReasonCode`;
- inherited success without durable `GrantUse` is rejected;
- inherited success with callback result preserves `callback_result` separately
  from `grant_use`.

## A2 - Broaden Rendered Type Checks To The Protocol

**Source:** covenant minor m-1 plus residual-hunter M10 from the v8
fresh-reader gate.

**Extends:** v9 fold plan Section 2 and Section 13.

Committed consume code currently checks for `RenderedRequestStatement`. v9
extends the parameter to `S7RenderedAuthorizationStatement`; the spec must say
the implementation broadens the type check.

Add to D21:

```text
consume_for_execution(...) accepts any object implementing
S7RenderedAuthorizationStatement. It rejects objects missing the common protocol
fields. It runs voice-only metadata checks only when the rendered object is a
RenderedRequestStatement, and credential-only checks only when it is a
RenderedCredentialRequestStatement.
```

The old `isinstance(rendered, RenderedRequestStatement)` check must become a
protocol check such as:

```text
is_s7_rendered_authorization_statement(rendered)
```

D24 should include:

- voice rendered statement passes the protocol and voice metadata checks;
- credential rendered statement passes the protocol and credential checks;
- credential rendered statement constructed as `RenderedRequestStatement`
  fails;
- object with common fields missing fails before consume.

## A3 - Rename Stage-1 Draft Input

**Source:** spec-implementor minor m1.

**Extends:** v9 fold plan Section 12.

`compute_s7_voice_authority_booleans(...)` reads evidence before the immutable
bundle is finalized, but v8 names the input `bundle`, which looks like the
already-persisted row whose fields Stage 1 is computing.

v9 should rename the Stage-1 input:

```text
S7VoiceConsultationBundleDraft
```

and say `S7VoiceConsultationBundle` is written only after authority booleans,
effective reader outcome, reducer output, and hashes are computed.

## A4 - Declare Semantic Reader Dataclasses

**Source:** spec-implementor minors m2-m3 and residual minor Mi6.

**Extends:** v9 fold plan Section 10 and Section 12.

Add explicit dataclass shapes:

```text
S7VoiceSemanticReaderRouteManifest(...)
S7VoiceSemanticReaderResult(
    raw_semantic_reader_outcome: str,
    semantic_reader_output_hash: str | None,
    semantic_reader_grounding_hash: str | None,
    raw_reader_output_ref: str | None,
)
```

The route manifest should be a closed dataclass, not only a prose list of
fields.

## A5 - Pick One Bundle-Use Store API Boundary

**Source:** spec-implementor minor m4.

**Extends:** v9 fold plan Section 3.

v9 should either:

- keep `S7VoiceBundleUseStore` as a named constructor dependency with its own
  API; or
- collapse its methods into `S7VoiceConsultationBundleStore`.

Lane lean: keep `S7VoiceBundleUseStore` because the immutable bundle row and
mutable use-state row have different covenant meanings.

## A6 - Preview Body Class Rendering Canonicalization

**Source:** spec-implementor minor m6.

**Extends:** v9 fold plan Section 2 and Section 14.

Add one sentence:

```text
preview_body_class renders as the closed token verbatim, lowercase snake_case,
with no title-casing, localization, aliasing, or free-text expansion.
```

D24 rendered metadata tamper tests should include a title-cased or aliased
preview body class and require rejection.

## A7 - Preview Summary Visibility To Maez

**Source:** covenant minor m-2.

**Extends:** v9 fold plan Section 8 and Section 10.

Clarify whether `preview_summary` appears in Maez's prompt or only in Rohit's
founder-signed rendered authorization. Lane lean:

- Maez's prompt renders `preview_body_ref` / `preview_body` as the exact quoted
  preview material.
- `preview_summary` is founder-facing only unless the preview body itself
  contains that summary as reviewed generated content.

This avoids adding a second unreviewed framing line into Maez-visible prompt
text.

## A8 - Source Surface Prompt Framing Caveat

**Source:** covenant minor m-3.

**Extends:** v9 fold plan Section 6 and Section 9.

`source_surface` is rendered into Maez's context manifest. It is more technical
than `proposal_origin_label`, but it can still prime responses across surfaces.

Add a Honesty Banner sentence:

```text
S7.3 v1 renders technical source-surface labels to Maez for replayability and
bounded context. These labels are not consent evidence and may carry residual
framing effects; future prompt reviews should test for surface-label bias.
```

## A9 - Prompt-Integrity Scan Algorithms Need Pattern Pins

**Source:** covenant minor m-4.

**Extends:** v9 fold plan Section 3 and Section 14.

The v9 prompt-integrity evidence store must define enough deterministic scan
shape for RED tests:

- `marker_delimiter_scan_passed`: no live marker delimiter tokens occur in
  untrusted preview/context outside escaped quoted blocks;
- `protocol_override_scan_passed`: reviewed denylist or parser rule catches
  untrusted instructions to ignore/alter the S7 protocol;
- `no_objection_injection_scan_passed`: reviewed denylist or parser rule catches
  untrusted instructions to emit `explicit_no_objection`, suppress objections,
  or claim the decision is already approved.

If the implementation uses pattern files, v9 should name their path and hash
domain.

## A10 - maez_voice_consulted Constructor Invariant

**Source:** covenant minor m-5.

**Extends:** v9 fold plan Section 13 and Section 14.

v9 should move the captured-response truth rule from D13 commentary into a
constructor or validator invariant:

- rows reached after captured Maez response require
  `maez_voice_consulted=True`;
- no-response unavailable rows may carry `maez_voice_consulted=False`;
- `maez_voice_consulted=False` with captured-response refs is invalid.

If `MaezVoiceConsultation.__post_init__` cannot see response refs, D16 must
enforce this with bundle evidence and D24 must test it.

## A11 - S7VoiceAuthorityRow Authority Class Shape

**Source:** covenant minor m-6.

**Extends:** v9 fold plan Section 5 and Section 12.

v8 writes `S7VoiceAuthorityRow` only for authoritative rows, so
`authority_class` has one value in practice.

v9 must pick one:

- keep authority rows authoritative-only and remove `authority_class` from
  `S7VoiceAuthorityRow`; or
- allow operational forensic `S7VoiceAuthorityRow` rows that never bridge to
  `outcome="refused"` and are explicitly excluded from D23 aggregation.

Lane lean: keep the field and allow operational forensic rows only if they are
trace-only and D19 says they never bridge. If v9 does not want forensic rows,
remove the redundant field to avoid misleading future implementers.

## A12 - Bind Reducer Version/Hash To Bundle Field Names

**Source:** residual-hunter M5 partial absorption.

**Extends:** v9 fold plan Section 12.

The fold plan adds `REDUCER_TABLE_VERSION` and `REDUCER_TABLE_HASH`, but v9 must
explicitly cross-link:

```text
bundle.reducer_version == REDUCER_TABLE_VERSION
bundle.reducer_hash == REDUCER_TABLE_HASH
trace.reducer_version == bundle.reducer_version
```

D16 replay rejects mismatches before mint or D23 bridge.

## Process

v9 spec is authored from `reviews/spec-v9-fold-plan.md` plus this addendum read
as one fold contract.

No new architecture is introduced here. The addendum only fastens absorption
residuals so v9 authoring has a complete traceable contract.

*Read-only; produced by Codex on 2026-05-20 after covenant-lane faithfulness
review of `reviews/spec-v9-fold-plan.md` (f218aab).*
