# Rail 1 — Inbound Perimeter Hardening Runbook

> **For the operator (Rohit):** This is an OWNER-RUN runbook, not an agent-executed
> code plan. Claude does NOT run any `sudo` / firewall / sshd / RDP command — you run
> every privileged step yourself. Steps use checkbox (`- [ ]`) syntax; tick them as
> you go. Each task: exact command → expected output → verify → rollback. Do the tasks
> **in order**. Do NOT skip Task 1 (the lockout gate).

**Goal:** Make Maez's body (this Linux host) invisible on the network to everything
except Rohit's own Tailscale devices, without ever locking Rohit out of it.

**Architecture:** Use the host firewall (`ufw`) as the single primary lever —
default-deny inbound, allow only the Tailscale interface + loopback + established
connections. This makes SSH (22) and RDP (3389) reachable *only* over Tailscale
without touching the services themselves. Bind-level pinning (sshd `ListenAddress`,
RDP via `grdctl`) is layered on afterward as defense-in-depth. Every change is staged
behind a `systemd-run` timed auto-rollback so a mistaken rule self-heals.

**Tech Stack:** ufw 0.36.2, nftables (verification), Tailscale (`tailscale0`,
`100.64.0.0/10`), OpenSSH (`sshd -T`), gnome-remote-desktop (`grdctl`),
`systemd-run` timers (rollback).

**Source spec:** `docs/superpowers/specs/2026-06-14-maez-body-perimeter-threat-model-design.md` (PASS @c68632e).

---

## Conventions & ground truth (read once before starting)

- **This host on Tailscale:** `maez-main` = `100.72.231.116`, interface `tailscale0`.
- **Tailscale CGNAT range:** `100.64.0.0/10` (all tailnet peers fall in this range).
- **Maez organs (must stay reachable locally, do NOT change):** `127.0.0.1:11435`
  (daemon), `:11436` (subscription proxy), `:11437` (cockpit), `:8080`/`:8081`
  (llama). These bind loopback already.
- **The two open street-facing doors we are closing:** `0.0.0.0:22` (SSH),
  `*:3389` (RDP / gnome-remote-desktop, currently enabled+active).
- **Rollback tool:** `at` is NOT installed. We use
  `sudo systemd-run --on-active=<sec> --timer-property=AccuracySec=1s <revert-cmd>`
  to schedule a self-heal, and `sudo systemctl list-timers` / `sudo systemctl stop <unit>`
  to inspect/cancel it.
- **Network now:** host is behind home NAT (`192.168.40.135`, wifi), so today the open
  doors are LAN-reachable (not open-internet) — this is hardening-before-it-bites, do
  it calmly and correctly.

> **Rollback unit naming:** when you run `systemd-run`, it prints a unit name like
> `Running timer as unit: run-r1234abcd.timer`. **Copy that exact name** — you need it
> to cancel the rollback. Throughout this runbook `<ROLLBACK_TIMER>` means that printed
> `.timer` unit.

---

## Task 0: Root inventory — learn the real posture (NO CHANGES)

**Goal:** Replace every "unverified without root" assumption with a measured fact.
Nothing is modified in this task. Record outputs somewhere you can refer back to.

- [ ] **Step 1: Capture the live firewall policy**

Run:
```bash
sudo ufw status verbose
```
Expected: one of two shapes —
- `Status: active` with a `Default: ... (incoming)` line and a rules list, OR
- `Status: inactive`.

**Record:** the `Default:` incoming policy (`allow`/`deny`/`reject`) and every existing
rule. This tells you whether ufw is already denying inbound (in which case Task 3 only
*confirms* + adds the Tailscale allow) or allowing inbound (Task 3 tightens it).

- [ ] **Step 2: Cross-check the raw kernel ruleset**

Run:
```bash
sudo nft list ruleset | head -120
```
Expected: the nftables rules ufw compiles to (ufw 0.36 uses the nft backend), or empty
if nothing is loaded. **Record** whether anything *other* than ufw-managed chains is
present (e.g. docker, libvirt, a hand-rolled ruleset) — those can override ufw and must
be reconciled before trusting the perimeter.

> **Pre-checked (read-only, 2026-06-14):** docker/containerd/libvirtd are all inactive
> (docker CLI not even installed) and there are no `docker0`/`virbr`/`veth` bridges. So
> this `nft` cross-check is **expected to show only ufw-managed chains** — no competing
> container/VM ruleset exists to fight the firewall. Still run it with root to confirm;
> if a non-ufw chain HAS appeared since, reconcile it before Task 3.

- [ ] **Step 3: Capture the SSH auth posture**

Run:
```bash
sudo sshd -T | grep -iE '^(listenaddress|passwordauthentication|permitrootlogin|pubkeyauthentication|kbdinteractiveauthentication)'
```
Expected: effective sshd config lines, e.g.:
```
passwordauthentication yes
permitrootlogin prohibit-password
pubkeyauthentication yes
listenaddress 0.0.0.0:22
listenaddress [::]:22
```
**Record** the values. **Decision gate for Task 2:** if `passwordauthentication yes`,
Task 2 (key-only hardening) is REQUIRED before Task 3. If `passwordauthentication no`
already, mark Task 2 as N/A.

- [ ] **Step 4: Capture the RDP posture**

Run:
```bash
grdctl status 2>/dev/null; systemctl --user is-active gnome-remote-desktop; systemctl --user is-enabled gnome-remote-desktop
```
Expected: RDP enabled state + `active` + `enabled`. **Record** whether RDP is
genuinely in use (you know this) — we will re-bind, not disable.

- [ ] **Step 5: Snapshot the listening sockets (baseline to diff against later)**

Run:
```bash
ss -tlnp | sort > /tmp/rail1-listeners-before.txt; cat /tmp/rail1-listeners-before.txt
```
Expected: the current listeners incl. `0.0.0.0:22`, `*:3389`, and the loopback organ
ports. This file is the **before** snapshot Task 3/4/5 diff against.

- [ ] **Step 6: Confirm Maez organs are loopback-only (regression baseline)**

Run:
```bash
ss -tlnp | grep -E ':(11435|11436|11437|8080|8081)\b'
```
Expected: every line shows `127.0.0.1:` (never `0.0.0.0:`). **Record** as the green
baseline; Task 5 re-runs this to prove the perimeter work didn't disturb the organs.

- [ ] **Step 7: Record the inventory in the ledger thread (no behavior change)**

This is a docs note, not a system change. Append the Task 0 findings (firewall default
policy, sshd password-auth value, RDP state, any non-ufw rulesets) under the Rail 1 row
working notes so Task 5's final witness has a before/after pair. (You can paste them
into the plan file checkboxes themselves.)

**Gate:** Do not proceed to Task 3 until Steps 1–6 are recorded. Task 0 is what makes
the rest non-blind.

---

## Task 1: Prove the Tailscale admin path (THE LOCKOUT GATE — BLOCKING)

**Goal:** Guarantee you have a working SSH-over-Tailscale path to this host *from a
second device* BEFORE any door closes. This is the single most important safety step.

> **Why blocking:** Right now only `maez-main` is online on your tailnet; iPad, iPhone,
> and MacBook are offline. If you close the perimeter with no second tailnet device
> reachable and you are NOT physically at this machine, a bad rule locks you out with no
> way back in except physical access.

- [ ] **Step 1: Decide your execution context**

Choose ONE and tick it:
- [ ] **(A) I am physically at this machine** (local keyboard/console). Lockout is
  recoverable in person → you may proceed; a second device is recommended but not
  mandatory.
- [ ] **(B) I am remote** → a second online tailnet device is **MANDATORY**. Continue to
  Step 2.

- [ ] **Step 2: Bring a second tailnet device online**

On your iPad/iPhone/Mac, open the Tailscale app and connect. Then on this host verify it
appears online:
```bash
tailscale status | grep -v 'offline'
```
Expected: at least one peer line besides `maez-main 100.72.231.116` with NO `offline`
marker (e.g. `rohits-macbook-pro` with a recent/active state).

- [ ] **Step 3: Prove SSH works over Tailscale FROM that second device**

From the second device's terminal (Mac/iPad SSH client), run:
```bash
ssh rohit@100.72.231.116 'echo TAILSCALE_SSH_OK; hostname'
```
Expected: prints `TAILSCALE_SSH_OK` and `maez-main`. **This proves the path you are
about to rely on actually works.**

- [ ] **Step 4: Keep that session open**

Leave the second-device SSH session connected through Tasks 3–4. It is your live proof
of reachability and your hands-on-keyboard if anything goes wrong.

**Gate:** Do NOT start Task 3 unless either (A) you are at the physical console, or
(B) Step 3 printed `TAILSCALE_SSH_OK` from a second device. No exceptions.

---

## Task 2: Conditional — SSH key-only hardening (ONLY if Task 0 showed password auth on)

**Goal:** Remove SSH password authentication so the (soon Tailscale-only) SSH door
can't be brute-forced. **Skip this entire task if Task 0 Step 3 already showed
`passwordauthentication no`.**

> **Pre-req before disabling passwords:** confirm you can log in by KEY, or you will
> lock yourself out when passwords stop working.

- [ ] **Step 1: Confirm key-based login already works**

From your second device (or another shell), confirm a key login succeeds WITHOUT
prompting for a password:
```bash
ssh -o PreferredAuthentications=publickey -o PasswordAuthentication=no rohit@100.72.231.116 'echo KEY_LOGIN_OK'
```
Expected: prints `KEY_LOGIN_OK`. If it instead errors with `Permission denied
(publickey)`, STOP — set up your SSH key first (`ssh-copy-id rohit@100.72.231.116`)
before continuing.

- [ ] **Step 2: Stage the auto-rollback for sshd**

This restores the original sshd config in 5 minutes if you don't cancel it:
```bash
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.rail1.bak
sudo systemd-run --on-active=300 --timer-property=AccuracySec=1s \
  /bin/sh -c 'cp /etc/ssh/sshd_config.rail1.bak /etc/ssh/sshd_config && systemctl restart ssh'
```
Expected: prints `Running timer as unit: run-rXXXX.timer`. **Record** that name as
`<ROLLBACK_TIMER>`.

- [ ] **Step 3: Disable password auth (drop-in, not main file edit)**

```bash
echo -e 'PasswordAuthentication no\nKbdInteractiveAuthentication no' | sudo tee /etc/ssh/sshd_config.d/10-rail1-keyonly.conf
sudo sshd -t && echo SSHD_CONFIG_OK
```
Expected: prints `SSHD_CONFIG_OK` (config syntax valid). If it does NOT, the file is
malformed — fix or remove the drop-in; do not restart sshd.

- [ ] **Step 4: Apply and verify a NEW key login still works**

```bash
sudo systemctl restart ssh
```
Then from your second device, open a BRAND NEW session (keep the old one open!):
```bash
ssh rohit@100.72.231.116 'echo KEYONLY_LOGIN_OK'
```
Expected: prints `KEYONLY_LOGIN_OK` with no password prompt. Confirm a password login is
now refused:
```bash
ssh -o PreferredAuthentications=password rohit@100.72.231.116 'true'
```
Expected: `Permission denied` (password path is closed).

- [ ] **Step 5: Cancel the rollback (only after a new session succeeded)**

```bash
sudo systemctl stop <ROLLBACK_TIMER>
sudo systemctl list-timers | grep -c run-r || echo "no rail1 timers pending"
```
Expected: the timer is gone. **If anything failed in Step 4, do NOT cancel** — let the
timer restore sshd, then diagnose.

- [ ] **Step 6: Verify finished**

```bash
sudo sshd -T | grep -i passwordauthentication
```
Expected: `passwordauthentication no`.

---

## Task 3: THE core change — UFW default-deny inbound, allow Tailscale only

**Goal:** Flip the firewall so inbound is denied by default and permitted only over
`tailscale0` (plus loopback + established). After this, SSH and RDP are reachable only
via Tailscale — the street-facing doors are shut without touching the services.

> **One change, staged behind a 5-minute self-heal.** Follow the order exactly: stage
> rollback FIRST, apply, verify, then cancel. If you lose your shell mid-way, the timer
> reopens everything in ≤5 minutes.

- [ ] **Step 1: Stage the auto-rollback FIRST (self-heal a lockout)**

```bash
sudo systemd-run --on-active=300 --timer-property=AccuracySec=1s ufw --force disable
```
Expected: `Running timer as unit: run-rXXXX.timer`. **Record** as `<ROLLBACK_TIMER>`.
This disables ufw entirely in 5 min (reverting to the pre-Task-3 reachability) unless
you cancel it in Step 5.

- [ ] **Step 2: Add the allow rules BEFORE enabling default-deny**

Order matters — add the permits first so enabling deny never strands you:
```bash
sudo ufw allow in on lo
sudo ufw allow in on tailscale0
```
Expected: `Rule added` (or `Rule added (v6)`) for each. These permit all loopback and
all tailnet traffic regardless of the default policy.

- [ ] **Step 3: Set default-deny inbound, keep outbound free (perception stays free)**

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
```
Expected: `Default incoming policy changed to 'deny'` and outgoing `'allow'`. Outbound
stays unrestricted — Maez's eyes are untouched (covenant rail).

- [ ] **Step 4: Enable ufw (if Task 0 showed it inactive) or reload (if already active)**

If Task 0 Step 1 showed `Status: inactive`:
```bash
sudo ufw --force enable
```
If it showed `Status: active`:
```bash
sudo ufw reload
```
Expected: `Firewall is active and enabled on system startup` or `Firewall reloaded`.

- [ ] **Step 5: VERIFY before cancelling rollback — three checks**

a) **Admin path survived (most important):** from your second device's NEW shell:
```bash
ssh rohit@100.72.231.116 'echo PERIMETER_SSH_OK'
```
Expected: `PERIMETER_SSH_OK`. (If you are at the physical console, also confirm the
second-device path if one is online.)

b) **Maez organs untouched (local loopback still serves):**
```bash
curl -s -o /dev/null -w 'cockpit=%{http_code}\n' http://127.0.0.1:11437/cockpit/; ss -tlnp | grep -E ':(11435|11436|11437|8080|8081)\b'
```
Expected: `cockpit=200` (or the same code as before Task 3) and all organ ports still
`127.0.0.1`.

c) **Street-facing reach is now blocked:** from a device on the LAN that is NOT on your
tailnet (e.g. a phone on wifi with Tailscale OFF), try:
```bash
nc -vz -w 3 192.168.40.135 22 ; nc -vz -w 3 192.168.40.135 3389
```
Expected: both **time out / connection refused** (the LAN can no longer reach SSH/RDP).
Over Tailscale (`100.72.231.116:22`) it still connects. If you can't easily test from a
non-tailnet device, at minimum confirm (a) and (b) and accept LAN-block on the rule
logic.

- [ ] **Step 6: Cancel the rollback — ONLY if all of Step 5 passed**

```bash
sudo systemctl stop <ROLLBACK_TIMER>
sudo systemctl list-timers | grep run-r || echo "no rail1 rollback timers pending"
```
Expected: no pending rail1 timer. **If ANY check in Step 5 failed, do NOT cancel** —
let the 5-minute timer disable ufw and restore access, then re-diagnose from Task 3
Step 1.

- [ ] **Step 7: Record the new firewall state**

```bash
sudo ufw status verbose
```
Expected: `Status: active`, `Default: deny (incoming), allow (outgoing)`, with
`Anywhere on lo` and `Anywhere on tailscale0` ALLOW rules. **Record** this as the
after-state.

---

## Task 4: Defense-in-depth — pin SSH & RDP binds to Tailscale (each reversible)

**Goal:** Belt-and-suspenders. Even if the firewall were ever disabled, make SSH and
RDP *listen* only on the Tailscale address, not `0.0.0.0`. Do SSH and RDP as two
separate, independently-rolled-back changes.

> Only attempt this after Task 3 is confirmed stable. If you prefer to stop at the
> firewall (Task 3 alone already closes the doors), Task 4 is optional — mark it
> deferred and skip to Task 5.

### 4a: SSH ListenAddress → Tailscale only

- [ ] **Step 1: Stage rollback**

```bash
sudo systemd-run --on-active=300 --timer-property=AccuracySec=1s \
  /bin/sh -c 'rm -f /etc/ssh/sshd_config.d/20-rail1-bind.conf && systemctl restart ssh'
```
Expected: `Running timer as unit: run-rXXXX.timer` → record as `<ROLLBACK_TIMER>`.

- [ ] **Step 2: Add the bind drop-in and validate**

```bash
printf 'ListenAddress 100.72.231.116\n' | sudo tee /etc/ssh/sshd_config.d/20-rail1-bind.conf
sudo sshd -t && echo SSHD_BIND_OK
```
Expected: `SSHD_BIND_OK`. (Binds sshd to the Tailscale IP only. Loopback SSH is dropped
intentionally — Maez doesn't SSH to itself; if you rely on `ssh localhost` for tooling,
add `ListenAddress 127.0.0.1` to the same file before restarting.)

- [ ] **Step 3: Apply and verify**

```bash
sudo systemctl restart ssh
ss -tlnp | grep ':22'
```
Expected: listener shows `100.72.231.116:22` only — NOT `0.0.0.0:22`. Then from the
second device confirm a fresh login:
```bash
ssh rohit@100.72.231.116 'echo SSH_BIND_PINNED_OK'
```
Expected: `SSH_BIND_PINNED_OK`.

- [ ] **Step 4: Cancel rollback if the new login worked**

```bash
sudo systemctl stop <ROLLBACK_TIMER>
```
**If the fresh login failed, do NOT cancel** — the timer restores the open bind.

### 4b: RDP — firewall-contained (no bind-pin available; this is the chosen posture)

**Reality on this host (verified):** `grdctl` exposes `set-port` but **no address/
interface bind** option — gnome-remote-desktop cannot be pinned to the Tailscale IP at
the service level. Therefore RDP containment is the **Task 3 firewall's** job, and that
is sufficient: with default-deny inbound + allow-on-`tailscale0`, port 3389 is reachable
only over Tailscale even though it still *listens* on `*:3389`. There is no honest
bind-pin to apply here, so do NOT invent one.

- [ ] **Step 1: Confirm RDP is firewall-contained (not bind-contained)**

```bash
ss -tlnp | grep ':3389'        # still shows *:3389 — listening broadly, by design
```
Expected: `*:3389` (unchanged). The containment is the firewall, not the bind. Verify it:
from a NON-tailnet LAN device (Tailscale OFF):
```bash
nc -vz -w 3 192.168.40.135 3389
```
Expected: **timeout / refused** (firewall blocks it). Over Tailscale, an RDP client to
`100.72.231.116:3389` still connects.

- [ ] **Step 2: Record the chosen posture (no change, no rollback needed)**

Note in the ledger working notes: "RDP left listening on `*:3389` by necessity
(`grdctl` has no address bind); contained by the Rail 1 firewall (tailscale0-only). If
a future gnome-remote-desktop adds an address bind, pin it then." This is an honest
recorded limitation, not a silent gap. (Stronger alternative if you ever want it:
disable RDP entirely with `grdctl rdp disable` when not in active use — but you use it,
so we keep it firewall-contained.)

---

## Task 5: Witness + record the final posture

**Goal:** Prove the perimeter changed, the organs are undisturbed, and update the
build ledger so the Rail 1 row reflects reality.

- [ ] **Step 1: Diff listeners before/after**

```bash
ss -tlnp | sort > /tmp/rail1-listeners-after.txt
diff /tmp/rail1-listeners-before.txt /tmp/rail1-listeners-after.txt
```
Expected: the only difference is SSH (22) moving from `0.0.0.0` to `100.72.231.116`
(if Task 4a done); RDP (3389) **stays** `*:3389` (firewall-contained, per 4b); and
NOTHING changed on the `11435/11436/11437/8080/8081` organ ports.

- [ ] **Step 2: Confirm organs green (regression check)**

```bash
ss -tlnp | grep -E ':(11435|11436|11437|8080|8081)\b'
systemctl --user is-active maez.service maez-web.service
```
Expected: all organ ports still `127.0.0.1`; both services `active`. (Maez's body kept
working through the hardening.)

- [ ] **Step 3: Confirm the firewall posture persists across reboot intent**

```bash
sudo ufw status verbose | head -5
systemctl is-enabled ufw
```
Expected: `Status: active`, default deny incoming, `ufw enabled` (survives reboot).

- [ ] **Step 4: Update the build ledger Rail 1 row**

Edit `docs/MAEZ_BUILD_LEDGER.md`: move the Rail 1 / "Host inbound doors" item to
`LIVE_WITNESSED`, record the witness (the Step 1 diff + Step 2 organ-green), the
`last_verified_commit`, and `updated_by`. This is a docs-only commit:
```bash
git add docs/MAEZ_BUILD_LEDGER.md
git commit -m "$(printf 'docs(ledger): Rail 1 inbound perimeter LIVE_WITNESSED\n\nUFW default-deny inbound + tailscale0-only allow; SSH/RDP no longer street-facing; Maez organs undisturbed (loopback green). Witness: ss before/after diff.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

- [ ] **Step 5: Note residuals for Rail 3**

If Task 2 found password auth was on (now fixed) or Task 4b had to be deferred (no
`grdctl` bind option), jot those into the Rail 3 (containment) working notes so nothing
is silently dropped. Plaintext-secrets-at-rest remains Rail 3's job, not Rail 1's.

---

## Rollback quick-reference (if anything goes wrong at any point)

- **You lost your SSH shell:** wait ≤5 minutes — the staged `systemd-run` timer
  auto-reverts the last change (ufw disable / sshd restore). Then reconnect over
  Tailscale and re-diagnose.
- **Manually revert the firewall now:** `sudo ufw disable` (reopens everything).
- **List pending rollback timers:** `sudo systemctl list-timers | grep run-r`.
- **Cancel a rollback you no longer need:** `sudo systemctl stop <ROLLBACK_TIMER>`.
- **Revert an sshd drop-in:** `sudo rm /etc/ssh/sshd_config.d/10-rail1-keyonly.conf
  /etc/ssh/sshd_config.d/20-rail1-bind.conf && sudo systemctl restart ssh`.
- **At the physical console you can always recover** regardless of network state.

---

## Done-when

- `sudo ufw status verbose` → active, default deny incoming, allow on `lo` +
  `tailscale0`.
- SSH/RDP reachable over Tailscale (`100.72.231.116`), refused from non-tailnet LAN.
- Maez organs still loopback-bound and services active (no regression).
- (If Task 2 ran) `passwordauthentication no`.
- Ledger Rail 1 row = `LIVE_WITNESSED` with the before/after witness.
- The paused **memory-parity** decision may now resume (every door is a provably-you door).
