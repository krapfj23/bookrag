// ─────────────────────────────────────────────────────────────
// Variation D+ : Marginalia spread — with chat & page-turn flows
// Explores:
//   1. Chat interface (right panel slides in, replaces margin rail)
//   2. Chat bubble anchored to a margin note (inline thread)
//   3. Page turn — mid-flip state (subtle paper slide)
//   4. Chapter boundary flip
// ─────────────────────────────────────────────────────────────

// Minimal chat bubble components local to this variation
const ChatMsgUser = ({ children, pageRef }) => (
  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 14 }}>
    <div style={{
      maxWidth: '85%', padding: '10px 14px',
      background: 'var(--accent-soft)', color: 'var(--accent-ink)',
      borderRadius: 'var(--r-lg)', borderBottomRightRadius: 4,
      fontFamily: 'var(--serif)', fontSize: 14, lineHeight: 1.55,
    }}>
      {pageRef && (
        <div style={{
          fontFamily: 'var(--sans)', fontSize: 10, letterSpacing: 0.6,
          textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 4,
          display: 'flex', alignItems: 'center', gap: 5,
        }}>
          <span style={{ width: 3, height: 3, borderRadius: 999, background: 'var(--accent)' }}/>
          from p. {pageRef}
        </div>
      )}
      {children}
    </div>
  </div>
);
const ChatMsgAssist = ({ children, sources, streaming }) => (
  <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 14 }}>
    <div style={{
      maxWidth: '88%', padding: '10px 14px',
      background: 'var(--paper-00)', border: '1px solid var(--paper-2)',
      borderRadius: 'var(--r-lg)', borderBottomLeftRadius: 4,
      fontFamily: 'var(--serif)', fontSize: 14, lineHeight: 1.6, color: 'var(--ink-0)',
    }}>
      {children}
      {streaming && <span style={{ display: 'inline-block', width: 6, height: 14, background: 'var(--ink-2)', verticalAlign: 'middle', marginLeft: 2, animation: 'blink 1s infinite' }}/>}
      {sources && sources.length > 0 && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px dashed var(--paper-2)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {sources.map((s, i) => (
            <div key={i} style={{
              display: 'flex', gap: 8, fontSize: 11,
              color: 'var(--ink-2)', alignItems: 'baseline',
              fontFamily: 'var(--sans)',
            }}>
              <span style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', color: 'var(--ink-1)', flex: 1 }}>"{s.quote}"</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-3)', whiteSpace: 'nowrap' }}>p. {s.page}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  </div>
);

// The chat panel — replaces the right margin rail when opened
const ChatPanel = ({ inlineThread }) => (
  <div style={{
    padding: '24px 20px 0 20px',
    display: 'flex', flexDirection: 'column',
    height: '100%', boxSizing: 'border-box',
    borderLeft: '1px solid var(--paper-2)',
    background: 'color-mix(in oklab, var(--paper-0) 65%, var(--paper-00))',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        fontSize: 10.5, letterSpacing: 1.2, textTransform: 'uppercase', color: 'var(--ink-3)',
      }}>
        <IcSpark size={11}/> BookRAG · Stave I
      </div>
      <div style={{ color: 'var(--ink-3)', cursor: 'pointer' }}><IcClose size={12}/></div>
    </div>

    <div style={{ flex: 1, overflow: 'auto', paddingRight: 4 }}>
      {inlineThread ? (
        <>
          <div style={{
            padding: '8px 12px', marginBottom: 14,
            background: 'var(--accent-softer)', borderRadius: 'var(--r-md)',
            borderLeft: '2px solid var(--accent)',
          }}>
            <div style={{ fontSize: 9.5, letterSpacing: 1.2, color: 'var(--accent-ink)', marginBottom: 3 }}>
              THREAD ON MARGIN MARK
            </div>
            <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 12.5, color: 'var(--ink-1)', lineHeight: 1.5 }}>
              "Scrooge signed it." · p. 2
            </div>
          </div>
          <ChatMsgUser>Why does Dickens emphasize Scrooge signing it?</ChatMsgUser>
          <ChatMsgAssist sources={[
            { quote: "Scrooge signed it.", page: 2 },
            { quote: "Scrooge was his sole executor", page: 3 },
          ]}>
            It's a legal ritual — Dickens is binding Scrooge to Marley's death through the paper. The single sentence puts weight on the act: not just <em>present</em> at the funeral, but <em>responsible</em>. Later he'll sign nothing for the poor, of course.
          </ChatMsgAssist>
          <ChatMsgUser>Does this foreshadow the Cratchit scene?</ChatMsgUser>
          <ChatMsgAssist streaming>
            Yes — the contrast is deliberate. Watch how his reluctance to give anything to Fred's charity callers echoes this opening
          </ChatMsgAssist>
        </>
      ) : (
        <>
          <ChatMsgUser pageRef="2">Who is Marley and why is he dead to begin with?</ChatMsgUser>
          <ChatMsgAssist sources={[
            { quote: "Marley was dead, to begin with.", page: 1 },
            { quote: "Scrooge and he were partners for I don't know how many years.", page: 3 },
          ]}>
            Jacob Marley was Scrooge's <em>business partner</em>, dead seven years before the story opens. Dickens insists on this fact upfront — <em>"as dead as a door-nail"</em> — because the whole plot hinges on it being unambiguous. A ghost can only terrify if there's no doubt he's a ghost.
          </ChatMsgAssist>
          <ChatMsgUser>What about Scrooge's relationship to him now?</ChatMsgUser>
          <ChatMsgAssist streaming>
            Scrooge is his "sole executor, sole administrator, sole assign" — Dickens hammers the word <em>sole</em> to show
          </ChatMsgAssist>
        </>
      )}
    </div>

    {/* Composer */}
    <div style={{
      padding: '12px 0 16px', borderTop: '1px solid var(--paper-2)',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{
        display: 'flex', gap: 8, padding: '10px 12px',
        background: 'var(--paper-00)', border: '1px solid var(--paper-2)',
        borderRadius: 'var(--r-lg)',
      }}>
        <input
          placeholder="Ask about what you've read…"
          style={{
            flex: 1, border: 0, outline: 0, background: 'transparent',
            fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--ink-0)',
          }}
        />
        <div style={{
          width: 26, height: 26, borderRadius: 999, background: 'var(--ink-0)', color: 'var(--paper-00)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
        }}><IcSend size={11}/></div>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {['Summarize Stave I', 'Who is Scrooge?', 'Key themes so far'].map((c) => (
          <div key={c} style={{
            padding: '5px 10px', background: 'var(--paper-1)', borderRadius: 999,
            fontSize: 11, color: 'var(--ink-2)', cursor: 'pointer',
            fontFamily: 'var(--sans)',
          }}>{c}</div>
        ))}
      </div>
      <div style={{ fontSize: 10, color: 'var(--ink-3)', display: 'flex', alignItems: 'center', gap: 5, marginTop: 2 }}>
        <IcLock size={10}/> Only the text you've read (up to p. 3) is in scope.
      </div>
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// Base spread builder — parameterized for state variations
// ─────────────────────────────────────────────────────────────
const SpreadD = ({
  mode = 'rail',        // 'rail' | 'chat' | 'thread'
  turnState = null,     // null | 'turning' | 'chapterBreak'
  showTurnHint = false,
  spreadPages = [2, 3],
  leftChapter = 1,
  chapterTitle = "Marley's Ghost",
  showFog = true,
}) => {
  const gridCols = mode === 'rail'
    ? '180px 1fr 1fr 180px'
    : '180px 1fr 1fr 340px'; // chat panel wider

  const pageLift = turnState === 'turning' ? 'translateX(-6px) rotate(-.4deg)' : 'none';

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
        <div style={{ justifySelf: 'end', display: 'flex', gap: 10, color: 'var(--ink-2)', alignItems: 'center' }}>
          <IcSearch size={13}/><IcBookmark size={13}/>
          {/* Chat toggle */}
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '5px 10px', borderRadius: 999,
            background: mode !== 'rail' ? 'var(--accent)' : 'var(--paper-1)',
            color: mode !== 'rail' ? 'var(--paper-00)' : 'var(--ink-1)',
            fontSize: 11, fontWeight: 500, cursor: 'pointer',
            marginLeft: 4,
          }}>
            <IcSpark size={11}/> Ask
          </div>
        </div>
      </div>

      {/* Stage */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 24px', position: 'relative' }}>
        <button style={arrowStyleD2('left')}><IcArrowL size={20}/></button>

        <div style={{
          position: 'relative',
          width: mode === 'rail' ? 1320 : 1480, height: 720, maxHeight: 'calc(100vh - 160px)',
          display: 'grid', gridTemplateColumns: gridCols,
          background: 'var(--paper-00)',
          boxShadow: '0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)',
          borderRadius: 3,
          transition: 'all var(--dur-slower) var(--ease)',
        }}>
          {/* LEFT MARGIN RAIL */}
          <div style={{
            padding: '56px 16px 44px 20px',
            display: 'flex', flexDirection: 'column', gap: 14,
            fontFamily: 'var(--sans)',
          }}>
            <MarginNote kind="highlight" text="Marley: 7 years dead, still haunts Scrooge's door-plate." linkTarget="Jacob Marley"/>
            <MarginNote kind="ask" text="Why a door-nail, specifically?" answered/>
            {mode === 'thread' && (
              <MarginNote kind="ask" text="Why does Dickens emphasize Scrooge signing it?" answered/>
            )}
          </div>

          {/* LEFT PAGE */}
          <div style={{
            padding: '56px 44px 44px',
            display: 'flex', flexDirection: 'column',
            transform: pageLift, transformOrigin: 'right center',
            transition: 'transform var(--dur-slower) var(--ease)',
          }}>
            <div style={pageChapD2()}>Stave {ROMAN_V2[leftChapter]}</div>
            <div style={pageHeadD2()}>{chapterTitle}</div>
            <div style={proseD2()}>
              <p style={{ margin: '0 0 14px' }} className="dropcap">
                {PROSE_V2[1][0].replace('Scrooge signed it.', '')}
                <span style={{
                  background: mode === 'thread' ? 'var(--accent-soft)' : 'var(--accent-softer)',
                  color: mode === 'thread' ? 'var(--accent-ink)' : 'var(--accent-ink)',
                  padding: '1px 0',
                  boxShadow: mode === 'thread' ? '0 0 0 2px var(--accent-soft)' : 'none',
                }}>Scrooge signed it.</span>
                {' And Scrooge\'s name was good upon \'Change for anything he chose to put his hand to.'}
              </p>
              <p style={{ margin: '0 0 14px' }}>
                Old Marley was as dead as a{' '}
                <span style={{
                  textDecoration: 'underline', textDecorationStyle: 'dotted',
                  textDecorationColor: 'var(--accent)', textUnderlineOffset: 3,
                }}>door-nail</span>. Mind! I don't mean to say that I know, of my own knowledge, what there is particularly dead about a door-nail.
              </p>
              <p style={{ margin: '0 0 14px' }}>{PROSE_V2[1][2]}</p>
            </div>
            <div style={folioD2()}>
              <span>Charles Dickens</span>
              <span style={{ fontFamily: 'var(--mono)' }}>{spreadPages[0]}</span>
            </div>
          </div>

          {/* gutter */}
          <div style={{
            position: 'absolute',
            left: mode === 'rail'
              ? 'calc(180px + (100% - 360px) / 2)'
              : 'calc(180px + (100% - 180px - 340px) / 2)',
            top: 0, bottom: 0, width: 30,
            transform: 'translateX(-50%)', pointerEvents: 'none',
            background: 'linear-gradient(to right, transparent 0%, color-mix(in oklab, var(--ink-0) 7%, transparent) 50%, transparent 100%)',
          }}/>

          {/* Turning page overlay — a sheet of paper lifting */}
          {turnState === 'turning' && (
            <div style={{
              position: 'absolute',
              left: mode === 'rail' ? 180 : 180,
              right: mode === 'rail' ? 180 : 340,
              top: 0, bottom: 0,
              pointerEvents: 'none',
            }}>
              <div style={{
                position: 'absolute', left: '50%', top: 0, bottom: 0,
                width: '50%', transformOrigin: 'left center',
                transform: 'rotateY(-38deg) skewY(-.5deg)',
                background: 'linear-gradient(to right, var(--paper-00) 0%, color-mix(in oklab, var(--paper-00) 86%, var(--paper-1)) 100%)',
                boxShadow: '12px 10px 40px -10px rgba(28,24,18,.22), 2px 2px 8px rgba(28,24,18,.08)',
                borderRadius: '0 3px 3px 0',
                padding: '56px 44px',
                fontFamily: 'var(--serif)', fontSize: 15, lineHeight: 1.72, color: 'var(--ink-0)',
                textAlign: 'justify', hyphens: 'auto',
                overflow: 'hidden',
              }}>
                <p style={{ margin: 0, opacity: .4 }}>
                  {PROSE_V2[1][3].slice(0, 200)}
                </p>
              </div>
            </div>
          )}

          {/* RIGHT PAGE */}
          <div style={{
            padding: '56px 44px 44px',
            display: 'flex', flexDirection: 'column',
            opacity: turnState === 'turning' ? 0.4 : 1,
            transition: 'opacity var(--dur)',
          }}>
            <div style={proseD2()}>
              <p style={{ margin: '0 0 14px' }}>
                {PROSE_V2[1][3].slice(0, 140)}
                <span style={{ borderBottom: '1.5px solid oklch(58% 0.1 55)', paddingBottom: 1 }}>sole mourner</span>
                {PROSE_V2[1][3].slice(140 + 'sole mourner'.length)}
              </p>
              {showFog && (
                <p style={{ margin: '0 0 14px', filter: 'blur(3px)', opacity: .7, userSelect: 'none' }}>
                  {PROSE_V2[1][4]}
                </p>
              )}
            </div>
            <div style={folioD2()}>
              <span style={{ fontFamily: 'var(--mono)' }}>{spreadPages[1]}</span>
              <span>{chapterTitle}</span>
            </div>
          </div>

          {/* Right side — rail OR chat panel */}
          {mode === 'rail' ? (
            <div style={{
              padding: '56px 20px 44px 16px',
              display: 'flex', flexDirection: 'column', gap: 14,
              fontFamily: 'var(--sans)',
            }}>
              <MarginNote kind="note" text="Pencil cutoff here. Spoiler fog starts at 'sole mourner'." self/>
              <MarginNote kind="entity" text="Ebenezer Scrooge" subtitle="5 mentions · up to here"/>
            </div>
          ) : (
            <ChatPanel inlineThread={mode === 'thread'}/>
          )}

          {/* Thread connector — line from margin note to chat panel */}
          {mode === 'thread' && (
            <svg style={{
              position: 'absolute',
              left: '180px', top: '60px',
              width: 'calc(100% - 180px)', height: 80,
              pointerEvents: 'none',
            }}>
              <defs>
                <marker id="arrow" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="6" markerHeight="6" orient="auto">
                  <path d="M0 0 L8 4 L0 8 z" fill="var(--accent)"/>
                </marker>
              </defs>
              {/* A subtle dotted arc from the highlighted phrase to the top of the chat panel */}
              <path
                d="M 80 50 Q 500 20 900 40"
                fill="none" stroke="var(--accent)" strokeWidth="1" strokeDasharray="2 4" opacity="0.6"
              />
            </svg>
          )}
        </div>

        <button style={arrowStyleD2('right')}><IcArrowR size={20}/></button>

        {/* Page-turn keyboard hint */}
        {showTurnHint && (
          <div style={{
            position: 'absolute', bottom: -4, left: '50%', transform: 'translateX(-50%)',
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '7px 12px',
            background: 'var(--ink-0)', color: 'var(--paper-00)',
            borderRadius: 999, fontSize: 11,
            fontFamily: 'var(--sans)',
            boxShadow: '0 8px 24px -8px rgba(28,24,18,.3)',
          }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <Kbd>←</Kbd> <Kbd>→</Kbd> turn pages
            </span>
            <span style={{ color: 'var(--ink-3)' }}>·</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <Kbd>Space</Kbd> next
            </span>
            <span style={{ color: 'var(--ink-3)' }}>·</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <Kbd>/</Kbd> ask
            </span>
          </div>
        )}
      </div>

      {/* Bottom */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center',
        padding: '14px 32px 18px', height: 56, boxSizing: 'border-box', fontSize: 11, color: 'var(--ink-3)',
      }}>
        <span>{mode === 'rail' ? '3 margin marks on this spread' : mode === 'thread' ? '1 thread open · anchored to p. 2' : 'Chat scoped to Stave I · 3 pages read'}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ProgressDots current={1} total={5}/>
          <span style={{ fontFamily: 'var(--mono)' }}>3%</span>
        </div>
        <span style={{ justifySelf: 'end', fontFamily: 'var(--mono)' }}>p. {spreadPages[0]}–{spreadPages[1]} / 176</span>
      </div>
    </div>
  );
};

const Kbd = ({ children }) => (
  <span style={{
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    minWidth: 18, height: 18, padding: '0 5px',
    background: 'color-mix(in oklab, var(--paper-00) 20%, transparent)',
    border: '1px solid color-mix(in oklab, var(--paper-00) 30%, transparent)',
    borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 10.5,
    color: 'var(--paper-00)',
  }}>{children}</span>
);

const arrowStyleD2 = (side) => ({
  position: 'absolute', top: '50%', transform: 'translateY(-50%)',
  [side]: 10,
  width: 42, height: 42, borderRadius: 999,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  color: 'var(--ink-2)', cursor: 'pointer', background: 'transparent', border: 0,
});
const pageChapD2 = () => ({
  fontFamily: 'var(--serif)', fontStyle: 'italic',
  fontSize: 12, color: 'var(--ink-3)', letterSpacing: 0.4, marginBottom: 6,
});
const pageHeadD2 = () => ({
  fontFamily: 'var(--serif)', fontWeight: 400,
  fontSize: 22, letterSpacing: -0.3, color: 'var(--ink-0)',
  margin: '0 0 22px',
});
const proseD2 = () => ({
  fontFamily: 'var(--serif)', fontSize: 15, lineHeight: 1.72,
  color: 'var(--ink-0)', textAlign: 'justify', hyphens: 'auto', flex: 1,
});
const folioD2 = () => ({
  marginTop: 'auto', paddingTop: 16,
  display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
  fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 11,
  color: 'var(--ink-3)', letterSpacing: 0.3,
});

// Chapter-break flip — shows a full page as a chapter title card
const SpreadD_ChapterBreak = () => (
  <div style={{
    width: '100%', height: '100%',
    background: 'radial-gradient(ellipse at center 30%, color-mix(in oklab, var(--paper-0) 92%, var(--paper-1)), var(--paper-0) 70%), var(--paper-0)',
    display: 'flex', flexDirection: 'column', overflow: 'hidden',
    fontFamily: 'var(--sans)',
  }}>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', padding: '14px 28px', height: 52, boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--ink-2)', fontSize: 12 }}>
        <IcArrowL size={13}/> Library
      </div>
      <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 14, color: 'var(--ink-1)' }}>
        A Christmas Carol · <span style={{ color: 'var(--ink-3)', fontStyle: 'normal' }}>Dickens</span>
      </div>
      <div style={{ justifySelf: 'end', display: 'flex', gap: 10, color: 'var(--ink-2)' }}>
        <IcSearch size={13}/><IcBookmark size={13}/>
        <div style={{ padding: '5px 10px', borderRadius: 999, background: 'var(--paper-1)', color: 'var(--ink-1)', fontSize: 11, fontWeight: 500, display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 4 }}>
          <IcSpark size={11}/> Ask
        </div>
      </div>
    </div>

    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 24px', position: 'relative' }}>
      <button style={arrowStyleD2('left')}><IcArrowL size={20}/></button>
      <div style={{
        position: 'relative',
        width: 1320, height: 720, maxHeight: 'calc(100vh - 160px)',
        display: 'grid', gridTemplateColumns: '180px 1fr 1fr 180px',
        background: 'var(--paper-00)',
        boxShadow: '0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)',
        borderRadius: 3,
      }}>
        {/* empty rails */}
        <div/>
        {/* left page — end of Stave I */}
        <div style={{ padding: '56px 44px 44px', display: 'flex', flexDirection: 'column' }}>
          <div style={proseD2()}>
            <p style={{ margin: '0 0 14px' }}>{PROSE_V2[1][4].slice(0, 160)}…</p>
            <div style={{ marginTop: 'auto', textAlign: 'center', color: 'var(--ink-3)', letterSpacing: 8, fontSize: 12, padding: '40px 0' }}>
              · · ·
            </div>
            <div style={{ textAlign: 'center', fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 11, color: 'var(--ink-3)', letterSpacing: 0.4 }}>
              end of Stave I
            </div>
          </div>
          <div style={folioD2()}>
            <span>Charles Dickens</span>
            <span style={{ fontFamily: 'var(--mono)' }}>22</span>
          </div>
        </div>
        {/* gutter */}
        <div style={{
          position: 'absolute', left: 'calc(180px + (100% - 360px) / 2)', top: 0, bottom: 0, width: 30,
          transform: 'translateX(-50%)', pointerEvents: 'none',
          background: 'linear-gradient(to right, transparent 0%, color-mix(in oklab, var(--ink-0) 7%, transparent) 50%, transparent 100%)',
        }}/>
        {/* right page — Stave II title card */}
        <div style={{
          padding: '56px 44px 44px',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: 16,
        }}>
          <div style={{ fontSize: 10.5, letterSpacing: 2.4, textTransform: 'uppercase', color: 'var(--ink-3)' }}>
            Stave {ROMAN_V2[2]}
          </div>
          <div style={{ fontFamily: 'var(--serif)', fontSize: 34, letterSpacing: -0.5, color: 'var(--ink-0)', textAlign: 'center', maxWidth: 380, lineHeight: 1.15 }}>
            The First of the Three Spirits
          </div>
          <div style={{ margin: '8px 0', width: 40, height: 1, background: 'var(--paper-3)' }}/>
          <div style={{
            fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 13,
            color: 'var(--ink-2)', maxWidth: 300, textAlign: 'center', lineHeight: 1.55,
          }}>
            in which Scrooge meets a figure <br/>"like a child; yet not so like a child as like an old man."
          </div>
          <div style={{ marginTop: 'auto', fontSize: 11, color: 'var(--ink-3)', fontFamily: 'var(--mono)', alignSelf: 'flex-end' }}>23</div>
        </div>
        <div/>
      </div>
      <button style={arrowStyleD2('right')}><IcArrowR size={20}/></button>
    </div>

    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', padding: '14px 32px 18px', height: 56, fontSize: 11, color: 'var(--ink-3)' }}>
      <span style={{ fontStyle: 'italic' }}>Stave I complete · 7 notes made</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <ProgressDots current={2} total={5}/>
        <span style={{ fontFamily: 'var(--mono)' }}>25%</span>
      </div>
      <span style={{ justifySelf: 'end', fontFamily: 'var(--mono)' }}>p. 22–23 / 176</span>
    </div>
  </div>
);

Object.assign(window, { SpreadD, SpreadD_ChapterBreak });
