// components2.jsx — chat bubbles, reading text features, form inputs, tooltip, dropzone, pipeline, lock.

// ─────────────────────────────────────────────────────────────
// Chat Bubbles
// ─────────────────────────────────────────────────────────────

const UserBubble = ({ children, pageAt }) => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, marginLeft: 48 }}>
    <div style={{
      background: 'var(--paper-1)', color: 'var(--ink-0)',
      padding: '12px 16px', borderRadius: 'var(--r-lg)',
      borderBottomRightRadius: 'var(--r-xs)',
      fontFamily: 'var(--serif)', fontSize: 15, lineHeight: 1.55,
      maxWidth: '100%', textWrap: 'pretty',
    }}>{children}</div>
    {pageAt != null && (
      <div style={{ fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--ink-3)', letterSpacing: 0.2, marginRight: 4 }}>
        asked at p. {pageAt}
      </div>
    )}
  </div>
);

const AssistantBubble = ({ children, sources, streaming, spoilerSafe = true }) => (
  <div style={{ display: 'flex', gap: 12, marginRight: 48 }}>
    <div style={{
      flexShrink: 0, width: 28, height: 28, borderRadius: 999,
      background: 'var(--accent-softer)', color: 'var(--accent)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 13, fontWeight: 500,
      marginTop: 2,
    }}>r</div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{
        fontFamily: 'var(--serif)', fontSize: 15.5, lineHeight: 1.65, color: 'var(--ink-0)',
        textWrap: 'pretty',
      }}>
        {children}
        {streaming && <span className="br-cursor" style={{
          display: 'inline-block', width: 7, height: 15, background: 'var(--accent)',
          marginLeft: 2, verticalAlign: -2, animation: 'brBlink 1s steps(2) infinite',
        }}/>}
      </div>
      {spoilerSafe && (
        <div style={{ marginTop: 10, display: 'inline-flex', alignItems: 'center', gap: 6,
          fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--ink-3)', letterSpacing: 0.2 }}>
          <IcLock size={11}/> spoiler-safe through your page
        </div>
      )}
      {sources && sources.length > 0 && (
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {sources.map((s, i) => (
            <div key={i} style={{
              padding: '8px 12px', borderLeft: '2px solid var(--accent)',
              background: 'var(--accent-softer)',
              fontFamily: 'var(--serif)', fontSize: 13.5, fontStyle: 'italic', lineHeight: 1.5,
              color: 'var(--ink-1)',
            }}>
              <span style={{ textWrap: 'pretty' }}>“{s.quote}”</span>
              <span style={{ display: 'inline-block', marginLeft: 8, fontFamily: 'var(--sans)',
                fontStyle: 'normal', fontSize: 11, color: 'var(--ink-2)', letterSpacing: 0.2 }}>
                {s.ch} · p. {s.page}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// Word-level highlight / selection
// ─────────────────────────────────────────────────────────────

const Highlight = ({ children, variant = 'mark', onClick }) => {
  // variant: 'mark' (user highlight) · 'selection' (active) · 'entity' (linked) · 'quote' (cited)
  const styles = {
    mark:      { background: 'color-mix(in oklab, var(--accent-soft) 70%, transparent)', color: 'var(--ink-0)' },
    selection: { background: 'var(--accent)', color: 'var(--paper-00)' },
    entity:    { borderBottom: '1.5px solid var(--accent)', color: 'var(--ink-0)', cursor: 'pointer' },
    quote:     { background: 'var(--accent-softer)', color: 'var(--ink-0)' },
  }[variant];
  return <span onClick={onClick} style={{ padding: '0 2px', borderRadius: 'var(--r-xs)', ...styles }}>{children}</span>;
};

// Progressive blur overlay — SVG mask, not CSS filter (composites reliably)
const ProgressiveBlur = ({ from = 0.55, to = 1, height = 260, locked = true }) => (
  <div style={{
    position: 'absolute', left: 0, right: 0, bottom: 0, height, pointerEvents: 'none',
    background: `linear-gradient(to bottom,
      transparent 0%,
      color-mix(in oklab, var(--paper-0) 25%, transparent) ${from * 50}%,
      color-mix(in oklab, var(--paper-0) 65%, transparent) ${from * 70 + 20}%,
      var(--paper-0) ${to * 100}%)`,
    backdropFilter: `blur(${6}px)`,
    maskImage: `linear-gradient(to bottom, transparent 0%, #000 ${from * 60}%, #000 100%)`,
    WebkitMaskImage: `linear-gradient(to bottom, transparent 0%, #000 ${from * 60}%, #000 100%)`,
  }}>
    {locked && (
      <div style={{ position: 'absolute', bottom: 40, left: 0, right: 0, display: 'flex', justifyContent: 'center' }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '8px 14px', borderRadius: 'var(--r-pill)',
          background: 'var(--paper-00)', color: 'var(--ink-1)',
          boxShadow: 'var(--shadow-1)', border: 'var(--hairline)',
          fontFamily: 'var(--sans)', fontSize: 12, pointerEvents: 'auto',
          letterSpacing: 0.2, cursor: 'pointer',
        }}>
          <IcLock size={12}/> beyond your page — advance to reveal
        </div>
      </div>
    )}
  </div>
);

// ─────────────────────────────────────────────────────────────
// Inputs
// ─────────────────────────────────────────────────────────────

const TextInput = ({ label, placeholder, value, onChange, hint, error, icon, size = 'md' }) => {
  const [focus, setFocus] = React.useState(false);
  const heights = { sm: 30, md: 38, lg: 44 };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontFamily: 'var(--sans)' }}>
      {label && <label style={{ fontSize: 12, color: 'var(--ink-2)', letterSpacing: 0.2 }}>{label}</label>}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        height: heights[size], padding: '0 12px',
        background: 'var(--paper-00)', color: 'var(--ink-0)',
        border: `1px solid ${error ? 'var(--err)' : focus ? 'var(--accent)' : 'var(--paper-2)'}`,
        boxShadow: focus ? '0 0 0 3px var(--accent-softer)' : 'none',
        borderRadius: 'var(--r-md)',
        transition: 'border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease)',
      }}>
        {icon && <span style={{ color: 'var(--ink-3)' }}>{icon}</span>}
        <input value={value ?? ''} onChange={(e) => onChange && onChange(e.target.value)}
          onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
          placeholder={placeholder}
          style={{
            flex: 1, border: 0, outline: 'none', background: 'transparent',
            fontFamily: 'var(--sans)', fontSize: 14, color: 'var(--ink-0)',
          }}/>
      </div>
      {(hint || error) && <div style={{ fontSize: 11, color: error ? 'var(--err)' : 'var(--ink-3)' }}>{error || hint}</div>}
    </div>
  );
};

const ChatInput = ({ value, onChange, onSend, placeholder = 'Ask about what you\'ve read…', disabled }) => {
  const [focus, setFocus] = React.useState(false);
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-end', gap: 8,
      padding: '10px 10px 10px 16px',
      background: 'var(--paper-00)',
      border: `1px solid ${focus ? 'var(--accent)' : 'var(--paper-2)'}`,
      boxShadow: focus ? '0 0 0 3px var(--accent-softer), var(--shadow-1)' : 'var(--shadow-1)',
      borderRadius: 'var(--r-lg)',
      transition: 'border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease)',
      fontFamily: 'var(--serif)',
    }}>
      <textarea value={value ?? ''} onChange={(e) => onChange && onChange(e.target.value)}
        onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
        placeholder={placeholder} rows={1}
        style={{
          flex: 1, border: 0, outline: 'none', background: 'transparent', resize: 'none',
          fontFamily: 'var(--serif)', fontSize: 15.5, lineHeight: 1.5,
          color: 'var(--ink-0)', padding: '6px 0', minHeight: 24, maxHeight: 160,
        }}/>
      <button onClick={onSend} disabled={disabled || !value} style={{
        width: 34, height: 34, borderRadius: 'var(--r-md)',
        background: value ? 'var(--accent)' : 'var(--paper-1)',
        color: value ? 'var(--paper-00)' : 'var(--ink-3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: value ? 'pointer' : 'not-allowed',
        transition: 'background var(--dur) var(--ease), color var(--dur) var(--ease)',
      }}><IcSend size={15}/></button>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Tooltip (visual component — static positioning)
// ─────────────────────────────────────────────────────────────

const Tooltip = ({ children, content, side = 'top' }) => (
  <span style={{ position: 'relative', display: 'inline-flex' }} className="br-tt">
    {children}
    <span style={{
      position: 'absolute', [side === 'top' ? 'bottom' : 'top']: 'calc(100% + 6px)',
      left: '50%', transform: 'translateX(-50%)',
      background: 'var(--ink-0)', color: 'var(--paper-00)',
      fontFamily: 'var(--sans)', fontSize: 12, letterSpacing: 0.1,
      padding: '6px 10px', borderRadius: 'var(--r-sm)',
      boxShadow: 'var(--shadow-2)', whiteSpace: 'nowrap',
      pointerEvents: 'none', opacity: 0,
      transition: 'opacity var(--dur) var(--ease)',
    }} className="br-tt-bubble">{content}</span>
  </span>
);

// ─────────────────────────────────────────────────────────────
// Dropzone
// ─────────────────────────────────────────────────────────────

const Dropzone = ({ active, filename, state = 'idle' }) => {
  // state: 'idle' | 'hover' | 'uploading' | 'done' | 'error'
  const isHover = active || state === 'hover';
  return (
    <div style={{
      border: `1.5px dashed ${isHover ? 'var(--accent)' : 'var(--paper-3)'}`,
      background: isHover ? 'var(--accent-softer)' : 'var(--paper-00)',
      borderRadius: 'var(--r-lg)',
      padding: '56px 40px', textAlign: 'center',
      fontFamily: 'var(--sans)', color: 'var(--ink-1)',
      transition: 'all var(--dur) var(--ease)',
      cursor: 'pointer',
    }}>
      <div style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 44, height: 44, borderRadius: 999,
        background: isHover ? 'var(--accent)' : 'var(--paper-1)',
        color: isHover ? 'var(--paper-00)' : 'var(--ink-2)',
        marginBottom: 16, transition: 'all var(--dur) var(--ease)',
      }}>
        <IcUpload size={18}/>
      </div>
      <div style={{ fontFamily: 'var(--serif)', fontSize: 20, color: 'var(--ink-0)', letterSpacing: -0.3, marginBottom: 6 }}>
        {filename || (isHover ? 'Drop it here' : 'Drop your EPUB')}
      </div>
      <div style={{ fontSize: 13, color: 'var(--ink-2)' }}>
        or <span style={{ color: 'var(--accent)', textDecoration: 'underline', textUnderlineOffset: 3 }}>browse files</span>
        {' '}· EPUB up to 500&nbsp;MB
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Pipeline Status Badge
// ─────────────────────────────────────────────────────────────

const StatusBadge = ({ state = 'idle', label }) => {
  // state: 'idle' | 'running' | 'done' | 'error' | 'queued'
  const variants = {
    idle:    { bg: 'var(--paper-1)',     fg: 'var(--ink-2)',  dot: 'var(--ink-3)' },
    queued:  { bg: 'var(--paper-1)',     fg: 'var(--ink-1)',  dot: 'var(--ink-3)' },
    running: { bg: 'var(--accent-softer)', fg: 'var(--accent-ink)', dot: 'var(--accent)', pulse: true },
    done:    { bg: 'var(--accent-softer)', fg: 'var(--accent-ink)', dot: 'var(--ok)' },
    error:   { bg: 'color-mix(in oklab, var(--err) 12%, var(--paper-0))', fg: 'var(--err)', dot: 'var(--err)' },
  }[state];
  const labels = { idle: 'idle', queued: 'queued', running: 'running', done: 'done', error: 'failed' };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 7,
      height: 22, padding: '0 10px', borderRadius: 'var(--r-pill)',
      background: variants.bg, color: variants.fg,
      fontFamily: 'var(--sans)', fontSize: 11, fontWeight: 500, letterSpacing: 0.4,
      textTransform: 'uppercase',
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: 999, background: variants.dot,
        boxShadow: variants.pulse ? '0 0 0 0 currentColor' : 'none',
        animation: variants.pulse ? 'brPulse 1.6s var(--ease-out) infinite' : 'none',
      }}/>
      {label || labels[state]}
    </span>
  );
};

const PipelineRow = ({ stage, desc, state, meta }) => (
  <div style={{
    display: 'grid', gridTemplateColumns: '24px 1fr auto auto',
    alignItems: 'center', gap: 16, padding: '14px 4px',
    borderBottom: 'var(--hairline)',
    fontFamily: 'var(--sans)',
    opacity: state === 'idle' ? 0.55 : 1,
    transition: 'opacity var(--dur) var(--ease)',
  }}>
    <div style={{
      width: 20, height: 20, borderRadius: 999,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: state === 'done' ? 'var(--ok)' : state === 'running' ? 'var(--accent)' : state === 'error' ? 'var(--err)' : 'var(--ink-4)',
      background: state === 'done' ? 'color-mix(in oklab, var(--ok) 18%, var(--paper-0))' : state === 'running' ? 'var(--accent-softer)' : 'transparent',
      border: state === 'idle' ? '1px solid var(--paper-3)' : 'none',
    }}>
      {state === 'done' ? <IcCheck size={12}/> : state === 'running' ? <span style={{ width:6, height:6, borderRadius:999, background:'currentColor', animation:'brPulse 1.6s infinite'}}/> : state === 'error' ? <IcClose size={11}/> : null}
    </div>
    <div>
      <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--ink-0)', fontFamily: 'var(--sans)', letterSpacing: 0.1 }}>{stage}</div>
      <div style={{ fontSize: 12, color: 'var(--ink-2)', marginTop: 2 }}>{desc}</div>
    </div>
    <div style={{ fontSize: 11, color: 'var(--ink-3)', fontVariantNumeric: 'tabular-nums' }}>{meta}</div>
    <StatusBadge state={state}/>
  </div>
);

// ─────────────────────────────────────────────────────────────
// Lock icon states
// ─────────────────────────────────────────────────────────────

const LockState = ({ state = 'locked', label }) => {
  const map = {
    locked:    { Icon: IcLock,    color: 'var(--ink-3)',  label: label ?? 'Locked until this chapter' },
    unlocked:  { Icon: IcUnlock,  color: 'var(--accent)', label: label ?? 'Unlocked' },
    current:   { Icon: IcBookmark,color: 'var(--accent)', label: label ?? "You're here" },
    spoilerSafe:{Icon: IcLock,    color: 'var(--accent)', label: label ?? 'Spoiler-safe' },
  }[state];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: 'var(--sans)', fontSize: 12, color: map.color, letterSpacing: 0.2,
    }}>
      <map.Icon size={12}/>{map.label}
    </span>
  );
};

Object.assign(window, {
  UserBubble, AssistantBubble, Highlight, ProgressiveBlur,
  TextInput, ChatInput, Tooltip, Dropzone, StatusBadge, PipelineRow, LockState,
});
