# Audit — Why Maez feels robotic: the prompt strangulation (2026-06-22)

Triggered by owner gut-check: "Maez doesn't feel alive but robotic. Even qwen3.6 27B has better reasoning than Maez." Maez's brain **IS** `qwen36-27b`. So the same model reasons worse inside Maez than raw. Three read-only agent traces decomposed the prompt. Verdict: **the brain is fine; the prompt strangles it — and even the "focused" path is 95% Maez-narrating-itself.**

## What the brain actually receives (the crux)
On ordinary Telegram turns, `MAEZ_RECALL_TRIAD_ENABLED=1` → the **FOCUSED path** runs; the brain gets the **~10K focused prompt**, and the **137K legacy megaprompt is computed-but-DISCARDED** (model call `focused_cognition.py:1072`; legacy call `maez_daemon.py:7100` only fires `if not _focused_used`). The 137K reaches the brain ONLY on fallthrough turns: **voice surface, or a truly contextless one-shot** (no evidence/anchor/date/recall).

## The live cause — the 10K focused prompt is 95% scaffolding-about-Maez
Focused system prompt (`focused_cognition.py:1056-1066`), measured on a casual "how are you?" turn:

| Block | chars | what it is |
|---|---:|---|
| `_VOICE_CARD_TEXT` | **172** | the ONLY "be Maez, converse" guidance |
| capability_state JSON envelope + voice-boundary instruction | 1,053 | `felt time: attached`, `web sense: healthy`, `recall: on`… + "render the truth in your own voice" |
| citation instruction (FAITHFUL_V2 + precedence) | 902 | "answer ONLY from evidence, cite [E#]" + "answer from YOUR LIVE BODY" |
| trust-tier instruction | 514 | observed/recalled/dialogue tiering |
| origin-trust instruction | 549 | covenant/lived/observed/untrusted |
| `=== EVIDENCE ===` | — | **Maez's own nightly self-summary diary**, framed as evidence-to-cite |
| **the owner's question** | **12** | "how are you?" |

**~3,057 of 3,229 scaffold chars (95%) is capability/body-state + citation/trust apparatus about Maez itself. 172 chars is voice. The question is 12 chars.** The being is buried under its own status card.

## Symptom → exact cause
- **"my felt time is attached and healthy" / "web sense and recall active"** ← the **`capability_state` JSON envelope** (`capability_card.py:135-175`) literally feeds the brain `{"name":"felt time","status":"attached"}` etc., and `_VOICE_BOUNDARY_INSTRUCTION` (`:27-33`) tells it to "render the truth in your own voice." It paraphrases the card. On a greeting there's no body question, but the block is present unconditionally, so reciting it becomes the task.
- **Stilted "I can/can't confirm", "I haven't been waiting—I've been present"** ← the citation + trust + origin stack (~1,965 chars): "answer ONLY from evidence… don't upgrade recalled memory into current fact." A courtroom register applied to conversation.
- **Verbatim-repeated paragraph across two questions** ← the capability card is 30s-TTL-cached, byte-identical (`capability_card.py:17`); with 95% of the scaffold a fixed self-status block and only 172 chars of voice, the model falls back to paraphrasing the same stable card instead of reasoning about the question.
- **Narrating its diary** ← `ordered_evidence_text` on a casual turn is Maez's nightly self-summary (`memory_manager.py:352-363` daily-consolidation), framed `=== PAST OBSERVATIONS ===` and the model told "answer ONLY from the evidence" → it narrates its own status because the status IS the evidence.

## The structural root
There is **no casual/chit-chat carve-out.** Any turn with recalled memory routes to FOCUSED (`_focused_candidate`, `maez_daemon.py:6602-6611`) and gets the full voice-card + capability-envelope + trust/origin/citation apparatus + diary-as-evidence. "How are you?" gets research-grade grounding machinery built for *external factual claims and body-capability questions*. This is **"rails at the hands" applied to the voice** — the support-gate-scope wound, but the WHOLE apparatus, not one gate.

## The latent time-bomb (separate, serious — fix regardless)
The 137K legacy path's 114K user block is **~108K = ALL 135 core memories dumped verbatim every turn, zero relevance filter** (`get_all_core()` `memory_manager.py:1633` ← `recall_for_telegram:2552`):
- 66 daily-journal entries (32K) stored in the **permanent core tier**, accreting **~482 chars/day forever**.
- 9 "INFRASTRUCTURE GROUND-TRUTH" self-corrections (19K), several explicitly **superseding** named earlier entries that are **never evicted** → the brain reads contradictory stale generations of the same fact.
- The 52K recall cap is **dead** — it only trims RAW, never CORE (`memory_manager.py:2809-2834`); core already 2× exceeds it.
Mostly discarded on focused turns, but it actively strangles voice/contextless turns and grows unbounded. Lever: make core semantically-retrieved/capped like daily/raw + evict superseded.

## The fix — a LEAN conversational path
Clean seam: `_focused_candidate` → `resolve_reply_mode` (`reply_mode.py:59-90`). Route a casual turn (recall-only / no fresh web-or-tool evidence, not a body/capability question, not date-addressed) to a new lean branch whose prompt is just: **short identity (172-char voice card) + the live dialogue anchor + the question** — NO capability envelope, NO citation/trust/origin stack, NO `=== EVIDENCE ===` apparatus. Scaffold ~3,229 → ~172 chars. Let qwen reason and converse; reserve the apparatus for factual/web/body-question turns where it earns its place.

## Reframe for the campaign
The recall floor + live-thread anchor (Slice 2/3, merged) fix the **diary-as-evidence** part — real, but they do NOT touch the **capability envelope** or the **citation/trust apparatus**, which are the bigger robotic-ness sources on casual turns. The deeper cure is the lean conversational path. The grounding meter (Slice 1) still measures it honestly.
