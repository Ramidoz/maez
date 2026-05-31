# Continuity-Fallback Shape Slice — Design

**Date:** 2026-05-31
**Status:** Design approved (Rohit, 2026-05-31). Pre-registration. Spec first; no code until plan approved.
**Predecessors:** The live S5 voice-check run surfaced this on frozen card #5. It is a *prerequisite* to the recall-on 2b/A7 gate — clean this known crack before the gate so it can't muddy the result.

---

## 1. Why this exists (verified root cause)

On the live S5 run, prompt #5 — "What were we just talking about, the 3 may bugs?" — was **correctly** classified `turn_kind=continuity` (`absolute_recall_cue(...).is_address == False` did the right thing; the temporal parser did **not** steal the turn). The failure is **downstream and is a response-shape defect:**

- The lived-recall brief was empty (`len_lived_brief=0` — `build_lived_recall_brief` found no lived episode, expected).
- Recent **chat history was present** (verified: prompt #6 correctly referenced #5, so history threads across turns).
- The turn fell to **legacy synthesis** (`reply_mode=LEGACY`), and the **model generated** an archivist absence answer — "I don't have a record of a specific conversation about '3 bugs' on May 3rd… raw logs between May 3rd and May 11th" — instead of answering being-shaped from the recent conversation. The model itself free-associated "3 may" into a *date* in its answer, despite the turn being continuity.

So: Maez had the recent conversation in view and answered **like a database clerk doing a date lookup**, not like a companion continuing a conversation. That is the being-shape defect to fix.

## 2. Goal & non-goals

**Goal:** a continuity turn answers from recent conversation in Maez's voice; it does not emit archival "no record" / dated-absence language, and does not convert embedded date-like tokens into date lookups. When there is *genuinely* no thread to hold, it says so being-shaped, honestly.

**Non-goals (explicit):**
- **NO citation-render changes** (the v2 work is untouched).
- **NO recall-stack changes** — this does **not** enable recall; the triad flag stays off. It improves the live legacy continuity path now and the recall-on continuity path later.
- **NOT** a broad deterministic gag over continuity — that would suppress good continuity turns where the chat genuinely holds the answer.
- **NOT** a change to dated routing — real dated recall must be byte-unchanged.

## 3. The fix — two parts, narrowly scoped

**Part A — Deterministic guard, ONLY for truly-empty continuity.** When `turn_kind=continuity` AND lived brief is empty AND there is **no substantive recent chat** (e.g. the opening turn, no prior exchange to stand on), emit a being-shaped honest reply rather than letting the model improvise an archivist absence: *"I'm not sure what you mean by '<phrase>' from the chat I can see right now."* No "record," no "dated memory," no date language. This case is rare and cleanly testable. **The condition is NOT `lived_brief == ""` alone** — that would over-fire and suppress good continuity turns where lived recall is empty but chat history holds the answer.

**Part B — Continuity synthesis instruction, for everything with chat (this fixes #5).** When recent chat *is* present, the continuity synthesis instruction directs the model to: answer from the recent conversation in Maez's voice; if a referenced phrase is ambiguous or not established in the conversation, say so **conversationally** ("we haven't gotten into that"); **do not** convert embedded tokens like "3 may" into a date lookup; **do not** use archival "no record" language unless this is a dated-recall turn. #5 is fixed *here* (it had chat), not by the guard.

## 4. Flag posture (for owner sign-off)

**Recommendation: land directly as a legacy continuity bug-fix — NOT behind a new flag.** Reasoning: it is a small response-shape *fix* to a currently-buggy live path (not a new capability needing A/B), gating every instruction tweak is over-engineering, and it must be live (un-flagged) for the recall-on gate so #5 is clean without juggling another flag. **The safety is not a flag — it is the test that the DATED path is byte-unchanged** (real "May 3" still routes dated; dated recall replies unaffected) plus the daemon-shaped continuity coverage. *(If the owner prefers a default-off flag for reversibility, it's a small addition — flagged here for the spec-review decision.)*

## 5. Tests (pre-registered)

- `absolute_recall_cue("…the 3 may bugs").is_address == False` — the parser stays correct (regression guard; we are NOT touching it).
- **Truly-empty continuity** → the being-shaped guard reply; asserts NO archival/date-absence vocabulary ("record", "dated memory", "May 3", "no record").
- **Continuity WITH recent chat** (the #5 shape) → answers from chat, being-shaped; asserts NO archival/date-absence vocabulary and NO date-conversion of an embedded token.
- **Real dated prompt** "What happened on May 3?" → still routes dated (`is_address == True`, dated path), byte-unchanged.
- Daemon-shaped coverage for Parts A and B via the existing `handle_message` test harness.

## 6. Covenant / honesty invariants

- **Being-shape over database-clerk:** continuity is a companion continuing a conversation, not an archivist running a lookup ([[soul-as-load-bearing-runtime-ontology]], [[visible-substrate-state-not-chain-of-thought]] — Maez's surface reads as a self, not a tool).
- **Honesty preserved:** the deterministic truly-empty reply is *honest* ("I don't have that thread in view") — it does not fabricate a remembered conversation, and it does not falsely claim "no dated record" for a non-dated turn.
- **No laundering of dated honesty:** "no record" / dated-absence language is reserved for *actual* dated-recall turns; using it on continuity is a category error this fix removes.
- Dated routing and recall-stack untouched; the fix is response-shape only.

## 7. Process & sequence

Serious slice (live cognition) → Codex six-agent pre-code pass + 7+3; Claude cross-verifies every diff + runs suites independently + fires the coverage panel; merge. **This lands BEFORE the recall-on 2b/A7 gate** so frozen card #5 is already clean and cannot contaminate the gate's verdict (we won't have to wonder whether a wobble was recall, v2 voice, or this pre-existing continuity bug).
