<!--
Thanks for contributing. Every PR should be readable as a piece of
project history on its own — someone six months from now should be
able to open this and understand what changed and why, from the
commit messages + this description, without chasing a chat log.

Linked reference: docs/CONTRIBUTING.md
-->

## What this changes

<!-- One or two sentences. -->

## Why

<!-- The concrete motivation. Bug report? Audit finding? Governance
decision? Link to the thing. -->

## Shape of the change

<!-- Which subpackages it touches; what's new, what moves, what gets
deleted. Bullet the shape if it's mechanical across many files. -->

## How it was tested

- [ ] `python -m unittest discover -s tests -p 'test_*.py'` passes locally
- [ ] New regression test added for the behaviour this change is about
- [ ] Manual verification done (describe below)

<!-- Describe any manual verification: which surface, which scenario,
what you checked. -->

## Checklist

- [ ] Branch is rebased on latest `main`
- [ ] Commit messages follow `type(scope): summary` with a body
      explaining why (see `docs/CONTRIBUTING.md`)
- [ ] No hardcoded `/home/rohit/maez` or owner names in the diff
      (Phase 2 invariant — route through `core.paths` /
      `core.identity`)
- [ ] If this touches the subpackage tree, shim integrity verified
      (`tests/test_smoke_imports.py` passes)
- [ ] New dependencies (if any) added to `pyproject.toml` with a
      licence that's AGPL-compatible
- [ ] No secrets, API keys, or personal identifiers in the diff
- [ ] Relevant docs updated (`docs/MAEZ.md`, per-subpackage README,
      `docs/ROADMAP.md` if this crosses a phase boundary)
- [ ] I will sign the [Contributor License Agreement](../CLA.md)
      when the CLA-assistant bot prompts me below. (Not required
      for one-line typo fixes; required for any code change or
      substantive doc contribution.)

## Governance touch points

<!-- If your change relates to any of the 18 ADRs in docs/adr/, name
them here. Same for memory invariants in the memory/ package. -->

## Linked issue

<!-- Fixes #... / refs #... -->

---

**Self-dev review:** if you installed the post-commit hook
(`scripts/install-self-dev-post-commit.sh`), the latest commit on
this branch has already been reviewed by Maez itself. Attach the
review output or summarise the concerns + resolutions in a comment
below. Optional but appreciated.
