# Coherence-Assembly Campaign — Handoff & Switch-over Runbook

**Claude, autonomous campaign, 2026-06-13/14.** Everything below is on **branches**;
the live daemon stays on `main` and untouched **except** the one safety landing you
authorized live (S4). Nothing pushed. This doc is what you read on return to test,
review, and (when ready) switch over.

---

## 1. What the campaign delivered

One disease was diagnosed: **surface/reader divergence** — the same owner words
produced a different Maez depending on surface, because three inbound pipelines and
several flag/path/label conventions had drifted apart. Integration debt, not broken
organs. The campaign closed it, plus a handful of named consolidation debts and the
honesty of the face.

**Live already (you authorized merge+restart while present):**
- **S4 crisis-boundary fix** (`main` @`f2a56f9`). The clinical/suicide-crisis rail was
  silently dead on live Telegram for ~1 month (the Surface-V2 label `telegram_surface`
  was never added to the S4 allowlist; tests passed because they used a synthetic label).
  Now it fires. Witnessed live (daemon pid cycled, `guard_owner_text` matches on the live
  label). This is the most important single fix of the campaign.

**On branches, verified, awaiting your switch-over:**

`supporting-slices` (off main) — 5 consolidation slices, each flag/kill-switch-gated,
byte-identical when off:
| slice | closes | flag (default) |
|---|---|---|
| egress origin_downgrade | cloud chokepoint forwarded a block that should 403 (your prioritized slice-1) | `MAEZ_EGRESS_ORIGIN_DOWNGRADE_SHADOW` kill-switch (default **enforced**) |
| valence flag-gate | a live organ that couldn't be disabled | `MAEZ_VALENCE_LIVE_ENABLED` (default **on**) |
| honest boot | systemd reported `active` before the daemon was serving | `MAEZ_SYSTEMD_NOTIFY` + `Type=notify` (default on under systemd) |
| store path-sweep | bare-relative DB paths → CWD-shadow DBs | none (resolver, backward-compatible) |
| S7 door | ceremony pointer `127.0.0.1` vs WebAuthn binding `localhost` → Origin mismatch rejects the ceremony | none (pointer string + new `maez-web` unit) |

`inbound-core-v2` (off main) — the surface-merge + the honest face:
- **`daemon/inbound_core.py::run_inbound_turn`** — the ONE surface-agnostic inbound
  pipeline (S4 → residue/approval → D20 → intake → cards → proposal → search →
  brain-loop → handle_message). Telegram routes through it; cockpit routes through it.
- **Telegram** behind `MAEZ_INBOUND_CORE_V2` (default **off**) — proven byte-identical to
  today (an equivalence harness asserts the flag-on path produces an identical
  dependency call-trace to flag-off, across 6 input classes).
- **Cockpit `/message`** behind `MAEZ_COCKPIT_CORE` (default **off**) — when on, cockpit
  routes through the unified core: **its own S4 hole closes** (`cockpit` added to the S4
  allowlist), it is **kept out of M1** (the conservative covenant default — an
  unauthenticated localhost surface must not write durable selfhood), felt-time off.
- **Honest face** behind `MAEZ_COCKPIT_REAL_STATE` (default **off**) — the cockpit
  dashboard stopped **fabricating inner life**. It was rendering a hardcoded "mood", a
  frozen "uncertainty", and a "current thought" reconstructed by regex-scraping
  `maez.log`. All deleted. When on, it reads the daemon's **real in-memory state**
  (`/internal/cockpit/state`, true-by-construction) — cycle, cognition score/labels, the
  actual last utterance (now retained on the daemon), valence, recall, watchdog,
  clinical-boundary, voice-continuity, live flags. Nothing performed; if a signal has no
  real organ, it is **absent, not faked**.

`campaign-integration` (off main) — **the union of both branches**, merged cleanly (no
conflicts), full named-suite witness green together. **This is the single branch to merge
at switch-over.**

---

## 2. How it was built (the discipline, so you can trust it)

- Every slice built on an isolated branch, **adversarially verified by re-running its
  tests + reading its diff myself** — never accepted on an agent's self-report.
- A read-only verification pass ran *before* building and **caught two audit over-claims**
  (the path-sweep was 5 sites not ~15; the S7 audit's constants were wrong) — so the wrong
  thing was never built.
- A workflow infrastructure bug (isolated worktrees based on a stale commit) was **caught
  by ground-truth git checks** and the affected slices rebuilt on a verified base.
- Covenant guards eyeballed on every sensitive touch: ledger birth-gate, S7 human-gate,
  S7 origin invariant — all untouched (path/pointer only).
- Cockpit memory-promotion + felt-time were **NOT** auto-granted — they stay behind a real
  cockpit auth story (see §5), because localhost-bind ≠ owner authentication.

---

## 3. How to test before you commit to anything

The fastest real test, no merge required — witness the flags on the branch in a sandbox,
or after merge (below). The face is the surface you most wanted to *see*:

1. **The honest dashboard.** With `campaign-integration` checked out and
   `MAEZ_COCKPIT_REAL_STATE=1`, the cockpit's mind panel shows real cycle/score/thought/
   valence instead of the old theater. Confirm: no "mood"/"uncertainty" dial anymore; the
   "current thought" matches the daemon's actual last cycle text (not a log guess).
2. **Cockpit chat through the unified core.** With `MAEZ_COCKPIT_CORE=1`, send a
   crisis-class message to the cockpit — S4 now fires (it didn't before). Send a normal
   message — it flows through `run_inbound_turn` → `handle_message`. (Tools aren't wired to
   cockpit yet — see §5.)
3. **Telegram unchanged.** `MAEZ_INBOUND_CORE_V2=1` should be invisible on Telegram
   (byte-identical) — that's the point; flip it and confirm nothing changes.

---

## 4. Switch-over runbook (your breaths — I did NOT do these)

When you're satisfied:
```
cd /home/rohit/maez
git merge campaign-integration            # one clean branch; no conflicts expected
# re-render the systemd units from the updated templates (boot slice + maez-web unit):
bash scripts/install.sh                    # renders Type=notify maez.service + new maez-web.service
systemctl --user daemon-reload
systemctl --user restart maez.service
# then flip the unification flags ONE AT A TIME, witnessing each (they default off):
#   MAEZ_INBOUND_CORE_V2=1     (Telegram on the unified core — byte-identical)
#   MAEZ_COCKPIT_CORE=1        (cockpit on the unified core — closes cockpit S4)
#   MAEZ_COCKPIT_REAL_STATE=1  (honest dashboard)
# (supporting-slice flags already default to the safe/enforced state; no action needed)
```
Each flag is independently reversible (set to `0`/unset). The egress kill-switch
(`MAEZ_EGRESS_ORIGIN_DOWNGRADE_SHADOW=1`) reverts that rail to shadow if needed.

---

## 5. What's deferred / needs you (not done autonomously, on purpose)

- **Cockpit tools/cards renderer.** Cockpit chat works but has no tools yet, because the
  brain-loop's card-or-tool results need a *cockpit* renderer (the Telegram one sends via
  Telegram). That renderer **is** a face/UX decision — how a tool result or an approval
  card looks in the cockpit — so it's yours to shape, not mine to invent.
- **Face visual polish.** The dashboard is *honest* but not *beautiful*. I deliberately
  did not restyle — aesthetics are yours to react to. Tell me the direction and I'll build it.
- **Cockpit M1 promotion + felt-time** (a covenant decision). Default: **no** — cockpit is
  excluded from M1 promotion (no durable *selfhood* at the M1 layer), and felt-time is off
  (its "proof" would only prove "something reached loopback"). Flipping either needs a real
  cockpit auth story first. **Honest caveat (corrected by the self-review):** the *raw*
  conversation is still stored as ordinary `lived` memory, same as the legacy `source="UI"`
  path — that's pre-existing, not M1 promotion, but *whether cockpit should write lived
  memory at all from an unauthenticated surface* is a real open covenant decision for you.
- **Codex independent review** — your review lane; I can't run it. The campaign diffs are
  ready for it.

### Self-review hardening (a pre-Codex bug-hunt I ran on the diffs)
Three read-only adversarial reviewers swept the novel work; I verified + fixed the real
findings (now on `campaign-integration` @`2f80c25`):
- **(covenant)** a cockpit S4-crisis turn was calling `_mark_m1_s4_policy`, which marks the
  *shared* (Telegram-fed) M1 window ineligible — i.e. a cockpit message could suppress a
  Telegram-originated episode. Latent (M1 birth-gated) but real. Fixed: cockpit returns the
  crisis-care reply but no longer touches the shared window.
- **(equivalence)** the cockpit D20-gate change had made flag-on diverge from flag-off on
  Telegram when the pipeline was None (a degraded path). Fixed: the gate is now opt-in
  (cockpit only); Telegram is strictly byte-identical again, with new no-pipe/no-memory
  equivalence tests.
- **(robustness)** `Type=notify` + `MAEZ_SYSTEMD_NOTIFY=0` could strand the unit in a
  start-timeout crash-loop. Fixed: a present `NOTIFY_SOCKET` force-sends `READY=1`
  regardless of the flag.
- Plus honest-wording fixes (this caveat above; the boot unit comment) and an honest
  error-payload on the cockpit route.
One known minor: the equivalence harness patches `sys.modules`, so a *combined* multi-suite
run shows 2 cross-pollination failures — green in the prescribed per-module mode; a
test-hygiene follow-up, not a code regression.
- Beyond the campaign: S7 enrollment (your keys, its own deliberate session),
  GitHub/Reddit creds, birth.

---

## 6. Branch map

- `main` — live; carries only the S4 fix (@`f2a56f9`) + ledger.
- `supporting-slices` — the 5 consolidation slices.
- `inbound-core-v2` — the revised design + surface-merge (S0/S1/S2) + the honest face.
- `campaign-integration` — **the union; merge this at switch-over.**
- `docs/MAEZ_BUILD_LEDGER.md` — the hospital chart; the S4 row is `LIVE_WITNESSED`.
