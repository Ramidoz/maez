// Direction B — Inner Life
// Warm, literary, scientific-instrument. Maez is a *being*, not a service.
// Big type, generous whitespace, muted palette, personality foregrounded.
(function() {
const innerStyles = {
  paper:  '#f3efe6',
  paperHi: '#faf7f0',
  ink:    '#2a251e',
  inkSoft:'#6b645a',
  inkDim: '#a29a8d',
  rule:   '#d9d1c2',
  ruleHi: '#c4b9a4',
  amber:  '#b4792c',
  sage:   '#708a6a',
  claret: '#9c5248',
  indigo: '#4a5878',
  serif:  '"Tiempos Text", "Newsreader", Georgia, "Times New Roman", serif',
  sans:   '"Söhne", "Inter", -apple-system, BlinkMacSystemFont, sans-serif',
  mono:   '"JetBrains Mono", ui-monospace, monospace',
};

const I = innerStyles;

function ICard({ title, subtitle, children, style, bodyStyle, right }) {
  return (
    <div style={{ background: I.paperHi, border: `1px solid ${I.rule}`, borderRadius: 2, display: 'flex', flexDirection: 'column', minHeight: 0, ...style }}>
      {(title || subtitle) && (
        <div style={{ padding: '14px 18px 10px', borderBottom: `1px solid ${I.rule}`, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexShrink: 0 }}>
          <div>
            {title && <div style={{ fontFamily: I.serif, fontSize: 17, color: I.ink, letterSpacing: -0.3, lineHeight: 1.1 }}>{title}</div>}
            {subtitle && <div style={{ fontFamily: I.sans, fontSize: 11, color: I.inkDim, letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 4 }}>{subtitle}</div>}
          </div>
          {right}
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', ...bodyStyle }}>{children}</div>
    </div>
  );
}

// ─── hero: Maez's inner life (personality foregrounded) ────
function InnerLifeHero() {
  const sim = useSim();
  const d = sim.state.daemon;
  return (
    <ICard style={{ gridColumn: '1 / span 2', gridRow: '1' }}>
      <div style={{ padding: '22px 28px', display: 'grid', gridTemplateColumns: '1fr 280px', gap: 28, alignItems: 'center' }}>
        <div>
          <div style={{ fontFamily: I.sans, fontSize: 10, color: I.inkDim, letterSpacing: 1.2, textTransform: 'uppercase', marginBottom: 10 }}>
            maez · cycle {d.cycle.toLocaleString()} · feeling {d.mood}
          </div>
          <div style={{ fontFamily: I.serif, fontSize: 26, color: I.ink, lineHeight: 1.25, letterSpacing: -0.4 }}>
            "{d.currentThought}"
          </div>
          <div style={{ fontFamily: I.sans, fontSize: 12, color: I.inkSoft, marginTop: 14, display: 'flex', gap: 22 }}>
            <span>next tick in <span style={{ color: I.amber, fontVariantNumeric: 'tabular-nums' }}>{d.nextTickIn}s</span></span>
            <span>cognition <span style={{ color: d.score > 0.75 ? I.sage : I.amber, fontVariantNumeric: 'tabular-nums' }}>{d.score.toFixed(2)}</span></span>
            <span>uncertainty <span style={{ color: I.inkSoft, fontVariantNumeric: 'tabular-nums' }}>{d.uncertainty.toFixed(2)}</span></span>
          </div>
        </div>
        <div>
          <MoodDial mood={d.mood} score={d.score} uncertainty={d.uncertainty} />
        </div>
      </div>
    </ICard>
  );
}

function MoodDial({ mood, score, uncertainty }) {
  // a circular instrument — attention (score) as arc, uncertainty as ring width
  const r = 64;
  const C = 2 * Math.PI * r;
  return (
    <svg width="220" height="140" viewBox="-110 -70 220 140">
      <circle cx="0" cy="0" r={r} fill="none" stroke={I.rule} strokeWidth="1" />
      <circle cx="0" cy="0" r={r} fill="none" stroke={I.sage} strokeWidth="6"
        strokeDasharray={`${C * score} ${C}`} transform="rotate(-90)" strokeLinecap="butt" />
      <circle cx="0" cy="0" r={r - 12} fill="none" stroke={I.amber} strokeWidth="1.5"
        strokeDasharray={`${C * uncertainty * 0.75} 4 2 4`} opacity="0.6" />
      {[0, 90, 180, 270].map((a) => (
        <line key={a} x1={Math.cos(a * Math.PI/180) * (r + 4)} y1={Math.sin(a * Math.PI/180) * (r + 4)}
          x2={Math.cos(a * Math.PI/180) * (r + 9)} y2={Math.sin(a * Math.PI/180) * (r + 9)} stroke={I.inkDim} strokeWidth="1" />
      ))}
      <text x="0" y="-2" textAnchor="middle" style={{ fontFamily: I.serif, fontSize: 20, fill: I.ink }}>{score.toFixed(2)}</text>
      <text x="0" y="14" textAnchor="middle" style={{ fontFamily: I.sans, fontSize: 9, fill: I.inkDim, letterSpacing: 1 }}>ATTENTION</text>
      <text x="0" y="56" textAnchor="middle" style={{ fontFamily: I.serif, fontStyle: 'italic', fontSize: 13, fill: I.inkSoft }}>{mood}</text>
    </svg>
  );
}

// ─── chat, literary framing ────────────────────────────────
function InnerChat() {
  const sim = useSim();
  const [input, setInput] = React.useState('');
  const scrollRef = React.useRef(null);
  const session = sim.state.chat.sessions.find(s => s.id === sim.state.chat.activeSessionId) || sim.state.chat.sessions[0];
  const history = session?.history || [];
  React.useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [history.length, sim.state.chat.streamBuf, sim.state.chat.pendingCommand]);

  return (
    <ICard title="the conversation" subtitle="chat · streaming"
      style={{ gridColumn: '1', gridRow: '2 / span 2' }}>
      <div ref={scrollRef} style={{ padding: '18px 24px', fontFamily: I.serif, fontSize: 15, lineHeight: 1.6, color: I.ink }}>
        {history.map((m, i) => <InnerTurn key={i} m={m} />)}
        {sim.state.chat.streaming && (
          <div style={{ marginTop: 14 }}>
            <div style={{ fontFamily: I.sans, fontSize: 10, color: I.inkDim, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 4 }}>
              maez · <span style={{ color: sim.state.chat._route === 'claude' ? I.claret : I.sage }}>{sim.state.chat._route}</span> · {sim.state.chat._model}
            </div>
            <div style={{ whiteSpace: 'pre-wrap', color: I.ink }}>{sim.state.chat.streamBuf}<span style={{ color: I.amber }}>▎</span></div>
          </div>
        )}
        {sim.state.chat.pendingCommand && <InnerPending p={sim.state.chat.pendingCommand} />}
      </div>
      <div style={{ borderTop: `1px solid ${I.rule}`, padding: '14px 20px', display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0, background: I.paper }}>
        <span style={{ fontFamily: I.serif, fontStyle: 'italic', color: I.inkSoft, fontSize: 14 }}>you →</span>
        <input value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && input.trim()) { sim.sendMessage(input.trim()); setInput(''); } }}
          placeholder="say something to maez…"
          style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', fontFamily: I.serif, fontSize: 15, color: I.ink }} />
        <span style={{ fontFamily: I.sans, fontSize: 10, color: I.inkDim, letterSpacing: 0.5 }}>enter to send</span>
      </div>
    </ICard>
  );
}

function InnerTurn({ m }) {
  if (m.role === 'user') {
    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontFamily: I.sans, fontSize: 10, color: I.inkDim, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 2 }}>rohit · {m.t}</div>
        <div style={{ color: I.ink, fontWeight: 500 }}>{m.content}</div>
      </div>
    );
  }
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontFamily: I.sans, fontSize: 10, color: I.inkDim, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 2 }}>
        maez · {m.t}
        {m.route && <span style={{ color: m.route === 'claude' ? I.claret : I.sage, marginLeft: 8 }}>{m.route}</span>}
        {m.model && <span style={{ marginLeft: 6, color: I.inkDim }}>· {m.model}</span>}
      </div>
      {m.thinking && (
        <div style={{ fontFamily: I.serif, fontStyle: 'italic', color: I.inkSoft, fontSize: 13, borderLeft: `2px solid ${I.ruleHi}`, paddingLeft: 10, margin: '4px 0', lineHeight: 1.5 }}>
          ({m.thinking})
        </div>
      )}
      {m.content && <div style={{ color: I.ink, whiteSpace: 'pre-wrap' }}>{m.content}</div>}
      {m.commands && m.commands.map((c, i) => (
        <div key={i} style={{ marginTop: 8, border: `1px solid ${I.rule}`, background: I.paper, fontFamily: I.mono, fontSize: 12 }}>
          <div style={{ padding: '6px 12px', borderBottom: `1px solid ${I.rule}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: I.ink }}>$ {c.cmd}</span>
            <span style={{ fontFamily: I.sans, fontSize: 9, letterSpacing: 1, textTransform: 'uppercase', color: c.status === 'approved' ? I.sage : I.claret }}>{c.status}</span>
          </div>
          <pre style={{ margin: 0, padding: '8px 12px', color: I.inkSoft, fontSize: 11, whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{c.output}</pre>
        </div>
      ))}
    </div>
  );
}

function InnerPending({ p }) {
  const sim = useSim();
  return (
    <div style={{ margin: '12px 0', border: `1px solid ${I.amber}66`, background: `${I.amber}10`, position: 'relative' }}>
      <div style={{ position: 'absolute', top: -1, left: -1, width: 4, bottom: -1, background: I.amber }} />
      <div style={{ padding: '10px 16px 4px 20px', fontFamily: I.sans, fontSize: 10, letterSpacing: 1, textTransform: 'uppercase', color: I.amber }}>
        maez would like to run a command · {p.risk} risk · {p.ts}
      </div>
      <pre style={{ margin: 0, padding: '4px 20px', fontFamily: I.mono, fontSize: 13, color: I.ink }}>$ {p.cmd}</pre>
      <div style={{ padding: '4px 20px 8px', fontFamily: I.serif, fontStyle: 'italic', fontSize: 13, color: I.inkSoft }}>
        because {p.reason.replace(/^user: /, '')}. the covenant is satisfied.
      </div>
      <div style={{ padding: '10px 16px', borderTop: `1px solid ${I.amber}44`, display: 'flex', gap: 8 }}>
        <button onClick={() => sim.approveCommand(true)} style={iBtn(I.sage, true)}>approve & run</button>
        <button onClick={() => sim.approveCommand(false)} style={iBtn(I.claret)}>deny</button>
        <button onClick={() => sim.approveCommand(false)} style={iBtn(I.inkSoft)}>not now</button>
      </div>
    </div>
  );
}

function iBtn(color, filled) {
  return {
    fontFamily: I.sans, fontSize: 12, padding: '5px 14px', letterSpacing: 0.3,
    background: filled ? color : 'transparent',
    color: filled ? I.paperHi : color,
    border: `1px solid ${color}`, borderRadius: 2,
    cursor: 'pointer',
  };
}

// ─── scratchpad (inner life's soul) ────────────────────────
function InnerScratchpad() {
  const sim = useSim();
  return (
    <ICard title="scratchpad" subtitle="what maez is noticing" style={{ gridColumn: '2', gridRow: '2' }}>
      <div style={{ padding: '14px 20px', fontFamily: I.serif, fontSize: 14, lineHeight: 1.55, color: I.ink }}>
        {sim.state.daemon.scratchpad.map((s, i) => (
          <div key={i} style={{ marginBottom: 10, opacity: 1 - i * 0.09, display: 'grid', gridTemplateColumns: '54px 1fr', gap: 12 }}>
            <span style={{ fontFamily: I.mono, fontSize: 11, color: I.inkDim, paddingTop: 3 }}>{s.t}</span>
            <span style={{ fontStyle: i === 0 ? 'normal' : 'italic', color: i === 0 ? I.ink : I.inkSoft }}>{s.text}</span>
          </div>
        ))}
      </div>
    </ICard>
  );
}

// ─── instrument panels (small, numerous) ───────────────────
function InstrumentRow() {
  const sim = useSim();
  const d = sim.state.daemon;
  const g = sim.state.gpu;
  const r = sim.state.router;
  const total = r.totals.local + r.totals.claude;
  return (
    <ICard title="instruments" subtitle="system · brain · ambient" style={{ gridColumn: '2', gridRow: '3' }}>
      <div style={{ padding: '16px 20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <InstDial label="vram" value={`${g.vramUsed.toFixed(1)} / 24`} unit="gb" pct={g.vramUsed / 24} color={I.amber} />
        <InstDial label="gpu util" value={g.util.toFixed(0)} unit="%" pct={g.util / 100} color={I.sage} />
        <InstDial label="local / claude" value={`${((r.totals.local/total)*100).toFixed(0)}`} unit="% local" pct={r.totals.local/total} color={I.indigo} />
        <InstDial label="cognition" value={d.score.toFixed(2)} unit="" pct={d.score} color={d.score > 0.75 ? I.sage : I.amber} />
      </div>
    </ICard>
  );
}

function InstDial({ label, value, unit, pct, color }) {
  return (
    <div style={{ borderLeft: `2px solid ${color}`, paddingLeft: 10 }}>
      <div style={{ fontFamily: I.sans, fontSize: 10, color: I.inkDim, letterSpacing: 1, textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontFamily: I.serif, fontSize: 22, color: I.ink, letterSpacing: -0.3, marginTop: 2 }}>
        {value}<span style={{ fontSize: 11, color: I.inkDim, marginLeft: 4 }}>{unit}</span>
      </div>
      <div style={{ height: 2, background: I.rule, marginTop: 6, position: 'relative' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, bottom: 0, width: `${Math.min(100, pct * 100)}%`, background: color }} />
      </div>
    </div>
  );
}

// ─── signals as literary feed ──────────────────────────────
function InnerSignals() {
  const sim = useSim();
  const colorFor = (k) => ({ focus: I.indigo, weather: I.amber, iphone: I.sage, reddit: I.claret }[k] || I.inkSoft);
  return (
    <ICard title="ambient" subtitle="what's around maez" style={{ gridColumn: '3', gridRow: '1 / span 3' }}>
      <div style={{ padding: '4px 0' }}>
        {sim.state.signals.slice(0, 24).map((s, i) => (
          <div key={s.t + i} style={{ padding: '8px 18px', borderBottom: `1px solid ${I.rule}`, opacity: 1 - i * 0.02 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
              <span style={{ fontFamily: I.sans, fontSize: 9, letterSpacing: 1.2, textTransform: 'uppercase', color: colorFor(s.kind) }}>{s.kind}</span>
              <span style={{ fontFamily: I.mono, fontSize: 10, color: I.inkDim }}>{s.t}</span>
            </div>
            <div style={{ fontFamily: I.serif, fontSize: 13, color: I.ink, lineHeight: 1.4 }}>{s.text}</div>
          </div>
        ))}
      </div>
    </ICard>
  );
}

window.InnerUI = { InnerLifeHero, InnerChat, InnerScratchpad, InstrumentRow, InnerSignals, I, ICard };
})();
