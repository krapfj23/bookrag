// ─────────────────────────────────────────────────────────────
// Variations C + D
//   C · Columnar (responsive 2-column on wide viewports, reflowing)
//   D · Editorial spread with marginalia rail (RAG in the margin)
// ─────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────
// Variation C · Columnar reader
// Two text columns that flow left→right, with a persistent minimal
// top bar and a chapter scrubber along the bottom.
// ─────────────────────────────────────────────────────────────
const VarC_Columns = ({ showFog = false }) => {
  return (
    <div style={{
      width: '100%', height: '100%', background: 'var(--paper-0)',
      display: 'flex', flexDirection: 'column', fontFamily: 'var(--sans)', overflow: 'hidden',
    }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 28px', height: 52, boxSizing: 'border-box',
        borderBottom: '1px solid var(--paper-2)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ color: 'var(--ink-2)', cursor: 'pointer' }}>
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M2 4h12M2 8h12M2 12h12"/></svg>
          </div>
          <div>
            <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 14, color: 'var(--ink-0)', lineHeight: 1 }}>A Christmas Carol</div>
            <div style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 2 }}>Charles Dickens · Stave III</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 11, color: 'var(--ink-2)' }}>
          <span style={{ fontFamily: 'var(--mono)' }}>p. 96–97 / 176</span>
          <div style={{ display: 'flex', gap: 4, color: 'var(--ink-3)' }}>
            <div style={{ padding: 6, cursor: 'pointer' }}><IcSearch size={14}/></div>
            <div style={{ padding: 6, cursor: 'pointer' }}><IcBookmark size={14}/></div>
            <div style={{ padding: 6, cursor: 'pointer' }}><IcSettings size={14}/></div>
          </div>
        </div>
      </div>

      {/* Columns */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'stretch', position: 'relative' }}>
        <button style={{ ...colArrow, left: 8 }}><IcArrowL size={18}/></button>
        <div style={{
          flex: 1, padding: '40px 80px 40px',
          columnCount: 2, columnGap: 64, columnRule: '1px solid var(--paper-2)',
          fontFamily: 'var(--serif)', fontSize: 15, lineHeight: 1.7,
          color: 'var(--ink-0)', textAlign: 'justify', hyphens: 'auto',
          overflow: 'hidden',
        }}>
          <div style={{ ...pageChap(), marginBottom: 6, breakAfter: 'avoid' }}>Stave III</div>
          <h2 style={{ ...pageHead(), fontSize: 20, marginTop: 0, marginBottom: 18, breakAfter: 'avoid' }}>
            The Second of the Three Spirits
          </h2>
          <p style={{ margin: '0 0 14px' }} className="dropcap">{PROSE_V2[3][0]}</p>
          <p style={{ margin: '0 0 14px' }}>{PROSE_V2[3][1]}</p>
          <p style={{ margin: '0 0 14px' }}>{PROSE_V2[3][2]}</p>
          <p style={{ margin: '0 0 14px' }}>{PROSE_V2[3][3]}</p>
          <p style={{ margin: '0 0 14px' }}>{PROSE_V2[3][4]}</p>
          {showFog ? (
            <p style={{ margin: '0 0 14px', filter: 'blur(4px)', opacity: .7, userSelect: 'none' }}>{PROSE_V2[3][5]}</p>
          ) : (
            <p style={{ margin: '0 0 14px' }}>{PROSE_V2[3][5]}</p>
          )}
        </div>
        <button style={{ ...colArrow, right: 8 }}><IcArrowR size={18}/></button>
      </div>

      {/* Chapter scrubber */}
      <div style={{
        borderTop: '1px solid var(--paper-2)',
        padding: '12px 28px 14px', background: 'var(--paper-00)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 10.5, letterSpacing: 1.2, textTransform: 'uppercase', color: 'var(--ink-3)', minWidth: 70 }}>
            54% read
          </span>
          <div style={{ flex: 1, position: 'relative', height: 20, display: 'flex', alignItems: 'center' }}>
            {/* chapter segments */}
            <div style={{ width: '100%', height: 4, background: 'var(--paper-1)', borderRadius: 999, position: 'relative', display: 'flex' }}>
              {CHAPTERS_V2.map((c, i) => {
                // widths approx: 25, 23, 24, 20, 8
                const w = [25, 23, 24, 20, 8][i];
                const done = i < 2;
                const cur = i === 2;
                return (
                  <div key={c.n} style={{
                    flex: `${w} 0 0`, height: '100%',
                    background: done ? 'var(--accent)' : cur ? `linear-gradient(to right, var(--accent) 30%, var(--paper-1) 30%)` : 'var(--paper-1)',
                    borderRight: i < 4 ? '2px solid var(--paper-0)' : 'none',
                  }}/>
                );
              })}
              {/* scrubber head */}
              <div style={{
                position: 'absolute', left: 'calc(25% + 23% + 24% * 0.3)', top: '50%',
                transform: 'translate(-50%, -50%)', width: 12, height: 12, borderRadius: 999,
                background: 'var(--paper-00)', border: '2px solid var(--accent)',
                boxShadow: '0 2px 6px rgba(28,24,18,.18)',
              }}/>
            </div>
          </div>
          <span style={{ fontSize: 10.5, color: 'var(--ink-3)', fontFamily: 'var(--mono)', minWidth: 120, textAlign: 'right' }}>
            15 min left in Stave
          </span>
        </div>
        {/* chapter labels */}
        <div style={{ display: 'flex', marginTop: 6, fontSize: 10, color: 'var(--ink-3)', fontFamily: 'var(--sans)', paddingLeft: 86, paddingRight: 136 }}>
          {CHAPTERS_V2.map((c, i) => {
            const w = [25, 23, 24, 20, 8][i];
            return (
              <div key={c.n} style={{ flex: `${w} 0 0`, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 8 }}>
                <span style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', marginRight: 4, color: i === 2 ? 'var(--accent-ink)' : undefined }}>{ROMAN_V2[c.n]}.</span>
                {c.title.split(' ').slice(0, 3).join(' ')}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

const colArrow = {
  position: 'absolute', top: '50%', transform: 'translateY(-50%)',
  width: 40, height: 40, borderRadius: 999,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  color: 'var(--ink-3)', cursor: 'pointer', background: 'var(--paper-00)',
  border: '1px solid var(--paper-2)',
};

// ─────────────────────────────────────────────────────────────
// Variation D · Editorial spread with marginalia rail
// Two-page spread with narrow outer rails where RAG highlights,
// entity links, and user notes appear inline beside the text they
// reference — like a printed book's marginalia.
// ─────────────────────────────────────────────────────────────
const VarD_Marginalia = () => {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'radial-gradient(ellipse at center 30%, color-mix(in oklab, var(--paper-0) 92%, var(--paper-1)), var(--paper-0) 70%), var(--paper-0)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      fontFamily: 'var(--sans)',
    }}>
      {/* Top */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr auto 1fr',
        alignItems: 'center', padding: '14px 28px', height: 52, boxSizing: 'border-box',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--ink-2)', fontSize: 12 }}>
          <IcArrowL size={13}/> Library
        </div>
        <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 14, color: 'var(--ink-1)' }}>
          A Christmas Carol · <span style={{ color: 'var(--ink-3)', fontStyle: 'normal' }}>Dickens</span>
        </div>
        <div style={{ justifySelf: 'end', display: 'flex', gap: 10, color: 'var(--ink-2)' }}>
          <IcSearch size={13}/><IcBookmark size={13}/><IcSettings size={13}/>
        </div>
      </div>

      {/* Stage */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 24px', position: 'relative' }}>
        <button style={arrowStyleD('left')}><IcArrowL size={20}/></button>

        <div style={{
          position: 'relative',
          width: 1320, height: 720, maxHeight: 'calc(100vh - 160px)',
          display: 'grid', gridTemplateColumns: '180px 1fr 1fr 180px',
          background: 'var(--paper-00)',
          boxShadow: '0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)',
          borderRadius: 3,
        }}>
          {/* LEFT MARGIN RAIL */}
          <div style={marginalRail('left')}>
            <MarginNote
              kind="highlight"
              text="Marley: 7 years dead, still haunts Scrooge's door-plate."
              linkTarget="Jacob Marley"
            />
            <MarginNote
              kind="ask"
              text="Why a door-nail, specifically?"
              answered
            />
          </div>

          {/* LEFT PAGE */}
          <div style={{ ...pageStyleD(), borderRight: '0' }}>
            <div style={pageChap()}>Stave I</div>
            <div style={pageHead()}>Marley's Ghost</div>
            <div style={proseStyleD()}>
              <p style={{ margin: '0 0 14px' }} className="dropcap">
                {PROSE_V2[1][0].replace('Scrooge signed it.', '')}
                <span style={{ background: 'var(--accent-soft)', color: 'var(--accent-ink)', padding: '1px 0' }}>Scrooge signed it.</span>
                {' And Scrooge\'s name was good upon \'Change for anything he chose to put his hand to.'}
              </p>
              <p style={{ margin: '0 0 14px' }}>
                Old Marley was as dead as a <span style={{ textDecoration: 'underline', textDecorationStyle: 'dotted', textDecorationColor: 'var(--accent)', textUnderlineOffset: 3 }}>door-nail</span>. Mind! I don't mean to say that I know, of my own knowledge, what there is particularly dead about a door-nail.
              </p>
              <p style={{ margin: '0 0 14px' }}>{PROSE_V2[1][2]}</p>
            </div>
            <div style={folioStyle()}>
              <span>Charles Dickens</span>
              <span style={{ fontFamily: 'var(--mono)' }}>2</span>
            </div>
          </div>

          {/* gutter */}
          <div style={{
            position: 'absolute', left: 'calc(180px + (100% - 360px) / 2)', top: 0, bottom: 0, width: 30,
            transform: 'translateX(-50%)', pointerEvents: 'none',
            background: 'linear-gradient(to right, transparent 0%, color-mix(in oklab, var(--ink-0) 7%, transparent) 50%, transparent 100%)',
          }}/>

          {/* RIGHT PAGE */}
          <div style={pageStyleD()}>
            <div style={proseStyleD()}>
              <p style={{ margin: '0 0 14px' }}>
                {PROSE_V2[1][3].slice(0, 140)}
                <span style={{ borderBottom: '1.5px solid oklch(58% 0.1 55)', paddingBottom: 1 }}>sole mourner</span>
                {PROSE_V2[1][3].slice(140 + 'sole mourner'.length)}
              </p>
              <p style={{ margin: '0 0 14px', filter: 'blur(3px)', opacity: .7, userSelect: 'none' }}>
                {PROSE_V2[1][4]}
              </p>
            </div>
            <div style={folioStyle()}>
              <span style={{ fontFamily: 'var(--mono)' }}>3</span>
              <span>Marley's Ghost</span>
            </div>
          </div>

          {/* RIGHT MARGIN RAIL */}
          <div style={marginalRail('right')}>
            <MarginNote
              kind="note"
              text="Pencil cutoff here. Spoiler fog starts at 'sole mourner'."
              self
            />
            <MarginNote
              kind="entity"
              text="Ebenezer Scrooge"
              subtitle="5 mentions · up to here"
            />
          </div>
        </div>

        <button style={arrowStyleD('right')}><IcArrowR size={20}/></button>
      </div>

      {/* Bottom */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center',
        padding: '14px 32px 18px', height: 56, boxSizing: 'border-box', fontSize: 11, color: 'var(--ink-3)',
      }}>
        <span>3 margin marks on this spread</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ProgressDots current={1} total={5}/>
          <span style={{ fontFamily: 'var(--mono)' }}>3%</span>
        </div>
        <span style={{ justifySelf: 'end', fontFamily: 'var(--mono)' }}>p. 2–3 / 176</span>
      </div>
    </div>
  );
};

const pageStyleD = () => ({
  padding: '56px 44px 44px',
  display: 'flex', flexDirection: 'column',
});
const proseStyleD = () => ({
  fontFamily: 'var(--serif)', fontSize: 15, lineHeight: 1.72,
  color: 'var(--ink-0)', textAlign: 'justify', hyphens: 'auto', flex: 1,
});
const arrowStyleD = (side) => ({
  position: 'absolute', top: '50%', transform: 'translateY(-50%)',
  [side]: 10,
  width: 42, height: 42, borderRadius: 999,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  color: 'var(--ink-2)', cursor: 'pointer', background: 'transparent', border: 0,
});
const marginalRail = (side) => ({
  padding: side === 'left' ? '56px 16px 44px 20px' : '56px 20px 44px 16px',
  display: 'flex', flexDirection: 'column', gap: 14,
  fontFamily: 'var(--sans)',
  borderRight: side === 'left' ? 'none' : 'none',
  position: 'relative',
});

const MarginNote = ({ kind, text, subtitle, linkTarget, answered, self }) => {
  const colors = {
    highlight: { bar: 'var(--accent)', label: 'HIGHLIGHT' },
    ask:       { bar: 'oklch(65% 0.08 65)', label: answered ? 'ASKED · ANSWERED' : 'ASKED' },
    note:      { bar: 'oklch(58% 0.1 55)', label: 'NOTE' },
    entity:    { bar: 'var(--ink-2)', label: 'ENTITY' },
  };
  const c = colors[kind] || colors.note;
  return (
    <div style={{
      position: 'relative', paddingLeft: 10,
      borderLeft: `2px solid ${c.bar}`,
    }}>
      <div style={{ fontSize: 9, letterSpacing: 1.2, color: 'var(--ink-3)', marginBottom: 3, fontWeight: 500 }}>{c.label}</div>
      <div style={{
        fontFamily: kind === 'note' ? 'var(--serif)' : 'var(--sans)',
        fontStyle: kind === 'note' ? 'italic' : 'normal',
        fontSize: kind === 'entity' ? 12.5 : 11.5,
        fontWeight: kind === 'entity' ? 500 : 400,
        lineHeight: 1.45, color: 'var(--ink-1)',
      }}>
        {kind === 'ask' && <span style={{ color: 'var(--ink-3)', marginRight: 3 }}>Q:</span>}
        {text}
      </div>
      {subtitle && <div style={{ fontSize: 10, color: 'var(--ink-3)', marginTop: 2 }}>{subtitle}</div>}
      {linkTarget && (
        <div style={{ fontSize: 10, color: 'var(--accent-ink)', marginTop: 3 }}>
          → {linkTarget}
        </div>
      )}
    </div>
  );
};

Object.assign(window, { VarC_Columns, VarD_Marginalia, MarginNote });
