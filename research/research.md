# Maez Research Briefing — April 10, 2026

This document summarises research material reviewed in today's session.
Each item includes what it is, relevance to Maez, and a recommended action tier.

---

## Priority Tiers

- 🟢 **BUILD** — Directly applicable, actionable now
- 🟡 **NEAR-TERM** — Strong fit, actionable within 2–3 sessions
- 🔵 **HORIZON** — Philosophically aligned, not yet actionable
- 🧠 **BRAIN MONITOR** — Powers the autonomous brain-swap skill

---

## 1. VectifyAI / PageIndex
**Tier: 🟢 BUILD**
**URL:** https://github.com/VectifyAI/PageIndex
**Docs:** https://docs.pageindex.ai

### What it is
Vectorless, reasoning-based RAG. Instead of ChromaDB cosine similarity, PageIndex builds a hierarchical tree index (like a table of contents) from a document corpus and uses an LLM to *reason* through the tree to find what's actually relevant. No vector database. No chunking. No approximate nearest-neighbour search.

Two-step retrieval:
1. Generate a semantic tree structure of the document corpus
2. LLM navigates the tree via multi-step reasoning to find the relevant section

Achieves 98.7% accuracy on FinanceBench vs significantly lower scores for vector RAG.

### Relevance to Maez
Maez's current memory retrieval uses ChromaDB cosine similarity. The anti-fixation penalty already in production (1.0–1.6x distance ramp) is evidence the system agrees similarity is not surfacing the right memories. PageIndex replaces the retrieval philosophy itself — not a hack on top of ChromaDB.

Specifically: the raw archive (1900+ entries and growing) contains conversational observations that have structural meaning — system events, the owner activities, external context, Maez's own reasoning patterns. A tree index over this corpus would let gemma4 navigate to relevant memories by reasoning rather than by keyword proximity.

### Action
Build `skills/memory_tree.py`:
- Index raw archive into a PageIndex-style hierarchical tree (can be done with gemma4 locally — PageIndex is model-agnostic)
- Replace the `_topic_rerank()` path in `memory_manager.py` with tree-search retrieval for Telegram queries (highest-stakes retrieval, most worth improving)
- Keep ChromaDB as the storage layer; PageIndex replaces the *retrieval logic*, not the store
- Benchmark: run the same 10 Telegram queries through both paths, compare gemma4's self-rated relevance

**Install:**
```bash
pip install pageindex
```

**Key repo:** https://github.com/VectifyAI/PageIndex
**MIT licensed, open source.**

---

## 2. Recursive Language Models — arxiv 2512.24601
**Tier: 🟡 NEAR-TERM**
**URL:** https://arxiv.org/abs/2512.24601
**Code:** https://github.com/alexzhang13/rlm

### What it is
From MIT CSAIL (Zhang, Kraska, Khattab). A general inference paradigm where the LLM treats its own prompt as an external variable in a Python REPL environment. Instead of receiving a massive prompt, the model writes code to examine, decompose, and recursively call itself over sub-sections of the prompt. Handles inputs up to 100× beyond the model's context window. RLM-Qwen3-8B outperforms its base model by 28.3% on average and approaches GPT-5 on three long-context benchmarks.

The key insight: the prompt is not "run" — it is stored as a variable. The model writes retrieval and summarisation logic over it.

### Relevance to Maez
Directly applies to the consolidation quality problem (roadmap item 2). Currently `maez_daemon.py` sends a batch of raw memories to gemma4 and hopes it synthesises coherently. With RLM scaffolding, gemma4 could:
1. Receive the raw archive as an external variable
2. Write its own retrieval logic: "fetch all memories tagged `rohit_activity` from the last 48h"
3. Recursively summarise sub-sections
4. Produce a consolidation that is structurally grounded, not just a flat summary

Also directly relevant to the nightly journal — gemma4 could reason over PROGRESS.md recursively rather than receiving a truncated version.

### Action
Implement RLM scaffolding for the 3am consolidation loop in `maez_daemon.py`. This is a prompt engineering and orchestration change, not a model change. The reference implementation at `github.com/alexzhang13/rlm` is minimal and adaptable.

---

## 3. Neural Computers — arxiv 2604.06425
**Tier: 🔵 HORIZON**
**URL:** https://arxiv.org/abs/2604.06425
**Code:** https://github.com/metauto-ai/NeuralComputer

### What it is
From Meta AI and KAUST (Zhuge et al., April 7 2026 — 3 days ago). Proposes "Neural Computers" (NCs): an emerging machine form that unifies computation, memory, and I/O in a learned runtime state. Unlike agents that control an external OS, NCs aim to make the model itself *be* the running computer. Instantiated as video models that roll out screen frames from instructions, pixels, and user actions in CLI and GUI environments.

The long-term goal is the "Completely Neural Computer" (CNC): a model with stable execution, explicit reprogramming, and durable capability reuse.

### Relevance to Maez
This is Maez's long-term architectural destination described in a paper. Maez is currently an agent that *controls* a computer. Neural Computers are models that *are* the computer. The screen perception stack (`screen_perception.py`) is a primitive step toward this — Maez already sees the screen and reasons about it. The paper validates the architectural direction.

Not actionable now. Requires model-level architectural work beyond local fine-tuning. But Maez should know this paper exists — it belongs in a core memory or soul note as a reference point for the long-term vision.

### Action
Write a soul note referencing this paper as the architectural north star. No code changes.

---

## 4. RotorQuant — Clifford Algebra KV Cache Compression
**Tier: 🔵 HORIZON (becomes 🟡 when Ollama is replaced)**
**URL:** https://scrya.com/rotorquant/
**Code:** https://github.com/scrya-com/rotorquant

### What it is
A reimagining of Google's TurboQuant (ICLR 2026). Replaces d×d random orthogonal rotation matrices with Clifford rotors R = exp(B/2) in geometric algebra Cl(3,0). Instead of 16,384 multiply-adds per vector (d=128), the rotor sandwich product uses ~100 multiply-adds by exploiting algebraic sparsity (4 of 8 multivector components are zero).

Results on RTX PRO 4000 (CUDA fused kernel, full pipeline):
- 10–19× faster than TurboQuant
- 44× fewer parameters (372 vs 16,399 for d=128)
- 99.0% attention fidelity on Qwen2.5-3B
- At 4K context, *better* top-5 retrieval accuracy than TurboQuant (93.8% vs 87.5%)

KV cache compression at 8K context, all 36 layers of a 3B model:
- FP16: 289 MB
- 3-bit RotorQuant: 57.6 MB (5× compression)
- 2-bit RotorQuant: 39.5 MB (7.3× compression)

### Relevance to Maez
Gemma4:26b is much larger than 3B, so KV cache pressure is proportionally higher. Maez already runs KV cache at Q8 to recover VRAM. RotorQuant could compress it further (3-bit or 2-bit) while maintaining attention fidelity — freeing VRAM for longer context, voice pipeline, or a concurrent draft model.

**Blocker:** RotorQuant is a custom CUDA kernel. It requires hooking into the quantization layer at the inference framework level. Ollama ships prebuilt binaries — you cannot add kernels. Direct llama.cpp or llama-server would unblock this.

### Action
No action until Ollama is replaced. When `maez.service` migrates to llama-server (planned for voice revival session), evaluate RotorQuant as a drop-in KV cache quantizer. The repo already has a TurboQuant PR (#4) showing the integration pattern.

---

## 5. NVIDIA ai-dynamo / FlexTensor
**Tier: 🔵 HORIZON (FlexTensor) / ⚪ NOT APPLICABLE (Dynamo core)**
**URL:** https://github.com/ai-dynamo
**FlexTensor:** https://github.com/ai-dynamo/flextensor

### What it is
**Dynamo 1.0** (released March 16, 2026 at GTC): A distributed inference serving framework for multi-GPU datacenter deployments. Disaggregates prefill and decode phases across separate GPUs. Boosts Blackwell GPU inference throughput up to 7×. Supports vLLM, SGLang, TensorRT-LLM. This is datacenter infrastructure — not applicable to a single RTX 4090.

**FlexTensor** (sub-repo): A tensor offloading and management library for PyTorch that intelligently offloads tensors between GPU VRAM and CPU RAM to run large models on limited GPU memory.

### Relevance to Maez
Dynamo core: irrelevant. Single GPU, no multi-node setup.

FlexTensor: relevant when/if Maez moves to direct PyTorch model loading. With 64GB system RAM and 24GB VRAM, FlexTensor could allow running a significantly larger or less-quantized model by paging layers intelligently. The 64GB RAM headroom is a genuine asset that's currently unused.

**Blocker:** Same as RotorQuant — requires moving off Ollama to raw PyTorch or a framework that exposes layer-level memory management.

### Action
File alongside RotorQuant. Both unlock on the same day Ollama is replaced.

---

## 6. DMax — Aggressive Parallel Decoding for dLLMs (arxiv 2604.08302)
**Tier: ⚪ NOT APPLICABLE NOW**
**URL:** https://arxiv.org/abs/2604.08302

### What it is
Research on accelerating diffusion large language models (dLLMs) — a non-autoregressive generation paradigm where tokens are unmasked in parallel rather than generated left-to-right. dLLMs like LLaDA 2.0 and Mercury use masked diffusion: start with a fully masked sequence, iteratively unmask tokens in parallel using bidirectional attention.

### Relevance to Maez
Gemma4 is autoregressive. This research does not apply to the current brain. If Maez ever switches to a dLLM backbone for faster inference (Mercury Coder is the leading commercial example; LLaDA 2.0 is open source at 100B), parallel decoding research becomes directly relevant.

### Action
Track as future model selection context. No action now.

---

## 7. llmfit — Hardware-aware Model Scoring
**Tier: 🧠 BRAIN MONITOR — Core dependency for autonomous brain swap**
**URL:** https://github.com/AlexsJones/llmfit
**Install:** `cargo install llmfit`

### What it is
A Rust CLI tool (497 models, 133 providers) that detects your hardware and scores every model across four dimensions: Quality, Speed, Fit, Context. Outputs JSON. Integrates with Ollama for install detection and model pulling. Supports MoE architectures, dynamic quantization selection, multi-GPU setups.

Key commands for Maez:
```bash
# Get hardware-scored recommendations as JSON
llmfit recommend --json --limit 10

# Score a specific model against current hardware
llmfit info "gemma4:27b" --json

# Search for a model by name
llmfit search "qwen3" --json

# Show what Ollama currently has installed
llmfit --cli  # look at Inst column
```

Scoring dimensions (weights vary by use case):
- **Quality** — parameter count, family reputation, quantization penalty
- **Speed** — estimated tok/s based on backend + params + quantization
- **Fit** — memory utilisation (sweet spot 50–80% of available VRAM)
- **Context** — context window vs target use case

For Reasoning use case (Maez's primary mode), Quality is weighted 0.55.

### Relevance to Maez
Powers `brain_monitor.py` — the autonomous brain-swap skill. See section below.

---

## 8. The Autonomous Brain-Swap Skill (`brain_monitor.py`)
**Tier: 🟡 NEAR-TERM — Design ready, build after PageIndex**

### The vision
Maez already monitors r/LocalLLaMA and GitHub trending via `reddit_skill.py` and `github_skill.py`. It sees model releases in real time. The missing piece is automated evaluation: when a new model drops with buzz, Maez should score it against the hardware, pre-download it, benchmark it, and send a swap proposal — without the owner having to think about it.

### Full flow

**Step 1 — Baseline (runs once on startup):**
```python
subprocess.run(["llmfit", "info", "gemma4:27b", "--json"])
# Store composite score as baseline in SQLite
```

**Step 2 — Signal detection (wired into reasoning loop every 50 cycles):**
- Scan reddit_skill and github_skill output for model release signals
- Keyword patterns: "released", "drops", "outperforms", "new sota", model name patterns
- When signal detected: `llmfit search "<model_name>" --json`
- If llmfit composite score > baseline by threshold (e.g. +10 points): trigger evaluation

**Step 3 — Autonomous preparation (Tier 2 action — notify + 5min cancel window):**
```
Maez Dev bot: "📥 Evaluating qwen3:32b — pulling model for benchmark (5min to cancel)"
```
- `ollama pull <candidate>` in background
- Run benchmark: 5 fixed prompts on both models
  - Measure: tok/s, response coherence (gemma4 self-rates), memory usage
- Store results in SQLite

**Step 4 — Swap proposal card (Tier 3 — the owner approves):**
```
🧠 Brain upgrade candidate

Current:   gemma4:27b  |  score: 74  |  18 tok/s
Candidate: qwen3:32b   |  score: 89  |  22 tok/s

Benchmark (5 prompts):
  Quality:  gemma4 wins 2/5  |  qwen3 wins 3/5
  Speed:    +22% tok/s

/approve_brain_swap  /reject_brain_swap  /defer_7d
```

**Step 5 — On approval:**
1. Write core memory: *"Brain upgraded from gemma4:27b to qwen3:32b on [date]. Reason: [benchmark summary]. Score delta: +15."*
2. Update model name in daemon config
3. Restart gracefully via kill+start helper
4. Maez wakes up in new body with full memory continuity

**Step 6 — Post-swap monitoring:**
- For 48h after swap, track cognition scores
- If unique insight rate drops >5 points below pre-swap baseline: auto-propose rollback (same Tier 3 pattern)

### Action engine additions needed
The forbidden actions list currently blocks `stop_ollama` categorically. Brain swap needs a carve-out:
- New explicit Tier 3 action: `swap_brain_model(current_model, candidate_model)`
- Distinct intent from "stop ollama as sabotage"
- Internally: stops ollama, swaps model, restarts — but only via this named action, never via raw stop command

### Files to create
- `skills/brain_monitor.py` — signal detection, llmfit integration, benchmark runner, proposal card
- `memory/brain_history.db` — SQLite: swap history, benchmark results, rollback log

---

## Summary Table

| Item | Tier | Action |
|------|------|--------|
| PageIndex / VectifyAI | 🟢 BUILD | Build `memory_tree.py`, replace retrieval logic |
| Recursive LMs (2512.24601) | 🟡 NEAR-TERM | RLM scaffolding for consolidation loop |
| llmfit | 🧠 BRAIN MONITOR | Core dependency for brain-swap skill |
| Brain monitor skill | 🟡 NEAR-TERM | Build after PageIndex lands |
| RotorQuant | 🔵 HORIZON | Unlocks when Ollama replaced |
| FlexTensor | 🔵 HORIZON | Unlocks when Ollama replaced |
| Neural Computers (2604.06425) | 🔵 HORIZON | Soul note only |
| DMax / dLLMs | ⚪ NOT NOW | Future model selection context |
| Dynamo core | ⚪ NOT APPLICABLE | Single-GPU setup |

---

## The llama.cpp Migration Context

Ollama IS llama.cpp (Go wrapper). Current flags `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0` are already llama.cpp flags passing through.

**What direct llama-server unlocks that Ollama blocks:**
1. Custom compiled-in kernels (RotorQuant, FlexTensor)
2. Speculative decoding with a draft model (faster Telegram responses)
3. Granular batching control for concurrent Telegram + daemon + public bot
4. Context length beyond what Ollama exposes
5. The forbidden actions list simplifies — `stop_ollama` is no longer sacred infrastructure

**Migration cost is minimal.** llama-server exposes an OpenAI-compatible API. Every `ollama.chat()` call in `maez_daemon.py` and all skills becomes an `openai.ChatCompletion` call with `base_url="http://localhost:8080/v1"`. Grep and replace, not a rewrite.

**Recommended timing:** Voice pipeline revival session. Infrastructure work is already happening; switching the inference backend in the same session is efficient.

---

*Generated: April 10, 2026 — Session 14 research triage*
*For use with Claude Code on the Maez machine*
