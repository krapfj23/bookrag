// ─────────────────────────────────────────────────────────────
// Chat variations — larger, better aligned, exploring 4 directions
//   V1: Side drawer — wider (480), bigger type, clearer hierarchy
//   V2: Bottom sheet — chat as a drawer from the bottom, book stays in view
//   V3: Inline cards — answers appear as floating note-cards pinned into
//       the page margin, anchored to the quoted line
//   V4: Split view — reading column + dedicated chat column, equal weight
// ─────────────────────────────────────────────────────────────

// ─── Shared chat primitives (larger, refined) ────────────────
const ChatBubbleUser = ({ children, pageRef, size = 'md' }) => {
  const fs = size === 'lg' ? 16 : size === 'sm' ? 13 : 15;
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 18 }}>
      <div style={{
        maxWidth: '82%', padding: '12px 16px',
        background: 'var(--accent-soft)', color: 'var(--accent-ink)',
        borderRadius: 14, borderBottomRightRadius: 4,
        fontFamily: 'var(--serif)', fontSize: fs, lineHeight: 1.55,
      }}>
        {pageRef && (
          <div style={{
            fontFamily: 'var(--sans)', fontSize: 10, letterSpacing: 0.8,
            textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 5,
            display: 'flex', alignItems: 'center', gap: 6, fontWeight: 500,
          }}>
            <span style={{ width: 4, height: 4, borderRadius: 999, background: 'var(--accent)' }}/>
            from p. {pageRef}
          </div>
        )}
        {children}
      </div>
    </div>
  );
};

const ChatBubbleAssist = ({ children, sources, streaming, size = 'md', avatar = true }) => {
  const fs = size === 'lg' ? 16 : size === 'sm' ? 13 : 15;
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 18, gap: 10 }}>
      {avatar && (
        <div style={{
          flexShrink: 0, width: 26, height: 26, borderRadius: 999,
          background: 'var(--ink-0)', color: 'var(--paper-00)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--serif)', fontSize: 12, fontStyle: 'italic',
          marginTop: 2,
        }}>B</div>
      )}
      <div style={{
        maxWidth: avatar ? 'calc(88% - 36px)' : '88%',
        padding: '12px 16px',
        background: 'var(--paper-00)', border: '1px solid var(--paper-2)',
        borderRadius: 14, borderBottomLeftRadius: 4,
        fontFamily: 'var(--serif)', fontSize: fs, lineHeight: 1.6, color: 'var(--ink-0)',
      }}>
        {children}
        {streaming && (
          <span style={{
            display: 'inline-block', width: 6, height: 15,
            background: 'var(--ink-2)', verticalAlign: 'text-bottom',
            marginLeft: 3, animation: 'blink 1s infinite',
          }}/>
        )}
        {sources && sources.length > 0 && (
          <div style={{
            marginTop: 12, paddingTop: 12,
            borderTop: '1px dashed var(--paper-2)',
            display: 'flex', flexDirection: 'column', gap: 8,
          }}>
            <div style={{
              fontFamily: 'var(--sans)', fontSize: 10, letterSpacing: 1,
              textTransform: 'uppercase', color: 'var(--ink-3)', fontWeight: 500,
            }}>Grounded in</div>
            {sources.map((s, i) => (
              <div key={i} style={{
                display: 'flex', gap: 10, alignItems: 'baseline',
                padding: '4px 0',
              }}>
                <span style={{
                  fontFamily: 'var(--serif)', fontStyle: 'italic',
                  color: 'var(--ink-1)', flex: 1, fontSize: fs - 2, lineHeight: 1.5,
                }}>"{s.quote}"</span>
                <span style={{
                  fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink-3)',
                  whiteSpace: 'nowrap', padding: '2px 6px',
                  background: 'var(--paper-1)', borderRadius: 4,
                }}>p. {s.page}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const Composer = ({ size = 'md', suggestions = ['Summarize Stave I', 'Who is Scrooge?', 'Key themes so far'] }) => {
  const pad = size === 'lg' ? '14px 16px' : '12px 14px';
  const fs = size === 'lg' ? 15 : 14;
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      <div style={{
        display: 'flex', gap: 10, padding: pad,
        background: 'var(--paper-00)', border: '1px solid var(--paper-2)',
        borderRadius: 14,
        boxShadow: '0 1px 0 rgba(28,24,18,.02)',
      }}>
        <input
          placeholder="Ask about what you've read…"
          style={{
            flex: 1, border: 0, outline: 0, background: 'transparent',
            fontFamily: 'var(--sans)', fontSize: fs, color: 'var(--ink-0)',
          }}
        />
        <div style={{
          width: 32, height: 32, borderRadius: 999,
          background: 'var(--ink-0)', color: 'var(--paper-00)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
        }}><IcSend size={13}/></div>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {suggestions.map((c) => (
          <div key={c} style={{
            padding: '6px 12px', background: 'var(--paper-1)', borderRadius: 999,
            fontSize: 12, color: 'var(--ink-2)', cursor: 'pointer',
            fontFamily: 'var(--sans)', fontWeight: 500,
            border: '1px solid transparent',
          }}>{c}</div>
        ))}
      </div>
    </div>
  );
};

// ─── Reusable reading surface (the book behind the chat) ────
const BookSpread = ({ dim = false, highlightPhrase = null, narrow = false, singlePage = false }) => {
  const pageStyle = {
    padding: '52px 44px 40px',
    display: 'flex', flexDirection: 'column',
    opacity: dim ? 0.55 : 1,
    transition: 'opacity var(--dur)',
  };
  const chap = { fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 11.5, color: 'var(--ink-3)', letterSpacing: 0.4, marginBottom: 6 };
  const head = { fontFamily: 'var(--serif)', fontWeight: 400, fontSize: 22, letterSpacing: -0.3, color: 'var(--ink-0)', margin: '0 0 20px' };
  const prose = { fontFamily: 'var(--serif)', fontSize: narrow ? 14 : 15, lineHeight: 1.72, color: 'var(--ink-0)', textAlign: 'justify', hyphens: 'auto', flex: 1 };
  const folio = { marginTop: 'auto', paddingTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 11, color: 'var(--ink-3)', letterSpacing: 0.3 };

  const LeftPage = (
    <div style={pageStyle}>
      <div style={chap}>Stave I</div>
      <div style={head}>Marley's Ghost</div>
      <div style={prose}>
        <p style={{ margin: '0 0 12px' }} className="dropcap">
          Marley was dead, to begin with. There is no doubt whatever about that. The register of his burial was signed by the clergyman, the clerk, the undertaker, and the chief mourner.{' '}
          <span data-phrase="scrooge-signed" style={{
            background: highlightPhrase === 'scrooge-signed' ? 'var(--accent-soft)' : 'transparent',
            color: highlightPhrase === 'scrooge-signed' ? 'var(--accent-ink)' : 'inherit',
            padding: '1px 2px',
            boxShadow: highlightPhrase === 'scrooge-signed' ? '0 0 0 2px var(--accent-soft)' : 'none',
            borderRadius: 2,
          }}>Scrooge signed it.</span>
          {' '}And Scrooge's name was good upon 'Change for anything he chose to put his hand to.
        </p>
        <p style={{ margin: '0 0 12px' }}>
          Old Marley was as dead as a{' '}
          <span style={{
            textDecoration: 'underline', textDecorationStyle: 'dotted',
            textDecorationColor: 'var(--accent)', textUnderlineOffset: 3,
          }}>door-nail</span>. Mind! I don't mean to say that I know, of my own knowledge, what there is particularly dead about a door-nail.
        </p>
        <p style={{ margin: '0 0 12px' }}>But the wisdom of our ancestors is in the simile; and my unhallowed hands shall not disturb it, or the Country's done for.</p>
      </div>
      <div style={folio}><span>Charles Dickens</span><span style={{ fontFamily: 'var(--mono)' }}>2</span></div>
    </div>
  );
  const RightPage = (
    <div style={pageStyle}>
      <div style={{ ...prose, marginTop: 0 }}>
        <p style={{ margin: '0 0 12px' }}>
          Scrooge knew he was dead? Of course he did. How could it be otherwise? Scrooge and he were partners for I don't know how many years. Scrooge was his sole executor, his{' '}
          <span style={{ borderBottom: '1.5px solid oklch(58% 0.1 55)', paddingBottom: 1 }}>sole mourner</span>.
        </p>
        <p style={{ margin: '0 0 12px', filter: 'blur(3px)', opacity: .7, userSelect: 'none' }}>
          And even Scrooge was not so dreadfully cut up by the sad event, but that he was an excellent man of business on the very day of the funeral.
        </p>
      </div>
      <div style={folio}><span style={{ fontFamily: 'var(--mono)' }}>3</span><span>Marley's Ghost</span></div>
    </div>
  );

  if (singlePage) {
    return (
      <div style={{
        background: 'var(--paper-00)',
        boxShadow: '0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)',
        borderRadius: 3, display: 'flex', flexDirection: 'column',
        width: '100%', height: '100%',
      }}>
        {LeftPage}
      </div>
    );
  }

  return (
    <div style={{
      background: 'var(--paper-00)',
      boxShadow: '0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)',
      borderRadius: 3,
      display: 'grid', gridTemplateColumns: '1fr 1fr',
      width: '100%', height: '100%', position: 'relative',
    }}>
      {LeftPage}
      <div style={{
        position: 'absolute', left: '50%', top: 0, bottom: 0, width: 30,
        transform: 'translateX(-50%)', pointerEvents: 'none',
        background: 'linear-gradient(to right, transparent 0%, color-mix(in oklab, var(--ink-0) 7%, transparent) 50%, transparent 100%)',
      }}/>
      {RightPage}
    </div>
  );
};

const ChatHeader = ({ title = 'BookRAG', subtitle = 'A Christmas Carol · Stave I', onClose = true }) => (
  <div style={{
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '18px 24px', borderBottom: '1px solid var(--paper-2)',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{
        width: 34, height: 34, borderRadius: 10,
        background: 'var(--accent-softer)', color: 'var(--accent-ink)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}><IcSpark size={14}/></div>
      <div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 600, color: 'var(--ink-0)', letterSpacing: -0.1 }}>
          {title}
        </div>
        <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 12, color: 'var(--ink-3)', marginTop: 1 }}>
          {subtitle}
        </div>
      </div>
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{
        padding: '4px 10px', background: 'var(--paper-1)', borderRadius: 999,
        fontSize: 10.5, color: 'var(--ink-2)', display: 'inline-flex', alignItems: 'center', gap: 5,
        fontFamily: 'var(--sans)', fontWeight: 500,
      }}>
        <IcLock size={10}/> p. 1–3 in scope
      </div>
      {onClose && <div style={{ color: 'var(--ink-3)', cursor: 'pointer' }}><IcClose size={14}/></div>}
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// V1 — Wider side drawer (480px), better alignment, larger type
// ─────────────────────────────────────────────────────────────
const ChatV1_Drawer = ({ thread = false }) => (
  <div style={{
    width: '100%', height: '100%',
    background: 'radial-gradient(ellipse at center 30%, color-mix(in oklab, var(--paper-0) 92%, var(--paper-1)), var(--paper-0) 70%), var(--paper-0)',
    display: 'flex', flexDirection: 'column', overflow: 'hidden',
    fontFamily: 'var(--sans)',
  }}>
    {/* Top bar */}
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
        <div style={{
          padding: '5px 11px', borderRadius: 999,
          background: 'var(--accent)', color: 'var(--paper-00)',
          fontSize: 11, fontWeight: 500, display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 4,
        }}>
          <IcSpark size={11}/> Ask
        </div>
      </div>
    </div>

    {/* Stage — book + side drawer */}
    <div style={{
      flex: 1, display: 'grid', gridTemplateColumns: '1fr 520px',
      gap: 24, padding: '8px 24px 24px',
      alignItems: 'stretch',
    }}>
      {/* Book area (slightly dimmed to pull focus to chat) */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
      }}>
        <BookSpread dim highlightPhrase={thread ? 'scrooge-signed' : null}/>
      </div>

      {/* Chat drawer */}
      <div style={{
        display: 'flex', flexDirection: 'column',
        background: 'var(--paper-00)',
        border: '1px solid var(--paper-2)',
        borderRadius: 'var(--r-lg)',
        boxShadow: '0 30px 70px -24px rgba(28,24,18,.18), 0 10px 20px -8px rgba(28,24,18,.06)',
        overflow: 'hidden',
      }}>
        <ChatHeader/>

        <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>
          {thread ? (
            <>
              <div style={{
                padding: '12px 14px', marginBottom: 20,
                background: 'var(--accent-softer)', borderRadius: 10,
                borderLeft: '3px solid var(--accent)',
                display: 'flex', flexDirection: 'column', gap: 4,
              }}>
                <div style={{ fontSize: 9.5, letterSpacing: 1.4, color: 'var(--accent-ink)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <IcBookmark size={9}/> ANCHORED TO p. 2
                </div>
                <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 14, color: 'var(--ink-1)', lineHeight: 1.5 }}>
                  "Scrooge signed it."
                </div>
              </div>
              <ChatBubbleUser size="md">Why does Dickens emphasize Scrooge signing it?</ChatBubbleUser>
              <ChatBubbleAssist size="md" sources={[
                { quote: "Scrooge signed it.", page: 2 },
                { quote: "Scrooge was his sole executor", page: 3 },
              ]}>
                It's a legal ritual — Dickens binds Scrooge to Marley's death through the paper. One clipped sentence puts weight on the act: not just <em>present</em> at the funeral, but <em>responsible</em>.
              </ChatBubbleAssist>
              <ChatBubbleUser size="md">Does this foreshadow Cratchit?</ChatBubbleUser>
              <ChatBubbleAssist size="md" streaming>
                Yes — the contrast is deliberate. Watch how his reluctance with Fred's charity callers echoes this opening
              </ChatBubbleAssist>
            </>
          ) : (
            <>
              <ChatBubbleUser size="md" pageRef="2">Who is Marley and why is he dead to begin with?</ChatBubbleUser>
              <ChatBubbleAssist size="md" sources={[
                { quote: "Marley was dead, to begin with.", page: 1 },
                { quote: "Scrooge and he were partners for I don't know how many years.", page: 3 },
              ]}>
                Jacob Marley was Scrooge's <em>business partner</em>, dead seven years before the story opens. Dickens insists on this fact upfront — <em>"as dead as a door-nail"</em> — because the whole plot hinges on it being unambiguous. A ghost can only terrify if there's no doubt he's a ghost.
              </ChatBubbleAssist>
              <ChatBubbleUser size="md">What about Scrooge's relationship to him now?</ChatBubbleUser>
              <ChatBubbleAssist size="md" streaming>
                Scrooge is his "sole executor, sole administrator, sole assign" — Dickens hammers the word <em>sole</em> to show
              </ChatBubbleAssist>
            </>
          )}
        </div>

        <div style={{ padding: '16px 24px 20px', borderTop: '1px solid var(--paper-2)', background: 'var(--paper-0)' }}>
          <Composer/>
        </div>
      </div>
    </div>

    <div style={{ padding: '0 32px 14px', fontSize: 11, color: 'var(--ink-3)', display: 'flex', justifyContent: 'space-between' }}>
      <span>{thread ? '1 thread anchored to p. 2' : 'Chat scoped to 3 pages read'}</span>
      <span style={{ fontFamily: 'var(--mono)' }}>p. 2–3 / 176 · 3%</span>
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// V2 — Bottom sheet — chat rises from the bottom; book stays centered
// ─────────────────────────────────────────────────────────────
const ChatV2_BottomSheet = () => (
  <div style={{
    width: '100%', height: '100%',
    background: 'radial-gradient(ellipse at center 30%, color-mix(in oklab, var(--paper-0) 92%, var(--paper-1)), var(--paper-0) 70%), var(--paper-0)',
    display: 'flex', flexDirection: 'column', overflow: 'hidden',
    fontFamily: 'var(--sans)', position: 'relative',
  }}>
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
        <IcSearch size={13}/><IcBookmark size={13}/>
      </div>
    </div>

    {/* Book behind — visible above the sheet */}
    <div style={{
      flex: 1, display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
      padding: '0 80px', minHeight: 0,
    }}>
      <div style={{ width: 1100, height: 460, maxHeight: 460, display: 'flex' }}>
        <BookSpread/>
      </div>
    </div>

    {/* Bottom sheet */}
    <div style={{
      position: 'absolute', left: 80, right: 80, bottom: 0,
      height: 440,
      background: 'var(--paper-00)',
      borderTopLeftRadius: 20, borderTopRightRadius: 20,
      border: '1px solid var(--paper-2)', borderBottom: 0,
      boxShadow: '0 -20px 50px -16px rgba(28,24,18,.18)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Grabber */}
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 10 }}>
        <div style={{ width: 40, height: 4, borderRadius: 4, background: 'var(--paper-3)' }}/>
      </div>
      <ChatHeader/>
      <div style={{ flex: 1, overflow: 'auto', padding: '18px 28px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <div>
          <ChatBubbleUser size="md" pageRef="2">Who is Marley and why is he dead to begin with?</ChatBubbleUser>
          <ChatBubbleAssist size="md" sources={[
            { quote: "Marley was dead, to begin with.", page: 1 },
            { quote: "partners for I don't know how many years.", page: 3 },
          ]}>
            Jacob Marley was Scrooge's <em>business partner</em>, dead seven years before the story opens. Dickens insists on this upfront — a ghost can only terrify if there's no doubt he's a ghost.
          </ChatBubbleAssist>
        </div>
        <div>
          <ChatBubbleUser size="md">What about Scrooge's relationship to him now?</ChatBubbleUser>
          <ChatBubbleAssist size="md" streaming>
            Scrooge is his "sole executor, sole administrator, sole assign" — Dickens hammers the word <em>sole</em> to show how completely intertwined
          </ChatBubbleAssist>
        </div>
      </div>
      <div style={{ padding: '14px 28px 22px', borderTop: '1px solid var(--paper-2)', background: 'var(--paper-0)' }}>
        <Composer/>
      </div>
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// V3 — Inline cards pinned to the margin, anchored to quoted line
// ─────────────────────────────────────────────────────────────
const ChatV3_Inline = () => (
  <div style={{
    width: '100%', height: '100%',
    background: 'radial-gradient(ellipse at center 30%, color-mix(in oklab, var(--paper-0) 92%, var(--paper-1)), var(--paper-0) 70%), var(--paper-0)',
    display: 'flex', flexDirection: 'column', overflow: 'hidden',
    fontFamily: 'var(--sans)',
  }}>
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
        <IcSearch size={13}/><IcBookmark size={13}/>
      </div>
    </div>

    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 24px', position: 'relative' }}>
      <div style={{
        position: 'relative',
        width: 1360, height: 720, maxHeight: 'calc(100vh - 160px)',
        display: 'grid', gridTemplateColumns: '1fr 380px',
        gap: 28, alignItems: 'stretch',
      }}>
        {/* Book */}
        <div style={{ position: 'relative' }}>
          <BookSpread highlightPhrase="scrooge-signed"/>
        </div>

        {/* Inline card column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, paddingTop: 40 }}>
          {/* Connector line from highlight to card */}
          <svg style={{ position: 'absolute', left: -28, top: 80, width: 60, height: 40, pointerEvents: 'none' }}>
            <path d="M 0 20 Q 20 0 60 10" stroke="var(--accent)" strokeWidth="1" fill="none" strokeDasharray="2 3" opacity="0.6"/>
          </svg>

          <div style={{
            padding: '16px 18px',
            background: 'var(--paper-00)', border: '1px solid var(--paper-2)',
            borderLeft: '3px solid var(--accent)',
            borderRadius: 10,
            transform: 'rotate(-.3deg)',
            boxShadow: '0 4px 12px -4px rgba(28,24,18,.08)',
          }}>
            <div style={{ fontSize: 9.5, letterSpacing: 1.4, color: 'var(--accent-ink)', fontWeight: 600, marginBottom: 6 }}>
              ASKED ABOUT "Scrooge signed it." · p. 2
            </div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 14, color: 'var(--ink-1)', lineHeight: 1.55, marginBottom: 10, fontStyle: 'italic' }}>
              Why does Dickens emphasize this?
            </div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 14.5, color: 'var(--ink-0)', lineHeight: 1.65 }}>
              It's a legal ritual. Dickens binds Scrooge to Marley's death through the paper — not just <em>present</em> at the funeral, but <em>responsible</em> for what follows.
            </div>
          </div>

          <div style={{
            padding: '16px 18px',
            background: 'var(--paper-00)', border: '1px solid var(--paper-2)',
            borderLeft: '3px solid var(--accent)',
            borderRadius: 10,
            transform: 'rotate(.2deg)',
            boxShadow: '0 4px 12px -4px rgba(28,24,18,.08)',
          }}>
            <div style={{ fontSize: 9.5, letterSpacing: 1.4, color: 'var(--accent-ink)', fontWeight: 600, marginBottom: 6 }}>
              ASKED ABOUT "door-nail" · p. 2
            </div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 14, color: 'var(--ink-1)', lineHeight: 1.55, marginBottom: 10, fontStyle: 'italic' }}>
              Why a door-nail specifically?
            </div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 14.5, color: 'var(--ink-0)', lineHeight: 1.65 }}>
              Proverbial — a door-nail was hammered flat on the reverse, so could never be re-used. The narrator defends the simile even while doubting it, which is pure Dickens.
            </div>
          </div>

          {/* New question composer — minimal */}
          <div style={{
            padding: '12px 14px',
            background: 'var(--paper-00)', border: '1px dashed var(--paper-3)',
            borderRadius: 10, display: 'flex', alignItems: 'center', gap: 10,
            color: 'var(--ink-3)', fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 13,
          }}>
            <IcPlus size={12}/> Highlight text or click <IcSpark size={11}/> to ask about this page
          </div>
        </div>
      </div>
    </div>

    <div style={{ padding: '14px 32px 18px', fontSize: 11, color: 'var(--ink-3)', display: 'flex', justifyContent: 'space-between' }}>
      <span>2 inline asks on this spread</span>
      <span style={{ fontFamily: 'var(--mono)' }}>p. 2–3 / 176 · 3%</span>
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// V4 — Split view — reading and chat get equal weight
// ─────────────────────────────────────────────────────────────
const ChatV4_Split = () => (
  <div style={{
    width: '100%', height: '100%',
    background: 'var(--paper-1)',
    display: 'flex', flexDirection: 'column', overflow: 'hidden',
    fontFamily: 'var(--sans)',
  }}>
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr auto 1fr',
      alignItems: 'center', padding: '14px 28px', height: 52, boxSizing: 'border-box',
      background: 'var(--paper-0)', borderBottom: '1px solid var(--paper-2)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--ink-2)', fontSize: 12 }}>
        <IcArrowL size={13}/> Library
      </div>
      <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 14, color: 'var(--ink-1)' }}>
        A Christmas Carol · <span style={{ color: 'var(--ink-3)', fontStyle: 'normal' }}>Dickens</span>
      </div>
      <div style={{ justifySelf: 'end', display: 'flex', gap: 10, color: 'var(--ink-2)', alignItems: 'center' }}>
        <div style={{
          display: 'inline-flex', background: 'var(--paper-1)', borderRadius: 999, padding: 2,
        }}>
          <div style={{ padding: '4px 12px', fontSize: 11, borderRadius: 999, color: 'var(--ink-2)' }}>Read</div>
          <div style={{ padding: '4px 12px', fontSize: 11, borderRadius: 999, background: 'var(--paper-00)', color: 'var(--ink-0)', fontWeight: 500, boxShadow: '0 1px 3px rgba(28,24,18,.08)' }}>Read + Ask</div>
        </div>
      </div>
    </div>

    <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', minHeight: 0 }}>
      {/* Reading column */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 40, borderRight: '1px solid var(--paper-2)',
        background: 'var(--paper-1)',
      }}>
        <div style={{ width: '100%', maxWidth: 520, height: '100%', maxHeight: 720 }}>
          <BookSpread singlePage/>
        </div>
      </div>

      {/* Chat column */}
      <div style={{ display: 'flex', flexDirection: 'column', background: 'var(--paper-0)' }}>
        <ChatHeader onClose={false}/>
        <div style={{ flex: 1, overflow: 'auto', padding: '24px 32px' }}>
          <div style={{
            fontSize: 10.5, letterSpacing: 1.2, color: 'var(--ink-3)', textTransform: 'uppercase',
            fontWeight: 500, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{ height: 1, flex: 1, background: 'var(--paper-2)' }}/>
            Today · after p. 3
            <span style={{ height: 1, flex: 1, background: 'var(--paper-2)' }}/>
          </div>

          <ChatBubbleUser size="lg" pageRef="2">Who is Marley and why is he dead to begin with?</ChatBubbleUser>
          <ChatBubbleAssist size="lg" sources={[
            { quote: "Marley was dead, to begin with.", page: 1 },
            { quote: "Scrooge and he were partners for I don't know how many years.", page: 3 },
            { quote: "Scrooge was his sole executor", page: 3 },
          ]}>
            Jacob Marley was Scrooge's <em>business partner</em>, dead seven years before the story opens. Dickens insists on this fact upfront — <em>"as dead as a door-nail"</em> — because the whole plot hinges on it being unambiguous.
            <br/><br/>
            A ghost can only terrify if there's no doubt he's a ghost.
          </ChatBubbleAssist>
          <ChatBubbleUser size="lg">What about Scrooge's relationship to him now?</ChatBubbleUser>
          <ChatBubbleAssist size="lg" streaming>
            Scrooge is his "sole executor, sole administrator, sole assign" — Dickens hammers the word <em>sole</em> to show how completely Scrooge has absorbed Marley's
          </ChatBubbleAssist>
        </div>
        <div style={{ padding: '18px 32px 24px', borderTop: '1px solid var(--paper-2)', background: 'var(--paper-00)' }}>
          <Composer size="lg" suggestions={['Summarize Stave I', 'Who is Scrooge?', 'Explain "door-nail"', 'Key themes so far']}/>
        </div>
      </div>
    </div>
  </div>
);

Object.assign(window, {
  ChatV1_Drawer, ChatV2_BottomSheet, ChatV3_Inline, ChatV4_Split,
  ChatBubbleUser, ChatBubbleAssist, Composer, ChatHeader, BookSpread,
});
