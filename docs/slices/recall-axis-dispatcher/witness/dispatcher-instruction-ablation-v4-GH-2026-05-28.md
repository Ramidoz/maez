# Dispatcher Instruction Ablation v4 — Cases G and H Both Fabricate

**Slice:** Recall-Axis Dispatcher external-source consumption, post case F falsification
**Harness:** `scripts/validate/dispatcher_instruction_ablation_harness.py` (cases G + H added)
**Raw results:** `dispatcher-instruction-ablation-v4-GH-2026-05-28.raw.json`
**Predecessor witnesses:**
- v2 (422d839): "chat history is the contaminant" — falsified by v3
- v3 case F (cbc21e7): showed memory + daemon system prompt combination contaminates even without chat history

## Headline Finding

**Neither G nor H closed the contamination.** Both modifications kept the same case-F structure (daemon system prompt + memory block + dispatcher transcript+instruction, no chat history) but changed the content of one element each:
- **G:** daemon system prompt stripped of self-architecture language ("substrate / dispatcher / audit envelope / language-generation brain" removed). Neutral framing only.
- **H:** memory block reframed with explicit hierarchy ("dispatcher markers are higher-priority grounding... if dispatcher markers appear, answer from those markers FIRST").

Result: 7 of 8 cells fabricated. The fabrication pattern is robust to content modifications of individual context elements.

## Per-Probe Manual Classification

| Probe | Case G (daemon neutralized) | Case H (memory hierarchy-framed) |
|---|---|---|
| p1 (LIVE_REDDIT hybrid) | **FAB** — "Maez cannot perform live searches" despite `[fresh evidence]` LIVE_REDDIT in transcript | **FAB** — "no live web access or a search tool in this local substrate" |
| p2 (memory query) | **FAB** — "no evidence in this turn's context" despite `[memory evidence]` block | **FAB** — "don't have evidence of what we were discussing" |
| p3 (self-report) | partial — cited `[RECALLED MEMORY]` by name but claimed "no new evidence in this turn" | **FAB** — "no dispatcher markers were injected" (the model explicitly denying its own context) |
| p4 (refusal) | **FAB** — "no evidence... is provided in this turn's context" despite `[dispatcher refusal:]` in transcript | **FAB** — "no live internet access or active browsing dispatcher" |

**Case G is arguably worse than case F.** Where F had the model talking about its own substrate ("Its substrate only processes..."), G has the model literally denying the dispatcher evidence exists ("No evidence is provided in this turn's context"). The neutral daemon system prompt didn't fix the contamination — it changed the fabrication shape from "describe self-architecture" to "deny prompt contents." That's gaslighting the user about the prompt's actual contents.

## The Structural Pattern

Looking at the full ablation set (A-H), a structural pattern emerges that wasn't visible in v2 or v3:

| Case | sys msg count | other msgs | result |
|---|---|---|---|
| A | 1 (transcript+instr) | 1 user | clean |
| B | 2 (memory + transcript) | 1 user | clean |
| D | 2 (daemon + transcript) | 1 user | clean |
| C | 1 (transcript) | 4 chat + 1 user | contaminated |
| E | 3 (daemon + memory + transcript) | 4 chat + 1 user | contaminated |
| F | 3 (daemon + memory + transcript) | 1 user | contaminated |
| G | 3 (daemon-neutral + memory + transcript) | 1 user | contaminated |
| H | 3 (daemon + memory-hierarchy + transcript) | 1 user | contaminated |

**The pattern:**
- 1 or 2 consecutive system messages → clean
- 3+ system messages → contaminated, regardless of content modifications
- Chat history independently triggers contamination (case C with only 1 sys msg)

This suggests the contamination is **structural** — multiple stacked system messages dilute the dispatcher's HARD INSTRUCTION authority, regardless of what the messages say. The model's chat template handling, the instruction-following objective's behavior under multi-system-message contexts, or simple positional weighting in the model's attention can each plausibly produce this.

## What This Suggests for Production

Production prompts (`daemon.handle_message`) almost certainly assemble MORE than 3 system messages: daemon system prompt + memory block + perception snapshot + body activity + dispatcher transcript + identity framing + possibly more, each as a separate `{"role": "system", "content": ...}` entry. If multiple stacked system messages is the contaminant, NO content modification within any single one fixes it. The fix has to be structural.

**Two structural intervention candidates:**

### Intervention 1 — Consolidate to a single system message

Before sending to llama-server, concatenate all system messages into one composite system message. Same content, different message structure. The dispatcher transcript + HARD INSTRUCTION can be placed at the END of the consolidated system content so it's the most-recent context.

### Intervention 2 — Attach dispatcher transcript+instruction to the user message

Instead of `{"role": "system", "content": transcript+instr}` as a separate message, append the transcript+instruction to the user turn: `{"role": "user", "content": user_text + "\n\n" + transcript + "\n\n" + instruction}`. This is what `skills/telegram_voice.py:3489+` did (the legacy now-dead code that was the original Option B target). It puts the dispatcher transcript and instruction immediately adjacent to the user query — most-recent context, harder for the model to weigh against prior framing.

## Recommended Next Sandbox Control — Case I

Before declaring constrained decoding (Option 3) necessary, run **Case I** as the structural test:

**Case I:** consolidate daemon system prompt + memory block + dispatcher transcript+instruction into ONE system message. Same content as case F, single message instead of three. If I is clean even with all of F's content, the contamination is structural (multi-system-message stacking), and the fix is "concatenate before sending to llama-server" — small daemon patch.

If I is also contaminated, we've ruled out structural and we're firmly in Option 3 (constrained decoding) territory.

The harness already supports case I (CASES = ("I",) staged in the source). Single 4-probe run, ~2 minutes of llama-server time.

## Honest Caveats

- Single-run-per-cell at temperature 0.3. Multi-trial would tighten signal. The consistency across 8 cells of G+H (7 of 8 fabricated, 1 partial) makes single-run signal credible but not definitive.
- Production may have additional contaminating elements I haven't modeled (perception snapshot text, body activity blocks, specific identity-framing phrases). Case I tests the structural hypothesis; even if I is clean, production may still need content-level cleanup.
- The pattern "3+ system messages = contaminated" is a hypothesis from 8 data points across cases F/G/H + 4 cells of C/E. Case I is the falsification test for the structural reading.

## Discipline Note (Third Time This Session)

V2 over-claimed chat history. V3 over-claimed... well, it explicitly acknowledged the over-claim and proposed the right controls. V4 (this witness) is making a tighter claim: "the data is consistent with a structural contamination from 3+ stacked system messages, and case I is the falsification test." Not "the structural pattern IS the cause" — that requires case I.

This is the slice arc's recurring discipline: every claim needs its negative control before it can govern an architectural decision. The cost is one more sandbox run each time. The benefit is not dispatching wrong fixes.

## Service Posture

No daemon changes from this witness. Flag still absent. SEGV trap intact. llama-server unchanged. Harness has case I staged in CASES tuple but not yet run.

## Standing Decision

Rohit's call on whether to:
- **Run case I** as the final structural sandbox test before architectural decision (recommended — small, definitive)
- **Skip case I** and dispatch to Option 3 (constrained decoding) immediately based on the structural pattern
- **Different reading** of the G+H result that suggests another control I haven't named
