---
name: Feature / change proposal
about: You want Maez to do something it doesn't currently do
title: "feat: "
labels: enhancement
assignees: ''
---

<!--
Read before filing:
  - docs/ROADMAP.md (where the project is heading)
  - docs/MAEZ.md    (what Maez is + isn't)
  - docs/governance/BETA_ARCHITECTURE_DECISIONS.md (18 load-bearing decisions)
  - docs/covenant/for_oss_users.md (universal-vs-per-user framing)

Maez is opinionated. Some feature ideas are out of scope by design
(multi-tenant hosting, Windows, Docker packaging, screen-capture-by-
default). The doc set above names those up front. If your proposal
falls outside them, say why the framing should change instead of
starting with the implementation.
-->

## The thing you want

<!-- One or two sentences. What should Maez be able to do that it
currently can't? -->

## Why

<!-- Concrete motivating scenario. Which user? Which moment? What
does success look like after the change? -->

## How it fits

- Which subsystem would own it? (brain / safety / decision / cognition
  / actions / evolution / memory / routing / learning / self_dev / infra)
- Is this universal (ships with the repo, every Maez gets it) or
  per-user (a knob in `identity.yaml`)?
- Does it touch any of the 18 governance decisions? If yes, which
  and how?

## Alternatives considered

<!-- Briefly note what you rejected and why. "I also thought about X
but it would break invariant Y." -->

## Willing to contribute?

- [ ] I'd like to write this myself (opens a draft PR when ready)
- [ ] Happy to test it once someone else implements it
- [ ] Just raising it — no capacity to work on it
