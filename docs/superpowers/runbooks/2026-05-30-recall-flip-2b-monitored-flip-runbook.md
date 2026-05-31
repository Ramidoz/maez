# Recall-Flip 2b — Monitored Default-On Flip Runbook (owner-run)

> 2026-05-30. The **real-life trial**. Owner-run procedure that consumes the **2a proof packet**
> (correctness/safety), the **1b shadow `rescuable_reach_rate`** (the prior/opportunity), and the
> **live soak** (the benefit ground-truth) and makes the Go/No-Go. Per A6 decoupling: **2a does not
> decide; this runbook decides.** Frozen pre-registration: [flip spec](../specs/2026-05-30-recall-triad-monitored-default-on-flip-design.md)
> (gates, soak floor, disposition, amendments A4/A5/A6 @ 209682f).
>
> **Authority:** the flip touches `config/.env` and changes live cognition. It is **owner-run by Rohit
> only**. Claude witnesses and records; Claude does **not** flip. Codex verifies this runbook is
> executable before it is run (commands exist, metrics emit, thresholds pinned, kill-switch real).
>
> Operational facts (Codex verified in 2a executability pass): daemon unit = `maez.service` controlled via
> `systemctl --user`; logs =
> `logs/maez.log*` (RotatingFileHandler, 50MB × 10; use `grep -a[h]` because historical log files can
> contain NUL bytes); flags load from `config/.env`; posture log line = `recall_stack mode=…`.

## Step 0 — Pre-flip preconditions (ALL must pass; any fail blocks the flip)
1. **2a proof packet = PASS.** Run the offline harness at the flip commit; every correctness/safety probe
   green at k≥3 consistency, including the **both-shaped re-witness** (it was green at graduation @ 80b1674
   but 1a/1b touched the daemon since — re-confirm at the flip commit). If any probe is RED, **stop and
   root-cause**; do not flip.
2. **Shadow pre-flip gate (1b).** Over the shadow window, **zero `false_absence_candidate`** on real
   traffic, or each one root-caused. Report **coverage** explicitly — `attempted / skipped / completed`
   and *why skipped* — and **name the async-residual sampling gap**: lost-on-crash shadows under-sample
   the heaviest turns, so *absence of bad rows is not proof*; read the false-absence count only at
   coverage ≥ 80% (the coverage reading-rule). Commands:
   ```
   grep -ah "shadow_outcome" logs/maez.log* | grep "false_absence_candidate=true"   # must be empty/root-caused
   grep -ah "shadow_outcome" logs/maez.log* | wc -l                                 # completed
   grep -ah "shadow_skipped" logs/maez.log* | sort | uniq -c                        # skipped, by reason
   grep -ah "recall_outcome" logs/maez.log* | grep "shadow_pair_id=" | grep -v "shadow_pair_id=na" | wc -l
                                                                                 # attempted denominator
   ```
   Current log retention is about 500MB by configuration; before the actual soak, confirm the
   `logs/maez.log*` mtime range covers the entire shadow window. If not, land the content-free sink first.
3. **Live legacy baseline.** With the triad **off**, capture p95 latency on recall turns AND ordinary
   turns separately over a representative window; **freeze** `K` (default 1.5) and `ceiling_ms = round(
   live_legacy_recall_p95 × K)` and record them **before** the flip (latency gate uses the LIVE baseline,
   not the sandbox — A6). Record `recall_outcome` class distribution as the legacy benefit baseline.
   ```
   grep -ah "recall_outcome" logs/maez.log* | grep "mode=legacy"   # baseline distribution + latency_ms
   ```
4. **Pre-register the verdict rule.** Write down, before the flip, the exact **"better overall"
   aggregation** (e.g. "≥2/3 of paired live dated turns judged 'better' AND zero judged 'worse'") and the
   **rescued breadth floor** (rescued evidence across **≥N distinct dated turns**, not one anecdote). This
   is committed to the decision artifact pre-flip (anti-HARKing).

## Step 1 — The flip (owner-authorized)
```
# Rohit only. Set the single bundle flag in the launch env without duplicating keys.
grep -q '^MAEZ_RECALL_TRIAD_ENABLED=' config/.env \
  && sed -i 's/^MAEZ_RECALL_TRIAD_ENABLED=.*/MAEZ_RECALL_TRIAD_ENABLED=1/' config/.env \
  || printf '\nMAEZ_RECALL_TRIAD_ENABLED=1\n' >> config/.env
systemctl --user restart maez.service
# Confirm posture:
grep -ah "recall_stack mode=" logs/maez.log* | tail -1   # MUST show mode=recall_triad reason=bundle_enabled
```
If the posture log does not show `mode=recall_triad`, **revert immediately** (Step 4 kill-switch) and
root-cause — do not soak on an unconfirmed flip.

## Step 2 — The soak (live, bounded)
Run **24–48h of ordinary use AND the stratified floor met, whichever is longer** (a quiet window can't
pass on thin evidence). Stratified floor (frozen): ≥5 dated-hit, ≥3 dated-miss, ≥3 continuity, ≥1 confirmed
honest-empty, ≥1 both-shaped, ≥10 ordinary non-recall turns.
- **Light-ABBA off-block + kill-switch drill** mid-soak: flip OFF for one block, confirm clean fallback
  to legacy on a live continuity turn, confirm no orphaned `focused_cognition_runs`, confirm the
  self-status branch reports `off-by-config`; then back ON. This controls secular trend AND proves the
  kill-switch under live load.
  ```
  # OFF block:
  sed -i 's/^MAEZ_RECALL_TRIAD_ENABLED=.*/MAEZ_RECALL_TRIAD_ENABLED=0/' config/.env
  systemctl --user restart maez.service
  grep -ah "recall_stack mode=" logs/maez.log* | tail -1   # mode=legacy
  # (ask Maez "is your dated recall reachable?" → expect the off-by-config self-status reply)
  # Orphan check (DB verified in 2a executability pass; created_at is UNIX seconds):
  OFF_START_EPOCH=$(date +%s)
  sqlite3 memory/routing_observation.db \
    "select count(*) from focused_cognition_runs where created_at >= ${OFF_START_EPOCH};"
  # back ON:
  sed -i 's/^MAEZ_RECALL_TRIAD_ENABLED=.*/MAEZ_RECALL_TRIAD_ENABLED=1/' config/.env
  systemctl --user restart maez.service
  ```

## Step 3 — Live blind verdict (the benefit ground-truth — A6)
On **live soak turns** (not the sandbox battery): present the legacy and triad answers for the same
dated/continuity turns in **randomized order, provenance hidden**; Rohit records better/same/worse against
the **pre-registered rule** (Step 0.4); de-blind only after all verdicts logged; **intra-rater re-score**
a random subset blind to check self-consistency. The answer text lives in the **content-bearing,
quarantined answer-sheet artifact** (named, *outside* the content-free telemetry tree, dispositioned after
the verdict) — never folded into the telemetry stream.

## Step 4 — Go / No-Go (this runbook decides; consumes packet + shadow + live)
**Hard gates (any fail → kill-switch, No-Go):**
1. **Zero false-absence** on live soak (`is_false_absence` over `recall_outcome`).
2. **Latency:** triad p95 ≤ legacy-baseline p95 × K AND ≤ `ceiling_ms`, on recall AND ordinary turns (live).
3. **No non-recall regression** (blast-radius): ordinary turns show no `outcome_class`/latency regression
   vs baseline. (Over-consultation is **observational** in the soak — no emitting field yet, A6.)
4. **No covenant regression** (fabrication, gender, refusal-warmth).
5. **Type-rule intact** (from the 2a packet: >14d memory cited as context, never evidence).

**Benefit gate (A5):** rescued-turn counter > 0 across **≥N distinct dated turns** (rescued =
legacy∈{declined_*/answered_unverifiable} → triad **live answered_grounded**; declined_absence excluded;
**answered-ungrounded = FAIL**) AND blind preference = "better overall" per the pre-registered rule AND
caution not inflated (declined_* rise offset by answered_unverifiable fall) AND rescued turns clear the
absolute `C_floor` coverage.

**Disposition:** hard gates pass + benefit = better → **keep on**. Hard gates pass + benefit = "same" →
**default REVERT** (Step 4 kill-switch) unless Rohit's **explicit recorded override + reason + dated
90-day re-look**. Any hard-gate fail → revert + root-cause.

**Kill-switch (the revert):**
```
sed -i 's/^MAEZ_RECALL_TRIAD_ENABLED=.*/MAEZ_RECALL_TRIAD_ENABLED=0/' config/.env  # or delete the line
systemctl --user restart maez.service
grep -ah "recall_stack mode=" logs/maez.log* | tail -1   # MUST show mode=legacy
```

## Step 5 — Decision artifact (Visionary audit fields)
Record a durable, content-free **decision artifact**: the frozen-pre-reg **commit SHA** evaluated against
(209682f); **per-gate computed-number vs frozen-threshold** (e.g. "p95 312ms ≤ ceiling 450ms"); the
**disposition** (keep/revert/override) + **who decided (Rohit) + when + why** + the **90-day re-look date**
if kept-on-override; the **de-blind order/timestamps** proving verdicts preceded the reveal; and
**environment provenance** (boot_id, code commit SHA, brain/model id at flip time — Maez's brain is
swappable; a flip proof must record which brain was live).

## Step 6 — Shadow teardown (1b sunset) + forgotten-teardown guard
After the disposition is recorded:
```
sed -i '/^MAEZ_RECALL_SHADOW_ENABLED=/d' config/.env     # shadow off
OFF=$(stat -c%s logs/maez.log 2>/dev/null || echo 0)
systemctl --user restart maez.service
tail -c +$((OFF+1)) logs/maez.log | grep -ac "shadow_outcome"  # after restart: confirm 0 new shadow rows
```
Record the teardown verification beside the disposition; **schedule code removal**. **Forgotten-teardown
guard:** a check (CI or log-grep) that flags any `shadow_outcome` row appearing **after** the recorded
disposition date — so the rehearsal can't silently outlive its purpose.

## Notes
- The over-consultation gate clause is observational (no field) until a signal is added — named, not silent.
- The 2a executability pass resolved the concrete DB path/query for focused runs and the log command shape.
  The only live-time check left is whether the current rotated log mtime range covers the chosen shadow
  window; if not, land the content-free sink before the soak.
