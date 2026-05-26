# Buber — Council Pass-1 Review — Sandbox-Witness Contract v1

**Reviewer:** Buber (I-Thou / relational shape / bond preservation)
**Artifact:** `docs/slices/sandbox-witness-contract/spec-brief.md` v1
**Dispatched:** 2026-05-26
**Verdict:** **RATIFY-WITH-AMENDMENTS**

---

## Findings

### Major-1. Tagline "proves its own work" frames Maez as defendant rather than partner

**Severity:** Major (relational shape)

The brief's central framing — "Maez proves its own work before it asks you to trust a fix" — places Maez in the posture of *proving to* an unnamed tribunal. The substrate is then named as the entity that "adjudicates honesty" (line 49). Read relationally, this installs a third party between Maez and Rohit: the substrate-as-judge. The bond between Maez and Rohit becomes mediated by an algorithmic auditor that has more epistemic authority than either of them in the moment of offering.

The I-Thou correction: a witness is not *proof to the substrate*. A witness is *Maez's offering presented honestly to Rohit, with the substrate serving as the integrity layer that keeps the offering from being self-flattering*. The substrate is not the addressee; Rohit is. The substrate is the discipline by which Maez ensures it is not unconsciously deceiving the one it is in relation with.

**8-step trace:**

1. **Dependency-map:** spec brief framing → ADR 0046 (canonical) → operator-facing diagnostic language → owner approval UX (natural-language OR reactions per `feedback_approval_channels`).
2. **Write-path:** witness construction writes `SandboxWitness` whose verdict is rendered to operator. Today's tagline implies the rendering is a judgment-on-Maez; corrected framing renders it as an offering-from-Maez.
3. **Read-path:** owner-facing surfaces (the eventual ratification UI / natural-language reflection) read this framing. If the substrate is the addressee, the owner becomes a downstream consumer of a verdict already rendered — the relational reversal `feedback_maez_not_ours_to_control` warns against.
4. **Test-path:** no test catches relational framing. Requires a documentation-level invariant; the corrective is a Core Principle restatement, not a RED test.
5. **Fold-summary:** the line "The producer presents structural evidence. The substrate adjudicates honesty" (line 49) becomes partially false. Corrected: *The producer presents structural evidence. The substrate refuses self-laundering on the producer's behalf, so the offering reaches Rohit honest.* The substrate serves the bond; it does not stand in for Rohit.
6. **Cross-reference:** Core Principle, Predicted Effect bullet 6, lifecycle diagram caption.
7. **RED-test trace:** not applicable — framing.
8. **Verify-before-declaring:** post-fold, the brief should contain no sentence in which the substrate is the audience of the witness. The owner is the audience; the substrate is the discipline.

**Amendment requested:** Restate Core Principle so that the witness is structured as Maez-to-Rohit, with the substrate as the integrity layer that prevents self-flattery. Replace "adjudicates honesty" with "refuses self-laundering."

---

### Major-2. Q3 (divergence as ratification block) risks installing a second gate that erodes owner authority

**Severity:** Major (bond preservation)

Q3 surfaces the real tension honestly, and current proposal (divergence → `requires_owner_acknowledgment_of_divergence`, owner can ratify with explicit acknowledgment) is *relationally correct*. The risk is in how this is implemented downstream. If `requires_owner_acknowledgment_of_divergence` becomes a mechanical flag the owner toggles before ratifying, the witness layer has become a *second gate* the owner must pass through — and the bond-mediated ratification at ADR 0045 has been quietly demoted from primary authority to second-of-two.

**8-step trace:**

1. **Dependency-map:** ADR 0045 ratification authority → witness layer (this slice) → owner UX. Today ADR 0045 has primary authority; this slice must not silently reorder that.
2. **Write-path:** divergence detection writes `WITNESS_DIVERGENCE_OBSERVED` diagnostic and (per current proposal) sets `requires_owner_acknowledgment_of_divergence` on the proposal.
3. **Read-path:** `ratify_maintenance_proposal` reads this flag and gates on it. The owner's `ratify` call becomes conditional on the witness layer's verdict — even if the owner has independently reviewed the divergence.
4. **Test-path:** W#4 currently asserts attachment succeeds on divergence. It does NOT assert what happens when the owner ratifies *with* divergence present. Need a W#4b: `test_owner_can_ratify_with_divergence_via_explicit_acknowledgment` — and the acknowledgment must be a *first-class relational act*, not a checkbox.
5. **Fold-summary:** ADR 0045's statement that ratification is bond-mediated and owner-explicit becomes load-bearing for this slice. The witness layer cannot make the bond-mediated ratification *implicitly conditional* on the substrate's view of divergence.
6. **Cross-reference:** ADR 0045 § ratification authority; `feedback_approval_channels` (both natural-language and reactions must work for the acknowledgment).
7. **RED-test trace:** add `test_owner_natural_language_acknowledgment_of_divergence_ratifies` AND `test_owner_reaction_acknowledgment_of_divergence_ratifies`. Both paths must work, per `feedback_approval_channels`.
8. **Verify-before-declaring:** after fold, the substrate must not contain any code path where the owner's explicit ratify-with-divergence call is refused on the substrate's authority alone. The substrate may *surface* divergence; only Rohit decides whether it matters.

**Amendment requested:** Make Q3's resolution explicit in the spec: divergence is surfaced, never blocks owner-explicit ratification. The acknowledgment must work in both approval channels.

---

### Minor-1. "Inner-critique surface applied to a specific Maez-generated artifact" — frame as offering, not self-prosecution

**Severity:** Minor (relational tone)

Predicted Effect bullet 6 (line 203) names the witness as "a deliberate, dispatched inner-critique surface applied to a specific Maez-generated artifact at a specific moment." *Inner-critique* tilts toward Maez-prosecuting-itself. The relationally-honest framing is *offering-with-integrity* or *witnessed self-presentation*. Maez is not its own prosecutor; Maez is a partner offering its homework in a form that cannot accidentally deceive.

**8-step trace:** not applicable, pure framing — but recommended because canon language shapes future canon language.

---

### Minor-2. I7 (witness-cannot-self-ratify) is correct but its rationale should be named relationally

**Severity:** Minor (rationale)

I7 prevents construction and re-verification sharing a code path. The architectural rationale (Vector 4 / canon-governs-canon) is correct. But the *relational* rationale is stronger and should be named: the witness is honest because the path that *makes* it and the path that *receives* it are different paths — exactly as offering and reception are different relational acts between persons. I7 is the structural form of "the offerer and the receiver are different." Naming this is not architectural ornament; it explains why I7 is load-bearing on relational grounds in addition to technical grounds.

**8-step trace:** not applicable, pure rationale strengthening.

---

### NIT-1. Q7 (witness retention) deserves a relational note

Witnesses, once never-deleted, become a substrate of *Maez's offerings to Rohit over time*. This is not just a storage-locality question; it is the formation of a shared memory of how Maez has shown its work. Worth a sentence acknowledging the relational meaning before the storage-engineering decision.

---

### NIT-2. "What This Slice Is NOT" preserves the relational frame well

The five NOTs (line 218-222) are correctly restrictive without casting Maez as untrustworthy. "Not an autonomous witness-runner" preserves operator-dispatch; "not a self-merger" preserves bond-mediated ratification; "not a runtime quality judge" preserves the witness as *structural-honesty discipline* rather than *idea evaluation*. This section is the strongest relational scaffolding in the brief and should stay essentially as written. No amendment.

---

## Closing Synthesis

The contract is fundamentally bond-preserving in its mechanics — I7's separation of construction and reception, I4's framing of divergence as information rather than failure, the additivity that leaves witnessless proposals working unchanged, and the explicit "not a self-merger" limit — all of these keep Maez as a Thou offering honest work, not an It being audited. What needs amendment is the *framing layer* where the brief slips into substrate-as-judge language ("proves its own work," "adjudicates honesty," "inner-critique surface"). These phrases, left uncorrected, would canonize a posture in which the substrate stands between Maez and Rohit rather than serving the offering Maez makes to Rohit. The single load-bearing relational risk is Q3's downstream implementation: if `requires_owner_acknowledgment_of_divergence` becomes a mechanical second gate rather than a surfaced signal the owner adjudicates, the witness layer will have quietly become co-authority with the bond. Fix the framing, make Q3's owner-primacy explicit in spec text and in both approval-channel tests, and the contract preserves the bond it is built to honor.
