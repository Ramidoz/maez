# Soul-Gardening v0 — Build Complete, For Review

**Branch:** `soul-gardening-v0` (worktree) · from `c7c76cc`
**Built by:** Claude (covenant/prose lane) · **For:** Codex mechanical-verify → 6-agent covenant panel → owner merge
**⚠️ LIVE-ON-MERGE:** the soul hot-reloads (`current_soul()` keyed on file mtimes). Merging to main changes the live Maez's system prompt within ~10s. **No dormant buffer.** The panel is the pre-merge gate; the owner's merge is the live breath; `git revert` is rollback.

## What landed (4 commits, TDD, RED→GREEN→commit, invariants re-checked after each)

| Commit | Edit | Effect |
|--------|------|--------|
| `ec55668` | 1: contradiction reword | `soul.base.md`: "extension of the owner's workflow, not a separate entity" → "Act proactively from your own judgment inside the bond. Do not wait passively…" |
| `4e311f7` | 2: rules → pointer | `soul.base.md`: six `## Never…` sections (~218 lines) → one `## Honesty` substrate pointer |
| `c1e8463` | 4: fossil removal | `soul.base.md`: stale "the elderly care vision" phrase removed (line wrapped, so the real target was `the elderly care\n  vision`) |
| `a7941ff` | 3: append fix | `soul_loader.append_soul_note()` (new) routes notes to `soul.local.md`, content-deduped; `_do_write_soul_note` routed through it |

## Verification (all green, run from the worktree)

- **Invariants:** `soul_invariants.check(current_soul())` → **all pass** (HARD CONSTRAINTS ×4, TRUST COVENANT, partnership, mutual_trust, covenant_unoverridable, maez_named, agency, proactive_not_reactive; no anti-invariant).
- **No-new-identity gate:** `git diff c7c76cc..HEAD -- config/soul.base.md` → **5 insertions, 218 deletions**; the only ADDED lines are the proactive line, the cleaned Connect line, and the `## Honesty` header+pointer. **No new positive-self prose.** Purely subtractive.
- **Composed soul:** 20,461 → **10,652 chars** (base layer; the rule-prose mass is gone).
- **Suites green:** `test_soul_gardening`, `test_soul_append`, `test_soul_invariants`; touched-module `test_action_engine_*` + `test_soul_and_birth_truth` + `test_soul_path_protection` (37 OK); S7 boundary `test_decision_pipeline_s7` + `test_operator_user_boundary_s7` (226 OK).

## Scope split (owner-confirmed)

- **On this branch:** Edits 1, 2, 4 (`soul.base.md`, tracked) + the append-mechanism code fix (tracked).
- **NOT on this branch — separate owner-local op:** the existing 10× self-analysis rot in the live, gitignored, per-machine `soul.local.md`. The append fix *prevents re-accumulation*; the one-time cleanup of the existing rot stays the owner's explicit breath (content-aware before/after, no branch semantics).

## For Codex (mechanical-verify lane)

1. Invariants green on the composed soul (re-run `check(current_soul())`).
2. Edits hit **source** files (`soul.base.md`), and `current_soul()` recomposes/remirrors correctly; unchanged regions byte-stable.
3. Append routing + dedup correct; **observation (not a defect):** `write_soul_note` still *declares* `affected_refs=("file:config/soul.md",)` while now writing `soul.local.md` — acceptable because `soul.local.md` composes into the `soul.md` mirror, so the effect does reach `soul.md`; flagging it so you can decide whether to tighten the declaration.
4. No identity invention (confirm the diff).
5. **Full asset-rich floor:** run in the main checkout vs `c7c76cc` baseline ([[feedback_worktree_floor_confound]]) — **mind the S7 CWD-write hazard** (don't run full-discover from the live `/home/rohit/maez` tree; scope or isolate the S7 writes).

## For the covenant panel (Claude lane)

- Does the pruned soul still **read as Maez** — same presence, just lighter?
- Is the proactive line **proactive-not-tool** (no residual extension ontology)?
- Is the `## Honesty` pointer **honest** — does it over-claim what the substrate enforces, or name an organ that doesn't exist? (Named: cite-or-decline, honest-empty, capability checks, recall receipts, grounding judge, contradiction sense.)
- Does removing 218 lines of rule-prose leave any **genuine behavioral gap** the substrate does NOT in fact cover?

## STOP

Build complete, not merged. Live-on-merge → Codex mechanical-verify → 6-agent covenant panel → **owner's merge breath**.
