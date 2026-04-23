# Third-party attribution — `skills/surface/`

This directory vendors the **gateway/platforms** layer of the open-source
**Hermes Agent** project (https://github.com/NousResearch/hermes-agent),
licensed under the **MIT License**. The vendored files are the Telegram
adapter and its supporting platform-base + session infrastructure.

**What was vendored:**

| Our file | From upstream path |
|----------|--------------------|
| `platform_base.py` | `gateway/platforms/base.py` |
| `telegram_adapter.py` | `gateway/platforms/telegram.py` |
| `telegram_network.py` | `gateway/platforms/telegram_network.py` |
| `session.py` (slim) | `gateway/session.py` (only `SessionSource` + `build_session_key`) |
| `platform_config.py` (slim) | `gateway/config.py` (only `Platform`, `HomeChannel`, `PlatformConfig`) |

**What is Maez-authored:**

| File | Role |
|------|------|
| `__init__.py` | Re-exports |
| `maez_surface_paths.py` | Replaces upstream's `hermes_constants.get_hermes_dir` |
| `maez_adapter.py` | Bridges `BasePlatformAdapter.MessageHandler` → Maez decision pipeline |

**Why selective vendoring, not a pip dependency:**

- Identity: Maez keeps its own surface layer. No external "Hermes" name
  appears in the import path, the config, the logs, or the runtime
  dependency tree.
- License: MIT → AGPL is one-way compatible. Maez can embed MIT-licensed
  code under AGPL; the vendored files retain their MIT copyright header
  at the top as legal attribution.
- Maintenance: we copy once, freeze, and take upstream updates
  manually (diff-and-merge) when there's a clear reason. Avoids
  surprise breakages from upstream refactors.

**Upstream copyright headers are preserved at the top of each vendored
file per MIT's redistribution clause.** If we later strip them, we
violate the license — they must stay even after branding cleanup in
docstrings and log strings.

**Upstream version at vendor time:** `main` branch, fetched
2026-04-20, corresponding to Hermes Agent release track v0.10.x.
