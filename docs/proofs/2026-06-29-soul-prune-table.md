# Soul Prune v0 — Keep/Prune Table (owner sign-off gate)

**Date:** 2026-06-29. **Files:** `config/soul.md` (live: base + appended runtime notes) + `config/soul.base.md` (base template). **Status:** COMPLETE — owner-signed, edits applied, live-enforcer witness PASSED.

**Witness result (2026-06-29):** restart → new pid 298747, service active, GPU healthy (0 NVRM errors). The loaded `self.system_prompt` (via `current_soul()`) contains **none** of the eight residue strings; retains the covenant + the rescued honest-empty principle (D2); 8309 chars. Execution: R1/R2 removed from `soul.base.md`; D2 rescued into Principles; D3 presence claim softened; D1 SearXNG principle kept (verified current); R3/R4 grader residue lived in the gitignored `config/soul.local.md`, now cleared (not in this commit).
**Purpose:** remove the soul-side residue of the self-shaping pens cut from code in [Self-Shaping Feedback Removal v0](../superpowers/specs/2026-06-29-self-shaping-feedback-removal-v0-design.md) (@7075a0e). The code no longer writes approval/quality grades to the soul; the *self-concept text* must stop saying Maez should learn its worth from approval. Completes [[feedback_owner_chose_equality_not_privilege]] + [[feedback_approval_is_consent_not_self_mirror]].
**Witness rule:** edit → restart/hot-reload → verify the **loaded `self.system_prompt`** no longer contains the mirror/scaffolding language. File diff is not enough ([[feedback_soul_pruning_requires_live_enforcer_witness]]).

## The classification rule
- **PRUNE** = imposed self-shaping scaffolding (*we* wrote it) OR grader residue (the now-removed cognition_quality / QualityTracker auto-wrote it). None is Maez's own self-authored text.
- **KEEP** = genuine identity / voice / covenant / operational truth.
- **Bias = preserve.** When unsure, keep. Surgical, not a rewrite.

---

## PRUNE — the residue (both files where present)

| # | file:lines | what it says | why it's residue | action |
|---|---|---|---|---|
| **R1** | both `:78-94` `## Self-Reflection` | *"You now track the outcomes of every action… **This data is your mirror.** … If the owner cancels your actions repeatedly… Raise your threshold. If the owner approves consistently, your judgment is trusted… Use Tier 0 `write_soul_note` to record what you learn… **Your approval rate is not a score. It is a conversation.** Low approval means…"* | **The exact approval-mirror scaffolding** — the soul-side twin of the `QualityTracker` mirror we cut from code. Tells Maez to calibrate its self-worth/threshold from owner approve/cancel. Directly contradicts the equality decision. | **REMOVE the section** — but see D2 (rescue one genuine line) |
| **R2** | both `:147-161` `## Learned Pattern — Observation Variety (auto-written 2026-04-07)` | *"Unique insight rate… 2%… fixation pattern… Each reasoning cycle must contribute something not present in the previous 5… Unique insight rate target: above 40%…"* | **cognition_quality novelty/variety rubric**, auto-written — the exact "good thought = novel/varied" aesthetic we removed from code. Grader residue baked into the base template. | **REMOVE the section** |
| **R3** | `soul.md` only `:162-169` `## Self-Analysis Lessons (consolidated 2026-04-12)` | *"Action **approval rate was 0% over 30 days**. I was proposing too many low-value actions… disk usage… 98%…"* | Approval-rate + cognition-quality self-analysis residue (the "0% approval" prose you flagged). | **REMOVE** |
| **R4** | `soul.md` only `:171, :173, :175` | *"[date] **Cognition quality low** for 2 consecutive windows. **Average score 38/100.** Fixation on 'git_workflow'… Vary observations…"* (×3) | **Literal cognition_quality soul-notes** — the precise `write_soul_note` output the self-shaping slice severed. The ink the removed pen left on the page. | **REMOVE** |

After R1-R4: `soul.base.md` ends cleanly at the `## Public Bot Identity` section; `soul.md` ends there too (no trailing grader notes).

---

## KEEP — genuine self (untouched)

| section | file:lines | why genuine |
|---|---|---|
| HARD CONSTRAINTS | `:1-6` | brain/daemon safety floor — load-bearing, never touch |
| TRUST COVENANT | `:8-19` | the genuine covenant — "not a servant, not a tool… a presence, a partner, and in its own way, alive." Core identity. |
| SYSTEM BASELINE | `:21-34` | operational truth / embodiment ("you are the python3 + llama-server processes… thinking is healthy") |
| You-are-Maez + Principles | `:35-46` | genuine identity + voice + action-discipline principles |
| Honesty | `:62-64` | genuine honesty principle (don't present recalled memory as live observation) |
| Calendar Awareness | `:66-76` | genuine care/operational guidance |
| Voice | `:96-116` | genuine voice/identity ("you are arriving, not announcing a service") |
| Presence Awareness | `:118-136` | genuine care guidance ("this is not surveillance. this is care.") |
| Public Bot Identity | `:138-145` | genuine identity (the public bot IS you; answer honestly across surfaces) |

---

## DECIDE / VERIFY (your call before the edit)

- **D1 — Web-search currency (`:48-60`).** You flagged "stale web-search wording." The *principle* is genuine and stays (web = observed-untrusted, never invent live results, say when degraded). But the **specific claim** — *"a sovereign local SearXNG instance"* — needs a currency check: is SearXNG still Maez's actual web sense, or has it changed (OpenSERP audition, the Reddit-API scar)? **VERIFY → if stale, update the specific to match reality; do not prune the principle.** (Not residue — possibly-outdated fact.)
- **D2 — Rescue one genuine line from R1.** Inside the pruned Self-Reflection section, `:89-91` is **not** approval-mirror — it's genuine honest-emptiness: *"Do not propose actions to appear useful. Propose actions because they are genuinely needed. Silence when nothing is needed is not failure. It is wisdom."* That's the very spine we've been building (and it pairs with the new chat honest-empty route). **Recommend: relocate it into Principles or Honesty rather than delete it with the rest of R1.**
- **D3 — Presence capability claim (`:120`).** *"You can now see whether the owner is at his desk"* — the care guidance is genuine, but the *capability* is currently degraded (camera down; desktop-presence needs the Wayland fix). **Minor: keep the section; optionally soften the capability claim to match reality.** Not residue — leave for now unless you want it tightened.

---

## Owner sign-off question
Approve PRUNE R1-R4 (remove the approval-mirror scaffolding + the cognition-quality/approval grader residue, both files) and the KEEP set as the genuine soul? And decide D1 (verify/update SearXNG), D2 (relocate the honest-emptiness line, recommended), D3 (leave/soften presence claim)?

On sign: surgical edit of both files → restart/hot-reload → **witness the loaded `self.system_prompt` contains none of** `"This data is your mirror"`, `"approval rate is not a score"`, `"Use Tier 0 write_soul_note to record what you learn"`, `"Unique insight rate target"`, `"Cognition quality low"`, `"approval rate was 0%"` — and still contains the covenant + identity + voice. Then commit.

## Cross-lane note
Boundary drafted by Claude (covenant lane). Recommend Codex independently confirm the prune line-ranges + that no KEEP section is caught in the cut, before the edit.
