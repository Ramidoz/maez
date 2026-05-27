# Descartes — Council Pass-1 Review — Recall-Axis Dispatcher v1

**Reviewer:** Descartes (foundations / doubt / indubitability)
**Artifact:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1 (HEAD `9110084`)
**Dispatched:** 2026-05-26
**Verdict:** **RATIFY-WITH-AMENDMENTS**

The brief's citation chain mostly holds under doubt, but two load-bearing references drift and one foundational claim — "Composition is the value" — is asserted axiomatically rather than earned. The structural argument is sound; the foundations need targeted shoring.

---

### Findings

**MAJOR — F1. Citation drift: `memory/embedding_contract.py:177` does not contain `all-MiniLM-L6-v2`.**

8-step trace: (1) Brief §4 cites *"using `all-MiniLM-L6-v2` per `memory/embedding_contract.py:177`"*. (2) Read of `embedding_contract.py:170–185` shows line 177 sits inside the docstring of the package-drift diagnostic. (3) `grep -n "all-MiniLM"` of `embedding_contract.py` returns no hits; the string `MiniLM` appears at lines 178/181 only as the class name `ONNXMiniLM_L6_V2`. (4) The literal string `"all-MiniLM-L6-v2"` lives in `memory/embedding_contract.json:6`, not the `.py`. (5) The `.py` reads the manifest and validates it; the manifest is the canonical source of the model name. (6) Downstream effect: a Codex reader auditing the spec will follow the citation, find it false, and discount the whole §4 mechanics half. (7) This is the exact failure mode Descartes B1 caught in the sandbox-witness pass-1 — load-bearing line-number citations that have drifted from substrate. (8) Required amendment: cite `memory/embedding_contract.json` for the model identity and `memory/embedding_contract.py` (no line number, or a verified one such as line 178) for the validator that pins it.

**MAJOR — F2. ADR 0042 cited as the producer-causality / anti-laundering anchor, but ADR 0042's body does not contain that discipline.**

8-step trace: (1) Brief §1, §2, §8 repeatedly cite "ADR 0042 / producer-causality" and "ADR 0042's anti-laundering discipline." (2) Read of the full `docs/adr/0042-drive-driven-curiosity-felt-organ.md` (47 lines). (3) `grep` for `producer-causality|caller-supplied|substrate-computed|laundering` in ADR 0042 returns zero hits. (4) ADR 0042 governs the drive-driven curiosity felt-organ — producers in the curiosity sense (encounter producers, wondering producers), not in the producer-causality / anti-laundering sense. (5) The actual canon for the anti-laundering discipline is `feedback_producer_causality_no_caller_score_laundering` (a Claude memory file, surfaced in the system context), reconstructed 2026-05-26. (6) The brief is conflating "ADR 0042's *producers*" with "producer-causality discipline." These are homonyms across two different design lineages. (7) Downstream effect: a council member checking the citation will read ADR 0042 and find the cited discipline absent; the brief looks like canon-laundering. (8) Required amendment: split the citation — cite ADR 0042 only for the curiosity-felt-organ frame; cite `feedback_producer_causality_no_caller_score_laundering` (and, if upgraded since, the canonical ADR for it) for the anti-laundering discipline. Invariant D6 still stands but its citation root must move.

**MAJOR — F3. `provenance_framing` mechanical enforceability is asserted, not foundationally earned.**

8-step trace: (1) §4.5 claims *"`provenance_framing` is not decoration. It drives template selection… can be audited by post-generation `self_claim_audit` against the fabrication_log discipline."* (2) `core/safety/self_claim_audit.py` exists (verified). (3) But the brief does not show that `self_claim_audit` exposes a hook that consumes `provenance_framing`, or that any prompt-assembly template surface exists today which is parameterized on the framing. (4) Today, the seam between `CompositionSpec` and the prompt-assembly layer is unspecified — Layer 0 emits a spec; nobody is named as the consumer. (5) Open Question §10.8 effectively concedes this (*"What minimal runtime proof should show that `provenance_framing` actually shaped the answer"*). (6) That is a foundational dependency posing as a closed mechanism. (7) Downstream effect: D4 (Provenance Seam Visibility) is unenforceable until a prompt-assembly hook exists. (8) Required amendment: §4.5 must say enforceability is *contracted* but the audit hook is a v1-implementation deliverable, not a present fact; or §10.8 must be promoted from open-question to blocker-for-implementation.

**MINOR — F4. ADR 0046 patterns cited; verified clean.**

8-step trace not required (citation holds): `grep` confirms "Monotonic generation as identity" and "Atomic authority-transition snapshot" appear as headers at lines 51 and 61 of ADR 0046. The brief's reference in §8 ("Future dispatcher fixes should be expressible as maintenance proposals with sandbox witnesses") is consistent with the ADR. Foundation holds.

**MINOR — F5. The keystone claim "Composition is the value" rests on a Rohit quotation, not a derivation.**

§2 Principle 2 anchors composition-as-value to *"If it just searches one specific topic I might as well do it myself"* at commit `5bcb15e` (verified). The quotation is canonical evidence of *operator preference*; it is not a derivation that composition is the *only* value, nor that pure-recall and pure-fetch are *only* edges. The brief presents composition-as-value as load-bearing law (Principle 2, §4 framing, §11 predicted effect). Under doubt, this is a strong design preference earned by operator witness, not an indubitable truth. Amendment is light: state explicitly that Principle 2 is *operator-witnessed value, ratified by council*, not a derived theorem. This protects the canon trail per ADR 0044 (claim is witnessed, verdict is recorded).

**MINOR — F6. `CompositionSpec` 4-field completeness assumed, not earned.**

§4 introduces the 4-tuple `(substrate_sources, external_sources, composition_hint, provenance_framing)` and treats it as sufficient to cover every composition mode. Doubt: where does *freshness threshold*, *budget*, *user-trust-scope* live? Open Question §10.2 (freshness window) and §10.5 (cross-surface scope union) hint these are missing fields, not just unresolved policies. Amendment: §4 should flag the 4-tuple as v1-minimal and acknowledge that §10.2 / §10.5 outcomes may add a fifth field.

**NIT — F7. RED anchor R#10 reads `unknown closed_vocabulary_value_refused` — typographically holds, no trace required.**

**NIT — F8. §10.10 ("Does this brief successfully avoid absorbing producer-causality consolidation") is rhetorical and should be removed.** A self-asked council question that the brief already answers in §0 (scope boundary) is not undecided.

---

### Closing synthesis — what holds under doubt, what needs shoring

Under doubt, the brief's **structural architecture survives cleanly**: the three-layer separation (§5), the closed-vocabulary discipline (§6), the ten invariants (§7), and the fifteen RED anchors (§9) are mutually consistent and substrate-grounded. The doctor analogy (§3) is genuinely teachable and not over-claimed. The dependency map (§8) correctly de-scopes producer-causality consolidation and ADR 0046 hardening as separate slices. `brain_loop.py:324`, the 41-finding dispatch synthesis at `8300984`, the v0 archetype set at `2c80820`, the Finding 19 root-cause at `45dcf3d`, ADR 0019 never-delete, ADR 0044's "Evidence first, witnessed verdict second, provenance forever," NORTH_STAR invariant #4, ADR 0046 monotonic-generation / atomic-authority-transition, and the `injection_patterns.py` seven-bucket catalog all verify against substrate.

What needs shoring: **F1's `embedding_contract.py:177` drift** and **F2's ADR 0042 conflation** are the two findings that, left unrepaired, would let a downstream agent doubt the entire citation pile. **F3's `provenance_framing` enforceability** is the load-bearing mechanism whose foundation is currently a promise, not a fact — it should be marked as contracted-deliverable rather than present-mechanism. The keystone "composition is the value" (F5) and the 4-field `CompositionSpec` completeness (F6) are weaker doubts: easily addressed by reframing as witnessed-preference and v1-minimal-shape respectively.

With F1, F2, F3 amended and F5, F6 reframed, the foundations hold. Verdict: **RATIFY-WITH-AMENDMENTS**.

**Files referenced:**
- /home/rohit/maez/docs/slices/recall-axis-dispatcher/spec-brief.md
- /home/rohit/maez/docs/adr/0042-drive-driven-curiosity-felt-organ.md
- /home/rohit/maez/docs/adr/0044-canon-governs-canon.md
- /home/rohit/maez/docs/adr/0046-sandbox-witness-contract.md
- /home/rohit/maez/docs/adr/0019-lived-memory-architecture.md
- /home/rohit/maez/docs/MAEZ_NORTH_STAR.md
- /home/rohit/maez/memory/embedding_contract.py
- /home/rohit/maez/memory/embedding_contract.json
- /home/rohit/maez/core/brain/brain_loop.py
- /home/rohit/maez/core/safety/injection_patterns.py
- /home/rohit/maez/core/safety/self_claim_audit.py
- /home/rohit/maez/docs/roadmap/post_s73_frontier_backlog.md
- /home/rohit/maez/docs/roadmap/dispatcher-archetypes-v0-2026-05-26.md
