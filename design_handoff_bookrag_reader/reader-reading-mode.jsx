// ─────────────────────────────────────────────────────────────
// READING MODE — no sidebar; pure two-page spread with indicators
// Conservative: highlights + underlines preserved; thin hairline chrome
// Ambitious: adds hover-reveal note peek, chapter pacing, ambient paper
// ─────────────────────────────────────────────────────────────

// A reading-mode-aware BookSpread that renders phrase indicators:
// - Asked-about phrases → dark green highlight
// - Noted phrases → underline
// Shared between the two variants so they read consistently.
const ReadingSpread = ({ variant = 'conservative', onHoverNote, hoveredNote }) => {
  const pageStyle = {
    padding: variant === 'ambitious' ? '64px 72px 56px' : '56px 60px 48px',
    display: 'flex', flexDirection: 'column',
    minWidth: 0,
  };
  const chap = { fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 11.5, color: 'var(--ink-3)', letterSpacing: 0.4, marginBottom: 6 };
  const head = { fontFamily: 'var(--serif)', fontWeight: 400, fontSize: 24, letterSpacing: -0.3, color: 'var(--ink-0)', margin: '0 0 22px' };
  const prose = {
    fontFamily: 'var(--serif)',
    fontSize: variant === 'ambitious' ? 16 : 15,
    lineHeight: 1.72,
    color: 'var(--ink-0)',
    textAlign: 'justify',
    hyphens: 'auto',
    flex: 1,
    minWidth: 0,
    textWrap: 'pretty',
  };
  const folio = {
    marginTop: 'auto', paddingTop: 24,
    display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
    fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 11,
    color: 'var(--ink-3)', letterSpacing: 0.3,
  };

  // Highlight / note styling — these are persistent markers of prior activity
  const asked = {
    background: 'oklch(72% 0.08 155 / 0.42)',
    color: 'var(--ink-0)',
    padding: '1px 3px',
    borderRadius: 2,
    cursor: 'pointer',
    transition: 'background 180ms ease',
  };
  const noted = {
    textDecoration: 'underline',
    textDecorationColor: 'oklch(58% 0.1 55)',
    textDecorationThickness: 1.5,
    textUnderlineOffset: 3,
    cursor: 'pointer',
  };
  const entity = {
    textDecoration: 'underline',
    textDecorationStyle: 'dotted',
    textDecorationColor: 'var(--accent)',
    textUnderlineOffset: 3,
  };

  const LeftPage = (
    <div style={pageStyle}>
      <div style={chap}>Stave I</div>
      <div style={head}>Marley's Ghost</div>
      <div style={prose}>
        <p style={{ margin: '0 0 14px' }} className="dropcap">
          Marley was dead, to begin with.{' '}
          <span style={asked} data-asked>There is no doubt whatever about that.</span>{' '}
          The register of his burial was signed by the clergyman, the clerk, the undertaker, and the chief mourner.{' '}
          <span style={asked} data-asked>Scrooge signed it.</span>
          {' '}And Scrooge's name was good upon 'Change for anything he chose to put his hand to.
        </p>
        <p style={{ margin: '0 0 14px' }}>
          Old Marley was as dead as a{' '}
          <span style={entity}>door-nail</span>. Mind! I don't mean to say that I know, of my own knowledge, what there is particularly dead about a door-nail.
          {' '}I might have been inclined, myself, to regard a coffin-nail as the deadest piece of ironmongery in the trade.
        </p>
        <p style={{ margin: '0 0 14px' }}>
          But the wisdom of our ancestors is in the simile; and my unhallowed hands shall not disturb it, or the Country's done for. You will therefore permit me to repeat, emphatically, that{' '}
          <span
            style={{
              ...noted,
              ...(hoveredNote === 'marley-dead' ? { background: 'oklch(92% 0.04 55 / 0.8)' } : null),
            }}
            data-note="marley-dead"
            onMouseEnter={onHoverNote ? () => onHoverNote('marley-dead') : undefined}
            onMouseLeave={onHoverNote ? () => onHoverNote(null) : undefined}
          >Marley was as dead as a door-nail</span>.
        </p>
        <p style={{ margin: '0 0 14px' }}>
          Scrooge knew he was dead? Of course he did. How could it be otherwise? Scrooge and he were partners for I don't know how many years.
        </p>
      </div>
      <div style={folio}><span>Charles Dickens</span><span style={{ fontFamily: 'var(--mono)' }}>2</span></div>
    </div>
  );

  const RightPage = (
    <div style={pageStyle}>
      <div style={{ ...prose, marginTop: 0 }}>
        <p style={{ margin: '0 0 14px' }}>
          Scrooge was his{' '}
          <span style={entity}>sole executor</span>, his sole administrator, his sole assign, his{' '}
          <span
            style={{
              ...noted,
              ...(hoveredNote === 'sole-mourner' ? { background: 'oklch(92% 0.04 55 / 0.8)' } : null),
            }}
            data-note="sole-mourner"
            onMouseEnter={onHoverNote ? () => onHoverNote('sole-mourner') : undefined}
            onMouseLeave={onHoverNote ? () => onHoverNote(null) : undefined}
          >sole residuary legatee, his sole friend, and sole mourner</span>.
        </p>
        <p style={{ margin: '0 0 14px' }}>
          And even Scrooge was not so dreadfully cut up by the sad event, but that he was an excellent man of business on the very day of the funeral, and solemnised it with an undoubted bargain.
        </p>
        <p style={{ margin: '0 0 14px' }}>
          The mention of Marley's funeral brings me back to the point I started from. There is no doubt that Marley was dead. This must be distinctly understood, or nothing wonderful can come of the story I am going to relate.
        </p>
        <p style={{ margin: '0 0 14px' }}>
          If we were not perfectly convinced that Hamlet's Father died before the play began, there would be nothing more remarkable in his taking a stroll at night,{' '}
          <span style={asked} data-asked>in an easterly wind</span>, upon his own ramparts, than there would be in any other middle-aged gentleman rashly turning out after dark in a breezy spot—say Saint Paul's Churchyard for instance—literally to astonish his son's weak mind.
        </p>
      </div>
      <div style={folio}><span style={{ fontFamily: 'var(--mono)' }}>3</span><span>Marley's Ghost</span></div>
    </div>
  );

  return (
    <div style={{
      background: 'var(--paper-00)',
      boxShadow: variant === 'ambitious'
        ? '0 50px 120px -40px rgba(28,24,18,.28), 0 20px 40px -16px rgba(28,24,18,.1)'
        : '0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)',
      borderRadius: 3,
      display: 'grid', gridTemplateColumns: '1fr 1fr',
      width: '100%', height: '100%', position: 'relative',
    }}>
      {LeftPage}
      <div style={{
        position: 'absolute', left: '50%', top: 0, bottom: 0, width: 40,
        transform: 'translateX(-50%)', pointerEvents: 'none',
        background: 'linear-gradient(to right, transparent 0%, color-mix(in oklab, var(--ink-0) 7%, transparent) 50%, transparent 100%)',
      }}/>
      {RightPage}
    </div>
  );
};

// ─── Shared top-bar chrome (minimal) ────────────────────────
const ReadingTopBar = ({ isReading, onToggle }) => (
  <div style={{
    display: 'grid', gridTemplateColumns: '1fr auto 1fr',
    alignItems: 'center', padding: '14px 28px', height: 52, boxSizing: 'border-box',
    opacity: isReading ? 0.55 : 1,
    transition: 'opacity 240ms ease',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--ink-2)', fontSize: 12 }}>
      <IcArrowL size={13}/> Library
    </div>
    <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 14, color: 'var(--ink-1)' }}>
      A Christmas Carol · <span style={{ color: 'var(--ink-3)', fontStyle: 'normal' }}>Dickens</span>
    </div>
    <div style={{ justifySelf: 'end', display: 'flex', gap: 10, color: 'var(--ink-2)', alignItems: 'center' }}>
      <IcSearch size={13}/>
      <IcBookmark size={13}/>
      {/* Reading mode toggle */}
      <div
        onClick={onToggle}
        style={{
          padding: '5px 12px', borderRadius: 999,
          background: isReading ? 'var(--ink-0)' : 'var(--paper-1)',
          color: isReading ? 'var(--paper-00)' : 'var(--ink-1)',
          fontSize: 11, fontWeight: 500,
          display: 'inline-flex', alignItems: 'center', gap: 6,
          fontFamily: 'var(--sans)', cursor: 'pointer',
          marginLeft: 4,
          transition: 'background 200ms ease, color 200ms ease',
        }}
      >
        {isReading ? <><IcCheck size={10}/> Reading</> : <>Reading mode</>}
      </div>
    </div>
  </div>
);

// ─── Legend that explains the indicators (only in reading mode) ─
const ReadingLegend = ({ show }) => (
  <div style={{
    position: 'absolute',
    bottom: 28, left: '50%', transform: 'translateX(-50%)',
    display: 'flex', gap: 18, alignItems: 'center',
    fontSize: 10.5, color: 'var(--ink-3)', letterSpacing: 0.6, fontWeight: 500,
    fontFamily: 'var(--sans)',
    opacity: show ? 1 : 0,
    transition: 'opacity 260ms ease 180ms',
    pointerEvents: 'none',
  }}>
    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        display: 'inline-block', width: 14, height: 10,
        background: 'oklch(72% 0.08 155 / 0.42)', borderRadius: 2,
      }}/>
      ASKED
    </span>
    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        display: 'inline-block', width: 14, height: 2,
        background: 'oklch(58% 0.1 55)', marginBottom: -2,
      }}/>
      NOTED
    </span>
    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        display: 'inline-block', width: 14, height: 0,
        borderBottom: '1.5px dotted var(--accent)', marginBottom: -1,
      }}/>
      ENTITY
    </span>
  </div>
);

// ─── Thin progress hairline at the bottom edge ──────────────
const ProgressHairline = ({ pct = 3 }) => (
  <div style={{
    position: 'absolute', bottom: 0, left: 0, right: 0, height: 3,
    background: 'color-mix(in oklab, var(--paper-2) 60%, transparent)',
  }}>
    <div style={{
      height: '100%', width: `${pct}%`,
      background: 'var(--accent)',
      transition: 'width 400ms ease',
    }}/>
  </div>
);

// ─────────────────────────────────────────────────────────────
// Sample cards that match the phrases on the reading spread —
// used by the OFF state sidebar so the page indicators correspond
// to real entries in the margin.
// ─────────────────────────────────────────────────────────────
const READING_CARDS = [
  {
    kind: 'ask',
    quote: 'There is no doubt whatever',
    page: '2',
    q: 'Why belabor the point this hard?',
    a: <>The narrator is protesting too much — a classic Dickens feint. The certainty about Marley's death is the table being set for the ghost.</>,
    rotate: -0.2,
  },
  {
    kind: 'note',
    quote: 'Marley was as dead as a door-nail',
    page: '2',
    q: null,
    a: <>Dickens hammers it four times in two pages. The over-insistence is the joke — and the set-up for the ghost.</>,
    rotate: 0.2,
    isNote: true,
  },
  {
    kind: 'note',
    quote: 'sole mourner',
    page: '3',
    q: null,
    a: <>Five "soles" in one sentence. Scrooge is Marley's entire world, legally and otherwise.</>,
    rotate: -0.15,
    isNote: true,
  },
  {
    kind: 'ask',
    quote: 'in an easterly wind',
    page: '3',
    q: 'Why specify the wind?',
    a: <>Dickens is doing standup — pretending to worry about the logistics of a ghost taking a walk. Deadpan setup for a ghost story.</>,
    rotate: 0.3,
  },
];

const ReadingSidebar = () => (
  <div style={{
    display: 'flex', flexDirection: 'column', gap: 12,
    paddingTop: 40, overflow: 'hidden',
  }}>
    <div style={{
      fontSize: 10, letterSpacing: 1.2, color: 'var(--ink-3)', fontWeight: 600,
      textTransform: 'uppercase', fontFamily: 'var(--sans)',
      display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
      padding: '0 2px',
    }}>
      <span>Notes &amp; asks · this spread</span>
      <span style={{ fontFamily: 'var(--mono)', letterSpacing: 0, fontWeight: 500 }}>4</span>
    </div>
    {READING_CARDS.map((c, i) => {
      const isNote = c.isNote;
      const accent = isNote ? 'oklch(58% 0.1 55)' : 'var(--accent)';
      const accentInk = isNote ? 'oklch(30% 0.1 55)' : 'var(--accent-ink)';
      return (
        <div key={i} style={{
          padding: '12px 14px',
          background: 'var(--paper-00)',
          border: '1px solid var(--paper-2)',
          borderLeft: `3px solid ${accent}`,
          borderRadius: 10,
          transform: `rotate(${c.rotate}deg)`,
          boxShadow: '0 4px 12px -4px rgba(28,24,18,.08)',
        }}>
          <div style={{
            fontSize: 9.5, letterSpacing: 1.3, color: accentInk, fontWeight: 600,
            marginBottom: 6,
          }}>
            {isNote ? 'NOTE' : 'ASKED'} ON "{c.quote}" · p. {c.page}
          </div>
          {c.q && (
            <div style={{
              fontFamily: 'var(--serif)', fontSize: 12.5, fontStyle: 'italic',
              color: 'var(--ink-1)', lineHeight: 1.5, marginBottom: 6,
            }}>
              {c.q}
            </div>
          )}
          <div style={{
            fontFamily: 'var(--serif)', fontSize: 13, color: 'var(--ink-0)', lineHeight: 1.55,
          }}>
            {c.a}
          </div>
        </div>
      );
    })}
    <div style={{
      padding: '10px 12px',
      background: 'var(--paper-00)', border: '1px dashed var(--paper-3)',
      borderRadius: 10, display: 'flex', alignItems: 'center', gap: 8,
      color: 'var(--ink-3)', fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 12.5,
    }}>
      <IcPlus size={11}/> Highlight text to ask or note
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// CONSERVATIVE — sidebar (with real cards) OFF ↔ reading mode ON
// ─────────────────────────────────────────────────────────────
const ReadingModeConservative = ({ initialReading = true }) => {
  const [reading, setReading] = React.useState(initialReading);
  const SIDEBAR_W = 380;

  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative', overflow: 'hidden',
      background: reading
        ? 'var(--paper-0)'
        : 'radial-gradient(ellipse at center 30%, color-mix(in oklab, var(--paper-0) 92%, var(--paper-1)), var(--paper-0) 70%), var(--paper-0)',
      display: 'flex', flexDirection: 'column',
      fontFamily: 'var(--sans)',
      transition: 'background 320ms ease',
    }}>
      <ReadingTopBar isReading={reading} onToggle={() => setReading(r => !r)}/>

      <div style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: reading ? `1fr 0px` : `1fr ${SIDEBAR_W}px`,
        columnGap: reading ? 0 : 28,
        alignItems: 'stretch',
        padding: reading ? '0 120px 40px' : '0 28px 24px',
        minHeight: 0,
        transition: 'grid-template-columns 320ms ease, column-gap 320ms ease, padding 320ms ease',
      }}>
        <div style={{
          display: 'flex', alignItems: 'stretch', justifyContent: 'center',
          minHeight: 0, minWidth: 0,
        }}>
          <div style={{
            width: '100%',
            maxWidth: reading ? 1200 : 1100,
            height: '100%',
            transition: 'max-width 320ms ease',
            display: 'flex',
          }}>
            <ReadingSpread variant="conservative"/>
          </div>
        </div>

        {/* Sidebar — hidden when reading */}
        <div style={{
          overflow: 'hidden',
          opacity: reading ? 0 : 1,
          transform: `translateX(${reading ? 40 : 0}px)`,
          transition: 'opacity 220ms ease, transform 320ms ease',
          pointerEvents: reading ? 'none' : 'auto',
        }}>
          {!reading && <ReadingSidebar/>}
        </div>
      </div>

      <ReadingLegend show={reading}/>
      <ProgressHairline pct={3}/>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// AMBITIOUS — wider margins, ambient paper, note peek, breathing
// ─────────────────────────────────────────────────────────────
const ReadingModeAmbitious = ({ initialReading = true }) => {
  const [reading, setReading] = React.useState(initialReading);
  const [hoveredNote, setHoveredNote] = React.useState(null);
  const SIDEBAR_W = 380;

  // Content of the two notes, keyed by data-note attribute
  const notes = {
    'marley-dead': {
      title: 'Your note',
      body: 'Dickens hammers it four times in two pages. The over-insistence is the joke — and the set-up for the ghost.',
      when: '2 days ago',
    },
    'sole-mourner': {
      title: 'Your note',
      body: 'Five "soles" in one sentence. Scrooge is Marley\'s entire world, legally and otherwise.',
      when: 'last week',
    },
  };

  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative', overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
      fontFamily: 'var(--sans)',
      background: reading
        // Ambient vignette + warm paper when in reading mode
        ? 'radial-gradient(ellipse 80% 60% at center 40%, oklch(96% 0.012 85), oklch(93% 0.015 80) 80%)'
        : 'radial-gradient(ellipse at center 30%, color-mix(in oklab, var(--paper-0) 92%, var(--paper-1)), var(--paper-0) 70%), var(--paper-0)',
      transition: 'background 420ms ease',
    }}>
      <ReadingTopBar isReading={reading} onToggle={() => setReading(r => !r)}/>

      {/* Title card — chapter pacing — only shows in reading mode */}
      <div style={{
        position: 'absolute', top: 64, left: 0, right: 0,
        textAlign: 'center',
        fontFamily: 'var(--serif)', fontStyle: 'italic',
        fontSize: 12, color: 'var(--ink-3)', letterSpacing: 1.4,
        textTransform: 'uppercase',
        opacity: reading ? 0.7 : 0,
        transform: `translateY(${reading ? 0 : -8}px)`,
        transition: 'opacity 320ms ease 120ms, transform 320ms ease 120ms',
        pointerEvents: 'none',
      }}>
        Stave One · of five
      </div>

      <div style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: reading ? `1fr 0px` : `1fr ${SIDEBAR_W}px`,
        columnGap: reading ? 0 : 28,
        alignItems: 'stretch',
        padding: reading ? '32px 180px 64px' : '0 28px 24px',
        minHeight: 0,
        transition: 'grid-template-columns 420ms cubic-bezier(.2,.7,.2,1), column-gap 420ms cubic-bezier(.2,.7,.2,1), padding 420ms cubic-bezier(.2,.7,.2,1)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'stretch', justifyContent: 'center',
          minHeight: 0, minWidth: 0,
        }}>
          <div style={{
            width: '100%',
            maxWidth: reading ? 1240 : 1100,
            height: '100%',
            transition: 'max-width 420ms cubic-bezier(.2,.7,.2,1)',
            position: 'relative',
            display: 'flex',
          }}>
            <ReadingSpread
              variant="ambitious"
              onHoverNote={reading ? setHoveredNote : null}
              hoveredNote={hoveredNote}
            />

            {/* Note peek popover */}
            {reading && hoveredNote && (
              <div style={{
                position: 'absolute',
                left: '50%', bottom: -20, transform: 'translate(-50%, 100%)',
                background: 'var(--paper-00)',
                border: '1px solid var(--paper-2)',
                borderLeft: '3px solid oklch(58% 0.1 55)',
                borderRadius: 10,
                padding: '12px 16px',
                width: 360,
                boxShadow: '0 20px 40px -12px rgba(28,24,18,.2)',
                animation: 'fadeIn 180ms ease',
                zIndex: 10,
              }}>
                <div style={{
                  fontSize: 9.5, letterSpacing: 1.3, color: 'oklch(30% 0.1 55)',
                  fontWeight: 600, marginBottom: 6,
                  display: 'flex', justifyContent: 'space-between',
                }}>
                  <span>{notes[hoveredNote].title.toUpperCase()}</span>
                  <span style={{ color: 'var(--ink-3)', fontWeight: 500 }}>{notes[hoveredNote].when}</span>
                </div>
                <div style={{
                  fontFamily: 'var(--serif)', fontSize: 13.5,
                  color: 'var(--ink-0)', lineHeight: 1.55,
                }}>
                  {notes[hoveredNote].body}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar — hidden when reading */}
        <div style={{
          overflow: 'hidden',
          opacity: reading ? 0 : 1,
          transform: `translateX(${reading ? 40 : 0}px)`,
          transition: 'opacity 260ms ease, transform 420ms cubic-bezier(.2,.7,.2,1)',
          pointerEvents: reading ? 'none' : 'auto',
        }}>
          {!reading && <ReadingSidebar/>}
        </div>
      </div>

      <ReadingLegend show={reading}/>

      {/* Page turn arrows — reveal only at edges, faint */}
      {reading && (
        <>
          <div style={{
            position: 'absolute', left: 40, top: '50%', transform: 'translateY(-50%)',
            width: 48, height: 48, borderRadius: 999,
            background: 'var(--paper-00)',
            border: '1px solid var(--paper-2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--ink-2)', cursor: 'pointer', opacity: 0.5,
            boxShadow: '0 8px 20px -8px rgba(28,24,18,.15)',
          }}><IcArrowL size={14}/></div>
          <div style={{
            position: 'absolute', right: 40, top: '50%', transform: 'translateY(-50%)',
            width: 48, height: 48, borderRadius: 999,
            background: 'var(--paper-00)',
            border: '1px solid var(--paper-2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--ink-2)', cursor: 'pointer', opacity: 0.5,
            boxShadow: '0 8px 20px -8px rgba(28,24,18,.15)',
          }}><IcArrowR size={14}/></div>
        </>
      )}

      <ProgressHairline pct={3}/>
    </div>
  );
};

// Variants also rendered in "off" state so we can see the before/after
const ReadingModeConservativeOff = () => <ReadingModeConservative initialReading={false}/>;
const ReadingModeAmbitiousOff    = () => <ReadingModeAmbitious    initialReading={false}/>;

// Ambitious with a note hovered, to showcase the peek affordance
const ReadingModeAmbitiousHover = () => {
  const [, setHover] = React.useState('sole-mourner');
  return (
    <ReadingModeAmbitiousWithForcedHover/>
  );
};
const ReadingModeAmbitiousWithForcedHover = () => {
  // Render ambitious mode with a note pre-hovered for the artboard thumbnail
  const [hoveredNote, setHoveredNote] = React.useState('sole-mourner');
  const reading = true;
  const notes = {
    'marley-dead': {
      title: 'Your note',
      body: 'Dickens hammers it four times in two pages. The over-insistence is the joke — and the set-up for the ghost.',
      when: '2 days ago',
    },
    'sole-mourner': {
      title: 'Your note',
      body: 'Five "soles" in one sentence. Scrooge is Marley\'s entire world, legally and otherwise.',
      when: 'last week',
    },
  };
  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative', overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
      fontFamily: 'var(--sans)',
      background: 'radial-gradient(ellipse 80% 60% at center 40%, oklch(96% 0.012 85), oklch(93% 0.015 80) 80%)',
    }}>
      <ReadingTopBar isReading={reading} onToggle={() => {}}/>
      <div style={{
        position: 'absolute', top: 64, left: 0, right: 0,
        textAlign: 'center',
        fontFamily: 'var(--serif)', fontStyle: 'italic',
        fontSize: 12, color: 'var(--ink-3)', letterSpacing: 1.4,
        textTransform: 'uppercase', opacity: 0.7, pointerEvents: 'none',
      }}>Stave One · of five</div>
      <div style={{
        flex: 1, display: 'flex', alignItems: 'stretch', justifyContent: 'center',
        padding: '32px 180px 64px', minHeight: 0, minWidth: 0,
      }}>
        <div style={{
          width: '100%', maxWidth: 1240, height: '100%', position: 'relative',
          display: 'flex',
        }}>
          <ReadingSpread variant="ambitious" onHoverNote={setHoveredNote} hoveredNote={hoveredNote}/>
          {hoveredNote && (
            <div style={{
              position: 'absolute',
              left: '50%', bottom: -20, transform: 'translate(-50%, 100%)',
              background: 'var(--paper-00)',
              border: '1px solid var(--paper-2)',
              borderLeft: '3px solid oklch(58% 0.1 55)',
              borderRadius: 10, padding: '12px 16px', width: 360,
              boxShadow: '0 20px 40px -12px rgba(28,24,18,.2)', zIndex: 10,
            }}>
              <div style={{
                fontSize: 9.5, letterSpacing: 1.3, color: 'oklch(30% 0.1 55)',
                fontWeight: 600, marginBottom: 6,
                display: 'flex', justifyContent: 'space-between',
              }}>
                <span>{notes[hoveredNote].title.toUpperCase()}</span>
                <span style={{ color: 'var(--ink-3)', fontWeight: 500 }}>{notes[hoveredNote].when}</span>
              </div>
              <div style={{
                fontFamily: 'var(--serif)', fontSize: 13.5,
                color: 'var(--ink-0)', lineHeight: 1.55,
              }}>{notes[hoveredNote].body}</div>
            </div>
          )}
        </div>
      </div>
      <ReadingLegend show/>
      <ProgressHairline pct={3}/>
    </div>
  );
};

Object.assign(window, {
  ReadingModeConservative, ReadingModeConservativeOff,
  ReadingModeAmbitious, ReadingModeAmbitiousOff,
  ReadingModeAmbitiousHover, ReadingModeAmbitiousWithForcedHover,
});
