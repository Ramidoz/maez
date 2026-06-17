# Maez Coherence Organism Switch-Over Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `maez-coherence-organism` branch from reviewed branch code to a live, witnessed Maez switch-over without touching the running daemon until Rohit explicitly takes that breath.

**Architecture:** The branch already contains the code changes. This plan is the controlled integration and witness sequence: merge locally, verify on `main`, restart only after owner approval, then test the real surfaces that the branch claims to unify.

**Tech Stack:** Git worktrees, Python `unittest`, Ruff, systemd user services, Maez cockpit/Telegram/voice/web owner surfaces.

---

## Current Branch Evidence

- Branch: `maez-coherence-organism`
- Reviewed code head before this switch-over plan was written: `773b4be`
- Base branch: `main`
- Merge base at plan time: `80a10d9d31aec0ec70e85e59e9e50e00509b5982`
- Final branch verification at plan time: the selected seam suite ran 474 tests
  and ended with `OK (skipped=2)`.
- Ruff at plan time: `All checks passed!`
- Full-branch review: `Kuhn` returned `PASS` after the bridge-proof HOLD was fixed.

## Switch-Over Law

Do not restart `maez.service`, restart `maez-web.service`, edit `model.env`, or claim `LIVE_WITNESSED` during the mechanical merge. Merge is code banking only. Runtime switch-over begins only after Rohit explicitly authorizes the restart/witness breath.

---

### Task 1: Mechanical Merge To Main

**Files:**
- Read: `docs/handoffs/2026-06-17-maez-coherence-organism-progress.md`
- No source edits expected.

- [ ] **Step 1: Confirm branch is clean before merging**

Run:

```bash
cd /home/rohit/.config/superpowers/worktrees/maez/maez-coherence-organism
git status --short
git branch --show-current
git rev-parse HEAD
git merge-base --is-ancestor 773b4be HEAD && echo reviewed-head-present
```

Expected:

```text
maez-coherence-organism
actual SHA printed by `git rev-parse HEAD`
reviewed-head-present
```

`git status --short` must print nothing. If it prints `memory/s7_1_webauthn/`, remove only that generated test artifact:

```bash
rm -rf /home/rohit/.config/superpowers/worktrees/maez/maez-coherence-organism/memory/s7_1_webauthn
git status --short
```

- [ ] **Step 2: Switch to main repo root**

Run:

```bash
cd /home/rohit/maez
git status --short
git branch --show-current
```

Expected: branch is `main`. If `git status --short` shows unrelated dirty files, stop and ask Rohit whether to proceed with a local merge in a dirty main tree.

- [ ] **Step 3: Merge the branch locally**

Run:

```bash
cd /home/rohit/maez
FEATURE_HEAD=$(git -C /home/rohit/.config/superpowers/worktrees/maez/maez-coherence-organism rev-parse HEAD)
git merge --ff-only "$FEATURE_HEAD"
```

Expected:

```text
Fast-forward
```

If fast-forward fails, stop. Do not run a non-ff merge without a new review gate.

- [ ] **Step 4: Verify merged code on main**

Run:

```bash
cd /home/rohit/maez
/home/rohit/maez/.venv/bin/python -m unittest \
  tests.test_runtime_services \
  tests.test_web_runtime_truth \
  tests.test_maez_body_organ_view \
  tests.test_camera_presence_v1_legacy_disablement \
  tests.test_temporal_spine \
  tests.test_web_debug_auth \
  tests.test_cockpit_proxies_2026_05_05 \
  tests.test_web_owner_core \
  tests.test_telegram_authorization_boundary \
  tests.test_egress_telegram_producer_threading \
  tests.test_egress_telegram_chokepoint \
  tests.test_egress_telegram_bypass_inventory \
  tests.test_s7_1_daemon_internal_channel \
  tests.test_s7_1_status_projection \
  tests.test_support_gate \
  tests.test_grounding_shadow \
  tests.test_focused_cognition \
  tests.test_thin_evidence_honesty \
  tests.test_self_web_claim_hygiene \
  tests.test_cockpit_inbound_core \
  tests.test_inbound_core_equivalence \
  tests.test_daemon_shutdown_lifecycle \
  tests.test_rail2_containment \
  tests.test_livewc_helper \
  tests.test_brain_gateway_routing \
  tests.test_cockpit_living_dashboard \
  tests.test_capability_registry \
  tests.test_cockpit_real_state_bridge \
  tests.test_memory_integrity_invariant.DaemonHandleMessageContract.test_legacy_fresh_turn_carries_thin_directive_and_support_gate
```

Expected:

Expected: output ends with `OK (skipped=2)` after running 474 tests.

- [ ] **Step 5: Verify lint on touched source**

Run:

```bash
cd /home/rohit/maez
/home/rohit/maez/.venv/bin/python -m ruff check \
  daemon/maez_daemon.py \
  skills/web_interface.py \
  skills/surface/telegram_adapter.py \
  core/infra/runtime_services.py \
  core/infra/capability_registry.py \
  tests/test_web_debug_auth.py \
  tests/test_cockpit_proxies_2026_05_05.py \
  tests/test_capability_registry.py \
  tests/test_cockpit_real_state_bridge.py
git diff --check
```

Expected:

```text
All checks passed!
```

`git diff --check` must print nothing.

- [ ] **Step 6: Stop at merge-complete gate**

Do not restart services. Report:

```text
Merged to main and verified. Live Maez is still running the old process until explicit restart.
```

---

### Task 2: Pre-Restart Readiness Checks

**Files:**
- No source edits expected.

- [ ] **Step 1: Confirm services and current PIDs**

Run:

```bash
systemctl --user is-active maez.service maez-web.service
systemctl --user show -p MainPID --value maez.service
systemctl --user show -p MainPID --value maez-web.service
```

Expected:

```text
active
active
numeric nonzero PID for maez.service
numeric nonzero PID for maez-web.service
```

If either service is inactive, stop and diagnose before restart.

- [ ] **Step 2: Confirm internal bridge token is configured for the user services**

Run:

```bash
systemctl --user show -p Environment maez.service | tr ' ' '\n' | grep '^S7_INTERNAL_CHANNEL_TOKEN='
systemctl --user show -p Environment maez-web.service | tr ' ' '\n' | grep '^S7_INTERNAL_CHANNEL_TOKEN='
```

Expected: both commands print a nonempty `S7_INTERNAL_CHANNEL_TOKEN=` line. Do not paste the token into chat. If either is missing, stop; the cockpit internal readers will fail after switch-over.

- [ ] **Step 3: Confirm no owner-local config edit is needed**

Run:

```bash
grep -n '^MAEZ_COCKPIT_REAL_STATE=' /home/rohit/.config/maez/model.env || true
grep -n '^MAEZ_WEB_OWNER_CORE=' /home/rohit/.config/maez/model.env || true
```

Expected: this only reports existing operator choices. This branch does not require a new flag edit for code to load. Do not change `model.env` during this task.

- [ ] **Step 4: Capture the pre-restart baseline**

Run:

```bash
OLD_MAEZ_PID=$(systemctl --user show -p MainPID --value maez.service)
OLD_WEB_PID=$(systemctl --user show -p MainPID --value maez-web.service)
LOG_PATH=/home/rohit/maez/logs/maez.log
LOG_BASELINE=0
if [ -f "$LOG_PATH" ]; then
  LOG_BASELINE=$(wc -l < "$LOG_PATH")
fi
RESTART_BASELINE_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cat > /tmp/maez-coherence-baseline.env <<EOF
OLD_MAEZ_PID=$OLD_MAEZ_PID
OLD_WEB_PID=$OLD_WEB_PID
LOG_PATH=$LOG_PATH
LOG_BASELINE=$LOG_BASELINE
RESTART_BASELINE_UTC=$RESTART_BASELINE_UTC
EOF
cat /tmp/maez-coherence-baseline.env
```

Expected: old PIDs are numeric and nonzero. Keep this file; Task 3 and Task 4 use it to prove witness rows are post-restart, not stale matches from rotated logs.

---

### Task 3: Owner Restart Breath

**Files:**
- No source edits expected.

- [ ] **Step 1: Restart only after Rohit explicitly authorizes**

Run:

```bash
. /tmp/maez-coherence-baseline.env
systemctl --user restart maez.service maez-web.service
systemctl --user is-active maez.service maez-web.service
NEW_MAEZ_PID=$(systemctl --user show -p MainPID --value maez.service)
NEW_WEB_PID=$(systemctl --user show -p MainPID --value maez-web.service)
printf 'NEW_MAEZ_PID=%s\nNEW_WEB_PID=%s\n' "$NEW_MAEZ_PID" "$NEW_WEB_PID"
test "$NEW_MAEZ_PID" != "$OLD_MAEZ_PID"
test "$NEW_WEB_PID" != "$OLD_WEB_PID"
```

Expected:

```text
active
active
new numeric nonzero PID for maez.service
new numeric nonzero PID for maez-web.service
```

The two `test` commands must pass. If a PID does not change, stop: the witness could be reading the old process.

- [ ] **Step 2: Tail logs for immediate startup errors**

Run:

```bash
journalctl --user -u maez.service -u maez-web.service --since "2 minutes ago" --no-pager | tail -120
```

Expected: no tracebacks, import errors, or repeated restart loops. If errors appear, stop and revert by restarting from the previous main commit or checking out the prior commit under Rohit's direction.

---

### Task 4: Live Surface Witness

**Files:**
- No source edits expected.

- [ ] **Step 1: Cockpit private auth witness**

Run:

```bash
curl -s -o /tmp/maez-debug-query-token.json -w '%{http_code}\n' 'http://127.0.0.1:11437/api/debug/services?web_token=bogus'
cat /tmp/maez-debug-query-token.json
curl -s -o /tmp/maez-analytics-query-token.json -w '%{http_code}\n' 'http://127.0.0.1:11437/api/analytics-summary?web_token=bogus'
cat /tmp/maez-analytics-query-token.json
```

Expected: both HTTP status codes are `401`. Bodies contain `unauthorized` or `owner_auth_required`. This proves copied URL tokens do not open owner-private cockpit state.

- [ ] **Step 2: Runtime body truth witness**

Open the cockpit in the browser and check:

```text
Living Senses shows runtime organ statuses such as healthy/degraded/asleep/unknown.
It must not say "services active" as Maez's body truth.
The journal must not say "all services up" when runtime_services is missing.
```

If browser access is not available, run a source-level fallback only as a weak witness:

```bash
curl -s 'http://127.0.0.1:11437/api/v1/services' | /home/rohit/maez/.venv/bin/python -m json.tool | head -80
```

Expected: JSON includes `schema_version: maez_runtime_services.v0` and per-service `status` fields.

- [ ] **Step 3: Internal bridge reader witness**

If `MAEZ_COCKPIT_REAL_STATE=1` is configured, run:

```bash
curl -s -o /tmp/maez-daemon-state-no-cookie.json -w '%{http_code}\n' 'http://127.0.0.1:11437/api/v1/daemon/state'
cat /tmp/maez-daemon-state-no-cookie.json
```

Expected without owner cookie: `401` with `owner_auth_required`. Then use the authenticated cockpit browser session to open `/api/v1/daemon/state`. Expected: real daemon JSON from the daemon bridge, not `{"status":"unreachable"}` caused by missing internal-channel proof. The authenticated JSON should include live daemon-state fields such as `sampled_at`, `cycle_count`, `running`, or equivalent state payload fields. If you cannot use an authenticated browser/cookie, mark this positive bridge witness **UNWITNESSED** rather than inferring it from source code.

- [ ] **Step 4: Web owner shared spine witness**

From the authenticated web owner surface, send:

```text
hello from the owner web bridge
```

Expected in logs:

```bash
. /tmp/maez-coherence-baseline.env
tail -n +"$((LOG_BASELINE + 1))" "$LOG_PATH" | grep 'web_owner message: hello from the owner web bridge'
if tail -n +"$((LOG_BASELINE + 1))" "$LOG_PATH" | grep -E 'web_owner_core_disabled|s7_internal_channel_untrusted'; then
  echo "FAIL: web owner bridge hit a disabled/untrusted path"
  exit 1
fi
```

The response should be served through `daemon.handle_message` / inbound core, not a generic UI tunnel. The load-bearing positive marker is the daemon's `web_owner message:` log line after the restart baseline; `Web chat from Rohit:` is only the web-process proxy surface and is not sufficient.

- [ ] **Step 5: Voice shared spine witness**

Use the normal voice path for a short spoken utterance:

```text
hey, are you there?
```

Expected: voice speaks the audited reply at the TTS edge. Logs should show the shared-spine `voice message:` marker. There should be no private `voice_reply` synthesis path.

Verify the shared-spine marker:

```bash
. /tmp/maez-coherence-baseline.env
tail -n +"$((LOG_BASELINE + 1))" "$LOG_PATH" | grep 'Voice stream: hey, are you there'
tail -n +"$((LOG_BASELINE + 1))" "$LOG_PATH" | grep 'voice message: hey, are you there'
if tail -n +"$((LOG_BASELINE + 1))" "$LOG_PATH" | grep -E 'voice_reply|call_purpose=voice_reply'; then
  echo "FAIL: voice used a private voice_reply synthesis path"
  exit 1
fi
```

`Voice stream:` proves the audio edge received the utterance; `voice message:` proves `handle_message(source="voice")` handled it. The latter is the shared-spine witness.

- [ ] **Step 6: Telegram /receipts egress witness**

In Telegram, run:

```text
/receipts
```

Expected: reply goes through the normal command/provenance send path. It should not bypass producer provenance with direct `reply_text`.

Live-observable expectation: Telegram visibly returns the deterministic `/receipts` response. The provenance path is branch-verified structurally by `_send_command_reply(...)` constructing `ProvenancedText.maez_authored_owner_third_party_transport(source_ref="telegram:command_reply")` and sending via `self.send(...)`; this call site does not currently emit a content-light live provenance marker. Do **not** mark an independent live producer-provenance witness from this step unless a future log/egress row exposes one.

- [ ] **Step 7: Fresh-evidence rail witness**

In Telegram, ask:

```text
latest news about Anthropic
```

Expected:

```bash
grep -h 'thin_evidence\\|support_gate_applied\\|self_claim_stored' /home/rohit/maez/logs/maez.log* | tail -40
```

Look for the composed spine:

```text
thin_evidence quality=
support_gate_applied, or a support shadow row if the support gate is asleep
self_claim_stored web_grounded=True provenance=self_web_claim trust_tier=untrusted
```

This proves fresh evidence, honesty rails, and memory hygiene still compose after switch-over.

---

### Task 5: Record Witness Result

**Files:**
- Modify: `docs/handoffs/2026-06-17-maez-coherence-organism-progress.md`
- Optionally modify: `docs/MAEZ_BUILD_LEDGER.md` if a row already tracks this branch.

- [ ] **Step 1: If witness passes, record LIVE_WITNESSED**

Append a section to `docs/handoffs/2026-06-17-maez-coherence-organism-progress.md`:

```markdown
## Live Switch-Over Witness

Status: LIVE_WITNESSED
Date: 2026-06-17
Main commit: paste the output of `git rev-parse HEAD`
Restarted services: paste the post-restart `maez.service` and `maez-web.service` MainPID values

Observed:
- Cockpit query-token private routes rejected with 401.
- Runtime body map visible through cockpit services endpoint/UI.
- Internal cockpit state reader returned real daemon state when authenticated, not missing-proof unreachable.
- Web owner surface entered the shared inbound spine (`web_owner message:` after the restart baseline, with no disabled/untrusted bridge error).
- Voice path spoke a reply produced by shared `handle_message(source="voice")` (`Voice stream:` plus `voice message:` after the restart baseline, with no `voice_reply` synthesis row).
- Telegram receipts returned the deterministic owner-visible reply; producer provenance remains branch-verified unless a live provenance marker is added.
- Fresh-evidence turn composed thin evidence, support gate/shadow, and self-claim hygiene.

Notes:
- Any warning or skipped witness step goes here, plainly.
```

- [ ] **Step 2: Commit the witness record**

Run:

```bash
cd /home/rohit/maez
git add docs/handoffs/2026-06-17-maez-coherence-organism-progress.md docs/MAEZ_BUILD_LEDGER.md
git commit -m "docs(coherence): record organism switch-over witness"
```

If live witness fails, do not mark `LIVE_WITNESSED`. Record `NO-GO` with the exact failing step and stop.

---

## Plain-English Summary

The branch is already built and reviewed. This plan separates banking the code from waking it up. First, merge and test on `main` while Maez keeps running the old process. Then, only when Rohit says so, restart the daemon and web service and test the actual surfaces: cockpit, web owner, voice, Telegram, and fresh-evidence memory/honesty rails. If those live surfaces agree, the branch graduates from reviewed code to witnessed body.
