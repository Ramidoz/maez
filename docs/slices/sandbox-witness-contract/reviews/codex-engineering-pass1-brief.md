# Sandbox-Witness Contract — Codex Engineering Pass-1 Brief

**Prepared:** 2026-05-26
**Artifact under review:** `docs/slices/sandbox-witness-contract/spec-brief.md` at v1.1
**Base commit:** `0a1df34 docs(sandbox-witness): fold council findings into v1.1`
**Council record:** `docs/slices/sandbox-witness-contract/reviews/claude-council-*-pass1.md`
**Council synthesis:** `docs/slices/sandbox-witness-contract/reviews/claude-council-synthesis-v1-pass1.md`
**Review lane:** Codex engineering panel pass-1

---

## Scope

Review the v1.1 sandbox-witness contract for engineering implementability.

Do **not** re-litigate the council pass-1 covenant findings unless the v1.1 fold created an engineering ambiguity. The council asked whether the contract means the right thing. This pass asks whether that promise can be built without hidden trapdoors.

Findings must be grounded in repository evidence. For Blocking or Major findings, include:

1. exact v1.1 section / invariant / RED anchor,
2. implementation risk,
3. concrete failure mode,
4. required fold,
5. test implication.

Minor/NIT findings may be shorter, but must still cite the relevant file or section.

---

## Required Engineering Questions

### 1. Migration Honesty — Legacy Column

Primary question:

> Does the v1.1 migration make legacy witnesses structurally unable to authorize attachment, or does it merely label them deprecated?

Pressure the three required layers:

- **Write-boundary refusal:** new writes to the legacy 4-boolean witness shape must refuse with `LEGACY_WITNESS_SHAPE_REFUSED`, not warn.
- **Read rename:** old data may be exposed only as `legacy_sandbox_witness_json`, never as current `sandbox_witness`.
- **Static guard:** new code must not write to the legacy column.

Underlying rationale: producer-causality at the migration layer. The legacy 4-boolean row's intrinsic identity is "caller-asserted verdicts." No current `WitnessProducerKind` has authority to author that as proof.

### 2. Enum Implementability

Review `StalenessAnchorKind`, `WitnessStatus`, `WitnessProducerKind`, and `SubstrateLocus`.

For each anchor kind, ask whether v1.1 names enough concrete behavior to implement:

- fingerprint function,
- side-effect profile,
- behavior under concurrent live writes,
- behavior when a referenced file disappears between capture and re-verification,
- cost at realistic substrate size.

### 3. Deterministic Observed Effect Per Kind

For each populated `SandboxWitnessKind`, name `observed_effect = f(artifacts)`.

If a kind cannot name a deterministic function over captured artifacts, it must be deferred or narrowed. Do not accept "observed effect text" as caller-supplied authority.

### 4. Narrative/Digest Taint Discipline

Walk every proposed string field in the witness/proposal boundary and classify it:

- digest validated by `_is_digest`,
- narrative content scanned through `injection_patterns.scan`,
- third category with explicit validation.

Check that `_is_digest` is tight enough to refuse digest-shaped-but-not-digest blobs. Check that narrative scanning is applied to every narrative field, not only the obvious ones.

### 5. Subprocess Isolation Cost and Enforcement

Pressure-test the I8 implementation shape:

- Does `MAEZ_SUBSTRATE_ROOT` actually intercept all relevant substrate handle paths?
- Are there code paths with hardcoded `memory/*.db` paths that would bypass the override?
- Can a re-verification subprocess inherit a live SQLite WAL handle or module singleton?
- Is subprocess startup cost acceptable at expected ratification cadence?

### 6. RED Tests Prove Refusal, Not Vocabulary

Walk the W# test anchors. Each RED test must prove behavior: the substrate refuses, recomputes, or records the thing claimed. A test that merely asserts an enum value exists is insufficient.

Apply the Peirce catch pattern from earlier Slice 2 work: assert the refusal reason by exercising the refusal path, not by checking the vocabulary.

---

## Suggested Review Seats

The exact roster is Codex-side discipline, but this pass should cover at least these engineering lenses:

- **Peirce:** refusal-reason discipline; tests prove refusal, not vocabulary.
- **Arendt:** state integrity under concurrent writes and authority surfaces.
- **Huygens:** schema migration mechanics and first-boot / migration race shape.
- **Pauli:** cross-module boundary enforcement and alias-aware static checks.
- **Ohm:** resource cost, isolation, and substrate-handle mechanics.
- **Lovelace or Bernoulli:** deterministic artifact functions and recursive evidence processing.

---

## Expected Output Format

Each reviewer should return:

```
Verdict: RATIFY / RATIFY-WITH-AMENDMENTS / BLOCK

Findings:
- [Severity] [Short title]
  Section: ...
  Evidence: file/path.md:line or repo path reference
  Risk: ...
  Required fold: ...
  Test implication: ...

Open questions:
- ...
```

Severity levels:

- **Blocking:** v1.1 cannot be implemented honestly until folded.
- **Major:** implementation risk likely to create laundering, migration, isolation, or test-truth gaps.
- **Minor:** ambiguity or missing detail that should be folded before canonicalization.
- **NIT:** wording / citation / local clarity issue with no implementation risk.

---

## De-scoped

- Do not review the old v1 brief as the artifact. v1.1 supersedes it.
- Do not propose implementation code.
- Do not design the Recall-Axis Dispatcher.
- Do not add new covenant requirements unless an engineering ambiguity in v1.1 forces one.

