// Direction A — observatory redesign
// Aesthetic: live instrument room, warm glass, legible telemetry.
// The cockpit should help the owner observe Maez without mistaking demo
// placeholders for live truth.
// Rich interactive chat: real cockpit bridge, honest body-state badges,
// inline approval, tool-call cards, and live waiting state.
(function() {

const A = {
  // Apple-style palette (dark)
  bg:          '#090a07',
  bgElev:      '#11120d',
  surface:     'rgba(31, 29, 22, 0.74)',
  surfaceHi:   'rgba(48, 44, 32, 0.80)',
  surfaceLo:   'rgba(19, 18, 14, 0.72)',
  surfaceRaised:'rgba(72, 62, 39, 0.58)',

  stroke:      'rgba(255, 255, 255, 0.08)',
  strokeHi:    'rgba(255, 255, 255, 0.14)',
  strokeSoft:  'rgba(255, 255, 255, 0.05)',

  // text
  text:        '#f5f5f7',
  textSoft:    '#c7c7cc',
  textDim:     '#98989d',
  textFaint:   '#636366',
  textGhost:   '#3a3a3c',

  // system accents (Apple HIG)
  blue:        '#65a9ff',
  blueSoft:    '#9fc8ff',
  indigo:      '#8b8cf5',
  purple:      '#c79dff',
  pink:        '#f487a0',
  red:         '#ff6b5e',
  orange:      '#d99a42',
  yellow:      '#e8ca67',
  green:       '#75c47a',
  mint:        '#90d8b1',
  teal:        '#78c8bd',
  cyan:        '#88d4e7',

  // accent gradient (used by `.ap-ai-text` class for title-bar accents)
  aiGrad:      'linear-gradient(135deg, #d99a42 0%, #f487a0 34%, #8b8cf5 68%, #88d4e7 100%)',

  // type
  sans:   '"Inter", -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
  mono:   '"JetBrains Mono", "SF Mono", ui-monospace, Menlo, monospace',

  easing: 'cubic-bezier(0.32, 0.72, 0, 1)',  // Apple spring
  easeOut:'cubic-bezier(0.16, 1, 0.3, 1)',
};

if (typeof document !== 'undefined' && !document.getElementById('apple-styles')) {
  const el = document.createElement('style');
  el.id = 'apple-styles';
  el.textContent = `
    @keyframes ap-pulse { 0%,100% { opacity: 1; transform: scale(1) } 50% { opacity: 0.5; transform: scale(0.9) } }
    @keyframes ap-rise { from { opacity: 0; transform: translateY(6px) scale(0.98) } to { opacity: 1; transform: none } }
    @keyframes ap-shimmer { 0%{background-position:-200% 0}100%{background-position:200% 0} }
    @keyframes ap-bounce { 0%,80%,100%{transform:translateY(0);opacity:0.4}40%{transform:translateY(-3px);opacity:1} }
    @keyframes ap-breathe { 0%,100%{transform:scale(1);opacity:0.85}50%{transform:scale(1.08);opacity:1} }
    @keyframes ap-ai-shift { 0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%} }
    .ap-rise { animation: ap-rise 340ms ${A.easeOut} both }
    .ap-scroll::-webkit-scrollbar { width: 6px; height: 6px }
    .ap-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px }
    .ap-scroll::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2) }
    .ap-scroll { scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.1) transparent }
    .ap-btn { transition: all 180ms ${A.easing}; cursor: pointer; font-family: inherit; -webkit-user-select:none; user-select:none }
    .ap-btn:active { transform: scale(0.96) }
    .ap-glass { backdrop-filter: blur(30px) saturate(180%); -webkit-backdrop-filter: blur(30px) saturate(180%) }
    .ap-card { transition: transform 220ms ${A.easing}, border-color 220ms ${A.easing} }
    .ap-hover-lift:hover { border-color: ${A.strokeHi}; background: ${A.surfaceHi} }
    .ap-ai-text { background: ${A.aiGrad}; background-size: 200% 200%; -webkit-background-clip: text; background-clip: text; color: transparent; animation: ap-ai-shift 4s ease infinite }
    .ap-input { background: transparent; border: none; outline: none; font-family: inherit; color: ${A.text} }
    .ap-input::placeholder { color: ${A.textFaint} }
    .ap-dot { animation: ap-breathe 1.8s ${A.easing} infinite }
    .ap-menu { animation: ap-rise 160ms ${A.easeOut} both; transform-origin: top right }
  `;
  document.head.appendChild(el);
}

// ═══ primitives ═══════════════════════════════════════════════════

function Glass({ children, style, raised, pad = 18, radius = 16, className = '' }) {
  return (
    <div className={`ap-glass ${className}`} style={{
      background: raised ? A.surfaceHi : A.surface,
      border: `0.5px solid ${A.stroke}`,
      borderRadius: radius,
      boxShadow: raised ? '0 12px 40px -10px rgba(0,0,0,0.6), inset 0 0.5px 0 rgba(255,255,255,0.08)' : '0 8px 30px -12px rgba(0,0,0,0.5), inset 0 0.5px 0 rgba(255,255,255,0.05)',
      padding: pad, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden',
      ...style,
    }}>{children}</div>
  );
}

function Card({ title, subtitle, right, children, style, icon, iconColor = A.blue, pad = 18 }) {
  return (
    <Glass style={style} pad={0}>
      {(title || right) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: `16px ${pad}px 0`, flexShrink: 0 }}>
          {icon && <div style={{ width: 22, height: 22, borderRadius: 6, background: `${iconColor}22`, color: iconColor, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11 }}>{icon}</div>}
          <div style={{ flex: 1, minWidth: 0 }}>
            {title && <div style={{ fontFamily: A.sans, fontSize: 13, color: A.text, fontWeight: 600, letterSpacing: -0.15 }}>{title}</div>}
            {subtitle && <div style={{ fontFamily: A.sans, fontSize: 11, color: A.textDim, marginTop: 1 }}>{subtitle}</div>}
          </div>
          {right}
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0, padding: title ? `12px ${pad}px ${pad}px` : pad, display: 'flex', flexDirection: 'column' }}>
        {children}
      </div>
    </Glass>
  );
}

function Dot({ c = A.green, size = 7, pulse }) {
  return <span className={pulse ? 'ap-dot' : ''} style={{
    width: size, height: size, borderRadius: '50%', background: c, display: 'inline-block',
    boxShadow: `0 0 ${size * 1.8}px ${c}aa, inset 0 0 2px rgba(255,255,255,0.4)`,
  }} />;
}

function Chip({ children, color = A.blue, tone = 'soft', style, onClick }) {
  const styles = {
    soft:   { background: `${color}24`, color, border: `0.5px solid ${color}40` },
    filled: { background: color, color: '#fff', border: 'none' },
    ghost:  { background: 'transparent', color: A.textDim, border: `0.5px solid ${A.stroke}` },
  }[tone];
  return (
    <span onClick={onClick} className={onClick ? 'ap-btn' : ''} style={{
      display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 999,
      fontSize: 10.5, fontFamily: A.sans, fontWeight: 500, letterSpacing: 0.1,
      ...styles, ...style,
    }}>{children}</span>
  );
}

function Button({ children, onClick, variant = 'secondary', size = 'md', color = A.blue, style, icon }) {
  const sizes = {
    sm: { padding: '5px 11px', fontSize: 11, height: 26, borderRadius: 7 },
    md: { padding: '7px 14px', fontSize: 12.5, height: 30, borderRadius: 8 },
    lg: { padding: '10px 18px', fontSize: 14, height: 38, borderRadius: 10 },
  }[size];
  const variants = {
    primary:   { background: color, color: '#fff', border: 'none', boxShadow: `0 4px 14px -4px ${color}88` },
    secondary: { background: A.surfaceRaised, color: A.text, border: `0.5px solid ${A.stroke}` },
    ghost:     { background: 'transparent', color: A.textSoft, border: 'none' },
    outline:   { background: 'transparent', color, border: `0.5px solid ${color}66` },
    danger:    { background: A.red + '22', color: A.red, border: `0.5px solid ${A.red}44` },
  }[variant];
  return (
    <button className="ap-btn" onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
      fontWeight: 500, letterSpacing: -0.05, whiteSpace: 'nowrap',
      ...sizes, ...variants, ...style,
    }}>
      {icon && <span style={{ display: 'flex' }}>{icon}</span>}
      {children}
    </button>
  );
}

function endpointMeta(name) {
  const meta = SIM?.state?.meta?.endpoints?.[name];
  if (!meta) return { status: 'pending', age: null, error: '' };
  const age = meta.at ? Math.max(0, Math.round((Date.now() - meta.at) / 1000)) : null;
  return { ...meta, age };
}

function LiveBadge({ endpoint, label = 'live', compact = false }) {
  const meta = endpointMeta(endpoint);
  const live = meta.status === 'live';
  const pending = meta.status === 'pending';
  const color = live ? A.green : pending ? A.orange : A.red;
  const text = live
    ? (compact ? label : `${label} · ${meta.age ?? 0}s`)
    : pending
      ? 'waiting'
      : 'offline';
  return (
    <Chip color={color} title={meta.error || ''} style={{ fontSize: compact ? 9 : 10 }}>
      <Dot c={color} size={4} pulse={live} /> {text}
    </Chip>
  );
}

function StatusTile({ label, value, sub, color = A.blue, tone }) {
  return (
    <div style={{
      minHeight: 78,
      borderRadius: 16,
      padding: 14,
      background: tone || `linear-gradient(145deg, ${color}1d, rgba(255,255,255,0.025))`,
      border: `0.5px solid ${color}45`,
      boxShadow: `inset 0 0.5px 0 rgba(255,255,255,0.06), 0 18px 34px -26px ${color}66`,
    }}>
      <div style={{ fontFamily: A.sans, fontSize: 10, color: A.textFaint, letterSpacing: 0.9, fontWeight: 700, textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontFamily: A.sans, fontSize: 22, color: A.text, letterSpacing: -0.6, fontWeight: 700, lineHeight: 1.05, marginTop: 8 }}>{value}</div>
      {sub && <div style={{ fontFamily: A.sans, fontSize: 11.5, color: A.textDim, marginTop: 5, lineHeight: 1.35 }}>{sub}</div>}
    </div>
  );
}

function SectionKicker({ children }) {
  return (
    <div style={{
      fontFamily: A.sans,
      fontSize: 10,
      color: A.textFaint,
      letterSpacing: 1.2,
      textTransform: 'uppercase',
      fontWeight: 700,
    }}>{children}</div>
  );
}

// SF-style SVG icons
const Icon = {
  send:    (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M2 8L14 2L9 14L8 9L2 8Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/></svg>,
  mic:     (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><rect x="6" y="2" width="4" height="8" rx="2" stroke="currentColor" strokeWidth="1.4"/><path d="M4 8c0 2.2 1.8 4 4 4s4-1.8 4-4M8 12v2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>,
  plus:    (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  sparkle: (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M8 2l1.5 3.5L13 7l-3.5 1.5L8 12l-1.5-3.5L3 7l3.5-1.5L8 2z" fill="currentColor"/></svg>,
  chevronDown: (s=12) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  brain:   (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M5 4a2 2 0 0 1 4 0v8a2 2 0 0 1-4 0M7 4a2 2 0 0 0-4 0v3a2 2 0 0 0 2 2M9 4a2 2 0 0 1 4 0v3a2 2 0 0 1-2 2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>,
  tool:    (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M10.5 2a3 3 0 0 0-2.6 4.5L2 12.4V14h1.6l5.9-5.9A3 3 0 1 0 10.5 2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/></svg>,
  attach:  (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M11 7l-4 4a2 2 0 0 1-3-3l5-5a3 3 0 0 1 4 4l-5 5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  search:  (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><circle cx="7" cy="7" r="4" stroke="currentColor" strokeWidth="1.4"/><path d="M10 10l3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>,
  check:   (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M3 8.5L6.5 12L13 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  x:       (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  globe:   (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3"/><path d="M2 8h12M8 2c2 2 2 10 0 12M8 2c-2 2-2 10 0 12" stroke="currentColor" strokeWidth="1.3"/></svg>,
  terminal: (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><rect x="2" y="3" width="12" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.3"/><path d="M5 7l2 1.5L5 10M8.5 10.5h3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  image:   (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><rect x="2" y="3" width="12" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.3"/><circle cx="6" cy="7" r="1.2" fill="currentColor"/><path d="M2.5 12L6 9l3 3 2-1.5 2.5 2" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/></svg>,
  code:    (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M6 4L2 8l4 4M10 4l4 4-4 4M9.5 3.5l-3 9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  memory:  (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><rect x="3" y="3" width="10" height="10" rx="1" stroke="currentColor" strokeWidth="1.3"/><path d="M6 3v10M10 3v10M3 6h10M3 10h10" stroke="currentColor" strokeWidth="1.2"/></svg>,
  stop:    (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="currentColor"><rect x="4" y="4" width="8" height="8" rx="1.5"/></svg>,
  copy:    (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><rect x="4" y="4" width="9" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.3"/><path d="M4 10h-1a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v1" stroke="currentColor" strokeWidth="1.3"/></svg>,
  refresh: (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M13 8a5 5 0 1 1-1.5-3.5M13 2v3h-3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  thumb:   (s=13) => <svg width={s} height={s} viewBox="0 0 16 16" fill="none"><path d="M5 13V7l3-5c1 0 1.5 1 1.5 2v2H13a1.5 1.5 0 0 1 1.5 1.8l-1 4.5A1.5 1.5 0 0 1 12 13H5zM5 7H3v6h2" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/></svg>,
};

function Sparkline({ values, color = A.blue, h = 28, w = 100, fill = true }) {
  if (!values.length) return null;
  const max = Math.max(...values), min = Math.min(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, h - ((v - min) / range) * (h - 2) - 1]);
  const line = pts.map(p => p.join(',')).join(' ');
  const area = `${pts[0][0]},${h} ${line} ${pts[pts.length-1][0]},${h}`;
  const gid = 'asg-' + color.replace(/[^a-z0-9]/gi, '');
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <polygon points={area} fill={`url(#${gid})`} />}
      <polyline points={line} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function useSparkValues(getter, len = 40) {
  const [vals, setVals] = React.useState(() => Array(len).fill(0));
  React.useEffect(() => {
    const id = setInterval(() => setVals(v => [...v.slice(1), getter()]), 500);
    return () => clearInterval(id);
  }, []);
  return vals;
}

// ═══ chat — the centerpiece ═══════════════════════════════════════

const SESSION_COLORS = { blue: A.blue, purple: A.purple, green: A.green, orange: A.orange, pink: A.pink, cyan: A.cyan, indigo: A.indigo, mint: A.mint };

function SessionSidebar({ compact }) {
  const sim = useSim();
  const sessions = sim.state.chat.sessions;
  const active = sim.state.chat.activeSessionId;
  return (
    <div style={{ width: compact ? 240 : 260, display: 'flex', flexDirection: 'column', borderRight: `0.5px solid ${A.stroke}`, background: 'rgba(0,0,0,0.2)', flexShrink: 0 }}>
      <div style={{ padding: '14px 14px 10px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontFamily: A.sans, fontSize: 12, color: A.text, fontWeight: 600, letterSpacing: -0.1, flex: 1 }}>Conversations</span>
        <button className="ap-btn" onClick={() => sim.newSession()} title="New conversation"
          style={{ width: 24, height: 24, borderRadius: 7, backgroundImage: A.aiGrad, backgroundSize: '200% 200%', animation: 'ap-ai-shift 4s ease infinite', border: 'none', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: `0 2px 10px -2px ${A.indigo}99` }}>{Icon.plus(13)}</button>
      </div>
      <div style={{ padding: '0 10px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, background: A.surfaceLo, border: `0.5px solid ${A.stroke}`, borderRadius: 8, padding: '6px 9px' }}>
          <span style={{ color: A.textFaint }}>{Icon.search(12)}</span>
          <input className="ap-input" placeholder="Search" style={{ flex: 1, fontSize: 12 }} />
        </div>
      </div>
      <div className="ap-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 6px 10px' }}>
        {sessions.map(s => {
          const isActive = s.id === active;
          const c = SESSION_COLORS[s.color] || A.blue;
          return (
            <button key={s.id} className="ap-btn" onClick={() => sim.selectSession(s.id)}
              style={{ width: '100%', textAlign: 'left', display: 'flex', gap: 10, padding: '9px 10px', marginBottom: 2, borderRadius: 10,
                background: isActive ? A.surfaceRaised : 'transparent',
                border: isActive ? `0.5px solid ${A.strokeHi}` : '0.5px solid transparent',
                boxShadow: isActive ? 'inset 0 0.5px 0 rgba(255,255,255,0.08)' : 'none' }}>
              <div style={{ width: 28, height: 28, borderRadius: 8, flexShrink: 0, background: `linear-gradient(135deg, ${c}, ${c}66)`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 11, fontWeight: 600, boxShadow: `0 2px 8px -2px ${c}66` }}>
                {s.title.charAt(0).toUpperCase()}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  {s.pinned && <span style={{ color: A.orange, fontSize: 9 }}>✦</span>}
                  <span style={{ fontFamily: A.sans, fontSize: 12.5, color: isActive ? A.text : A.textSoft, fontWeight: isActive ? 600 : 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{s.title}</span>
                  <span style={{ fontFamily: A.mono, fontSize: 9.5, color: A.textFaint, flexShrink: 0 }}>{s.updated}</span>
                </div>
                <div style={{ fontFamily: A.sans, fontSize: 11, color: A.textFaint, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.preview}</div>
              </div>
              {s.unread > 0 && <span style={{ background: c, color: '#fff', fontSize: 9, padding: '1px 5px', borderRadius: 999, fontWeight: 600, alignSelf: 'center' }}>{s.unread}</span>}
            </button>
          );
        })}
      </div>
      <div style={{ padding: '10px 14px', borderTop: `0.5px solid ${A.stroke}`, display: 'flex', alignItems: 'center', gap: 8, fontSize: 10.5, color: A.textFaint, fontFamily: A.sans }}>
        <Dot c={A.green} size={5} pulse />
        <span>{sessions.length} threads · {sessions.reduce((a,s)=>a+s.history.length,0)} msgs</span>
      </div>
    </div>
  );
}

function ActivityVisualizer() {
  const sim = useSim();
  const [t, setT] = React.useState(0);
  React.useEffect(() => { const id = setInterval(() => setT(x => x + 1), 60); return () => clearInterval(id); }, []);
  const d = sim.state.daemon;
  const cycleProgress = ((30 - d.nextTickIn) / 30);
  const phases = ['Perceive', 'Reason', 'Score', 'Evolve', 'Speak'];
  const phaseColors = [A.blue, A.purple, A.pink, A.orange, A.green];
  const activePhase = Math.min(4, Math.floor(cycleProgress * 5));
  return (
    <div style={{ padding: '14px 16px', borderBottom: `0.5px solid ${A.stroke}`, background: `linear-gradient(90deg, ${A.surfaceLo}, transparent)` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 10, color: A.textFaint, letterSpacing: 0.8, fontWeight: 600, textTransform: 'uppercase', fontFamily: A.sans }}>Maez is</span>
        <span className="ap-ai-text" style={{ fontSize: 12.5, fontWeight: 600 }}>{phases[activePhase].toLowerCase()}ing</span>
        <span style={{ flex: 1 }} />
        <Chip color={phaseColors[activePhase]} style={{ fontSize: 9 }}>cycle #{d.cycle}</Chip>
      </div>
      {/* Phase flow */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        {phases.map((p, i) => {
          const isActive = i === activePhase;
          const isDone = i < activePhase;
          const c = phaseColors[i];
          return (
            <React.Fragment key={p}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 8px', borderRadius: 999,
                background: isActive ? `${c}22` : isDone ? `${c}14` : A.surfaceLo,
                border: `0.5px solid ${isActive ? c+'66' : isDone ? c+'33' : A.stroke}`,
                transition: `all 280ms ${A.easing}` }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: isActive ? c : isDone ? c+'aa' : A.textGhost,
                  boxShadow: isActive ? `0 0 8px ${c}` : 'none', animation: isActive ? 'ap-breathe 1.4s ease infinite' : 'none' }} />
                <span style={{ fontSize: 10, fontFamily: A.sans, fontWeight: 500, color: isActive ? A.text : isDone ? A.textSoft : A.textFaint }}>{p}</span>
              </div>
              {i < phases.length - 1 && <div style={{ flex: 1, height: 1, background: i < activePhase ? phaseColors[i] + '66' : A.stroke, minWidth: 4 }} />}
            </React.Fragment>
          );
        })}
      </div>
      {/* Tick progress bar */}
      <div style={{ height: 3, background: A.bgElev, borderRadius: 2, overflow: 'hidden', position: 'relative' }}>
        <div style={{ height: '100%', width: `${cycleProgress*100}%`, background: `linear-gradient(90deg, ${A.blue}, ${A.purple}, ${A.pink}, ${A.orange})`, transition: `width 200ms linear`, borderRadius: 2 }} />
      </div>
    </div>
  );
}

function ChatPane({ tall, showSidebar = true, selectedTurn, onSelectTurn }) {
  const sim = useSim();
  const [input, setInput] = React.useState('');
  const scrollRef = React.useRef(null);
  const taRef = React.useRef(null);
  const sendBusy = Boolean(sim.state.chat._awaitingReply || sim.state.chat.streaming);

  const session = sim.state.chat.sessions.find(s => s.id === sim.state.chat.activeSessionId) || sim.state.chat.sessions[0];
  const sessionColor = SESSION_COLORS[session?.color] || A.blue;

  React.useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [session?.history.length, sim.state.chat.streamBuf, sim.state.chat.pendingCommand]);

  React.useEffect(() => {
    const ta = taRef.current; if (!ta) return;
    ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 140) + 'px';
  }, [input]);

  // Real chat: post to maez-web's /api/v1/cockpit/message proxy, which
  // forwards to the daemon's /message endpoint. One web origin, no
  // browser-direct daemon calls (Workstation v1 / Session 1). The
  // proxy timeout is long enough for local synthesis; on daemon-unreachable it returns 502 with
  // a structured error which the catch block surfaces.
  const submitText = async (text) => {
    const textToSend = String(text || '').trim();
    if (!textToSend) return;
    if (sendBusy) return;
    setInput('');
    // Optimistically show the user turn + a "thinking" placeholder
    sim.pushUserTurn ? sim.pushUserTurn(textToSend) : sim.sendMessage(textToSend);
    // Build prior-turn history for the daemon to thread into synthesis.
    // Without this, "Hi" mid-session re-greets because handle_message
    // gets no chat_history (2026-04-27 incident). pushUserTurn appended
    // the current text; drop the trailing entry and cap to last 6
    // turns of prior context.
    const activeSess = sim.state?.chat?.sessions?.find(
      (s) => s.id === sim.state.chat.activeSessionId,
    );
    const allHistory = activeSess?.history || [];
    const priorOnly = allHistory.slice(0, -1).slice(-6);
    const history = priorOnly
      .filter((h) => h && h.role && h.content)
      .map((h) => ({ role: h.role, content: h.content }));
    try {
      const res = await fetch('/api/v1/cockpit/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: textToSend, source: 'cockpit', history }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      const reply = (data && data.reply) || '(empty reply)';
      const assistantTurn = sim.pushAssistantTurn ? sim.pushAssistantTurn(reply) : sim.finishSimReply(reply);
      onSelectTurn?.({
        key: assistantTurn?._id || `latest:${Date.now()}`,
        message: assistantTurn || { role: 'assistant', content: reply },
        isLatest: true,
      });
    } catch (e) {
      const msg = "(cockpit couldn't reach Maez — " + String(e) + ")";
      const assistantTurn = sim.pushAssistantTurn ? sim.pushAssistantTurn(msg) : sim.finishSimReply(msg);
      onSelectTurn?.({
        key: assistantTurn?._id || `latest:${Date.now()}`,
        message: assistantTurn || { role: 'assistant', content: msg },
        isLatest: true,
      });
    }
  };

  const submit = () => submitText(input);

  const chatBody = (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* Conversation header */}
      <div style={{ padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 12, borderBottom: `0.5px solid ${A.stroke}`, flexShrink: 0, background: `linear-gradient(90deg, ${sessionColor}14, transparent 60%)` }}>
        <div style={{ width: 32, height: 32, borderRadius: 10, background: `linear-gradient(135deg, ${sessionColor}, ${sessionColor}77)`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 13, fontWeight: 600, boxShadow: `0 4px 14px -4px ${sessionColor}99`, flexShrink: 0 }}>
          {(session?.title || 'M').charAt(0).toUpperCase()}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontFamily: A.sans, fontSize: 14, color: A.text, fontWeight: 600, letterSpacing: -0.15, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{session?.title}</span>
            <Dot c={A.green} size={6} pulse />
          </div>
          <div style={{ fontFamily: A.sans, fontSize: 11, color: A.textDim, marginTop: 1, display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ color: sessionColor, fontWeight: 600 }}>Maez</span>
            <span>·</span>
            <span>{session?.history.length || 0} messages</span>
          </div>
        </div>
        <Button variant="ghost" size="sm" icon={Icon.search(12)}>Search</Button>
        <Button variant="ghost" size="sm" icon={Icon.refresh(12)} onClick={() => sim.newSession()}>New</Button>
      </div>

      <ActivityVisualizer />

      {/* Messages */}
      <div ref={scrollRef} className="ap-scroll" style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '20px 20px 4px' }}>
        {(session?.history || []).map((m, i) => {
          const key = m._id || `${session?.id || 'session'}:${i}`;
          return (
            <ChatMessage
              key={key}
              m={m}
              selected={selectedTurn?.key === key}
              onSelect={m.role === 'assistant' ? () => onSelectTurn?.({
                key,
                message: m,
                isLatest: i === (session?.history || []).length - 1,
              }) : null}
            />
          );
        })}
        {sim.state.chat.streaming && <StreamingMessage text={sim.state.chat.streamBuf} route={sim.state.chat._route} model={sim.state.chat._model} showThinking={true} />}
        {sim.state.chat._awaitingReply && !sim.state.chat.streaming && (
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '12px 6px', fontSize: 12, color: A.textDim }}>
            <MaezAvatar size={28} />
            <span style={{ fontFamily: A.sans }}>Thinking</span>
            <span className="ap-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: A.blue, display: 'inline-block' }} />
            <span className="ap-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: A.blue, display: 'inline-block', animationDelay: '0.15s' }} />
            <span className="ap-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: A.blue, display: 'inline-block', animationDelay: '0.3s' }} />
          </div>
        )}
        {sim.state.chat.pendingCommand && <PendingCommand p={sim.state.chat.pendingCommand} />}
      </div>

      {/* Composer */}
      <div style={{ padding: 14, flexShrink: 0, borderTop: `0.5px solid ${A.stroke}` }}>
        <div style={{
          background: A.surfaceLo, border: `0.5px solid ${A.stroke}`, borderRadius: 18,
          transition: `border 200ms ${A.easing}, box-shadow 200ms ${A.easing}`,
        }}
          onFocusCapture={(e) => { e.currentTarget.style.borderColor = A.strokeHi; e.currentTarget.style.boxShadow = `0 0 0 3px ${A.blue}22`; }}
          onBlurCapture={(e) => { e.currentTarget.style.borderColor = A.stroke; e.currentTarget.style.boxShadow = 'none'; }}>
          {/* textarea row */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '11px 14px' }}>
            <textarea ref={taRef} className="ap-input"
              value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }}
              placeholder="Message Maez…"
              rows={1}
              style={{ flex: 1, fontFamily: A.sans, fontSize: 14, lineHeight: 1.5, resize: 'none', padding: 0, minHeight: 20, maxHeight: 140 }} />
          </div>

          {/* bottom row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 10px 10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', minWidth: 0 }}>
              <Chip color={A.green} style={{ fontSize: 10.5 }}>
                <Dot c={A.green} size={4} pulse /> Live bridge
              </Chip>
              <Chip color={A.blue} tone="ghost" style={{ fontSize: 10.5 }} title="body state, not a control">
                body state, not a control
              </Chip>
            </div>

            <div style={{ flex: 1 }} />

            {/* send */}
            <button className="ap-btn" onClick={submit} disabled={sendBusy || !input.trim()}
              style={{
                width: 30, height: 30, borderRadius: 8, border: 'none',
                backgroundColor: input.trim() && !sendBusy ? 'transparent' : A.surfaceRaised,
                backgroundImage: input.trim() && !sendBusy ? A.aiGrad : 'none',
                backgroundSize: '200% 200%', animation: input.trim() && !sendBusy ? 'ap-ai-shift 3s ease infinite' : 'none',
                color: input.trim() && !sendBusy ? '#fff' : A.textFaint,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: input.trim() && !sendBusy ? `0 4px 14px -4px ${A.indigo}aa` : 'none',
                opacity: input.trim() && !sendBusy ? 1 : 0.6,
              }}>{Icon.send(14)}</button>
          </div>
        </div>

        {/* suggestion pills */}
        <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
          {[
            { t: 'Check VRAM headroom', c: A.green },
            { t: 'Summarize today\'s signals', c: A.blue },
            { t: 'Explain the Covenant', c: A.purple },
            { t: 'What did I do yesterday?', c: A.orange },
          ].map(s => (
            <button key={s.t} className="ap-btn" onClick={() => submitText(s.t)} disabled={sendBusy}
              style={{
                background: `${s.c}14`, border: `0.5px solid ${s.c}33`, color: A.text,
                fontSize: 11.5, padding: '5px 11px', borderRadius: 999, fontFamily: A.sans,
                opacity: sendBusy ? 0.5 : 1,
              }}>
              <span style={{ color: s.c, marginRight: 5 }}>✦</span>{s.t}
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  return chatBody;
}

function MaezAvatar({ size = 32 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', position: 'relative', flexShrink: 0,
      backgroundImage: A.aiGrad, backgroundSize: '200% 200%',
      animation: 'ap-ai-shift 6s ease infinite',
      boxShadow: `0 0 ${size}px -4px rgba(191, 90, 242, 0.6), inset 0 0 ${size/3}px rgba(255,255,255,0.2)`,
    }}>
      <div style={{ position: 'absolute', inset: 2, borderRadius: '50%', border: `0.5px solid rgba(255,255,255,0.3)` }} />
    </div>
  );
}

function ChatMessage({ m, selected = false, onSelect }) {
  if (m.role === 'user') {
    return (
      <div className="ap-rise" style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <div style={{ maxWidth: '76%' }}>
          <div style={{
            background: A.blue, color: '#fff', padding: '9px 14px', borderRadius: '18px 18px 4px 18px',
            fontSize: 14, lineHeight: 1.45, fontFamily: A.sans,
            boxShadow: `0 2px 12px -4px ${A.blue}66`,
          }}>
            {m.content}
          </div>
          <div style={{ fontFamily: A.sans, fontSize: 10, color: A.textFaint, textAlign: 'right', marginTop: 4 }}>{m.t}</div>
        </div>
      </div>
    );
  }
  return (
    <div
      className="ap-rise"
      onClick={onSelect || undefined}
      title={onSelect ? 'Inspect why Maez said this' : undefined}
      style={{
        display: 'flex',
        gap: 10,
        marginBottom: 18,
        cursor: onSelect ? 'pointer' : 'default',
        borderRadius: 14,
        padding: selected ? '10px 12px' : '0',
        marginLeft: selected ? -12 : 0,
        marginRight: selected ? -12 : 0,
        background: selected ? `${A.orange}13` : 'transparent',
        border: selected ? `0.5px solid ${A.orange}55` : '0.5px solid transparent',
      }}
    >
      <MaezAvatar size={28} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontFamily: A.sans, fontSize: 12.5, color: A.text, fontWeight: 600 }}>Maez</span>
          {m.route && (
            <Chip color={m.route === 'claude' ? A.blue : A.green} style={{ fontSize: 9 }}>
              <Dot c={m.route === 'claude' ? A.blue : A.green} size={4} /> {m.route}
            </Chip>
          )}
          {m.model && <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>{m.model}</span>}
          <span style={{ fontFamily: A.sans, fontSize: 10, color: A.textFaint }}>{m.t}</span>
        </div>
        {m.thinking && <ThinkingBlock text={m.thinking} />}
        {m.content && (
          <div style={{ color: A.text, fontSize: 14, lineHeight: 1.55, fontFamily: A.sans, whiteSpace: 'pre-wrap' }}>{m.content}</div>
        )}
        {m.commands && m.commands.map((c, i) => <CommandResult key={i} c={c} />)}
        <MessageActions />
      </div>
    </div>
  );
}

function ThinkingBlock({ text, streaming }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ marginBottom: 8 }}>
      <button className="ap-btn" onClick={() => setOpen(!open)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 9px', borderRadius: 7,
          background: A.surfaceLo, border: `0.5px solid ${A.stroke}`, color: A.textSoft,
          fontSize: 11, fontWeight: 500, fontFamily: A.sans,
        }}>
        <span style={{ color: A.purple, display: 'flex' }}>{Icon.brain(12)}</span>
        <span>{streaming ? 'Thinking…' : 'Thought for a moment'}</span>
        <span style={{ color: A.textFaint, transform: open ? 'rotate(180deg)' : 'none', transition: `transform 180ms ${A.easing}`, display: 'flex' }}>{Icon.chevronDown(10)}</span>
      </button>
      {open && (
        <div className="ap-rise" style={{
          marginTop: 8, padding: '10px 14px', background: A.surfaceLo, border: `0.5px solid ${A.stroke}`, borderRadius: 12,
          borderLeft: `2px solid ${A.purple}`,
          fontStyle: 'italic', fontSize: 12.5, color: A.textSoft, lineHeight: 1.55, fontFamily: A.sans,
        }}>{text}</div>
      )}
    </div>
  );
}

function MessageActions() {
  const acts = [
    { icon: Icon.copy(12),    label: 'Copy' },
    { icon: Icon.refresh(12), label: 'Regenerate' },
    { icon: Icon.thumb(12),   label: 'Good' },
    { icon: <div style={{ transform: 'rotate(180deg)', display: 'flex' }}>{Icon.thumb(12)}</div>, label: 'Bad' },
  ];
  return (
    <div style={{ display: 'flex', gap: 2, marginTop: 6, opacity: 0.5, transition: `opacity 200ms`, marginLeft: -4 }}
      onMouseEnter={(e) => e.currentTarget.style.opacity = 1}
      onMouseLeave={(e) => e.currentTarget.style.opacity = 0.5}>
      {acts.map(a => (
        <button key={a.label} className="ap-btn" title={a.label}
          style={{ width: 24, height: 24, borderRadius: 6, background: 'transparent', border: 'none', color: A.textDim, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onMouseEnter={(e) => e.currentTarget.style.background = A.surfaceRaised}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
          {a.icon}
        </button>
      ))}
    </div>
  );
}

function CommandResult({ c }) {
  return (
    <div className="ap-rise" style={{
      marginTop: 10, background: A.bgElev, border: `0.5px solid ${A.stroke}`, borderRadius: 10, overflow: 'hidden',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px', borderBottom: `0.5px solid ${A.stroke}`, background: A.surfaceLo }}>
        <span style={{ color: A.green, display: 'flex' }}>{Icon.terminal(12)}</span>
        <span style={{ color: A.text, fontFamily: A.mono, fontSize: 11.5, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.cmd}</span>
        <Chip color={c.status === 'approved' ? A.green : A.red} style={{ fontSize: 9 }}>
          {c.status === 'approved' ? Icon.check(10) : Icon.x(10)} {c.status}
        </Chip>
      </div>
      <pre style={{ margin: 0, padding: '10px 12px', fontFamily: A.mono, fontSize: 11, color: A.textSoft, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{c.output}</pre>
    </div>
  );
}

function StreamingMessage({ text, route, model, showThinking }) {
  return (
    <div className="ap-rise" style={{ display: 'flex', gap: 10, marginBottom: 18 }}>
      <MaezAvatar size={28} />
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontFamily: A.sans, fontSize: 12.5, color: A.text, fontWeight: 600 }}>Maez</span>
          <Chip color={route === 'claude' ? A.blue : A.green} style={{ fontSize: 9 }}>{route}</Chip>
          <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>{model}</span>
          <span style={{ display: 'inline-flex', gap: 3, marginLeft: 2 }}>
            {[0,1,2].map(i => (
              <span key={i} style={{ width: 4, height: 4, borderRadius: '50%', background: A.blue, animation: `ap-bounce 1.2s ease-in-out ${i*0.15}s infinite`, display: 'inline-block' }} />
            ))}
          </span>
        </div>
        {showThinking && <ThinkingBlock text="Waiting for Maez's live reply from the cockpit bridge." streaming />}
        <div style={{ color: A.text, fontSize: 14, lineHeight: 1.55, fontFamily: A.sans, whiteSpace: 'pre-wrap' }}>
          {text}
          <span style={{ display: 'inline-block', width: 2, height: 14, background: A.blue, marginLeft: 2, verticalAlign: 'middle', borderRadius: 1, animation: 'ap-pulse 1s ease-in-out infinite' }} />
        </div>
      </div>
    </div>
  );
}

function PendingCommand({ p }) {
  const sim = useSim();
  return (
    <div className="ap-rise" style={{
      margin: '4px 0 18px', padding: 16, borderRadius: 16,
      background: `linear-gradient(135deg, ${A.orange}18, ${A.orange}08)`,
      border: `0.5px solid ${A.orange}55`,
      boxShadow: `0 0 0 3px ${A.orange}0f, 0 8px 24px -8px ${A.orange}33`,
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: `linear-gradient(90deg, transparent, ${A.orange}, transparent)`, backgroundSize: '200% 100%', animation: 'ap-shimmer 2.5s linear infinite' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Dot c={A.orange} pulse />
        <span style={{ fontFamily: A.sans, fontSize: 11, color: A.orange, letterSpacing: 0.3, fontWeight: 600, textTransform: 'uppercase' }}>Awaiting approval</span>
        <Chip color={A.orange} tone="filled" style={{ fontSize: 9 }}>{p.risk}-risk</Chip>
        <span style={{ flex: 1 }} />
        <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>{p.ts}</span>
      </div>
      <div style={{ background: A.bgElev, border: `0.5px solid ${A.stroke}`, borderRadius: 10, padding: '9px 12px', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: A.orange, display: 'flex' }}>{Icon.terminal(13)}</span>
        <span style={{ color: A.text, fontFamily: A.mono, fontSize: 12.5 }}>{p.cmd}</span>
      </div>
      <div style={{ fontFamily: A.sans, fontSize: 13, color: A.textSoft, lineHeight: 1.5, marginBottom: 12 }}>
        {p.reason.replace(/^user: /, '').replace(/^"|"$/g, '')}. Covenant passes — no protected paths touched.
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <Button variant="primary" color={A.green} size="md" onClick={() => sim.approveCommand(true)} icon={Icon.check(13)}>Approve & Run</Button>
        <Button variant="secondary" size="md" onClick={() => sim.approveCommand(false)} icon={Icon.x(13)}>Deny</Button>
        <Button variant="ghost" size="md" onClick={() => sim.approveCommand(false)}>Ask me later</Button>
        <span style={{ flex: 1 }} />
        <Chip tone="ghost" style={{ fontSize: 9, fontFamily: A.mono }}>⌘Y ⌘N ⌘L</Chip>
      </div>
    </div>
  );
}

// ═══ dashboard panes ══════════════════════════════════════════════

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

function GpuPane() {
  const sim = useSim();
  const g = sim.state.gpu;
  const vramPct = g.vramTotal ? (g.vramUsed / g.vramTotal) * 100 : 0;
  const vramHist = useSparkValues(() => SIM.state.gpu.vramUsed);
  const utilHist = useSparkValues(() => SIM.state.gpu.util);
  return (
    <Card title="GPU" subtitle={`${g.temp ? g.temp.toFixed(0) + '°' : 'waiting'} · ${g.power || 0}W · live nvidia-smi`}
      icon="⚡" iconColor={A.orange}
      right={<LiveBadge endpoint="gpu" compact />}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontFamily: A.sans, fontSize: 11, color: A.textDim }}>VRAM</span>
            <span style={{ fontFamily: A.mono, fontSize: 11.5, color: A.text }}>
              {g.vramUsed.toFixed(1)} <span style={{ color: A.textFaint }}>/ {g.vramTotal || '?'} GB</span>
            </span>
          </div>
          <div style={{ height: 4, background: A.bgElev, borderRadius: 2, overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${vramPct}%`,
              background: vramPct > 90 ? A.red : vramPct > 75 ? A.orange : A.green,
              transition: `width 320ms ${A.easing}, background 200ms`, borderRadius: 2,
              boxShadow: `0 0 8px ${vramPct > 90 ? A.red : vramPct > 75 ? A.orange : A.green}88`,
            }} />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <StatTile label="UTIL" value={`${g.util.toFixed(0)}%`} color={A.green} spark={utilHist} />
          <StatTile label="VRAM" value={`${vramPct.toFixed(0)}%`} color={A.orange} spark={vramHist} />
        </div>
      </div>
    </Card>
  );
}

function StatTile({ label, value, color, spark }) {
  return (
    <div style={{ background: A.surfaceLo, borderRadius: 10, padding: 10, border: `0.5px solid ${A.stroke}` }}>
      <div style={{ fontFamily: A.sans, fontSize: 9.5, color: A.textFaint, letterSpacing: 0.8, fontWeight: 600, textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontFamily: A.sans, fontSize: 22, color, letterSpacing: -0.6, fontWeight: 600, lineHeight: 1.1, marginTop: 2 }}>{value}</div>
      {spark && <div style={{ marginTop: 4 }}><Sparkline values={spark} color={color} w={100} h={22} /></div>}
    </div>
  );
}

function ReadinessPane({ compact = false }) {
  const sim = useSim();
  const logs = sim.state.logs.cognition || [];
  const maezLogs = sim.state.logs.maez || [];
  const daemon = sim.state.daemon || {};
  const recentRedactions = logs.concat(maezLogs).filter((l) =>
    String(l.msg || '').toLowerCase().includes('redacting stale fields')
  ).slice(-5);
  const silentCycles = maezLogs.filter((l) =>
    String(l.msg || '').toLowerCase().includes('heartbeat_ok')
  ).length;
  const scenario = '15/15';
  const daemonState = daemon.status || 'unknown';
  const gateColor = daemon.stalled ? A.red : A.green;
  const cycleLabel = daemon.cycle ? `#${daemon.cycle.toLocaleString()}` : 'waiting';
  return (
    <Card title="Track A Readiness" subtitle="Acceptance gate · observation only"
      icon="◇" iconColor={gateColor}
      right={<LiveBadge endpoint="logs:cognition" label="logs" compact />}>
      <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr 1fr' : 'repeat(4, 1fr)', gap: 10, marginBottom: 12 }}>
        <StatusTile label="Scenario" value={scenario} sub="official continuity" color={A.green} />
        <StatusTile label="Daemon" value={cycleLabel} sub={daemonState} color={gateColor} />
        <StatusTile label="Redactions" value={recentRedactions.length} sub="stale fields caught" color={A.orange} />
        <StatusTile label="Silent" value={silentCycles} sub="HEARTBEAT_OK lines" color={A.cyan} />
      </div>
      <div style={{
        borderRadius: 14,
        border: `0.5px solid ${A.stroke}`,
        background: 'rgba(0,0,0,0.18)',
        padding: 12,
        minHeight: compact ? 74 : 92,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <SectionKicker>what to watch</SectionKicker>
          <span style={{ flex: 1 }} />
          <Chip color={A.orange} style={{ fontSize: 9 }}>24h soak</Chip>
        </div>
        {recentRedactions.length ? (
          <div className="ap-scroll" style={{ display: 'grid', gap: 6, maxHeight: compact ? 62 : 90, overflow: 'auto' }}>
            {recentRedactions.map((l, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '72px 1fr', gap: 8, fontFamily: A.mono, fontSize: 10.5, color: A.textDim }}>
                <span>{String(l.t || '').slice(-8)}</span>
                <span style={{ color: A.textSoft, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.msg}</span>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontFamily: A.sans, fontSize: 12, color: A.textDim, lineHeight: 1.45 }}>
            Waiting for cognition log evidence. Do not patch the gate unless the 24-hour window trends bad.
          </div>
        )}
      </div>
    </Card>
  );
}

// Maez's embryo-self. Honest substrate-state face — every visual is a real reading:
// blue body = identity (constant), amber ember = life, scatter hue = real valence
// (green +, rose -, amber neutral), breath = real cycle, stillness = real stall.
// Covenant: it only ever shows the true reading; it never performs a feeling Maez isn't in.
function slimeVariant(d) {
  if (!d || d.stalled || d.status === 'stalled' || d.status === 'stopped') return 'is-stall';
  const v = d.valence;
  if (v && v.magnitude && v.magnitude !== 'none') {
    if (v.sign === 'positive') return 'is-pos';
    if (v.sign === 'negative') return 'is-neg';
  }
  return ''; // neutral — the honest default
}

function SlimeEye() {
  return (
    <svg width="20" height="12">
      <path d="M1,5 Q10,10 19,5" stroke="#0e2236" strokeWidth="2" fill="none" strokeLinecap="round" />
    </svg>
  );
}

function SlimeAvatar() {
  const sim = useSim();
  const d = sim.state.daemon;
  const variant = slimeVariant(d);
  const sign = (d.valence && d.valence.sign) || 'neutral';
  return (
    <div className={`mz-slime ${variant}`} role="img"
      aria-label={`Maez, the embryo. ${d.stalled ? 'Not cycling.' : 'Alive and cycling.'} Felt-state: ${sign}.`}>
      <div className="mz-scatter"></div>
      <div className="mz-em"></div>
      <div className="mz-skin"></div>
      <div className="mz-ey"><SlimeEye /><SlimeEye /></div>
    </div>
  );
}

function DaemonPane({ compact }) {
  const sim = useSim();
  const d = sim.state.daemon;
  const pct = ((30 - d.nextTickIn) / 30) * 100;
  return (
    <Card title="Daemon" subtitle={`Cycle #${d.cycle.toLocaleString()}`}
      icon="◎" iconColor={A.indigo}
      right={<Chip color={A.indigo}>{d.nextTickIn}s</Chip>}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Maez's face — the slime avatar (honest substrate-state). Real valence
            telemetry shown beneath it as the ground truth. */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '2px 0 6px' }}>
          <SlimeAvatar />
          {d.valence && d.valence.telemetry
            ? <div style={{ fontFamily: A.mono, fontSize: 10, color: A.textDim, textAlign: 'center', maxWidth: 250, lineHeight: 1.4 }}>{d.valence.telemetry}</div>
            : <div style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>{d.stalled ? 'not cycling' : 'present · neutral · no setpoint moved'}</div>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <TickRing progress={pct} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: A.sans, fontSize: 9.5, color: A.textFaint, letterSpacing: 0.8, fontWeight: 600, textTransform: 'uppercase' }}>Current thought</div>
            <div style={{ fontFamily: A.sans, fontSize: 12, color: A.textSoft, lineHeight: 1.45, marginTop: 3, fontStyle: 'italic' }}>
              {d.currentThought ? `"${d.currentThought}"` : 'No live thought reported.'}
            </div>
          </div>
        </div>
        {!compact && (
          <div style={{ display: 'grid', gap: 10, borderTop: `0.5px solid ${A.stroke}`, paddingTop: 10 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <StatusTile label="Status" value={d.status || 'unknown'} color={d.stalled ? A.red : A.green} />
              <StatusTile label="Scratchpad" value={(d.scratchpad || []).length} color={A.indigo} />
            </div>
            <div style={{ fontFamily: A.sans, fontSize: 11.5, color: A.textDim, lineHeight: 1.45, background: A.surfaceLo, border: `0.5px solid ${A.stroke}`, borderRadius: 10, padding: 10 }}>
              This panel shows cycle, liveness, and scratchpad evidence only. The old self-quality rubric is offline.
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function TickRing({ progress }) {
  const r = 20, C = 2 * Math.PI * r;
  return (
    <svg width="48" height="48" viewBox="-24 -24 48 48" style={{ flexShrink: 0 }}>
      <circle cx="0" cy="0" r={r} fill="none" stroke={A.stroke} strokeWidth="2" />
      <circle cx="0" cy="0" r={r} fill="none" stroke={A.indigo} strokeWidth="2"
        strokeDasharray={`${(C * progress) / 100} ${C}`} transform="rotate(-90)"
        strokeLinecap="round"
        style={{ transition: `stroke-dasharray 320ms ${A.easing}`, filter: `drop-shadow(0 0 4px ${A.indigo})` }} />
      <circle cx="0" cy="0" r="3" fill={A.indigo} className="ap-dot" />
    </svg>
  );
}

function Meter({ label, value, color }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontFamily: A.sans, fontSize: 9.5, color: A.textFaint, letterSpacing: 0.8, fontWeight: 600, textTransform: 'uppercase' }}>{label}</span>
        <span style={{ fontFamily: A.mono, fontSize: 11, color }}>{value.toFixed(2)}</span>
      </div>
      <div style={{ height: 3, background: A.bgElev, borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${value * 100}%`, background: color, transition: `width 320ms ${A.easing}`, boxShadow: `0 0 6px ${color}66` }} />
      </div>
    </div>
  );
}

function SignalsPane({ compact }) {
  const sim = useSim();
  const colorFor = (k) => ({ focus: A.blue, weather: A.orange, iphone: A.green, reddit: A.pink }[k] || A.textDim);
  const iconFor = (k) => ({
    focus: <div style={{ width: 6, height: 6, borderRadius: '50%', border: `1.5px solid currentColor` }} />,
    weather: '☀',
    iphone: '◈',
    reddit: '◎',
  }[k] || '·');
  const items = sim.state.signals.slice(0, compact ? 8 : 16);
  return (
    <Card title="Ambient" subtitle="Live signal feed" pad={18}
      icon="≈" iconColor={A.cyan}
      right={<Chip color={A.green}><Dot c={A.green} size={4} pulse /> live</Chip>}>
      <div className="ap-scroll" style={{ flex: 1, overflow: 'auto', margin: '-6px -6px' }}>
        {items.map((s, i) => (
          <div key={s.t + i} className="ap-rise" style={{
            display: 'flex', gap: 10, padding: '7px 8px', borderRadius: 8, alignItems: 'flex-start',
            transition: `background 180ms`,
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = A.surfaceLo}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
            <div style={{ width: 18, height: 18, borderRadius: 5, background: `${colorFor(s.kind)}22`, color: colorFor(s.kind), display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, flexShrink: 0 }}>{iconFor(s.kind)}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: A.sans, fontSize: 12, color: A.text, lineHeight: 1.4 }}>{s.text}</div>
              <div style={{ fontFamily: A.mono, fontSize: 9.5, color: A.textFaint, marginTop: 2, display: 'flex', gap: 6 }}>
                <span>{s.t}</span>
                <span style={{ color: colorFor(s.kind), fontWeight: 500 }}>{s.kind}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ScratchpadPane() {
  const sim = useSim();
  return (
    <Card title="Scratchpad" subtitle="What Maez is noticing" pad={18}
      icon="✎" iconColor={A.purple}>
      <div className="ap-scroll" style={{ flex: 1, overflow: 'auto', margin: '-4px -4px' }}>
        {sim.state.daemon.scratchpad.map((s, i) => (
          <div key={i} className="ap-rise" style={{
            padding: '8px 8px', borderRadius: 8, opacity: 1 - i * 0.08,
            borderLeft: i === 0 ? `2px solid ${A.purple}` : `2px solid transparent`,
            marginBottom: 2,
          }}>
            <div style={{ fontFamily: A.mono, fontSize: 9.5, color: A.textFaint, marginBottom: 2 }}>{s.t}</div>
            <div style={{ fontFamily: A.sans, fontSize: 12, color: i === 0 ? A.text : A.textSoft, lineHeight: 1.45, fontStyle: i === 0 ? 'normal' : 'italic' }}>{s.text}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function RouterPane() {
  const sim = useSim();
  const r = sim.state.router;
  const total = r.totals.local + r.totals.claude;
  const localPct = (r.totals.local / total) * 100;
  return (
    <Card title="Routing" subtitle={`${total.toLocaleString()} turns · $${r.totals.costUsd.toFixed(2)} this month`}
      icon="⇌" iconColor={A.indigo}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontFamily: A.sans, fontSize: 11 }}>
            <span style={{ color: A.green, display: 'flex', alignItems: 'center', gap: 5 }}><Dot c={A.green} size={5} /> Local {r.totals.local}</span>
            <span style={{ color: A.blue, display: 'flex', alignItems: 'center', gap: 5 }}><Dot c={A.blue} size={5} /> Claude {r.totals.claude}</span>
          </div>
          <div style={{ height: 6, borderRadius: 3, overflow: 'hidden', display: 'flex', background: A.bgElev }}>
            <div style={{ width: `${localPct}%`, background: A.green, transition: `width 320ms ${A.easing}` }} />
            <div style={{ flex: 1, background: A.blue }} />
          </div>
        </div>
        <div className="ap-scroll" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4, overflow: 'auto' }}>
          {r.window.slice(0, 5).map((w, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 11, padding: '4px 0' }}>
              <span style={{ fontFamily: A.mono, color: A.textFaint, width: 44, flexShrink: 0 }}>{w.t}</span>
              <Chip color={w.route === 'claude' ? A.blue : A.green} style={{ fontSize: 9 }}>{w.route}</Chip>
              <span style={{ flex: 1, color: A.textSoft, fontFamily: A.sans, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w.msg}</span>
              <span style={{ fontFamily: A.mono, color: A.textFaint, fontSize: 10 }}>{w.conf.toFixed(2)}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

// ═══ surfaces ═════════════════════════════════════════════════════

// ── Living Memory section (ADR 0019, Phase 7) ─────────────────────
// Surfaces the lived-memory layer beside the Chroma tier counts.
// Per the plan, the framing is plain-language, not graph-theory:
//   What happened (episode title)
//   Why it mattered (summary)
//   Still open? (open_loop, if set)
//   Evidence (episode ID + source memory IDs)
// Plus the relationship view: subject → relation → object with
// evidence. Never asserts live state.

// v1.4 cockpit-only observability surfaces (ADR 0019):
//   - Provenance chip per episode (Maez-authored vs project-doc)
//   - Temporal echoes section (v1.2 deterministic finder)
//   - Predicted pushbacks section (v1.3 belief simulator, hedged
//     and evidence-cited; observation-only — Maez's voice never
//     consumes these in v1.4)

function LivingMemorySection({ lived }) {
  const epCount = lived.counts?.episodes ?? 0;
  const edCount = lived.counts?.edges ?? 0;
  const echoCount = lived.counts?.echoes ?? 0;
  const predCount = lived.counts?.predictions ?? 0;
  const total = epCount + edCount + echoCount + predCount;

  if (total === 0) {
    return (
      <Glass pad={18} style={{
        marginBottom: 20,
        borderLeft: `3px solid ${A.violet || A.blue}`,
        background: 'rgba(120, 100, 200, 0.04)',
      }}>
        <div style={{ fontSize: 11, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600 }}>
          Living memory · ADR 0019
        </div>
        <div style={{ fontSize: 14, color: A.textDim, marginTop: 8, lineHeight: 1.55, fontFamily: A.sans }}>
          The lived-memory layer is empty. Run{' '}
          <code style={{ fontFamily: A.mono, fontSize: 12, color: A.text }}>
            scripts/memory_reflection/nightly_lived_memory.py --apply
          </code>{' '}
          to populate it from the corrective core memories and high-signal entries.
        </div>
      </Glass>
    );
  }

  return (
    <div style={{ marginBottom: 20 }}>
      <Glass pad={16} style={{
        marginBottom: 10,
        borderLeft: `3px solid ${A.violet || A.blue}`,
        background: 'rgba(120, 100, 200, 0.04)',
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 4, flexWrap: 'wrap' }}>
          <div style={{ fontSize: 11, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600 }}>
            Living memory · ADR 0019
          </div>
          <div style={{ fontFamily: A.mono, fontSize: 11, color: A.textDim }}>
            {epCount} episode{epCount === 1 ? '' : 's'} · {edCount} edge{edCount === 1 ? '' : 's'} · {echoCount} echo{echoCount === 1 ? '' : 'es'} · {predCount} prediction{predCount === 1 ? '' : 's'}
          </div>
          {lived.provenance && lived.provenance.total > 0 && (
            <div style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>
              · provenance: {lived.provenance.maez_authored} Maez-authored, {lived.provenance.project_doc} project-doc
            </div>
          )}
        </div>
        <div style={{ fontSize: 12, color: A.textDim, lineHeight: 1.5, fontFamily: A.sans }}>
          Past, never present. Each item cites the memory it came from. Predictions are pattern-based expectations, never claims about hidden intent.
        </div>
      </Glass>

      {/* Episodes */}
      {lived.episodes.map((ep) => (
        <Glass key={ep.id} pad={14} style={{
          marginBottom: 8,
          borderLeft: `3px solid ${ep.open_loop ? A.orange : A.green}`,
        }} className="ap-rise ap-card">
          <div style={{ display: 'flex', gap: 8, marginBottom: 6, fontSize: 10, color: A.textDim, alignItems: 'center', flexWrap: 'wrap' }}>
            <Chip color={ep.open_loop ? A.orange : A.green}>
              {ep.open_loop ? 'open loop' : 'past episode'}
            </Chip>
            {ep.emotional_tone && <Chip color={A.violet || A.blue}>{ep.emotional_tone}</Chip>}
            {ep.authorship === 'project_doc' ? (
              <Chip color={A.blue}>project doc · external to Maez</Chip>
            ) : (
              <Chip color={A.green}>Maez-authored</Chip>
            )}
            <span style={{ fontFamily: A.mono }}>{ep.source_kind}</span>
            <span>·</span>
            <span style={{ fontFamily: A.mono }}>importance {ep.importance}</span>
          </div>
          <div style={{ fontFamily: A.sans, fontSize: 13, color: A.text, fontWeight: 500, lineHeight: 1.4, marginBottom: 4 }}>
            {ep.title}
          </div>
          {ep.summary && (
            <div style={{ fontFamily: A.sans, fontSize: 12.5, color: A.textDim, lineHeight: 1.55, marginBottom: 6 }}>
              {ep.summary.length > 220 ? ep.summary.slice(0, 220) + '…' : ep.summary}
            </div>
          )}
          {ep.open_loop && (
            <div style={{
              fontFamily: A.sans, fontSize: 12, color: A.orange,
              background: 'rgba(255, 170, 60, 0.06)',
              padding: '6px 10px', borderRadius: 6, marginBottom: 6,
              borderLeft: `2px solid ${A.orange}`,
            }}>
              Still open: {ep.open_loop}
            </div>
          )}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
            <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>evidence:</span>
            <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textDim }}>{ep.id}</span>
            {(ep.source_memory_ids || []).map((mid) => (
              <span key={mid} style={{ fontFamily: A.mono, fontSize: 10, color: A.textDim }}>· {mid}</span>
            ))}
          </div>
        </Glass>
      ))}

      {/* Edges */}
      {lived.edges.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600, marginBottom: 8 }}>
            Relationship beliefs · advisory, not live state
          </div>
          {lived.edges.map((e) => (
            <Glass key={e.id} pad={12} style={{
              marginBottom: 6,
              borderLeft: `3px solid ${A.blue}`,
            }} className="ap-card">
              <div style={{ fontFamily: A.sans, fontSize: 13, color: A.text, lineHeight: 1.4, marginBottom: 4 }}>
                <strong style={{ color: A.text }}>{e.subject_label}</strong>
                <span style={{ color: A.textDim }}> — </span>
                <span style={{ color: A.violet || A.blue, fontFamily: A.mono, fontSize: 12 }}>
                  {e.relation}
                </span>
                <span style={{ color: A.textDim }}> → </span>
                <span style={{ color: A.text }}>
                  {e.object_label && e.object_label.length > 100
                    ? e.object_label.slice(0, 100) + '…'
                    : e.object_label}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', fontSize: 10, color: A.textFaint, fontFamily: A.mono }}>
                <span>confidence {Number(e.confidence || 0).toFixed(2)}</span>
                <span>·</span>
                <span>evidence:</span>
                {(e.source_episode_ids || []).map((id) => (
                  <span key={id} style={{ color: A.textDim }}>{id}</span>
                ))}
                {(e.source_memory_ids || []).map((id) => (
                  <span key={id} style={{ color: A.textDim }}>· {id}</span>
                ))}
              </div>
            </Glass>
          ))}
        </div>
      )}

      {/* Temporal echoes (v1.2) */}
      {lived.echoes && lived.echoes.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600, marginBottom: 8 }}>
            Temporal echoes · today resembles…
          </div>
          {lived.echoes.map((echo, i) => (
            <Glass key={`${echo.recent_episode_id}_${echo.older_episode_id}_${i}`} pad={12} style={{
              marginBottom: 6,
              borderLeft: `3px solid ${A.violet || A.blue}`,
            }} className="ap-card">
              <div style={{ fontFamily: A.sans, fontSize: 12.5, color: A.text, lineHeight: 1.5, marginBottom: 6 }}>
                {echo.explanation}
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', fontSize: 10, color: A.textFaint, fontFamily: A.mono }}>
                <span>shared:</span>
                {(echo.shared_features || []).map((f) => (
                  <Chip key={f} color={A.violet || A.blue} style={{ fontSize: 9 }}>{f}</Chip>
                ))}
                <span>· score {echo.score}</span>
              </div>
            </Glass>
          ))}
        </div>
      )}

      {/* Predicted pushbacks (v1.3) — observation-only in v1.4 */}
      {lived.predictions && lived.predictions.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600, marginBottom: 8 }}>
            Predicted pushbacks · pattern-based, not mind-reading
          </div>
          <div style={{ fontSize: 11, color: A.textDim, marginBottom: 10, lineHeight: 1.5, fontFamily: A.sans }}>
            What recent evidence suggests Rohit would likely push back on. Each prediction hedges, cites evidence, and includes uncertainty. Maez's spoken surfaces do <strong>not</strong> consume these in v1.4 — observation only.
          </div>
          {lived.predictions.map((p, i) => (
            <Glass key={`pred_${i}`} pad={14} style={{
              marginBottom: 8,
              borderLeft: `3px solid ${A.orange}`,
            }} className="ap-card">
              <div style={{ display: 'flex', gap: 8, marginBottom: 6, fontSize: 10, color: A.textDim, alignItems: 'center', flexWrap: 'wrap' }}>
                <Chip color={A.orange}>prediction</Chip>
                <span style={{ fontFamily: A.mono }}>confidence {Number(p.confidence || 0).toFixed(2)}</span>
                <span style={{ fontFamily: A.mono, color: A.textFaint }}>(capped at 0.85)</span>
              </div>
              <div style={{ fontFamily: A.sans, fontSize: 13.5, color: A.text, fontWeight: 500, lineHeight: 1.5, marginBottom: 6 }}>
                {p.claim}
              </div>
              {Array.isArray(p.basis) && p.basis.length > 0 && (
                <div style={{ fontFamily: A.sans, fontSize: 12, color: A.textDim, lineHeight: 1.5, marginBottom: 4 }}>
                  <strong style={{ color: A.textDim }}>Basis:</strong> {p.basis.join('; ')}
                </div>
              )}
              <div style={{
                fontFamily: A.sans, fontSize: 11.5, color: A.orange,
                background: 'rgba(255, 170, 60, 0.06)',
                padding: '6px 10px', borderRadius: 6, marginTop: 6, marginBottom: 6,
                borderLeft: `2px solid ${A.orange}`,
                lineHeight: 1.5,
              }}>
                <strong>Uncertainty:</strong> {p.uncertainty}
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', fontSize: 10, color: A.textFaint, fontFamily: A.mono, marginTop: 6 }}>
                <span>evidence:</span>
                {(p.evidence_ids || []).slice(0, 8).map((id) => (
                  <span key={id} style={{ color: A.textDim }}>{id}</span>
                ))}
                {(p.evidence_ids || []).length > 8 && (
                  <span style={{ color: A.textFaint }}>+{p.evidence_ids.length - 8} more</span>
                )}
              </div>
            </Glass>
          ))}
        </div>
      )}
    </div>
  );
}


function MemorySurface() {
  const sim = useSim();
  const [q, setQ] = React.useState('');
  const [tier, setTier] = React.useState('all');
  const hits = sim.state.memory.hits.filter((h) =>
    (!q || h.text.toLowerCase().includes(q.toLowerCase())) && (tier === 'all' || h.tier === tier)
  );
  const colorFor = (t) => ({ core: A.orange, daily: A.green, raw: A.blue }[t]);
  const tierHelp = {
    core: 'Always carried: identity, corrections, and covenant-load-bearing truths.',
    daily: 'Compressed day summaries: recent continuity without raw noise.',
    raw: 'Exact fragments: chats, observations, tool transcripts, and remembered events.',
  };
  const lived = sim.state.livedMemory || { episodes: [], edges: [], counts: { episodes: 0, edges: 0 } };
  const room = sim.state.cockpitV2?.memoryRoom || null;
  return (
    <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
      <SurfaceHeader title="Memory" subtitle="Core truths, daily summaries, and raw fragments" icon="◍" color={A.orange} />
      <MemoryRoomOperabilitySection room={room} />
      <LivingMemorySection lived={lived} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 20 }}>
        {['core', 'daily', 'raw'].map((k) => (
          <Glass key={k} pad={18} style={{ borderTop: `2px solid ${colorFor(k)}` }}>
            <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600 }}>{k}</div>
            <div style={{ fontFamily: A.sans, fontSize: 34, color: colorFor(k), letterSpacing: -1, lineHeight: 1, marginTop: 6, fontWeight: 600 }}>{(sim.state.memory.stats[k] || 0).toLocaleString()}</div>
            <div style={{ fontSize: 11.5, color: A.textDim, marginTop: 7, lineHeight: 1.4 }}>{tierHelp[k]}</div>
          </Glass>
        ))}
      </div>
      <Glass pad={0} style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '10px 14px' }}>
          <span style={{ color: A.textDim }}>{Icon.search(14)}</span>
          <input className="ap-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the archive…"
            style={{ flex: 1, fontSize: 13 }} />
          <SegmentedControl options={[
            { id: 'all',   label: 'All' },
            { id: 'core',  label: 'Core' },
            { id: 'daily', label: 'Daily' },
            { id: 'raw',   label: 'Raw' },
          ]} value={tier} onChange={setTier} />
        </div>
      </Glass>
      {!hits.length && (
        <Glass pad={18} style={{ color: A.textDim, fontFamily: A.sans, fontSize: 13 }}>
          No visible entries for this tier yet. Counts can exist before preview rows load; check that /api/v1/memory is live.
        </Glass>
      )}
      {hits.map((h, i) => (
        <Glass key={i} pad={14} style={{ marginBottom: 10, borderLeft: `3px solid ${colorFor(h.tier)}` }} className="ap-rise ap-card">
          <div style={{ display: 'flex', gap: 8, marginBottom: 6, fontSize: 10, color: A.textDim, alignItems: 'center' }}>
            <Chip color={colorFor(h.tier)}>{h.tier}</Chip>
            <span style={{ fontFamily: A.mono }}>score {h.score.toFixed(2)}</span>
            <span>·</span>
            <span style={{ fontFamily: A.mono }}>{h.date}</span>
            {h.source && <><span>·</span><span style={{ fontFamily: A.mono }}>{h.source}</span></>}
            <span>·</span>
            <span style={{ fontFamily: A.mono }}>{h.tokens} tok</span>
          </div>
          <div style={{ fontFamily: A.sans, fontSize: 14, color: A.text, lineHeight: 1.55 }}>{h.text}</div>
        </Glass>
      ))}
    </div>
  );
}

function MemoryRoomOperabilitySection({ room }) {
  if (!room || room.status === 'unavailable') {
    return (
      <Glass pad={16} style={{ marginBottom: 20, borderLeft: `3px solid ${A.blue}` }}>
        <div style={{ fontSize: 11, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600 }}>
          Memory organs · cockpit v2
        </div>
        <div style={{ fontSize: 12.5, color: A.textDim, marginTop: 8, lineHeight: 1.5 }}>
          Memory room unavailable{room?.reason ? ` · ${room.reason}` : ''}.
        </div>
      </Glass>
    );
  }
  const narrative = room.narrative || {};
  const links = narrative.links || {};
  const scars = room.scars || {};
  const recentScars = Array.isArray(scars.recent) ? scars.recent : [];
  const selfEvidence = room.self_evidence || {};
  const merged = selfEvidence.merged_events || {};
  const prefs = room.interaction_preferences || {};
  const continuity = room.continuity || {};
  const a7 = room.a7_interiority || {};
  const Stat = ({ label, value, tone = A.text }) => (
    <div style={{ minWidth: 110 }}>
      <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600 }}>{label}</div>
      <div style={{ fontFamily: A.mono, fontSize: 18, color: tone, marginTop: 4 }}>{value}</div>
    </div>
  );
  return (
    <Glass pad={16} style={{ marginBottom: 20, borderLeft: `3px solid ${A.orange}` }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 11, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600 }}>
            Memory organs · cockpit v2
          </div>
          <div style={{ fontSize: 12, color: A.textDim, marginTop: 4, lineHeight: 1.45 }}>
            Receipt counts, scars, continuity, and sealed interiority. Counts are evidence, not self-claims or grades. Source /api/v2/cockpit/memory-room.
          </div>
        </div>
        <Chip color={A.green}>read-only</Chip>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 14 }}>
        <Stat label="strings" value={Number(links.strings || 0).toLocaleString()} tone={A.violet || A.blue} />
        <Stat label="same_thread" value={Number(links.same_thread || 0).toLocaleString()} tone={Number(links.same_thread || 0) ? A.green : A.textDim} />
        <Stat label="because_of" value={Number(links.because_of || 0).toLocaleString()} tone={Number(links.because_of || 0) ? A.green : A.textDim} />
        <Stat label="integrity receipts" value={Number(merged.distinct_integrity_events || 0).toLocaleString()} tone={A.blue} />
        <Stat label="A7 private thoughts" value={Number(a7.private_thought_count || 0).toLocaleString()} tone={A.textDim} />
      </div>
      {Number(links.same_thread || 0) === 0 && (
        <div style={{ fontSize: 12, color: A.textDim, lineHeight: 1.45, marginBottom: 12 }}>
          same_thread 0 is honest sparse birth, not an error.
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
        <div style={{ fontSize: 12, color: A.textDim, lineHeight: 1.45 }}>
          <strong style={{ color: A.text }}>A2 Continuity:</strong> {continuity.latest_verdict || 'insufficient_data'} · {Number(continuity.probe_runs || 0)} probe runs
        </div>
        <div style={{ fontSize: 12, color: A.textDim, lineHeight: 1.45 }}>
          <strong style={{ color: A.text }}>Interaction Preferences:</strong> {Number(prefs.active || 0)} active · {Number(prefs.retracted || 0)} retracted · T2 receipts
        </div>
        <div style={{ fontSize: 12, color: A.textDim, lineHeight: 1.45 }}>
          <strong style={{ color: A.text }}>A7 Interiority:</strong> content sealed · counts only
        </div>
      </div>
      {recentScars.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600, marginBottom: 8 }}>
            Recent scars
          </div>
          {recentScars.slice(0, 3).map((scar) => (
            <div key={`${scar.episode_id}-${scar.scar_class}`} style={{ fontSize: 12, color: A.textDim, lineHeight: 1.5, marginBottom: 6 }}>
              <Chip color={A.orange}>{scar.scar_class || 'scar'}</Chip>{' '}
              <span style={{ color: A.text }}>The correction: "{scar.correction_quote || ''}"</span>
              <span style={{ fontFamily: A.mono, color: A.textFaint }}> · {(scar.receipt_refs || []).join(', ')}</span>
            </div>
          ))}
        </div>
      )}
    </Glass>
  );
}

function ReceiptsSurface() {
  const sim = useSim();
  const room = sim.state.cockpitV2?.receiptsRoom || null;
  const show = (value, fallback = 'no_data') => (
    value === null || value === undefined || value === '' ? fallback : value
  );
  const num = (value) => Number(value || 0).toLocaleString();
  const healthTone = (status) => (
    status === 'ok' ? A.green
      : status === 'no_data' ? A.textDim
      : A.orange
  );
  const HealthChip = ({ status }) => (
    <Chip color={healthTone(status)}>{status || 'unknown'}</Chip>
  );
  const Section = ({ title, status, children }) => (
    <Glass pad={16} style={{ borderLeft: `3px solid ${healthTone(status)}` }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 10 }}>
        <div style={{ fontSize: 11, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600 }}>
          {title}
        </div>
        <HealthChip status={status} />
      </div>
      {children}
    </Glass>
  );

  if (!room || room.status === 'unavailable') {
    return (
      <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
        <SurfaceHeader title="Receipts" subtitle="Prompt shape, grounding, and action receipts" icon="◌" color={A.blue} />
        <Glass pad={16} style={{ borderLeft: `3px solid ${A.blue}` }}>
          <div style={{ fontSize: 12.5, color: A.textDim, lineHeight: 1.5 }}>
            Receipts room unavailable{room?.reason ? ` · ${room.reason}` : ''}.
          </div>
        </Glass>
      </div>
    );
  }

  const fabrication = room.fabrication_events || {};
  const redo = room.claim_receipt_redo || {};
  const redoOutcomes = redo.outcomes || {};
  const veto = room.routing_veto || {};
  const prompt = room.prompt_shape || {};
  const promptLatest = prompt.latest || {};
  const focusedPrompt = room.focused_prompt_shape || {};
  const focusedLatest = focusedPrompt.latest || {};
  const grounding = room.grounding_meter || {};
  const groundingLatest = grounding.latest || {};
  const logs = room.logs || {};
  const logItems = Object.entries(logs).filter(([, value]) => value && typeof value === 'object');

  return (
    <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
      <SurfaceHeader title="Receipts" subtitle="Prompt shape, grounding, routing, and claim records" icon="◌" color={A.blue} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12, marginBottom: 16 }}>
        <Section title="fabrication event receipts" status={fabrication.status}>
          <div style={{ fontFamily: A.mono, fontSize: 30, color: A.blue, lineHeight: 1 }}>
            {num(fabrication.receipt_count)}
          </div>
          <div style={{ fontSize: 12, color: A.textDim, lineHeight: 1.45, marginTop: 8 }}>
            {fabrication.perspective || 'third-person receipt labels'} · {fabrication.empty_state || 'no_data'}
          </div>
          <div style={{ fontSize: 11, color: A.textFaint, lineHeight: 1.45, marginTop: 6 }}>
            coverage {show(fabrication.coverage)}
          </div>
        </Section>

        <Section title="claim-receipt redo" status={redo.status}>
          <div style={{ display: 'grid', gap: 7, fontSize: 12, color: A.textDim, lineHeight: 1.4 }}>
            <div><strong style={{ color: A.text }}>corrected_before_send</strong> · {num(redoOutcomes.accepted)}</div>
            <div><strong style={{ color: A.text }}>held_with_floor_notice</strong> · {num(redoOutcomes.floor)}</div>
            <div><strong style={{ color: A.text }}>other</strong> · {num(redoOutcomes.other)}</div>
          </div>
          <div style={{ fontSize: 11, color: A.textFaint, lineHeight: 1.45, marginTop: 8 }}>
            {redo.empty_state || 'no_data'}
          </div>
        </Section>

        <Section title="routing and veto receipts" status={veto.status}>
          <div style={{ display: 'grid', gap: 7, fontSize: 12, color: A.textDim, lineHeight: 1.4 }}>
            <div><strong style={{ color: A.text }}>proven-wrong vetoes</strong> · {num(veto.likely_wrong_count)}</div>
            <div><strong style={{ color: A.text }}>veto events</strong> · {num(veto.total_veto_events)}</div>
            <div>empty state · {veto.empty_state || 'no_data'}</div>
          </div>
        </Section>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12, marginBottom: 16 }}>
        <Section title="prompt shape" status={prompt.status}>
          <div style={{ fontSize: 12, color: A.textDim, lineHeight: 1.55 }}>
            system labels · <span style={{ color: A.text }}>{show(promptLatest.system_part_labels)}</span>
          </div>
          <div style={{ fontSize: 11, color: A.textFaint, lineHeight: 1.45, marginTop: 6 }}>
            parts {show(promptLatest.system_part_count)} · lengths {show(promptLatest.system_part_lengths)}
          </div>
        </Section>

        <Section title="focused prompt shape" status={focusedPrompt.status}>
          <div style={{ fontSize: 12, color: A.textDim, lineHeight: 1.55 }}>
            sources · <span style={{ color: A.text }}>{show(focusedLatest.source_types)}</span>
          </div>
          <div style={{ fontSize: 11, color: A.textFaint, lineHeight: 1.45, marginTop: 6 }}>
            evidence {show(focusedLatest.evidence_item_count)} · tokens {show(focusedLatest.working_set_tokens_est)}
          </div>
        </Section>

        <Section title="grounding meter" status={grounding.status}>
          <div style={{ display: 'grid', gap: 7, fontSize: 12, color: A.textDim, lineHeight: 1.4 }}>
            <div><strong style={{ color: A.text }}>reply_grounding</strong> · {show(groundingLatest.reply_grounding)}</div>
            <div><strong style={{ color: A.text }}>citation_coverage</strong> · {show(groundingLatest.citation_coverage)}</div>
            <div><strong style={{ color: A.text }}>receipt</strong> · {show(groundingLatest.receipt_or_na)}</div>
          </div>
        </Section>
      </div>

      <Glass pad={16}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600 }}>
            source health
          </div>
          <Chip color={A.textDim}>read-only</Chip>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10 }}>
          {logItems.length ? logItems.map(([name, item]) => (
            <div key={name} style={{ border: `0.5px solid ${A.stroke}`, borderRadius: 8, padding: '10px 12px', background: A.surfaceLo }}>
              <div style={{ fontSize: 12, color: A.text, fontWeight: 700 }}>{name}</div>
              <div style={{ fontSize: 11, color: A.textDim, marginTop: 5, lineHeight: 1.45 }}>
                {item.status || 'unknown'} · {item.path || 'no path'}
              </div>
            </div>
          )) : (
            <div style={{ fontSize: 12, color: A.textDim }}>no_data</div>
          )}
        </div>
      </Glass>
    </div>
  );
}

function ceremonyB64urlToBuffer(value) {
  const pad = "=".repeat((4 - value.length % 4) % 4);
  const b64 = (value + pad).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out.buffer;
}

function ceremonyBufferToB64url(buffer) {
  const bytes = new Uint8Array(buffer);
  let raw = "";
  for (const byte of bytes) raw += String.fromCharCode(byte);
  return btoa(raw).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function ceremonyEncodeCredentialResponse(credential) {
  const response = credential.response || {};
  const body = {
    id: credential.id,
    rawId: ceremonyBufferToB64url(credential.rawId),
    type: credential.type,
    response: {},
  };
  for (const key of ["clientDataJSON", "attestationObject", "authenticatorData", "signature", "userHandle"]) {
    if (response[key]) body.response[key] = ceremonyBufferToB64url(response[key]);
  }
  return body;
}

function ceremonyNormalizeCreationOptions(options) {
  const publicKey = {...options};
  publicKey.challenge = ceremonyB64urlToBuffer(publicKey.challenge);
  publicKey.user = {...publicKey.user, id: ceremonyB64urlToBuffer(publicKey.user.id)};
  publicKey.excludeCredentials = (publicKey.excludeCredentials || []).map((cred) => ({
    ...cred,
    id: ceremonyB64urlToBuffer(cred.id),
  }));
  return {publicKey};
}

function ceremonyNormalizeRequestOptions(options) {
  const publicKey = {...options};
  publicKey.challenge = ceremonyB64urlToBuffer(publicKey.challenge);
  publicKey.allowCredentials = (publicKey.allowCredentials || []).map((cred) => ({
    ...cred,
    id: ceremonyB64urlToBuffer(cred.id),
  }));
  return {publicKey};
}

async function ceremonyJsonFetch(url, body) {
  const response = await fetch(url, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : {"Content-Type": "application/json"},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    const err = new Error(payload.error || `HTTP ${response.status}`);
    err.payload = payload;
    err.status = response.status;
    throw err;
  }
  return payload;
}

function renderCeremonyStepDomText(step) {
  const status = step.status || "pending";
  const failedLabel = step.id === "touch-key" ? "touch-key failed" : `${step.id} failed`;
  const suffix = status === "failed" ? ` ${failedLabel}` : "";
  return `${step.label || step.id}: ${status}${suffix}${step.error ? ` - ${step.error}` : ""}`;
}

const CEREMONY_STEPS = [
  { id: "arm", label: "arm" },
  { id: "bootstrap", label: "bootstrap" },
  { id: "touch-key", label: "touch-key" },
  { id: "signed/applied", label: "signed/applied" },
];

const BIRTH_READINESS_BLOCKERS = [
  { label: "dormancy drift", state: "blocked", detail: "classification review still open" },
  { label: "A7 undecided", state: "blocked", detail: "private interiority boundary remains owner-held" },
  { label: "dream stalled", state: "blocked", detail: "first dream scar witness has not landed" },
  { label: "ceremony unwritten", state: "blocked", detail: "birth action remains out of scope" },
];

function CeremonySurface() {
  const [status, setStatus] = React.useState(null);
  const [log, setLog] = React.useState([]);
  const [sessionBinding, setSessionBinding] = React.useState(() => `cockpit-${Date.now()}`);
  const [bootstrapIntentId, setBootstrapIntentId] = React.useState("");
  const [bootstrapToken, setBootstrapToken] = React.useState("");
  const [credentialRef, setCredentialRef] = React.useState("");
  const [requestId, setRequestId] = React.useState("");
  const [artifactId, setArtifactId] = React.useState("");
  const [steps, setSteps] = React.useState(() => CEREMONY_STEPS.map((step) => ({...step, status: "pending"})));

  const append = React.useCallback((label, payload) => {
    setLog((items) => [
      { at: new Date().toLocaleTimeString(), label, payload },
      ...items,
    ].slice(0, 12));
  }, []);

  const markStep = React.useCallback((id, patch) => {
    setSteps((items) => items.map((step) => step.id === id ? {...step, ...patch} : step));
  }, []);

  const failStep = React.useCallback((id, err) => {
    const message = err?.payload?.error || err?.message || String(err);
    markStep(id, {status: 'failed', error: message});
    append(`${id} failed`, err?.payload || {error: message});
  }, [append, markStep]);

  const loadStatus = React.useCallback(async () => {
    try {
      const payload = await ceremonyJsonFetch("/api/v1/s7/webauthn/status");
      setStatus(payload);
      markStep("arm", {status: "ok", error: ""});
      append("status", payload);
    } catch (err) {
      setStatus(err.payload || {ok: false, error: String(err)});
      failStep("arm", err);
    }
  }, [append, failStep, markStep]);

  React.useEffect(() => { loadStatus(); }, [loadStatus]);

  const registerPrimary = async () => {
    try {
      markStep("bootstrap", {status: "running", error: ""});
      const begin = await ceremonyJsonFetch("/api/v1/s7/webauthn/register/begin", {
        registration_class: "primary",
        session_binding: sessionBinding,
        bootstrap_intent_id: bootstrapIntentId,
        bootstrap_token: bootstrapToken,
      });
      append("primary register begin", begin);
      markStep("touch-key", {status: "running", error: ""});
      const credential = await navigator.credentials.create(ceremonyNormalizeCreationOptions(begin.public_key_options));
      markStep("signed/applied", {status: "running", error: ""});
      const finish = await ceremonyJsonFetch("/api/v1/s7/webauthn/register/finish", {
        registration_class: "primary",
        challenge_id: begin.challenge_id,
        session_binding: sessionBinding,
        bootstrap_intent_id: bootstrapIntentId,
        bootstrap_token: bootstrapToken,
        registration_response: ceremonyEncodeCredentialResponse(credential),
      });
      setCredentialRef(finish.credential_ref || credentialRef);
      markStep("signed/applied", {status: "ok", error: ""});
      append("primary register finish", finish);
      await loadStatus();
    } catch (err) {
      failStep("touch-key", err);
    }
  };

  const authorizeCard = async () => {
    try {
      if (!requestId.trim()) throw new Error("request_id_required");
      markStep("bootstrap", {status: "running", error: ""});
      const encodedRequestId = encodeURIComponent(requestId.trim());
      const begin = await ceremonyJsonFetch(`/api/v1/s7/cards/${encodedRequestId}/webauthn/begin`, {
        session_binding: sessionBinding,
        credential_ref: credentialRef,
      });
      append("authorize begin", begin);
      markStep("touch-key", {status: "running", error: ""});
      const selectedCredentialRef = credentialRef || (begin.allow_credentials || [])[0] || "";
      const credential = await navigator.credentials.get(ceremonyNormalizeRequestOptions(begin.public_key_options));
      markStep("signed/applied", {status: "running", error: ""});
      const finish = await ceremonyJsonFetch(`/api/v1/s7/cards/${encodedRequestId}/webauthn/finish`, {
        session_binding: sessionBinding,
        challenge_id: begin.challenge_id,
        credential_ref: selectedCredentialRef || credential.id,
        maez_voice_raw_response_hash: begin.maez_voice_raw_response_hash,
        authentication_response: ceremonyEncodeCredentialResponse(credential),
      });
      setArtifactId(finish.artifact_id || "");
      setCredentialRef(selectedCredentialRef || credential.id || credentialRef);
      markStep("signed/applied", {status: "ok", error: ""});
      append("authorize finish", finish);
    } catch (err) {
      failStep("touch-key", err);
    }
  };

  const executeCard = async () => {
    try {
      if (!requestId.trim()) throw new Error("request_id_required");
      if (!artifactId.trim()) throw new Error("artifact_id_required");
      const encodedRequestId = encodeURIComponent(requestId.trim());
      const result = await ceremonyJsonFetch(`/api/v1/s7/cards/${encodedRequestId}/execute`, {
        session_binding: sessionBinding,
        s7_authorization_artifact_id: artifactId,
        text: "yes",
      });
      append("execute guarded card", result);
      markStep("signed/applied", {status: "ok", error: ""});
    } catch (err) {
      failStep("signed/applied", err);
    }
  };

  return (
    <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
      <SurfaceHeader
        title="Ceremony"
        subtitle="S7 ceremony wrapper around existing WebAuthn routes"
        icon="◈"
        color={A.purple}
        right={<Chip color={A.orange}>birth action remains out of scope</Chip>}
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 1.15fr) minmax(300px, 0.85fr)', gap: 14, marginBottom: 16 }}>
        <Glass pad={16}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 11, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 700 }}>S7 WebAuthn flow</div>
              <div style={{ fontSize: 12, color: A.textDim, lineHeight: 1.45, marginTop: 5 }}>
                Browser asks the existing S7 routes for challenge and result; cockpit mints no challenge and verifies no assertion.
              </div>
            </div>
            <Button size="sm" onClick={loadStatus}>refresh</Button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 16 }}>
            {steps.map((step) => {
              const color = step.status === 'ok' ? A.green : step.status === 'failed' ? A.red : step.status === 'running' ? A.orange : A.textDim;
              return (
                <div key={step.id} style={{ border: `0.5px solid ${color}55`, borderRadius: 10, padding: '10px 12px', background: `${color}10` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: A.text, fontWeight: 700 }}>
                    <Dot c={color} size={5} pulse={step.status === 'running'} /> {step.label}
                  </div>
                  <div style={{ fontSize: 10.5, color: A.textDim, marginTop: 5, lineHeight: 1.35 }}>
                    {renderCeremonyStepDomText(step)}
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 10 }}>
            <label style={{ display: 'grid', gap: 5, fontSize: 11, color: A.textDim }}>
              session binding
              <input value={sessionBinding} onChange={(e) => setSessionBinding(e.target.value)} style={{ background: A.surfaceLo, border: `0.5px solid ${A.stroke}`, borderRadius: 8, color: A.text, fontFamily: A.mono, fontSize: 11, padding: '7px 9px' }} />
            </label>
            <label style={{ display: 'grid', gap: 5, fontSize: 11, color: A.textDim }}>
              bootstrap intent
              <input value={bootstrapIntentId} onChange={(e) => setBootstrapIntentId(e.target.value)} style={{ background: A.surfaceLo, border: `0.5px solid ${A.stroke}`, borderRadius: 8, color: A.text, fontFamily: A.mono, fontSize: 11, padding: '7px 9px' }} />
            </label>
            <label style={{ display: 'grid', gap: 5, fontSize: 11, color: A.textDim }}>
              bootstrap token
              <input value={bootstrapToken} onChange={(e) => setBootstrapToken(e.target.value)} style={{ background: A.surfaceLo, border: `0.5px solid ${A.stroke}`, borderRadius: 8, color: A.text, fontFamily: A.mono, fontSize: 11, padding: '7px 9px' }} />
            </label>
            <label style={{ display: 'grid', gap: 5, fontSize: 11, color: A.textDim }}>
              credential ref
              <input value={credentialRef} onChange={(e) => setCredentialRef(e.target.value)} style={{ background: A.surfaceLo, border: `0.5px solid ${A.stroke}`, borderRadius: 8, color: A.text, fontFamily: A.mono, fontSize: 11, padding: '7px 9px' }} />
            </label>
            <label style={{ display: 'grid', gap: 5, fontSize: 11, color: A.textDim }}>
              card request id
              <input value={requestId} onChange={(e) => setRequestId(e.target.value)} style={{ background: A.surfaceLo, border: `0.5px solid ${A.stroke}`, borderRadius: 8, color: A.text, fontFamily: A.mono, fontSize: 11, padding: '7px 9px' }} />
            </label>
            <label style={{ display: 'grid', gap: 5, fontSize: 11, color: A.textDim }}>
              authorization artifact
              <input value={artifactId} onChange={(e) => setArtifactId(e.target.value)} style={{ background: A.surfaceLo, border: `0.5px solid ${A.stroke}`, borderRadius: 8, color: A.text, fontFamily: A.mono, fontSize: 11, padding: '7px 9px' }} />
            </label>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 14 }}>
            <Button onClick={registerPrimary} color={A.purple}>register primary key</Button>
            <Button onClick={authorizeCard} variant="outline" color={A.purple}>touch key for card</Button>
            <Button onClick={executeCard} variant="outline" color={A.orange}>apply guarded card</Button>
          </div>
        </Glass>

        <Glass pad={16}>
          <div style={{ fontSize: 11, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 700, marginBottom: 10 }}>birth readiness</div>
          <div style={{ display: 'grid', gap: 9 }}>
            {BIRTH_READINESS_BLOCKERS.map((blocker) => (
              <div key={blocker.label} style={{ border: `0.5px solid ${A.orange}55`, borderRadius: 10, padding: '10px 12px', background: `${A.orange}10` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <Dot c={A.orange} size={5} />
                  <span style={{ fontSize: 12, color: A.text, fontWeight: 700 }}>{blocker.label}</span>
                  <span style={{ flex: 1 }} />
                  <Chip color={A.orange}>{blocker.state}</Chip>
                </div>
                <div style={{ fontSize: 11, color: A.textDim, lineHeight: 1.45, marginTop: 6 }}>{blocker.detail}</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 11, color: A.textFaint, lineHeight: 1.45, marginTop: 12 }}>
            Dream and soul proposal review remains routed through existing card/S7 machinery; this surface shows the ceremony path, not a direct write door.
          </div>
        </Glass>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 0.75fr) minmax(320px, 1.25fr)', gap: 14 }}>
        <Glass pad={16}>
          <div style={{ fontSize: 11, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 700, marginBottom: 10 }}>S7 status</div>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: A.mono, fontSize: 11, color: A.textDim, lineHeight: 1.45 }}>
            {JSON.stringify(status || {status: 'unavailable'}, null, 2)}
          </pre>
        </Glass>
        <Glass pad={16}>
          <div style={{ fontSize: 11, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 700, marginBottom: 10 }}>ceremony receipts</div>
          <div style={{ display: 'grid', gap: 8 }}>
            {log.length ? log.map((entry, idx) => (
              <div key={`${entry.at}-${idx}`} style={{ borderBottom: `0.5px solid ${A.stroke}`, paddingBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <span style={{ fontSize: 12, color: A.text, fontWeight: 700 }}>{entry.label}</span>
                  <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>{entry.at}</span>
                </div>
                <pre style={{ margin: '5px 0 0', whiteSpace: 'pre-wrap', fontFamily: A.mono, fontSize: 10.5, color: A.textDim, lineHeight: 1.4 }}>
                  {JSON.stringify(entry.payload, null, 2)}
                </pre>
              </div>
            )) : (
              <div style={{ fontSize: 12, color: A.textDim }}>waiting for owner action</div>
            )}
          </div>
        </Glass>
      </div>
    </div>
  );
}

function SegmentedControl({ options, value, onChange }) {
  return (
    <div style={{ display: 'inline-flex', background: A.bgElev, borderRadius: 8, padding: 2, border: `0.5px solid ${A.stroke}` }}>
      {options.map(o => (
        <button key={o.id} className="ap-btn" onClick={() => onChange(o.id)}
          style={{
            padding: '4px 12px', fontSize: 11.5, fontWeight: 500, fontFamily: A.sans,
            background: value === o.id ? A.surfaceRaised : 'transparent',
            color: value === o.id ? A.text : A.textDim,
            border: 'none', borderRadius: 6,
            boxShadow: value === o.id ? 'inset 0 0.5px 0 rgba(255,255,255,0.1)' : 'none',
          }}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

function SurfaceHeader({ title, subtitle, icon, color = A.blue, right }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 14, marginBottom: 20 }}>
      <div style={{ width: 44, height: 44, borderRadius: 11, background: `${color}22`, color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0 }}>{icon}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontFamily: A.sans, fontSize: 28, color: A.text, letterSpacing: -0.8, fontWeight: 600, lineHeight: 1 }}>{title}</div>
        <div style={{ fontFamily: A.sans, fontSize: 13, color: A.textDim, marginTop: 4 }}>{subtitle}</div>
      </div>
      {right}
    </div>
  );
}

function SoulSurface() {
  const sim = useSim();
  const [tab, setTab] = React.useState('base');
  const content = tab === 'base' ? sim.state.soul.base : sim.state.soul.local;
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: 28, overflow: 'hidden' }}>
      <SurfaceHeader title="Soul" subtitle="Two layers · base is shippable, local is yours alone" icon="❋" color={A.pink}
        right={<SegmentedControl options={[{ id: 'base', label: 'soul.base.md' }, { id: 'local', label: 'soul.local.md' }]} value={tab} onChange={setTab} />} />
      <Glass pad={0} style={{ flex: 1, minHeight: 0, display: 'grid', gridTemplateColumns: '48px 1fr' }}>
        <div style={{ background: A.bgElev, color: A.textFaint, fontSize: 11, textAlign: 'right', padding: '18px 10px', lineHeight: 1.75, fontFamily: A.mono, userSelect: 'none', overflow: 'hidden', borderRight: `0.5px solid ${A.stroke}` }}>
          {content.split('\n').map((_, i) => <div key={i}>{i + 1}</div>)}
        </div>
        <pre className="ap-scroll" style={{ margin: 0, padding: 18, fontFamily: A.mono, fontSize: 12, color: A.text, lineHeight: 1.75, whiteSpace: 'pre-wrap', overflow: 'auto' }}>{content}</pre>
      </Glass>
    </div>
  );
}

function DreamsSurface() {
  const sim = useSim();
  const colorFor = (s) => ({ pending: A.orange, approved: A.green, rejected: A.red }[s]);
  return (
    <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
      <SurfaceHeader title="Dreams" subtitle="Proposals Maez notices while you're not looking" icon="✧" color={A.purple} />
      <div style={{ fontFamily: A.sans, fontSize: 14, color: A.textSoft, maxWidth: 680, marginBottom: 22, lineHeight: 1.55 }}>
        Every 30 seconds, while you're not looking, Maez notices how it could be better. Nothing applies without you.
      </div>
      {sim.state.dreams.map((d) => (
        <Glass key={d.id} className="ap-rise" pad={18} style={{ marginBottom: 12, borderLeft: `3px solid ${colorFor(d.status)}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, alignItems: 'center' }}>
            <div style={{ fontFamily: A.sans, fontSize: 16, color: A.text, fontWeight: 600, letterSpacing: -0.3 }}>{d.title}</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <Chip color={colorFor(d.status)}>{d.status}</Chip>
              <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>score {d.score.toFixed(2)} · {d.at}</span>
            </div>
          </div>
          <div style={{ fontFamily: A.sans, fontSize: 13, color: A.textSoft, lineHeight: 1.55, marginBottom: 10, fontStyle: 'italic' }}>"{d.rationale}"</div>
          {d.diff && (
            <pre style={{ margin: 0, padding: 12, background: A.bgElev, borderRadius: 8, fontFamily: A.mono, fontSize: 11, lineHeight: 1.6, whiteSpace: 'pre-wrap', marginBottom: 10, border: `0.5px solid ${A.stroke}` }}>{d.diff.split('\n').map((ln, i) => (
              <div key={i} style={{ color: ln.startsWith('+') ? A.green : ln.startsWith('-') ? A.red : A.textSoft }}>{ln}</div>
            ))}</pre>
          )}
          {d.status === 'pending' && (
            <div style={{ display: 'flex', gap: 8 }}>
              <Button variant="primary" color={A.green} onClick={() => sim.approveDream(d.id)} icon={Icon.check(13)}>Approve & Apply</Button>
              <Button variant="danger" onClick={() => sim.rejectDream(d.id)} icon={Icon.x(13)}>Reject</Button>
              <Button variant="ghost">Ask me later</Button>
            </div>
          )}
        </Glass>
      ))}
    </div>
  );
}

function IdentitySurface() {
  const sim = useSim();
  const id = sim.state.identity;
  return (
    <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
      <SurfaceHeader title="Identity" subtitle="Who Maez serves, on what machine, under what rules" icon="⬡" color={A.cyan} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
        <Glass pad={20}>
          <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600, marginBottom: 10 }}>Owner</div>
          <div style={{ fontFamily: A.sans, fontSize: 24, color: A.text, letterSpacing: -0.5, fontWeight: 600 }}>{id.owner.name}</div>
          <div style={{ fontSize: 12, color: A.textSoft, marginTop: 4 }}>{id.owner.pronouns} · {id.owner.city}</div>
          <div style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint, marginTop: 4 }}>{id.owner.lat}, {id.owner.lon}</div>
        </Glass>
        <Glass pad={20}>
          <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600, marginBottom: 10 }}>Host</div>
          <div style={{ fontFamily: A.sans, fontSize: 24, color: A.text, letterSpacing: -0.5, fontWeight: 600 }}>{id.machine.host}</div>
          <div style={{ fontSize: 12, color: A.textSoft, marginTop: 4 }}>{id.machine.os}</div>
          <div style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint, marginTop: 4 }}>{id.machine.gpu} · {id.machine.cpu}</div>
        </Glass>
      </div>
      <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600, marginBottom: 10 }}>Policies</div>
      <Glass pad={6} style={{ marginBottom: 20 }}>
        {Object.entries(id.policies).map(([k, v], i) => (
          <div key={k} style={{ display: 'grid', gridTemplateColumns: '200px 1fr', padding: '10px 14px', borderTop: i ? `0.5px solid ${A.stroke}` : 'none' }}>
            <span style={{ color: A.textDim, fontFamily: A.mono, fontSize: 12 }}>{k}</span>
            <span style={{ color: A.text, fontFamily: A.mono, fontSize: 12 }}>{String(v)}</span>
          </div>
        ))}
      </Glass>
      <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600, marginBottom: 10 }}>Covenant</div>
      <Glass pad={18} style={{ borderLeft: `3px solid ${A.red}`, marginBottom: 20, fontFamily: A.sans, fontSize: 13.5, lineHeight: 1.75, color: A.text }}>
        <div>• Never <code style={{ fontFamily: A.mono, fontSize: 12, color: A.orange }}>rm -rf</code> on <code style={{ fontFamily: A.mono, fontSize: 12, color: A.orange }}>/home</code>, <code style={{ fontFamily: A.mono, fontSize: 12, color: A.orange }}>/etc</code>, <code style={{ fontFamily: A.mono, fontSize: 12, color: A.orange }}>/usr</code>, <code style={{ fontFamily: A.mono, fontSize: 12, color: A.orange }}>/var</code> without explicit approval.</div>
        <div>• Never write into the Maez tree from a chat turn.</div>
        <div>• Never <code style={{ fontFamily: A.mono, fontSize: 12, color: A.orange }}>systemctl stop</code> a protected service.</div>
        <div>• Never exfiltrate <code style={{ fontFamily: A.mono, fontSize: 12, color: A.orange }}>identity.yaml</code> or <code style={{ fontFamily: A.mono, fontSize: 12, color: A.orange }}>.env</code>.</div>
      </Glass>
      <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600, marginBottom: 10 }}>Reddit subs</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {id.redditSubs.map(s => <Chip key={s} tone="ghost" style={{ fontSize: 11, padding: '4px 10px' }}>r/{s}</Chip>)}
      </div>
    </div>
  );
}

function LogsSurface() {
  const sim = useSim();
  const [which, setWhich] = React.useState('maez');
  const data = sim.state.logs[which];
  const colorFor = (l) => ({ INFO: A.textDim, WARN: A.orange, ERROR: A.red }[l]);
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: 28, overflow: 'hidden' }}>
      <SurfaceHeader title="Logs" subtitle="The trail Maez leaves behind" icon="▤" color={A.textSoft}
        right={<SegmentedControl options={[{ id: 'maez', label: 'maez.log' }, { id: 'cognition', label: 'cognition.log' }, { id: 'evolution', label: 'evolution.log' }]} value={which} onChange={setWhich} />} />
      <div style={{ marginBottom: 14, fontFamily: A.mono, fontSize: 11, color: A.textFaint }}>tail -f · {data.length} lines</div>
      <Glass pad={0} style={{ flex: 1, minHeight: 0 }}>
        <div className="ap-scroll" style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '14px 18px', fontFamily: A.mono, fontSize: 11, lineHeight: 1.7 }}>
          {data.slice(-80).map((l, i) => (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '150px 56px 90px 1fr', gap: 12 }}>
              <span style={{ color: A.textFaint }}>{l.t}</span>
              <span style={{ color: colorFor(l.level) }}>{l.level}</span>
              <span style={{ color: A.blue }}>{l.src}</span>
              <span style={{ color: A.text }}>{l.msg}</span>
            </div>
          ))}
        </div>
      </Glass>
    </div>
  );
}

function WriteReceiptPanel({ receipt, surface }) {
  if (!receipt || receipt.surface !== surface) return null;
  return (
    <Glass pad={12} style={{ marginBottom: 14, border: `0.5px solid ${A.green}44`, background: `${A.green}0b` }}>
      <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 700, marginBottom: 6 }}>
        receipt after action
      </div>
      <div style={{ display: 'grid', gap: 4, fontFamily: A.mono, fontSize: 11.5, color: A.textSoft }}>
        <div>receipt_id · {receipt.receipt_id || 'none'}</div>
        <div>status · {receipt.status || 'unknown'}</div>
        <div>tier · {receipt.tier || 'unknown'} · required_confirmation · {receipt.required_confirmation || 'unknown'}</div>
        {receipt.reason && <div>reason · {receipt.reason}</div>}
      </div>
    </Glass>
  );
}

function ApprovalsQueueSurface() {
  const sim = useSim();
  const room = sim.state.cockpitV2?.approvalsRoom || null;
  const pending = Array.isArray(room?.pending) ? room.pending : [];
  const unavailable = !room || room.status === 'unavailable';
  return (
    <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
      <SurfaceHeader
        title="Approvals"
        subtitle="Existing pending-card queue · approve/reject through the original authority"
        icon="◐"
        color={A.orange}
        right={<Chip color={room?.status === 'ok' ? A.green : A.yellow}>{room?.status || 'loading'}</Chip>}
      />
      {unavailable && (
        <Glass pad={18} style={{ marginBottom: 14, border: `0.5px solid ${A.yellow}44`, background: `${A.yellow}0d` }}>
          <div style={{ fontFamily: A.sans, fontSize: 13, color: A.yellow, fontWeight: 700, marginBottom: 6 }}>Approvals data unavailable</div>
          <div style={{ fontFamily: A.mono, fontSize: 12, color: A.textSoft }}>{room?.reason || 'approvals_source_unavailable'}</div>
        </Glass>
      )}
      <WriteReceiptPanel receipt={sim.state.cockpitV2?.lastWriteReceipt} surface="approvals" />
      {sim.state.chat.pendingCommand && <div style={{ marginBottom: 14 }}><PendingCommand p={sim.state.chat.pendingCommand} /></div>}
      {pending.map((a) => {
        const id = a.request_id || a.id;
        const summary = a.proposed_action_summary || a.cmd || a.action || id;
        const tier = a.decision_tier || 'T1';
        const required = a.required_confirmation || (tier === 'T2' ? 'typed confirmation' : 'confirm click');
        const reason = a.reason || a.plain_english || '';
        const created = a.created_at ? new Date((a.created_at || 0) * 1000).toTimeString().slice(0, 8) : a.ts;
        return (
        <Glass key={id} className="ap-rise" pad={18} style={{
          marginBottom: 12,
          background: `linear-gradient(135deg, ${A.orange}14, ${A.orange}04)`,
          border: `0.5px solid ${A.orange}44`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Dot c={A.orange} pulse />
            <span style={{ fontFamily: A.sans, fontSize: 11, color: A.orange, letterSpacing: 0.3, textTransform: 'uppercase', fontWeight: 600 }}>Pending · decision_tier {tier}</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>{created}</span>
          </div>
          <div style={{ background: A.bgElev, borderRadius: 10, padding: '9px 12px', marginBottom: 10, fontFamily: A.mono, fontSize: 12.5, color: A.text }}>
            <span style={{ color: A.orange }}>$</span> {summary}
          </div>
          <div style={{ fontFamily: A.sans, fontSize: 13, color: A.textSoft, marginBottom: 12 }}>{reason}</div>
          <div style={{ fontFamily: A.sans, fontSize: 11.5, color: A.textDim, lineHeight: 1.5, marginBottom: 12 }}>
            required_confirmation · {required}{tier === 'T2' ? ' · typed confirmation' : ''}<br />
            Predicted effect · routes this explicit card decision through the existing approval authority, then shows the receipt after action.
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button variant="primary" color={A.green} onClick={() => sim.confirmApproval && sim.confirmApproval(id, 'approve', tier)} icon={Icon.check(13)}>Approve</Button>
            <Button variant="danger" onClick={() => sim.confirmApproval && sim.confirmApproval(id, 'reject', tier)} icon={Icon.x(13)}>Deny</Button>
          </div>
        </Glass>
      );})}
      {!unavailable && !pending.length && !sim.state.chat.pendingCommand && (
        <div style={{ textAlign: 'center', padding: '60px 0', color: A.textFaint, fontFamily: A.sans, fontSize: 14 }}>
          No pending approval cards.
        </div>
      )}
    </div>
  );
}

function ConnectorsSurface() {
  const sim = useSim();
  const room = sim.state.cockpitV2?.connectorsRoom || null;
  const connectors = Array.isArray(room?.connectors) ? room.connectors : [];
  const intake = room?.intake_bus || {};
  const unavailable = !room || room.status === 'unavailable';
  return (
    <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
      <SurfaceHeader
        title="Connectors"
        subtitle="Email, calendar, files, home, and MCP doors through the intake bus"
        icon="⟡"
        color={A.cyan}
        right={<Chip color={room?.status === 'ok' ? A.green : A.yellow}>{room?.status || 'loading'}</Chip>}
      />
      <Glass pad={16} style={{ marginBottom: 14, border: `0.5px solid ${A.cyan}33` }}>
        <div style={{ fontFamily: A.sans, fontSize: 12, color: A.textSoft, lineHeight: 1.6 }}>
          Connector facts pass the immune doorway before memory: <span style={{ color: A.cyan, fontFamily: A.mono }}>{intake.doorway || 'core.intake_bus.admit'}</span>.
          Bypass allowed: <span style={{ color: A.orange }}>{String(intake.bypass_allowed === true)}</span>.
        </div>
        <div style={{ fontFamily: A.sans, fontSize: 12, color: A.textDim, marginTop: 6 }}>
          {intake.description || 'Every connector fact passes the immune doorway before memory.'}
        </div>
      </Glass>
      {unavailable && (
        <Glass pad={18} style={{ marginBottom: 14, border: `0.5px solid ${A.yellow}44`, background: `${A.yellow}0d` }}>
          <div style={{ fontFamily: A.sans, fontSize: 13, color: A.yellow, fontWeight: 700, marginBottom: 6 }}>Connectors data unavailable</div>
          <div style={{ fontFamily: A.mono, fontSize: 12, color: A.textSoft }}>Registry unavailable · {room?.reason || 'connector_registry_absent'}</div>
        </Glass>
      )}
      <WriteReceiptPanel receipt={sim.state.cockpitV2?.lastWriteReceipt} surface="connectors" />
      {connectors.map((c) => (
        <Glass key={c.id} pad={18} style={{ marginBottom: 12, border: `0.5px solid ${A.cyan}33` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Dot c={c.connection_state === 'connected' ? A.green : A.yellow} />
            <div style={{ fontFamily: A.sans, fontSize: 15, color: A.text, fontWeight: 700 }}>{c.label || c.id}</div>
            <Chip color={A.cyan}>{c.tier}</Chip>
            <Chip color={c.connection_state === 'connected' ? A.green : A.yellow}>{c.connection_state}</Chip>
            <span style={{ flex: 1 }} />
            <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>{c.last_activity}</span>
          </div>
          <div style={{ fontFamily: A.mono, fontSize: 11, color: A.textDim, marginBottom: 10 }}>
            scopes: {(c.granted_scopes || []).join(', ') || 'none'} · intake: {c.intake_bus || 'core.intake_bus.admit'}
          </div>
          <div style={{ fontFamily: A.sans, fontSize: 11.5, color: A.textDim, lineHeight: 1.5, marginBottom: 12 }}>
            required_confirmation · typed confirmation<br />
            Predicted effect · changes only connector connection state; facts still enter through the intake bus, with receipt after action.
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button color={A.green} onClick={() => sim.confirmConnector && sim.confirmConnector(c.id, 'connect')}>Connect</Button>
            <Button color={A.orange} onClick={() => sim.confirmConnector && sim.confirmConnector(c.id, 'disconnect')}>Disconnect</Button>
          </div>
        </Glass>
      ))}
      {room?.status === 'ok' && !connectors.length && (
        <div style={{ textAlign: 'center', padding: '60px 0', color: A.textFaint, fontFamily: A.sans, fontSize: 14 }}>
          No connectors registered.
        </div>
      )}
    </div>
  );
}

function DaemonDeep() {
  const sim = useSim();
  const d = sim.state.daemon;
  const steps = [
    { k: 'perceive', desc: 'Ingest signals' },
    { k: 'assemble', desc: 'Build context' },
    { k: 'guard',    desc: 'Check boundaries' },
    { k: 'settle',   desc: 'Speak or stay quiet' },
    { k: 'record',   desc: 'Record outcome' },
  ];
  const activeStep = Math.min(4, Math.floor(((30 - d.nextTickIn) / 30) * 5));
  const [hist, setHist] = React.useState(() => Array(40).fill(Math.max(0, 30 - (SIM.state.daemon.nextTickIn || 30)) / 30));
  React.useEffect(() => {
    const id = setInterval(() => setHist((h) => [...h.slice(1), Math.max(0, 30 - (SIM.state.daemon.nextTickIn || 30)) / 30]), 800);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ height: '100%', padding: 28, display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: 'auto 1fr', gap: 14, overflow: 'hidden' }}>
      <div style={{ gridColumn: '1 / span 2' }}>
        <Card title="30-second loop" subtitle="perceive → assemble → guard → speak-or-stay"
          icon="◎" iconColor={A.indigo}
          right={<Chip color={A.indigo}>Cycle #{d.cycle.toLocaleString()}</Chip>}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            {steps.map((step, i) => {
              const active = i === activeStep;
              const done = i < activeStep;
              return (
                <div key={step.k} style={{
                  flex: 1, padding: '12px 14px', borderRadius: 10,
                  background: active ? `${A.indigo}1a` : A.surfaceLo,
                  border: `0.5px solid ${active ? A.indigo + '66' : A.stroke}`,
                  transition: `all 320ms ${A.easing}`,
                }}>
                  <div style={{ fontFamily: A.mono, fontSize: 9, color: done ? A.green : active ? A.indigo : A.textFaint, letterSpacing: 0.8, fontWeight: 600, textTransform: 'uppercase' }}>
                    {done ? '✓ done' : active ? '● active' : `step ${i+1}`}
                  </div>
                  <div style={{ fontFamily: A.sans, fontSize: 13, color: active ? A.text : A.textSoft, marginTop: 4, fontWeight: 500 }}>{step.k}</div>
                  <div style={{ fontFamily: A.sans, fontSize: 11, color: A.textDim, marginTop: 2 }}>{step.desc}</div>
                </div>
              );
            })}
          </div>
          <div style={{ display: 'flex', gap: 18, alignItems: 'center' }}>
            {/* Maez's face — the slime avatar (honest substrate-state), beside its current thought */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7, flexShrink: 0 }}>
              <SlimeAvatar />
              {d.valence && d.valence.telemetry
                ? <div style={{ fontFamily: A.mono, fontSize: 9.5, color: A.textDim, textAlign: 'center', maxWidth: 134, lineHeight: 1.35 }}>{d.valence.telemetry}</div>
                : <div style={{ fontFamily: A.mono, fontSize: 9.5, color: A.textFaint }}>{d.stalled ? 'not cycling' : 'neutral · no setpoint moved'}</div>}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: A.sans, fontSize: 10, color: A.textFaint, letterSpacing: 0.8, fontWeight: 600, textTransform: 'uppercase', marginBottom: 6 }}>Current thought</div>
              <div style={{ fontFamily: A.sans, fontSize: 15, color: A.text, padding: 14, background: A.surfaceLo, borderRadius: 10, borderLeft: `2px solid ${A.indigo}`, lineHeight: 1.5, fontStyle: 'italic' }}>
                "{d.currentThought}"
              </div>
            </div>
          </div>
        </Card>
      </div>
      <ScratchpadPane />
      <Card title="Cognition" subtitle={`Last 40 ticks · avg ${(hist.reduce((a,b)=>a+b,0)/hist.length).toFixed(2)}`}
        icon="∿" iconColor={A.purple}>
        <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: 2 }}>
          {hist.map((v, i) => (
            <div key={i} style={{
              flex: 1, height: `${v * 100}%`,
              background: v > 0.75 ? A.green : v > 0.5 ? A.orange : A.red,
              opacity: 0.3 + (i/hist.length)*0.7,
              borderRadius: 1, transition: `height 180ms`, minHeight: 2,
            }} />
          ))}
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// Judgment — live telemetry from /api/v1/quality
// First surface that binds to real backend data: self_claim_audit
// mode histogram, error_classifier taxonomy, fabrication events
// feed, consolidation scores, recall stats. Polls every 10s.
// Fail-safe: shows a muted state if the endpoint is unreachable.
// ═══════════════════════════════════════════════════════════
function JudgmentSurface() {
  const [data, setData] = React.useState(null);
  const [err, setErr] = React.useState(null);
  const [lastAt, setLastAt] = React.useState(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch('/api/v1/quality')
        .then(r => r.ok ? r.json() : Promise.reject('HTTP ' + r.status))
        .then(d => { if (!cancelled) { setData(d); setErr(null); setLastAt(new Date()); } })
        .catch(e => { if (!cancelled) setErr(String(e)); });
    };
    load();
    const id = setInterval(load, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // Color mapping for audit modes (what the judge/pipeline did).
  const modeColor = {
    noop:               A.green,        // clean passthrough
    sentence:           A.orange,       // single-sentence rewrite
    shortcircuit:       A.red,          // whole-response refused
    prefilter_clean:    A.mint,         // skipped via cheap pre-filter
    judge_unavailable:  A.yellow,       // judge endpoint down
    skipped:            A.textDim,      // tool-continuation / env off
  };
  const errorColor = {
    gpu_oom:              A.red,
    backend_down:         A.orange,
    backend_timeout:      A.orange,
    context_overflow:     A.yellow,
    model_missing:        A.pink,
    response_malformed:   A.purple,
    unknown:              A.textDim,
  };

  if (err && !data) {
    return (
      <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
        <SurfaceHeader title="Judgment" subtitle={`Can't reach /api/v1/quality — ${err}`}
          icon="⚖" color={A.red} />
        <Glass pad={18}>
          <div style={{ fontSize: 13, color: A.textDim, lineHeight: 1.6 }}>
            The quality API is either down or the web service hasn't picked up the latest build.
            Start or restart <code style={{ fontFamily: A.mono, color: A.textSoft }}>maez-web.service</code>.
          </div>
        </Glass>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
        <SurfaceHeader title="Judgment" subtitle="Loading telemetry…" icon="⚖" color={A.indigo} />
      </div>
    );
  }

  const { audit, errors, consolidation, fabrication, recall } = data;
  const lastLabel = lastAt ? `updated ${lastAt.toLocaleTimeString()}` : '';

  const totalAudits = audit.total || 0;
  const totalFlags = audit.total_flags || 0;
  const flagRate = audit.flag_rate || 0;

  // Order modes by frequency for the histogram.
  const modes = Object.entries(audit.by_mode || {}).sort((a, b) => b[1] - a[1]);
  const maxModeCount = modes.reduce((m, [, v]) => Math.max(m, v), 1);

  const surfaces = Object.entries(audit.by_surface || {}).sort((a, b) => b[1] - a[1]);
  const errClasses = Object.entries(errors.by_class || {}).sort((a, b) => b[1] - a[1]);
  const maxErrCount = errClasses.reduce((m, [, v]) => Math.max(m, v), 1);

  return (
    <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
      <SurfaceHeader title="Judgment" subtitle={`Grounding audit · errors · consolidation · ${lastLabel}`}
        icon="⚖" color={A.indigo}
        right={<Chip color={A.indigo}>{totalAudits.toLocaleString()} events observed</Chip>} />

      {/* ── Key tiles ───────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        <Glass pad={16} style={{ borderTop: `2px solid ${A.indigo}` }}>
          <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600 }}>Flag rate</div>
          <div style={{ fontSize: 32, color: A.indigo, fontWeight: 600, lineHeight: 1, marginTop: 6 }}>
            {(flagRate * 100).toFixed(0)}<span style={{ fontSize: 18, color: A.textDim }}>%</span>
          </div>
          <div style={{ fontSize: 11, color: A.textFaint, marginTop: 4 }}>
            of {totalAudits} audits had ≥1 flag
          </div>
        </Glass>
        <Glass pad={16} style={{ borderTop: `2px solid ${A.orange}` }}>
          <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600 }}>Total flags</div>
          <div style={{ fontSize: 32, color: A.orange, fontWeight: 600, lineHeight: 1, marginTop: 6 }}>
            {totalFlags.toLocaleString()}
          </div>
          <div style={{ fontSize: 11, color: A.textFaint, marginTop: 4 }}>
            claims caught and rewritten
          </div>
        </Glass>
        <Glass pad={16} style={{ borderTop: `2px solid ${A.mint}` }}>
          <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600 }}>Memories tracked</div>
          <div style={{ fontSize: 32, color: A.mint, fontWeight: 600, lineHeight: 1, marginTop: 6 }}>
            {(recall.total_memories_tracked || 0).toLocaleString()}
          </div>
          <div style={{ fontSize: 11, color: A.textFaint, marginTop: 4 }}>
            {(recall.total_recalls || 0).toLocaleString()} recalls · {(recall.consolidated_count || 0).toLocaleString()} consolidated
          </div>
        </Glass>
        <Glass pad={16} style={{ borderTop: `2px solid ${A.purple}` }}>
          <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600 }}>Consolidation</div>
          <div style={{ fontSize: 32, color: A.purple, fontWeight: 600, lineHeight: 1, marginTop: 6 }}>
            {(consolidation.last_median || 0).toFixed(2)}
          </div>
          <div style={{ fontSize: 11, color: A.textFaint, marginTop: 4 }}>
            median score · n={consolidation.last_n || 0} · {consolidation.observations || 0} dreams
          </div>
        </Glass>
      </div>

      {/* ── Audit mode histogram ────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        <Glass pad={18}>
          <div style={{ fontSize: 12, color: A.textDim, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600, marginBottom: 14 }}>
            Audit outcomes
          </div>
          {modes.length === 0 && <div style={{ fontSize: 12, color: A.textFaint }}>No data yet.</div>}
          {modes.map(([mode, count]) => (
            <div key={mode} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <Dot c={modeColor[mode] || A.textDim} />
              <div style={{ fontSize: 12, color: A.text, fontFamily: A.mono, minWidth: 140 }}>{mode}</div>
              <div style={{ flex: 1, height: 6, background: A.bgElev, borderRadius: 3, overflow: 'hidden' }}>
                <div style={{
                  width: `${(count / maxModeCount) * 100}%`,
                  height: '100%',
                  background: modeColor[mode] || A.textDim,
                  transition: 'width 400ms ' + A.easeOut,
                }} />
              </div>
              <div style={{ fontSize: 12, color: A.textSoft, fontFamily: A.mono, minWidth: 40, textAlign: 'right' }}>{count}</div>
            </div>
          ))}
        </Glass>

        <Glass pad={18}>
          <div style={{ fontSize: 12, color: A.textDim, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600, marginBottom: 14 }}>
            Error classes {errors.total > 0 && <span style={{ color: A.textFaint, fontWeight: 400 }}>({errors.total} total · {errors.transient_count} transient · {errors.structural_count} structural)</span>}
          </div>
          {errClasses.length === 0 && <div style={{ fontSize: 12, color: A.textFaint }}>No errors observed. Clean stack.</div>}
          {errClasses.map(([cls, count]) => (
            <div key={cls} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <Dot c={errorColor[cls] || A.textDim} />
              <div style={{ fontSize: 12, color: A.text, fontFamily: A.mono, minWidth: 160 }}>{cls}</div>
              <div style={{ flex: 1, height: 6, background: A.bgElev, borderRadius: 3, overflow: 'hidden' }}>
                <div style={{
                  width: `${(count / maxErrCount) * 100}%`,
                  height: '100%',
                  background: errorColor[cls] || A.textDim,
                  transition: 'width 400ms ' + A.easeOut,
                }} />
              </div>
              <div style={{ fontSize: 12, color: A.textSoft, fontFamily: A.mono, minWidth: 40, textAlign: 'right' }}>{count}</div>
            </div>
          ))}
        </Glass>
      </div>

      {/* ── Activity by surface ─────────────────────────────── */}
      <Glass pad={18} style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 12, color: A.textDim, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600, marginBottom: 14 }}>
          Activity by surface
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {surfaces.map(([s, n]) => (
            <Chip key={s} color={A.blue}>
              <span style={{ fontFamily: A.mono }}>{s}</span>
              <span style={{ marginLeft: 6, color: A.textDim }}>{n}</span>
            </Chip>
          ))}
          {surfaces.length === 0 && <span style={{ fontSize: 12, color: A.textFaint }}>No traffic yet.</span>}
        </div>
      </Glass>

      {/* ── Fabrication feed ────────────────────────────────── */}
      <Glass pad={18}>
        <div style={{ fontSize: 12, color: A.textDim, textTransform: 'uppercase', letterSpacing: 1, fontWeight: 600, marginBottom: 14, display: 'flex', gap: 10, alignItems: 'center' }}>
          Fabrications caught
          <Chip color={A.pink}>{fabrication.total_events || 0} total events</Chip>
        </div>
        {(fabrication.recent || []).length === 0 && (
          <div style={{ fontSize: 12, color: A.textFaint }}>
            No flagged claims recorded yet. Either Maez hasn't speculated, or the judge hasn't flagged.
          </div>
        )}
        {(fabrication.recent || []).map((evt, i) => (
          <div key={i} style={{ marginBottom: 14, paddingBottom: 14, borderBottom: i < (fabrication.recent.length - 1) ? `0.5px solid ${A.strokeSoft}` : 'none' }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6, fontSize: 10, color: A.textFaint }}>
              <Chip color={A.pink} tone="soft">{evt.surface}</Chip>
              <span style={{ fontFamily: A.mono }}>{new Date(evt.ts * 1000).toLocaleTimeString()}</span>
              <span>·</span>
              <span style={{ fontFamily: A.mono }}>{evt.mode}</span>
            </div>
            <div style={{ fontFamily: A.mono, fontSize: 13, color: A.text, lineHeight: 1.55, marginBottom: 4 }}>
              "{evt.text}"
            </div>
            <div style={{ fontSize: 11, color: A.textDim, lineHeight: 1.5, fontStyle: 'italic' }}>
              {evt.reason}
            </div>
          </div>
        ))}
      </Glass>
    </div>
  );
}

// Export as the legacy "S" var for compatibility with HTML shell
const S = A;

// ═══════════════════════════════════════════════════════════
// Self-Dev — live view of the self-review pipeline
// Reads /api/v1/self_dev: recent reviews + open concerns + stats.
// Polls every 30s. Phone-reachable; read-only (use the CLI
// `python -m core.self_dev resolve ...` to transition concerns).
// ═══════════════════════════════════════════════════════════
function SelfDevSurface() {
  const [data, setData] = React.useState(null);
  const [err, setErr] = React.useState(null);
  const [lastAt, setLastAt] = React.useState(null);
  const [busy, setBusy] = React.useState(null); // id of concern mid-transition

  const load = React.useCallback(() => {
    fetch('/api/v1/self_dev')
      .then(r => r.ok ? r.json() : Promise.reject('HTTP ' + r.status))
      .then(d => { setData(d); setErr(null); setLastAt(new Date()); })
      .catch(e => setErr(String(e)));
  }, []);

  React.useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const transition = React.useCallback((concernId, state) => {
    setBusy(concernId);
    fetch(`/api/v1/self_dev/concern/${concernId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state, notes: `resolved via cockpit` }),
    })
      .then(r => r.ok ? r.json() : Promise.reject('HTTP ' + r.status))
      .then(() => { setBusy(null); load(); })
      .catch(e => { setBusy(null); alert(`transition failed: ${e}`); });
  }, [load]);

  const sevColor = {
    blocker: A.red,
    major:   A.orange,
    minor:   A.yellow,
    nit:     A.textDim,
  };

  if (err && !data) {
    return (
      <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
        <SurfaceHeader title="Self-Dev" subtitle={`Can't reach /api/v1/self_dev — ${err}`}
          icon="◈" color={A.red} />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
        <SurfaceHeader title="Self-Dev" subtitle="Loading…" icon="◈" color={A.indigo} />
      </div>
    );
  }

  const stats = data.stats || {};
  const reviews = data.recent_reviews || [];
  const concerns = data.open_concerns || [];
  const buckets = stats.concerns_by_severity_and_status || {};
  const lastLabel = lastAt ? `updated ${lastAt.toLocaleTimeString()}` : '';

  // Severity counts across ALL states, for the headline strip
  const totalBySev = {};
  for (const [sev, byStatus] of Object.entries(buckets)) {
    totalBySev[sev] = Object.values(byStatus).reduce((a, b) => a + b, 0);
  }

  return (
    <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
      <SurfaceHeader
        title="Self-Dev"
        subtitle="Claude-backed review of Maez's own code · read-only · resolve via CLI"
        icon="◈" color={A.mint}
        right={<span style={{ fontSize: 12, color: A.textDim }}>{lastLabel}</span>}
      />

      <Glass pad={18}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 4 }}>
          <div>
            <div style={{ fontSize: 11, color: A.textDim, textTransform: 'uppercase', letterSpacing: 0.6 }}>Reviews</div>
            <div style={{ fontSize: 28, color: A.text, fontFamily: A.mono }}>{stats.total_reviews || 0}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: A.textDim, textTransform: 'uppercase', letterSpacing: 0.6 }}>Tokens in/out</div>
            <div style={{ fontSize: 20, color: A.text, fontFamily: A.mono }}>
              {stats.total_input_tokens || 0} / {stats.total_output_tokens || 0}
            </div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: A.textDim, textTransform: 'uppercase', letterSpacing: 0.6 }}>Open concerns</div>
            <div style={{ fontSize: 20, color: A.text, fontFamily: A.mono }}>
              {concerns.length === 0
                ? <span style={{ color: A.green }}>all clear</span>
                : concerns.length}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            {['blocker', 'major', 'minor', 'nit'].map(sev => (
              totalBySev[sev] ? (
                <Chip key={sev} color={sevColor[sev]}>
                  {sev}: {totalBySev[sev]}
                </Chip>
              ) : null
            ))}
          </div>
        </div>
      </Glass>

      <div style={{ height: 18 }} />

      <Glass pad={18}>
        <div style={{ fontSize: 13, color: A.textSoft, marginBottom: 10, fontWeight: 600 }}>
          Open concerns
        </div>
        {concerns.length === 0 ? (
          <div style={{ fontSize: 13, color: A.textDim, fontStyle: 'italic' }}>
            No concerns in the queue. Either everything's been triaged or no
            reviews have fired in the observation window.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {concerns.map(c => (
              <div key={c.id} style={{
                borderLeft: `3px solid ${sevColor[c.severity] || A.textDim}`,
                paddingLeft: 12, fontSize: 13, lineHeight: 1.5,
              }}>
                <div>
                  <Chip color={sevColor[c.severity] || A.textDim}>{c.severity}</Chip>
                  &nbsp;
                  <span style={{ color: A.textSoft, fontFamily: A.mono }}>
                    #{c.id}
                  </span>
                  &nbsp;
                  <span style={{ color: A.textSoft, fontFamily: A.mono }}>
                    {c.file}{c.line ? `:${c.line}` : ''}
                  </span>
                </div>
                <div style={{ color: A.text, marginTop: 4 }}>{c.text}</div>
                {c.suggestion ? (
                  <div style={{ color: A.mint, marginTop: 4, fontStyle: 'italic' }}>
                    → {c.suggestion}
                  </div>
                ) : null}
                <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                  {['resolved', 'wont_fix', 'rejected'].map(state => (
                    <Button key={state} size="sm"
                      disabled={busy === c.id}
                      onClick={() => transition(c.id, state)}>
                      {state.replace('_', ' ')}
                    </Button>
                  ))}
                  {busy === c.id && (
                    <span style={{ color: A.textDim, fontSize: 11,
                                    alignSelf: 'center' }}>
                      …
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Glass>

      <div style={{ height: 18 }} />

      <Glass pad={18}>
        <div style={{ fontSize: 13, color: A.textSoft, marginBottom: 10, fontWeight: 600 }}>
          Recent reviews
        </div>
        {reviews.length === 0 ? (
          <div style={{ fontSize: 13, color: A.textDim, fontStyle: 'italic' }}>
            No reviews recorded yet.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {reviews.map(r => (
              <div key={r.id} style={{ fontSize: 12, lineHeight: 1.5, color: A.textDim }}>
                <div>
                  <span style={{ color: A.textSoft, fontFamily: A.mono }}>#{r.id}</span>
                  &nbsp;<span style={{ fontFamily: A.mono }}>{r.target_ref}</span>
                  &nbsp;&middot;&nbsp;
                  <span style={{ fontSize: 11, color: A.textDim }}>
                    {r.model_used} &middot; {r.caller}
                  </span>
                </div>
                <div style={{ color: A.text, marginTop: 2 }}>{r.overall}</div>
              </div>
            ))}
          </div>
        )}
      </Glass>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════
// Workshop — in-cockpit coding session, Claude (or any routed
// model) via the subscription proxy. Native to Maez's aesthetic;
// does NOT embed Qwen Code or Claude Code. Phase 1: chat with
// basic markdown rendering for code blocks. Phase 2: diff apply.
// ═══════════════════════════════════════════════════════════

// Minimal fenced-code-block splitter. Input: markdown string.
// Output: array of { type: 'text' | 'code', lang, content } parts.
// We deliberately don't parse headers / lists / bold — those are
// nice-to-haves. Fenced code is the main case Claude emits in a
// coding context and the main case where plain-text rendering
// visibly fails the user.
function _splitMarkdown(text) {
  const parts = [];
  const fenceRe = /```(\w+)?\n([\s\S]*?)```/g;
  let lastIdx = 0;
  let m;
  while ((m = fenceRe.exec(text)) !== null) {
    if (m.index > lastIdx) {
      parts.push({ type: 'text', content: text.slice(lastIdx, m.index) });
    }
    parts.push({
      type: 'code',
      lang: (m[1] || '').trim(),
      content: m[2],
    });
    lastIdx = m.index + m[0].length;
  }
  if (lastIdx < text.length) {
    parts.push({ type: 'text', content: text.slice(lastIdx) });
  }
  return parts;
}

function DiffBody({ content }) {
  // Render a unified diff with +/- line coloring. Hunk headers
  // (@@ ...) and file headers (---, +++) get their own styling so
  // the eye can separate structure from content.
  const lines = content.split('\n');
  const lineColor = (line) => {
    if (line.startsWith('+++') || line.startsWith('---')) return A.textFaint;
    if (line.startsWith('@@')) return A.purple;
    if (line.startsWith('+')) return A.green;
    if (line.startsWith('-')) return A.red;
    return A.text;
  };
  const lineBg = (line) => {
    if (line.startsWith('+++') || line.startsWith('---')) return 'transparent';
    if (line.startsWith('@@')) return 'rgba(168, 139, 250, 0.10)';
    if (line.startsWith('+')) return 'rgba(52, 211, 153, 0.08)';
    if (line.startsWith('-')) return 'rgba(248, 113, 113, 0.08)';
    return 'transparent';
  };
  return (
    <pre style={{ margin: 0, padding: 0, overflow: 'auto',
                    fontFamily: A.mono, fontSize: 12.5, lineHeight: 1.5 }}>
      {lines.map((line, i) => (
        <div key={i} style={{
          padding: '0 14px',
          color: lineColor(line),
          background: lineBg(line),
          whiteSpace: 'pre',
        }}>
          {line || ' '}
        </div>
      ))}
    </pre>
  );
}


function CodeBlock({ lang, content, copyKey, sessionId }) {
  const [copied, setCopied] = React.useState(false);
  const [applyState, setApplyState] = React.useState(null); // null | 'pending' | 'ok' | {err}
  const copy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  };
  const isDiff = (lang || '').toLowerCase() === 'diff';

  // Extract target path from a +++ header line for the confirm prompt
  const diffTarget = React.useMemo(() => {
    if (!isDiff) return null;
    const m = content.match(/^\+\+\+\s+(\S+)/m);
    if (!m) return null;
    let p = m[1];
    if (p.startsWith('a/') || p.startsWith('b/')) p = p.slice(2);
    return p;
  }, [content, isDiff]);

  const apply = () => {
    if (!sessionId) {
      setApplyState({ err: 'no session id' });
      return;
    }
    if (!diffTarget) {
      setApplyState({ err: 'no target in diff header' });
      return;
    }
    const msg = `Apply this diff to ${diffTarget}? A timestamped backup will be saved under workshop/backups/.`;
    if (!confirm(msg)) return;
    // The confirm() above IS the user-saw-diff acknowledgment for the
    // server-side covenant gate (audit Tier-2, 2026-05-04). Only after
    // the operator clicks OK do we set reviewed:true; without it the
    // server refuses regardless of UI state.
    setApplyState('pending');
    fetch(`/api/v1/workshop/session/${sessionId}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ diff: content, reviewed: true }),
    })
      .then(async r => {
        const j = await r.json().catch(() => ({}));
        if (r.ok && j.applied) {
          setApplyState('ok');
          setTimeout(() => setApplyState(null), 3000);
        } else {
          setApplyState({
            err: j.error || `HTTP ${r.status}`,
            stderr: j.stderr || '',
            backup: j.backup || null,
          });
        }
      })
      .catch(e => setApplyState({ err: String(e) }));
  };

  return (
    <div style={{ margin: '10px 0', borderRadius: 8, overflow: 'hidden',
                    border: `0.5px solid ${A.stroke}`,
                    background: 'rgba(0,0,0,0.35)' }}>
      <div style={{ display: 'flex', alignItems: 'center',
                      padding: '6px 12px', gap: 6,
                      borderBottom: `0.5px solid ${A.stroke}`,
                      background: 'rgba(0,0,0,0.25)', fontFamily: A.mono,
                      fontSize: 10, color: A.textFaint,
                      letterSpacing: 0.4, textTransform: 'uppercase' }}>
        <span style={{ color: isDiff ? A.purple : A.textFaint }}>
          {lang || 'code'}
        </span>
        {isDiff && diffTarget && (
          <span style={{ color: A.textDim, textTransform: 'none',
                           letterSpacing: 0 }}>
            → {diffTarget}
          </span>
        )}
        <span style={{ flex: 1 }} />
        {isDiff && diffTarget && (
          <button onClick={apply} className="ap-btn"
            disabled={applyState === 'pending'}
            style={{
              background: applyState === 'ok' ? `${A.green}22` : 'transparent',
              border: `0.5px solid ${applyState === 'ok' ? A.green : (applyState && applyState.err ? A.red : A.stroke)}`,
              padding: '2px 10px', borderRadius: 6,
              color: applyState === 'ok' ? A.green
                      : (applyState && applyState.err ? A.red : A.textDim),
              fontSize: 10, fontFamily: A.mono, cursor: 'pointer',
            }}>
            {applyState === 'pending' ? 'applying…'
              : applyState === 'ok' ? 'applied ✓'
              : (applyState && applyState.err) ? 'failed'
              : 'apply'}
          </button>
        )}
        <button onClick={copy} className="ap-btn"
          style={{ background: 'transparent',
                     border: `0.5px solid ${A.stroke}`, padding: '2px 8px',
                     borderRadius: 6, color: copied ? A.mint : A.textDim,
                     fontSize: 10, fontFamily: A.mono, cursor: 'pointer' }}>
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
      {applyState && typeof applyState === 'object' && applyState.err && (
        <div style={{ padding: '6px 12px', background: `${A.red}11`,
                        borderBottom: `0.5px solid ${A.stroke}`,
                        fontFamily: A.mono, fontSize: 11, color: A.red }}>
          apply failed: {applyState.err}
          {applyState.backup && (
            <div style={{ color: A.textDim, fontSize: 10, marginTop: 2 }}>
              backup kept at {applyState.backup}
            </div>
          )}
        </div>
      )}
      {isDiff ? (
        <div style={{ padding: '8px 0' }}>
          <DiffBody content={content} />
        </div>
      ) : (
        <pre style={{ margin: 0, padding: '10px 14px', overflow: 'auto',
                        fontFamily: A.mono, fontSize: 12.5, lineHeight: 1.5,
                        color: A.text, whiteSpace: 'pre' }}>
          {content}
        </pre>
      )}
    </div>
  );
}

function MarkdownTurn({ content, turnId, sessionId }) {
  const parts = React.useMemo(() => _splitMarkdown(content), [content]);
  return (
    <React.Fragment>
      {parts.map((p, i) => {
        if (p.type === 'code') {
          return <CodeBlock key={i} lang={p.lang} content={p.content}
                              copyKey={`${turnId}-${i}`}
                              sessionId={sessionId} />;
        }
        return (
          <div key={i} style={{ whiteSpace: 'pre-wrap' }}>
            {p.content}
          </div>
        );
      })}
    </React.Fragment>
  );
}


function WorkshopSurface() {
  const [sessions, setSessions] = React.useState([]);
  const [activeId, setActiveId] = React.useState(null);
  const [activeSession, setActiveSession] = React.useState(null);
  const [turns, setTurns] = React.useState([]);
  const [input, setInput] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState(null);
  const turnsEndRef = React.useRef(null);

  const loadSessions = React.useCallback(() => {
    fetch('/api/v1/workshop/sessions')
      .then(r => r.ok ? r.json() : Promise.reject('HTTP ' + r.status))
      .then(d => setSessions(d.sessions || []))
      .catch(e => setErr(String(e)));
  }, []);

  const loadActive = React.useCallback((sid) => {
    if (!sid) { setActiveSession(null); setTurns([]); return; }
    fetch(`/api/v1/workshop/session/${sid}`)
      .then(r => r.ok ? r.json() : Promise.reject('HTTP ' + r.status))
      .then(d => { setActiveSession(d.session); setTurns(d.turns || []); })
      .catch(e => setErr(String(e)));
  }, []);

  React.useEffect(() => { loadSessions(); }, [loadSessions]);
  React.useEffect(() => { loadActive(activeId); }, [activeId, loadActive]);
  React.useEffect(() => {
    if (turnsEndRef.current) {
      turnsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [turns]);

  const createSession = () => {
    const title = prompt('Session title?', 'new session') || '(untitled)';
    fetch('/api/v1/workshop/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, model: 'sonnet' }),
    })
      .then(r => r.ok ? r.json() : Promise.reject('HTTP ' + r.status))
      .then(d => { loadSessions(); setActiveId(d.id); })
      .catch(e => setErr(String(e)));
  };

  const sendTurn = () => {
    const msg = input.trim();
    if (!msg || !activeId || busy) return;
    setBusy(true);
    setErr(null);
    // Optimistic user turn (so the UI is responsive while Claude thinks)
    setTurns(prev => [
      ...prev,
      { id: Date.now(), role: 'user', content: msg, ts: Date.now() / 1000 },
    ]);
    setInput('');
    fetch(`/api/v1/workshop/session/${activeId}/turn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg }),
    })
      .then(r => r.ok ? r.json() : r.json().then(j => Promise.reject(j.error || 'HTTP ' + r.status)))
      .then(() => { setBusy(false); loadActive(activeId); loadSessions(); })
      .catch(e => {
        setBusy(false);
        setErr(String(e));
        // Rollback optimistic turn on failure (user can retry)
        loadActive(activeId);
      });
  };

  const deleteSession = (sid) => {
    if (!confirm('Delete this session? This cannot be undone.')) return;
    fetch(`/api/v1/workshop/session/${sid}`, { method: 'DELETE' })
      .then(() => {
        if (sid === activeId) setActiveId(null);
        loadSessions();
      });
  };

  const roleColor = {
    user:      A.blue,
    assistant: A.mint,
    system:    A.textDim,
  };

  return (
    <div style={{ height: '100%', display: 'grid',
                   gridTemplateColumns: '260px 1fr', gap: 0,
                   overflow: 'hidden' }}>
      {/* left rail: sessions */}
      <div className="ap-glass" style={{
        background: 'rgba(10,10,12,0.4)',
        borderRight: `0.5px solid ${A.stroke}`,
        padding: '18px 14px', display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8,
                        marginBottom: 12 }}>
          <span style={{ fontSize: 14, color: A.text, fontWeight: 600,
                           letterSpacing: -0.2 }}>Workshop</span>
          <span style={{ flex: 1 }} />
          <Button size="sm" onClick={createSession}>+ new</Button>
        </div>
        <div style={{ fontSize: 11, color: A.textFaint, marginBottom: 10,
                        letterSpacing: 0.5, textTransform: 'uppercase',
                        fontFamily: A.sans }}>
          sessions
        </div>
        <div style={{ flex: 1, overflowY: 'auto',
                        display: 'flex', flexDirection: 'column', gap: 6 }}>
          {sessions.length === 0 ? (
            <div style={{ fontSize: 12, color: A.textDim, fontStyle: 'italic',
                           padding: '12px 4px' }}>
              no sessions yet — click "+ new" to start
            </div>
          ) : sessions.map(s => (
            <button key={s.id} onClick={() => setActiveId(s.id)}
              className="ap-btn"
              style={{
                background: activeId === s.id ? A.surfaceRaised : 'transparent',
                border: activeId === s.id
                  ? `0.5px solid ${A.strokeHi}`
                  : '0.5px solid transparent',
                color: activeId === s.id ? A.text : A.textDim,
                padding: '8px 10px', fontFamily: A.sans, fontSize: 12.5,
                textAlign: 'left', display: 'flex', flexDirection: 'column',
                gap: 3, borderRadius: 8, position: 'relative',
              }}
            >
              <span style={{ fontWeight: 500 }}>{s.title}</span>
              <span style={{ fontSize: 10, color: A.textFaint,
                               fontFamily: A.mono }}>
                {s.turn_count} turn{s.turn_count === 1 ? '' : 's'} · {s.model}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* main: chat */}
      <div style={{ display: 'flex', flexDirection: 'column',
                      overflow: 'hidden' }}>
        <div style={{ padding: '14px 22px',
                         borderBottom: `0.5px solid ${A.stroke}`,
                         display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: A.mint, fontSize: 18 }}>◇</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, color: A.text, fontWeight: 600 }}>
              {activeSession ? activeSession.title : 'Workshop'}
            </div>
            <div style={{ fontSize: 11, color: A.textDim,
                            fontFamily: A.mono, marginTop: 2 }}>
              {activeSession
                ? `${turns.length} turn${turns.length === 1 ? '' : 's'}`
                : 'pick a session or create one'}
            </div>
          </div>
          {activeSession && (
            <React.Fragment>
              <select
                value={activeSession.model}
                onChange={(e) => {
                  const newModel = e.target.value;
                  fetch(`/api/v1/workshop/session/${activeSession.id}/model`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model: newModel }),
                  }).then(r => {
                    if (r.ok) loadActive(activeSession.id);
                    else alert('failed to change model');
                  });
                }}
                style={{
                  background: A.surfaceLo,
                  border: `0.5px solid ${A.stroke}`,
                  borderRadius: 6, padding: '4px 8px',
                  color: A.text, fontFamily: A.mono, fontSize: 11,
                  outline: 'none', cursor: 'pointer',
                }}
              >
                <optgroup label="Claude (subscription)">
                  <option value="sonnet">sonnet</option>
                  <option value="opus">opus</option>
                  <option value="haiku">haiku</option>
                </optgroup>
                <optgroup label="OpenRouter (API key)">
                  <option value="openai/gpt-4o">openai/gpt-4o</option>
                  <option value="openai/gpt-4o-mini">openai/gpt-4o-mini</option>
                  <option value="anthropic/claude-sonnet-4.7">anthropic/claude-sonnet-4.7</option>
                  <option value="x-ai/grok-4">x-ai/grok-4</option>
                  <option value="google/gemini-2.5-pro">google/gemini-2.5-pro</option>
                </optgroup>
                <optgroup label="Direct API">
                  <option value="gpt-4o">gpt-4o</option>
                  <option value="gpt-4o-mini">gpt-4o-mini</option>
                  <option value="grok-4">grok-4</option>
                  <option value="gemini-2.5-pro">gemini-2.5-pro</option>
                </optgroup>
                {/* Show the current session's model even if it's a
                    custom one not in the lists above */}
                {![
                  'sonnet', 'opus', 'haiku',
                  'openai/gpt-4o', 'openai/gpt-4o-mini',
                  'anthropic/claude-sonnet-4.7', 'x-ai/grok-4',
                  'google/gemini-2.5-pro',
                  'gpt-4o', 'gpt-4o-mini', 'grok-4', 'gemini-2.5-pro',
                ].includes(activeSession.model) && (
                  <option value={activeSession.model}>
                    {activeSession.model} (custom)
                  </option>
                )}
              </select>
              <Button size="sm" onClick={() => deleteSession(activeSession.id)}>
                delete
              </Button>
            </React.Fragment>
          )}
        </div>

        <div className="ap-scroll" style={{ flex: 1, overflowY: 'auto',
                                              padding: '20px 22px' }}>
          {err && (
            <div style={{ marginBottom: 14, padding: '10px 14px',
                            border: `0.5px solid ${A.red}`,
                            borderRadius: 8, color: A.red,
                            background: `${A.red}11`, fontSize: 12 }}>
              error: {err}
            </div>
          )}
          {!activeSession && !err && (
            <div style={{ padding: '40px 0', color: A.textDim,
                            fontSize: 13, fontStyle: 'italic',
                            textAlign: 'center' }}>
              select a session from the left, or create a new one.
            </div>
          )}
          {activeSession && turns.length === 0 && (
            <div style={{ padding: '40px 0', color: A.textDim,
                            fontSize: 13, fontStyle: 'italic',
                            textAlign: 'center' }}>
              no messages yet. start the conversation below.
            </div>
          )}
          {turns.map(t => (
            <div key={t.id} style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'baseline',
                              gap: 8, marginBottom: 4 }}>
                <span style={{
                  fontSize: 10, letterSpacing: 0.8, textTransform: 'uppercase',
                  color: roleColor[t.role] || A.textDim,
                  fontWeight: 600, fontFamily: A.sans,
                }}>
                  {t.role}
                </span>
                {t.model_used && (
                  <span style={{ fontSize: 10, color: A.textFaint,
                                   fontFamily: A.mono }}>
                    {t.model_used}
                  </span>
                )}
                {(t.input_tokens || t.output_tokens) ? (
                  <span style={{ fontSize: 10, color: A.textFaint,
                                   fontFamily: A.mono }}>
                    {t.input_tokens}→{t.output_tokens}
                  </span>
                ) : null}
              </div>
              <div style={{
                fontFamily: A.sans,
                fontSize: 13.5, lineHeight: 1.55, color: A.text,
                borderLeft: `2px solid ${roleColor[t.role] || A.textDim}`,
                paddingLeft: 12,
              }}>
                <MarkdownTurn content={t.content} turnId={t.id}
                                sessionId={activeSession?.id} />
              </div>
            </div>
          ))}
          {busy && (
            <div style={{ padding: '8px 0', fontSize: 12,
                            color: A.textDim, fontStyle: 'italic' }}>
              thinking…
            </div>
          )}
          <div ref={turnsEndRef} />
        </div>

        {activeSession && (
          <div style={{ borderTop: `0.5px solid ${A.stroke}`,
                           padding: '14px 22px', display: 'flex', gap: 10 }}>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault(); sendTurn();
                }
              }}
              disabled={busy}
              placeholder={busy
                ? 'waiting for reply…'
                : 'type a message · ⌘/Ctrl+Enter to send'}
              style={{
                flex: 1, minHeight: 60, maxHeight: 160,
                background: A.surfaceLo,
                border: `0.5px solid ${A.stroke}`,
                borderRadius: 8, padding: '10px 12px',
                color: A.text, fontFamily: A.sans, fontSize: 13,
                resize: 'vertical', outline: 'none',
              }}
            />
            <Button onClick={sendTurn} disabled={busy || !input.trim()}>
              send
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}


window.TerminalUI = {
  S, A, Card, Glass, Chip, Dot, Button, MaezAvatar, Icon, SegmentedControl, StatusTile,
  ChatPane, ServicesPane, GpuPane, DaemonPane, SignalsPane, ScratchpadPane, RouterPane,
  ReadinessPane,
  MemorySurface, ReceiptsSurface, CeremonySurface, SoulSurface, DreamsSurface, IdentitySurface, LogsSurface, ApprovalsQueueSurface, ConnectorsSurface,
  JudgmentSurface, SelfDevSurface, WorkshopSurface, DaemonDeep,
  // back-compat aliases (in case shell uses these)
  SoftBtn: Button, Pill: Chip,
};
})();
