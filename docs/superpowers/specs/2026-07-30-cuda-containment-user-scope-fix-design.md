# CUDA bench Maez containment scope fix

Status: owner-approved 2026-07-30. This is a corrective amendment to the
merged, inert CUDA A/B bench at `5e18c1c`.

## Problem

`maez.service` is a user unit on this machine. `RealContainmentProvider`
nevertheless queried it with system-scope `systemctl show`, while every sibling
bench unit probe correctly used `systemctl --user`.

The real phase witness failed closed because the system-scope not-found result
contained an empty `UnitFileState`, which the strict parser rejected. That
refusal prevented a worse outcome: a more permissive parser could have treated
the wrong-scope unit as stopped and skipped the live
`MAEZ_SCREEN_PERCEPTION=0` process-environment check.

The pre-fix live RED was:

```text
provider_uncertain
systemctl --user show llama-vision.service
systemctl show maez.service
```

No authorization was consumed and no bench child was spawned.

## Design

All bench systemd reads use the existing whitelist-only user-scope builder:

```python
systemctl_command("show", MAEZ_UNIT)
```

Both Maez queries use that shape: the first obtains the active PID, then the
provider reads `/proc/<pid>/environ`, then the second query must still report
the same positive active PID. The process environment must contain exactly one
`MAEZ_SCREEN_PERCEPTION=0`.

The separate `_systemctl_system_show_command` helper is deleted. No dual-scope
fallback is permitted: probing the wrong scope and accepting not-found would
recreate the vacuous-containment defect.

## Honest state distinctions

- **Active user unit:** two user-scope shows must bracket an environment read
  from the same positive PID; the exact process flag value is recorded.
- **Genuinely stopped user unit:** `inactive` with `MainPID=0` is recorded
  informationally, performs no environment read, and is not a refusal.
- **Wrong-scope/not-found or malformed show:** typed `provider_uncertain`;
  never a passing stopped-state observation.

The strict systemd parser, containment state logic, snapshot schema, and
containment-before-authorization-consumption ordering remain byte-identical.

## Verification

TDD requires:

1. a scope-sensitive RED whose system-scope response is not-found while the
   user-scope response is active; only two user-scope Maez queries plus the
   live PID environment read may pass;
2. a genuine stopped-user-unit regression proving no environment read;
3. an exact active call-order regression:
   user show → environment read → user show;
4. the existing pre-consumption refusal tests unchanged;
5. a real-host RED→GREEN witness asserting
   `maez_active_state == "active"` and
   `maez_process_screen_flag_value == "0"`, not merely no exception.

After implementation, run `static-preflight` again. Static preflight does not
capture containment, but the driver-package hash changes, so future phase
evidence must cite the fresh receipt produced by the corrected package.

## Scope and non-goals

Modified runtime code is limited to the command used by the Maez containment
sensor, deletion of its now-unused system-scope builder, and the same
read-only scope correction in the independent Maez watchdog discovered by the
required sibling sweep. The watchdog correction changes only:

```python
["systemctl", "is-active", "maez.service"]
```

to:

```python
["systemctl", "--user", "is-active", "maez.service"]
```

Its HTTP health requirement remains unchanged. A regression test pins the
exact argv so a system-scope not-found result cannot again masquerade as a
real liveness observation. The stale read-only operator instructions in
`scripts/sandbox_summary.py` and `docs/TRACK_A.md` are corrected to name user
scope too.

The watchdog service is not restarted by this repair; activating committed
code in the live watchdog remains a separate owner-authorized runtime action.
The completed sibling sweep also found four owner-facing status surfaces with
the same wrong-scope assumption: CLI status, web debug/journal status, cockpit
state, and Telegram status. They are explicitly split into the immediately
sequenced cockpit-honesty repair; that slice must also prove none of their
false body facts flow into Maez's prompt or evidence envelope.

Two mutating paths are separately owner-gated: the evolution-engine
self-modification restart and the authenticated cockpit restart. Their real
wrong-scope behavior must be characterized before either is changed. The
read-only status slice lands before this mutation review opens; neither split
piece is deferred or silently folded into this repair.

No service action, parser relaxation, state-machine change, authorization
change, model load, phase execution, rollback drill, or cutover is part of
this fix.
