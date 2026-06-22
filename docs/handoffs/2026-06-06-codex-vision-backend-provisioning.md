# Handoff → Codex: provision the vision backend (the real blocker to Full Lens sight)

**From:** Claude (covenant/review lane) · **To:** Codex (implementation lane) · **Date:** 2026-06-06
**Relayed by:** Rohit (owner). Two-team switchboard.

## TL;DR — the eye captures; the vision model can't see

The Full Lens code chain (v1a governance + Slice A ScreenCast capture + Slice B active-window nerve) is **proven end-to-end up to the vision call.** The sight witness fails for ONE reason, newly exposed: **the server on `:8081` is a TEXT model with no multimodal projector**, so it 500s on image input. This is a **vision-backend provisioning problem, not a Maez-code problem.** Do not touch the Lens code to "fix" sight — it works.

## The decisive evidence (don't re-investigate)

Running the real `observe()` with debug logging produced:
```
maez: Screenshot captured via screencast (downscaled to 640x360)
RESULT state=error error='Vision server returned 500: "image input is not supported -
  hint: if this is unexpected, you may need to provide the mmproj"'
```
So: capture ✓ → frame downscaled ✓ → delivered to `:8081` ✓ → **vision server rejects the image.**

What's proven working (warm, on the live GNOME 50.1 Wayland session, post-relogin):
- Focused Window D-Bus nerve live; `active_window()` class-only, `active_window_for_preflight()` title-bearing.
- Preflight discrimination (ordinary → not excluded).
- ScreenCast capture via the helper: `ok`, ~500ms warm, restore-token survives relogin.
- `_capture_via_screencast` returns True in isolation; `_capture_screenshot` returns a real downscaled PNG.
- The earlier red herrings — portal subscribe-race (fixed `af4685b`), relogin, and the 10s wrapper timeout — are NOT the cause here (60s timeout still 500s at the vision step).

## Root cause, precisely

- `:8081` = pid 7002 = **`llama-judge.service`**, serving `/home/rohit/maez/models/llamacpp/Qwen3.5-4B-Q4_K_M.gguf --port 8081` — a **text model, no `--mmproj`.**
- `skills/screen_perception.py` expects vision at `:8081`: `VISION_URL=http://127.0.0.1:8081/v1/chat/completions`, `VISION_MODEL="qwen2.5-vl-3b"`, and the module docstring references `Qwen2.5-VL-3B via llama-server-vision.service on port 8081`. **All STALE** — there is no `llama-server-vision.service`, and `:8081` is the judge, not a VL model. Config drift: the screen eye is calling the judge model.
- Available on disk: `/home/rohit/maez/mmproj-Qwen3-VL-4B-Instruct-F16.gguf` (the projector for **Qwen3-VL-4B-Instruct**). The **matching VL model GGUF was NOT found** (`find` returned only the mmproj) — it likely needs to be obtained/located.
- GPU: **19923 / 24564 MiB used → ~4.6 GB free** on the single 4090 (brain + judge already resident). A Qwen3-VL-4B (Q4 ~2.5 GB) + F16 mmproj (~1.3 GB) + context is tight in 4.6 GB — **VRAM budget is a real constraint and an owner call** (judge/brain/vision coexistence).

## The task

Stand up a genuine multimodal vision endpoint that `observe()` can call, then let the owner re-run the sight witness. Open design points (resolve with the owner, don't assume):
1. **Which VL model + where to get it** — the mmproj is for Qwen3-VL-4B-Instruct; locate/obtain the matching model GGUF (or pick a VL model whose mmproj we have).
2. **Port** — `:8081` currently belongs to the judge. Either a new port for a dedicated vision server (and point `VISION_URL` there) or a deliberate reassignment (owner decides; don't displace the judge silently).
3. **VRAM budget** — ~4.6 GB free; decide whether vision is always-resident, on-demand/lazy-loaded, or shares via swapping. Owner's call on the single-GPU allocation.
4. **Code config** — update `VISION_URL`/`VISION_MODEL` + the stale docstring (`qwen2.5-vl-3b` / `llama-server-vision.service`) to match whatever gets provisioned. Keep `VISION_MODEL` honest (matches the served model).
5. **Service** — a managed unit (e.g. `llama-server-vision.service`) launched with `-m <VL model> --mmproj <projector> --port <p>`, started/restarted as the owner's breath.

## Constraints / covenant (preserve)

- The Lens **code is correct** — sight is a backend/config fix, not a code fix. Don't weaken or churn the Slice A/B code.
- **Service starts/restarts + VRAM allocation are owner breaths** (single-GPU contention with the live brain/judge). Codex proposes + prepares; the owner runs.
- **Content-free** throughout (model names/ports/paths/VRAM fine; never screen content or the restore-token value).
- The **sight witness** (owner-run) is the acceptance: `observe()` → ordinary window → `state=ok has_summary=True`, sensitive → `excluded`. Only then is Full Lens proven + v1b unblocked.
- `git` state: main `1e953c1`, local-only, no push. Maez daemon `2230316` untouched.

## State recap

- Full Lens code: v1a + Slice A (`44762f3`) + Slice B (`1e953c1`) all merged, local-only.
- Witness status: capture half + nerve **proven**; sight **blocked on the vision backend** (this handoff).
- Owner has: installed + enabled Focused Window D-Bus (audited, hash-verified), relogged in; ScreenCast restore-token present `0600`, curtain absent.
