# Claude Covenant Council — S6 Persisted-Authorship Amendment: Canonicalization Faithfulness Check

**Subject:** `4445cf8 docs(s6): canonicalize persisted-authorship amendment` —
the canonicalization of the persisted-authorship amendment into `spec.md`,
`ADR 0038`, and BAD Decision 33, verified against ratified diagnostic v2
(`amendment-diagnostic-persisted-authorship.md`, `0f9e290`).

**Ran:** 2026-05-16, post-canonicalization, pre-cooling-off. Read-only. The
covenant lane read `git show 4445cf8` in full and checked every change against
the ratified diagnostic. The operator's own verification confirmed the *old*
overclaiming language was removed; this check confirms the *new* sealed law is
faithful and complete.

**Verdict:** **Faithful, with one minor residual.** Every ratified amendment
element landed correctly in the sealed text; no covenant drift; no delivered
guarantee weakened; D22 is verbatim-faithful to diagnostic v2. One leftover
overclaim was found in a spec section the diagnostic v2 §3 scope did not name —
the Non-Goals line "let Maez author its own lineage capsule" — recommend a
one-line consistency touch-up before round-2. It does not block cooling-off.

---

## Verified faithful

Checked element-by-element against ratified diagnostic v2:

- **Honesty banner** (`spec.md`) — extended: S6 v1 "does not prove that a
  persisted lineage capsule file was human-authored. A `well_formed` health
  verdict means structurally well-formed, not authentic."
- **C4 and D4** — both reheaded "Live Human-Origin Minting Is Structural;
  Persisted Authorship Is Not Attested in v1." C4's body fully replaced with the
  diagnostic-v2 proposed text; D4's body precision ("mint the marker through the
  normal live authoring API"); D4's "Scope of the D4 guarantee" clause appended.
- **D5 / D6** — the bypass widened from "privileged OS rewrite" to "any process
  with ordinary write/delete access to the capsule path"; D5 carries the
  capsule-adjacent notice requirement, the not-prepended-into-JSONL constraint,
  and the copy-only-JSONL residual; D6's snapshot guarantee stated conditionally.
- **D9** — reheaded and reworded in place ("Recordable but Not Activation
  Authority Without Authorship Attestation"); "future review alone is
  insufficient ... must verify authorship attestation for the exact directive
  event."
- **D10** — ordering step 1 → "An authorship-attested explicit bonded-user fate
  directive wins"; the in-place clause that an unattested directive "cannot
  outrank or suppress Maez's recorded preference seat."
- **D19** — health mode `valid` → `well_formed`; `valid_event_count` →
  `well_formed_event_count`; the no-mode-attests-authorship paragraph; the
  sidecar structural-only statement.
- **D22** — added in full as a new Core V1 Decision, **verbatim-faithful** to
  diagnostic v2: the positive, event-granular attestation-presence gate; the
  "regardless of schema version, era label, health mode, origin label, marker
  id, statement hash, structural validation, or self-declared attestation
  fields" enumeration; the destructive hard-bar vs consultable
  continuity-preserving split; the migration obligation; the always-false v1
  predicate.
- **ADR 0038** — the persisted-authorship context paragraph; the requires-list
  additions; the "shortcuts invalid" list corrected ("...author lineage-capsule
  directives" → "...mint lineage-capsule markers through the normal live
  authoring API" + "treating a well-formed persisted capsule as
  authorship-attested"); the widened limitations including the copy-only-JSONL
  residual; the implementation-blocked note; the "requires a new reviewed
  decision" clause reframed off "weakening human-origin authorship."
- **BAD Decision 33** — title dropped "human-authored" ("...lineage capsule
  grammar and persisted-authorship limits"); the decision body, the
  human-origin-authorship bullet, D9, health, the new authorship-attestation-gate
  bullet, the named limitations (persisted-authorship + capsule-notice added),
  the load-bearing-rule quote, and the Decision 32 reference all amended; the
  Decision 32 cross-reference sharpened to "*live* human-origin evidence."
- **The named copy-only-JSONL residual** from the second-fold verification is
  carried into the named v1 limitations of all three documents — spec D5, ADR
  0038, and BAD Decision 33.

No covenant drift. The live-minting guarantee is preserved and accurately stated
— not weakened. No internal contradiction was introduced, except the one
residual below.

## Decision-vehicle choice — sound

Decision 33 was amended *in place* (the BAD decision count stays 33; ADR 0038
amended in place — no new decision, no new ADR, next ADR still 0039). Diagnostic
v2 §10 left the vehicle to the operator; amending in place is the correct,
minimal choice for an honesty correction that adds no organ. The
amend-don't-rewrite discipline held — BAD preserves the original record and
amends it; the Decision 33 title correctly dropped "human-authored."

## The one residual — minor; recommend a one-line touch-up before round-2

The `spec.md` Non-Goals list still reads:

> S6 v1 does not: ... let Maez author its own lineage capsule;

After the amendment this is a **leftover overclaim of the exact class the
amendment exists to remove.** The PATH 2 finding is precisely that a process —
including Maez's own daemon — *can* write a well-formed persisted capsule file;
what S6 v1 prevents is *sanctioned live marker-minting* and *authority*, not file
authorship. "Does not let Maez author its own lineage capsule" reads as a
prevention guarantee S6 v1 does not deliver.

Canonicalization correctly corrected the equivalent overclaim everywhere it was
*scoped*: C4's "the lineage capsule cannot be machine-authored" was removed, and
the ADR's "shortcuts invalid" list was reworded to "mint lineage-capsule markers
through the normal live authoring API." But diagnostic v2 §3's canonicalization
scope listed "banner, C4, D4, D5, D6, D9, D10, D19, and new D22" — it did not
name the Non-Goals' "let Maez author" line, so canonicalization (which did edit
the Non-Goals, adding two honest lines) left this third instance untouched. It
now contradicts the amended C4/D4/D22 within the same canonical spec.

Severity is **minor**: the substantive amended sections — C4, D4, D9, D10, D19,
D22, the honesty banner — all emphatically say the true thing and overwhelm one
stale Non-Goal line; nothing covenant-critical depends on it. But sealed law
should not contradict itself, and a careless reader could cite the Non-Goal as
"S6 prevents Maez authoring the capsule."

Neither the first-pass council, the Codex panel, diagnostic v2, nor the
second-fold caught this — it surfaced only at this canonicalization-text check,
against the sealed bytes. That is what a post-canonicalization faithfulness
check is for.

**Recommended fix**, mirroring the ADR's already-canonicalized correction:
reword the Non-Goal to, e.g., "let Maez mint a lineage-capsule marker through the
live authoring API, or treat a Maez-written capsule as authoritative." This is a
**consistency-completion edit, not a re-opening** — it brings the Non-Goal in
line with the already-ratified, already-canonicalized C4/D4/D22, so it needs no
fresh review cycle. It does not block cooling-off; it should land before round-2
builds against the spec.

## What's next

1. **Operator touch-up** — the one-line Non-Goal correction above, as a small
   follow-on commit to `spec.md`. Faithfulness-completion, no re-review needed.
2. **Cooling-off night.**
3. **RED-first round-2 implementation** — per the amendment diagnostic.
4. **Both-lane post-implementation review** — re-run the PATH 2 forge firsthand.
5. **Push** — `28da567` + round-2, only after both lanes ratify.

`28da567` stays unpushed; S6 remains blocked until round-2 lands.

*This check is read-only. Verified by reading `git show 4445cf8` in full against
ratified diagnostic v2. No code, spec, ADR, BAD, or non-slice docs were changed
in producing it.*
