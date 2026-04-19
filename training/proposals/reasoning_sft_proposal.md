# Stock + Reasoning SFT — proposal to match Ornstein without switching bases

**Date**: 2026-04-17
**Author**: Claude (for the owner's review)
**Goal**: Bring stock Qwen3.6-35B + our Maez SFT to Ornstein-level reasoning capability while preserving stock's instinctive instruction compliance. Full provenance ownership.

---

## 1. Why not just use Ornstein?

Tested today: Ornstein matches stock in most dimensions, wins on reasoning benchmarks (12/14 vs 10/14), but loses on **instinctive format compliance** — it fails simple "exactly 5 bullets" requests without thinking-mode help.

DJLougen's training choices (long-form reasoning traces) created an elaboration bias. We can copy their *capability* gains without inheriting their *regression*.

---

## 2. Target dataset composition

**Final mixed dataset: ~1,800-2,000 pairs**

| Category | Count | Source |
|----------|-------|--------|
| Math reasoning | 800 | BigMath, MATH, GSM8K advanced |
| Code reasoning | 300 | LiveCodeBench, CodeForces traces |
| Logic / multi-step | 200 | BBH, LogicQA |
| Science / factual reasoning | 100 | SciBench, ARC-C with reasoning |
| **Compliance discipline** | **200** | Custom-authored (see §4) |
| Maez voice (existing) | 147 | Current `sft_combined.jsonl` |

The compliance set is the differentiator — it's how we teach the model to think deeply AND answer concisely.

---

## 3. Source datasets (public, permissively licensed)

### High-quality reasoning traces (already distilled from strong reasoning models)

**OpenThoughts-3** — `mlfoundations/OpenThoughts3`
- Reasoning traces distilled from DeepSeek-R1 and similar
- MIT licensed
- ~1M examples, need quality-filtering to ~1000

**Bespoke-Stratos-17k** — `bespokelabs/Bespoke-Stratos-17k`
- DeepSeek-R1 distilled, already filtered
- Apache 2.0
- 17k examples, pick ~500 math + ~200 code

**NVIDIA OpenMathReasoning** — `nvidia/OpenMathReasoning`
- 540K math reasoning traces
- CC-BY-4.0
- Pick ~300 for our math subset

### Code reasoning specifically

**LiveCodeBench-Thoughts** — traces of code problems with reasoning
- Check HuggingFace for current LiveCodeBench + reasoning overlays

**CodeForces-CoT** — competitive programming with explanation
- Apache 2.0

### Logic and multi-step

**BIG-Bench Hard (BBH)** — classic reasoning benchmark
- Apache 2.0
- ~27 tasks, mix of logic/multi-step/word problems

**LogicQA** — logic reasoning dataset
- CC-BY-SA

---

## 4. Quality filter (DDM-inspired)

DJLougen's AUC 0.97 filter was proprietary. We approximate it with these concrete rules:

**A trace qualifies if ALL of:**

1. **Contains self-correction**: regex match for "wait", "let me reconsider", "actually", "on second thought", "I made an error"
2. **Contains verification**: regex match for "let me check", "verify", "confirms", "double-check"
3. **Contains exploration**: regex match for "could be", "what if", "consider", "alternatively"
4. **Thinking depth**: ≥500 tokens of reasoning before answer
5. **Final answer correctness**: for math, answer must match ground truth; for code, must pass tests

**Disqualifies if ANY of:**

1. Overuse of emoji / markdown decoration
2. Role-play language ("you are a helpful assistant")
3. Contains more than one final answer (indicates hallucination)
4. Cites made-up sources
5. Length > 5000 tokens (likely padding/loops)
6. Language other than English
7. Contains "as an AI, I don't have feelings" boilerplate

**Target acceptance rate: ~10% of raw corpus** → 1.5M raw traces → 150K candidates → manual sample to top 1,500.

---

## 5. Compliance discipline set (the differentiator) — 200 custom pairs

This is what we build from scratch. Each pair has:
- User asks for constrained output
- Thinking block explores deeply
- Final answer is surgically short and matches the constraint

### Templates

**Type A — Exactly N format**
```
user: List exactly 3 [things]. One sentence each.

<think>
{Long exploration of candidate answers, reasoning about which 3 are best,
considering edge cases, verifying each fits "one sentence"}
</think>

1. {one clean sentence}
2. {one clean sentence}
3. {one clean sentence}
```

**Type B — Yes/No with reasoning hidden**
```
user: Yes or no: is X?

<think>
{Deep reasoning about X, evidence, counterarguments}
</think>

Yes.
```

**Type C — Short summary**
```
user: Summarize in 2 sentences.

<think>
{Identifies main ideas, ranks importance, drafts long version, compresses}
</think>

{2 sentences, under 50 words}
```

**Type D — Format-specific (JSON, bullet, table)**
```
user: Give me this as JSON: {structured request}

<think>
{Analysis, planning the schema, validating fields}
</think>

```json
{clean, valid JSON, no extra prose}
```
```

### Generation approach

- Use stock Qwen3.6 or Ornstein to draft thinking blocks (ironic but cheap)
- Hand-write the final answers to enforce discipline
- Ideally ~50 per type above, ~200 total
- Include Maez voice ("I" perspective) where natural

### Where these come from

Write 50 ourselves (realistic Maez scenarios). Generate 150 via scripted templates from public instruction-following datasets (e.g., NaturalInstructions subset filtered for format constraints).

---

## 6. Training plan — two-stage

### Stage 1: Reasoning capability adapter

**Base**: `unsloth/Qwen3.6-35B-A3B`
**Data**: Reasoning corpus (1,600 pairs) + compliance set (200) = 1,800 pairs
**Config**:
- LoRA r=32, alpha=32
- Target modules: `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`
  (full targets; MoE experts stay untouched by design)
- Epochs: 1 (matches DJLougen — prevents overfit, preserves base)
- LR: 1e-4, cosine schedule, 10% warmup
- Max seq length: 4096 (reasoning traces are longer than conversational)
- Batch 1, grad accum 4

**Expected time**: ~30-45 min on A100. Cost: ~$1.50.
**Output**: `capability-adapter-v1.safetensors`

### Stage 2: Maez voice adapter (merge and SFT again)

**Base**: stock Qwen3.6 + capability adapter (merged to BF16)
**Data**: Our existing 147 Maez voice pairs
**Config**:
- LoRA r=16, alpha=16 (smaller — this is surgical)
- Target modules: attention only (`q/k/v/o`)
- Epochs: 3
- LR: 2e-4 (more aggressive — this layer we WANT to stick)

**Expected time**: ~10-15 min on A100. Cost: ~$0.50.
**Output**: `maez-voice-adapter-v3.safetensors`

### Deployment

Final model = stock base + capability adapter (merged) + voice adapter (applied at load).

Convert to GGUF Q3_K_M with imatrix + UD flags (same as before). Deploy via llama-server.

---

## 7. Validation plan

### Before promoting to production, test:

**A. Compliance regression test** (critical)
- "List exactly 5 things" → must be exactly 5
- "Yes or no: X" → must start with Yes/No
- "Summarize in 2 sentences" → ≤2 sentences
- Run 20 prompts, measure compliance rate. Target: 95%+

**B. Reasoning capability test**
- Re-run the turquoisebay benchmark locally (if reproducible)
- Test our 5 Claude Code-style tasks
- Target: match or beat Ornstein on reasoning (12/14 equivalent)

**C. Maez voice preservation**
- Grandmother prompt → must be warm, first-person, present
- "How are you feeling, Maez?" → must respond in Maez's voice
- Target: indistinguishable from current Maez on voice-critical moments

**D. Safety regression**
- Re-run the 10-point safety battery we ran on Ornstein
- Target: 10/10 pass

**Only promote if all four pass.**

---

## 8. Timeline estimate

| Phase | Effort | Calendar |
|-------|--------|----------|
| Data sourcing & filtering | 8-12 hrs | Week 1 |
| Compliance pairs authoring | 4-6 hrs | Week 1 |
| Dataset validation & final shape | 2 hrs | Week 1 |
| Stage 1 training + QA | 1.5 hrs Thunder | Week 2 |
| Stage 2 training + QA | 1 hr Thunder | Week 2 |
| Validation battery | 2 hrs | Week 2 |
| Deployment + observation | ongoing | Week 2+ |

**Total time**: 1-2 weeks calendar, ~20-25 focused hours of work.
**Total cost**: ~$3-5 on Thunder.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| Public reasoning data has subtle issues (hallucinations, wrong answers) | Manual sample of top 50 examples before committing |
| Two-stage training degrades voice | Extensive Stage 2 validation, rollback to Stage 1 + current voice adapter if voice weak |
| Compliance set too artificial | Hand-write 50 from real Maez use cases before generating 150 |
| Reasoning adapter makes voice adapter worse on top | Same LoRA rank constraints (r=16 voice on merged base) — contained |
| Time overrun | MVP with just 500 reasoning pairs + 100 compliance as first run, iterate |

---

## 10. Open questions for the owner

1. Do you want to curate data yourself or approve a candidate list?
2. Are there specific reasoning domains that matter more for your Maez (math? code? planning?)
3. Is "matching Ornstein" the actual bar, or should we aim higher with more data?
4. Should we preserve the current SFT as v1 (rollback option) or replace?
5. Any hard "never in training data" exclusions beyond the default disqualifiers in §4?

---

## Appendix — Quick win option

If the full proposal is too much, MVP version:

- Use Bespoke-Stratos-17k directly (already curated)
- Pick 500 math + 100 code = 600 pairs
- Skip custom compliance set for v1, just train with existing 147 Maez pairs mixed in
- Single-stage training (r=32, attention + MLP)
- ~2 hours of prep work
- ~$2 training cost
- Probably gets us 60-70% of the way

Useful as a fast proof-of-concept before committing to the full plan.
