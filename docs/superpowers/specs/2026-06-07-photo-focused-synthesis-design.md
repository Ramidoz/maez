# Photo Focused-Cognition Synthesis — Design (direction b)

**Date:** 2026-06-07 · **Lane:** Claude implements / Codex reviews (swapped) · **Branch:** `photo-focused-synthesis`

## Problem (witnessed live)

Live witness 2026-06-07 22:41 (daemon 81895, merged main): the LFM-1.6B vision
model **succeeded** on a real owner photo — diagnostic
`Photo vision diagnostic image=1 success=True analysis_chars=342 error=none`.
Routing fix `2bdd191` correctly forwarded the analysis to synthesis. Yet the
reply was still *"I can't see the image. The vision pipeline is offline, so the
photo came through as blank data to me."*

**Root cause:** the photo analysis reaches `daemon.handle_message`, but that path
builds the full ~megaprompt — which includes a *self-diagnostic "broken systems"
block* (`skills/web_interface.py:3588`) fed by the cyclic "screen perception
disabled" log line:

> "Vision (screen perception): Intentionally retired. Maez cannot see what's on
> your screen."

The brain over-generalizes "cannot see [screen]" → "cannot see [this photo]" and
lets it override the 342-char analysis sitting right beside it. This is the
[[feedback_focused_cognition_over_megaprompt]] knowledge-conflict: held evidence
losing to a contradicting block in the same megaprompt.

## Fix: synthesize photo turns over a BOUNDED working set

When a photo turn carries a successful vision analysis (`has_local_photo_context`
true), do **not** route it through the full megaprompt. Instead synthesize the
reply from a small, non-contradictory working set:

```
voice card  +  photo-faithful instruction  +  [E1] = the photo analysis
                                            +  user = the caption
```

No broken-systems block, no "screen perception disabled" line, no ambient/system
megaprompt. The brain answers from exactly what it saw. This is the architectural
fix the memory prescribes (the same shape proven by ablation for recall).

## Reuse, do not duplicate

`core/routing/focused_cognition.py` already has the machinery:
- `WorkingSet`, `EvidenceItem`, `FocusedResult` dataclasses.
- `_voice_card(surface)` → `_VOICE_CARD_TEXT` (scrubbed voice).
- `build_honest_empty_reply(...)` — **the exact template**: builds a one-fact
  `WorkingSet`, a small system prompt, calls `chat_fn`, deterministic honest
  fallback on empty/raise.
- `record_focused_cognition_run(...)` telemetry.

## Components

### 1. `synthesize_photo_turn(...)` in `focused_cognition.py` (new)
Mirrors `build_honest_empty_reply`. Signature:
```python
def synthesize_photo_turn(
    *, analysis_text: str, caption: str, surface: str,
    chat_fn=None, model=None,
) -> FocusedResult
```
- Builds one `EvidenceItem(local_label="E1", source_type="photo_vision",
  text=analysis_text)` + a `WorkingSet`.
- System prompt = `_voice_card(surface)` + `_PHOTO_VISION_INSTRUCTION` +
  `=== WHAT MAEZ SAW IN THE PHOTO (cite [E1]) ===\n{analysis_text}`.
- `_PHOTO_VISION_INSTRUCTION` (new constant): first-party framing — *you looked
  at this with your own local vision; never say you can't see it / vision is
  offline / it's blank; answer the caption from what you saw; if the caption asks
  something not shown, say what you see and what's missing.*
- `chat_fn` defaults to the brain via `BrainPurpose.OWNER_REPLY`; `model` defaults
  to `PRIMARY_MODEL`.
- **Deterministic honest fallback** if `chat_fn` returns empty or raises: surface
  the analysis directly (`"Here's what I saw in the photo: …"`) — never fabricate,
  never "can't see".
- Add `"photo_vision"` → `"first-party local vision"` to `_AUTHORITY_LABEL`.

### 2. `_analyze_photo_event` (telegram_adapter) — stash clean evidence
Already builds `event.channel_prompt` (the injection) for the legacy path. Also
store the raw joined analyses (`event.photo_analysis_text`) so the focused path
gets clean evidence without re-parsing the injection. Set it only when at least
one analysis is present.

### 3. `maez_adapter` — route photo turns to the focused path
In `MaezMessageHandler.handle_message`, where `has_local_photo_context` is already
computed (and `2bdd191` already skips the brain-loop planning pass): when
`has_local_photo_context` is true, synthesize via `synthesize_photo_turn(
analysis_text=<event.photo_analysis_text or stripped channel_prompt>, caption=text,
surface=SURFACE_NAME)` and use that reply — **bypassing `daemon.handle_message`**.
- **Gate:** `MAEZ_PHOTO_FOCUSED_SYNTH` (default `"1"` on; set `"0"` to fall back).
- **Safe fallback:** if focused synth raises or yields empty, fall through to the
  existing `daemon.handle_message` path (no regression, honest).
- Telemetry: `record_focused_cognition_run(...)` tagged purpose `photo_synthesis`.

## Egress / provenance (unchanged, must stay intact)
- The photo analysis stays local (`owner_message_context`); raw image bytes never
  leave home (existing `vision_tools` gates untouched).
- The synthesized reply is Maez-authored text and goes out the existing send path,
  classified `maez_authored_owner_third_party_transport` like any reply. No new
  egress surface.

## Tests (TDD)
1. `synthesize_photo_turn` builds a one-item working set (analysis=E1, caption=question).
2. With a mock `chat_fn`, returns the brain reply; reply is grounded in the analysis.
3. The focused **system prompt excludes** megaprompt/broken-systems content
   (`"cannot see"`, `"screen perception"`, `"broken"` absent) — the core point.
4. Deterministic honest fallback when `chat_fn` raises/empty; never "can't see".
5. `_analyze_photo_event` sets `event.photo_analysis_text` from the analyses.
6. `maez_adapter` routes `has_local_photo_context` → `synthesize_photo_turn`,
   and does **not** call `daemon.handle_message` (mutation-proof).
7. `MAEZ_PHOTO_FOCUSED_SYNTH=0` → falls back to `handle_message`.
8. Focused-synth failure → falls back to `handle_message` (no regression).
9. Egress/provenance suites stay green (reply via send path; analysis local).

## Predicted effect (for the commit)
After restart, a Telegram photo captioned "Check this" is answered from the local
vision analysis in Maez's voice — describing what's in the photo — and never says
the vision pipeline is offline / it can't see / the photo is blank. Non-photo
turns are unchanged (full megaprompt path). Latency for photo turns drops (small
prompt vs ~megaprompt).
