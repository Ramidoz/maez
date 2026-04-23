# core/self_dev

Maez reviewing its own code. A subscription-proxied Claude call
reviews every commit (opt-in) or a queued module each night, logs
concerns to a sqlite sidecar, and surfaces them through the cockpit
or the CLI.

| Module | Role |
|---|---|
| [`__init__.py`](__init__.py) | The package entry. Exposes `review(git_ref)`, `review_module(path)`, `propose_tests(path)` and the CLI argparser. |
| [`__main__.py`](__main__.py) | CLI dispatcher — `python -m core.self_dev {review, review-module, propose-tests, history, concerns, resolve, stats}`. |
| [`hooks.py`](hooks.py) | Post-commit policy + orchestrator. `decide(sha)` says whether to fire a review (diff size, budget, Claude tier health). `run_post_commit(sha)` disowns the review into the background. |
| [`persistence.py`](persistence.py) | SQLite sidecar: reviews, concerns, state transitions. Concern lifecycle: `open → resolved | wont_fix | rejected`. |
| [`scheduler.py`](scheduler.py) | Idle-time scheduled review — `python -m core.self_dev_scheduler run` pick-one-module-and-review. Paired with the systemd timer. |
| [`workshop.py`](workshop.py) | In-cockpit agentic-coding surface. Per-session model picker, @-mentions for file refs, unified-diff render + apply. |

## Install (opt-in)

Nothing here runs automatically unless you install the post-commit hook:

```bash
./scripts/install-self-dev-post-commit.sh
```

Or the scheduled review timer:

```bash
systemctl --user enable --now maez-self-dev-scheduled.timer
```

Both are fail-closed — if the subscription proxy is down, the
budget is saturated, or the diff is empty, the review skips rather
than blocks the commit.

## Budget defaults

Per-adapter caps live in `core/subscription_proxy/`. Defaults:

| Adapter | Hourly | Daily |
|---|---:|---:|
| Claude (subscription) | 10 | 30 |
| Gemini (subscription) | 10 | 30 |
| OpenRouter / OpenAI / xAI / Ollama Cloud (paid API) | 30 | 100 |

Override with `MAEZ_<ADAPTER>_HOURLY_CAP` / `_DAILY_CAP` env vars.

## Hook policy gates

The hook skips review if any of:

- SHA unresolves
- Significant diff == 0 (empty or lockfile-only)
- Significant diff > `MAEZ_SELF_DEV_MAX_AUTO_DIFF_CHARS` (default 80 000)
- Proxy unreachable
- Claude hourly remaining < `MAEZ_SELF_DEV_HOURLY_FLOOR` (default 3)
- Claude daily remaining < `MAEZ_SELF_DEV_DAILY_FLOOR` (default 5)

All gates can be inspected with `python -m core.self_dev_hooks decide <sha>`.

## CLI

```bash
python -m core.self_dev review HEAD~1..HEAD    # review a range
python -m core.self_dev history                 # recent reviews
python -m core.self_dev concerns --status open  # filterable
python -m core.self_dev resolve 42 resolved --notes "fixed in a63..."
python -m core.self_dev stats                   # aggregate usage
```

## Invariants

- **Never auto-fix.** The reviewer only flags concerns; the author
  decides what to do. Auto-fixers are a Workshop feature, not a
  self-dev feature, and they always go through a card.
- **Concerns are durable.** A `wont_fix` resolution with notes is a
  permanent record — the reasoning stays in the db. Don't mark
  things resolved that weren't actually fixed.
- **Fail-closed on proxy outages.** A crashed subscription proxy
  never blocks a commit or a cycle — reviews silently skip.

## Public surface

- `review(git_ref, persist=True) -> ReviewResult`
- `review_module(path) -> ReviewResult`
- `propose_tests(path, write=False, force=False) -> ProposalResult`
- `hooks.decide(sha) -> PolicyDecision`
- `hooks.run_post_commit(sha) -> int` — disowned subprocess entry
- `persistence.store_review(...)`, `.list_reviews(limit)`, `.list_concerns(...)`, `.set_concern_status(id, state, notes)`, `.stats(...)`

## Legacy import paths

`core.self_dev_hooks`, `core.self_dev_persistence`, `core.self_dev_scheduler`,
`core.workshop` are shims. The package itself lives at `core.self_dev`
directly (the pre-Phase-3 `core/self_dev.py` became `core/self_dev/__init__.py`).
