# Chat Photo Vision v0 — Maez Sees Photos You Send — Design

**Date:** 2026-06-06
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner witnesses (send a photo, judge LFM).
**Lane:** Codex implements / Claude reviews. `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`.

## 0. Why — the fastest useful win, and the LFM quality witness, with zero desktop-capture

The chat-image vision path is **wired but hollow**: `skills/surface/telegram_adapter.py` already downloads + caches user photos/stickers and calls `tools.vision_tools.vision_analyze_tool(image_url, user_prompt)` — but **that tool does not exist** (the import `ModuleNotFoundError`s; analysis silently fails today). This slice **builds the missing tool**, pointed at the now-live local vision endpoint (`:8082`/`maez-vision`, LFM2.5-VL-1.6B). It needs **none** of the broken ScreenCast/PipeWire desktop-capture pipe — the owner hands Maez the image directly. It ships a real feature (Maez sees photos you send) **and** is the first honest witness of LFM's vision quality on real images.

**Scope honesty:** this validates LFM's **general** vision quality on owner-sent photos. It does **NOT** validate desktop **screen-reading/OCR at 640px** (a separate, harder task still blocked on the capture pipe). Two witnesses; this is the unblocked one.

## 1. The spine

> The owner's photo is consented local input. **The raw image is seen ONLY by the local vision model (`:8082`); its pixels never leave the box.** Only the resulting *text* analysis enters cognition — as `owner_message_context`, redacted at the cloud door. Raw images live in the existing ephemeral cache (24h cleanup), never a durable archive; one photo never becomes a durable person-model. If vision is unavailable, say so honestly — never fabricate a description.

## 2. Scope

**v0 MUST-HAVES:**
1. **Implement `tools/vision_tools.py:vision_analyze_tool(image_url, user_prompt) -> str`** (async), returning a JSON string matching the existing caller contract: `{"success": bool, "analysis": str, "error": str}`.
2. **Reuse the endpoint config from `screen_perception`** — import the env-driven `VISION_URL` / `VISION_MODEL` (`:8082`/`maez-vision`); no duplicated/hardcoded endpoint. The multimodal call shape mirrors `screen_perception` (`content: [{text}, {image_url: data:image/...;base64,…}]`).
3. **Downscale to `MAEZ_CHAT_PHOTO_VISION_MAX_DIM` (default 1024)** before send — separate from screen perception's `MAEZ_VISION_MAX_DIM` (640). Chat photos are occasional + owner-sent → afford the detail (text/objects/documents/handwriting).
4. **Wire the Telegram photo path** to invoke `vision_analyze_tool` (stickers already call it → fixed for free).
5. **Fail-safe / no-fabrication:** vision unreachable/error → `{"success": false, "error": …}`; callers fall back honestly (the sticker path already does) — never a fabricated `analysis`.
6. **Loopback hard gate (locked door, not intention):** before sending image bytes, `vision_analyze_tool` **refuses any non-loopback `VISION_URL`** — host must resolve to `127.0.0.1` / `localhost` / `::1`. Even if `MAEZ_VISION_URL` env points remote (`screen_perception._normalize_vision_url` will normalize arbitrary `http(s)` hosts), the tool returns `{"success": false, "error": "non_local_vision_endpoint"}` and sends **nothing**. Raw owner-photo pixels never reach a non-local host.
7. **Image input is cache-contained:** `image_url` accepts **only** a real local file whose `realpath` (symlinks resolved) is under `get_image_cache_dir()`. Reject `http(s)://`, `..`, arbitrary filesystem paths, symlink escapes, non-existent/non-regular files → `{"success": false, "error": "image_not_in_cache"}`. The tool is never a general file reader or an exfil path.
8. **Album bound:** cap analyses per message/album at `MAEZ_CHAT_PHOTO_MAX_IMAGES` (default **3**); beyond the cap, skip the extras and add a plain overflow note (e.g. "(+N more images not analyzed)"). One album can't fan out unbounded vision calls.

**DEFERRED:** video/animated-sticker analysis; durable curation of photo memories (a v1 "remember this photo" path, governed); a shared vision-client refactor (DRY `screen_perception` + `vision_tools` later); desktop screen-OCR (the capture-pipe track).

## 3. Architecture

`vision_analyze_tool(image_url, user_prompt)`:
1. **Gate A — loopback:** resolve `VISION_URL`'s host; if not `127.0.0.1`/`localhost`/`::1` → return `{"success": false, "error": "non_local_vision_endpoint"}`, send nothing (Rail 1 / must-have 6).
2. **Gate B — cache containment:** `realpath(image_url)` must be an existing regular file (not symlink-escaping) under `get_image_cache_dir()`; else `{"success": false, "error": "image_not_in_cache"}` (must-have 7).
3. Load the cached image; downscale to `MAEZ_CHAT_PHOTO_VISION_MAX_DIM` (1024) via PIL.
4. Base64-encode; POST to **`VISION_URL`** (imported from `screen_perception`, `:8082`/`maez-vision`) with the multimodal message (`user_prompt` + the image), bounded `max_tokens` + timeout.
5. Parse the model's text → `{"success": true, "analysis": <text>}`. On any failure (unreachable/non-200/parse) → `{"success": false, "error": <stage>}` (no fabricated analysis).
6. **Never** writes the raw image anywhere durable; **never** sends image bytes to any endpoint other than the (loopback-verified) `VISION_URL`.

**Telegram photo wiring (explicit seam — there is NO generic `media_urls` consumer; they are only buffered/merged):** add a real photo-analysis step in the **photo-batch flush path** (`_flush_photo_batch` / the media-group settle), **after** album batching settles and **before** `handle_message(event)`. For each cached image up to `MAEZ_CHAT_PHOTO_MAX_IMAGES` (3), call `vision_analyze_tool` (photo prompt), collect the `analysis` strings (+ an overflow note past the cap), and fold them into `event.text` (mirroring how `_handle_sticker` sets `event.text`). The analysis is then part of the **owner's message context** → already `owner_message_context` for egress. Stickers keep their existing direct call.

## 4. Rails (the covenant for this slice)

1. **Raw image is LOCAL-ONLY — enforced by a loopback gate, not assumption.** The tool **refuses to send** unless `VISION_URL` resolves to loopback (`127.0.0.1`/`localhost`/`::1`) — even if env points it remote. Image bytes go **only** to the loopback vision endpoint and **never** appear in any cloud-bound payload (the cloud brain sees only the *text* analysis). Test-enforced (remote `VISION_URL` → refused, zero bytes sent).
1b. **Input is cache-contained.** `image_url` is read **only** if its `realpath` is an existing regular file under `get_image_cache_dir()` (symlinks resolved, `..`/`http(s)`/arbitrary paths/symlink-escape rejected). The tool is never a general file reader or exfil path. Test-enforced.
2. **No durable raw-image archive.** Raw images stay in the pre-existing ephemeral `cache/images` (24h `cleanup_image_cache`); this slice creates **no new persistent raw-image store** and copies no image bytes into durable memory. Test-enforced.
2b. **Album-bounded.** ≤ `MAEZ_CHAT_PHOTO_MAX_IMAGES` (3) vision calls per message/album; overflow noted, not analyzed. No unbounded fan-out.
3. **Analysis is `owner_message_context`.** The text analysis enters cognition as part of the owner's message → covered by the existing minimizable/redact-at-the-door path. No raw pixels egress; the text is redacted cloudward like any owner-message content.
4. **No durable person-model from one photo.** A single photo's analysis is ephemeral input to the reply; v0 does **not** auto-create durable memories modeling identifiable people from it ([[feedback_third_party_autonomous_research_boundary]]).
5. **No fabrication.** Vision down → honest `success:false` + fallback, never an invented description ([[feedback_no_fabrication]]).
6. **Reuse, don't duplicate** the endpoint config (`screen_perception` VISION_URL/MODEL); a single source of vision-endpoint truth.

## 5. Config

```
MAEZ_VISION_URL / MAEZ_VISION_MODEL    # shared endpoint (screen_perception), default :8082 / maez-vision
MAEZ_VISION_MAX_DIM            = 640   # screen/continuous perception (unchanged)
MAEZ_CHAT_PHOTO_VISION_MAX_DIM = 1024  # chat-photo (new, this slice)
MAEZ_CHAT_PHOTO_MAX_IMAGES     = 3     # album bound (new, this slice)
```

## 6. Tests

1. **No cloud egress of raw image (HEADLINE):** mock the HTTP layer; assert the image base64 is POSTed **only** to `VISION_URL` (`:8082`), and never appears in any other (cloud) request payload.
2. **Loopback gate (HEADLINE):** with `MAEZ_VISION_URL` set to a **remote** host, `vision_analyze_tool` returns `{"success": false, "error": "non_local_vision_endpoint"}` and the HTTP layer receives **zero** image bytes (assert no POST fired).
3. **Cache containment:** `image_url` pointing at `/etc/passwd`, an `http(s)://` URL, a `..`-traversal, a symlink escaping the cache, or a missing file → `{"success": false, "error": "image_not_in_cache"}`, file **not read / not sent**; a real file under `get_image_cache_dir()` → accepted.
4. **No raw-image persistence:** after an analysis, assert no image bytes are written to durable memory / no new persistent image store (only the pre-existing ephemeral cache).
5. **Endpoint reuse:** `vision_analyze_tool` uses `screen_perception`'s `VISION_URL`/`VISION_MODEL` (assert host:port + model), not a hardcoded other.
6. **Downscale:** the sent image is downscaled to ≤ `MAEZ_CHAT_PHOTO_VISION_MAX_DIM` (1024), distinct from the 640 screen default.
7. **Contract + fail-safe:** success → JSON `{"success":true,"analysis":…}`; vision unreachable (mock) → `{"success":false,…}` with **no** `analysis` fabricated.
8. **Photo wiring + album bound:** a Telegram photo event invokes `vision_analyze_tool` (not just stickers) at the batch-flush seam; an album of >3 images analyzes exactly 3 + emits the overflow note.
9. Full `discover` green; apples-to-apples in `/home/rohit/maez`.

## 7. Witness (owner-run — the LFM quality test, today, no capture needed)

**Precondition (verify the right eye-brain is loaded):** confirm `:8082/v1/models` serves the `maez-vision` alias backed by **LFM2.5-VL-1.6B** (the last `:8082` state may have been the 450M model from benchmarking — don't silently witness the wrong model). E.g. `curl -s http://127.0.0.1:8082/v1/models` and confirm the served file/alias, then proceed.

Send Maez photos via Telegram and judge the `analysis`:
1. **General scene:** an ordinary photo → is ACTIVITY/objects/context accurate?
2. **Text/OCR:** a photo containing text (a document, a sign, a screenshot) → does LFM read the visible text at 1024px?
3. **People present:** a photo with a person → described as context, **no durable person-model**; appropriate, not invasive.
4. **Vision-down honesty:** stop `:8082` briefly → Maez says it couldn't see the image, doesn't fabricate.
Owner verdict: **good / weak / wrong** on LFM's real-image reading — the keep/replace signal for the eye-brain (general-vision axis).

## 8. Acceptance rules

1. `vision_analyze_tool` implemented, contract-matching, reusing `screen_perception` endpoint config (Rail 6; tests 5,7).
2. **Loopback gate + cache containment + no-cloud-egress + no durable archive** (Rails 1/1b/2/2b; tests 1,2,3,4) — the covenant headline (locked door: remote endpoint refused, out-of-cache input refused, raw pixels never egress, no persistent image store).
3. Analysis is `owner_message_context`, redacted cloudward; raw pixels never egress (Rail 3; tests 1,2).
4. 1024 chat-photo downscale, separate from 640 (test 6).
5. **Explicit photo seam** (batch-flush, before `handle_message`) wired; stickers fixed for free; album-bounded (≤3 + overflow); honest fail-safe (Rails 2b,5; tests 7,8).
6. No durable person-model from one photo (Rail 4).
7. Witness precondition: `:8082` confirmed serving LFM-backed `maez-vision` before judging (§7).
8. Full suite green; **`## Predicted effect`** on the impl commit.

## 9. Predicted effect

When the owner sends a photo, Maez downscales it to 1024, sends it **only** to the local LFM (`:8082`), and answers what it sees; the text analysis enters the conversation as `owner_message_context` (redacted at the cloud door); the raw image never leaves the box and is not durably archived (ephemeral cache only); a single photo creates no durable person-model; if vision is down, Maez says so. **Falsifiable:** sending a photo yields an accurate (per owner) description; a network trace shows image bytes only to `127.0.0.1:8082`; no image bytes in durable memory; stopping `:8082` yields an honest "couldn't see it," not a fabrication. **This also delivers the LFM general-vision quality witness** — independent of the still-blocked desktop-capture pipe.

## 10. Lane / deferred

Codex implements / Claude reviews (anchors: **no-cloud-egress-of-raw-image** + **no-durable-image-persistence** by test, endpoint reuse, fail-safe-no-fabrication, photo wiring). Owner witnesses (send photos, judge LFM). **Desktop screen-OCR + the PipeWire/Gst capture fix remain a separate, parallel track.**
