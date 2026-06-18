# Runtime Body Truth (organ) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the runtime body-truth (services-map) organ from the quarry branch `maez-coherence-organism` onto `main` so Maez's two visible body surfaces — the cockpit and the project planner — tell the truth about its organs.

**Architecture:** Lift ONLY the read-only, always-on `runtime_services.py` organ (incl fix #3) + its two direct UI consumers. The endpoint `/api/v1/services` and the journal `/api/maez-state` serve a `maez_runtime_services.v0` snapshot (per-organ `healthy`/`degraded`/`asleep`/`unknown` from systemctl+TCP+HTTP-contract probes); the cockpit and planner render the real statuses; the fake simulator stays dead. No owner-spine/S7/web-owner/capability-card/daemon-`/health` code comes along.

**Tech Stack:** Python 3, Flask (`skills/web_interface.py`), `core/infra/runtime_services.py`, cockpit JS (`web/cockpit/sim.jsx`, `web/cockpit/terminal-ui.jsx`), `ui/project-planner.html`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-06-18-runtime-body-truth-organ-design.md` (@a0ca349).

---

## Lane discipline

- Test runner: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v` — named modules only, NEVER full-discover.
- Branch (use `superpowers:using-git-worktrees`): `runtime-body-truth-organ`. `main` local-only — **no push**.
- `## Predicted effect` on behavior commits; docs/spec/test-only commits omit it. End every commit with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **STOP at the review gate** (after Task 5). No merge/restart/flag (owner-sovereign). Cross-lane Codex review at the gate. Live witness before `LIVE_WITNESSED`.
- **Scope guard (every task):** touch ONLY the files this plan names. If a port drags in owner-spine/S7/web-owner/capability-card/daemon-`/health` code, STOP.

## File structure

- **Create** `core/infra/runtime_services.py` (verbatim port from quarry, incl #3) — the organ.
- **Create** `scripts/maez_runtime_services_probe.py` (verbatim port) — CLI probe.
- **Create** `tests/test_runtime_services.py` (verbatim port, 14 tests) — organ tests.
- **Create** `tests/test_runtime_body_truth_surfaces.py` — the two-mouth web/source tests (authored here).
- **Modify** `skills/web_interface.py` — replace `/api/v1/services`; add `runtime_services` to `/api/maez-state`; add the `_runtime_services_state` helper.
- **Modify** `ui/project-planner.html` — State line reads `runtime_services.overall`, no "all services up".
- **Modify** `web/cockpit/sim.jsx` — `_pollServices` stores the v0 snapshot into `state.runtimeServices` (tick stays dead).
- **Modify** `web/cockpit/terminal-ui.jsx` — `ServicesPane` renders `runtimeServices.services` with the new status vocab.
- **Create** `docs/proof/2026-06-18-runtime-body-truth-task0.md` (Task 0).

---

### Task 0: HARD PROOF GATE (docs/proof only — no behavior change, committed first)

**Files:** Create `docs/proof/2026-06-18-runtime-body-truth-task0.md`

- [ ] **Step 1: Full quarry `runtime_services` reference inventory, each classified IN/OUT**

Run:
```bash
cd /home/rohit/maez
git grep -n runtime_services maez-coherence-organism -- '*.py' '*.html' '*.jsx' | grep -v '^maez-coherence-organism:tests/'
```
Record every hit in the proof doc with an IN/OUT tag. Required classifications (from the spec):
**IN** — `core/infra/runtime_services.py`, `scripts/maez_runtime_services_probe.py`, `tests/test_runtime_services.py`, `skills/web_interface.py` `/api/v1/services` + `/api/maez-state` (the `_runtime_services_state` helper + the two handlers), `ui/project-planner.html`, `web/cockpit/sim.jsx`, `web/cockpit/terminal-ui.jsx`.
**OUT** — any `runtime_services` ref inside `/api/v1/now`, `core/infra/capability_registry.py`, `core/cognition/capability_card.py`, the daemon `/health` embedding (`daemon/maez_daemon.py`), and `tests/test_maez_body_organ_view.py`.
If any hit doesn't fit cleanly, STOP and ask.

- [ ] **Step 2: Clean-separation proof — no owner-spine/S7 import in any IN backend file**

Run:
```bash
for f in core/infra/runtime_services.py scripts/maez_runtime_services_probe.py tests/test_runtime_services.py; do
  echo "=== $f ==="
  git show "maez-coherence-organism:$f" | grep -nE '^(import|from) ' | grep -iE 's7|web_owner|owner_private|internal_channel|private_owner' && echo "  !! OWNER-SPINE/S7 IMPORT — STOP" || echo "  clean"
done
```
Expected: all "clean". Paste into the proof doc.

- [ ] **Step 3: Import-resolution proof — every `runtime_services.py` symbol resolves on main**

Run:
```bash
git show maez-coherence-organism:core/infra/runtime_services.py | grep -nE '^(import|from) '
/home/rohit/maez/.venv/bin/python -c "from core.infra.env_flags import strict_env_flag; from core.routing.llm_client import served_model_alias; print('served_model_alias + strict_env_flag resolve on main OK')"
```
Expected: the two project imports (`core.infra.env_flags.strict_env_flag`, `core.routing.llm_client.served_model_alias`) + stdlib only; the python import line prints OK. If `served_model_alias` is missing on main, STOP and note it (port only that helper, scope-guarded). Record the result.

- [ ] **Step 4: Confirm `#3` present + `test_maez_body_organ_view.py` is OUT**

Run:
```bash
git show maez-coherence-organism:core/infra/runtime_services.py | sed -n '140,144p'   # expect: raw = response.read()  (NOT read(4096))
git show maez-coherence-organism:tests/test_maez_body_organ_view.py | grep -n 'runtime_services\|_body_health\|/health' | head
```
Record: `_http_json` uses full `response.read()` (#3); `test_maez_body_organ_view.py`'s runtime case is the daemon `/health` embedding (OUT — do not port).

- [ ] **Step 5: Commit the proof (docs only)**
```bash
git add docs/proof/2026-06-18-runtime-body-truth-task0.md
git commit -m "docs(proof): runtime-body-truth Task 0 — ref inventory, clean separation, import resolution

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1: Port the organ backend (verbatim, incl #3) + its tests + probe

**Files:** Create `core/infra/runtime_services.py`, `scripts/maez_runtime_services_probe.py`, `tests/test_runtime_services.py` (all verbatim from quarry).

- [ ] **Step 1: Port the three files verbatim**
```bash
cd /home/rohit/maez
git show maez-coherence-organism:core/infra/runtime_services.py        > core/infra/runtime_services.py
git show maez-coherence-organism:scripts/maez_runtime_services_probe.py > scripts/maez_runtime_services_probe.py
git show maez-coherence-organism:tests/test_runtime_services.py         > tests/test_runtime_services.py
```

- [ ] **Step 2: Confirm #3 + clean imports landed**
```bash
grep -n 'response.read()' core/infra/runtime_services.py          # expect line ~142, NOT read(4096)
grep -nE '^(import|from) ' core/infra/runtime_services.py | grep -iE 's7|web_owner|owner_private|internal_channel' && echo "STOP: owner/s7 import" || echo "clean"
```
Expected: `raw = response.read()` present; "clean".

- [ ] **Step 3: Run the ported organ tests on main (they ARE the spec; verbatim port → green)**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_runtime_services -v`
Expected: 14 tests OK, including the #3 full-body-read regression (`test_http_json_reads_complete_response_body_before_parsing`). If any test ERRORs on a missing import, Task 0's import-resolution proof was wrong — STOP and fix the proof/port.

- [ ] **Step 4: Commit (behavior — new organ + its tests + probe)**
```bash
git add core/infra/runtime_services.py scripts/maez_runtime_services_probe.py tests/test_runtime_services.py
git commit -m "feat(body): port runtime_services organ to main (incl #3 full-body read)

## Predicted effect
main gains the read-only runtime_services snapshot organ (maez_runtime_services.v0;
per-organ healthy/degraded/asleep/unknown via systemctl+TCP+HTTP-contract probes) and its
CLI probe. _http_json reads the full /health body (#3), so a large healthy payload is not
truncated into a false-degraded. No endpoint/UI wired yet.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Replace `/api/v1/services` with the v0 snapshot (cockpit's backend)

**Files:** Modify `skills/web_interface.py` (the `api_services` handler; add `_runtime_services_state` helper). Test: `tests/test_runtime_body_truth_surfaces.py`.

- [ ] **Step 1: Write the failing test — `tests/test_runtime_body_truth_surfaces.py`**
```python
import os, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from unittest import mock
from skills import web_interface as W

_FAKE_SNAP = {
    "schema_version": "maez_runtime_services.v0",
    "overall": "degraded",
    "services": {
        "maez_daemon": {"status": "healthy", "degraded_reasons": []},
        "primary_brain": {"status": "healthy", "degraded_reasons": []},
        "search_body": {"status": "asleep", "degraded_reasons": []},
    },
}

class ApiV1Services(unittest.TestCase):
    def test_returns_v0_schema_and_services(self):
        with mock.patch.object(W, "_runtime_services_state", return_value=_FAKE_SNAP):
            client = W.app.test_client()
            r = client.get("/api/v1/services")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["runtime_services"]["schema_version"], "maez_runtime_services.v0")
        self.assertEqual(body["services"]["maez_daemon"]["status"], "healthy")
```
> The test patches the `_runtime_services_state` helper (added in Step 3) — the single seam both endpoints use — so it's deterministic regardless of where `runtime_services_snapshot_cached` is imported. (`mock.patch.object(W, "_runtime_services_state", ...)` requires the helper to exist; it does once Step 3 lands, which is why this test is RED until then.)

- [ ] **Step 2: Run — expect FAIL** (main's ad-hoc handler returns `{"services": {...}}` with `status/sub/desc`, no `runtime_services` key)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_runtime_body_truth_surfaces -v`

- [ ] **Step 3: Replace the handler.** In `skills/web_interface.py`, add the helper near the other private helpers and replace the `api_services` body:
```python
def _runtime_services_state(timeout_s: float = 0.35) -> dict:
    from core.infra.runtime_services import runtime_services_snapshot_cached
    return runtime_services_snapshot_cached(timeout_s=timeout_s)


@app.route("/api/v1/services")
def api_services():
    """Runtime service readiness from Maez's contract-aware body snapshot."""
    try:
        snapshot = _runtime_services_state()
    except Exception as e:
        return jsonify({"error": str(e), "services": {}}), 500
    return jsonify(
        {
            "runtime_services": snapshot,
            "services": snapshot.get("services") or {},
        }
    )
```
Delete the old ad-hoc `systemctl list-units` body entirely (the `import subprocess as _sp` + the parse loop). The helper keeps its local import (`from core.infra.runtime_services import runtime_services_snapshot_cached`); the test patches the `_runtime_services_state` helper itself, so no module-top import is required.

- [ ] **Step 4: Run — expect PASS**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_runtime_body_truth_surfaces -v`

- [ ] **Step 5: Commit (behavior)**
```bash
git add skills/web_interface.py tests/test_runtime_body_truth_surfaces.py
git commit -m "feat(body): /api/v1/services serves the contract-aware runtime_services v0 snapshot

## Predicted effect
/api/v1/services now returns {runtime_services: <v0 snapshot>, services: <per-organ>} with
real healthy/degraded/asleep/unknown statuses instead of an ad-hoc systemctl list-units parse.
Read-only; always-on.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `/api/maez-state` carries `runtime_services`; planner stops saying "all services up"

**Files:** Modify `skills/web_interface.py` (`api_maez_state` ~:7193), `ui/project-planner.html` (~:2012-2031). Test: `tests/test_runtime_body_truth_surfaces.py` (add cases).

- [ ] **Step 1: Add the failing tests** (append to `tests/test_runtime_body_truth_surfaces.py`)
```python
class ApiMaezState(unittest.TestCase):
    def test_maez_state_carries_runtime_services(self):
        with mock.patch.object(W, "_runtime_services_state", return_value=_FAKE_SNAP):
            client = W.app.test_client()
            r = client.get("/api/maez-state")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["runtime_services"]["overall"], "degraded")

class PlannerNoAllServicesUp(unittest.TestCase):
    def test_planner_source_has_no_all_services_up_and_reads_overall(self):
        import pathlib
        src = pathlib.Path("/home/rohit/maez/ui/project-planner.html").read_text()
        self.assertNotIn("all services up", src)
        self.assertIn("runtime_services", src)  # planner now reads the real overall
```

- [ ] **Step 2: Run — expect FAIL** (`/api/maez-state` has no `runtime_services` key; planner still contains "all services up")

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_runtime_body_truth_surfaces -v`

- [ ] **Step 3a: Add `runtime_services` to `/api/maez-state`.** In `api_maez_state` (after the `daemon_health.pop(...)` block, before the `return jsonify({...})`), insert:
```python
    try:
        runtime_services = _runtime_services_state(timeout_s=0.35)
    except Exception as e:
        runtime_services = {
            "schema_version": "maez_runtime_services.v0",
            "overall": "unknown",
            "services": {},
            "error": str(e)[:160],
        }
```
and add the key to the returned dict (right after `"services": _journal_services_state(),`):
```python
            "runtime_services": runtime_services,
```

- [ ] **Step 3b: Rewrite the planner State line.** In `ui/project-planner.html`, replace the `allUp` computation (lines ~2016-2017):
```javascript
        const allUp = ['maez', 'maez_web', 'llama_server', 'llama_server_vision']
          .every((k) => services[k] === 'active');
```
with a read of the real overall:
```javascript
        const overall = (state.runtime_services && state.runtime_services.overall) || 'unknown';
```
and replace the State line (line ~2030) — change:
```javascript
escHtml(adapter) + (allUp ? ' · all services up' : ' · degraded') +
```
to:
```javascript
escHtml(adapter) + ' · body ' + escHtml(overall) +
```
(So the planner shows " · body healthy" / " · body degraded" / " · body unknown" from the real snapshot. No "all services up" string remains.)

- [ ] **Step 4: Run — expect PASS** (both new tests + the Task-2 test still green)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_runtime_body_truth_surfaces -v`

- [ ] **Step 5: Commit (behavior)**
```bash
git add skills/web_interface.py ui/project-planner.html tests/test_runtime_body_truth_surfaces.py
git commit -m "feat(body): /api/maez-state carries runtime_services; planner reads real overall

## Predicted effect
/api/maez-state now includes the runtime_services v0 snapshot; project-planner's State line
reads runtime_services.overall ('body <overall>') instead of a hardcoded 'all services up'
computed from a stale service list. The dishonest 'all services up' string is gone.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Cockpit renders the real organ statuses (sim.jsx + ServicesPane)

**Files:** Modify `web/cockpit/sim.jsx` (`_pollServices` ~:533), `web/cockpit/terminal-ui.jsx` (`ServicesPane` ~:781). Test: source-guard in `tests/test_runtime_body_truth_surfaces.py`; full render is browser-witnessed (Task 5).

**Context:** main's `_pollServices` currently overlays the OLD `info.status === 'active'` shape onto `state.health`. After Task 2 the endpoint returns the v0 shape (`status` ∈ healthy/degraded/asleep/unknown), so that overlay is now wrong. Repoint the cockpit to the real snapshot. `tick()` stays dead (line ~470, commented — DO NOT re-enable).

- [ ] **Step 1: Add the source-guard test** (append to `tests/test_runtime_body_truth_surfaces.py`)
```python
class CockpitReadsRuntimeServices(unittest.TestCase):
    def test_servicespane_reads_runtimeServices_and_tick_stays_dead(self):
        import pathlib
        tui = pathlib.Path("/home/rohit/maez/web/cockpit/terminal-ui.jsx").read_text()
        sim = pathlib.Path("/home/rohit/maez/web/cockpit/sim.jsx").read_text()
        # ServicesPane renders the real snapshot, not the old sim.state.health
        self.assertIn("runtimeServices", tui)
        # the new status vocab is handled
        self.assertIn("healthy", tui)
        # the fake simulator stays dead
        self.assertNotIn("\n  setInterval(tick", sim)  # uncommented tick must not exist
```

- [ ] **Step 2: Run — expect FAIL** (terminal-ui.jsx has no `runtimeServices` yet)

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_runtime_body_truth_surfaces -v`

- [ ] **Step 3a: `web/cockpit/sim.jsx` — store the v0 snapshot.** In `_pollServices`, after `const d = await r.json();` and `markLive('services');`, set the new state and drop the old `state.health` overlay:
```javascript
  const _pollServices = async () => {
    try {
      const r = await fetch('/api/v1/services');
      if (!r.ok) { markOffline('services', r.status); return; }
      const d = await r.json();
      markLive('services');
      state.runtimeServices = d.runtime_services || { schema_version: 'maez_runtime_services.v0', overall: 'unknown', services: {} };
      emit();
    } catch (e) { markOffline('services', e); }
  };
```
And ensure the initial state has the key (find the `state = {` init object and add, near other organ fields):
```javascript
    runtimeServices: { schema_version: 'maez_runtime_services.v0', overall: 'unknown', services: {} },
```

- [ ] **Step 3b: `web/cockpit/terminal-ui.jsx` — `ServicesPane` renders the real statuses.** Replace the `ServicesPane` body:
```javascript
function ServicesPane() {
  const sim = useSim();
  const rs = sim.state.runtimeServices || { overall: 'unknown', services: {} };
  const entries = Object.entries(rs.services || {});
  const COLOR = { healthy: A.green, degraded: A.red, asleep: A.textFaint, unknown: A.orange };
  const attention = entries.filter(([, v]) => v.status === 'degraded' || v.status === 'unknown').length;
  return (
    <Card title="Living Senses" subtitle={`body ${rs.overall || 'unknown'} · ${entries.length} organs · ${attention} attention`}
      icon={<Dot c={attention ? A.orange : A.green} size={6} pulse={!attention} />} iconColor={attention ? A.orange : A.green}
      right={<LiveBadge endpoint="services" compact />}>
      <div className="ap-scroll" style={{ margin: '-4px -4px', overflow: 'auto', maxHeight: '100%', paddingRight: 4 }}>
        {entries.map(([name, v]) => (
          <div key={name} className="ap-hover-lift" title={(v.degraded_reasons || []).join(', ')} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', borderRadius: 8,
            border: '0.5px solid transparent', transition: `all 180ms`,
          }}>
            <Dot c={COLOR[v.status] || A.orange} pulse={v.status === 'healthy'} size={5} />
            <span style={{ flex: 1, fontFamily: A.sans, fontSize: 12.5, color: A.text }}>{name}</span>
            <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textDim }}>{v.status}</span>
            <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>{(v.port && v.port.port) ? `:${v.port.port}` : '—'}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
```
(Renders `healthy`/`degraded`/`asleep`/`unknown` with honest colors, `degraded_reasons` as hover title, real overall in the subtitle. No fabricated liveliness — pulse only on genuinely `healthy`.)

- [ ] **Step 4: Run — expect PASS** (source-guard) + the whole module green
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_runtime_body_truth_surfaces tests.test_runtime_services -v
```

- [ ] **Step 5: Commit (behavior)**
```bash
git add web/cockpit/sim.jsx web/cockpit/terminal-ui.jsx tests/test_runtime_body_truth_surfaces.py
git commit -m "feat(body): cockpit Living Senses renders real runtime_services statuses

## Predicted effect
The cockpit services pane reads the v0 runtime_services snapshot (healthy/degraded/asleep/
unknown per organ, real overall, degraded_reasons on hover) instead of the stale active/
inactive overlay. The fake tick() simulator stays dead. No simulated liveliness.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: STOP-at-gate handoff

**Files:** Create `docs/handoffs/2026-06-18-runtime-body-truth-organ-handoff.md`.

- [ ] **Step 1: Whole-organ green + ruff**
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_runtime_services tests.test_runtime_body_truth_surfaces -v
/home/rohit/maez/.venv/bin/python -m ruff check core/infra/runtime_services.py skills/web_interface.py scripts/maez_runtime_services_probe.py tests/test_runtime_services.py tests/test_runtime_body_truth_surfaces.py
```
Expected: all green; ruff clean.

- [ ] **Step 2: Write the handoff + commit (docs)**

Cover: branch tip, the Task-0 proof outputs, the diff (organ + 2 endpoints + planner + cockpit), test results, and the **Codex cross-lane anchors**: (1) clean separation — no owner-spine/S7/web-owner import in any ported file; (2) both lying mouths fixed (cockpit `/api/v1/services` + planner `/api/maez-state`); (3) `/api/v1/now`, `capability_registry`, `capability_card`, daemon `/health` embedding all OUT (confirm the diff doesn't touch them); (4) `#3` live — `maez_daemon` reads healthy not false-degraded; (5) `tick()` stays dead. Then the **owner breath**: restart `maez-web` → witness in the browser BOTH surfaces — the cockpit Living Senses shows differentiated organ statuses (`maez_daemon: healthy`, not degraded), and the project planner's State line reads "body <overall>" with no "all services up." `curl /api/v1/services` shows the v0 schema. Not `LIVE_WITNESSED` until the owner confirms both surfaces.
```bash
git add docs/handoffs/2026-06-18-runtime-body-truth-organ-handoff.md
git commit -m "docs(handoff): runtime body truth organ — review gate + owner-breath sequence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 3: STOP.** No merge, no restart, no flag — owner-sovereign. Hand to Codex cross-lane review.

---

## Notes for the implementer

- **Verify before patching JS line numbers** — `project-planner.html`, `sim.jsx`, `terminal-ui.jsx` line numbers drift; grep for the anchor strings (`allUp`, `_pollServices`, `function ServicesPane`) and edit surgically.
- **Scope guard is absolute** — the cockpit JS files have many *other* organism changes on the quarry; do NOT `git show quarry:<jsx> > main` (that drags organism code). Edit main's files surgically per the steps above.
- **`tick()` stays dead** — never re-enable the simulator; pulse only on real `healthy`.
- **DRY:** `_runtime_services_state` is defined once and used by both `/api/v1/services` and `/api/maez-state`.
