// ─────────────────────────────────────────────────────────────
// Variations E + F
//   E · Focus mode with chapter tile strip (top edge dots)
//   F · Refined scroll — paper leaves with chapter breaks
// ─────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────
// Variation E · Focus mode
// Single page, very quiet. Subtle chapter tile strip peeks from top edge;
// on hover it expands. Discrete page count bottom-right. Big prose.
// ─────────────────────────────────────────────────────────────
const VarE_Focus = ({ tilesExpanded = false, showSelection = false }) => {
  return (
    <div style={{
      width: '100%', height: '100%', background: 'var(--paper-0)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      position: 'relative', fontFamily: 'var(--sans)',
    }}>
      {/* Chapter tile strip — collapsed by default, expanded on hover */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: 0,
        display: 'flex', justifyContent: 'center',
        padding: tilesExpanded ? '14px 20px 12px' : '10px 20px 8px',
        background: tilesExpanded ? 'color-mix(in oklab, var(--paper-00) 94%, transparent)' : 'transparent',
        backdropFilter: tilesExpanded ? 'saturate(140%) blur(8px)' : 'none',
        borderBottom: tilesExpanded ? '1px solid var(--paper-2)' : 'none',
        transition: 'all var(--dur-slow) var(--ease)',
        zIndex: 4,
      }}>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {CHAPTERS_V2.map((c, i) => {
            const done = i < 2;
            const cur = i === 2;
            return (
              <div key={c.n} style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                padding: tilesExpanded ? '8px 14px' : 0,
                borderRadius: 'var(--r-md)',
                background: tilesExpanded && cur ? 'var(--accent-softer)' : 'transparent',
                transition: 'all var(--dur-slow) var(--ease)',
                cursor: 'pointer', minWidth: tilesExpanded ? 110 : 'auto',
              }}>
                <div style={{
                  width: cur ? (tilesExpanded ? 'auto' : 22) : (tilesExpanded ? 'auto' : 6),
                  height: tilesExpanded ? 'auto' : 4,
                  background: tilesExpanded ? 'transparent' : (cur ? 'var(--accent)' : done ? 'var(--accent-soft)' : 'var(--paper-2)'),
                  borderRadius: 999,
                  transition: 'all var(--dur-slow) var(--ease)',
                }}>
                  {tilesExpanded && (
                    <>
                      <div style={{
                        fontFamily: 'var(--serif)', fontStyle: 'italic',
                        fontSize: 11, color: cur ? 'var(--accent-ink)' : 'var(--ink-3)',
                        letterSpacing: 0.4, textAlign: 'center',
                      }}>
                        Stave {ROMAN_V2[c.n]}
                      </div>
                      <div style={{
                        fontSize: 11, color: cur ? 'var(--accent-ink)' : 'var(--ink-2)',
                        fontWeight: cur ? 500 : 400, textAlign: 'center', marginTop: 2,
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 120,
                      }}>
                        {c.title.split(' ').slice(0, 3).join(' ')}
                      </div>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Page */}
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '60px 60px 60px' }}>
        <div style={{ width: 640, maxWidth: '100%' }}>
          <div style={{
            textAlign: 'center', marginBottom: 36,
          }}>
            <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 13, color: 'var(--ink-3)', letterSpacing: 0.5, marginBottom: 6 }}>
              Stave {ROMAN_V2[3]}
            </div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 24, color: 'var(--ink-0)', letterSpacing: -0.3 }}>
              The Second of the Three Spirits
            </div>
            <div style={{
              margin: '18px auto 0', width: 36, height: 1,
              background: 'var(--paper-3)',
            }}/>
          </div>
          <div style={{
            fontFamily: 'var(--serif)', fontSize: 18, lineHeight: 1.8,
            color: 'var(--ink-0)', textAlign: 'justify', hyphens: 'auto',
          }}>
            <p style={{ margin: '0 0 20px' }} className="dropcap">{PROSE_V2[3][0]}</p>
            <p style={{ margin: '0 0 20px' }}>
              {showSelection ? (
                <>
                  {PROSE_V2[3][1].slice(0, 180)}
                  <Selection>{PROSE_V2[3][1].slice(180, 280)}</Selection>
                  {PROSE_V2[3][1].slice(280)}
                </>
              ) : PROSE_V2[3][1]}
            </p>
          </div>
          {showSelection && <SelectionToolbar x={300} y={405} visible/>}
        </div>
      </div>

      {/* discreet page number, bottom right */}
      <div style={{
        position: 'absolute', right: 24, bottom: 20,
        fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-3)',
      }}>
        96 · 54%
      </div>
      {/* discreet book title, bottom left */}
      <div style={{
        position: 'absolute', left: 24, bottom: 20,
        fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 11, color: 'var(--ink-3)',
      }}>
        Dickens · A Christmas Carol
      </div>

      {/* invisible left/right click zones — visual cue */}
      <div style={{
        position: 'absolute', left: 0, top: 52, bottom: 52, width: 80,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--ink-4)', pointerEvents: 'none', opacity: .4,
      }}><IcArrowL size={16}/></div>
      <div style={{
        position: 'absolute', right: 0, top: 52, bottom: 52, width: 80,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--ink-4)', pointerEvents: 'none', opacity: .4,
      }}><IcArrowR size={16}/></div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Variation F · Refined scroll
// Scroll, but chunked into chapter "leaves" (paper cards with gaps).
// Sticky thin top bar with progress. Inside each leaf: drop cap,
// centered chapter title, body.
// ─────────────────────────────────────────────────────────────
const VarF_Scroll = () => {
  return (
    <div style={{
      width: '100%', height: '100%', background: 'var(--paper-1)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      fontFamily: 'var(--sans)', position: 'relative',
    }}>
      {/* Sticky top bar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 5,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 28px', background: 'color-mix(in oklab, var(--paper-1) 92%, transparent)',
        backdropFilter: 'saturate(140%) blur(10px)',
        borderBottom: '1px solid var(--paper-2)',
        height: 52, boxSizing: 'border-box',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ color: 'var(--ink-2)', cursor: 'pointer' }}>
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M2 4h12M2 8h12M2 12h12"/></svg>
          </div>
          <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 14, color: 'var(--ink-0)' }}>
            A Christmas Carol
          </div>
          <div style={{ fontSize: 11, color: 'var(--ink-3)' }}>· Stave III, ¶6</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'var(--ink-2)' }}>
          <MiniBar pct={54} w={140} h={3}/>
          <span style={{ fontFamily: 'var(--mono)' }}>54%</span>
          <div style={{ display: 'flex', gap: 4, marginLeft: 8 }}>
            <div style={{ padding: 6, cursor: 'pointer' }}><IcSearch size={13}/></div>
            <div style={{ padding: 6, cursor: 'pointer' }}><IcBookmark size={13}/></div>
            <div style={{ padding: 6, cursor: 'pointer' }}><IcSettings size={13}/></div>
          </div>
        </div>
      </div>

      {/* Scrollable stage */}
      <div style={{
        flex: 1, overflow: 'auto',
        background: 'linear-gradient(to bottom, var(--paper-1), color-mix(in oklab, var(--paper-1) 85%, var(--paper-2)))',
        padding: '28px 0 80px',
      }}>
        {/* Leaf: Stave II (tail, just a reminder) */}
        <Leaf>
          <div style={{ textAlign: 'center', marginBottom: 20 }}>
            <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 12, color: 'var(--ink-3)', letterSpacing: 0.4 }}>
              End of Stave II
            </div>
            <div style={{ margin: '14px auto 0', color: 'var(--ink-3)', letterSpacing: '8px', fontSize: 10 }}>
              · · ·
            </div>
          </div>
          <div style={leafProse()}>
            <p style={{ margin: '0 0 14px' }}>{PROSE_V2[2][2].slice(0, 180)}…</p>
          </div>
        </Leaf>

        {/* Chapter break */}
        <ChapterBreak n={3} title="The Second of the Three Spirits"/>

        {/* Leaf: Stave III */}
        <Leaf>
          <div style={leafProse()}>
            <p style={{ margin: '0 0 16px' }} className="dropcap">{PROSE_V2[3][0]}</p>
            <p style={{ margin: '0 0 16px' }}>{PROSE_V2[3][1]}</p>
            <p style={{ margin: '0 0 16px' }}>{PROSE_V2[3][2]}</p>
            <p style={{ margin: '0 0 16px' }}>{PROSE_V2[3][3]}</p>
            <p style={{ margin: '0 0 16px' }}>{PROSE_V2[3][4]}</p>
          </div>
        </Leaf>

        {/* Cutoff bar and fog */}
        <div style={{
          maxWidth: 720, margin: '8px auto', padding: '0 28px',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 14px',
            background: 'var(--paper-00)',
            border: '1px dashed var(--paper-3)',
            borderRadius: 999,
            fontSize: 11.5, color: 'var(--ink-2)',
          }}>
            <IcLock size={12}/>
            <span>Reading up to <em style={{ fontFamily: 'var(--serif)', color: 'var(--ink-1)' }}>"rust"</em></span>
            <span style={{ color: 'var(--ink-4)' }}>·</span>
            <span style={{ fontFamily: 'var(--mono)' }}>Stave III · 54%</span>
            <span style={{ marginLeft: 'auto', color: 'var(--accent-ink)', cursor: 'pointer', fontSize: 11 }}>Update</span>
          </div>
        </div>

        {/* Leaf: fogged continuation */}
        <Leaf fogged>
          <div style={leafProse()}>
            <p style={{ margin: '0 0 16px', filter: 'blur(3px)', opacity: .7, userSelect: 'none' }}>{PROSE_V2[3][5]}</p>
            <p style={{ margin: '0 0 16px', filter: 'blur(4px)', opacity: .6, userSelect: 'none' }}>{PROSE_V2[3][6]}</p>
            <p style={{ margin: '0 0 16px', filter: 'blur(5px)', opacity: .5, userSelect: 'none' }}>{PROSE_V2[3][7]}</p>
          </div>
        </Leaf>
      </div>
    </div>
  );
};

const Leaf = ({ children, fogged = false }) => (
  <div style={{
    maxWidth: 720, margin: '0 auto 14px', padding: '48px 60px 40px',
    background: 'var(--paper-00)',
    boxShadow: '0 1px 0 color-mix(in oklab, var(--paper-2) 60%, transparent), 0 10px 28px -14px rgba(28,24,18,.12), 0 2px 4px rgba(28,24,18,.04)',
    borderRadius: 4,
    position: 'relative',
    opacity: fogged ? 0.92 : 1,
  }}>
    {children}
  </div>
);
const leafProse = () => ({
  fontFamily: 'var(--serif)', fontSize: 16.5, lineHeight: 1.75,
  color: 'var(--ink-0)', textAlign: 'justify', hyphens: 'auto',
});

const ChapterBreak = ({ n, title }) => (
  <div style={{
    maxWidth: 720, margin: '28px auto 20px', padding: '0 60px',
    display: 'flex', flexDirection: 'column', alignItems: 'center',
  }}>
    <div style={{
      fontFamily: 'var(--sans)', fontSize: 10, letterSpacing: 2,
      textTransform: 'uppercase', color: 'var(--ink-3)', marginBottom: 8,
    }}>
      Stave {ROMAN_V2[n]}
    </div>
    <div style={{
      fontFamily: 'var(--serif)', fontSize: 26, color: 'var(--ink-0)',
      letterSpacing: -0.3, textAlign: 'center',
    }}>
      {title}
    </div>
    <div style={{ margin: '14px 0 0', color: 'var(--ink-3)', letterSpacing: 6, fontSize: 11 }}>
      · · ·
    </div>
  </div>
);

Object.assign(window, { VarE_Focus, VarF_Scroll });
