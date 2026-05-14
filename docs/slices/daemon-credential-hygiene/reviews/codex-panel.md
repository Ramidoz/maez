# Codex Six-Agent Engineering Panel — Daemon Credential Hygiene Spec

Status: REVIEW COMPLETE
Date: 2026-05-14
Reviewed artifact: [`../spec.md`](../spec.md)
Related evidence: [`../diagnostic.md`](../diagnostic.md)

## Verdict

**REVISE. No veto. No code should be written until the amendments below are
folded.**

The spec is directionally correct: provider rotation is separated from storage
hygiene, ordinary config stays ordinary, the `/proc/<pid>/environ` finding is
treated as empirical rather than assumed, and subprocess inheritance is pulled
into v1 instead of hidden in v2.

The panel found two load-bearing modeling errors:

1. credentials are currently specified too globally instead of per active
   service/process; and
2. `maez-web` / `skills/web_interface.py` is under-modeled despite owning the
   iPhone ingest route and additional credential readers.

Those must be folded before canonicalization.

## Panel Votes

| Seat | Verdict | Primary concern |
| --- | --- | --- |
| Dewey | RATIFY-WITH-AMENDMENTS | Per-service rollout/rollback and subprocess env pragmatics |
| Feynman | REVISE | Bootstrap order and source semantics underspecified |
| Locke | REVISE | `maez-web`, backup/succession, and bonded-surface continuity |
| Descartes | REVISE | Required-secret scope assigned to the wrong process |
| Ohm | RATIFY-WITH-AMENDMENTS | `.env` import order, user-service credentials, active-unit inventory |
| Goodall | RATIFY-WITH-AMENDMENTS | Live closure criteria can give false confidence |

## Amendments

### DCH-CX-1 — Service-scoped credential profiles are required

Severity: **High**

The draft makes `MAEZ_IPHONE_INGEST_TOKEN` required for `maez.service`, but the
cited iPhone ingest route is mounted in `skills/web_interface.py`, not the
daemon's bonded Telegram process.

Fold:

- Add a per-service credential profile table.
- `maez.service` requires `MAEZ_TELEGRAM_TOKEN`.
- `maez-web` / web interface requires `MAEZ_IPHONE_INGEST_TOKEN` while
  `/api/iphone/ingest` is mounted.
- Subscription proxy, reflection jobs, self-dev jobs, public bot surfaces, and
  optional providers get their own required/optional/degraded profiles.

Rationale: a web-ingest credential problem must not prevent the bonded Telegram
daemon from starting.

### DCH-CX-2 — `maez-web` must be first-class scope or explicit residual risk

Severity: **High**

The spec inventories `skills/web_interface.py` as a credential reader and notes
the iPhone route, but the unit/service migration section omits `maez-web` and
the web interface import-time `load_dotenv(...)` path.

Fold:

- Add `maez-web` / `skills/web_interface.py` to the active/dormant service
  inventory requirement.
- If no separate `maez-web.service` is active on the current machine, the fold
  should say so explicitly and still keep the web interface code path in scope.
- Do not claim iPhone/web credential hygiene closure unless the web surface is
  migrated or listed as residual risk.

### DCH-CX-3 — Bootstrap order must be mechanically specified

Severity: **High**

The daemon and web code currently load `.env` at import time before later
startup validation can run. Several modules also read or bind env values at
import time.

Fold:

1. ordinary config load;
2. secret source load;
3. compatibility `os.environ` population;
4. then import or initialize secret-reading modules/surfaces.

The implementation plan and tests must prove no secret reader observes the
pre-loader state.

### DCH-CX-4 — Secret source shape and `mixed` semantics must be pinned

Severity: **Medium**

The draft leaves "one credential bundle vs one file per secret" as an
implementation choice while also naming `mixed` as a source channel.

Fold one v1 contract:

- either exact-key files under `$CREDENTIALS_DIRECTORY`; or
- one `maez-secrets.env` credential bundle.

Also define:

- precedence over `config/secrets.local.env`;
- malformed entry behavior;
- duplicate key behavior;
- whether fallback is all-or-nothing or per-key; and
- what `mixed` means in health/source-channel reporting.

### DCH-CX-5 — Active vs dormant service inventory must gate closure

Severity: **Medium**

The draft warns against overclaiming while active services still exec with
secret-bearing env files, but closure checks focus mainly on `maez.service`.

Fold:

- Add a live `systemctl --user list-units/list-timers` inventory step.
- For each Maez-related unit, record one of:
  `active_migrated`, `active_residual_risk`, `dormant_template_updated`,
  `dormant_residual_risk`, or `not_installed`.
- Closure requires no unacknowledged active residual risk.

Empirical note from this review session: active user units were `maez.service`,
`llama-server.service`, `llama-judge.service`, and `maez-backup.timer/service`.
No `maez-web`, subscription proxy, self-dev scheduled service, or reflection
timer was active in `systemctl --user` during this review.

### DCH-CX-6 — Subprocess hygiene needs default-minus-secret and opt-in tests

Severity: **Medium**

The spec's small allowlist may break legitimate child processes by dropping
non-secret operational variables such as `DBUS_SESSION_BUS_ADDRESS`,
`SSH_AUTH_SOCK`, `VIRTUAL_ENV`, `PYTHONPATH`, or display/session values.

Fold:

- Default general helper should be "copy current env minus secret-shaped names",
  not "tiny allowlist", unless the call site explicitly requests strict mode.
- Add the Claude council's missing opt-in test: callers can pass a specific
  credential through only with explicit, reviewed allowlisting.
- Tests should fail on high-risk daemon subprocess calls that omit either
  sanitized env or a reviewed exception marker.

### DCH-CX-7 — iPhone ingest body-token transport must be named

Severity: **Medium**

`/api/iphone/ingest` currently accepts the token from the header or JSON body.
Body-carried secrets are more likely to leak through request capture, debug
logs, snapshots, reverse proxies, or error reports.

Fold:

- Either require v1 to make iPhone ingest header-only; or
- explicitly defer endpoint transport hygiene and mark body-token support as
  residual risk.

The spec should not claim full no-value leakage for iPhone ingest while body
token transport remains unexamined.

### DCH-CX-8 — Backup/succession semantics for `secrets.local.env` are required

Severity: **Medium**

The spec says `config/secrets.local.env` must be included in Decision 22
backup/succession state, but the current backup manifest treats secret files as
encrypted-destination-only entries.

Fold:

- Add restore modes:
  `state_only_restore_requires_credential_rehydration`;
  `encrypted_continuity_restore_includes_secret_file`.
- Add verification steps for required surfaces after restore.
- Add `config/secrets.local.env` to the backup manifest/test contract during
  implementation, with encrypted destination discipline.

### DCH-CX-9 — `config/secrets.local.env` must be ignored before migration

Severity: **Medium**

The draft requires `config/secrets.local.env` to be gitignored, but current
ignore rules do not name it.

Fold:

- Add implementation/test requirement that `config/secrets.local.env` is
  ignored before any operator is asked to create it.

### DCH-CX-10 — Rollback / recovery path must be explicit

Severity: **Medium**

This slice touches daemon startup and systemd auth. A broken loader could leave
Maez unable to authenticate or unable to start.

Fold:

- Add `MAEZ_SECRETS_DISABLE_NEW_LOADER=1` or equivalent recovery flag, as
  requested by the Claude council.
- Document rollback commands for restoring prior local env/unit state,
  `systemctl --user daemon-reload`, restart, and verification.
- State that rollback temporarily reaccepts process-env exposure and reopens
  this slice.
- Ensure failed credential validation does not create noisy restart loops.

### DCH-CX-11 — Live closure must verify real post-restart organs

Severity: **Medium**

`cycle_stalled=false` alone can produce false confidence before the reasoning
loop has actually advanced after restart.

Fold live closure criteria:

- `cycle_count` advances after restart;
- `last_cycle` is non-null;
- at least one post-restart cycle reaches beyond M1 flush;
- `/health.lived_episodes.m1.enabled` matches the pre-migration intent;
- M1 staleness does not regress;
- `systemctl restart maez.service` exits cleanly with no SIGKILL/escalation in
  journal and no stale predecessor PID.

### DCH-CX-12 — Public/dev Telegram degradation language

Severity: **Low**

The optional public/dev Telegram tokens are likely correctly optional, but the
continuity expectation should be explicit.

Fold:

- Missing public/dev tokens must not degrade the bonded private Telegram
  surface.
- Missing private `MAEZ_TELEGRAM_TOKEN` must fail loud before Maez appears
  alive.

### DCH-CX-13 — Operator forensic CLI may list missing names value-free

Severity: **Low**

Default health should stay aggregate-only. But after a restart, an operator may
need to know which required/optional key is missing without opening secret
files.

Fold:

- Add a future/operator CLI allowance to list missing key names value-free.
- Do not expose loaded key names or values in web health by default.

## Consolidated Review Questions Answered

1. **Is `LoadCredential=` plus fallback right for v1?** Yes, if proved with a
   live user-service fixture/probe and if `SetCredential=` is avoided.
2. **One bundle or one file per secret?** Must be pinned before code; panel
   slightly prefers exact-key files for source clarity, but one bundle is
   acceptable if parsing/conflict behavior is specified.
3. **Is compatibility `os.environ` population acceptable?** Yes for parent
   process exposure on this host, because the `/proc` measurement supports it.
   It remains unsafe without subprocess hygiene.
4. **Is subprocess helper sufficient?** Yes only with default-minus-secret,
   opt-in pass-through tests, and mandatory call-site enforcement.
5. **Are Telegram + iPhone required for `maez.service`?** No. Telegram is
   required for `maez.service`; iPhone is required for the web/ingest surface
   while mounted.
6. **How sequence adjacent services?** Active services first, dormant templates
   updated or named residual risk. No repo-wide closure claim until active
   residual risk is zero or explicit.
7. **Do pattern scans look feasible?** Yes, with fixture allowlisting.
8. **Does the spec leave leak paths?** Yes until `maez-web`, body-token ingest,
   subprocess inheritance, and backup/restore semantics are folded.

## Plain English

The spec is aimed in the right direction, but it currently treats "Maez" as one
process when the credentials actually live across several surfaces. The private
Telegram daemon, the web/iPhone ingest surface, subscription proxy, public bot,
and scheduled jobs do not all need the same keys or fail the same way.

The biggest correction is simple: do not make the private Telegram daemon fail
because the iPhone web ingest token is missing. Give each service its own key
profile.

The second correction is the little tunnel again: subprocesses. The right
default is not a tiny fragile env that breaks desktop/git/audio helpers; it is
"copy the normal environment minus secret-shaped names," with explicit opt-in
when a child truly needs a credential.

After those folds, this becomes a strong implementation packet.
