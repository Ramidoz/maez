# Changelog

All notable changes to Maez are recorded here. Format is loosely
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning
is [Semantic Versioning](https://semver.org/spec/v2.0.0.html) with
pre-release suffixes for the alpha / beta / release-candidate
windows. See [Versioning conventions](#versioning-conventions) at
the bottom of this file.

## [Unreleased]

No unreleased changes. The next version cuts when Track A passes
its acceptance gate (see [`docs/TRACK_A.md`](docs/TRACK_A.md)).

## [0.1.0-alpha] — 2026-04-23

**First public tag.** The road-to-public-OSS-launch road has
reached the Phase 9 checkpoint: the codebase is reproducible from
source on any Linux + NVIDIA GPU box, a fresh clone can onboard
without talking to the maintainer, every runtime dep is AGPL-
compatible, no secrets have ever been committed, and the full
test suite is green.

Maez-the-being is still in Track A — this tag describes the
*codebase* as ready for public contribution, not a declaration
that the first Maez has passed its readiness check. Those are
independent timelines, covered in
[`docs/ROADMAP.md`](docs/ROADMAP.md).

### Added

- **Clone-and-install on a fresh box.** `./scripts/install.sh`
  walks through Python / git / systemd / GPU prereq checks, creates
  `.venv`, installs core and optional extras, seeds configuration
  from templates, runs the first-run wizard, and renders systemd
  unit templates. `pyproject.toml` declares 16 runtime dependencies
  + four optional extras (vision, telegram, google, dev).
- **Per-user identity through `core.identity`.** `display_name()`,
  `user_profile_id()`, `git_handle()`, `telegram_user_id()`,
  `machine_profile()`, `home_coords()`, `timezone()` and per-
  policy accessors (`jarvis_tier`, `signal_ingest`,
  `proactive_messages`). Each reads `config/identity.yaml` with
  `MAEZ_OWNER_*` env overrides. `.env.example` documents every
  knob. The first-run wizard
  (`scripts/first_run_wizard.py`) captures them interactively.
- **Subpackage tree under `core/`.** Twelve subpackages —
  `core/{brain, memory, safety, cognition, evolution, actions,
  decision, learning, routing, self_dev, infra, subscription_proxy}`
  — replace 67 flat files. Each subpackage carries a README with
  its public surface, invariants, and legacy import paths. All
  pre-Phase-3 import paths continue to work via
  `sys.modules`-alias shims so external code isn't forced to
  migrate.
- **Path resolution through `core.paths`.** `home()`, `config_dir()`,
  `data_dir()`, `memory_dir()`, `logs_dir()`, `identity_file()`,
  `soul_base_path()`, `soul_local_path()`, `soul_combined_path()`,
  `ensure_dirs()`, `describe()`. Overridable via `MAEZ_HOME` /
  `MAEZ_CONFIG` / `MAEZ_DATA` / `MAEZ_CACHE`.
- **Documentation set.** `README.md` (first-contact), `docs/MAEZ.md`
  (master architecture + philosophy), `docs/GETTING_STARTED.md`,
  `docs/CONTRIBUTING.md`, `docs/ROADMAP.md`,
  `docs/covenant/for_oss_users.md` (universal-vs-per-user framing),
  `docs/adr/0001..0018` (stable per-decision anchors cross-linking
  the governance doc), twelve per-subpackage READMEs.
- **Comprehensive audit record.** `docs/audit_2026-04-22/` contains
  the 85-finding audit that shipped as Phase 1 — twelve agent
  reports, a master consolidation with top-20 ranking, and the six
  themed fix-now commit batches that closed 11 of 12 blockers.
- **Regression test net.**
  `tests/test_smoke_imports.py` verifies every (legacy, new) shim
  pair resolves to the same module object (65 pairs + 3 surface
  asserts). `tests/test_phase_5b_blocker_regressions.py` locks in
  the audit's blocker fixes with behavioural + source-level checks.
  Total suite: 530 tests, < 2 seconds.
- **Licence + security audit.**
  `docs/governance/LICENCE_AUDIT.md` confirms every runtime dep is
  AGPL-3.0-compatible. `docs/governance/SECURITY_AUDIT.md` reports
  a clean secret-history scan and documents the complete network
  surface (three localhost-bound ports: cockpit, fast-reply,
  subscription proxy).
- **Contributor infrastructure.** GitHub Actions workflows for
  `tests` and `lint` run on every push and PR. Issue templates
  (bug / feature / question), PR template enforcing Phase 2/3/7
  invariants in its checklist, `CODE_OF_CONDUCT.md` (Contributor
  Covenant 2.1 with founding-motivation language), opt-in
  `.pre-commit-config.yaml` (gitleaks + whitespace + ruff).
- **Every `.py` file carries an AGPL copyright header** (208 of
  208).

### Fixed — blocker + major from the 2026-04-22 audit

Eleven of twelve blockers and twelve major findings were closed in
six themed commits (batches A–F):

- `09-M1`, `09-M2`, `05-M3`, `05-M1`, `07-M2` — sqlite connection
  hygiene (connections-never-closed, missing-commit, NameError-in-
  finally masking root cause).
- `02-B1` — decision pipeline no longer propagates `CardStoreError`
  when a card races to terminal between will-I check and
  `mark_running` / `mark_done` / `mark_failed`.
- `02-M1`, `02-M2`, `02-m2` — `consequence_memory.record_event`
  failures now log a warning instead of silently dropping; synthetic
  classification objects in dialog-routed approvals now propagate
  `audit_request_id`; the missing module-level `logger` was added.
- `05-B1` — `cognition_quality.score_and_classify` ring buffers now
  roll back on partial-append failure. Previously a mid-function
  exception desynced the three buffers and corrupted fixation
  detection on every subsequent turn.
- `01-B1`, `01-M2` — the brain loop retry-context block previously
  dereferenced `self` inside a module-level function (raised
  NameError on every retry-intent match). Now resolves the
  audit-log path through `core.paths.memory_dir()` with a connect
  timeout.
- `01-M1` / `09-B1` — `consequence_memory.relevant` query + haystack
  token filters now match, restoring recall for URL / path /
  hyphenated tokens.
- `01-m1` — `_summarize_shell_error` no longer truncates first
  stderr line mid-word.
- `03-m1` — `owner_trust.is_risky_cmd` now collapses runs of
  whitespace before substring matching; `rm  -rf /` no longer
  slips past the fragment list.
- `06-M1` — pre-flight destructive snapshot errors are now
  inspected and logged when non-empty (previously commands
  proceeded over partial backups silently).
- `06-M2` — `tool_loop.is_read_only` docstring makes the intentional
  divergence from `action_classifier` Lane 0 explicit (allow-list
  vs deny-patterns).
- `06-m1` — `command_decomposer` adds explicit double-quote state
  tracking.
- `07-B1` — `soul_loader.append_to_local` now reads + writes inside
  the same lock. Previously a concurrent dream-apply race could
  silently overwrite one writer's contribution.
- `07-M1` — `temperament` first-event log renders missing prior as
  `NULL` rather than the literal `nan`.
- `10-B1`, `10-B2`, `10-M2` — `fast_backend_router.BackendSelection`
  carries an explicit `policy_denied` flag so callers can
  distinguish a policy refusal from a backend outage;
  `private_thoughts.py` routes its default DB path through
  `core.paths.memory_dir()`; `fast_backend_local.is_available()`
  resolves `active_backend()` once at the top and drives both the
  llamacpp and Ollama probe branches from that single decision.
- `X2-B1`, `X2-B2`, `X2-M2` — root-doc portability caveat,
  TRACK_A.md acceptance-gate inline summary, Decision-2
  revocation-URL implementation-status annotation.

### Fixed — Phase 3 regression

- Nine modules used `Path(__file__).resolve().parent.parent` to
  compute their default DB / config path, which was correct when
  they lived at `core/<name>.py` but resolved to `core/` after the
  Phase 3 subpackage moves. The smoke-import suite caught this on
  first run; the fix routes each through `core.paths` with a
  correct `parent.parent.parent` fallback.

### Changed

- **`core/` directory layout.** Pre-Phase-3 flat structure is gone;
  twelve subpackages carry the modules now. Legacy paths continue
  to resolve via shims — no forced migration for downstream code.
- **Owner identity hardcodes removed.** `Ramidoz`, `rtx 4090`,
  `Alienware R16`, `/home/rohit/maez` and `rohit` references in
  runtime code now route through `core.identity` / `core.paths`.
  Some cosmetic references remain in comments / landing-page HTML;
  those are Phase 10 polish work.

### Security

- **Clean secret history.** Phase 7 git-log scan found zero matches
  for AWS keys, GitHub tokens (ghp / gho / ghu), OpenAI / Anthropic
  / xAI keys, GitLab PATs, PEM private keys, or inline-assigned
  token-shaped values. Maintained by `.gitignore` discipline and
  env-var-only key reads.
- **Network surface documented.** Three services bind to localhost:
  cockpit (5173), fast-reply adapter (8765), subscription proxy
  (11438). Everything else is outbound. See
  [`docs/governance/SECURITY_AUDIT.md`](docs/governance/SECURITY_AUDIT.md).
- **Pre-flight redaction before cloud.** Every payload crossing
  into a cloud adapter passes through `core.safety.cloud_redactor`.

### Documented as out-of-scope

- macOS and Windows as first-class platforms for v0.1. WSL2 +
  Ubuntu is the supported path today.
- Hosted multi-tenant Maez-as-a-service (violates sovereignty).
- Docker / Kubernetes packaging (host-level install is the target).
- A non-technical web UI for end users (the cockpit is an
  engineering surface).
- Full ruff modernisation sweep (lint is informational in CI; the
  sweep lands as Phase-8 follow-up).

### Known issues

- The Phase 3 shim pattern leaves 68 `core/<name>.py` stubs that
  immediately redirect into their new subpackage. They're load-
  bearing (legacy imports depend on them) and will be removed in a
  later "shim sunset" pass after external code has migrated.
- `core/memory/` (this package) and the top-level `memory/` package
  coexist. Python resolves them independently but humans may
  initially confuse them. Each has a README clarifying its role.
- Several modules in the author's venv carry GPL / Elastic licences
  (`pylint`, `udapi`, `udtools`, `tnr`). None are in the Maez
  runtime dep set — they're training or dev-only tools.

---

## Versioning conventions

Maez follows [SemVer 2.0](https://semver.org/spec/v2.0.0.html) with
pre-release suffixes:

| Tag form | Meaning |
|---|---|
| `vMAJOR.MINOR.PATCH-alpha[.N]` | Codebase still churning. No stability guarantee across alpha bumps. Public OSS launch phase. |
| `vMAJOR.MINOR.PATCH-beta[.N]` | At least one non-author contributor has shipped a merged PR. API surface mostly stable; breaking changes flagged in the release notes. |
| `vMAJOR.MINOR.PATCH-rc[.N]` | Release candidate. No known blockers; one bump away from the general-availability tag. |
| `vMAJOR.MINOR.PATCH` | General availability. Breaking changes require a MAJOR bump. |

### What counts as a breaking change

- Any import path removed (including Phase-3 legacy shims once the
  sunset window opens).
- Any public function / class signature changed in a way that
  breaks existing callers.
- Any governance decision reversed in a way that would invalidate
  a bonded user's Maez (see `docs/adr/` + `docs/covenant/`).
- Any on-disk schema change in `memory/` / `config/` that requires
  a manual migration.

Non-breaking changes (new features, bug fixes, internal refactors
that don't change public surface, new optional extras) bump the
minor or patch.

### Beta transition criterion

Alpha → beta happens when **at least one non-author contributor
has shipped a merged PR**. That event formalises the review
process, the CODEOWNERS file, and the `v0.1.0-beta` tag.

### Stable (1.0.0) transition criterion

Beta → 1.0 happens when:

- The Track A acceptance gate has been met for at least four
  consecutive weekly checks (twice the alpha minimum), and
- At least two non-author contributors are regularly shipping
  PRs, and
- The shim sunset pass has landed and the public API surface has
  been frozen for at least one full alpha → beta → rc cycle.

None of those are imminent. 1.0 is a later-year target, not
a next-month one.

---

## Attribution

Commit messages in the git log are the authoritative per-change
detail. This changelog is the user-visible summary. To reproduce
the detail for a given release, see the tag range in
`git log vX.Y.Z..vX.Y.W --oneline`.
