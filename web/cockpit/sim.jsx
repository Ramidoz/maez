// Shared cockpit state layer for Maez. The owner cockpit is a truth surface:
// it shows live API state, honest empty state, or explicit offline state.

const SIM = (() => {
  const listeners = new Set();
  const emit = () => { for (const l of listeners) l(); };

  // ──────────── seed data ────────────
  const now = () => new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const ts = (d = now()) => `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  const hms = (d = now()) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  let turnSeq = 0;
  const turnId = () => `turn-${Date.now()}-${++turnSeq}`;

  const state = {
    meta: {
      endpoints: {},
      mode: 'live-first',
    },
    health: {
      'maez (daemon)':       { port: 11435, status: 'unknown', vram: 0, ms: null },
      'maez-web':            { port: 11437, status: 'unknown', vram: 0, ms: null },
      'llama-server':        { port: 8080,  status: 'unknown', vram: 0, ms: null },
    },
    runtimeServices: { schema_version: 'maez_runtime_services.v0', overall: 'unknown', services: {} },
    gpu: { vramUsed: 0, vramTotal: 24, temp: 0, power: 0, util: 0 },
    cpu: { util: 0, temp: 0, load: [] },
    signals: [],
    daemon: {
      cycle: 0,
      lastTick: '',
      nextTickIn: 30,
      currentThought: '',
      // Honest organs for the slime avatar (flag-on real-state shape). Default
      // to the calm/alive baseline; never fabricate a feeling.
      valence: null,   // { sign, magnitude, telemetry } — the real felt-state reading
      status: 'unknown', // alive | stalled | stopped | safe_standby | unknown
      stalled: false,
      ledgerAttention: false,
      scratchpad: [],
    },
    chat: {
      activeSessionId: '',
      sessions: [],
      pendingCommand: null,
      streaming: false,
      streamBuf: '',
    },
    router: {
      window: [],
      totals: { local: 0, claude: 0, bytesIn: 0, bytesOut: 0, costUsd: 0.0 },
    },
    livedMemory: {
      // ADR 0019 — populated by _pollLivedMemory from
      // /api/v1/lived-memory; empty until owner runs the nightly
      // reflection orchestrator. v1.4 adds echoes (v1.2 finder),
      // predictions (v1.3 simulator), and provenance summary so the
      // Living Memory panel can render the full surface from a
      // single fetch.
      episodes: [],
      edges: [],
      echoes: [],
      predictions: [],
      provenance: { maez_authored: 0, project_doc: 0, total: 0 },
      counts: { episodes: 0, edges: 0, echoes: 0, predictions: 0 },
    },
    memory: {
      query: '',
      stats: { raw: 0, daily: 0, core: 0 },
      hits: [],
    },
    dreams: [],
    soul: {
      base: '',
      local: '',
    },
    identity: {
      owner: {},
      machine: {},
      policies: {},
      redditSubs: [],
    },
    logs: {
      maez:      [],
      cognition: [],
      evolution: [],
    },
    approvals: [],
  };

  const markLive = (name) => {
    state.meta.endpoints[name] = { status: 'live', at: Date.now(), error: '' };
  };
  const markOffline = (name, error) => {
    state.meta.endpoints[name] = {
      status: 'offline',
      at: Date.now(),
      error: String(error || 'unreachable').slice(0, 140),
    };
  };

  const ensureChatSession = () => {
    let sess = state.chat.sessions.find(s => s.id === state.chat.activeSessionId);
    if (sess) return sess;
    sess = {
      id: 'live',
      title: 'Recent Telegram',
      preview: '',
      updated: '',
      color: 'blue',
      unread: 0,
      history: [],
    };
    state.chat.sessions = [sess];
    state.chat.activeSessionId = sess.id;
    return sess;
  };

  // ──────────── api ────────────
  const api = {
    state,
    subscribe: (fn) => { listeners.add(fn); return () => listeners.delete(fn); },
    sendMessage: (text) => {
      const sess = ensureChatSession();
      const userTurn = { _id: turnId(), role: 'user', t: ts(), content: text };
      sess.history.push(userTurn);
      sess.preview = text.slice(0, 80);
      sess.updated = ts().slice(0,5);
      state.chat._awaitingReply = true;
      state.chat._tools = [];
      state.chat.streamBuf = '';
      emit();
    },
    // Real-chat helpers (used when the cockpit talks to the live daemon
    // via /message on port 11435). Push the user turn immediately and
    // flip the pending flag so the UI shows "Thinking…" while the
    // daemon reply is in flight. pushAssistantTurn drops that flag
    // and appends the real reply.
    pushUserTurn: (text) => {
      const sess = ensureChatSession();
      const userTurn = { _id: turnId(), role: 'user', t: ts(), content: text };
      sess.history.push(userTurn);
      sess.preview = text.slice(0, 80);
      sess.updated = ts().slice(0, 5);
      state.chat._awaitingReply = true;
      state.chat._tools = [];
      emit();
      return userTurn;
    },
    pushAssistantTurn: (reply) => {
      const sess = ensureChatSession();
      const assistantTurn = {
        _id: turnId(),
        role: 'assistant', t: ts(),
        route: 'local',
        model: 'daemon',
        content: reply,
        trace: { tools: state.chat._tools || [], memory: 0, tokens: Math.floor((reply||'').length / 4) },
      };
      sess.history.push(assistantTurn);
      state.chat._awaitingReply = false;
      state.chat.streaming = false;
      state.chat.streamBuf = '';
      emit();
      return assistantTurn;
    },
    finishSimReply: (reply) => {
      // Compatibility hook for ChatPane paths that still go through the
      // simulated flow — treat finish as a push-assistant.
      const sess = ensureChatSession();
      const assistantTurn = { _id: turnId(), role: 'assistant', t: ts(), route: 'local', model: 'daemon', content: reply, trace: { tools: [], memory: 0, tokens: Math.floor((reply||'').length/4) } };
      sess.history.push(assistantTurn);
      state.chat.streaming = false;
      state.chat.streamBuf = '';
      state.chat._awaitingReply = false;
      emit();
      return assistantTurn;
    },
    selectSession: (id) => { state.chat.activeSessionId = id; emit(); },
    newSession: () => {
      const colors = ['blue','purple','green','orange','pink','cyan','indigo','mint'];
      const id = 'n' + Math.random().toString(36).slice(2,6);
      state.chat.sessions.unshift({ id, title: 'New conversation', preview: 'start typing…', updated: 'now', color: colors[Math.floor(Math.random()*colors.length)], history: [] });
      state.chat.activeSessionId = id;
      emit();
    },
    deleteSession: (id) => {
      state.chat.sessions = state.chat.sessions.filter(s => s.id !== id);
      if (state.chat.activeSessionId === id) {
        state.chat.activeSessionId = state.chat.sessions.length ? state.chat.sessions[0].id : '';
      }
      emit();
    },
    approveCommand: (approve) => {
      const p = state.chat.pendingCommand;
      if (!p) return;
      const sess = state.chat.sessions.find(s => s.id === state.chat.activeSessionId);
      if (sess) sess.history.push({ role: 'assistant', t: ts(), route: 'local', model: 'qwen3.6-27b', commands: [{
        cmd: p.cmd, status: approve ? 'approved' : 'denied',
        output: approve ? '● ok. active (running) since 10:03. memory 18.4M.' : '(skipped — user declined)',
      }], trace: { tools: ['shell'], memory: 0, tokens: 20 } });
      state.chat.pendingCommand = null;
      emit();
    },
    approveQueued: (id, approve) => {
      // approve=true → maez-web's /api/v1/cards/<id>/approve proxy
      //   forwards to the daemon's /internal/approve_card/<id>, which
      //   runs the full pipeline approve path (covenant → will-I →
      //   execute → mark_done). Equivalent to typing 'yes' in Telegram;
      //   the actual execution lives in the daemon process where
      //   ActionEngine is. (Workstation v1 / Session 1: no more
      //   browser-direct daemon calls.)
      // approve=false → maez-web's safe deny (state transition only).
      const path = approve === true ? 'approve' : 'deny';
      fetch(`/api/v1/cards/${encodeURIComponent(id)}/${path}`, {
        method: 'POST',
      }).catch(() => {});
      // Optimistic removal — the next _pollCards tick will re-verify
      // against the DB and restore the card if the server-side call
      // didn't actually resolve it.
      state.approvals = state.approvals.filter((a) => a.id !== id);
      emit();
    },
    act: (name) => {
      if (name === 'forceDaemon') { state.daemon.nextTickIn = 1; emit(); }
    },
    approveDream: (id) => {
      // Optimistic UI: flip local state, fire POST, refetch to confirm.
      const d = state.dreams.find((x) => x.id === id);
      if (d) { d.status = 'approved'; d.appliedAt = hms(); emit(); }
      fetch(`/api/v1/dreams/${id}/approve`, { method: 'POST' })
        .then(() => _pollDreams())
        .catch(() => {});
    },
    rejectDream: (id) => {
      const d = state.dreams.find((x) => x.id === id);
      if (d) { d.status = 'rejected'; emit(); }
      fetch(`/api/v1/dreams/${id}/reject`, { method: 'POST' })
        .then(() => _pollDreams())
        .catch(() => {});
    },
  };

  // ── Live-data polling ─────────────────────────────────────────
  // A successful fetch owns the surface, including empty arrays,
  // empty strings, zeroes, and explicit nulls. A failed fetch marks
  // that surface offline instead of preserving old costume data.

  const _pollDaemon = async () => {
    try {
      const r = await fetch('/api/v1/daemon/state');
      if (!r.ok) { markOffline('daemon', r.status); return; }
      const d = await r.json();
      // Honest unreachable from the real-state proxy — don't overlay stale data.
      if (d && d.status === 'unreachable') { markOffline('daemon', 'unreachable'); return; }
      markLive('daemon');
      // Tolerate BOTH shapes during rollout:
      //   flag-off log-scrape: cycle, lastTick, currentThought
      //   flag-on real state:  cycle_count, last_cycle, last_thought
      const cycle = (typeof d.cycle === 'number') ? d.cycle
        : (typeof d.cycle_count === 'number') ? d.cycle_count : null;
      if (typeof cycle === 'number') state.daemon.cycle = cycle;
      const lastTick = d.lastTick || d.last_cycle;
      state.daemon.lastTick = typeof lastTick === 'string' ? lastTick : '';
      const thought = d.currentThought || d.last_thought;
      state.daemon.currentThought = typeof thought === 'string' ? thought : '';
      state.daemon.scratchpad = Array.isArray(d.scratchpad) ? d.scratchpad : [];
      // Real felt-state + liveness for the slime avatar (flag-on real shape).
      // Covenant: only ever the real reading; neutral/absent => the calm baseline.
      state.daemon.valence = d.valence && typeof d.valence === 'object' ? d.valence : null;
      state.daemon.status = typeof d.status === 'string' ? d.status : 'unknown';
      const _rl = d.reasoning_loop;
      state.daemon.stalled = !!(_rl && _rl.cycle_stalled) || d.status === 'stalled' || d.status === 'stopped';
      // Ledger admission health rides the same poll: omitted or
      // unexplained life must reach the VISIBLE cockpit, not only the
      // API payload (council round ten: withholding must be LOUD; Codex
      // validation 2026-08-27: both clients discarded ledger_admission,
      // so a terminally refused envelope left the UI green).
      const _adm = d.ledger_admission;
      state.daemon.ledgerAttention = !!(_adm && _adm.attention);
      emit();
    } catch (e) { markOffline('daemon', e); }
  };

  const _pollCards = async () => {
    try {
      const r = await fetch('/api/v1/cards');
      if (!r.ok) { markOffline('cards', r.status); return; }
      const d = await r.json();
      if (!Array.isArray(d.cards)) return;
      markLive('cards');
      // Only surface still-open cards as "approvals" (the red-badged
      // queue). Resolved cards stay in the API response for an
      // eventual "recent activity" view but don't clutter the badge.
      const open = d.cards.filter((c) => c.status === 'open' || c.status === 'deferred');
      state.approvals = open.map((c) => ({
        id: c.id,
        cmd: c.cmd || c.action,
        reason: c.reason || '',
        risk: (c.cmd && (c.cmd.includes('rm ') || c.cmd.includes('checkout') || c.cmd.includes('sudo'))) ? 'high' : 'low',
        ts: new Date((c.created_at || 0) * 1000).toTimeString().slice(0, 8),
      }));
      emit();
    } catch (e) { markOffline('cards', e); }
  };

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

  const _pollGpu = async () => {
    try {
      const r = await fetch('/api/v1/gpu');
      if (!r.ok) { markOffline('gpu', r.status); return; }
      const d = await r.json();
      markLive('gpu');
      if (typeof d.vramUsed === 'number') state.gpu.vramUsed = d.vramUsed;
      if (typeof d.vramTotal === 'number') state.gpu.vramTotal = d.vramTotal;
      if (typeof d.temp === 'number') state.gpu.temp = d.temp;
      if (typeof d.power === 'number') state.gpu.power = d.power;
      if (typeof d.util === 'number') state.gpu.util = d.util;
      emit();
    } catch (e) { markOffline('gpu', e); }
  };

  const _pollSignals = async () => {
    try {
      const r = await fetch('/api/v1/signals');
      if (!r.ok) { markOffline('signals', r.status); return; }
      const d = await r.json();
      markLive('signals');
      if (Array.isArray(d.signals)) {
        // Unconditional replace: showing an explicit no-source note is
        // more honest than pretending a live source exists.
        if (d.signals.length) {
          state.signals = d.signals;
        } else {
          state.signals = [{
            t: '', kind: 'info',
            text: '(no ambient sources configured — iphone / perception_cache not writing)',
            src: 'system',
          }];
        }
        emit();
      }
    } catch (e) { markOffline('signals', e); }
  };

  const _pollSoul = async () => {
    try {
      const r = await fetch('/api/v1/soul');
      if (!r.ok) { markOffline('soul', r.status); return; }
      const d = await r.json();
      markLive('soul');
      state.soul.base = typeof d.base === 'string' ? d.base : '';
      state.soul.local = typeof d.local === 'string' ? d.local : '';
      emit();
    } catch (e) { markOffline('soul', e); }
  };

  const _pollMemory = async () => {
    try {
      const r = await fetch('/api/v1/memory');
      if (!r.ok) { markOffline('memory', r.status); return; }
      const d = await r.json();
      markLive('memory');
      state.memory.stats = d.stats && typeof d.stats === 'object' ? d.stats : { raw: 0, daily: 0, core: 0 };
      state.memory.hits = Array.isArray(d.hits) ? d.hits : [];
      emit();
    } catch (e) { markOffline('memory', e); }
  };

  const _pollLivedMemory = async () => {
    try {
      const r = await fetch('/api/v1/lived-memory');
      if (!r.ok) { markOffline('livedMemory', r.status); return; }
      const d = await r.json();
      markLive('livedMemory');
      if (Array.isArray(d.episodes)) state.livedMemory.episodes = d.episodes;
      if (Array.isArray(d.edges)) state.livedMemory.edges = d.edges;
      if (Array.isArray(d.echoes)) state.livedMemory.echoes = d.echoes;
      if (Array.isArray(d.predictions)) state.livedMemory.predictions = d.predictions;
      state.livedMemory.provenance = d.provenance && typeof d.provenance === 'object'
        ? d.provenance : { maez_authored: 0, project_doc: 0, total: 0 };
      state.livedMemory.counts = d.counts && typeof d.counts === 'object'
        ? d.counts : { episodes: 0, edges: 0, echoes: 0, predictions: 0 };
      emit();
    } catch (e) { markOffline('livedMemory', e); }
  };

  const _pollDreams = async () => {
    try {
      const r = await fetch('/api/v1/dreams');
      if (!r.ok) { markOffline('dreams', r.status); return; }
      const d = await r.json();
      markLive('dreams');
      state.dreams = Array.isArray(d.dreams) ? d.dreams : [];
      emit();
    } catch (e) { markOffline('dreams', e); }
  };

  const _pollIdentity = async () => {
    try {
      const r = await fetch('/api/v1/identity');
      if (!r.ok) { markOffline('identity', r.status); return; }
      const d = await r.json();
      markLive('identity');
      state.identity.owner = d.owner && typeof d.owner === 'object' ? d.owner : {};
      state.identity.machine = d.machine && typeof d.machine === 'object' ? d.machine : {};
      state.identity.policies = d.policies && typeof d.policies === 'object' ? d.policies : {};
      state.identity.redditSubs = Array.isArray(d.redditSubs) ? d.redditSubs : [];
      emit();
    } catch (e) { markOffline('identity', e); }
  };

  const _pollRouter = async () => {
    try {
      const r = await fetch('/api/v1/router');
      if (!r.ok) { markOffline('router', r.status); return; }
      const d = await r.json();
      markLive('router');
      state.router.totals = d.totals && typeof d.totals === 'object'
        ? d.totals : { local: 0, claude: 0, bytesIn: 0, bytesOut: 0, costUsd: 0.0 };
      state.router.window = Array.isArray(d.window) ? d.window : [];
      emit();
    } catch (e) { markOffline('router', e); }
  };

  const _pollLogs = async () => {
    for (const name of ['maez', 'cognition', 'evolution']) {
      try {
        const r = await fetch(`/api/v1/logs/${name}`);
        if (!r.ok) { markOffline(`logs:${name}`, r.status); continue; }
        const d = await r.json();
        markLive(`logs:${name}`);
        state.logs[name] = Array.isArray(d.lines) ? d.lines : [];
      } catch (e) { markOffline(`logs:${name}`, e); }
    }
    emit();
  };

  const _pollChatSessions = async () => {
    try {
      const r = await fetch('/api/v1/chat/sessions');
      if (!r.ok) { markOffline('chat', r.status); return; }
      const d = await r.json();
      markLive('chat');
      if (state.chat._awaitingReply || state.chat.streaming) {
        emit();
        return;
      }
      state.chat.sessions = Array.isArray(d.sessions) ? d.sessions : [];
      state.chat.activeSessionId = d.activeSessionId || (state.chat.sessions[0] && state.chat.sessions[0].id) || '';
      emit();
    } catch (e) { markOffline('chat', e); }
  };

  // Kick off immediately, then poll each on its own cadence. Chose
  // cadences by staleness tolerance: daemon/gpu/cards update often,
  // soul/identity/logs rarely, memory/dreams in the middle.
  _pollDaemon(); _pollCards(); _pollGpu(); _pollServices();
  _pollSignals(); _pollMemory(); _pollLivedMemory(); _pollDreams(); _pollSoul();
  _pollIdentity(); _pollRouter(); _pollLogs(); _pollChatSessions();
  setInterval(_pollDaemon, 5000);
  setInterval(_pollCards, 10000);
  setInterval(_pollGpu, 5000);
  setInterval(_pollServices, 15000);
  setInterval(_pollSignals, 10000);
  setInterval(_pollMemory, 30000);
  setInterval(_pollLivedMemory, 60000);
  setInterval(_pollDreams, 20000);
  setInterval(_pollSoul, 120000);
  setInterval(_pollIdentity, 300000);
  setInterval(_pollRouter, 20000);
  setInterval(_pollLogs, 15000);
  setInterval(_pollChatSessions, 20000);

  return api;
})();

// hook
function useSim() {
  const [, set] = React.useState(0);
  React.useEffect(() => SIM.subscribe(() => set((x) => x + 1)), []);
  return SIM;
}

window.SIM = SIM;
window.useSim = useSim;
