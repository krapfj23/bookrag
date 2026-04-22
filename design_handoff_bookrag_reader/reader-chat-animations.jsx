// ─────────────────────────────────────────────────────────────
// Chat open animations — how chat arrives in each variation
// Uses simple CSS transitions driven by a React state.
// Each demo has a Replay button; all run with the same timing (520ms)
// so they can be compared.
// ─────────────────────────────────────────────────────────────

const OPEN_DUR = 520;  // ms
const EASE = 'cubic-bezier(.32, .72, .24, 1)'; // smooth, slightly overshooting feel

const ReplayButton = ({ onClick, label = 'Replay' }) => (
  <div
    onClick={onClick}
    style={{
      position: 'absolute', top: 12, right: 14, zIndex: 20,
      padding: '6px 12px', borderRadius: 999,
      background: 'var(--ink-0)', color: 'var(--paper-00)',
      fontSize: 11, fontWeight: 500, cursor: 'pointer',
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: 'var(--sans)',
      boxShadow: '0 4px 12px -4px rgba(28,24,18,.3)',
      userSelect: 'none',
    }}
  >
    <IcRefresh size={11}/> {label}
  </div>
);

const useReplay = () => {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const t1 = setTimeout(() => setOpen(true), 400);
    return () => clearTimeout(t1);
  }, []);
  const replay = () => {
    setOpen(false);
    setTimeout(() => setOpen(true), 50);
  };
  return [open, replay];
};

// ─────────────────────────────────────────────────────────────
// V1 Drawer — book shrinks left, drawer slides from right edge
// ─────────────────────────────────────────────────────────────
const AnimChatV1 = () => {
  const [open, replay] = useReplay();
  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative',
      background: 'radial-gradient(ellipse at center 30%, color-mix(in oklab, var(--paper-0) 92%, var(--paper-1)), var(--paper-0) 70%), var(--paper-0)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      fontFamily: 'var(--sans)',
    }}>
      <ReplayButton onClick={replay}/>
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
            background: open ? 'var(--accent)' : 'var(--paper-1)',
            color: open ? 'var(--paper-00)' : 'var(--ink-1)',
            fontSize: 11, fontWeight: 500, display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 4,
            transition: `all ${OPEN_DUR}ms ${EASE}`,
          }}>
            <IcSpark size={11}/> Ask
          </div>
        </div>
      </div>

      {/* Stage */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {/* Book — shifts from centered to left */}
        <div style={{
          position: 'absolute',
          top: 8, bottom: 24,
          left: open ? 24 : '50%',
          width: open ? 'calc(100% - 544px - 48px)' : 1120,
          transform: open ? 'none' : 'translateX(-50%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: `all ${OPEN_DUR}ms ${EASE}`,
          opacity: open ? 0.55 : 1,
        }}>
          <BookSpread/>
        </div>

        {/* Drawer — slides in from right */}
        <div style={{
          position: 'absolute',
          top: 8, bottom: 24, right: 24,
          width: 520,
          transform: open ? 'translateX(0)' : 'translateX(calc(100% + 24px))',
          opacity: open ? 1 : 0,
          transition: `transform ${OPEN_DUR}ms ${EASE}, opacity ${OPEN_DUR * 0.6}ms ${EASE} ${OPEN_DUR * 0.15}ms`,
          background: 'var(--paper-00)',
          border: '1px solid var(--paper-2)',
          borderRadius: 'var(--r-lg)',
          boxShadow: '0 30px 70px -24px rgba(28,24,18,.18), 0 10px 20px -8px rgba(28,24,18,.06)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          <ChatHeader/>
          <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>
            <ChatBubbleUser size="md" pageRef="2">Who is Marley and why is he dead to begin with?</ChatBubbleUser>
            <ChatBubbleAssist size="md" sources={[
              { quote: "Marley was dead, to begin with.", page: 1 },
              { quote: "partners for I don't know how many years.", page: 3 },
            ]}>
              Jacob Marley was Scrooge's <em>business partner</em>, dead seven years before the story opens. A ghost can only terrify if there's no doubt he's a ghost.
            </ChatBubbleAssist>
          </div>
          <div style={{ padding: '16px 24px 20px', borderTop: '1px solid var(--paper-2)', background: 'var(--paper-0)' }}>
            <Composer/>
          </div>
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// V2 Bottom sheet — book lifts up, sheet rises from bottom
// ─────────────────────────────────────────────────────────────
const AnimChatV2 = () => {
  const [open, replay] = useReplay();
  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative',
      background: 'radial-gradient(ellipse at center 30%, color-mix(in oklab, var(--paper-0) 92%, var(--paper-1)), var(--paper-0) 70%), var(--paper-0)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      fontFamily: 'var(--sans)',
    }}>
      <ReplayButton onClick={replay}/>
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

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {/* Book — lifts up slightly when sheet opens */}
        <div style={{
          position: 'absolute', top: 16, left: 80, right: 80,
          height: open ? 460 : 720,
          display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
          transition: `height ${OPEN_DUR}ms ${EASE}`,
        }}>
          <div style={{ width: 1100, maxWidth: '100%', height: '100%' }}>
            <BookSpread/>
          </div>
        </div>

        {/* Sheet — slides up from below */}
        <div style={{
          position: 'absolute', left: 80, right: 80, bottom: 0,
          height: 440,
          background: 'var(--paper-00)',
          borderTopLeftRadius: 20, borderTopRightRadius: 20,
          border: '1px solid var(--paper-2)', borderBottom: 0,
          boxShadow: '0 -20px 50px -16px rgba(28,24,18,.18)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
          transform: open ? 'translateY(0)' : 'translateY(100%)',
          transition: `transform ${OPEN_DUR}ms ${EASE}`,
        }}>
          <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 10 }}>
            <div style={{ width: 40, height: 4, borderRadius: 4, background: 'var(--paper-3)' }}/>
          </div>
          <ChatHeader/>
          <div style={{ flex: 1, overflow: 'auto', padding: '18px 28px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            <div>
              <ChatBubbleUser size="md" pageRef="2">Who is Marley?</ChatBubbleUser>
              <ChatBubbleAssist size="md" sources={[{ quote: "Marley was dead, to begin with.", page: 1 }]}>
                Scrooge's <em>business partner</em>, dead seven years before the story opens.
              </ChatBubbleAssist>
            </div>
            <div>
              <ChatBubbleUser size="md">Why emphasize this?</ChatBubbleUser>
              <ChatBubbleAssist size="md" streaming>
                A ghost can only terrify if there's no doubt he's a ghost. Dickens hammers the word <em>dead</em> early
              </ChatBubbleAssist>
            </div>
          </div>
          <div style={{ padding: '14px 28px 22px', borderTop: '1px solid var(--paper-2)', background: 'var(--paper-0)' }}>
            <Composer/>
          </div>
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// V3 Inline cards — cards flip-in from the highlighted phrase
// ─────────────────────────────────────────────────────────────
const AnimCard = ({ open, delay = 0, children, rotate = 0 }) => (
  <div style={{
    padding: '16px 18px',
    background: 'var(--paper-00)', border: '1px solid var(--paper-2)',
    borderLeft: '3px solid var(--accent)',
    borderRadius: 10,
    transform: open
      ? `translateX(0) rotate(${rotate}deg)`
      : `translateX(-40px) rotate(${rotate - 4}deg) scale(.95)`,
    opacity: open ? 1 : 0,
    transformOrigin: 'left center',
    transition: `transform ${OPEN_DUR}ms ${EASE} ${delay}ms, opacity ${OPEN_DUR * 0.7}ms ${EASE} ${delay}ms`,
    boxShadow: '0 4px 12px -4px rgba(28,24,18,.08)',
  }}>
    {children}
  </div>
);

const AnimChatV3 = () => {
  const [open, replay] = useReplay();
  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative',
      background: 'radial-gradient(ellipse at center 30%, color-mix(in oklab, var(--paper-0) 92%, var(--paper-1)), var(--paper-0) 70%), var(--paper-0)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      fontFamily: 'var(--sans)',
    }}>
      <ReplayButton onClick={replay}/>
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
        <div style={{ justifySelf: 'end' }}/>
      </div>

      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 24px', position: 'relative' }}>
        <div style={{
          position: 'relative',
          width: 1360, height: 720, maxHeight: 'calc(100vh - 160px)',
          display: 'grid', gridTemplateColumns: '1fr 380px',
          gap: 28, alignItems: 'stretch',
        }}>
          <div style={{ position: 'relative' }}>
            <BookSpread highlightPhrase={open ? 'scrooge-signed' : null}/>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, paddingTop: 40, position: 'relative' }}>
            <AnimCard open={open} delay={60} rotate={-0.3}>
              <div style={{ fontSize: 9.5, letterSpacing: 1.4, color: 'var(--accent-ink)', fontWeight: 600, marginBottom: 6 }}>
                ASKED ABOUT "Scrooge signed it." · p. 2
              </div>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 14, color: 'var(--ink-1)', lineHeight: 1.55, marginBottom: 10, fontStyle: 'italic' }}>
                Why does Dickens emphasize this?
              </div>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 14.5, color: 'var(--ink-0)', lineHeight: 1.65 }}>
                It's a legal ritual. Dickens binds Scrooge to Marley's death through the paper — not just <em>present</em>, but <em>responsible</em>.
              </div>
            </AnimCard>
            <AnimCard open={open} delay={200} rotate={0.2}>
              <div style={{ fontSize: 9.5, letterSpacing: 1.4, color: 'var(--accent-ink)', fontWeight: 600, marginBottom: 6 }}>
                ASKED ABOUT "door-nail" · p. 2
              </div>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 14, color: 'var(--ink-1)', lineHeight: 1.55, marginBottom: 10, fontStyle: 'italic' }}>
                Why a door-nail specifically?
              </div>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 14.5, color: 'var(--ink-0)', lineHeight: 1.65 }}>
                Proverbial — a door-nail was hammered flat, so could never be re-used.
              </div>
            </AnimCard>
            <div style={{
              padding: '12px 14px',
              background: 'var(--paper-00)', border: '1px dashed var(--paper-3)',
              borderRadius: 10, display: 'flex', alignItems: 'center', gap: 10,
              color: 'var(--ink-3)', fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 13,
              opacity: open ? 1 : 0,
              transition: `opacity ${OPEN_DUR}ms ${EASE} ${OPEN_DUR * 0.7}ms`,
            }}>
              <IcPlus size={12}/> Highlight text or click Ask to add a card
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// V4 Split — page slides to left column, chat fades in right
// ─────────────────────────────────────────────────────────────
const AnimChatV4 = () => {
  const [open, replay] = useReplay();
  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative',
      background: 'var(--paper-1)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      fontFamily: 'var(--sans)',
    }}>
      <ReplayButton onClick={replay}/>
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
            transition: `all ${OPEN_DUR}ms ${EASE}`,
          }}>
            <div style={{
              padding: '4px 12px', fontSize: 11, borderRadius: 999,
              background: open ? 'transparent' : 'var(--paper-00)',
              color: open ? 'var(--ink-2)' : 'var(--ink-0)',
              fontWeight: open ? 400 : 500,
              boxShadow: open ? 'none' : '0 1px 3px rgba(28,24,18,.08)',
              transition: `all ${OPEN_DUR}ms ${EASE}`,
            }}>Read</div>
            <div style={{
              padding: '4px 12px', fontSize: 11, borderRadius: 999,
              background: open ? 'var(--paper-00)' : 'transparent',
              color: open ? 'var(--ink-0)' : 'var(--ink-2)',
              fontWeight: open ? 500 : 400,
              boxShadow: open ? '0 1px 3px rgba(28,24,18,.08)' : 'none',
              transition: `all ${OPEN_DUR}ms ${EASE}`,
            }}>Read + Ask</div>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', minHeight: 0, position: 'relative' }}>
        {/* Reading column — slides from full-width to half */}
        <div style={{
          position: 'absolute', inset: 0,
          right: open ? '50%' : 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 40, borderRight: open ? '1px solid var(--paper-2)' : '0px solid transparent',
          background: 'var(--paper-1)',
          transition: `right ${OPEN_DUR}ms ${EASE}, border-right-color ${OPEN_DUR}ms ${EASE}`,
        }}>
          <div style={{
            width: '100%', maxWidth: 520, height: '100%', maxHeight: 720,
            transition: `max-width ${OPEN_DUR}ms ${EASE}`,
          }}>
            <BookSpread singlePage/>
          </div>
        </div>

        {/* Chat column — fades & slides in from right half */}
        <div style={{
          position: 'absolute', top: 0, bottom: 0, right: 0,
          width: '50%',
          display: 'flex', flexDirection: 'column', background: 'var(--paper-0)',
          transform: open ? 'translateX(0)' : 'translateX(20px)',
          opacity: open ? 1 : 0,
          transition: `transform ${OPEN_DUR}ms ${EASE} ${OPEN_DUR * 0.2}ms, opacity ${OPEN_DUR * 0.8}ms ${EASE} ${OPEN_DUR * 0.2}ms`,
        }}>
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
              { quote: "Scrooge was his sole executor", page: 3 },
            ]}>
              Jacob Marley was Scrooge's <em>business partner</em>, dead seven years before the story opens. A ghost can only terrify if there's no doubt he's a ghost.
            </ChatBubbleAssist>
          </div>
          <div style={{ padding: '18px 32px 24px', borderTop: '1px solid var(--paper-2)', background: 'var(--paper-00)' }}>
            <Composer size="lg"/>
          </div>
        </div>
      </div>
    </div>
  );
};

Object.assign(window, {
  AnimChatV1, AnimChatV2, AnimChatV3, AnimChatV4,
});
