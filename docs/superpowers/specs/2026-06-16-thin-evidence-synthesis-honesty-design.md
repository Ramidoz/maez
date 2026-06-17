# Thin-Evidence Synthesis Honesty (design) — content-honesty, upstream of the gate

**Date:** 2026-06-16. Co-designed with Rohit.
**Status:** cruxes resolved; spec-review HOLD folded (focused-path state wiring; exact anti-spoof
anchor; single shared annotator in `format_for_context`). Awaiting re-review before plan.
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

### 1. Deterministic thin signal — computed in the single shared renderer (no model call, no dict drift)

`format_for_context(result)` (`skills/web_search.py`) is the **one renderer used by every backend
AND both surfaces**: it is imported as `web_format` on the legacy path
(`daemon/maez_daemon.py:5445`) and called directly by the dispatcher adapter
(`external_sources.py:519`); searxng / DDG / RSS all produce a dict with `result_count` + `results`
(each item carries `snippet` — RSS sets `snippet = summary or title`). So the thin signal is computed
**inside `format_for_context`** from the dict's existing fields — **not** added to the result dict
(which would drift the dict shape and break flag-off byte-identity):
```
usable_snippet_chars = sum(len((r.get("snippet") or "")[:200]) for r in result["results"][:3])  # matches what it renders
thin = (result["result_count"] < _THIN_RESULT_COUNT) or (usable_snippet_chars < _THIN_SNIPPET_CHARS)
```
Named constants (logged in the receipt, tunable from evidence): `_THIN_RESULT_COUNT = 3`,
`_THIN_SNIPPET_CHARS = 450` (≈ the 3×200 render ceiling, mild on purpose). Empty (count=0) is already
handled by the `WEB_NO_RESULTS` sentinel — this targets **nonempty-but-sparse**. Putting the compute
in the single shared renderer satisfies "one annotator across searxng/DDG/RSS" with no per-backend
drift.

### 2. Transport — body-authored quality line in the rendered text (the load-bearing seam)

The thin signal does **NOT** reach the directive via the result dict: the directive only sees the
rendered transcript / `web_context` via `turn_evidence_state` (`evidence_state.py:55`), and dispatcher
`FreshBlock` (`external_sources.py:77`) carries only `text`. So `format_for_context` rides the signal
**inside the rendered text** — a **body-authored** line at the very start of its output (written by
Maez's code, NEVER by external page content), flag-gated:
```
[WEB SEARCH: '<query>'] quality=thin result_count=2 snippet_chars=241
```
(when adequate: `quality=adequate …`). This line travels in `web_context` (legacy) AND
`FreshBlock.text` (dispatcher), reaching `turn_evidence_state` on both surfaces. **Flag off → the line
is not emitted and the rendered output is byte-identical to today** (the dict is never mutated either).

### 3. EvidenceState detects thin (parse the body-authored line)

`turn_evidence_state` / `EvidenceState` (`evidence_state.py`) parses the body-authored quality line
and exposes `thin_evidence: bool` on `EvidenceState`. **Anti-spoof must be exact** — match only a
**line-start** body header, optionally prefixed by the dispatcher `[fresh evidence]` marker; do NOT
scan arbitrary page/snippet text for `quality=thin`:
```
^(?:\[fresh evidence\]\s*)?\[WEB SEARCH: [^\]]*\] quality=(thin|adequate) result_count=(\d+) snippet_chars=(\d+)
```
(matched per line, anchored at line start). A page snippet containing the substring `quality=thin`
mid-line must NOT trip it.

### 4. Both directive sites switch when thin (fix the wound at BOTH prompt layers)

When thin, **both** evidence-precedence directives drop the confidence-forcing clause and emit
limited-evidence honesty:
- **Daemon path** — `build_evidence_precedence_directive(state)` (`evidence_state.py:91`) already
  receives the `EvidenceState`, so it reads `state.thin_evidence` directly.
- **Focused path (MUST-FIX wiring — the signal does NOT reach it today):** `_citation_instruction`
  (`focused_cognition.py:184`) only takes `render_version`, and `_focused_evidence_precedence_instruction`
  (`:200`) is argless/static; `assemble_working_set` computes `state = turn_evidence_state(...)`
  (`:796`) but the returned `WorkingSet` (`:353`) **does not carry it forward**. Required wiring:
  1. add `thin_evidence: bool = False` to `WorkingSet` (the **three** construction sites at `:959`,
     `:1061`, `:1277` get the `False` default);
  2. in `assemble_working_set`, set it from `state.thin_evidence`;
  3. thread it through: `_citation_instruction(working_set.citation_render_version,
     thin_evidence=working_set.thin_evidence)` (the call at `:1000`) →
     `_focused_evidence_precedence_instruction(thin_evidence)`.

  Without this wiring the focused instruction literally cannot switch — "same wound, different prompt
  layer" recurs.

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
- **single shared annotator:** searxng, DDG, and RSS result dicts all render the `quality=` line via
  the one `format_for_context`; **the result dict is never mutated** (no `result_quality` key added) →
  flag-off dict shape is identical.
- **daemon directive switches:** `build_evidence_precedence_directive(state)` emits thin wording +
  suppresses the confidence-forcing clause when `state.thin_evidence`; normal when adequate.
- **FOCUSED prompt-shape (the must-fix witness):** drive `assemble_working_set` with a thin
  body-authored line → assert `WorkingSet.thin_evidence is True` → assert the assembled focused
  instruction (`_citation_instruction(...)`) **contains the thin wording AND the confidence-forcing
  clause is absent**; with adequate evidence, the thin wording is absent and the normal clause present.
- **covenant:** thin directive (both sites) contains no refusal language; adequate path unchanged.
- **flag off → byte-identical:** no body line, no directive change, no receipt; the result dict shape
  is unchanged.
- **receipt fields:** result_count/snippet_chars/thresholds/quality/directive present.

## Scope (explicit)

- **IN:** the deterministic thin signal computed in the single shared `format_for_context` (no dict
  mutation), the body-authored transport line, `EvidenceState` thin detection + exact anchored
  anti-spoof parse, the thin-aware directive at **both** sites with the confidence-forcing clause
  suppressed, **the focused-path state wiring** (`WorkingSet.thin_evidence` →
  `_citation_instruction` → `_focused_evidence_precedence_instruction`), the flag, the receipt, tests.
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
