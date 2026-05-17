# S7 Operator Runbook

Status: operator-facing notes for Decision 34 / ADR 0039.

## Honesty Banner

S7 is not role-encrypted on the founder box. It governs Maez-controlled runtime
or helper paths, including soul/config/model-routing changes, but it cannot stop
raw local write access through raw OS filesystem, database, or service edits
outside Maez's runtime. Those raw OS paths are accepted limitations, not
permission to bypass S7.

## D22 Bypass Boundary

- Maez-controlled runtime or helper writes to code, config, soul,
  model-routing, covenant organs, refusal policy, role boundary, successor
  governance, memory retention/deletion, or protection settings are gated by S7.
- Raw OS filesystem/database edits outside Maez runtime are an accepted
  limitation: S7 cannot stop raw local write access by a privileged local user.
- Raw OS service edits outside Maez runtime are an accepted limitation; the
  bounded Maez daemon-down helper remains gated, content-free, and audited.
- Track B backup restore remains future-slice work until confidentiality-safe
  restore staging exists.
