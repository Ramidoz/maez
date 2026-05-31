# Brain benchmark driver

This package is a producer-evidence instrument for the recall default-on latency
work. It does not flip Maez, does not choose a brain, and does not certify voice
continuity.

The unit suite proves the driver logic with stubbed inference: sandbox egress,
variant validation, the production `focused_synthesize(chat_fn=...)` seam,
two-stage `k=3` / `k=7` battery orchestration, hard gates, the advisory judge
library path, content-free packet output, and quarantined debug dumps. The owner
CLI does not run the advisory judge yet; it emits the deterministic screen
packet with `judge_evaluated: false` and `null` judge-derived winrates. Judge
wiring remains an explicit follow-up, not an inert CLI flag.

The real benchmark is owner-operated through the sandbox launcher against real
local model endpoints. Its `BenchPacket` is producer evidence only. Rohit's
owner verdict and the separate S5 voice-continuity gate are still required
before any 2b re-run or default-on decision.

## Citation render v1/v2 paired run

For the recall citation-accuracy slice, verification is an owner/Claude-operated
paired benchmark, not a unit test and not a live flip. Run the same variants in
the same session twice:

1. v1 baseline: leave `MAEZ_RECALL_CITATION_RENDER_V2` unset or `0`.
2. v2 candidate: set `MAEZ_RECALL_CITATION_RENDER_V2=1` for the launcher
   process.

Compare v2 against the same-session v1 packet and the pre-registered floors:
`multi_year` must improve materially from the 6/10 baseline, `dated_hit` must
stay at least 9/10, `both_shaped` must stay at least 8/10, overall
answered-grounded rate must not regress, and any new false-absence or
wrong-absence is a blocker. The debug dump records `citation_render_version`
for each raw sample so reviewers can prove the prompt actually used v1 or v2;
the producer `BenchPacket` stays content-free and does not carry raw answer or
evidence text.

Minimal owner-run shape:

```bash
.venv/bin/python scripts/brain_bench/launcher.py /tmp/maez-brain-bench \
  --variants-config /path/to/variants.json \
  --out logs/brain_bench_packets/packet.json
```

Each variant entry must name the closed wire protocol, endpoint, model, and
closed ops evidence. `backend_family` selects the transport path:

- `ollama` appends `/api/chat`.
- `openai_compatible` appends `/v1/chat/completions`.

`openai_compatible` means a local loopback server speaking that wire protocol,
such as llama-server. It is not permission to call external OpenAI/cloud
endpoints. `base_url` must stay pathless host:port.

```json
{
  "label": "current-q4",
  "backend_family": "openai_compatible",
  "base_url": "http://127.0.0.1:8080",
  "model": "qwen36-27b",
  "ops": {
    "api_family": "llama_cpp",
    "topology": "separate_server",
    "bind_host_verified": true,
    "live_daemon_disturbance": false,
    "gpu_contention": "high",
    "startup_health": "ok",
    "streaming_support": true,
    "restart_recovery": "manual"
  }
}
```

`draft_model` is currently only wired for the Ollama payload shape. The
OpenAI-compatible path rejects it rather than silently ignoring a speculative
decoding claim.
