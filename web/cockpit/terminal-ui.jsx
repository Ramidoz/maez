// Direction A — Apple Inc. redesign
// Aesthetic: glass / soft gradients / muted palette.
// Glass morphism, SF-style type (Inter fallback), precise motion, tight density.
// Rich interactive chat: model picker, thinking toggle, tool menu, attachments,
// inline approval, tool-call cards, streaming with thinking trace.
(function() {

// inject fonts + css
if (typeof document !== 'undefined' && !document.getElementById('apple-fonts')) {
  const l = document.createElement('link');
  l.id = 'apple-fonts';
  l.rel = 'stylesheet';
  l.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap';
  document.head.appendChild(l);
}

const A = {
  // Apple-style palette (dark)
  bg:          '#000000',
  bgElev:      '#0a0a0c',
  surface:     'rgba(28, 28, 30, 0.72)',   // glass primary
  surfaceHi:   'rgba(44, 44, 46, 0.78)',
  surfaceLo:   'rgba(18, 18, 20, 0.68)',
  surfaceRaised:'rgba(58, 58, 60, 0.6)',

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
  blue:        '#0a84ff',
  blueSoft:    '#409cff',
  indigo:      '#5e5ce6',
  purple:      '#bf5af2',
  pink:        '#ff375f',
  red:         '#ff453a',
  orange:      '#ff9f0a',
  yellow:      '#ffd60a',
  green:       '#30d158',
  mint:        '#63e6e2',
  teal:        '#40c8e0',
  cyan:        '#64d2ff',

  // accent gradient (used by `.ap-ai-text` class for title-bar accents)
  aiGrad:      'linear-gradient(135deg, #ff375f 0%, #bf5af2 35%, #5e5ce6 70%, #0a84ff 100%)',

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

// ═══ models ═══════════════════════════════════════════════════════

const MODELS = [
  { id: 'local-qwen',    name: 'Maez · Qwen 3.6',   sub: 'on-device · 35B · instant', family: 'local', badge: 'Local', color: A.green, ctx: '128K', speed: 'fast' },
  { id: 'local-vision',  name: 'Maez · Vision',     sub: 'on-device · multimodal',     family: 'local', badge: 'Local', color: A.mint,  ctx: '64K',  speed: 'fast' },
  { id: 'claude-sonnet', name: 'Claude Sonnet 4.6', sub: 'cloud · balanced',           family: 'claude',badge: 'Cloud', color: A.blue,  ctx: '200K', speed: 'med' },
  { id: 'claude-opus',   name: 'Claude Opus 4.7',   sub: 'cloud · deepest reasoning',  family: 'claude',badge: 'Cloud', color: A.purple,ctx: '200K', speed: 'slow' },
  { id: 'auto',          name: 'Auto',              sub: 'maez picks — usually local', family: 'auto',  badge: 'Smart', color: A.orange,ctx: 'auto', speed: 'adaptive' },
];

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
          style={{ width: 24, height: 24, borderRadius: 7, background: A.aiGrad, backgroundSize: '200% 200%', animation: 'ap-ai-shift 4s ease infinite', border: 'none', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: `0 2px 10px -2px ${A.indigo}99` }}>{Icon.plus(13)}</button>
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

function ChatPane({ tall, showSidebar = true }) {
  const sim = useSim();
  const [input, setInput] = React.useState('');
  const [modelId, setModelId] = React.useState('auto');
  const [thinking, setThinking] = React.useState(true);
  const [webSearch, setWebSearch] = React.useState(false);
  const [modelOpen, setModelOpen] = React.useState(false);
  const [toolsOpen, setToolsOpen] = React.useState(false);
  const [attachOpen, setAttachOpen] = React.useState(false);
  const scrollRef = React.useRef(null);
  const taRef = React.useRef(null);

  const model = MODELS.find(m => m.id === modelId);
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

  // Real chat: post to the daemon's /message endpoint (port 11435).
  // sim.sendMessage previously simulated a reply — now we push the user
  // turn into sim state, hit the daemon, and push the real reply back
  // into sim state when it arrives. No streaming yet (the daemon
  // endpoint returns the complete reply once); we just flip a pending
  // flag so the UI shows "Thinking…".
  const submit = async () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    // Optimistically show the user turn + a "thinking" placeholder
    sim.pushUserTurn ? sim.pushUserTurn(text) : sim.sendMessage(text);
    try {
      const res = await fetch('http://127.0.0.1:11435/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, source: 'cockpit' }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      const reply = (data && data.reply) || '(empty reply)';
      sim.pushAssistantTurn ? sim.pushAssistantTurn(reply) : sim.finishSimReply(reply);
    } catch (e) {
      const msg = "(cockpit couldn't reach daemon on :11435 — " + String(e) + ")";
      sim.pushAssistantTurn ? sim.pushAssistantTurn(msg) : sim.finishSimReply(msg);
    }
  };

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
            <span style={{ fontStyle: 'italic' }}>{sim.state.daemon.mood}</span>
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
        {(session?.history || []).map((m, i) => <ChatMessage key={i} m={m} />)}
        {sim.state.chat.streaming && <StreamingMessage text={sim.state.chat.streamBuf} route={sim.state.chat._route} model={sim.state.chat._model} showThinking={thinking} />}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px 10px' }}>
            {/* attach */}
            <div style={{ position: 'relative' }}>
              <button className="ap-btn" onClick={() => { setAttachOpen(!attachOpen); setModelOpen(false); setToolsOpen(false); }}
                style={composerIconBtn(attachOpen)}>{Icon.plus(15)}</button>
              {attachOpen && <AttachMenu onClose={() => setAttachOpen(false)} />}
            </div>

            {/* tools */}
            <div style={{ position: 'relative' }}>
              <button className="ap-btn" onClick={() => { setToolsOpen(!toolsOpen); setModelOpen(false); setAttachOpen(false); }}
                style={composerIconBtn(toolsOpen)}>{Icon.tool(14)}</button>
              {toolsOpen && <ToolsMenu onClose={() => setToolsOpen(false)} webSearch={webSearch} setWebSearch={setWebSearch} />}
            </div>

            {/* thinking toggle */}
            <button className="ap-btn" onClick={() => setThinking(!thinking)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 5, height: 28, padding: '0 10px',
                borderRadius: 8, border: `0.5px solid ${thinking ? A.purple + '66' : A.stroke}`,
                background: thinking ? `${A.purple}1f` : 'transparent',
                color: thinking ? A.purple : A.textDim, fontSize: 11.5, fontWeight: 500,
              }}>
              {Icon.brain(13)}
              <span>Extended Thinking</span>
              <span style={{ width: 22, height: 12, borderRadius: 999, background: thinking ? A.purple : A.textGhost, position: 'relative', transition: `background 200ms ${A.easing}` }}>
                <span style={{ position: 'absolute', top: 1, left: thinking ? 11 : 1, width: 10, height: 10, borderRadius: '50%', background: '#fff', transition: `left 200ms ${A.easing}`, boxShadow: '0 1px 2px rgba(0,0,0,0.3)' }} />
              </span>
            </button>

            {webSearch && <Chip color={A.cyan}>{Icon.globe(10)} Web</Chip>}

            <div style={{ flex: 1 }} />

            {/* model picker */}
            <div style={{ position: 'relative' }}>
              <button className="ap-btn" onClick={() => { setModelOpen(!modelOpen); setToolsOpen(false); setAttachOpen(false); }}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6, height: 28, padding: '0 10px',
                  borderRadius: 8, border: `0.5px solid ${A.stroke}`, background: A.surfaceRaised,
                  color: A.text, fontSize: 11.5, fontWeight: 500,
                }}>
                <Dot c={model.color} size={6} />
                <span>{model.name.replace('Maez · ', '').replace('Claude ', '')}</span>
                {Icon.chevronDown(11)}
              </button>
              {modelOpen && <ModelMenu current={modelId} onSelect={(id) => { setModelId(id); setModelOpen(false); }} onClose={() => setModelOpen(false)} />}
            </div>

            {/* mic */}
            <button className="ap-btn" style={composerIconBtn(false)}>{Icon.mic(14)}</button>

            {/* send */}
            <button className="ap-btn" onClick={submit} disabled={!input.trim()}
              style={{
                width: 30, height: 30, borderRadius: 8, border: 'none',
                background: input.trim() ? A.aiGrad : A.surfaceRaised,
                backgroundSize: '200% 200%', animation: input.trim() ? 'ap-ai-shift 3s ease infinite' : 'none',
                color: input.trim() ? '#fff' : A.textFaint,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: input.trim() ? `0 4px 14px -4px ${A.indigo}aa` : 'none',
                opacity: input.trim() ? 1 : 0.6,
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
            <button key={s.t} className="ap-btn" onClick={() => sim.sendMessage(s.t)}
              style={{
                background: `${s.c}14`, border: `0.5px solid ${s.c}33`, color: A.text,
                fontSize: 11.5, padding: '5px 11px', borderRadius: 999, fontFamily: A.sans,
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

function composerIconBtn(active) {
  return {
    width: 30, height: 28, borderRadius: 8,
    background: active ? A.surfaceRaised : 'transparent',
    border: `0.5px solid ${active ? A.strokeHi : 'transparent'}`,
    color: active ? A.text : A.textDim,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  };
}

function ModelMenu({ current, onSelect, onClose }) {
  React.useEffect(() => {
    const h = () => onClose();
    setTimeout(() => document.addEventListener('click', h, { once: true }), 0);
    return () => document.removeEventListener('click', h);
  }, []);
  return (
    <div className="ap-glass ap-menu" onClick={(e) => e.stopPropagation()}
      style={{
        position: 'absolute', bottom: 36, right: 0, width: 280,
        background: A.surfaceHi, border: `0.5px solid ${A.strokeHi}`, borderRadius: 14,
        boxShadow: '0 20px 50px -10px rgba(0,0,0,0.7)', padding: 5, zIndex: 100,
      }}>
      <div style={{ padding: '8px 10px 6px', fontSize: 10, color: A.textFaint, fontWeight: 600, letterSpacing: 0.6, textTransform: 'uppercase' }}>Model</div>
      {MODELS.map(m => {
        const active = current === m.id;
        return (
          <button key={m.id} className="ap-btn" onClick={() => onSelect(m.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px',
              background: active ? A.surfaceRaised : 'transparent', border: 'none', borderRadius: 8,
              color: A.text, textAlign: 'left', marginBottom: 1,
            }}>
            <Dot c={m.color} size={8} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 500, color: A.text }}>{m.name}</div>
              <div style={{ fontSize: 10.5, color: A.textDim, marginTop: 1 }}>{m.sub}</div>
            </div>
            <Chip color={m.color} tone="soft" style={{ fontSize: 9 }}>{m.badge}</Chip>
            {active && <span style={{ color: A.blue }}>{Icon.check(13)}</span>}
          </button>
        );
      })}
      <div style={{ borderTop: `0.5px solid ${A.stroke}`, margin: '6px 0 0', padding: '8px 10px', fontSize: 10.5, color: A.textFaint, fontFamily: A.mono, lineHeight: 1.5 }}>
        Auto routes to Claude for code-heavy, long-context, or deep reasoning — otherwise local.
      </div>
    </div>
  );
}

function ToolsMenu({ onClose, webSearch, setWebSearch }) {
  React.useEffect(() => {
    const h = () => onClose();
    setTimeout(() => document.addEventListener('click', h, { once: true }), 0);
    return () => document.removeEventListener('click', h);
  }, []);
  const [selected, setSelected] = React.useState({ shell: true, memory: true, web: webSearch, code: true, vision: false });
  const tools = [
    { k: 'shell',  label: 'Shell commands',   desc: 'Run bash, check services — with approval', icon: Icon.terminal(13), color: A.green },
    { k: 'memory', label: 'Memory recall',     desc: 'Search Chroma archive · three tiers',       icon: Icon.memory(13),   color: A.orange },
    { k: 'web',    label: 'Web search',        desc: 'Fetch up-to-date info from the web',        icon: Icon.globe(13),    color: A.cyan },
    { k: 'code',   label: 'Code execution',    desc: 'Python sandbox · scratch work',             icon: Icon.code(13),     color: A.purple },
    { k: 'vision', label: 'Vision',            desc: 'Screenshots, photos, diagrams',             icon: Icon.image(13),    color: A.pink },
  ];
  return (
    <div className="ap-glass ap-menu" onClick={(e) => e.stopPropagation()}
      style={{
        position: 'absolute', bottom: 36, left: 0, width: 320,
        background: A.surfaceHi, border: `0.5px solid ${A.strokeHi}`, borderRadius: 14,
        boxShadow: '0 20px 50px -10px rgba(0,0,0,0.7)', padding: 5, zIndex: 100,
      }}>
      <div style={{ padding: '8px 10px 6px', fontSize: 10, color: A.textFaint, fontWeight: 600, letterSpacing: 0.6, textTransform: 'uppercase' }}>Tools</div>
      {tools.map(t => {
        const on = selected[t.k];
        return (
          <button key={t.k} className="ap-btn"
            onClick={() => { const n = { ...selected, [t.k]: !on }; setSelected(n); if (t.k === 'web') setWebSearch(!on); }}
            style={{
              display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px',
              background: on ? A.surfaceRaised : 'transparent', border: 'none', borderRadius: 8,
              color: A.text, textAlign: 'left', marginBottom: 1,
            }}>
            <div style={{ width: 26, height: 26, borderRadius: 7, background: `${t.color}22`, color: t.color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{t.icon}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 500, color: A.text }}>{t.label}</div>
              <div style={{ fontSize: 10.5, color: A.textDim, marginTop: 1 }}>{t.desc}</div>
            </div>
            <span style={{ width: 26, height: 14, borderRadius: 999, background: on ? A.green : A.textGhost, position: 'relative', flexShrink: 0, transition: `background 200ms ${A.easing}` }}>
              <span style={{ position: 'absolute', top: 1, left: on ? 13 : 1, width: 12, height: 12, borderRadius: '50%', background: '#fff', transition: `left 200ms ${A.easing}`, boxShadow: '0 1px 2px rgba(0,0,0,0.3)' }} />
            </span>
          </button>
        );
      })}
    </div>
  );
}

function AttachMenu({ onClose }) {
  React.useEffect(() => {
    const h = () => onClose();
    setTimeout(() => document.addEventListener('click', h, { once: true }), 0);
    return () => document.removeEventListener('click', h);
  }, []);
  const items = [
    { label: 'Upload file',      icon: Icon.attach(13), color: A.blue },
    { label: 'Paste screenshot', icon: Icon.image(13),  color: A.pink },
    { label: 'Include signals',  icon: Icon.sparkle(13),color: A.orange },
    { label: 'Reference memory', icon: Icon.memory(13), color: A.purple },
    { label: 'Pin this thread',  icon: Icon.check(13),  color: A.green },
  ];
  return (
    <div className="ap-glass ap-menu" onClick={(e) => e.stopPropagation()}
      style={{
        position: 'absolute', bottom: 36, left: 0, width: 220,
        background: A.surfaceHi, border: `0.5px solid ${A.strokeHi}`, borderRadius: 14,
        boxShadow: '0 20px 50px -10px rgba(0,0,0,0.7)', padding: 5, zIndex: 100, transformOrigin: 'bottom left',
      }}>
      {items.map(i => (
        <button key={i.label} className="ap-btn"
          style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '8px 10px', background: 'transparent', border: 'none', borderRadius: 8, color: A.text, textAlign: 'left' }}>
          <span style={{ color: i.color }}>{i.icon}</span>
          <span style={{ fontSize: 12.5, fontWeight: 500 }}>{i.label}</span>
        </button>
      ))}
    </div>
  );
}

function MaezAvatar({ size = 32 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', position: 'relative', flexShrink: 0,
      background: A.aiGrad, backgroundSize: '200% 200%',
      animation: 'ap-ai-shift 6s ease infinite',
      boxShadow: `0 0 ${size}px -4px rgba(191, 90, 242, 0.6), inset 0 0 ${size/3}px rgba(255,255,255,0.2)`,
    }}>
      <div style={{ position: 'absolute', inset: 2, borderRadius: '50%', border: `0.5px solid rgba(255,255,255,0.3)` }} />
    </div>
  );
}

function ChatMessage({ m }) {
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
    <div className="ap-rise" style={{ display: 'flex', gap: 10, marginBottom: 18 }}>
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
        {showThinking && <ThinkingBlock text="Checking working memory for the rgb context from earlier. VRAM has headroom (1.6GB free). No need to route to Claude." streaming />}
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
  const entries = Object.entries(sim.state.health);
  return (
    <Card title="Services" subtitle={`${entries.length} running · 0 errors`}
      icon={<Dot c={A.green} size={6} pulse />} iconColor={A.green}
      right={<Chip color={A.green}>Nominal</Chip>}>
      <div className="ap-scroll" style={{ margin: '-4px -4px', overflow: 'auto', maxHeight: '100%', paddingRight: 4 }}>
        {entries.map(([name, v]) => (
          <div key={name} className="ap-hover-lift" style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', borderRadius: 8,
            border: '0.5px solid transparent', transition: `all 180ms`,
          }}>
            <Dot c={v.status === 'active' ? A.green : A.red} pulse={v.status === 'active'} size={5} />
            <span style={{ flex: 1, fontFamily: A.sans, fontSize: 12.5, color: A.text }}>{name}</span>
            <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textDim }}>{v.port ? `:${v.port}` : '—'}</span>
            {v.ms != null && (
              <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint, minWidth: 34, textAlign: 'right' }}>{v.ms}ms</span>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function GpuPane() {
  const sim = useSim();
  const g = sim.state.gpu;
  const vramPct = (g.vramUsed / g.vramTotal) * 100;
  const vramHist = useSparkValues(() => SIM.state.gpu.vramUsed);
  const utilHist = useSparkValues(() => SIM.state.gpu.util);
  return (
    <Card title="RTX 4090" subtitle={`${g.temp.toFixed(0)}° · ${g.power}W · CUDA 12.4`}
      icon="⚡" iconColor={A.orange}
      right={<Chip color={A.orange}>GPU</Chip>}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontFamily: A.sans, fontSize: 11, color: A.textDim }}>VRAM</span>
            <span style={{ fontFamily: A.mono, fontSize: 11.5, color: A.text }}>
              {g.vramUsed.toFixed(1)} <span style={{ color: A.textFaint }}>/ {g.vramTotal} GB</span>
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

function DaemonPane({ compact }) {
  const sim = useSim();
  const d = sim.state.daemon;
  const pct = ((30 - d.nextTickIn) / 30) * 100;
  return (
    <Card title="Daemon" subtitle={`Cycle #${d.cycle.toLocaleString()} · ${d.mood}`}
      icon="◎" iconColor={A.indigo}
      right={<Chip color={A.indigo}>{d.nextTickIn}s</Chip>}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <TickRing progress={pct} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: A.sans, fontSize: 9.5, color: A.textFaint, letterSpacing: 0.8, fontWeight: 600, textTransform: 'uppercase' }}>Current thought</div>
            <div style={{ fontFamily: A.sans, fontSize: 12, color: A.textSoft, lineHeight: 1.45, marginTop: 3, fontStyle: 'italic' }}>
              "{d.currentThought}"
            </div>
          </div>
        </div>
        {!compact && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, borderTop: `0.5px solid ${A.stroke}`, paddingTop: 10 }}>
            <Meter label="Cognition" value={d.score} color={d.score > 0.75 ? A.green : A.orange} />
            <Meter label="Uncertainty" value={d.uncertainty} color={A.cyan} />
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

function MemorySurface() {
  const sim = useSim();
  const [q, setQ] = React.useState('');
  const [tier, setTier] = React.useState('all');
  const hits = sim.state.memory.hits.filter((h) =>
    (!q || h.text.toLowerCase().includes(q.toLowerCase())) && (tier === 'all' || h.tier === tier)
  );
  const colorFor = (t) => ({ core: A.orange, daily: A.green, raw: A.blue }[t]);
  return (
    <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
      <SurfaceHeader title="Memory" subtitle="Chroma archive · three tiers of remembering" icon="◍" color={A.orange} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 20 }}>
        {Object.entries(sim.state.memory.stats).map(([k, v]) => (
          <Glass key={k} pad={18} style={{ borderTop: `2px solid ${colorFor(k)}` }}>
            <div style={{ fontSize: 10, color: A.textFaint, textTransform: 'uppercase', letterSpacing: 1, fontFamily: A.sans, fontWeight: 600 }}>{k}</div>
            <div style={{ fontFamily: A.sans, fontSize: 34, color: colorFor(k), letterSpacing: -1, lineHeight: 1, marginTop: 6, fontWeight: 600 }}>{v.toLocaleString()}</div>
            <div style={{ fontSize: 11, color: A.textFaint, marginTop: 4 }}>entries</div>
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
      {hits.map((h, i) => (
        <Glass key={i} pad={14} style={{ marginBottom: 10, borderLeft: `3px solid ${colorFor(h.tier)}` }} className="ap-rise ap-card">
          <div style={{ display: 'flex', gap: 8, marginBottom: 6, fontSize: 10, color: A.textDim, alignItems: 'center' }}>
            <Chip color={colorFor(h.tier)}>{h.tier}</Chip>
            <span style={{ fontFamily: A.mono }}>score {h.score.toFixed(2)}</span>
            <span>·</span>
            <span style={{ fontFamily: A.mono }}>{h.date}</span>
            <span>·</span>
            <span style={{ fontFamily: A.mono }}>{h.tokens} tok</span>
          </div>
          <div style={{ fontFamily: A.sans, fontSize: 14, color: A.text, lineHeight: 1.55 }}>{h.text}</div>
        </Glass>
      ))}
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

function ApprovalsQueueSurface() {
  const sim = useSim();
  return (
    <div className="ap-scroll" style={{ height: '100%', overflow: 'auto', padding: 28 }}>
      <SurfaceHeader title="Approvals" subtitle="Commands waiting for your nod" icon="◐" color={A.orange} />
      {sim.state.chat.pendingCommand && <div style={{ marginBottom: 14 }}><PendingCommand p={sim.state.chat.pendingCommand} /></div>}
      {sim.state.approvals.map((a) => (
        <Glass key={a.id} className="ap-rise" pad={18} style={{
          marginBottom: 12,
          background: `linear-gradient(135deg, ${A.orange}14, ${A.orange}04)`,
          border: `0.5px solid ${A.orange}44`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Dot c={A.orange} pulse />
            <span style={{ fontFamily: A.sans, fontSize: 11, color: A.orange, letterSpacing: 0.3, textTransform: 'uppercase', fontWeight: 600 }}>Pending · {a.risk}-risk</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontFamily: A.mono, fontSize: 10, color: A.textFaint }}>{a.ts}</span>
          </div>
          <div style={{ background: A.bgElev, borderRadius: 10, padding: '9px 12px', marginBottom: 10, fontFamily: A.mono, fontSize: 12.5, color: A.text }}>
            <span style={{ color: A.orange }}>$</span> {a.cmd}
          </div>
          <div style={{ fontFamily: A.sans, fontSize: 13, color: A.textSoft, marginBottom: 12 }}>{a.reason}</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button variant="primary" color={A.green} onClick={() => sim.approveQueued(a.id, true)} icon={Icon.check(13)}>Approve</Button>
            <Button variant="danger" onClick={() => sim.approveQueued(a.id, false)} icon={Icon.x(13)}>Deny</Button>
          </div>
        </Glass>
      ))}
      {!sim.state.approvals.length && !sim.state.chat.pendingCommand && (
        <div style={{ textAlign: 'center', padding: '60px 0', color: A.textFaint, fontFamily: A.sans, fontSize: 14 }}>
          Queue is empty. Maez is well-behaved.
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
    { k: 'reason',   desc: 'Weigh context' },
    { k: 'score',    desc: 'Rate response' },
    { k: 'evolve',   desc: 'Propose change' },
    { k: 'message?', desc: 'Speak or stay' },
  ];
  const activeStep = Math.min(4, Math.floor(((30 - d.nextTickIn) / 30) * 5));
  const [hist, setHist] = React.useState(() => Array(40).fill(0).map((_, i) => 0.5 + Math.sin(i/3) * 0.2 + Math.random()*0.1));
  React.useEffect(() => {
    const id = setInterval(() => setHist((h) => [...h.slice(1), SIM.state.daemon.score]), 800);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ height: '100%', padding: 28, display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: 'auto 1fr', gap: 14, overflow: 'hidden' }}>
      <div style={{ gridColumn: '1 / span 2' }}>
        <Card title="30-second loop" subtitle="perceive → reason → score → evolve → message"
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
          <div style={{ fontFamily: A.sans, fontSize: 10, color: A.textFaint, letterSpacing: 0.8, fontWeight: 600, textTransform: 'uppercase', marginBottom: 6 }}>Current thought</div>
          <div style={{ fontFamily: A.sans, fontSize: 15, color: A.text, padding: 14, background: A.surfaceLo, borderRadius: 10, borderLeft: `2px solid ${A.indigo}`, lineHeight: 1.5, fontStyle: 'italic' }}>
            "{d.currentThought}"
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

function CodeBlock({ lang, content, copyKey }) {
  const [copied, setCopied] = React.useState(false);
  const copy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  };
  return (
    <div style={{ margin: '10px 0', borderRadius: 8, overflow: 'hidden',
                    border: `0.5px solid ${A.stroke}`,
                    background: 'rgba(0,0,0,0.35)' }}>
      <div style={{ display: 'flex', alignItems: 'center',
                      padding: '6px 12px',
                      borderBottom: `0.5px solid ${A.stroke}`,
                      background: 'rgba(0,0,0,0.25)', fontFamily: A.mono,
                      fontSize: 10, color: A.textFaint,
                      letterSpacing: 0.4, textTransform: 'uppercase' }}>
        <span>{lang || 'code'}</span>
        <span style={{ flex: 1 }} />
        <button onClick={copy} className="ap-btn"
          style={{ background: 'transparent',
                     border: `0.5px solid ${A.stroke}`, padding: '2px 8px',
                     borderRadius: 6, color: copied ? A.mint : A.textDim,
                     fontSize: 10, fontFamily: A.mono, cursor: 'pointer' }}>
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
      <pre style={{ margin: 0, padding: '10px 14px', overflow: 'auto',
                      fontFamily: A.mono, fontSize: 12.5, lineHeight: 1.5,
                      color: A.text, whiteSpace: 'pre' }}>
        {content}
      </pre>
    </div>
  );
}

function MarkdownTurn({ content, turnId }) {
  const parts = React.useMemo(() => _splitMarkdown(content), [content]);
  return (
    <React.Fragment>
      {parts.map((p, i) => {
        if (p.type === 'code') {
          return <CodeBlock key={i} lang={p.lang} content={p.content}
                              copyKey={`${turnId}-${i}`} />;
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
                ? `${activeSession.model} · ${turns.length} turns`
                : 'pick a session or create one'}
            </div>
          </div>
          {activeSession && (
            <Button size="sm" onClick={() => deleteSession(activeSession.id)}>
              delete
            </Button>
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
                <MarkdownTurn content={t.content} turnId={t.id} />
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
  S, A, Card, Glass, Chip, Dot, Button, MaezAvatar, Icon, SegmentedControl,
  ChatPane, ServicesPane, GpuPane, DaemonPane, SignalsPane, ScratchpadPane, RouterPane,
  MemorySurface, SoulSurface, DreamsSurface, IdentitySurface, LogsSurface, ApprovalsQueueSurface,
  JudgmentSurface, SelfDevSurface, WorkshopSurface, DaemonDeep,
  // back-compat aliases (in case shell uses these)
  SoftBtn: Button, Pill: Chip,
};
})();
