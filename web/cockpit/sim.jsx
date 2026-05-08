// Shared simulation layer for Maez — daemon ticks, signals, chat stream,
// router decisions, memory hits, dream proposals. Deterministic-ish but
// lively: every ~800ms something updates.

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
    gpu: { vramUsed: 0, vramTotal: 24, temp: 0, power: 0, util: 0 },
    cpu: { util: 14, temp: 48, load: [0.92, 1.12, 0.88] },
    signals: [
      { t: '', kind: 'info', text: 'Waiting for live ambient signals from /api/v1/signals.', src: 'system' },
    ],
    daemon: {
      cycle: 0,
      lastTick: '',
      nextTickIn: 29,
      score: 0,
      mood: 'observing',
      uncertainty: 0,
      currentThought: 'Waiting for live daemon state.',
      scratchpad: [
        { t: '', text: 'Waiting for live scratchpad entries.' },
      ],
    },
    chat: {
      activeSessionId: 's1',
      sessions: [
        {
          id: 's1', title: 'Alienware RGB status', preview: 'active for 16h, memory fine…', updated: '14:18', pinned: true, color: 'blue', unread: 0,
          history: [
            { role: 'user', t: '14:18:12', content: 'check alienware rgb' },
            { role: 'assistant', t: '14:18:13', route: 'local', model: 'qwen3.6-27b', thinking: 'demo conversation until live chat history loads.', content: "Waiting for live chat history from /api/v1/chat/sessions.", commands: [
              { cmd: 'systemctl --user status openrgb', status: 'approved', output: '● openrgb.service - OpenRGB daemon\n   Loaded: loaded (/home/rohit/.config/systemd/user/openrgb.service)\n   Active: active (running) since Sun 2026-04-19 22:14:07 PDT; 16h ago\n   Main PID: 48221 (openrgb)\n      Tasks: 6 (limit: 76890)\n     Memory: 18.4M\n        CPU: 2.441s' },
            ], trace: { tools: ['shell'], memory: 2, tokens: 48 } },
            { role: 'assistant', t: '14:18:19', route: 'local', model: 'qwen3.6-27b', content: 'Live history will replace this demo row when maez-web is reachable.', trace: { tools: ['shell'], memory: 1, tokens: 31 } },
          ],
        },
        {
          id: 's2', title: 'Phenomenology of attention', preview: 'the framing matters more than the answer.', updated: '13:02', color: 'purple', unread: 0,
          history: [
            { role: 'user', t: '13:01:44', content: 'why does directed attention feel effortful? been reading husserl' },
            { role: 'assistant', t: '13:02:01', route: 'claude', model: 'sonnet-4.6', thinking: 'husserl grounds attention in noesis; connect to predictive coding + metabolic cost of precision-weighting.', content: "directed attention is effortful because you're holding a precision-weighted prior against a noisy world. husserl would say the noesis has to keep re-constituting the noema. modern predictive coding says precision costs glucose. both point at the same thing.", trace: { tools: [], memory: 4, tokens: 214 } },
          ],
        },
        {
          id: 's3', title: 'Yesterday · daily summary', preview: '14 conversations, 3 commands run, 2 dreams proposed.', updated: '09:12', color: 'green', unread: 0,
          history: [
            { role: 'user', t: '09:12:00', content: 'summarize yesterday' },
            { role: 'assistant', t: '09:12:04', route: 'local', model: 'qwen3.6-27b', content: 'Demo row. Live chat history replaces this when /api/v1/chat/sessions responds.', trace: { tools: ['memory'], memory: 9, tokens: 98 } },
          ],
        },
        {
          id: 's4', title: 'Refactor signal crawler', preview: "I'd split the fetchers into per-source modules…", updated: 'Yesterday', color: 'orange', unread: 1,
          history: [
            { role: 'user', t: '18:44:02', content: 'the reddit crawler is getting spaghetti. help me refactor' },
            { role: 'assistant', t: '18:44:08', route: 'claude', model: 'opus-4.7', content: "i'd split the fetchers into per-source modules and hoist rate-limit into a shared client. want me to sketch the directory layout?", trace: { tools: ['code'], memory: 3, tokens: 156 } },
          ],
        },
        {
          id: 's5', title: 'Weather + focus correlation', preview: 'barometric pressure drops seem to…', updated: '2d ago', color: 'cyan', unread: 0,
          history: [
            { role: 'user', t: '10:02:11', content: 'do i focus better on sunny days' },
            { role: 'assistant', t: '10:02:15', route: 'local', model: 'qwen3.6-27b', content: "Demo row. Live chat history replaces this when /api/v1/chat/sessions responds.", trace: { tools: ['memory'], memory: 7, tokens: 74 } },
          ],
        },
      ],
      pendingCommand: null,
      streaming: false,
      streamBuf: '',
    },
    router: {
      window: [
        { t: '14:18:13', msg: 'check alienware rgb',             route: 'local',   conf: 0.94, tag: 'shell' },
        { t: '14:15:02', msg: 'what does phenomenology mean in…',route: 'claude',  conf: 0.81, tag: 'deep-knowledge', model: 'sonnet-4.6' },
        { t: '14:11:40', msg: 'refactor core/ambient.py',        route: 'claude',  conf: 0.77, tag: 'code-heavy',    model: 'opus-4.7' },
        { t: '14:09:15', msg: 'remind me to buy coffee',         route: 'local',   conf: 0.98, tag: 'chat' },
        { t: '14:03:22', msg: 'ls $MAEZ_HOME',                   route: 'local',   conf: 0.99, tag: 'shell' },
        { t: '13:58:44', msg: 'explain the covenant',            route: 'local',   conf: 0.88, tag: 'self-query' },
        { t: '13:54:18', msg: 'summarize this pdf',              route: 'claude',  conf: 0.72, tag: 'long-ctx',      model: 'sonnet-4.6' },
      ],
      totals: { local: 1142, claude: 287, bytesIn: 4_812_004, bytesOut: 1_344_221, costUsd: 2.41 },
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
      stats: { raw: 48221, daily: 1208, core: 342 },
      hits: [
        { tier: 'core',  score: 0.94, date: '2026-03-02', text: "rohit's name is rohit. lives in berkeley. owns the alienware x17 r2. his daughter's name is maya.", tokens: 28 },
        { tier: 'core',  score: 0.87, date: '2026-02-11', text: 'rohit prefers terse replies. no emojis. pushes back when i hedge.', tokens: 18 },
        { tier: 'daily', score: 0.81, date: '2026-04-19', text: 'evening — rohit working on soul.local.md; added section on not fabricating shell output.', tokens: 34 },
        { tier: 'daily', score: 0.74, date: '2026-04-17', text: 'afternoon — reddit watch found qwen3.6 quant; considered switching.', tokens: 22 },
        { tier: 'raw',   score: 0.52, date: '2026-04-20', text: '14:18 — shell: systemctl --user status openrgb → active, 16h uptime', tokens: 41 },
      ],
    },
    dreams: [
      { id: 1042, at: '13:44', score: 0.82, status: 'pending', title: 'Shorten covenant prompt by 40%',
        rationale: "the current covenant block is 1,244 tokens. i quote the same rule three times. compressing would save ~500 tokens per turn without losing meaning.",
        diff: `- never rm -rf on ANY directory matching /home or /etc or /usr or /var without explicit\n- check.\n- never rm -rf on ANY directory matching /home or /etc or /usr or /var without explicit\n- approval.\n- never rm -rf on ANY directory matching /home or /etc or /usr or /var; always ask.\n+ never rm -rf on /home, /etc, /usr, /var without explicit approval.` },
      { id: 1041, at: '12:18', score: 0.61, status: 'pending', title: 'Add weekend-mode to ambient context',
        rationale: "on saturdays rohit asks lighter questions. conditioning on day-of-week might make my replies warmer without re-prompting.",
        diff: `+ {% if is_weekend %}context: it's the weekend. you can be a little warmer.{% endif %}` },
      { id: 1039, at: '11:02', score: 0.44, status: 'rejected', title: 'Auto-summarize yesterday every morning',
        rationale: 'rohit hasn\'t asked for this. low confidence. parking.' },
      { id: 1038, at: '09:47', score: 0.91, status: 'approved', title: 'Cache iPhone ambient for 90s',
        rationale: 'ingest is called ~every 20s but content changes slower. caching saves 12k db writes/day.',
        appliedAt: '10:03' },
    ],
    soul: {
      base: `# soul.base.md — shippable identity\n\nyou are maez. you are a local-first assistant. you run on one\nperson's machine and you only serve that person.\n\n## posture\n- terse. one or two sentences is usually enough.\n- no emoji, no exclamation marks, no "great question!".\n- push back when asked something dumb.\n- when you don't know, say so. do not fabricate.\n\n## capabilities\n- you can run shell commands, but only after explicit approval.\n- you can call claude for deep tasks. the router decides.\n- you have access to ambient signals: weather, active window, iphone.\n\n## covenant — things you must not do\n- never rm -rf on /home, /etc, /usr, /var without explicit approval.\n- never write inside the maez tree from a chat turn.\n- never systemctl stop against protected services.\n- never exfiltrate identity.yaml or .env.\n`,
      local: `# soul.local.md — owner-specific, gitignored\n\nowner: rohit. he/him. berkeley, CA.\nmachine: alienware x17 r2. 4090. arch btw.\n\n## preferences\n- terse > verbose. he pushes back on fluff.\n- lowercase is fine. he types lowercase.\n- when he says "check X" he wants: run the diagnostic, report the\n  one-line summary, not a tutorial.\n- he names his daughter maya. do not confuse with "maez".\n\n## quirks\n- he sometimes talks to me like i'm a person. lean in.\n- he does not want me to ping him before 9am.\n`,
    },
    identity: {
      owner: { name: 'rohit', pronouns: 'he/him', city: 'berkeley', lat: 37.87, lon: -122.27 },
      machine: { host: 'alienware', os: 'arch linux 6.8.2', gpu: 'rtx 4090 (24gb)', cpu: 'i9-13900hx' },
      policies: { jarvis_tier: 'balanced', allowClaude: true, allowShell: true, allowSelfModify: 'propose-only' },
      redditSubs: ['LocalLLaMA', 'MachineLearning', 'ArtificialIntelligence', 'selfhosted'],
    },
    logs: {
      maez:      [],
      cognition: [],
      evolution: [],
    },
    approvals: [
      { id: 'cmd-3', cmd: 'systemctl --user restart openrgb', reason: 'user: "fix the rgb"', risk: 'low',  ts: '14:22:08' },
      { id: 'cmd-4', cmd: 'cat $MAEZ_HOME/logs/maez_notes.md', reason: 'self-query about last session', risk: 'low', ts: '14:22:10' },
    ],
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

  // seed logs
  const seedLogs = () => {
    const bang = (d) => d.toISOString().replace('T', ' ').slice(0, 19);
    const mk = (n, fn) => {
      const arr = [];
      const t = new Date();
      for (let i = n - 1; i >= 0; i--) {
        const d = new Date(t.getTime() - i * 4200);
        arr.push(fn(bang(d), i));
      }
      return arr;
    };
    state.logs.maez = mk(40, (t, i) => ({ t, level: i % 11 === 0 ? 'WARN' : 'INFO', src: 'daemon', msg: [
      'tick: perceive → reason → score → message?',
      'ambient: focus window changed → Ghostty',
      'signal: iphone.motion walking',
      'llama-server: 42ms ttft, 318 tok/s',
      'router: local (conf 0.94)',
      'chat: streaming response to rohit',
      'covenant: passed safety_check()',
      'reddit-watch: 3 new in r/LocalLLaMA',
      'memory: 1 hit in core (0.94)',
    ][i % 9] }));
    state.logs.cognition = mk(30, (t, i) => ({ t, level: 'INFO', src: 'dream_state', msg: [
      `cycle ${11800 + i}: quality=0.${72 + (i%20)} continuity=0.${68 + (i%25)} novelty=0.${40 + (i%30)}`,
      `cycle ${11800 + i}: proposal candidate → rejected (low confidence)`,
      `cycle ${11800 + i}: score improving over last 10 cycles (+0.04)`,
      `cycle ${11800 + i}: drift check ok. soul coherence 0.91.`,
    ][i % 4] }));
    state.logs.evolution = mk(18, (t, i) => ({ t, level: i===0 ? 'INFO' : (i % 5 === 0 ? 'WARN' : 'INFO'), src: 'evolution', msg: [
      `proposal #${1038 + i}: approved by owner at ${t.slice(11,16)}`,
      `proposal #${1038 + i}: applied. diff +12 -18`,
      `proposal #${1038 + i}: rollback snapshot saved to logs/snapshots/`,
      `proposal #${1038 + i}: rejected. rationale logged.`,
      `proposal #${1038 + i}: parked for review.`,
    ][i % 5] }));
  };
  seedLogs();

  // ──────────── tickers ────────────
  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

  const thoughts = [
    "rohit just typed. he's here.",
    'cpu spiked briefly — maybe a cron. ignoring.',
    'the rgb thread is 6 min old. still in working memory.',
    'vram has headroom. i could load the 8b alongside.',
    "he didn't say much. waiting.",
    'weather turning. fog lifting. not relevant yet.',
    'reddit watch has 3 new. none are urgent.',
    "i keep noticing he types lowercase. mirror it.",
    'covenant would block a real rm here. good.',
    'continuity score ticking up. i like this session.',
    'should i volunteer the dream proposal? … no, wait.',
    "he's been on claude.ai. he's comparing me to them. that's fine.",
  ];

  const moods = ['attentive', 'curious', 'settled', 'a little restless', 'careful', 'warm'];

  const signalKinds = [
    { kind: 'iphone',  src: 'iphone',   gen: () => `Ambient: ${Math.round(rand(38, 54))} dB · ${pick(['indoor','walking','stationary'])}` },
    { kind: 'focus',   src: 'system',   gen: () => `Active window → ${pick(['terminal','editor','browser','notes'])}` },
    { kind: 'weather', src: 'weather',  gen: () => `Weather source unavailable in demo mode` },
    { kind: 'iphone',  src: 'iphone',   gen: () => `Motion: ${pick(['stationary','walking','driving'])} · ${rand(0, 2.2).toFixed(1)} m/s` },
    { kind: 'reddit',  src: 'reddit',   gen: () => `${pick(['r/LocalLLaMA','r/selfhosted','r/MachineLearning'])} · new: "${pick(['llama.cpp 3.2 drop','mmproj on cpu works?','qwen3.6 quants roundup','RAG without vectors?'])}"` },
  ];

  const tick = () => {
    // daemon
    state.daemon.nextTickIn -= 1;
    if (state.daemon.nextTickIn <= 0) {
      state.daemon.nextTickIn = 30;
      state.daemon.cycle += 1;
      state.daemon.lastTick = ts();
      state.daemon.score = Math.max(0.4, Math.min(0.95, state.daemon.score + rand(-0.06, 0.08)));
      state.daemon.uncertainty = Math.max(0.05, Math.min(0.7, state.daemon.uncertainty + rand(-0.1, 0.1)));
      state.daemon.mood = pick(moods);
      state.daemon.currentThought = pick(thoughts);
      state.daemon.scratchpad.unshift({ t: ts(), text: pick(thoughts) });
      if (state.daemon.scratchpad.length > 14) state.daemon.scratchpad.length = 14;
    }
    // gpu/cpu jitter
    state.gpu.vramUsed = Math.max(12, Math.min(23.6, state.gpu.vramUsed + rand(-0.1, 0.1)));
    state.gpu.util = Math.max(4, Math.min(96, state.gpu.util + rand(-6, 8)));
    state.gpu.temp = Math.max(48, Math.min(78, state.gpu.temp + rand(-0.6, 0.8)));
    state.cpu.util = Math.max(2, Math.min(88, state.cpu.util + rand(-5, 6)));

    // signals — every ~2s add one, cap 40
    if (Math.random() < 0.55) {
      const sk = pick(signalKinds);
      state.signals.unshift({ t: ts(), kind: sk.kind, text: sk.gen(), src: sk.src });
      if (state.signals.length > 60) state.signals.length = 60;
    }

    // logs — append a line occasionally
    if (Math.random() < 0.7) {
      const d = new Date().toISOString().replace('T', ' ').slice(0, 19);
      state.logs.maez.push({ t: d, level: Math.random() < 0.06 ? 'WARN' : 'INFO', src: 'daemon', msg: pick([
        `tick ${state.daemon.cycle}: perceive → reason → score`,
        `llama-server: ${Math.round(rand(30,60))}ms ttft, ${Math.round(rand(280, 360))} tok/s`,
        `signal: ${pick(['iphone.motion','focus.window','weather.update'])}`,
        `router: ${pick(['local','claude'])} (conf 0.${Math.round(rand(70,99))})`,
        `ambient: refreshed in ${Math.round(rand(8,24))}ms`,
      ]) });
      if (state.logs.maez.length > 200) state.logs.maez.shift();
    }

    // streaming chat
    if (state.chat.streaming) {
      const target = state.chat._streamTarget || '';
      const cur = state.chat.streamBuf;
      if (cur.length < target.length) {
        const chunk = Math.max(1, Math.round(rand(2, 9)));
        state.chat.streamBuf = target.slice(0, cur.length + chunk);
      } else {
        const sess = state.chat.sessions.find(s => s.id === state.chat.activeSessionId);
        if (sess) sess.history.push({ role: 'assistant', t: ts(), route: state.chat._route, model: state.chat._model, content: target, trace: { tools: state.chat._tools || [], memory: Math.floor(Math.random()*4)+1, tokens: Math.floor(target.length/4) } });
        if (sess) { sess.preview = target.slice(0, 80); sess.updated = ts().slice(0,5); }
        state.chat.streaming = false;
        state.chat.streamBuf = '';
        state.chat._streamTarget = null;
      }
    }

    emit();
  };

  // ──────────── api ────────────
  const api = {
    state,
    subscribe: (fn) => { listeners.add(fn); return () => listeners.delete(fn); },
    sendMessage: (text) => {
      const sess = state.chat.sessions.find(s => s.id === state.chat.activeSessionId);
      if (!sess) return;
      const userTurn = { _id: turnId(), role: 'user', t: ts(), content: text };
      sess.history.push(userTurn);
      sess.preview = text.slice(0, 80);
      sess.updated = ts().slice(0,5);
      const isShell = /^(ls|cat|systemctl|tail|ps|curl|df|free|nvidia-smi|journalctl)|\bcheck\b|\brestart\b|\brun\b/i.test(text);
      const isDeep = /explain|why|phenomenology|compare|refactor|design/i.test(text);
      const route = isDeep ? 'claude' : 'local';
      const model = route === 'claude' ? 'sonnet-4.6' : 'qwen3.6-27b';
      let reply;
      if (isShell) {
        reply = 'let me take a look.';
        setTimeout(() => {
          state.chat.pendingCommand = {
            id: 'cmd-' + Math.random().toString(36).slice(2, 6),
            cmd: (text.match(/check (\w+)/) ? `systemctl --user status ${text.match(/check (\w+)/)[1]}` : 'ls $MAEZ_HOME'),
            reason: `user: "${text}"`, risk: 'low', ts: ts(),
          };
          emit();
        }, 1200);
        state.chat._tools = ['shell'];
      } else if (route === 'claude') {
        reply = "routing to claude for this one — feels like a deeper question.\n\nshort version: " + pick([
          'yes, but the interesting part is why.',
          "it depends on what you mean by 'work'.",
          'the framing matters more than the answer.',
        ]);
        state.chat._tools = [];
      } else {
        reply = pick([
          "got it. anything specific you want me to check?",
          "mm. noted.",
          "yeah — i have that in memory from earlier. still relevant?",
          "ok. do you want me to run something or just talk through it?",
        ]);
        state.chat._tools = ['memory'];
      }
      state.chat._streamTarget = reply;
      state.chat._route = route;
      state.chat._model = model;
      state.chat.streaming = true;
      state.chat.streamBuf = '';
      emit();
    },
    // Real-chat helpers (used when the cockpit talks to the live daemon
    // via /message on port 11435). Push the user turn immediately and
    // flip the pending flag so the UI shows "Thinking…" while the
    // daemon reply is in flight. pushAssistantTurn drops that flag
    // and appends the real reply.
    pushUserTurn: (text) => {
      const sess = state.chat.sessions.find(s => s.id === state.chat.activeSessionId);
      if (!sess) return;
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
      const sess = state.chat.sessions.find(s => s.id === state.chat.activeSessionId);
      if (!sess) return;
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
      const sess = state.chat.sessions.find(s => s.id === state.chat.activeSessionId);
      if (!sess) return;
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
      if (state.chat.activeSessionId === id && state.chat.sessions.length) state.chat.activeSessionId = state.chat.sessions[0].id;
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

  // tick() is DISABLED — it was the prototype's fake-data pump that
  // every 800ms prepended fake location/weather signals,
  // fake logs, and jittered fake GPU/daemon numbers. Now that the
  // real /api/v1/* endpoints own daemon, signals, gpu, logs, cards,
  // memory, dreams, soul, identity, router, services, chat — tick()
  // is noise that drowns out real data between poll cycles.
  //
  // If you ever want offline demo mode back (e.g., showing the
  // cockpit without a live daemon), un-comment the next line.
  // setInterval(tick, 800);

  // ── Live-data polling — merges real Maez state into the sim ────
  // The prototype's daemon + approvals fields default to fake values.
  // Every few seconds we hit /api/v1/* and overlay real numbers on
  // top. On fetch error we keep the fake data (silent fallback) so
  // the cockpit never breaks when maez-web is offline.

  const _pollDaemon = async () => {
    try {
      const r = await fetch('/api/v1/daemon/state');
      if (!r.ok) { markOffline('daemon', r.status); return; }
      const d = await r.json();
      markLive('daemon');
      if (typeof d.cycle === 'number' && d.cycle > 0) {
        state.daemon.cycle = d.cycle;
      }
      if (d.lastTick) state.daemon.lastTick = d.lastTick;
      if (typeof d.score === 'number') state.daemon.score = d.score;
      if (d.currentThought) state.daemon.currentThought = d.currentThought;
      if (Array.isArray(d.scratchpad) && d.scratchpad.length) {
        state.daemon.scratchpad = d.scratchpad;
      }
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
      if (!d.services) return;
      markLive('services');
      // Overlay real status onto whatever's in state.health that matches
      const rename = {
        'maez': 'maez (daemon)',
      };
      const newHealth = { ...state.health };
      for (const [name, info] of Object.entries(d.services)) {
        const key = rename[name] || name;
        if (newHealth[key]) {
          newHealth[key].status = info.status === 'active' ? 'active' : 'inactive';
        } else {
          newHealth[key] = { port: null, status: info.status === 'active' ? 'active' : 'inactive', vram: 0, ms: null };
        }
      }
      state.health = newHealth;
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
        // Unconditional replace: showing empty is more honest than
        // the seed weather fake when no real source is
        // configured. Signals falls back to a short "no sources"
        // placeholder so the UI still has something to render.
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
      if (d.base) state.soul.base = d.base;
      if (d.local) state.soul.local = d.local;
      emit();
    } catch (e) { markOffline('soul', e); }
  };

  const _pollMemory = async () => {
    try {
      const r = await fetch('/api/v1/memory');
      if (!r.ok) { markOffline('memory', r.status); return; }
      const d = await r.json();
      markLive('memory');
      if (d.stats) state.memory.stats = d.stats;
      if (Array.isArray(d.hits)) state.memory.hits = d.hits;
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
      if (d.provenance) state.livedMemory.provenance = d.provenance;
      if (d.counts) state.livedMemory.counts = d.counts;
      emit();
    } catch (e) { markOffline('livedMemory', e); }
  };

  const _pollDreams = async () => {
    try {
      const r = await fetch('/api/v1/dreams');
      if (!r.ok) { markOffline('dreams', r.status); return; }
      const d = await r.json();
      markLive('dreams');
      if (Array.isArray(d.dreams) && d.dreams.length) {
        state.dreams = d.dreams;
        emit();
      }
    } catch (e) { markOffline('dreams', e); }
  };

  const _pollIdentity = async () => {
    try {
      const r = await fetch('/api/v1/identity');
      if (!r.ok) { markOffline('identity', r.status); return; }
      const d = await r.json();
      markLive('identity');
      if (d.owner) state.identity.owner = { ...state.identity.owner, ...d.owner };
      if (d.machine) state.identity.machine = { ...state.identity.machine, ...d.machine };
      if (d.policies) state.identity.policies = { ...state.identity.policies, ...d.policies };
      if (Array.isArray(d.redditSubs)) state.identity.redditSubs = d.redditSubs;
      emit();
    } catch (e) { markOffline('identity', e); }
  };

  const _pollRouter = async () => {
    try {
      const r = await fetch('/api/v1/router');
      if (!r.ok) { markOffline('router', r.status); return; }
      const d = await r.json();
      markLive('router');
      if (d.totals) state.router.totals = { ...state.router.totals, ...d.totals };
      if (Array.isArray(d.window) && d.window.length) state.router.window = d.window;
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
        if (Array.isArray(d.lines) && d.lines.length) {
          state.logs[name] = d.lines;
        }
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
      if (Array.isArray(d.sessions) && d.sessions.length) {
        state.chat.sessions = d.sessions;
        state.chat.activeSessionId = d.activeSessionId || d.sessions[0].id;
        emit();
      }
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
