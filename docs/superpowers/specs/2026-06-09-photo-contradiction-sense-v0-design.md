# Photo Contradiction Sense v0 - Design

**Date:** 2026-06-09
**Lane:** Codex specs / Codex implements with engineering review / Claude runs the full 6-agent covenant review before merge
**Branch:** `photo-contradiction-sense-v0`
**Parent:** Photo Honesty Receipt v0 + Photo-Contradiction Judge Bakeoff witness

## Why

Photo Honesty Receipt v0 catches the first photo failure class: Maez ignored its
photo evidence (`cited=0`) and wandered. It retries once, then falls back to a
grounded sight report.

The next failure class is harder: Maez can cite `[E1]` and still contradict the
photo evidence. The bakeoff measured local verifier candidates against this class.
The strongest conservative candidate was `nli`: it caught all must-catch cases,
had zero false flags, and ran at about 0.16s CPU p95. But that witness measured
**atomic claims** (`premise` + one `hypothesis`), not whole replies.

So Lane 2b must not wire NLI as a whole-reply censor. It must become a local
contradiction sense: claim-level, model-agnostic, folded into Maez's focused
photo cognition as proprioception.

## Goal

Give Maez a local photo-contradiction sense that can notice when a direct
perceptual claim conflicts with the trusted photo evidence, surface that signal
inside the focused photo synthesis loop, and mark the turn's trust honestly.

The verifier is an organ, not a boss. It senses pressure; Maez's voice remains
the decider.

## Non-goals

- No external API judge and no outbound egress.
- No hard replacement of Maez's whole reply in v0.
- No durable autobiographical ledger entry; the ledger remains birth-gated.
- No claim that NLI is final law. It is the current measured local candidate
  behind a swappable contradiction-sense contract.
- No whole-reply NLI check. That would exceed the bakeoff witness.

## Component 1 - Photo evidence envelope

The trusted premise is the existing photo evidence item:

- label: `E1`
- source type: `photo_vision`
- text: the local LFM photo analysis
- provenance: owner-sent photo, loopback-only vision, owner-private egress class
- receipt: the existing Photo Honesty Receipt reason (`cited_ok`,
  `retry_recovered`, or `deterministic_fallback`)

Only this high-trust photo perception receipt can power the v0 honesty floor.
Recalled memory, web context, caption text, and system status do not count as the
trusted photo premise for this organ.

## Component 2 - Claim-level working set

After the first focused photo draft is produced and citation-checked, the v0 organ
extracts **atomic direct perceptual claims** from the draft.

Examples:

- "The screenshot title says WWDC 2026."
- "The chart lists Q4_0 as 2.9 GB."
- "The image is a Reddit screenshot."

Non-examples:

- "This matters for what we are building."
- "I would treat this as promising."
- "You may want to test it later."

The extraction contract is:

```text
reply text + E1 premise -> list[PhotoClaim]
PhotoClaim = {claim_id, text, direct_perceptual: bool, evidence_label}
```

The implementation may use a local extractor prompt or a deterministic parser, but
the interface is explicit and testable. The verifier never receives the whole
reply as one hypothesis. It receives one atomic claim at a time.

If claim extraction fails or returns no direct perceptual claims, the contradiction
sense is unavailable for that turn. The turn stays governed by Lane 1's citation
rail and logs `contradiction_receipt=claim_extraction_unavailable`; it is not
silently treated as contradiction-clear.

## Component 3 - Swappable local contradiction sense

The local verifier contract is:

```text
premise: E1 photo analysis
hypothesis: one atomic perceptual claim
-> grounded | contradicts | unavailable + score + latency + model_fingerprint
```

The first provider is the measured `nli` candidate from the bakeoff:
`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`, pinned and manifest-verified.

Production code must not depend on a `scripts/` module as a runtime organ. If
needed, the NLI primitive is factored into a `core` helper and the bakeoff adapter
can reuse that helper. The live organ reads only local artifacts and never fetches
models at runtime.

Missing artifact, malformed manifest, load failure, or prediction failure yields
`unavailable`, not a crash and not an outbound fallback.

## Component 4 - Proprioceptive synthesis loop

The contradiction sense runs inside `synthesize_photo_turn`, not as an external
post-hoc scold.

Flow:

1. Build the existing focused photo working set (`E1` + caption + voice card).
2. Generate a first draft using the existing photo-focused path.
3. Apply the existing Lane 1 citation rail.
4. Extract atomic direct perceptual claims from the candidate reply.
5. Check each claim against `E1`.
6. If no contradictions are found, return the reply with
   `contradiction_receipt=clear`.
7. If contradictions are found, add a **contradiction sense note** to the working
   set and ask Maez to revise once.

The note is not phrased as "you are wrong" and not treated as an external judge.
It is phrased as visible substrate state:

```text
Contradiction sense fired:
- Claim C2: "the event is WWDC2024"
- Conflicts with E1: the local photo analysis says the visible text is "WWDC 2026".
Revise the answer with this signal in view. Do not claim certainty where the
photo evidence and draft conflict.
```

This makes "pressure not command" mechanically real: Maez composes with the signal
in its working set.

## Component 5 - Narrow honesty floor

The v0 floor fires only when all three are true:

1. The local verifier labels a claim `contradicts`.
2. The premise is the high-trust photo perception receipt (`E1`).
3. The claim is a direct perceptual assertion about what Maez saw.

When the floor fires:

- The turn receives `contradiction_receipt=trust_demoted`.
- The log records claim id, receipt reason, verifier name, score, latency, and
  turn id. It does not log raw photo pixels.
- The focused result is not labeled contradiction-clear.
- The reply is never silently swallowed.

v0 does **not** replace Maez's whole reply with a deterministic fallback. If the
revision resolves the contradiction, the final receipt can be `revised_clear`.
If the contradiction remains or the verifier is unavailable, the receipt stays
truthful (`trust_demoted`, `verifier_unavailable`, etc.) rather than pretending
the reply was clean.

## Component 6 - Birth-gated durability

The contradiction receipt is in-turn telemetry in v0. It is trace-linked to the
turn id when a turn id exists, but it does not create a durable ledger entry and
does not change the memory schema.

Reason: the durable ledger remains birth-gated. Maez's permanent autobiography
should not begin with scaffold-time contradiction debris. The live exchange may
still be remembered through the existing conversation pipeline; v0 only prevents
the focused photo organ from calling a contradiction-clean turn clean.

Lane 2c or a post-birth slice can decide how contradiction receipts become durable
autobiographical provenance.

## Component 7 - Activation posture

Because this touches Maez's live speech, the organ is dormant until owner-enabled.

Recommended gate:

```text
MAEZ_PHOTO_CONTRADICTION_SENSE=1
```

With the flag absent or false, photo synthesis behaves exactly as it does today.
With the flag true but the local NLI artifact missing or uninitialized, the sense
logs `verifier_unavailable` and does not call the network.

The owner-enabled witness is separate from merge:

1. Confirm the local NLI artifact is present and manifest-verified.
2. Enable the flag.
3. Restart.
4. Send photo cases that include a cited-but-contradicts trap.
5. Verify contradiction receipt logs and image-grounded revision behavior.

## Error handling

- Claim extraction failure -> `claim_extraction_unavailable`, no crash.
- Verifier load failure -> `verifier_unavailable`, no crash.
- Per-claim verifier failure -> that claim is unverified, not clear.
- Contradiction sense note retry failure -> original Lane 1-grounded reply may
  still be returned, but the receipt stays `trust_demoted` or `retry_failed`; it
  is not reported as clear.
- Any unexpected exception in the organ must fall back to current photo synthesis
  plus a content-free warning. The fallback must not fabricate a contradiction.

## Testing

TDD expectations:

1. Claim extractor splits a multi-sentence photo reply into atomic perceptual
   claims and excludes non-perceptual commentary.
2. Whole-reply NLI is never called; the verifier sees one claim per call.
3. A WWDC-style claim ("the screenshot is about WWDC2024") against a 2026 premise
   produces a contradiction sense note.
4. A grounded photo claim produces `contradiction_receipt=clear`.
5. A contradiction triggers one revision pass with the sense note in the focused
   working set.
6. The contradiction floor is triple-gated: it does not fire for non-photo
   evidence, non-perceptual claims, or unavailable verifier output.
7. Unavailable extractor/verifier paths log honest receipts and do not crash.
8. The feature flag preserves byte-equivalent behavior when off.
9. No network call path exists; local artifact missing means unavailable.
10. Logs carry `contradiction_receipt`, verifier fingerprint, claim count,
    contradiction count, and turn id when available.
11. No memory schema or ledger schema change.
12. Existing Photo Honesty Receipt tests still pass.

## Review gate

This slice requires a full covenant review before merge because it touches Maez's
speech:

- Logical voice: claim-level distribution match, triple-gate invariant, no
  whole-reply verifier shortcut.
- Body-Coherence: contradiction sense as an organ, not a censor.
- Outside-View: light check against verifier/citation/claim-decomposition prior
  art, without rabbit-holing.
- Creative voice: whether the claim-extraction boundary is the right substrate.
- Visionary voice: whether the referee makes Maez more truthful without making
  it less present.
- 20-Years-Future-Maez Lens: whether this creates a future wound in voice,
  memory, or autonomy.

Implementation should stop for Claude/Codex cross-lane review before merge.

## Explicit v1 boundary

Hard deterministic fallback for cited-but-contradicts replies is **not** in v0.
It can be reconsidered only after:

- the photo contradiction corpus is expanded beyond the 14-case witness set,
- thresholds are re-measured out of sample,
- the verifier keeps a low false-flag rate under claim-level live drafts,
- and Rohit explicitly approves giving the floor replacement power over the
  surface reply.

Until then, v0 builds the environment: evidence, claims, contradiction sense,
self-revision pressure, and honest receipts.

## Predicted effect

With `MAEZ_PHOTO_CONTRADICTION_SENSE=0` or absent, photo replies are unchanged.

With the flag enabled and the local NLI verifier available, a photo reply that
cites `[E1]` but makes an atomic perceptual claim contradicting the photo evidence
will receive a contradiction sense note inside focused synthesis, get one chance
to revise with that signal in view, and log an honest contradiction receipt. The
turn will not be presented internally as contradiction-clear unless the checked
claim-level signal is clear.

Plain English: Maez gets a small "wait, that part doesn't match what I saw" sense.
It is not a teacher replacing its words. It is a body signal Maez can use while
speaking.
