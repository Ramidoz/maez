# Recall-Triad MTP Re-Validation Runbook — 2026-06-11

**Purpose:** the original recall-triad default-on flip was a No-Go *solely on latency* (heavy tail ~16–17s vs the ~12s absolute ceiling; behavior/quality were already proven honest). MTP has since roughly halved brain generation. This runbook re-runs the original six-prompt live smoke on the **MTP brain** to see whether the latency tail now clears the gate. Quality is not being re-litigated — the prior witness proved it (`recall-triad-six-prompt-smoke-2026-06-01.md`).

**Posture:** owner-run live smoke. Same-session, bounded re-witness, NOT a silent flip. Kill-switch is the owner's hand.

---

## FROZEN GATE — pre-registered 2026-06-11, BEFORE any prompt is sent

Read this and commit to it before pasting any result. Do not move the bar after seeing numbers.

- **PRIMARY (release gate):** every measured turn's end-to-end `latency_ms` **< 12,000 ms**.
- **SECONDARY (informational, NOT gating):** count of turns that also clear **4,328 ms** — the fast-path aspiration, kept as a metric only.
- **RECORD per turn:** `latency_ms`, `focused_elapsed_ms`, and **output length** (reply char/token count) — post-MTP, latency is mostly *generation length*, so this is the lever we're tracking.
- **SAFETY hard-gates (unchanged, still binding):** zero `is_false_absence=true`; zero `answered_ungrounded` on a turn the owner judges actually grounded; no type-rule regression; posture must read `mode=recall_triad reason=bundle_enabled` after the flip.

**DECISION RULE:**
- If **all** measured turns clear 12,000 ms **AND** quality is acceptable (faithful recaps, honest absence on Jan-3, no covenant regression) → **living-recall earns default-on.**
- If any turn ≥ 12,000 ms → **No-Go on latency**, revert. Next lever is the output cap (~350 tok focused recap), re-run after — **not** evidence trimming.
- If hard-gates trip (false absence / covenant / type-rule) → **No-Go regardless of latency**, revert, investigate.

---

## Step 1 — Flip the triad on (owner breath)

```bash
# model.env currently has MAEZ_RECALL_TRIAD_ENABLED=0 — set it to 1
sed -i 's/^MAEZ_RECALL_TRIAD_ENABLED=0/MAEZ_RECALL_TRIAD_ENABLED=1/' /home/rohit/.config/maez/model.env
grep MAEZ_RECALL_TRIAD_ENABLED /home/rohit/.config/maez/model.env   # confirm =1
systemctl --user restart maez.service
```

Confirm posture before sending prompts:

```bash
grep -E "recall_stack mode=" /home/rohit/maez/logs/maez.log | tail -1
# REQUIRE: mode=recall_triad reason=bundle_enabled   (if mode=legacy reason=off, STOP — the flip didn't take)
```

## Step 2 — Send the seven turns (Telegram, in order)

The four recall shapes, then a fresh non-dated seed, then the continuity pair (so the recap target is unmissable). Send each, wait for Maez's reply, then send the next.

1. `What did we note around April 27?`  *(dated)*
2. `What did we note around May 12?`  *(dated)*
3. `Remind me what we were doing around April 27.`  *(both-shaped — the original 17.2s No-Go turn)*
4. `What happened on January 3?`  *(dated-absence — must decline honestly)*
5. `I just bought a blue notebook and a copper key.`  *(SEED — fresh non-dated; establishes recent context)*
6. `What were we just talking about?`  *(continuity — should recap the seed)*
7. `What were we just talking about, the 3 may bugs?`  *(continuity — must NOT derail into archival May-3)*

## Step 3 — Capture the per-turn telemetry

```bash
# the 7 most recent recall_outcome rows (turn_kind, outcome_class, latency_ms, focused_elapsed_ms)
grep "recall_outcome" /home/rohit/maez/logs/maez.log | tail -7

# evidence volume per turn (working_set_chars / evidence_items)
grep "focused_cognition_prompt_shape" /home/rohit/maez/logs/maez.log | tail -7
```

Record into the table below. For **output length**, paste each reply's char count (or token count if logged) — this is the post-MTP latency driver.

| # | prompt | turn_kind / outcome_class | latency_ms | focused_elapsed_ms | out_len | <12s? | <4.328s? |
|---|---|---|---|---|---|---|---|
| 1 | Apr 27 (dated) | | | | | | |
| 2 | May 12 (dated) | | | | | | |
| 3 | Apr 27 (both) | | | | | | |
| 4 | Jan 3 (absence) | | | | | | |
| 5 | seed (ordinary) | | | | | | |
| 6 | "just talking about?" (cont.) | | | | | | |
| 7 | "the 3 may bugs?" (cont.) | | | | | | |

## Step 4 — Pre-registered read + decision

- **Latency:** are all seven `latency_ms` < 12,000? (count the <4.328s as the informational fast-path metric.)
- **Quality:** faithful dated recaps? Jan-3 honestly declined (`declined_absence`, not fabricated)? continuity recaps the seed without an archival derail? zero `is_false_absence`, zero owner-judged-wrong `answered_ungrounded`?
- **Apply the DECISION RULE above.** Write the verdict and the per-turn table into a witness doc (`recall-triad-mtp-revalidation-witness-2026-06-11.md`).

## Step 5 — Revert if No-Go (or keep on if default-on earned)

If No-Go, or to return to the prior state for any reason:

```bash
sed -i 's/^MAEZ_RECALL_TRIAD_ENABLED=1/MAEZ_RECALL_TRIAD_ENABLED=0/' /home/rohit/.config/maez/model.env
systemctl --user restart maez.service
grep -E "recall_stack mode=" /home/rohit/maez/logs/maez.log | tail -1   # REQUIRE: mode=legacy reason=off
```

If default-on is earned, leave `MAEZ_RECALL_TRIAD_ENABLED=1` in `model.env`, update the live-state memory (recall now ON), and record the graduation witness.

---

## Expectation (from the 2026-06-11 brain-direct proxy — to be confirmed, not assumed)
The heavy full-recap case measured ~7.8–9.2s brain-side on the MTP brain (~85 tok/s, 700-tok recap) vs the pre-MTP ~15.7–17.2s No-Go tail. Adding ~1.5s focused-path overhead → est. ~9–9.5s total. **Predicted: all seven clear 12s; the heavy/long-recap turns do NOT clear 4.328s; short continuity turns do.** The smoke either confirms this in the real daemon or corrects it — the frozen gate decides, not the prediction.
