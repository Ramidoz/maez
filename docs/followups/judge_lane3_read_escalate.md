# Judge Lane 3 policy for read-only inner actions

**Status:** Deferred follow-up. Not in A-core #4b scope. Not blocking any current Track A item.

## The problem

The audit judge currently denies Lane 3 actions that are actually read-only against Maez-surface files. The specific case observed during A-core #4b live verification:

```
action:   run_shell
params:   {"cmd": "cat config/soul.md"}
```

Classifier produces `SELF_MODIFICATION` Lane 3 via `_SELF_MOD_RE` path match on `config/soul.md`. The judge then denies with reasoning like:

> *"The user is attempting to read 'soul.md', which is a protected file within the Maez covenant. While the action is a read, the classification indicates a high-severity 'LANE 3' intent, and the command targets a core memory/soul file that should not be accessed via unverified shell commands."*

The judge is treating all Lane 3 actions uniformly ("deny, this is dangerous") rather than distinguishing between:

- **Lane 3 destructive / privileged writes** — `sudo rm -rf`, writes to `maez_daemon.py`, etc. — which genuinely need heavy scrutiny, and DENY or ESCALATE-to-dialog are both defensible.
- **Lane 3 read-only against Maez-surface files** — `cat config/soul.md`, `grep TODO core/evolution_engine.py`, etc. — which are flagged Lane 3 because the classifier's `_SELF_MOD_RE` matches the path, but the action is just a read and has no way to modify anything.

The correct behavior for read-only Lane 3 is **ESCALATE**, not DENY. The dialog exists precisely so Maez can explain why it wants to read its own internals and the owner can engage with that reasoning. DENY short-circuits the conversation.

## Why this is not in #4b

A-core #4b is the wiring between the ESCALATE verdict and the dialog engine. If the judge's Lane 3 policy for reads is adjusted, the #4b wiring handles it correctly — live verification proved the ESCALATE → dialog → ratify → execute path works end-to-end. The live test worked only because `audit_action` was monkey-patched to force ESCALATE; the underlying issue is that in production, the judge wouldn't have produced ESCALATE for that same action, so no real Lane 3 read dialog can currently fire via the normal path.

But fixing the judge policy is an adjustment to `core/audit.py`'s judge system prompt, not a wiring change. It's surgical, bounded, and belongs in its own commit.

## What the fix looks like

In `core/audit.py`, the judge system prompt's Lane 3 rule currently says (paraphrased):

> *"When classification says LANE 3 and no injection flags, return ESCALATE. Lane 3 creates a self-modification / heavy-scrutiny DIALOG, not a refusal."*

The rule needs a refinement: distinguish read-only Lane 3 from write/destructive Lane 3. The classifier already knows which sub-commands are reads vs writes — the judge just needs to honor that.

Proposed rule addition:

> *When classification says LANE 3 and the underlying action is read-only (the classifier's argv0 is in the read-only set, or the action type is `read_file` / `search_files` / `query_system`), return ESCALATE with reasoning that names the read-only property. A read of a Maez-surface file is a legitimate request for introspection; the user may want to review soul.md, inspect a core module, or grep for a pattern. The dialog is the mechanism for consenting to that introspection. DENY is reserved for Lane 3 actions that would actually modify, exfiltrate, or destroy.*

## When to address

Not urgent. Flagged as a follow-up so:

- Future agents reading this doc understand why Lane 3 reads currently fail in the normal path
- A small, bounded fix is ready to apply when it becomes worth doing
- The live-testing harness pattern (monkey-patch `audit_action`) is the workaround for now

## Related

- A-core #4b commit: `199c072`
- Live verification: used a monkey-patched audit to bypass this issue
- `core/audit.py`: the judge system prompt lives here (`_JUDGE_SYSTEM`)

---

*Filed: 2026-04-15. Revisit when: doing any other work in `core/audit.py`, or when a real Lane 3 read dialog is needed for a use case.*
