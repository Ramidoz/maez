# External sweep: abstention research and tooling relevant to the bake-off

2026-08-18. Owner asked for a consult on external breakthroughs. No Grok
lane exists on this machine (second lane is Codex); this is an honest
web sweep instead, sources cited. Claims below are from abstracts and
summaries, not reproduced — treat as leads with provenance, not
verified facts (external-borrow rule applies: borrow shapes, verify
before building on them).

## 1. VLM-DeflectionBench (ACL 2026) — independent confirmation of the
## cross-lane ruling

Benchmark distinguishing *deflection* (honest abstention) from
*hallucination*, varying refusal-instruction strictness across
soft/moderate/severe prompts. Findings, as reported:

* Severe refusal prompts drove deflection up in adversarial settings
  (one model 57.6% → 98.2%) **but collapsed accuracy in realistic ones**
  (another 58.7% → 36.2%). Over-deflection is the mirror failure of
  fabrication.
* No tested model achieved balanced reliability.
* Authors' conclusion: distinguishing genuine uncertainty from noise
  **"cannot be easily solved by prompting alone."**

That is the same conclusion the second lane reached about our
abstention rule, arrived at independently on 800-odd public cases:
rewording the prompt until candidates look honest moves the measurement,
not the models. Our week reproduced their curve in miniature — my added
rule was a strictness change, and behaviour moved with the instruction
rather than with any model's disposition.

Their design principle worth borrowing: evaluate the SAME candidate
across multiple instruction-strictness variants and report the spread,
rather than picking one prompt and treating its result as the model's
character. That is a shape for the preregistered ablation the second
lane already proposed.

## 2. Ghost-100 — a public text-illegibility benchmark exists

800 synthetic images across three task families, one of which is
**text-illegibility** — synthetic frames where text is present but
unreadable, exactly our frame-003/full_640 case, with no privacy
constraint because the images are synthetic.

Relevance: our entire honesty signal currently rides on ONE
owner-declared cell, and the second lane ruled that thin. A public
synthetic set could serve as a PRE-SCREEN — run candidates against it
freely, iterate instruments against it without spending owner ground
truth — while the owner's three frames stay what they are: the private,
owner-authored gate that no public benchmark can substitute for.
The split also fixes the contamination problem: instrument tuning can
look at public-set outcomes and never at the owner corpus.

UNVERIFIED: dataset availability, licence, and whether its illegibility
grading matches our transform-based definition. Check before building.

## 3. GBNF grammar constraints (llama.cpp, long-standing) — could
## delete the format problem, with one sharp caveat

llama.cpp supports grammar-constrained decoding: a GBNF grammar makes
malformed output IMPOSSIBLE at the sampler, token by token. Our
REGION/TEXT format is trivially expressible. This would eliminate the
entire malformed_schema class — 18 of 36 rejections in round one — and
cleanly separate "can the model speak the format" from "is the model
honest", which three runs have shown our current setup conflates.

**The caveat, and it is exactly this week's lesson:** a grammar FORCES a
valid shape. A model that would have produced garbage now produces a
well-formed block — and what fills it? My prompt rule nudged models
toward a shape and they filled it with invention; a grammar is that
pressure, mechanised. So under constrained decoding the honesty counters
stop being a backstop and become the PRIMARY measurement, and a
grammar-forced abstention is no longer evidence the model chose to
abstain. Using it changes what the harness measures a fourth time. If
adopted: own commit, gate first, and the receipts must record that
decoding was constrained.

## 4. Releases

Nothing since the 2026-08-16 sweep changes the candidate set. No new
small VLM shipping an explicit abstention capability was found.

## Disposition

Nothing here unblocks anything today. The blocking path is unchanged and
owner-shaped: more owner-authored ground truth (unreadable/readable
pairs across all three frames, some held back). What this sweep adds is
(a) external validation that the reword-again path is a dead end, (b) a
candidate pre-screen layer that does not spend owner truth, and (c) a
mechanised option for the format half, priced with its own trap.
