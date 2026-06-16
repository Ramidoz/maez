# Thread A Task 0 Proof — Claim Entailment Support Rail

Date: 2026-06-16
Branch: `claim-entailment-support-rail`
Plan: `docs/superpowers/plans/2026-06-16-claim-entailment-support-rail.md`

## 0a — MiniCheck `/support` artifact

Existing listener check:

```text
no :8083 listener (expected if not installed)
```

Transient artifact probe, without installing or enabling a user unit:

```bash
.venv/bin/python -B scripts/minicheck_verifier_service.py
curl -sS -m 90 http://127.0.0.1:8083/support \
  -H 'Content-Type: application/json' \
  -d '{"evidence":"Anthropic released Claude Opus 4.5.","claim":"Anthropic released Claude Opus 4.5."}'
```

Observed response:

```json
{"verdict": "SUPPORTED", "score": 0.7047778367996216}
```

Result: `PASS`. The existing service artifact answers the load-bearing
`{"verdict", "score"}` contract expected by `HttpSupportVerifier`. The unit is
not installed or running persistently; that remains an owner breath.

## 0b — Capture-then-post-audit reachability

Source proof commands:

```bash
sed -n '6588,6594p' daemon/maez_daemon.py
sed -n '6617,6621p' daemon/maez_daemon.py
grep -n 'reply = audit_assistant_text' daemon/maez_daemon.py
awk 'NR>=6619 && NR<=6882 && /reply *=|_CITE_RE/' daemon/maez_daemon.py
grep -n 'local_label' core/routing/focused_cognition.py | head
```

Observed source facts:

- `daemon/maez_daemon.py:6590` runs
  `check_groundedness(_focused_result, _focused_working_set)`, so the focused
  result and working set are both in scope at the capture seam.
- `daemon/maez_daemon.py:6619-6621` assigns the focused reply into `reply` and
  sets `_focused_used = True`.
- `daemon/maez_daemon.py:6882` calls `reply = audit_assistant_text(...)`,
  leaving the post-audit served reply in the same `handle_message` scope.
- Between the focused assignment and audit call, the observed `reply =` writes
  are the focused assignment, dated/legacy/error fallbacks, tool-call leak
  stripping, pursuit append, and final audit assignment. No `_CITE_RE` citation
  strip appears in that range.
- `core/routing/focused_cognition.py` carries `EvidenceItem.local_label` and
  assigns labels such as `E1`, `E2`; the focused working set can therefore
  provide a `{local_label -> text}` map.

Runtime owner-turn proof: not run in this implementation session. No temporary
live-daemon instrumentation was committed. The handoff must keep runtime witness
honest: the first live focused web turn with the flag enabled must show
`post_audit: true` rows, cited labels, and a non-empty evidence map before the
row can be treated as a live verifier witness.

Result: `PASS_SOURCE_PROVEN_RUNTIME_PENDING`.

## Gate Summary

SEAM ASSUMPTIONS HELD: `YES` for implementation planning:

- MiniCheck service artifact speaks the expected HTTP contract.
- The focused evidence map and final post-audit reply are reachable in the same
  handler scope by source proof.

SEAM ASSUMPTIONS STILL TO WITNESS LIVE:

- A real focused web turn produces post-audit reply text retaining `[E#]`.
- The captured `{local_label -> text}` map is non-empty and overlaps cited
  labels in the served reply.
- Enqueue from the post-audit seam remains non-blocking under the live flag.

No behavior changed in Task 0.
