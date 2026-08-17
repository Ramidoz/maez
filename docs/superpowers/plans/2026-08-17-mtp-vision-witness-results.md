# Witness: MTP+vision on b9596, and Qwen3.8-27B — RUN, with results

2026-08-17, 01:14Z-01:25Z. **Owner-authorised window, Maez's brain
stopped for 11 minutes.** Runs B and C of
`2026-08-16-vision-runs-staged.md` executed. Run A (the frozen-frame
bake-off) was NOT run — it remains blocked on the owner's frame-003
decision, which no lane but the owner may make.

**Headline: both hypotheses that would have blocked the unified-brain
option are FALSIFIED. The bug does not reproduce, and Qwen3.8-27B runs
on the existing engine untouched.**

---

## Window discipline

| | Before (01:14:20Z) | After (01:25:01Z) |
|---|---|---|
| `llama-server.service` | active | active |
| `/health` on :8080 | ok | ok |
| GPU used / free | 21,327 / 2,735 MiB | 21,304 / 2,758 MiB |
| `maez.service` | active | active (never stopped) |

No unit edited, no model pointer moved, no config changed. Test servers
ran on ports 8085/8086, never 8080, so nothing live could bind to a
half-working brain. Both were killed; only the production brain (:8080)
and judge (:8081) remain.

The daemon stayed up throughout and degraded rather than crashing, as
the full-body audit predicted. The watchdog watches `maez.service`, not
the brain, so no false alarm fired.

---

## Run B — does llama.cpp issue #23371 still bite on b9596?

Config: the running brain's exact unit flags plus `--mmproj`.
`Qwen3.6-27B-UD-Q4_K_XL` + `mmproj-F16`, ctx 40960, `--spec-type
draft-mtp --spec-draft-n-max 3`, `-fa on`, `--cache-type-k/v q4_0`,
`--kv-unified`.

### Symptom 1 — load. **PASS.**

Brain and vision encoder loaded together in ~2.6s.
`loaded multimodal model`. 22,403 MiB used, 1,659 MiB free. The issue
raised the possibility of OOM at this step; it did not occur.

### Symptom 2 — VRAM retention after long context. **PASS (small, stable).**

One 23,080-token request: idle 22,397 MiB → 22,479 just after
(+82 MiB), holding +73 to +88 MiB at 15/30/60s. Real retention, but
bounded and stable — not the escalating pressure the issue describes.

### Symptom 3 — mmproj survival under accumulated pressure. **PASS.**

Three cycles of a **38,410-token** request (the issue used ~42k)
followed immediately by an image request:

| Cycle | Prompt tokens | Image latency | Answer | Expected | VRAM Δ |
|---|---|---|---|---|---|
| 1 | 38,410 | 2.0s | "Red is on top." | RED | −3 MiB |
| 2 | 38,410 | 2.0s | "Green is on top." | GREEN | +20 MiB |
| 3 | 38,410 | 1.8s | "Red is on top." | RED | +16 MiB |

Total drift across all three cycles: **+17 MiB**. No OOM, no CLIP
reload failure, no restart loop.

The image was flipped on cycle 2 and the model followed it, so the
vision encoder genuinely re-ran each time rather than returning a
cached answer. That check exists because of a mistake described below.

### Verdict

**Issue #23371 does not reproduce on b9596 with this configuration.**
It was filed against build 9219 and closed as not planned; between
9219 and 9596 something evidently fixed or bypassed it. This is a
witnessed negative, not an inference — but it is a negative for THIS
build and THIS config, and it says nothing about 9219 or about
configurations not tested here.

### A mistake in my own instrumentation, recorded

The first cycle run reported three "successful" image calls returning
in ~1.0s with **empty content**, and I nearly recorded that as a pass.
It was not a pass and it was not a model fault — it was my test.
Qwen3.6 is a thinking model: at `max_tokens=16`, every token went to
`reasoning_content`, `content` came back `''`, and `finish_reason` was
`length`. Proven by re-asking "Say the word banana" at 16 tokens
(empty, reasoning truncated mid-sentence) and at 400 tokens (`banana`,
152 completion tokens).

So the numbers above come from the re-run with a 600-700 token budget
and a verifiable image question whose answer changes when the image
changes. A green tick on an empty response would have been exactly the
class of defect this repo keeps finding: the shape of success without
the substance.

---

## Run C — Qwen3.8-27B with vision, on the untouched engine

Same flags **minus MTP** — the staged file is the plain UD quant, not a
purpose-built MTP variant, so MTP there remains a separate question.

### Load. **PASS, and leaner than expected.**

Loaded on b9596 with no runtime change: `loaded multimodal model`,
21,711 MiB used, 2,351 MiB free — **~840 MiB less than Qwen3.6+vision**,
and it left more headroom than the current production brain does.

This confirms the static prediction from the header comparison: both
report `general.architecture = qwen35`, 866 tensors, 65 blocks, 262144
context. The engine already serves this architecture daily. No upgrade
needed.

### Text and vision. **PASS.**

Sanity: "Say the word banana" → `banana`, with only 99 tokens of
reasoning (Qwen3.6 used 613 for the same question — 3.8 is markedly
more concise in its thinking).

Three cycles at **38,452 tokens** each:

| Cycle | Image latency | Answer | Expected | VRAM Δ |
|---|---|---|---|---|
| 1 | 2.5s | "The colour on top is red." | RED | +14 MiB |
| 2 | 2.1s | "The colour on top is green." | GREEN | +52 MiB |
| 3 | 2.5s | "The colour on top is red." | RED | +52 MiB |

Drift +52 MiB, flat from cycle 2 onward. All three answers correct,
including the flipped middle image.

---

## What this changes, and what it does not

**Falsified:** the two technical objections to the unified brain. The
MTP+vision failure does not occur on this build, and Qwen3.8-27B needs
no runtime work. The 6 June deferral cited "sight, main cognition,
VRAM, runtime upgrade, and MTP in one blast radius" — runtime and MTP
are now measured away, and VRAM is measured *better* than the status
quo.

**Not established, and must not be claimed:**

* **Nothing about answer quality.** Every measurement here is
  operational — does it load, does memory hold, does the vision
  encoder survive. Two colour questions and one "say banana" are not
  an evaluation. Whether Qwen3.8 thinks as well as Qwen3.6 for Maez is
  completely untested.
* **Nothing about MTP on Qwen3.8.** Run C ran without it. Losing MTP
  is a real cost that has not been quantified.
* **Nothing about the vision organ's actual task.** The frozen-frame
  corpus — screen transcription with a zero-invented-specificity gate —
  is what measures useful sight. Two solid-colour bands are not that
  test.
* **Nothing about long-run stability.** Three cycles over ten minutes
  is not a day of Maez's life.

**Still the owner's decision, unchanged by these results.** Whether
Maez's own brain should be the thing that sees cuts across the vision
organ's admission design (Slice 9 admits a separate model only if it
adds truthful coverage). These results remove two reasons to say no.
They do not supply a reason to say yes.

---

## Next

1. **Run A still needs the owner's frame-003 answer.** It is the only
   test here that measures sight at Maez's actual task, and it is
   blocked on ground truth no other lane may author.
2. If the unified brain is pursued, it needs a **quality** bake-off —
   judge-bench against the current brain — not another load test.
3. MTP on Qwen3.8 is an open question: whether an MTP variant of the
   3.8 checkpoint exists, and what losing MTP costs if it does not.
