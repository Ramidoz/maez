# Brain benchmark driver

This package is a producer-evidence instrument for the recall default-on latency
work. It does not flip Maez, does not choose a brain, and does not certify voice
continuity.

The unit suite proves the driver logic with stubbed inference: sandbox egress,
variant validation, the production `focused_synthesize(chat_fn=...)` seam,
two-stage `k=3` / `k=7` battery orchestration, hard gates, the advisory judge
library path, content-free packet output, and quarantined debug dumps. The owner
CLI does not run the advisory judge yet; it emits the deterministic screen
packet. Judge wiring remains an explicit follow-up, not an inert CLI flag.

The real benchmark is owner-operated through the sandbox launcher against real
local model endpoints. Its `BenchPacket` is producer evidence only. Rohit's
owner verdict and the separate S5 voice-continuity gate are still required
before any 2b re-run or default-on decision.

Minimal owner-run shape:

```bash
.venv/bin/python scripts/brain_bench/launcher.py /tmp/maez-brain-bench \
  --variants-config /path/to/variants.json \
  --out logs/brain_bench_packets/packet.json
```

Each variant entry must name the endpoint, model, and closed ops evidence:

```json
{
  "label": "current-q4",
  "base_url": "http://127.0.0.1:11434",
  "model": "local-model",
  "ops": {
    "api_family": "ollama",
    "topology": "reuse_endpoint",
    "bind_host_verified": true,
    "live_daemon_disturbance": false,
    "gpu_contention": "low",
    "startup_health": "ok",
    "streaming_support": true,
    "restart_recovery": "clean"
  }
}
```
