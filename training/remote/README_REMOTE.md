# Remote training runbook — RunPod H100 PCIe 80 GB

Session 11t's remote training workflow. Pasteable step-by-step.
Assumes the pod has been provisioned with the `maez-training` network
volume attached at `/workspace`.

---

## Before you start

| Check | Command / action |
|---|---|
| Pod is running | RunPod UI → Pods → status `Running` |
| SSH command is copied | RunPod UI → Connect → "SSH over exposed TCP" |
| `/home/rohit/maez/training/` exists locally | `ls /home/rohit/maez/training/` |
| Extractor output exists | `ls /tmp/probe.jsonl` (161 pairs from today's dry run) |

Replace `<ip>`, `<port>` below with the values from RunPod's SSH command.

---

## 1. Push code + corpus to the pod

```bash
# Set once per session
POD_SSH="root@<ip> -p <port>"
RUN_NAME="2026-04-11-first-run"

# Create the run directory on the remote
ssh $POD_SSH "mkdir -p /workspace/training/runs/$RUN_NAME"

# Push training scripts (exclude the local venv + runs dir to keep it small)
rsync -avz --exclude '.venv' --exclude 'runs/' --exclude '__pycache__' \
    --exclude 'unsloth_compiled_cache' \
    /home/rohit/maez/training/ \
    ${POD_SSH/-p /-e "ssh -p }":/workspace/training/

# ^ The -e "ssh -p <port>" dance is awkward; simpler form:
rsync -avz -e "ssh -p <port>" \
    --exclude '.venv' --exclude 'runs/' --exclude '__pycache__' \
    --exclude 'unsloth_compiled_cache' \
    /home/rohit/maez/training/ \
    root@<ip>:/workspace/training/

# Push the extracted training pairs into the run directory
rsync -avz -e "ssh -p <port>" \
    /tmp/probe.jsonl \
    root@<ip>:/workspace/training/runs/$RUN_NAME/training_pairs.jsonl
```

---

## 2. SSH in and bootstrap the pod

First-time only (~10 min):

```bash
ssh -p <port> root@<ip>

# Once inside:
cd /workspace/training
bash remote/setup_pod.sh
```

What this does:
- Creates `.venv` on the **persistent volume** (not ephemeral container disk)
- Installs from `requirements.lock.txt` (~5 min)
- Pre-downloads `unsloth/gemma-4-26B-A4B-it` into `/workspace/.cache/huggingface` (~5 min)
- Verifies CUDA + unsloth load

Setup is **idempotent** — safe to re-run on a future pod pointing at the same volume. Future runs will skip both `pip install` and the model download.

---

## 3. Run the training ladder

```bash
# Still SSH'd in:
cd /workspace/training
bash remote/train_run.sh 2026-04-11-first-run
```

Two phases:
1. **Sanity check** — 1 training step on fake 3-pair data. ~3–5 min. Fails fast if the model architecture isn't supported.
2. **Full training** — 161 pairs × 1 epoch. ~5–8 min on H100 PCIe.

Watch GPU usage from a second SSH session:
```bash
watch -n 2 nvidia-smi
```

Expected peak VRAM: **~15–25 GB** on the 80 GB card. If it OOMs, that's a signal something is wrong with the MoE fit (not 11t's problem — report back and we tune).

Artifacts land in `/workspace/training/runs/2026-04-11-first-run/`:
- `adapter/` — PEFT safetensors
- `train.log` — full stdout/stderr
- `summary.json` — hyperparams + loss + runtime

---

## 4. Pull the adapter back

From your local machine (new terminal):

```bash
cd /home/rohit/maez/training
mkdir -p runs/2026-04-11-first-run

rsync -avz -e "ssh -p <port>" \
    root@<ip>:/workspace/training/runs/2026-04-11-first-run/ \
    runs/2026-04-11-first-run/

ls -la runs/2026-04-11-first-run/adapter/
cat runs/2026-04-11-first-run/summary.json
```

The adapter directory is typically ~150–400 MB. Transfer <1 min.

---

## 5. Scrub personal data from pod ephemeral disk

Before destroying the pod, delete the training corpus + adapter from
the pod's ephemeral view **but keep the HF model cache** on the
persistent volume:

```bash
# SSH back in
ssh -p <port> root@<ip>
rm -rf /workspace/training/runs/*
# Keep: /workspace/.cache/huggingface/  (model weights only, no personal data)
# Keep: /workspace/training/.venv/       (pip packages only)
exit
```

---

## 6. Destroy the pod

In the RunPod UI:
- Pods → your pod → **Stop** then **Terminate**
- Billing stops the moment "Running" → "Stopped"
- The **Network Volume stays** — its ~$7/month flat charge continues, but no GPU bill

Set a spending alert before next session (RunPod UI → Billing → Alerts) at $20 to catch runaway pods.

---

## 7. Verify nothing was left running

From local:
```bash
curl -s -m 5 https://<pod-url>/ || echo "pod is gone (expected)"
```

---

## Emergency stop (if something goes wrong mid-session)

- **Abort training mid-run**: Ctrl-C in the SSH session. `train_lora.py` saves no checkpoint in 11t's initial version — the run dir will be partial. Delete it and re-run.
- **Pod stuck "Running" but unresponsive**: RunPod UI → Stop → Terminate
- **Accidentally overspending**: Stop the pod. The volume's flat cost continues; delete the volume if you want to stop that too (but you'll lose the 49 GB HF cache).

---

## Future sessions (11u+) on the warm volume

On run #2+ with the volume already cached:

```bash
# 1. Launch new pod with the same volume attached
# 2. rsync new training_pairs.jsonl up (run from local)
# 3. ssh in, cd /workspace/training, bash remote/train_run.sh <new-run-name>
# 4. rsync adapter back
# 5. destroy pod
```

Total wall clock: **~10–15 min per run** (no model download, no pip install). Cost: **~$0.50–0.80 per run** on H100 PCIe.

Maez will eventually drive this loop herself via the `proposal_type='training_run'` rail (11u). For now, it's a human-run workflow.
