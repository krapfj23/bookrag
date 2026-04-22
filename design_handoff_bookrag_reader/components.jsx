// components.jsx — BookRAG design system components.
// Every component reads CSS vars from tokens.css so theme/accent/density swap live.

// ─────────────────────────────────────────────────────────────
// Primitives
// ─────────────────────────────────────────────────────────────

const Stack = ({ gap = 16, children, style, ...rest }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap, ...style }} {...rest}>{children}</div>
);

const Row = ({ gap = 12, align = 'center', children, style, ...rest }) => (
  <div style={{ display: 'flex', alignItems: align, gap, ...style }} {...rest}>{children}</div>
);

const Divider = ({ style }) => (
  <div style={{ height: 1, background: 'var(--paper-2)', width: '100%', ...style }} />
);

// ─────────────────────────────────────────────────────────────
// Top Nav Bar
// ─────────────────────────────────────────────────────────────

const Wordmark = ({ size = 20 }) => (
  <span style={{ fontFamily: 'var(--serif)', fontSize: size, fontWeight: 500, letterSpacing: -0.3, color: 'var(--ink-0)' }}>
    Book<span style={{ fontStyle: 'italic', color: 'var(--accent)' }}>rag</span>
  </span>
);

const NavBar = ({ active = 'library', onThemeToggle, theme = 'light' }) => {
  const items = [
    { id: 'library', label: 'Library' },
    { id: 'reading', label: 'Reading' },
    { id: 'upload', label: 'Upload' },
  ];
  return (
    <header style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '14px 28px', borderBottom: 'var(--hairline)',
      background: 'color-mix(in oklab, var(--paper-0) 80%, transparent)',
      backdropFilter: 'saturate(140%) blur(12px)',
      fontFamily: 'var(--sans)',
      height: 56, boxSizing: 'border-box',
    }}>
      <Row gap={32}>
        <Wordmark />
        <nav style={{ display: 'flex', gap: 4 }}>
          {items.map((it) => (
            <a key={it.id} href="#" style={{
              padding: '6px 12px', fontSize: 'var(--t-sm)',
              color: active === it.id ? 'var(--ink-0)' : 'var(--ink-2)',
              borderRadius: 'var(--r-sm)',
              fontWeight: active === it.id ? 500 : 400,
              background: active === it.id ? 'var(--paper-1)' : 'transparent',
              transition: 'color var(--dur) var(--ease), background var(--dur) var(--ease)',
            }}>{it.label}</a>
          ))}
        </nav>
      </Row>
      <Row gap={8}>
        <IconBtn onClick={onThemeToggle} title="Toggle theme">
          {theme === 'dark' ? <IcSun size={15}/> : <IcMoon size={15}/>}
        </IconBtn>
        <IconBtn title="Settings"><IcSettings size={15}/></IconBtn>
        <div style={{
          width: 28, height: 28, borderRadius: 999, background: 'var(--accent-soft)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--serif)', fontSize: 13, color: 'var(--accent-ink)',
          fontWeight: 500, cursor: 'pointer',
        }}>N</div>
      </Row>
    </header>
  );
};

const IconBtn = ({ children, onClick, title, active }) => (
  <button onClick={onClick} title={title} style={{
    width: 30, height: 30, display: 'flex', alignItems: 'center', justifyContent: 'center',
    borderRadius: 'var(--r-sm)',
    color: active ? 'var(--ink-0)' : 'var(--ink-2)',
    background: active ? 'var(--paper-1)' : 'transparent',
    transition: 'background var(--dur) var(--ease), color var(--dur) var(--ease)',
    cursor: 'pointer',
  }}
  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--paper-1)'; e.currentTarget.style.color = 'var(--ink-0)'; }}
  onMouseLeave={(e) => { e.currentTarget.style.background = active ? 'var(--paper-1)' : 'transparent'; e.currentTarget.style.color = active ? 'var(--ink-0)' : 'var(--ink-2)'; }}
  >{children}</button>
);

// ─────────────────────────────────────────────────────────────
// Buttons
// ─────────────────────────────────────────────────────────────

const Button = ({ variant = 'primary', size = 'md', children, icon, iconRight, onClick, disabled, title, style }) => {
  const sizes = {
    sm: { padding: '5px 10px', fontSize: 13, height: 28, gap: 6 },
    md: { padding: '7px 14px', fontSize: 14, height: 34, gap: 8 },
    lg: { padding: '10px 18px', fontSize: 15, height: 42, gap: 10 },
  }[size];
  const variants = {
    primary: {
      background: 'var(--ink-0)', color: 'var(--paper-0)',
      hover: { background: 'var(--ink-1)' },
    },
    secondary: {
      background: 'var(--paper-1)', color: 'var(--ink-0)',
      hover: { background: 'var(--paper-2)' },
    },
    ghost: {
      background: 'transparent', color: 'var(--ink-1)',
      hover: { background: 'var(--paper-1)', color: 'var(--ink-0)' },
    },
    accent: {
      background: 'var(--accent)', color: 'var(--paper-00)',
      hover: { background: 'var(--accent-deep)' },
    },
    accentSoft: {
      background: 'var(--accent-soft)', color: 'var(--accent-ink)',
      hover: { background: 'color-mix(in oklab, var(--accent-soft) 85%, var(--ink-0))' },
    },
  }[variant];
  return (
    <button onClick={onClick} disabled={disabled} title={title} style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      gap: sizes.gap, padding: sizes.padding, height: sizes.height,
      fontSize: sizes.fontSize, fontFamily: 'var(--sans)', fontWeight: 500,
      letterSpacing: 0.1,
      borderRadius: 'var(--r-md)',
      background: variants.background, color: variants.color,
      transition: 'background var(--dur) var(--ease), color var(--dur) var(--ease), transform var(--dur-fast) var(--ease)',
      opacity: disabled ? 0.4 : 1, cursor: disabled ? 'not-allowed' : 'pointer',
      ...style,
    }}
    onMouseEnter={(e) => { if (!disabled) Object.assign(e.currentTarget.style, variants.hover); }}
    onMouseLeave={(e) => { if (!disabled) { e.currentTarget.style.background = variants.background; e.currentTarget.style.color = variants.color; } }}
    >{icon}{children}{iconRight}</button>
  );
};

// ─────────────────────────────────────────────────────────────
// Progress Pill  ("p. 142 of 228" style)
// ─────────────────────────────────────────────────────────────

const ProgressPill = ({ page, total, variant = 'default', size = 'md' }) => {
  const pct = Math.min(100, Math.max(0, (page / total) * 100));
  const sizes = {
    sm: { h: 22, px: 9, fs: 11, trackH: 2 },
    md: { h: 28, px: 12, fs: 12, trackH: 3 },
    lg: { h: 34, px: 14, fs: 13, trackH: 3 },
  }[size];
  const isSoft = variant === 'soft';
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 8, height: sizes.h,
      padding: `0 ${sizes.px}px`, borderRadius: 'var(--r-pill)',
      background: isSoft ? 'var(--accent-softer)' : 'var(--paper-1)',
      color: isSoft ? 'var(--accent-ink)' : 'var(--ink-1)',
      fontFamily: 'var(--sans)', fontSize: sizes.fs, fontWeight: 500,
      fontVariantNumeric: 'tabular-nums', letterSpacing: 0.2,
    }}>
      <span style={{ opacity: 0.7 }}>p.</span>
      <span>{page}</span>
      <span style={{
        flexShrink: 0, width: 36, height: sizes.trackH, borderRadius: 999,
        background: isSoft ? 'color-mix(in oklab, var(--accent) 20%, transparent)' : 'var(--paper-3)',
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{ position: 'absolute', inset: 0, width: `${pct}%`,
          background: isSoft ? 'var(--accent)' : 'var(--ink-2)',
          transition: 'width var(--dur-slow) var(--ease-out)' }} />
      </span>
      <span style={{ opacity: 0.6 }}>of {total}</span>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Book Card
// ─────────────────────────────────────────────────────────────

const BookCover = ({ title, author, mood = 'sage', style }) => {
  // Generative cover — two-tone paper + wordmark. No art-slop.
  const moods = {
    sage:   { bg: 'oklch(78% 0.04 145)', ink: 'oklch(22% 0.03 145)' },
    amber:  { bg: 'oklch(82% 0.06 70)',  ink: 'oklch(26% 0.05 70)'  },
    slate:  { bg: 'oklch(74% 0.03 240)', ink: 'oklch(22% 0.03 240)' },
    rose:   { bg: 'oklch(80% 0.04 20)',  ink: 'oklch(24% 0.04 20)'  },
    charcoal:{bg: 'oklch(30% 0.01 50)',  ink: 'oklch(94% 0.01 70)'  },
    paper:  { bg: 'oklch(92% 0.01 70)',  ink: 'oklch(22% 0.02 70)'  },
  }[mood] || { bg: 'var(--paper-1)', ink: 'var(--ink-0)' };
  return (
    <div style={{
      position: 'relative', background: moods.bg, color: moods.ink,
      aspectRatio: '2 / 3', borderRadius: 'var(--r-xs)',
      padding: '18px 16px', display: 'flex', flexDirection: 'column',
      justifyContent: 'space-between',
      boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.06), 2px 2px 0 rgba(0,0,0,0.04)',
      overflow: 'hidden', ...style,
    }}>
      {/* hairline border inset — mimics a book plate */}
      <div style={{ position: 'absolute', inset: 8, border: '0.5px solid currentColor', opacity: 0.3, borderRadius: 1, pointerEvents: 'none' }} />
      <div style={{ fontFamily: 'var(--sans)', fontSize: 9, letterSpacing: 1.5, textTransform: 'uppercase', opacity: 0.65 }}>
        a novel
      </div>
      <div>
        <div style={{
          fontFamily: 'var(--serif)', fontWeight: 500, fontStyle: 'italic',
          fontSize: 19, lineHeight: 1.15, letterSpacing: -0.3, textWrap: 'balance',
        }}>{title}</div>
        <div style={{ marginTop: 10, fontFamily: 'var(--sans)', fontSize: 10, letterSpacing: 1.2, textTransform: 'uppercase', opacity: 0.75 }}>
          {author}
        </div>
      </div>
    </div>
  );
};

const BookCard = ({ title, author, page, total, mood, lastRead, onClick }) => {
  const pct = Math.round((page / total) * 100);
  return (
    <div onClick={onClick} style={{
      fontFamily: 'var(--sans)', cursor: 'pointer',
      transition: 'transform var(--dur) var(--ease)',
      width: 200,
    }}
    onMouseEnter={(e) => { e.currentTarget.querySelector('.bc-cover').style.transform = 'translateY(-2px)'; }}
    onMouseLeave={(e) => { e.currentTarget.querySelector('.bc-cover').style.transform = 'none'; }}
    >
      <div className="bc-cover" style={{ transition: 'transform var(--dur) var(--ease)' }}>
        <BookCover title={title} author={author} mood={mood} />
      </div>
      <div style={{ marginTop: 14 }}>
        <div style={{ fontFamily: 'var(--serif)', fontSize: 16, fontWeight: 500, color: 'var(--ink-0)', lineHeight: 1.25, letterSpacing: -0.2 }}>
          {title}
        </div>
        <div style={{ marginTop: 2, fontSize: 12, color: 'var(--ink-2)', letterSpacing: 0.1 }}>
          {author}
        </div>
        <Row gap={10} style={{ marginTop: 10 }}>
          <div style={{ flex: 1, height: 2, background: 'var(--paper-2)', borderRadius: 999, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${pct}%`, background: 'var(--accent)', transition: 'width var(--dur-slow) var(--ease-out)' }}/>
          </div>
          <div style={{ fontSize: 11, color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums', letterSpacing: 0.3 }}>
            {pct}%
          </div>
        </Row>
        {lastRead && <div style={{ marginTop: 6, fontSize: 11, color: 'var(--ink-3)' }}>{lastRead}</div>}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Chapter Row
// ─────────────────────────────────────────────────────────────

const ChapterRow = ({ num, title, pages, state = 'unread', current }) => {
  // state: 'read' | 'current' | 'unread' | 'locked'
  const isLocked = state === 'locked';
  const isCurrent = state === 'current' || current;
  const isRead = state === 'read';
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '42px 1fr auto auto',
      alignItems: 'center', gap: 14,
      padding: '14px 20px',
      borderBottom: 'var(--hairline)',
      fontFamily: 'var(--sans)',
      background: isCurrent ? 'var(--accent-softer)' : 'transparent',
      color: isLocked ? 'var(--ink-3)' : 'var(--ink-1)',
      cursor: isLocked ? 'not-allowed' : 'pointer',
      transition: 'background var(--dur) var(--ease)',
    }}
    onMouseEnter={(e) => { if (!isLocked && !isCurrent) e.currentTarget.style.background = 'var(--paper-1)'; }}
    onMouseLeave={(e) => { if (!isLocked && !isCurrent) e.currentTarget.style.background = 'transparent'; }}
    >
      <div style={{
        fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 14,
        color: isCurrent ? 'var(--accent)' : isLocked ? 'var(--ink-4)' : 'var(--ink-3)',
        fontVariantNumeric: 'tabular-nums', letterSpacing: 0.3,
      }}>
        {num.toString().padStart(2, '0')}
      </div>
      <div style={{
        fontFamily: 'var(--serif)', fontSize: 16, fontWeight: isCurrent ? 500 : 400,
        color: isLocked ? 'var(--ink-3)' : isRead ? 'var(--ink-2)' : 'var(--ink-0)',
        letterSpacing: -0.2,
      }}>
        {title}
      </div>
      <div style={{ fontSize: 12, color: 'var(--ink-3)', fontVariantNumeric: 'tabular-nums' }}>
        {pages}
      </div>
      <div style={{ width: 20, display: 'flex', justifyContent: 'flex-end' }}>
        {isCurrent && <span style={{ color: 'var(--accent)' }}><IcDot size={10}/></span>}
        {isRead && <span style={{ color: 'var(--ink-3)' }}><IcCheck size={13}/></span>}
        {isLocked && <span style={{ color: 'var(--ink-4)' }}><IcLock size={13}/></span>}
      </div>
    </div>
  );
};

Object.assign(window, {
  Stack, Row, Divider, Wordmark, NavBar, IconBtn, Button,
  ProgressPill, BookCover, BookCard, ChapterRow,
});
