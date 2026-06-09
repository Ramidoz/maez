# Photo-Triggered Fact Check v0

Status: implementation slice, dormant until merged/restarted.

## Goal

When an owner-sent photo or caption implies a current-world claim, Maez must treat
the photo as a lead, perform a fresh web check, and answer from both surfaces:

- `E1`: what Maez saw in the photo.
- `E2`: fresh public-world evidence, or an honest no-results check.

The failure this fixes: a photo showed `Claude Mythos 5 and Fable 5`, but Maez
answered from stale memory that those names did not exist.

## Rules

1. A photo proves what the image appears to show; it does not by itself prove the
   outside-world fact is true.
2. Stale memory must not overrule current photo evidence.
3. If the photo/caption asks about `latest`, `released`, `announced`, current
   model names, benchmarks, prices, laws, medical/financial facts, or similar
   freshness-sensitive claims, run a fresh web check before the photo reply.
4. If fresh evidence is found, pass it into bounded photo synthesis as `E2`.
5. If the check returns no results, pass the no-results fact as `E2` and answer
   honestly: "the image appears to show X, but I could not verify it."
6. Keep Photo Contradiction Sense v0 intact: it still checks direct photo claims
   against `E1`. This slice adds freshness evidence; it does not turn the
   verifier into a censor.

## Scope

In v0, only owner-sent photo turns use this path. General text-only freshness
policy can reuse the same principle later, but this slice fixes the live photo
witness failure first.

## Tests

- A Fable/Mythos-style photo/caption derives a photo freshness query.
- Photo synthesis accepts citations to `E1` plus optional `E2`.
- The prompt distinguishes photo evidence from fresh web evidence.
- A successful photo analysis prevents empty-search fallback and passes fresh
  context into `synthesize_photo_turn`.
- No raw photo pixels leave the box; this slice only searches text derived from
  the local vision analysis and caption.

