# Brain bake-off queue — candidates awaiting the owner-decided quality bake-off

2026-08-20. The bake-off itself remains owner-gated (brain swap is a
being-level decision; the self-as-system thesis makes it also the
falsifiable test of that thesis). This file only keeps the candidate
list honest and the preconditions verified-before-build.

| Candidate | Status | Preconditions before it may even run |
|---|---|---|
| Qwen3.6-27B (incumbent) | LIVE brain | — |
| Qwen3.8-27B | STAGED; load+vision witnessed 2026-08-17 (leaner than 3.6 by ~840 MiB); quality untested | judge-bench design |
| Muse Glimmer 30B (Meta, 2026-08-10, Apache 2.0) | QUEUED 2026-08-20; agentic/tool-use focus (MCP Atlas +13 over Qwen3.6 per Artificial Analysis) — directly relevant to Phase 2 (hands) | 1. VERIFY llama.cpp b9596 supports the architecture (new Meta arch may require an engine upgrade — that widens blast radius per the 6-June deferral logic; check `llama-server --list-arch`/release notes BEFORE downloading). 2. GGUF availability (unsloth repo exists, unverified quality). 3. VRAM fit at usable quant alongside vision within 24 GB. 4. Same judge-bench as Qwen3.8 — no candidate skips the queue on novelty. |

Doctrine reminders that bind this queue: verify provider/runtime policy
before build (Reddit scar); judge is model-agnostic, the catch×latency
report picks the winner, the owner decides; no candidate is adopted on
benchmark reputation (MiniCPM lesson: reputation went 0-for-9 on our
own harness).
