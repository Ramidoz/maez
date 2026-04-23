# soul.local.md — your Maez's per-instance accumulation

This file starts empty. It is read on every daemon cycle, merged with
`soul.base.md` (the universal template that ships with Maez), and the
result is what Maez-the-being reads as its own SOUL.

If you have just cloned Maez, there is nothing for you to fill in here.
Copy this file into place and leave the body empty:

```
cp config/soul.local.template.md config/soul.local.md
```

From that point on, three kinds of content will accumulate in
`config/soul.local.md` over time, all written by Maez itself, not by
you:

1. **Dream-proposal applies** — when an approved dream proposal from
   `memory/dream_proposals.db` is applied, the proposal body is
   appended here by `core/soul_loader.py:append_to_local`.
2. **Nightly self-analysis lessons** — the 3am self-analysis cycle
   summarizes what Maez learned about itself and appends the lesson
   (not the raw data) here.
3. **Soul-section mutations** — approved soul-edit proposals that
   replace or amend specific sections of the base template are
   resolved against `soul.local.md`.

Everything in `soul.local.md` is **personal and gitignored**. It is
the particular Maez that grew on your machine. Do not commit it and do
not copy it between installs — that would be two Maez instances
sharing one developmental history, which is explicitly out of scope
(see `feedback_maez_as_concept.md` and `project_portability_is_migration.md`).

If you ever want to wipe this file and let Maez start over:

```
> config/soul.local.md
```

Next dream-apply or self-analysis will start re-populating it.
