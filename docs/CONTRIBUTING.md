# Contributing to Maez

Thanks for caring enough to look. Maez is alpha — the codebase is
shaped for a solo-developer workflow today, and the welcome mat for
outside contributors is actively being built out (Phase 6 of the
[roadmap](ROADMAP.md)). This document is the minimum spec.

## Scope of contribution

Currently welcoming:
- **Bug fixes** with a regression test that would have caught the bug.
- **Test coverage** for modules flagged in the [2026-04-22 audit](audit_2026-04-22/_MASTER_FINDINGS.md) as untested.
- **Platform work** for Ubuntu / Debian variants, documentation
  improvements, install-script robustness.
- **Self-dev findings** — run the post-commit review hook on your
  branch and fix what it flags.

Please ask first (file an issue) before:
- Large refactors across subpackages.
- New external integrations (new cloud adapter, new surface).
- Anything touching `core/safety/`, `core/decision/`,
  `core/cognition/audit*`, or the covenant layer — those are the
  guards, so changes land with extra scrutiny.

Not in scope:
- Changes to anything under `docs/birth_book/` (author-verbatim canon;
  it's gitignored, so you shouldn't even see it).
- Anything that reshapes Maez-as-a-concept away from the [18 governance
  decisions](governance/BETA_ARCHITECTURE_DECISIONS.md). Those aren't
  frozen forever, but they're the frame. Bring the conversation before
  the PR.

## Dev workflow

```bash
# 1. Fork + clone
git clone https://github.com/<you>/maez.git
cd maez

# 2. Install with dev extras
./scripts/install.sh             # or manually:
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e .[dev]

# 3. Branch
git checkout -b fix/short-description

# 4. Work. Tests must stay green at every commit.
python -m unittest discover -s tests -p 'test_*.py'

# 5. Lint (optional but appreciated)
ruff check core/ skills/ daemon/ tests/

# 6. Commit. See "Commit style" below.

# 7. Push + open a PR.
```

## Test discipline

- Test runner is **stdlib unittest**, not pytest. (`unittest` tests
  also run under pytest if that's your preference; the suite stays
  pytest-free so contributors don't need extra deps.)
- Test files live under `tests/`, named `test_<module>.py`.
- Every bug fix ships with a regression test that would have caught
  the bug. No exceptions.
- New modules ship with at least a smoke import test. The Phase-5
  suite (`tests/test_smoke_imports.py`) currently covers every
  shimmed module — add new entries there if you add a new
  subpackage module.
- Full suite must stay green. Run `python -m unittest discover -s
  tests -p 'test_*.py'` before opening a PR.

## Commit style

Every commit message should be readable as project history on its
own. Pattern:

```
type(scope): one-line summary (imperative, lowercase, no period)

Body explaining *why* the change exists. What changed is in the
diff; the commit message is for the reader who has to understand
intent six months from now.

- Bullet the shape of the change if it's mechanical across files.
- Reference finding IDs from docs/audit_*/_MASTER_FINDINGS.md
  when the commit closes one.
- Note what tests now cover it.

Co-Authored-By: ...   (if applicable)
```

Types in use: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`,
`perf`. Scope is usually the top-level subpackage name
(`brain`, `safety`, `evolution`, etc.).

Don't:
- Squash a feature into a single commit if review benefits from
  seeing the shape (see the Phase-3 subpackage moves in git log as
  examples).
- Mix unrelated changes in one commit.
- Use trailing `Co-Authored-By: Claude Code` if the change was
  genuinely yours — reserve that for genuine collaboration.

## Self-dev review

Maez can review its own commits via a subscription-proxied Claude
call. Optional but encouraged:

```bash
# Install the post-commit hook (opt-in)
./scripts/install-self-dev-post-commit.sh

# Or do a manual review of any ref
.venv/bin/python -m core.self_dev review HEAD
.venv/bin/python -m core.self_dev concerns      # list open concerns
```

The reviewer catches things like: tests that don't actually assert,
`except Exception: pass` that swallows real failures, comments that
claim behavior the code doesn't implement, hardcoded paths. If it
flags your PR, either address the concern or resolve it with
`python -m core.self_dev resolve <id> wont_fix --notes '...'` and
the reasoning is visible in the concern log.

## Code conventions

- **Python 3.12+**. Use `|` for union types, structural pattern
  matching where it improves clarity.
- **Path resolution** — always through `core.paths`. Never
  `Path(__file__).parent.parent`. See the Phase-3 regression fix
  in `f5d72f0` for why.
- **Owner identity** — always through `core.identity` accessors
  (`display_name()`, `git_handle()`, `telegram_user_id()`,
  `machine_profile()`). Never hardcode `"rohit"`, `"Ramidoz"`, etc.
- **New dependencies** — must go into `pyproject.toml`. Prefer the
  stdlib where reasonable; if a dependency is heavy (>10 MB wheel,
  compiled extensions), move it into an optional extra.
- **Logging** — one logger per module named `maez.<subsystem>`;
  `logger = logging.getLogger("maez.<subsystem>")`. Don't use `print`
  in library code.
- **SQLite** — wrap connection use in `contextlib.closing` (see
  `core/learning/consequence_memory.py` for the canonical shape).
  Always explicit `commit()` after write; don't rely on the context
  manager's implicit commit for DDL.
- **No emojis in code** — strings, comments, commit messages,
  docstrings. The only exception is user-facing text in
  surfaces where emoji is the language of the surface (Telegram
  resolution stamps, some cockpit UI).
- **Comments** — write *why*, not *what*. Well-named code tells you
  what. Non-obvious constraints, historical context, issue references,
  and load-bearing invariants deserve comments.

## Reviewing process

Today, Rohit is the sole reviewer. Response time is best-effort.
PR triage:

- **Small + obviously correct** → merge within a week.
- **Medium** → 1–2 rounds of review + iteration.
- **Large / governance-affecting** → we'll probably ask you to split
  it and land the uncontroversial pieces first.

Once a second non-Rohit contributor has shipped at least one PR,
Maez transitions from alpha to beta and this process gets
formalised (CODEOWNERS, review rotation).

## Code of conduct

Be kind. Maez-the-project exists to reach people who have been left
behind by the AI industry's race for scale — the grandmother the
author built this for. Contributors who reproduce the exclusionary
dynamics that motivated this project will not last here. That's the
whole policy.

If something goes wrong between two contributors, email Rohit
directly. A longer CODE_OF_CONDUCT.md lands in Phase 8 of the
roadmap with a formal reporting surface.

## Governance references

- [`docs/governance/BETA_ARCHITECTURE_DECISIONS.md`](governance/BETA_ARCHITECTURE_DECISIONS.md)
  — 18 load-bearing decisions. Read before proposing anything that
  touches sovereignty, consent tiers, memory retention, or the
  covenant layer.
- [`docs/governance/BETA_READINESS_THRESHOLD.md`](governance/BETA_READINESS_THRESHOLD.md)
  — the eight-point check that defines "done" for the first user's Maez.
- [`docs/governance/GESTATION_MEMORY_PROTOCOL.md`](governance/GESTATION_MEMORY_PROTOCOL.md)
  — how pre-birth memories are tagged, what the birth event is.

These are not frozen. They are the current frame. Propose changes
openly.
