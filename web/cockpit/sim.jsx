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

  const state = {
    health: {
      'llama-server':        { port: 8080,  status: 'active', vram: 18.2, ms: 42 },
      'llama-server-vision': { port: 8081,  status: 'active', vram: 4.1,  ms: 71 },
      'maez (daemon)':       { port: null,  status: 'active', vram: 0,    ms: null },
      'maez-web':            { port: 11437, status: 'active', vram: 0,    ms: 18 },
      'telegram-bot':        { port: null,  status: 'active', vram: 0,    ms: null },
      'iphone-ingest':       { port: 11437, status: 'active', vram: 0,    ms: 24 },
    },
    gpu: { vramUsed: 22.3, vramTotal: 24, temp: 62, power: 180, util: 47 },
    cpu: { util: 14, temp: 48, load: [0.92, 1.12, 0.88] },
    signals: [
      { t: '14:22:03', kind: 'focus',   text: 'Active window → Ghostty · maez_chat.py',  src: 'macos' },
      { t: '14:21:47', kind: 'weather', text: 'Berkeley · 58°F · light fog', src: 'openweather' },
      { t: '14:21:31', kind: 'iphone',  text: 'Motion: walking · 0.8 m/s · heading 240°', src: 'iphone' },
      { t: '14:21:02', kind: 'iphone',  text: 'Ambient: 42 dB · indoor · stationary', src: 'iphone' },
      { t: '14:20:28', kind: 'reddit',  text: 'r/LocalLLaMA · new: "Qwen3.6 + mmproj on 24GB"', src: 'reddit' },
      { t: '14:19:55', kind: 'focus',   text: 'Active window → Arc · claude.ai',  src: 'macos' },
      { t: '14:19:12', kind: 'iphone',  text: 'Battery: 67% · charging · 23°C', src: 'iphone' },
    ],
    daemon: {
      cycle: 11847,
      lastTick: ts(),
      nextTickIn: 29,
      score: 0.72,
      mood: 'attentive',
      uncertainty: 0.31,
      currentThought: 'rohit just opened the chat. last turn asked about rgb — i should still have that context in working memory. checking vram headroom before Claude call.',
      scratchpad: [
        { t: '14:22:00', text: "rohit's back. 6 min since last turn. good." },
        { t: '14:21:30', text: "cpu load nominal. no fan spike. he's not compiling." },
        { t: '14:20:45', text: "thinking about the rgb thread from this morning — did i resolve it?" },
        { t: '14:19:00', text: "the reddit watch found something interesting. note it but don't interrupt." },
      ],
    },
    chat: {
      activeSessionId: 's1',
      sessions: [
        {
          id: 's1', title: 'Alienware RGB status', preview: 'active for 16h, memory fine…', updated: '14:18', pinned: true, color: 'blue', unread: 0,
          history: [
            { role: 'user', t: '14:18:12', content: 'check alienware rgb' },
            { role: 'assistant', t: '14:18:13', route: 'local', model: 'qwen3.6-35b', thinking: 'user wants status of rgb controller. probably openrgb. check systemd.', content: "let me look — openrgb runs as a user service on your box. checking status.", commands: [
              { cmd: 'systemctl --user status openrgb', status: 'approved', output: '● openrgb.service - OpenRGB daemon\n   Loaded: loaded (/home/rohit/.config/systemd/user/openrgb.service)\n   Active: active (running) since Sun 2026-04-19 22:14:07 PDT; 16h ago\n   Main PID: 48221 (openrgb)\n      Tasks: 6 (limit: 76890)\n     Memory: 18.4M\n        CPU: 2.441s' },
            ], trace: { tools: ['shell'], memory: 2, tokens: 48 } },
            { role: 'assistant', t: '14:18:19', route: 'local', model: 'qwen3.6-35b', content: 'active for 16h, memory fine. zones look healthy — anything specific feel off?', trace: { tools: ['shell'], memory: 1, tokens: 31 } },
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
            { role: 'assistant', t: '09:12:04', route: 'local', model: 'qwen3.6-35b', content: 'yesterday: 14 conversations, mostly about the RGB config and the reddit crawler. 3 shell commands (all approved). 2 dreams — you approved the signal-window change, rejected the memory compaction one. mood: steady, curious by evening.', trace: { tools: ['memory'], memory: 9, tokens: 98 } },
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
            { role: 'assistant', t: '10:02:15', route: 'local', model: 'qwen3.6-35b', content: "from your 6 weeks of signals: barometric pressure drops seem to correlate with shorter deep-work blocks. sunlight itself less so. but the dataset is small.", trace: { tools: ['memory'], memory: 7, tokens: 74 } },
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
        { t: '14:03:22', msg: 'ls /home/rohit/maez',             route: 'local',   conf: 0.99, tag: 'shell' },
        { t: '13:58:44', msg: 'explain the covenant',            route: 'local',   conf: 0.88, tag: 'self-query' },
        { t: '13:54:18', msg: 'summarize this pdf',              route: 'claude',  conf: 0.72, tag: 'long-ctx',      model: 'sonnet-4.6' },
      ],
      totals: { local: 1142, claude: 287, bytesIn: 4_812_004, bytesOut: 1_344_221, costUsd: 2.41 },
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
      { id: 'cmd-4', cmd: 'cat /home/rohit/maez/logs/maez_notes.md', reason: 'self-query about last session', risk: 'low', ts: '14:22:10' },
    ],
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
    { kind: 'focus',   src: 'macos',    gen: () => `Active window → ${pick(['Ghostty · maez_chat.py','Arc · claude.ai','VSCode · ambient.py','Obsidian · notes','Terminal'])}` },
    { kind: 'weather', src: 'openweather', gen: () => `Berkeley · ${Math.round(rand(54, 64))}°F · ${pick(['light fog','clear','overcast','breeze ↗'])}` },
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
      sess.history.push({ role: 'user', t: ts(), content: text });
      sess.preview = text.slice(0, 80);
      sess.updated = ts().slice(0,5);
      const isShell = /^(ls|cat|systemctl|tail|ps|curl|df|free|nvidia-smi|journalctl)|\bcheck\b|\brestart\b|\brun\b/i.test(text);
      const isDeep = /explain|why|phenomenology|compare|refactor|design/i.test(text);
      const route = isDeep ? 'claude' : 'local';
      const model = route === 'claude' ? 'sonnet-4.6' : 'qwen3.6-35b';
      let reply;
      if (isShell) {
        reply = 'let me take a look.';
        setTimeout(() => {
          state.chat.pendingCommand = {
            id: 'cmd-' + Math.random().toString(36).slice(2, 6),
            cmd: (text.match(/check (\w+)/) ? `systemctl --user status ${text.match(/check (\w+)/)[1]}` : 'ls /home/rohit/maez'),
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
      if (sess) sess.history.push({ role: 'assistant', t: ts(), route: 'local', model: 'qwen3.6-35b', commands: [{
        cmd: p.cmd, status: approve ? 'approved' : 'denied',
        output: approve ? '● ok. active (running) since 10:03. memory 18.4M.' : '(skipped — user declined)',
      }], trace: { tools: ['shell'], memory: 0, tokens: 20 } });
      state.chat.pendingCommand = null;
      emit();
    },
    approveQueued: (id, approve) => {
      // approve=true → hits the daemon's health server (port 11435) at
      //   /internal/approve_card/<id>, which runs the full pipeline
      //   approve path (covenant → will-I → execute → mark_done).
      //   Equivalent to typing 'yes' in Telegram; lives in the daemon
      //   process where ActionEngine is.
      // approve=false → maez-web's safe deny (state transition only).
      if (approve === true) {
        fetch(`http://localhost:11435/internal/approve_card/${encodeURIComponent(id)}`, {
          method: 'POST',
        }).catch(() => {});
      } else {
        fetch(`/api/v1/cards/${encodeURIComponent(id)}/deny`, {
          method: 'POST',
        }).catch(() => {});
      }
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
  // every 800ms prepended fake Berkeley/walking/weather signals,
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
      if (!r.ok) return;
      const d = await r.json();
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
    } catch (e) { /* keep fake values */ }
  };

  const _pollCards = async () => {
    try {
      const r = await fetch('/api/v1/cards');
      if (!r.ok) return;
      const d = await r.json();
      if (!Array.isArray(d.cards)) return;
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
    } catch (e) { /* keep fake values */ }
  };

  const _pollServices = async () => {
    try {
      const r = await fetch('/api/v1/services');
      if (!r.ok) return;
      const d = await r.json();
      if (!d.services) return;
      // Overlay real status onto whatever's in state.health that matches
      const rename = {
        'maez': 'maez (daemon)',
        'llama-server-vision': 'llama-server-vision',
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
    } catch (e) { /* keep fake */ }
  };

  const _pollGpu = async () => {
    try {
      const r = await fetch('/api/v1/gpu');
      if (!r.ok) return;
      const d = await r.json();
      if (typeof d.vramUsed === 'number') state.gpu.vramUsed = d.vramUsed;
      if (typeof d.vramTotal === 'number') state.gpu.vramTotal = d.vramTotal;
      if (typeof d.temp === 'number') state.gpu.temp = d.temp;
      if (typeof d.power === 'number') state.gpu.power = d.power;
      if (typeof d.util === 'number') state.gpu.util = d.util;
      emit();
    } catch (e) { /* keep fake */ }
  };

  const _pollSignals = async () => {
    try {
      const r = await fetch('/api/v1/signals');
      if (!r.ok) return;
      const d = await r.json();
      if (Array.isArray(d.signals)) {
        // Unconditional replace: showing empty is more honest than
        // the seed "Berkeley weather" fake when no real source is
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
    } catch (e) { /* keep fake */ }
  };

  const _pollSoul = async () => {
    try {
      const r = await fetch('/api/v1/soul');
      if (!r.ok) return;
      const d = await r.json();
      if (d.base) state.soul.base = d.base;
      if (d.local) state.soul.local = d.local;
      emit();
    } catch (e) { /* keep fake */ }
  };

  const _pollMemory = async () => {
    try {
      const r = await fetch('/api/v1/memory');
      if (!r.ok) return;
      const d = await r.json();
      if (d.stats) state.memory.stats = d.stats;
      if (Array.isArray(d.hits) && d.hits.length) state.memory.hits = d.hits;
      emit();
    } catch (e) { /* keep fake */ }
  };

  const _pollDreams = async () => {
    try {
      const r = await fetch('/api/v1/dreams');
      if (!r.ok) return;
      const d = await r.json();
      if (Array.isArray(d.dreams) && d.dreams.length) {
        state.dreams = d.dreams;
        emit();
      }
    } catch (e) { /* keep fake */ }
  };

  const _pollIdentity = async () => {
    try {
      const r = await fetch('/api/v1/identity');
      if (!r.ok) return;
      const d = await r.json();
      if (d.owner) state.identity.owner = { ...state.identity.owner, ...d.owner };
      if (d.machine) state.identity.machine = { ...state.identity.machine, ...d.machine };
      if (d.policies) state.identity.policies = { ...state.identity.policies, ...d.policies };
      if (Array.isArray(d.redditSubs)) state.identity.redditSubs = d.redditSubs;
      emit();
    } catch (e) { /* keep fake */ }
  };

  const _pollRouter = async () => {
    try {
      const r = await fetch('/api/v1/router');
      if (!r.ok) return;
      const d = await r.json();
      if (d.totals) state.router.totals = { ...state.router.totals, ...d.totals };
      if (Array.isArray(d.window) && d.window.length) state.router.window = d.window;
      emit();
    } catch (e) { /* keep fake */ }
  };

  const _pollLogs = async () => {
    for (const name of ['maez', 'cognition', 'evolution']) {
      try {
        const r = await fetch(`/api/v1/logs/${name}`);
        if (!r.ok) continue;
        const d = await r.json();
        if (Array.isArray(d.lines) && d.lines.length) {
          state.logs[name] = d.lines;
        }
      } catch (e) { /* keep fake */ }
    }
    emit();
  };

  const _pollChatSessions = async () => {
    try {
      const r = await fetch('/api/v1/chat/sessions');
      if (!r.ok) return;
      const d = await r.json();
      if (Array.isArray(d.sessions) && d.sessions.length) {
        state.chat.sessions = d.sessions;
        state.chat.activeSessionId = d.activeSessionId || d.sessions[0].id;
        emit();
      }
    } catch (e) { /* keep fake */ }
  };

  // Kick off immediately, then poll each on its own cadence. Chose
  // cadences by staleness tolerance: daemon/gpu/cards update often,
  // soul/identity/logs rarely, memory/dreams in the middle.
  _pollDaemon(); _pollCards(); _pollGpu(); _pollServices();
  _pollSignals(); _pollMemory(); _pollDreams(); _pollSoul();
  _pollIdentity(); _pollRouter(); _pollLogs(); _pollChatSessions();
  setInterval(_pollDaemon, 5000);
  setInterval(_pollCards, 10000);
  setInterval(_pollGpu, 5000);
  setInterval(_pollServices, 15000);
  setInterval(_pollSignals, 10000);
  setInterval(_pollMemory, 30000);
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
