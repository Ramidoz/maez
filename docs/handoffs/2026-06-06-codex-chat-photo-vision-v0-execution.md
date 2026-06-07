# Handoff → Codex: execute Chat Photo Vision v0

**From:** Claude (covenant/review lane) · **To:** Codex (implementation lane) · **Date:** 2026-06-06
**Relayed by:** Rohit (owner). Two-team switchboard.

## READ FIRST — scope
Build the **missing** `tools/vision_tools.py:vision_analyze_tool` (the Telegram sticker/photo path imports it but it doesn't exist → chat-image vision is silently dark), pointed at the **local** `:8082`/`maez-vision` (LFM2.5-VL-1.6B), and wire the Telegram photo path. **Unblocked** — uses *none* of the broken ScreenCast/PipeWire desktop-capture pipe. Also delivers the first real LFM general-vision quality witness.

**This is NOT desktop screen perception.** It validates LFM on *owner-sent photos*, not desktop screen-OCR (separate, capture-blocked track). Don't touch the screen-capture code.

## Documents
- **Plan (task-by-task):** `docs/superpowers/plans/2026-06-06-chat-photo-vision-v0.md` (8 TDD tasks).
- **Spec:** `docs/superpowers/specs/2026-06-06-chat-photo-vision-v0-design.md`.

## The covenant — "raw photo never leaves home" is a LOCKED DOOR, test-enforced
1. **Loopback hard gate.** Before sending image bytes, refuse any non-loopback `VISION_URL` (host must be `127.0.0.1`/`localhost`/`::1`, resolved) → `{"success":false,"error":"non_local_vision_endpoint"}`, **zero bytes sent**. Even if `MAEZ_VISION_URL` env points remote. Raw pixels go *only* to the local vision model.
2. **Cache containment.** `image_url` is read only if `realpath` is an existing regular file under `get_image_cache_dir()` (symlinks resolved; reject `..`/`http(s)`/arbitrary paths/symlink-escape) → else `{"success":false,"error":"image_not_in_cache"}`. Never a general file reader or exfil path.
3. **No cloud egress of raw image.** Image base64 reaches *only* the loopback endpoint; the cloud brain sees only the *text* analysis (`owner_message_context`, redacted at the door). Test-enforced.
4. **No durable raw-image archive.** Images stay in the pre-existing ephemeral `cache/images` (24h cleanup); add no persistent image store; copy no image bytes to durable memory.
5. **No fabrication.** Vision down/unreachable → `{"success":false}` + honest fallback (sticker path already does); never an invented `analysis`.

## Hard constraints
- **Contract:** `vision_analyze_tool(image_url, user_prompt) -> str` returns JSON `{"success","analysis","error"}` (matches the existing sticker caller, which reads `success`/`analysis`).
- **Reuse, don't duplicate:** import `VISION_URL`/`VISION_MODEL` from `screen_perception`; `get_image_cache_dir` from `platform_base`. Single endpoint source of truth.
- **Downscale `MAEZ_CHAT_PHOTO_VISION_MAX_DIM` (default 1024)** — separate from screen's `MAEZ_VISION_MAX_DIM` (640).
- **Explicit photo seam.** There is **no generic `media_urls` consumer** — they're only buffered/merged. Add the analysis in the **photo-batch-flush** path, *after* album batching settles, *before* `handle_message`. Don't invent a "cognition consumer."
- **Album bound** `MAEZ_CHAT_PHOTO_MAX_IMAGES` (default 3): analyze ≤3, append a plain overflow note.
- **Make `tools` importable** (`tools/__init__.py` if needed) so the existing `from tools.vision_tools import vision_analyze_tool` resolves (fixes stickers for free).
- `unittest` not pytest; full `discover` in `/home/rohit/maez`; **`## Predicted effect`** on behavior commits.

## Claude's review anchors
1. **Loopback gate has teeth** — remote `VISION_URL` → refused, `requests.post` never called (mutation-checkable).
2. **Cache containment has teeth** — `/etc/passwd`, `..`, `http://`, symlink-escape all rejected, file not read.
3. **No raw image in any cloud-bound payload** — only loopback POST carries bytes.
4. **No durable image persistence** — no new image store / no bytes to `memory/`.
5. **Explicit seam, album-bounded, honest fail-safe** — analysis folded into `event.text`; ≤3 + overflow; vision-down → no fabrication.
6. **Reuse not duplicate** the endpoint config; no churn to screen-capture / Slice A/B code.

## Owner-only
The witness (Task 8): **first confirm `:8082/v1/models` serves the LFM2.5-VL-1.6B-backed `maez-vision`** (not the 450M bench leftover), then send photos and judge **good/weak/wrong**. Local merge owner-delegable; no push.

## Current state
main `cbcc5f3` (spec `9581d54` + plan `cbcc5f3`), local-only. Daemon `7005`; `:8080` brain + `:8081` judge untouched; `:8082` currently stopped/started by owner during provisioning (confirm the LFM build at witness time). Crown jewel safe.
