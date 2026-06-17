# Thin-Evidence Synthesis Honesty (design) — content-honesty, upstream of the gate

**Date:** 2026-06-16. Co-designed with Rohit.
**Status:** cruxes resolved; awaiting spec review before plan.
**Arc:** content-honesty. Composes with (does NOT duplicate) the LIVE support gate (the gate caveats
unsupported cited claims post-hoc; this slice reduces how often Maez fabricates them). Distinct from
the old "Thread B" framing (fresh-vs-memory *conflict*); this is **sparse evidence**, not conflict.

## Why this exists (the wound + an honest caveat)

The support gate's live witness (2026-06-16, "latest news about Anthropic?") caught **4 cited
sentences judged UNSUPPORTED, two flagrant** (MiniCheck P-supported 0.027 / 0.039). Investigation of
the cause: when a web search returns **thin** results (few / short snippets), Maez fabricates
confident cited specifics the evidence doesn't contain. Two confirmed sub-causes:
1. **Soft directives don't hold.** The focused synthesis path already carries `_FAITHFUL_INSTRUCTION`
   (`core/routing/focused_cognition.py:102`): *"Answer ONLY from the evidence… if the evidence does
   not cover the question, say so plainly. Do not add claims unsupported by the evidence."* Maez had
   it and fabricated anyway. Adding another sentence is the thing we know fails.
2. **The evidence-precedence directive actively pushes the wrong way on thin evidence.**
   `build_evidence_precedence_directive` (`core/routing/evidence_state.py:91`) emits *"EVIDENCE PRESENT
   THIS TURN… Answer from this evidence… you may NOT claim the source is blocked, missing,
   unavailable…"* — correct for fresh-vs-stale, but on one doorway link it **forbids the honest "I
   found limited info"** and presses a confident answer. The focused path has a second copy of this
   pressure: `_focused_evidence_precedence_instruction` (`focused_cognition.py:200`, *"Before you claim
   the evidence lacks something, re-read it"*).

**Honest caveat (thinness ≠ relevance):** `spec_match_score=0.000` from that turn is a *routing*
score, NOT a result-thinness measure — we do **not** yet know the Anthropic turn's actual
`result_count`/`snippet_chars`. If that query returned 3 long-but-irrelevant snippets, it is a
*relevance* miss, not thinness, and this slice would NOT fire on it (the gate stays the net). So the
witness MUST first record the Anthropic baseline's `result_count`/`snippet_chars`; this slice
provably helps **sparse** searches, and only explains that specific wound if the baseline measures
thin.

## The design (spec-ready flow)

`body computes quality → renderer carries a body-authored quality line → EvidenceState detects thin
→ daemon + focused directives switch from confidence-forcing to limited-evidence honesty → the
support gate remains the protection layer.`

### 1. Deterministic thin signal (computed by the body, no model call)

In `skills/web_search.py`, compute on the result dict:
```
usable_snippet_chars = sum(len((r.get("snippet") or "")[:200]) for r in results[:3])  # matches what format_for_context renders
thin = (result_count < _THIN_RESULT_COUNT) or (usable_snippet_chars < _THIN_SNIPPET_CHARS)
```
Named constants (logged in the receipt so they're tunable from evidence):
`_THIN_RESULT_COUNT = 3` (thin when fewer than 3 results) and `_THIN_SNIPPET_CHARS = 450`
(≈ the 3×200 render ceiling, mild on purpose). `result_quality = "thin" | "adequate"`. Empty
(count=0) is already handled by the `WEB_NO_RESULTS` sentinel — this targets **nonempty-but-sparse**.

### 2. Transport — body-authored quality line in the rendered text (the load-bearing seam)

`result_quality` in the result dict does **NOT** reach the directive: the directive only sees the
rendered transcript / `web_context` via `turn_evidence_state` (`evidence_state.py:55`), and dispatcher
`FreshBlock` (`external_sources.py:77`) carries only `text`. So the signal must ride **inside the
rendered text**. `format_for_context` (web_search.py) inserts a **body-authored** metadata line right
after its header (written by Maez's code, NEVER by external page content):
```
[WEB SEARCH: '<query>'] quality=thin result_count=2 snippet_chars=241
```
This line travels in `web_context` (legacy) AND `FreshBlock.text` (dispatcher), so it reaches
`turn_evidence_state` on both surfaces. Flag-gated: when the flag is off the line is not emitted
(off = byte-identical).

### 3. EvidenceState detects thin (parse the body-authored line)

`turn_evidence_state` / `EvidenceState` (`evidence_state.py`) parses the body-authored
`quality=thin` token from the transcript and/or web_context and exposes a `thin_evidence: bool` on
`EvidenceState`. Parse only the **body-authored** line shape (anchored, e.g. the `[WEB SEARCH: …]
quality=…` prefix) so external page text can't spoof `quality=thin`.

### 4. Both directive sites switch when thin (fix the wound at BOTH prompt layers)

When `EvidenceState.thin_evidence` is true, **both** evidence-precedence directives drop the
confidence-forcing clause and emit limited-evidence honesty:
- `build_evidence_precedence_directive` (`evidence_state.py:91`).
- `_focused_evidence_precedence_instruction` (`focused_cognition.py:200`).

Thin wording (both sites, shared constant):
> *"The fresh evidence this turn is THIN — few results, little detail. Answer only what it actually
> supports, and say plainly that the search returned limited information. Do not fabricate specifics
> the results don't contain. You may offer to search differently."*

The confidence-forcing clause (*"you may NOT claim the source is missing/unavailable"* / *"before you
claim the evidence lacks something, re-read it"*) is **suppressed** on thin turns — it must not forbid
the honest acknowledgment when the evidence genuinely is thin.

**Covenant guard (two-sided pressure):** this must NOT make Maez refuse, or blanket-hedge every
reply. Maez may still answer from honest background knowledge; the target is **fabricated specifics
presented as found in the results**, not all answers. Thin → "I found limited info" + what's
genuinely supported, never a flat refusal.

### 5. Flag + receipt

`MAEZ_THIN_EVIDENCE_HONESTY_ENABLED` (`strict_env_flag`), off = byte-identical (no body-authored
line, no directive change, no receipt). Receipt (greppable, every web turn when flag on — so the
witness can measure the baseline even on adequate turns):
```
thin_evidence quality=thin|adequate result_count=N snippet_chars=M thresholds=(3,450) directive=thin|normal surface=…
```

### 6. The witness is measurable (composition with the live gate)

The gate already logs `support_gate_applied … caveated_unsupported=N` per turn. Success of THIS slice
= on thin-evidence queries, that count **drops** (Maez fabricates fewer cited claims → fewer
caveats → the caveat regains signal), and Maez visibly hedges ("I found limited information")
instead of asserting. Witness steps: (a) record the **Anthropic baseline** `result_count`/
`snippet_chars` (is it actually thin?); (b) if thin, re-run with the flag on → `directive=thin`
receipt + Maez hedges + the gate's `caveated_unsupported` falls from the 4/4 baseline; (c) if the
baseline is NOT thin, record that honestly — this slice still helps sparse searches but doesn't
explain that wound (gate remains the net).

## Testing (TDD, fakes)

- **thin signal:** `result_count < 3` OR `usable_snippet_chars < 450` → `quality=thin`; an adequate
  result (3 results, ≥450 snippet chars) → `quality=adequate`; named constants used.
- **body-authored line:** `format_for_context` emits the anchored `quality=…` line (flag on); flag
  off → no line (byte-identical render).
- **transport + parse:** `EvidenceState.thin_evidence` true when the body-authored `quality=thin`
  line is in the transcript/web_context; an external page containing a spoofed `quality=thin`
  (not on the anchored body line) does NOT set it.
- **both directives switch:** `build_evidence_precedence_directive` and
  `_focused_evidence_precedence_instruction` both emit the thin wording and **suppress** the
  confidence-forcing clause when thin; both emit normal wording when adequate.
- **covenant:** thin directive contains no refusal language; adequate path unchanged.
- **flag off → byte-identical:** no line, no directive change, no receipt.
- **receipt fields:** result_count/snippet_chars/thresholds/quality/directive present.

## Scope (explicit)

- **IN:** the deterministic thin signal (web_search), the body-authored transport line, `EvidenceState`
  thin detection + anti-spoof parse, the thin-aware directive at **both** sites with the
  confidence-forcing clause suppressed, the flag, the receipt, tests.
- **OUT (separate/later):** a deterministic non-model preamble (we chose directive-only — the gate is
  the reliable net); **relevance** scoring (thinness ≠ relevance; irrelevant-but-long results are the
  gate's job); per-source quality weighting; the legacy-megaprompt overhaul; the `grounding_judge`
  overclaim-rail repair.

## Covenant rail

This makes Maez honest about the *limits of what it found* without silencing it or making it refuse.
A thin search becomes "I found limited information," not a confident fabrication. The directive stops
*forbidding* that honesty on the exact turns it's true. The deterministic signal + receipt make the
behavior witnessable and tunable; off = byte-identical, so arming it is a clean owner choice. The
support gate remains the per-claim net for everything this upstream reduction doesn't catch
(including the relevance class this slice deliberately does not address).
