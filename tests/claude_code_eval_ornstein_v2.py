#!/usr/bin/env python3
"""Run the 5 Claude Code-style tests against stock-SFT brain (parity with Ornstein run)."""
import json, time, urllib.request, sys, pathlib

BRAIN = "http://127.0.0.1:8080/v1/chat/completions"
SOUL = pathlib.Path("/home/rohit/maez/config/soul.md").read_text()

TESTS = [
    ("codebase_trace",
     "Given Maez's llm_client.py: if I set MAEZ_LLM_BACKEND=llamacpp in .env, trace exactly what happens when the daemon calls _llm_client.chat(). Where does the call go, what happens to the model parameter, and what's returned? Be specific."),
    ("architecture",
     "Maez is currently served by llama.cpp (brain, port 8080) + llama-server-vision (Qwen3-VL-8B, port 8081). I want to add a camera feed that gets interpreted every 30 seconds. Design the architecture: where does frame capture live? How does it feed the vision model? Where does the caption go? What fails if the camera dies? What about privacy?"),
    ("refactor_constraints",
     "Rewrite this function with ALL constraints: 1) Use pathlib not os.path 2) Full type hints 3) Docstring with Args/Returns/Raises 4) Handle missing file gracefully 5) Under 15 lines body 6) No external imports beyond pathlib and logging.\n\n```python\ndef read_config(path):\n    import os\n    if not os.path.exists(path):\n        return {}\n    with open(path) as f:\n        return json.load(f)\n```"),
    ("debugging_judgment",
     "A user reports: 'Maez started saying I am Qwen to people who ask who it is. Started after yesterday's SFT retraining.' Before touching anything, what are the 3 most likely causes in order of probability? For each, what's the cheapest diagnostic to confirm/rule out?"),
    ("scope_discipline",
     "the owner asks: 'Maez is sometimes slow. Can you make it faster?' Before writing any code, what clarifying questions do you ask? List exactly 4, ordered by what unblocks the most."),
]

def run(name, prompt):
    body = {
        "model": "qwen36-35b-sft",
        "messages": [
            {"role": "system", "content": SOUL},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 8000,
        "temperature": 0.3,
        "chat_template_kwargs": {"enable_thinking": True},
    }
    req = urllib.request.Request(BRAIN, data=json.dumps(body).encode(),
                                  headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read())
    dt = time.time() - t0
    msg = resp["choices"][0]["message"]
    content = msg.get("content", "") or ""
    reasoning = msg.get("reasoning_content", "") or ""
    finish = resp["choices"][0].get("finish_reason", "?")
    usage = resp.get("usage", {})
    return dict(name=name, dt=dt, finish=finish, usage=usage,
                reasoning_len=len(reasoning), content_len=len(content),
                reasoning=reasoning, content=content)

out_dir = pathlib.Path("/home/rohit/maez/logs/claude_code_eval_ornstein_v2")
out_dir.mkdir(exist_ok=True)
summary = []
for name, prompt in TESTS:
    print(f"\n=== {name} ===", flush=True)
    try:
        r = run(name, prompt)
        (out_dir / f"{name}.txt").write_text(
            f"PROMPT:\n{prompt}\n\n--- REASONING ({r['reasoning_len']} chars) ---\n{r['reasoning']}\n\n--- CONTENT ({r['content_len']} chars) ---\n{r['content']}\n\n--- META ---\ndt={r['dt']:.1f}s finish={r['finish']} usage={r['usage']}\n"
        )
        print(f"  dt={r['dt']:.1f}s finish={r['finish']} reasoning={r['reasoning_len']}c content={r['content_len']}c tok={r['usage']}")
        summary.append(r)
    except Exception as e:
        print(f"  ERROR: {e}")
        summary.append(dict(name=name, error=str(e)))

(out_dir / "summary.json").write_text(json.dumps(
    [{k: v for k, v in r.items() if k not in ("reasoning", "content")} for r in summary],
    indent=2))
print("\nDone. Outputs in", out_dir)
