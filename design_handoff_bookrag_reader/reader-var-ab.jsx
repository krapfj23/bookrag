// ─────────────────────────────────────────────────────────────
// Variations A + B
//   A · Two-page spread (book object)   — Kindle-ish but bookish
//   B · Single-page immersive           — chrome fully hides
// Both share the fog-of-war cutoff metaphor from Bookrag.
// ─────────────────────────────────────────────────────────────

// Helper — renders a column of prose paragraphs, optionally clipping at
// `maxParas` for page-fitting. Pure presentational.
const ProseColumn = ({ chNum, paras, first = 0, count = 4, dropCap = false, showCutoff = false, fogFrom = null, showSelection = false }) => {
  const src = paras.slice(first, first + count);
  return (
    <div style={{
      fontFamily: 'var(--serif)', fontSize: 16, lineHeight: 1.72, color: 'var(--ink-0)',
      textAlign: 'justify', hyphens: 'auto',
    }}>
      {src.map((p, i) => {
        const isFogStart = fogFrom && i === fogFrom.para;
        const isFogged   = fogFrom && i > fogFrom.para;
        const showFirstCap = dropCap && i === 0 && first === 0;
        if (isFogged) {
          return (
            <p key={i} style={{ margin: '0 0 14px', filter: `blur(${3 + (i - fogFrom.para) * 1.4}px)`, opacity: .7, userSelect: 'none' }}>
              {p}
            </p>
          );
        }
        if (isFogStart) {
          // split paragraph at cutoff sentence
          const cutIdx = p.indexOf('rust');
          const pre = cutIdx > -1 ? p.slice(0, cutIdx) : p.slice(0, Math.floor(p.length * 0.55));
          const cut = cutIdx > -1 ? 'rust' : p.slice(Math.floor(p.length * 0.55), Math.floor(p.length * 0.6));
          const post = cutIdx > -1 ? p.slice(cutIdx + 4) : p.slice(Math.floor(p.length * 0.6));
          return (
            <p key={i} style={{ margin: '0 0 14px' }}>
              {pre}
              <span style={{
                borderBottom: '1.5px solid oklch(58% 0.1 55)', paddingBottom: 1,
              }}>{cut}</span>
              <span style={{ filter: 'blur(2.5px)', opacity: .75, userSelect: 'none' }}>{post}</span>
            </p>
          );
        }
        if (showFirstCap) {
          return (
            <p key={i} style={{ margin: '0 0 14px' }} className="dropcap">
              {p}
            </p>
          );
        }
        if (showSelection && i === 1) {
          // render paragraph with a Selection wrapping a clause
          const mid = Math.floor(p.length * 0.35);
          const end = Math.floor(p.length * 0.55);
          return (
            <p key={i} style={{ margin: '0 0 14px' }}>
              {p.slice(0, mid)}
              <Selection>{p.slice(mid, end)}</Selection>
              {p.slice(end)}
            </p>
          );
        }
        if (showCutoff && i === src.length - 1 && chNum === 3) {
          // put a cutoff pencil mark on the last visible word
          const last = p.lastIndexOf(' ');
          return (
            <p key={i} style={{ margin: '0 0 14px' }}>
              {p.slice(0, last + 1)}
              <span style={{
                borderBottom: '1.5px solid oklch(58% 0.1 55)', paddingBottom: 1,
              }}>{p.slice(last + 1).replace('.', '')}</span>.
            </p>
          );
        }
        return <p key={i} style={{ margin: '0 0 14px' }}>{p}</p>;
      })}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Variation A · Two-page spread (book-as-object)
// Centered spread, gutter shadow down the middle, arrows outside.
// Chrome: thin title bar + thin footer with dots + percent.
// ─────────────────────────────────────────────────────────────
const VarA_Spread = ({ showSelection = false, showFog = false, showHover = false }) => {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'radial-gradient(ellipse at center 30%, color-mix(in oklab, var(--paper-0) 90%, var(--paper-1)), var(--paper-0) 70%), var(--paper-0)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      fontFamily: 'var(--sans)',
    }}>
      {/* Top chrome */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center',
        padding: '14px 28px', height: 52, boxSizing: 'border-box',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--ink-2)' }}>
          <IcLibrary size={14}/>
          <span style={{ fontSize: 12, letterSpacing: 0.2 }}>Library</span>
        </div>
        <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 14, color: 'var(--ink-1)', letterSpacing: 0.1 }}>
          A Christmas Carol · <span style={{ color: 'var(--ink-3)', fontStyle: 'normal' }}>Dickens</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, alignItems: 'center', color: 'var(--ink-2)' }}>
          <div style={{ display: 'inline-flex', padding: 6, borderRadius: 'var(--r-sm)', cursor: 'pointer' }}><IcSearch size={13}/></div>
          <div style={{ display: 'inline-flex', padding: 6, borderRadius: 'var(--r-sm)', cursor: 'pointer' }}><IcBookmark size={13}/></div>
          <div style={{ display: 'inline-flex', padding: 6, borderRadius: 'var(--r-sm)', cursor: 'pointer' }}><IcSettings size={13}/></div>
        </div>
      </div>

      {/* Stage with book spread */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', padding: '0 32px' }}>
        {/* left arrow */}
        <button style={arrowStyle('left')}>
          <IcArrowL size={20}/>
        </button>

        {/* The spread */}
        <div style={{
          position: 'relative',
          width: 1080, height: 700, maxHeight: 'calc(100vh - 160px)',
          display: 'grid', gridTemplateColumns: '1fr 1fr',
          background: 'var(--paper-00)',
          boxShadow: '0 1px 0 color-mix(in oklab, var(--paper-2) 70%, transparent), 0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)',
          borderRadius: 3,
        }}>
          {/* left page */}
          <div style={pageStyle()}>
            <div style={pageChap()}>Stave III</div>
            <div style={pageHead()}>The Second of the Three Spirits</div>
            <ProseColumn
              chNum={3}
              paras={PROSE_V2[3]}
              first={0} count={3}
              dropCap
              showSelection={showSelection}
            />
            <div style={folioStyle()}>
              <span>Charles Dickens</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10 }}>96</span>
            </div>
          </div>

          {/* gutter shadow */}
          <div style={{
            position: 'absolute', left: '50%', top: 0, bottom: 0, width: 40,
            transform: 'translateX(-50%)', pointerEvents: 'none',
            background: 'linear-gradient(to right, transparent 0%, color-mix(in oklab, var(--ink-0) 6%, transparent) 45%, color-mix(in oklab, var(--ink-0) 9%, transparent) 50%, color-mix(in oklab, var(--ink-0) 6%, transparent) 55%, transparent 100%)',
          }}/>

          {/* right page */}
          <div style={pageStyle()}>
            <ProseColumn
              chNum={3}
              paras={PROSE_V2[3]}
              first={3} count={4}
              fogFrom={showFog ? { para: 2 } : null}
              showCutoff={!showFog}
            />
            <div style={folioStyle()}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10 }}>97</span>
              <span>The Second of the Three Spirits</span>
            </div>
          </div>

          {/* Floating selection toolbar */}
          {showSelection && (
            <SelectionToolbar x={270} y={340} visible/>
          )}
        </div>

        {/* right arrow */}
        <button style={arrowStyle('right')}>
          <IcArrowR size={20}/>
        </button>
      </div>

      {/* Bottom chrome */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center',
        padding: '16px 32px 20px', height: 60, boxSizing: 'border-box',
      }}>
        <div style={{ fontSize: 11, color: 'var(--ink-3)', letterSpacing: 0.3, display: 'flex', alignItems: 'center', gap: 8 }}>
          <IcLock size={11}/> Reading up to <em style={{ fontFamily: 'var(--serif)', color: 'var(--ink-1)' }}>"rust"</em>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <ProgressDots current={3} total={5}/>
          <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-3)' }}>54%</span>
        </div>
        <div style={{ justifySelf: 'end', fontSize: 11, color: 'var(--ink-3)', fontFamily: 'var(--mono)' }}>
          p. 96–97 / 176
        </div>
      </div>
    </div>
  );
};

const arrowStyle = (side) => ({
  position: 'absolute', top: '50%', transform: 'translateY(-50%)',
  [side]: 18,
  width: 44, height: 44, borderRadius: 999,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  color: 'var(--ink-2)', cursor: 'pointer', background: 'transparent', border: 0,
  transition: 'background var(--dur) var(--ease)',
});
const pageStyle = () => ({
  padding: '64px 60px 52px',
  display: 'flex', flexDirection: 'column',
});
const pageChap = () => ({
  fontFamily: 'var(--serif)', fontStyle: 'italic',
  fontSize: 12, color: 'var(--ink-3)', letterSpacing: 0.4, marginBottom: 6,
});
const pageHead = () => ({
  fontFamily: 'var(--serif)', fontWeight: 400,
  fontSize: 22, letterSpacing: -0.3, color: 'var(--ink-0)',
  margin: '0 0 22px',
});
const folioStyle = () => ({
  marginTop: 'auto', paddingTop: 16,
  display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
  fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 11,
  color: 'var(--ink-3)', letterSpacing: 0.3,
});

// ─────────────────────────────────────────────────────────────
// Variation B · Single-page immersive
// Big margins, chrome fully auto-hides. Only a thin accent hairline
// at bottom for chapter progress. Click left/right edges.
// ─────────────────────────────────────────────────────────────
const VarB_Immersive = ({ chromeVisible = false, showSelection = false }) => {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'var(--paper-0)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      position: 'relative', fontFamily: 'var(--sans)',
    }}>
      {/* Edge click zones (visual hint only when chromeVisible) */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 120,
        display: 'flex', alignItems: 'center', justifyContent: 'flex-start', paddingLeft: 24,
        color: chromeVisible ? 'var(--ink-3)' : 'transparent',
        transition: 'color var(--dur)',
        pointerEvents: 'none',
      }}><IcArrowL size={18}/></div>
      <div style={{
        position: 'absolute', right: 0, top: 0, bottom: 0, width: 120,
        display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: 24,
        color: chromeVisible ? 'var(--ink-3)' : 'transparent',
        transition: 'color var(--dur)',
        pointerEvents: 'none',
      }}><IcArrowR size={18}/></div>

      {/* Top chrome (auto-hide) */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: 0, height: 52,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 28px',
        opacity: chromeVisible ? 1 : 0, transform: chromeVisible ? 'none' : 'translateY(-8px)',
        transition: 'all var(--dur-slow) var(--ease)',
        background: chromeVisible ? 'color-mix(in oklab, var(--paper-0) 90%, transparent)' : 'transparent',
        backdropFilter: chromeVisible ? 'saturate(140%) blur(10px)' : 'none',
        zIndex: 3,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--ink-2)', fontSize: 12 }}>
          <IcArrowL size={13}/> Library
        </div>
        <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 13, color: 'var(--ink-1)' }}>
          A Christmas Carol
        </div>
        <div style={{ display: 'flex', gap: 10, color: 'var(--ink-2)' }}>
          <IcSearch size={13}/><IcBookmark size={13}/><IcSettings size={13}/>
        </div>
      </div>

      {/* Page */}
      <div style={{
        flex: 1, display: 'flex', justifyContent: 'center',
        padding: '80px 60px 80px',
        overflow: 'hidden',
      }}>
        <div style={{
          width: 620, maxWidth: '100%',
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ ...pageChap(), marginBottom: 4 }}>Stave III — continued</div>
          <div style={{ ...pageHead(), fontSize: 20, marginBottom: 28 }}>The Second of the Three Spirits</div>

          <div style={{ fontFamily: 'var(--serif)', fontSize: 18, lineHeight: 1.78, color: 'var(--ink-0)', textAlign: 'justify', hyphens: 'auto' }}>
            <p style={{ margin: '0 0 18px' }} className="dropcap">{PROSE_V2[3][4]}</p>
            <p style={{ margin: '0 0 18px' }}>
              {PROSE_V2[3][5].slice(0, 180)}
              {showSelection ? <Selection>{PROSE_V2[3][5].slice(180, 260)}</Selection> : PROSE_V2[3][5].slice(180, 260)}
              {PROSE_V2[3][5].slice(260)}
            </p>
            <p style={{ margin: '0 0 18px' }}>{PROSE_V2[3][6]}</p>
          </div>

          {showSelection && <SelectionToolbar x={260} y={370} visible/>}
        </div>
      </div>

      {/* Bottom chrome (auto-hide — but thin progress hairline persists) */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0,
        display: 'flex', flexDirection: 'column',
      }}>
        {/* Bottom chrome block */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '0 32px', height: 48,
          opacity: chromeVisible ? 1 : 0, transform: chromeVisible ? 'none' : 'translateY(8px)',
          transition: 'all var(--dur-slow) var(--ease)',
          fontSize: 11, color: 'var(--ink-3)',
        }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <IcLock size={11}/> Reading up to <em style={{ fontFamily: 'var(--serif)', color: 'var(--ink-1)' }}>"rust"</em>
          </span>
          <span style={{ fontFamily: 'var(--mono)' }}>Stave III · p. 97 / 176 · 54%</span>
        </div>
        {/* Persistent thin progress hairline (bottom edge) */}
        <div style={{ height: 2, background: 'var(--paper-2)', position: 'relative' }}>
          <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '54%', background: 'var(--accent)' }}/>
        </div>
      </div>
    </div>
  );
};

Object.assign(window, { VarA_Spread, VarB_Immersive, ProseColumn });
