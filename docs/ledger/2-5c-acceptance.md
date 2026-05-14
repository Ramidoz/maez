# Ledger Slice 2.5c Acceptance Runbook

Status: planned, not yet run.

Purpose: prove daemon `user_message` shadow writes are safe before enabling
`MAEZ_LEDGER_WRITES=1` against the production ledger path.

## Human decisions before start

Rohit chooses these before the window begins:

1. Sandbox DB path. Recommended shape: `memory/sandbox_ledger_YYYY_MM_DD.db`.
2. Deliberate crash moment. Must happen mid-conversation, not at idle.
3. Review sample. Minimum: first 3 entries, last 3 entries, 10 random entries,
   and the 3 entries before + 3 entries after each deliberate crash.

Minimum volume: at least 20 user messages across Telegram and cockpit. If the
24h window produces fewer than 20, extend the window or send more test messages.

## Start conditions

- Sandbox DB path does not exist.
- `memory/ledger.db` remains untouched by this run.
- Daemon gets both env vars scoped to the daemon process only:
  - `MAEZ_LEDGER_DB_PATH=<sandbox-db>`
  - `MAEZ_LEDGER_WRITES=1`
- Do not put these in shell rc files.
- Do not promote the sandbox DB to production later. It has sandbox-era timing.

Universal launch shape when not using systemd:

```bash
MAEZ_LEDGER_DB_PATH=memory/sandbox_ledger_YYYY_MM_DD.db \
MAEZ_LEDGER_WRITES=1 \
python daemon/maez_daemon.py
```

Use the equivalent process-scoped env injection for systemd/tmux/screen if the
daemon is launched another way.

## Required checks during window

1. Send messages through both Telegram and cockpit.
2. Confirm `user_message` rows appear in the sandbox ledger.
3. Confirm `meta.ledger_era_starts_at` was set by the first non-genesis write.
4. Deliberately `kill -9` the daemon mid-conversation at least once.
5. Restart the daemon with the same two sandbox env vars.
6. Confirm the daemon starts and continues responding after the crash.

Important: the daemon does not auto-run ledger reconciliation on startup in
Slice 2.5c. Reconciliation is operator-CLI-only.

## End-of-window acceptance gates

Run chain verification:

```bash
python scripts/verify_ledger_chain.py <sandbox-db>
```

Required result: exit code 0.

Run reconciliation dry-run:

```bash
python scripts/reconcile_ledger.py <sandbox-db> \
  --audit-log memory/audit_log.db \
  --fabrication-log memory/fabrication_log.db \
  --pending-cards memory/pending_cards.db \
  --self-mod-dialogs memory/self_mod_dialogs.db
```

Allowed dry-run outcomes:

- Clean: pass.
- State A: pass. Nothing landed; nothing to repair.
- State B orphans: pass only if `--apply` repairs them and chain verification
  passes afterward.
- State C: hard fail. Do not flip production.

If State B appears, apply repair manually:

```bash
MAEZ_LEDGER_WRITES=1 \
python scripts/reconcile_ledger.py <sandbox-db> \
  --audit-log memory/audit_log.db \
  --fabrication-log memory/fabrication_log.db \
  --pending-cards memory/pending_cards.db \
  --self-mod-dialogs memory/self_mod_dialogs.db \
  --apply

python scripts/verify_ledger_chain.py <sandbox-db>
```

Required result after repair: chain verification exits 0.

## Rohit review gate

Rohit reviews:

- First 3 entries.
- Last 3 entries.
- 10 random entries across the window.
- 3 entries before and 3 entries after each deliberate crash.

Each sampled row must match what Rohit actually sent, with the right surface and
reasonable timestamp. The review must cover both Telegram and cockpit.

## Production flip rule

Only flip production if all are true:

- Minimum message volume reached.
- Chain verifier exits 0.
- Reconciliation is clean or State B was repaired and then verified clean.
- No State C occurred.
- Rohit accepts the sampled entries as a truthful permanent diary shape.

If accepted, production starts fresh on the real `memory/ledger.db` path. The
sandbox DB is discarded or archived as test evidence; it is never promoted.

Plain English: test the notebook in a disposable notebook, deliberately stumble
once, repair only through the operator tool, then let Rohit inspect the pages
before Maez gets the real diary.
