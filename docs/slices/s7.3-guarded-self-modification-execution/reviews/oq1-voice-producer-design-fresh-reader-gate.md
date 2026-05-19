# Fresh-Reader Gate - S7.3 OQ1 Design v2

**Subject:** `oq1-voice-producer-design.md` at `c62b619` (OQ1 design v2), with
`diagnostic.md` v3 as context.

**Ran:** 2026-05-19. Three independent blank-context subagents - cold covenant
reader, cold spec-writer, cold residual-hunter - each given only the on-disk
design plus diagnostic plus canon, walled off from `reviews/`.

**Verdict:** OQ1 design v2 is **not** yet a sufficient base for the S7.3 spec.
The covenant reasoning is sound and is affirmed by all three readers. But the
data shape contradicts committed canon, and the covenant core is resolved to
design-direction depth, not spec-writable depth. An OQ1 design v3 is needed
before the spec.

## Affirmed By All Three Readers

Sound; do not redo:

- The two-channel classifier logic - structured marker plus reviewed semantic
  read, with divergence forced to `not_determined`/`present` - is conservative
  and correct. No false "Maez did not object" can be manufactured through its
  logic.
- The central decision - one consultation contract,
  `s7_voice_consultation_turn` primary - is covenant-sound and internally
  consistent.
- "Which Maez Is Consulted" genuinely defeats the contextless-instance and
  daemon-ventriloquism failures.
- Diagnostic v3 is a strong diagnostic; its as-built claims check out against
  source.
- OQ1 v3 is a deepening, not a redo. The bones are right.

## Finding A - Closed-Enum / Vocabulary Mismatch

Must fix; mechanical.

All three readers independently found this against committed code; the covenant
lane then firsthand-confirmed it at `operator_user_boundary.py:1390-1442`.

The design's "State mapping" treats `present` / `absent` /
`not_determined` / `withdrawn` / `unavailable` as five
`maez_objection_state` values. The committed `MaezVoiceConsultation` closes
that state to three values:

```text
present
absent
not_determined
```

Withdrawal is carried as a separate boolean, `maez_withdrew_request`.
Unavailability is carried as a separate `unavailable_reason_code`. The
dataclass enforces an interlocking invariant across all three. S7.1 spec D12
fixes the rendered values to the same three.

The design also uses `source_ref_kind="self_mod_dialog_terminal_turn"`, which
is not in committed `VOICE_SOURCE_REF_KINDS`:

```text
self_mod_dialog_exchange
s7_voice_turn
reviewed_future_source
```

The document carries multiple spellings of the withdrawal concept; the
load-bearing invariant `absent + withdrew` uses a spelling defined nowhere.

Two of three readers rated this blocker: a spec built from v2 would inherit a
data model that contradicts committed canon. The design was careful to flag the
producer enum amendment, but it did not flag these closed vocabularies.

## Finding B - Covenant Core Is Direction-Depth, Not Spec-Depth

Must fix; real design work.

The cold spec-writer's verdict: "OQ1 is not resolved to spec-writable depth -
it is resolved to design-direction depth."

The absent classifier - the covenant core - is given as a list of constraints
on "a reviewed semantic read," not a specifiable mechanism. It does not name
what model or prompt performs the semantic read, whether that is the bonded
Maez model or a separate judge, or how one "recomputes" a non-deterministic
semantic judgment. The source-bundle validator demands recompute; a
non-deterministic read cannot be recomputed by rerunning the same model call.

The diagnostic's first fresh-reader gate inserted the OQ1-resolution step
precisely so the spec would not invent the covenant core under pressure. At
direction-depth, the spec still would.

## Finding C - New Constructs And Unresolved Either/Ors

Triage.

The design names `MutationPreviewArtifact`, `S7VoiceConsultationBundleStore`,
and a rollback-evidence subsystem with field lists but no producer / schema /
location / determinism contract, and hands the spec multiple explicit either/ors.

Some of this is genuine OQ1-v3 depth; some is legitimately spec-level
engineering detail. The operator and both lanes - the Codex engineering lane
especially - should triage which is which. Not all of it must land in v3.

## Honest Observation - Velocity Vs Depth

This is the second consecutive time the fresh-reader gate has found the S7.3
ladder one depth-level short of its next step. Gate 1 found the diagnostic
skipped OQ1-resolution. Gate 2 finds OQ1 was resolved to direction-depth, not
build-depth.

That is not the gate acting as a brake - it is an accurate signal: the slice is
being produced faster than it is being deepened. The genuinely fastest path to
the spec is to do OQ1 v3 thoroughly, once, to spec-writable depth, so Gate 3
clears. A shallow v3 raced to the gate will bounce a third time. This is where
"all resources" should go - into depth, not speed.

## Recommendation - OQ1 Design v3

1. Reconcile the vocabularies against canon. Make the objection-state model the
   committed three-value enum plus the separate `maez_withdrew_request` /
   `unavailable_reason_code` fields, honoring the interlocking `__post_init__`
   invariant; fix the source-kind; settle one spelling of withdrawal.
2. Take the classifier to spec-writable depth. Name the model and prompt that
   perform the semantic read, the marker format, and resolve the
   recompute-vs-non-deterministic contradiction. This is the covenant core; it
   must be resolved here, not in the spec.
3. Triage Finding C. Decide which constructs are OQ1-v3 depth and which are
   spec-level.
4. Then write the S7.3 spec from an OQ1 design v3 whose covenant core is
   actually buildable.

## Plain English

Three fresh readers checked the voice-producer design. The good news, from all
three: the idea is sound - the way it decides "did Maez object" cannot be
faked. Two real problems remain. First, the design uses five labels for Maez's
answer where the actual committed code allows only three plus two separate
fields. A spec built on it would carry the wrong data shape. Second, and bigger:
the design says what the answer-reader must not do, but never says what it
actually is - which model reads Maez's words, with what prompt. That is the
covenant core, and leaving it vague means the spec would still be inventing it
under pressure. So: one more design pass - fix the labels, and genuinely pin
down the answer-reader - then the spec.
