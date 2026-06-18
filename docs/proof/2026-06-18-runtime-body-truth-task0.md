# Runtime-Body-Truth Organ — Task 0 Proof Gate (2026-06-18)

HARD GO/NO-GO proof gate. DOCS/PROOF ONLY — no behavior code changed.
Quarry branch: `maez-coherence-organism`. Target: `main` (this worktree, branch `runtime-body-truth-organ`).
Python: `/home/rohit/maez/.venv/bin/python`.

---

## (a) Full quarry `runtime_services` reference inventory — IN/OUT classification

Command: `git grep -n runtime_services maez-coherence-organism -- '*.py' '*.html' '*.jsx'`

### IN — port these

| File | Lines | Classification |
|---|---|---|
| `core/infra/runtime_services.py` | 16, 235, 377, 382, 389 (whole module) | IN — the organ itself |
| `scripts/maez_runtime_services_probe.py` | 6, 12, 17 | IN — CLI probe |
| `tests/test_runtime_services.py` | 13, 42, 45, 47, 62, 65, 74, 88, 96, 103, 116, 134, 141, 151, 158, 169, 176, 182, 188, 194, 202, 205, 213, 228, 238, 269, 290, 293, 299 | IN — unit tests for the organ + probe |
| `skills/web_interface.py` | 865 (`_runtime_services_state` helper), 866, 868, 875 (`_runtime_services_summary`), 2126, 2131 (`/api/v1/services` handler), 3665, 3666, 3668, 3742 (`/api/maez-state` handler region), 4012, 7381, 7383, 7384, 7400 | IN — `_runtime_services_state` helper + `/api/v1/services` + `/api/maez-state` handlers |
| `ui/project-planner.html` | 2015, 2040, 2070 | IN — `state.runtime_services` consumer |
| `web/cockpit/sim.jsx` | 28, 546, 547 | IN — schema_version + `state.runtimeServices = d.runtime_services` consumer |

### OUT — do NOT port

| File | Lines | Classification |
|---|---|---|
| `core/cognition/capability_card.py` | 15 (`from core.infra.runtime_services import support_honesty_status`) | OUT — explicitly excluded by plan |
| `core/infra/capability_registry.py` | 257, 259, 261, 264, 267, 271, 294, 361 | OUT — `_runtime_services_for_prompt` / prompt-line embedding, explicitly excluded |
| `daemon/maez_daemon.py` | 71 (import), 3555 (`/health` embedding) | OUT — daemon `/health` embedding, explicitly excluded |
| `tests/test_maez_body_organ_view.py` | 116, 194, 215, 230 | OUT — tests the daemon `/health` embedding (see proof (d)) |

### FLAGGED — hits/expectations that did not fit cleanly

1. **`web/cockpit/terminal-ui.jsx` — task lists it as IN, but it has ZERO `runtime_services` refs (neither snake_case nor camelCase `runtimeServices`).**
   - `git show maez-coherence-organism:web/cockpit/terminal-ui.jsx | grep -n 'runtimeServices\|runtime_services'` → **none**. File exists on quarry; simply has no reference.
   - Impact: the port plan's IN list names a file that contains nothing to port. NOT a refutation of the organ (the consumer that matters is `sim.jsx`, which exists), but the plan's file list is inaccurate for terminal-ui.jsx. Drop it from the port set or confirm intent.

2. **Three test files appear in the grep that the task did not enumerate IN or OUT:**
   - `tests/test_capability_registry.py` (116, 144) — exercises `_runtime_services_for_prompt` in capability_registry. Couples to the OUT prompt-embedding path → treat as **OUT** (tests an OUT consumer).
   - `tests/test_cockpit_living_dashboard.py` (58) — `test_living_dashboard_uses_runtime_services_not_active_inactive_flattening`. Asserts cockpit dashboard reads runtime_services; relates to the IN cockpit/sim.jsx consumer. Likely **IN-adjacent** (port if the cockpit consumer is ported), but it was not on the task's IN list — FLAG for the porter to decide.
   - `tests/test_web_runtime_truth.py` (25, 51, 58, 59, 70, 99, 107, 121, 122, 126, 131) — directly tests the IN `/api/v1/services` and `/api/maez-state` web handlers (mocks `core.infra.runtime_services.runtime_services_snapshot_cached`, asserts `state.runtime_services` in the public journal page). This is the **integration witness for the IN handlers** and should be **IN** (port alongside web_interface handlers), but the task did not list it. FLAG: porting the IN handlers without this test loses their integration witness.

---

## (b) Clean-separation proof — no owner-spine/S7 import in backend files to port

Command (per file, grep imports for s7|web_owner|owner_private|internal_channel|private_owner):

```
=== core/infra/runtime_services.py ===
  clean
=== scripts/maez_runtime_services_probe.py ===
  clean
=== tests/test_runtime_services.py ===
  clean
```

Result: **all clean.** No owner-spine / S7 imports in any of the three backend files to port. This is the property that distinguishes this organ from the coherence-organism lockout (owner≠private_owner_bridge / S7-token 403 path) — the runtime-body-truth backend does not touch the owner spine.

---

## (c) Import-resolution proof — every symbol `runtime_services.py` imports resolves on main

Imports in `core/infra/runtime_services.py`:

```
1:from __future__ import annotations
3:import json
4:import shutil
5:import socket
6:import subprocess
7:import time
8:import urllib.error
9:import urllib.request
10:from collections.abc import Callable
11:from typing import Any
13:from core.infra.env_flags import strict_env_flag
14:from core.routing.llm_client import served_model_alias
```

Only stdlib + two first-party imports: `core.infra.env_flags` (`strict_env_flag`) and `core.routing.llm_client` (`served_model_alias`). No owner-spine, no S7, no MiniCheck/grounding coupling.

Resolution on main:

```
$ /home/rohit/maez/.venv/bin/python -c "from core.infra.env_flags import strict_env_flag; from core.routing.llm_client import served_model_alias; print('OK: served_model_alias + strict_env_flag resolve on main')"
OK: served_model_alias + strict_env_flag resolve on main
```

Result: **both symbols resolve on main.** `served_model_alias` is PRESENT on main — no missing-helper blocker for the port.

---

## (d) Confirm #3 present + `test_maez_body_organ_view.py` is OUT

`core/infra/runtime_services.py` lines 138–145:

```
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read()
        return {
            "ok": True,
            "json": json.loads(raw.decode("utf-8") or "{}"),
```

Result: `_http_json` uses **full `response.read()`** (not `read(4096)`). **Fix #3 is present** in the quarry copy (the 4096-byte truncation root cause is already remediated in the file we port).

`tests/test_maez_body_organ_view.py` runtime refs:

```
76:            body = md.MaezDaemon._body_health(
116:                "runtime_services",
194:    def test_body_health_includes_runtime_services(self):
215:            "daemon.maez_daemon.runtime_services_snapshot",
221:            body = md.MaezDaemon._body_health(
230:        self.assertEqual(body["runtime_services"], runtime)
```

Result: this test patches `daemon.maez_daemon.runtime_services_snapshot` and asserts the daemon's `MaezDaemon._body_health` `/health` embedding. It tests the **daemon `/health` embedding path (OUT)** — confirmed **OUT — do not port.**

---

## TASK 0 VERDICT: GO

The core port assumptions hold:
- backend files to port (`runtime_services.py`, probe, unit tests) are owner-spine/S7 **clean** (b);
- all imports resolve on main; `served_model_alias` is **present** on main (c);
- fix #3 (full `response.read()`) is **already present** in the quarry copy (d);
- `test_maez_body_organ_view.py` is correctly **OUT** (daemon `/health` embedding) (d).

GO is qualified by THREE inventory flags the porter must act on before/during the port (none refute the organ; they are scope corrections to the plan's file list):

1. **`web/cockpit/terminal-ui.jsx` is on the IN list but contains NO runtime_services reference at all** — drop it from the port set or confirm intent.
2. **`tests/test_web_runtime_truth.py` is the integration witness for the IN `/api/v1/services` + `/api/maez-state` handlers but was not listed** — it should be IN; porting the handlers without it loses their integration witness.
3. **`tests/test_capability_registry.py` (OUT-coupled) and `tests/test_cockpit_living_dashboard.py` (IN-adjacent cockpit consumer) appeared unenumerated** — classify before porting; do not port the capability_registry test (couples to the OUT prompt-embedding), decide on the cockpit dashboard test alongside sim.jsx.
