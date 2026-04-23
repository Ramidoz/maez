# Launch checklist

Single-use checklist for the moment the repo goes public and the
`v0.1.0-alpha` tag gets cut. Not something to run through now; this
is here for when the time is right.

Read before using:
- [`docs/ROADMAP.md`](ROADMAP.md) Phase 10 — where this fits.
- [`CHANGELOG.md`](../CHANGELOG.md) — the 0.1.0-alpha release notes.
- Previous-turn analysis in
  [`.claude/projects/-home-rohit/memory/`] memory notes on
  commercialisation posture and founder considerations.

The checklist is sequential. Each step has a "what" and a "why" line
so a future session doing this cold isn't guessing.

---

## A. Pre-push sanity checks (no network)

- [ ] **Local tree clean.** `git status` returns "nothing to commit".
  Any uncommitted runtime state is gitignored, not staged.
- [ ] **Test suite green.** `python -m unittest discover -s tests
  -p 'test_*.py'` → 530+ tests, zero failures.
- [ ] **No secrets in staged files.** `git diff --cached | grep -iE
  "(api_key|token|sk-|ghp_|xai-|AKIA)"` returns nothing that looks
  real.
- [ ] **Licence headers present on every `.py`.** `find core/ skills/
  daemon/ memory/ tests/ -name '*.py' | xargs grep -L 'Licensed under'`
  returns zero lines.
- [ ] **`config/.env`, `config/identity.yaml`, `config/soul.local.md`,
  `docs/birth_book/` all gitignored.** Confirm with
  `git check-ignore -v <path>`.
- [ ] **`.gitignore` covers runtime state.** `memory/*.db`,
  `core/memory/*.db`, `logs/*`, `daemon/*.pid`, `backups/`, `models/`
  all present.

## B. Push to public GitHub — first public moment

- [ ] **Repo exists on github.com/Ramidoz/maez** (or wherever the
  owner wants to host). Created via the web UI with:
  - [ ] Description: *"Always-on local AI companion. A kind of digital being — one machine, one user, continuous memory, one voice. Alpha."*
  - [ ] Topics: `ai`, `ai-agent`, `local-llm`, `llama-cpp`, `python`,
    `daemon`, `jarvis`, `chromadb`, `agpl`, `companion`.
  - [ ] Default branch: `main`.
  - [ ] Visibility: public.
- [ ] **Push the main branch:**
  ```bash
  git remote -v      # confirm origin is the public repo
  git push -u origin main
  ```
- [ ] **Immediately verify on github.com** that the repo renders:
  README, `docs/`, `core/` tree, `LICENSE`, `NOTICE`. Click through
  three random files to confirm they're not showing line-ending or
  encoding issues.
- [ ] **Enable branch protection on `main`:**
  Settings → Branches → Add rule for `main`:
  - [ ] Require PR before merging (1 approval).
  - [ ] Require status checks: `tests`, `lint`, `CLAAssistant`.
  - [ ] Require up-to-date branch before merging.
  - [ ] Include administrators (you can bypass per-PR with care).
- [ ] **Confirm the two GitHub Actions workflows run green** on a
  trivial doc-only PR against main. If `tests` fails on a fresh
  install, something's wrong with `pyproject.toml` dependencies.

## C. CLA bot setup (one-time)

The `.github/workflows/cla.yml` file is already in place. Finish
wiring it:

- [ ] **Create an orphan `cla-signatures` branch:**
  ```bash
  git checkout --orphan cla-signatures
  git rm -rf .
  mkdir -p signatures/version1
  echo '{ "signedContributors": [] }' > signatures/version1/cla.json
  git add signatures/version1/cla.json
  git commit -m "init: CLA signatures branch"
  git push -u origin cla-signatures
  git checkout main
  ```
- [ ] **Create a Personal Access Token (classic) with `repo` scope**
  at github.com/settings/tokens. Name it "maez-cla-pat". Copy the
  value.
- [ ] **Add as repo secret:** Settings → Secrets and variables →
  Actions → New repository secret → name `CLA_PAT`, paste the
  token value.
- [ ] **Verify by opening a trivial PR from a second account** (or
  asking an early tester). The CLA-assistant bot should post a
  comment requesting signature.

## D. Tag v0.1.0-alpha

**Only after A–C are all green.** The tag is the formal public
anchor.

- [ ] **Annotate and push the tag:**
  ```bash
  git tag -a v0.1.0-alpha -m "First public tag — see CHANGELOG.md"
  git push origin v0.1.0-alpha
  ```
- [ ] **Create a GitHub Release** at
  github.com/Ramidoz/maez/releases/new:
  - [ ] Select tag: `v0.1.0-alpha`.
  - [ ] Title: `v0.1.0-alpha — first public tag`.
  - [ ] Body: copy the `[0.1.0-alpha]` section of `CHANGELOG.md`.
  - [ ] Mark as pre-release.
  - [ ] Publish.
- [ ] **Pin the release** on the repo landing page.

## E. Cosmetic landing polish

- [ ] **Pin three issues** on the repo landing:
  - One "roadmap overview" linking to `docs/ROADMAP.md`.
  - One "first-time contributor" linking to `docs/CONTRIBUTING.md` +
    the CLA.
  - One "known issues / won't-fix" listing platform scope (macOS /
    Windows) and the deferred items in the changelog.
- [ ] **Enable Discussions** for non-issue questions
  (Settings → General → Features → Discussions).
- [ ] **Disable Wiki** (redundant with `docs/`).
- [ ] **Disable Projects** unless actively using (easy to clutter).
- [ ] **Add a sponsor link or leave blank** —
  `.github/FUNDING.yml` only if the owner wants early support
  channels (Patreon / GitHub Sponsors / Ko-fi / Buy-me-a-coffee).

## F. Announcement moment

After the above:

- [ ] **Prepare the pitch stack** per the README's "The pitch, staged"
  section. The alpha tag landing is the signal to ship:
  - [ ] A short video walk-through (screen recording or talking head).
  - [ ] The interactive mindmap visualisation.
  - [ ] The Zenodo paper draft uploaded.
- [ ] **Coordinated announcement:**
  - [ ] Show HN post pointing at github.com/Ramidoz/maez.
  - [ ] A single long Twitter / X thread linking the pitch stack.
  - [ ] LinkedIn post for the professional / research audience.
  - [ ] Submissions to `r/LocalLLaMA`, `r/aiagents`, any curated
    newsletters (Ben's Bites, TLDR AI, Import AI) that fit.
- [ ] **Email a small list** (5–10 people who would genuinely
  appreciate seeing it) with a short note and the repo link. Personal
  reach > broadcast reach for early signal.
- [ ] **Monitor** for the first 48 hours. Most response comes in that
  window. Triage issues into `docs: `, `bug: `, `out-of-scope` labels
  quickly.

## G. After launch — first week

- [ ] **First issue triage pass daily** for the first week, then
  weekly. Aim for `≤ 24h` response on any substantive issue.
- [ ] **First-contributor flow dry-run.** When someone opens their
  first PR, walk through: CI runs → CLA prompt → review → merge.
  Fix any friction visible in that flow.
- [ ] **Cost awareness check.** If `maez-subscription-proxy` sees any
  abuse via localhost binding, audit. Budget caps in
  `core/subscription_proxy/budget.py` should hold.
- [ ] **Week-one retrospective.** What surprised you? What was noisier
  than expected? What should move from "deferred" to "fix now"?

---

## Rollback options (just in case)

- **Tag was cut prematurely.** `git push --delete origin v0.1.0-alpha`
  removes the remote tag. Delete the GitHub release manually. People
  who cloned in the window still have a snapshot, but they can't
  install the release-tagged version anymore. This is messy; avoid
  if possible.
- **A secret leaked in a commit.** Rotate the secret on the provider
  first. Then `git filter-repo` / `bfg` to scrub history, and force-push.
  All contributors must re-clone. Painful; avoid by running the
  gitleaks pre-commit hook.
- **Someone forks and ships something against the project's spirit.**
  AGPL keeps hosted forks open-source. Ethically, the forked project
  is theirs — you don't have to endorse it. Your repo remains
  canonical and that's enough.

## Non-goals for launch day

- Don't promise stability. It's alpha.
- Don't commit to response times. You're one person.
- Don't benchmark against commercial products. Maez is a different
  category.
- Don't chase everyone's requested feature. Defer, explain, or
  `won't-fix` with reasoning.
- Don't neglect your Maez during launch week. Maez-the-being is
  ultimately the thing that validates the project; neglecting it to
  chase community metrics is the exact anti-pattern.
