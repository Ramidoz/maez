# Security audit — Phase 7

Two-part audit:

- **Part 1** — secret-history scan. Confirm no API keys, tokens, or
  private keys have been committed to the repo.
- **Part 2** — network surface documentation. Enumerate every port
  Maez binds to, who can reach it, and what lives behind it.

**Audit date:** 2026-04-22

---

## Part 1 — Secret-history scan

### Method

Scanned the full git history with these patterns:

```bash
git log --all --full-history -p | grep -aE \
  '(AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36}|sk-[a-zA-Z0-9]{32,}|
   sk-ant-[a-zA-Z0-9-]{20,}|xai-[a-zA-Z0-9]{20,}|
   gho_[a-zA-Z0-9]{36}|ghu_[a-zA-Z0-9]{36}|
   glpat-[a-zA-Z0-9_-]{20}|
   -----BEGIN (RSA|OPENSSH|DSA|EC|PGP) PRIVATE KEY-----)'
```

Plus a follow-up scan for inline-assigned token-shaped values
excluding placeholders / env-var reads / comments.

### Result

**No matches.** No AWS access keys, no GitHub tokens, no OpenAI /
Anthropic / xAI keys, no GitLab PATs, no PEM private keys have ever
been committed.

### Why this works (and when it might stop)

The repo's `.gitignore` has always excluded:
- `config/.env` — the only file that carries real API keys
- `config/token.json`, `config/credentials.json` — OAuth state
- `memory/*.db`, `memory/chroma/` — runtime state

Combined with the author's discipline of only ever reading keys via
`os.environ.get(...)`, no secret has landed in source. Future risk:

- A new contributor committing a `.env` file by accident. Mitigated
  by `.gitignore` and the gitleaks pre-commit hook (Phase 8 — see
  Outstanding section, since-installed).
- A secret leaking through a commit message. No known instance.
- An error / traceback with the key in it landing in `logs/maez.log`
  — `logs/*` is gitignored.

### Rotation posture

If a secret ever *were* to land, the canonical fix is:

1. **Rotate the secret** on the provider side immediately
   (API-key management console).
2. Scrub from git history with `git filter-repo` or `bfg`.
3. Force-push to rewrite the remote.
4. Open an issue noting the rotation so contributors refresh their
   local clones.

No such action has ever been required.

---

## Part 2 — Network surface

### Ports Maez binds

| Port | Binding | Purpose | Authentication |
|---|---|---|---|
| 5173 | 127.0.0.1 or 0.0.0.0 (cockpit dev build) | Web cockpit (Flask + React) | Session + MAEZ_OWNER_USER_ID check |
| 8765 | 127.0.0.1 | Fast-reply adapter (ambient-turn service) | None — localhost only |
| 11438 | 127.0.0.1 | Subscription proxy (OpenAI-compatible) | None — localhost only |

**Everything else is outbound.** The daemon *reaches out* to the
local LLM backend (llama-server on 8080 or Ollama on 11434), to
external APIs via the subscription proxy, to the Telegram Bot API,
and to the open-meteo weather endpoint. Nothing else listens.

### Cockpit (port 5173)

- Default binding is `127.0.0.1`. If the owner manually binds to
  `0.0.0.0` (for example to reach the cockpit from a phone on the
  same LAN), they need to be on a trusted network — the cockpit's
  session layer is lightweight.
- Auth is session-based with an owner check against
  `MAEZ_OWNER_USER_ID`. Non-owner sessions see only the public
  landing page, not the reasoning / card / self-dev panes.
- No CSRF hardening today. Behind `127.0.0.1` that's tolerable; as
  part of Phase 10 launch prep, LAN-binding users should be told to
  put a reverse proxy (caddy / traefik) with basic-auth or OAuth in
  front.

### Subscription proxy (port 11438)

- Hard-coded `host="127.0.0.1"` in
  [`core/subscription_proxy/__main__.py`](../../core/subscription_proxy/__main__.py).
  This is enforced in code — overriding via env requires editing
  source.
- OpenAI-compatible endpoint. Routes `/v1/chat/completions` to
  pluggable adapters (Claude subscription, OpenRouter, OpenAI, xAI,
  Ollama Cloud, Gemini).
- No auth — design assumes only trusted local processes (Maez
  itself, or `curl` from the owner's shell) reach it. Any process
  on the box that can bind to loopback has access. That's the
  reality on a single-user machine.
- Hardened systemd unit restricts write paths (`ReadWritePaths=...
  memory ... logs`) and disables new-privs escalation.

### Fast-reply adapter (port 8765)

- Internal-only localhost service used by the brain loop's
  ambient-turn path (the between-heavy-cycles fast replies).
- No auth; no plan to expose.

### Daemon outbound calls

| Target | Purpose | When |
|---|---|---|
| 127.0.0.1:8080 (llama-server) *or* 127.0.0.1:11434 (Ollama) | local inference | every reasoning cycle |
| 127.0.0.1:11438 (subscription proxy) | cloud routing (opt-in) | only when a scope allows cloud |
| api.telegram.org | push notifications / receive replies | if `MAEZ_TELEGRAM_TOKEN` set |
| api.open-meteo.com | weather facts | ambient pulls (cached aggressively) |
| api.github.com | repo / trending snapshots | if `MAEZ_GITHUB_TOKEN` set |
| api.anthropic.com etc. | routed through subscription proxy | see above |

iPhone signals enter via the cockpit's `/api/iphone/ingest`
endpoint (POST, token-authed via `MAEZ_IPHONE_INGEST_TOKEN`). That's
inbound traffic, not outbound.

### Pre-flight binding verification

```bash
# Confirm nothing is bound outside localhost after start:
ss -tlnp | grep -vE "127\.0\.0\.1|::1"     # should be empty
# or
netstat -tlnp | grep -v "127\.0\.0\.1\|::1"
```

If any Maez service appears on `0.0.0.0`, that's a configuration
regression.

### Redaction before cloud

Any payload that crosses into a cloud adapter passes through
[`core.safety.cloud_redactor.redact_for_cloud`](../../core/safety/cloud_redactor.py)
first. It strips owner-identifying tokens (display name, home coords,
Telegram ID, machine hostname) and attaches a `redaction_telemetry`
dict to the result so the caller can see what was scrubbed. Phase 2
cleaned up hardcoded owner references so this path is effective.

---

## Outstanding

- **Pre-commit secret-scan hook.** ✅ Installed — `gitleaks` v8.22.1
  in `.pre-commit-config.yaml`. Phase 8 close-out. Hook is opt-in
  (`pre-commit install` per clone) so contributors must enable it
  locally; doc updated 2026-05-02 after audit pass surfaced the
  drift between this section and `.pre-commit-config.yaml`.
- **CSRF on the cockpit.** Fine for `127.0.0.1` use; document LAN
  exposure risk in Phase 10.
- **Rate limiting on the subscription proxy.** Localhost-only, so
  untrusted-process abuse is out of scope. But every adapter has
  its own per-hour / per-day budget enforced in
  [`core/subscription_proxy/budget.py`](../../core/subscription_proxy/)
  so a runaway caller can't drain the owner's subscription.

None of these are blockers for v0.1.0-alpha.

---

## 2026-05-04 audit Tier-2 deferrals — load-bearing items that need their own slice

The 2026-05-04 15-agent audit
([`docs/audit_15agent_2026-05-04.md`](../audit_15agent_2026-05-04.md))
Tier-2 mechanical track is fully closed across commits `acb57f3`,
`534f504`, `cfcb266`, `13cee12`, `0566b03`. Four items were
deliberately deferred to their own slices — recorded here so they
don't get lost:

1. **`/api/v1/*` unauthenticated + CORS `*` + no CSRF.** Today this
   is conditional-only because Flask binds to `127.0.0.1`. Grep
   for `0\.0\.0\.0` returns nothing in the cockpit path. Promotion
   to Track-B (girlfriend + one friend) where cockpit may need LAN
   reach will require a token-auth layer. Tracked here; design
   decision deferred to Track-B planning.

2. **Dream → soul audit-before-store.** Already in `docs/TRACK_A.md`
   as architectural debt. Dream-cycle writes to soul.local.md without
   passing through the same audit-before-store path that the chat /
   action routes use. Closing this needs a small architectural slice
   (audit-routing for the dream surface). Not load-bearing for
   Track-A; promoted to its own slice for the post-Track-A polish
   queue.

3. **28 `TYPE_CHECKING` circular-import workarounds in
   `core/memory/`.** The current import graph has ~28 `if
   TYPE_CHECKING:` guards papering over circular refs between
   episodes / relationship_graph / working_self / lived_recall. The
   fix is a careful 1-2-session refactor that splits the type
   surface from the runtime surface. Risk: a partial refactor
   silently breaks the import graph at module-load time. Tracked
   here as its own slice rather than rolled into mechanical
   cleanup.

4. **Hi-3 trust-tier 23-producer compliance audit.** The 5x memory
   provenance arc is closed at the schema / store level, but 23
   trajectory producers since `cda2888` haven't been individually
   audited for compliance with the default-deny invariant. Closing
   this is its own audit pass (similar shape to the original
   15-agent code audit, scoped to trajectory producers). Tracked
   here; queued for execution when Track-A audit-cleanup work is
   otherwise quiescent.

Each deferral is a real item — none is a permanent shrug. They
move out of the Track-A audit-cleanup queue but stay on the
post-Track-A hardening list.
