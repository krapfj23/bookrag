// ─────────────────────────────────────────────────────────────
// V3 deep dive — atomic states + overflow strategies
// Reuses BookSpread, ChatBubbleUser/Assist, Composer, ChatHeader, IcPlus, etc.
// ─────────────────────────────────────────────────────────────

// Shared frame: header + book + right column
const V3Frame = ({ children, stateLabel, footer }) => (
  <div style={{
    width: '100%', height: '100%', position: 'relative',
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
        {stateLabel && (
          <div style={{
            padding: '4px 10px', background: 'var(--paper-1)', borderRadius: 999,
            fontSize: 10.5, color: 'var(--ink-2)', fontFamily: 'var(--mono)', fontWeight: 500,
          }}>{stateLabel}</div>
        )}
        <IcSearch size={13}/><IcBookmark size={13}/>
      </div>
    </div>

    {/* Stage */}
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 24px', minHeight: 0 }}>
      <div style={{
        position: 'relative',
        width: 1360, height: '100%', maxHeight: 720,
        display: 'grid', gridTemplateColumns: '1fr 400px',
        gap: 28, alignItems: 'stretch',
      }}>
        {children}
      </div>
    </div>

    {/* Footer */}
    <div style={{ padding: '12px 32px 16px', fontSize: 11, color: 'var(--ink-3)', display: 'flex', justifyContent: 'space-between' }}>
      {footer || <span>&nbsp;</span>}
      <span style={{ fontFamily: 'var(--mono)' }}>p. 2–3 / 176 · 3%</span>
    </div>
  </div>
);

// A single inline card
const V3Card = ({
  quote, page, question, answer, streaming, rotate = 0,
  offscreen, crossPage, longAnswer, pinned,
  kind = 'ask',  // 'ask' | 'note' | 'entity'
  children,
  actions = false,
}) => {
  const accent = {
    ask: 'var(--accent)',
    note: 'oklch(58% 0.1 55)',
    entity: 'oklch(58% 0.04 240)',
  }[kind];
  const accentSoft = {
    ask: 'var(--accent-ink)',
    note: 'oklch(30% 0.1 55)',
    entity: 'oklch(28% 0.04 240)',
  }[kind];

  return (
    <div style={{
      position: 'relative',
      padding: '14px 16px',
      background: 'var(--paper-00)',
      border: '1px solid var(--paper-2)',
      borderLeft: `3px solid ${accent}`,
      borderRadius: 10,
      transform: `rotate(${rotate}deg)`,
      boxShadow: '0 4px 12px -4px rgba(28,24,18,.08)',
      maxHeight: longAnswer ? 220 : 'none',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header strip */}
      <div style={{
        fontSize: 9.5, letterSpacing: 1.3, color: accentSoft, fontWeight: 600,
        marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6,
      }}>
        {offscreen && <span style={{ color: 'var(--ink-3)', fontWeight: 500 }}>↑ SCROLL UP · </span>}
        {crossPage && <span style={{ color: 'var(--ink-3)', fontWeight: 500 }}>← FROM p. 1 · </span>}
        {pinned && <IcBookmark size={9}/>}
        <span style={{ flex: 1 }}>ASKED ABOUT "{quote}" {page && `· p. ${page}`}</span>
        {actions && (
          <span style={{ display: 'flex', gap: 8, color: 'var(--ink-3)', fontWeight: 400 }}>
            <IcPlus size={10}/>
          </span>
        )}
      </div>

      {/* Question */}
      {question && (
        <div style={{
          fontFamily: 'var(--serif)', fontSize: 13.5, color: 'var(--ink-1)',
          lineHeight: 1.5, marginBottom: 8, fontStyle: 'italic',
        }}>
          {question}
        </div>
      )}

      {/* Answer — can scroll when long */}
      <div style={{
        fontFamily: 'var(--serif)', fontSize: 14, color: 'var(--ink-0)', lineHeight: 1.62,
        flex: 1, overflow: longAnswer ? 'auto' : 'visible',
        paddingRight: longAnswer ? 6 : 0,
        position: 'relative',
      }}>
        {answer}
        {streaming && (
          <span style={{
            display: 'inline-block', width: 6, height: 14,
            background: 'var(--ink-2)', verticalAlign: 'text-bottom',
            marginLeft: 3, animation: 'blink 1s infinite',
          }}/>
        )}
        {children}
      </div>
      {longAnswer && (
        <div style={{
          position: 'absolute', left: 16, right: 16, bottom: 0, height: 28,
          background: 'linear-gradient(to bottom, transparent, var(--paper-00))',
          pointerEvents: 'none',
        }}/>
      )}
    </div>
  );
};

// Follow-up (threaded reply) — rendered under a card, indented
const V3Followup = ({ question, answer, streaming }) => (
  <div style={{
    marginLeft: 14,
    paddingLeft: 14,
    borderLeft: '1px dashed var(--paper-3)',
    display: 'flex', flexDirection: 'column', gap: 8,
  }}>
    <div style={{
      display: 'flex', gap: 6, alignItems: 'baseline',
      fontFamily: 'var(--serif)', fontSize: 13, fontStyle: 'italic',
      color: 'var(--ink-1)', lineHeight: 1.5,
    }}>
      <span style={{
        fontFamily: 'var(--sans)', fontSize: 9.5, letterSpacing: 1,
        color: 'var(--ink-3)', fontWeight: 600, fontStyle: 'normal',
      }}>FOLLOW-UP</span>
      <span>{question}</span>
    </div>
    <div style={{
      fontFamily: 'var(--serif)', fontSize: 13.5, color: 'var(--ink-0)', lineHeight: 1.6,
    }}>
      {answer}
      {streaming && (
        <span style={{
          display: 'inline-block', width: 5, height: 13,
          background: 'var(--ink-2)', verticalAlign: 'text-bottom',
          marginLeft: 3, animation: 'blink 1s infinite',
        }}/>
      )}
    </div>
  </div>
);

// Invitation block — shown in empty state, or at the end of the column
const V3Invitation = ({ variant = 'empty' }) => {
  if (variant === 'add') {
    return (
      <div style={{
        padding: '12px 14px',
        background: 'var(--paper-00)', border: '1px dashed var(--paper-3)',
        borderRadius: 10, display: 'flex', alignItems: 'center', gap: 10,
        color: 'var(--ink-3)', fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 13,
      }}>
        <IcPlus size={12}/> Highlight text to ask
      </div>
    );
  }
  return (
    <div style={{
      padding: '28px 22px',
      background: 'var(--paper-00)', border: '1px dashed var(--paper-3)',
      borderRadius: 12,
      display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 10,
    }}>
      <div style={{
        width: 34, height: 34, borderRadius: 10,
        background: 'var(--accent-softer)', color: 'var(--accent-ink)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}><IcSpark size={14}/></div>
      <div style={{ fontFamily: 'var(--serif)', fontSize: 18, color: 'var(--ink-0)', letterSpacing: -0.1, lineHeight: 1.25 }}>
        Ask about what you're reading
      </div>
      <div style={{ fontFamily: 'var(--serif)', fontSize: 13.5, color: 'var(--ink-2)', lineHeight: 1.55 }}>
        Highlight any passage and tap <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 3,
          padding: '1px 7px', background: 'var(--accent-soft)', color: 'var(--accent-ink)',
          borderRadius: 999, fontSize: 11, fontWeight: 500, fontFamily: 'var(--sans)',
          fontStyle: 'normal',
        }}><IcSpark size={10}/> Ask</span>. Your question and the answer appear here, linked to the passage.
      </div>
      <div style={{
        marginTop: 6, paddingTop: 12, borderTop: '1px solid var(--paper-2)', width: '100%',
        display: 'flex', flexDirection: 'column', gap: 8,
      }}>
        <div style={{ fontSize: 10, letterSpacing: 1, textTransform: 'uppercase', color: 'var(--ink-3)', fontWeight: 500 }}>
          Try on this page
        </div>
        {['Who is Marley?', 'Why "as dead as a door-nail"?', 'What does Scrooge signing it mean?'].map((s, i) => (
          <div key={i} style={{
            padding: '8px 10px', background: 'var(--paper-0)', borderRadius: 8,
            fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 13,
            color: 'var(--ink-1)', cursor: 'pointer', border: '1px solid transparent',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{ color: 'var(--ink-3)', fontStyle: 'normal', fontFamily: 'var(--mono)', fontSize: 10 }}>{i + 1}</span>
            {s}
          </div>
        ))}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// V3 STATES
// ─────────────────────────────────────────────────────────────

// 1. Empty state
const V3_Empty = () => (
  <V3Frame stateLabel="empty · no cards yet" footer={<span>Highlight any passage to begin</span>}>
    <div><BookSpread/></div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, paddingTop: 48 }}>
      <V3Invitation variant="full"/>
    </div>
  </V3Frame>
);

// 2. Single card — first question on page
const V3_Single = () => (
  <V3Frame stateLabel="1 card" footer={<span>1 card on this spread</span>}>
    <div><BookSpread highlightPhrase="scrooge-signed"/></div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingTop: 40, position: 'relative' }}>
      <svg style={{ position: 'absolute', left: -28, top: 30, width: 60, height: 40, pointerEvents: 'none' }}>
        <path d="M 0 20 Q 20 0 60 10" stroke="var(--accent)" strokeWidth="1" fill="none" strokeDasharray="2 3" opacity="0.6"/>
      </svg>
      <V3Card
        quote="Scrooge signed it."
        page="2"
        question="Why does Dickens emphasize this?"
        answer={<>It's a legal ritual. Dickens binds Scrooge to Marley's death through the paper — not just <em>present</em> at the funeral, but <em>responsible</em> for what follows.</>}
        rotate={-0.3}
      />
      <V3Invitation variant="add"/>
    </div>
  </V3Frame>
);

// 3. Streaming answer
const V3_Streaming = () => (
  <V3Frame stateLabel="streaming" footer={<span>Answer streaming…</span>}>
    <div><BookSpread highlightPhrase="scrooge-signed"/></div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingTop: 40, position: 'relative' }}>
      <svg style={{ position: 'absolute', left: -28, top: 30, width: 60, height: 40, pointerEvents: 'none' }}>
        <path d="M 0 20 Q 20 0 60 10" stroke="var(--accent)" strokeWidth="1" fill="none" strokeDasharray="2 3" opacity="0.6"/>
      </svg>
      <V3Card
        quote="Scrooge signed it."
        page="2"
        question="Why does Dickens emphasize this?"
        answer={<>It's a legal ritual. Dickens binds Scrooge to Marley's death through the paper — not just <em>present</em>, but <em>responsible</em>. The single clipped sentence puts weight on the act, and the paperwork</>}
        streaming
        rotate={-0.3}
      />
      {/* Shimmer placeholder for a second card being thought about */}
      <div style={{
        padding: '14px 16px',
        background: 'color-mix(in oklab, var(--paper-00) 80%, var(--paper-1))',
        border: '1px dashed var(--paper-3)',
        borderRadius: 10,
        display: 'flex', flexDirection: 'column', gap: 8,
        opacity: 0.7,
      }}>
        <div style={{ height: 8, width: '60%', borderRadius: 4, background: 'var(--paper-2)' }}/>
        <div style={{ height: 8, width: '90%', borderRadius: 4, background: 'var(--paper-2)' }}/>
        <div style={{ height: 8, width: '40%', borderRadius: 4, background: 'var(--paper-2)' }}/>
        <div style={{ fontSize: 10, letterSpacing: 1, color: 'var(--ink-3)', fontFamily: 'var(--sans)', marginTop: 4, fontWeight: 500 }}>
          THINKING · gathering 3 more passages
        </div>
      </div>
    </div>
  </V3Frame>
);

// 4. Long answer (scrolls in card)
const V3_LongAnswer = () => (
  <V3Frame stateLabel="long answer · scrolls in card" footer={<span>Long answer — scrolls within the card</span>}>
    <div><BookSpread highlightPhrase="scrooge-signed"/></div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingTop: 40 }}>
      <V3Card
        quote="Scrooge signed it."
        page="2"
        question="Full reading — legal and narrative implications?"
        longAnswer
        rotate={-0.3}
        answer={
          <>
            <p style={{ margin: '0 0 10px' }}>It's a legal ritual. Dickens binds Scrooge to Marley's death through the paper — not just <em>present</em>, but <em>responsible</em>.</p>
            <p style={{ margin: '0 0 10px' }}>The single clipped sentence — "Scrooge signed it." — stands alone in its paragraph, and that's the point. Dickens isolates the act because the whole plot will turn on Scrooge's complicity with what Marley became.</p>
            <p style={{ margin: '0 0 10px' }}>There's also a legal specificity here. In 1843, "signing it" at a burial meant affirming the death to the parish authorities. The narrator has already stacked up the witnesses: the clergyman, the clerk, the undertaker. Scrooge is the fourth, and the most interested party.</p>
            <p style={{ margin: '0 0 10px' }}>Dickens will come back to signatures and legal papers throughout the tale — most notably when the Cratchits' fate hinges on what Scrooge is willing to sign for.</p>
          </>
        }
      />
      <V3Invitation variant="add"/>
    </div>
  </V3Frame>
);

// 5. Thread — follow-ups nested under a card
const V3_Thread = () => (
  <V3Frame stateLabel="thread · follow-ups" footer={<span>1 card · 2 follow-ups</span>}>
    <div><BookSpread highlightPhrase="scrooge-signed"/></div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 40, position: 'relative' }}>
      <svg style={{ position: 'absolute', left: -28, top: 30, width: 60, height: 40, pointerEvents: 'none' }}>
        <path d="M 0 20 Q 20 0 60 10" stroke="var(--accent)" strokeWidth="1" fill="none" strokeDasharray="2 3" opacity="0.6"/>
      </svg>
      <V3Card
        quote="Scrooge signed it."
        page="2"
        question="Why does Dickens emphasize this?"
        answer={<>It's a legal ritual. Dickens binds Scrooge to Marley's death through the paper — not just <em>present</em>, but <em>responsible</em>.</>}
        rotate={-0.3}
        pinned
      />
      <V3Followup
        question="Does this foreshadow Cratchit?"
        answer={<>Yes — the contrast is deliberate. Scrooge's reluctance with Fred's charity callers echoes this opening: he signed a burial paper, but will sign no gift.</>}
      />
      <V3Followup
        question="And the Ghost of Christmas Yet to Come?"
        answer={<>That Ghost reveals Scrooge's own unsigned grave. The arc is: Scrooge signs for Marley → refuses to sign for the poor →</>}
        streaming
      />
      <V3Invitation variant="add"/>
    </div>
  </V3Frame>
);

// 6. Off-screen anchor — card references a passage not currently in view
const V3_Offscreen = () => (
  <V3Frame stateLabel="off-screen anchor" footer={<span>Card references a passage higher up the page</span>}>
    <div style={{ position: 'relative' }}>
      <BookSpread/>
      {/* Indicator showing anchor is above */}
      <div style={{
        position: 'absolute', top: 120, right: -24, width: 4, height: 60,
        background: 'var(--accent)', borderRadius: 4, opacity: 0.6,
      }}/>
      <div style={{
        position: 'absolute', top: 90, right: -34, fontSize: 10, letterSpacing: 1,
        color: 'var(--accent-ink)', fontWeight: 600, writingMode: 'vertical-rl',
      }}>↑ ANCHOR</div>
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingTop: 340, position: 'relative' }}>
      <V3Card
        offscreen
        quote="Marley was dead"
        page="1"
        question="Is there irony in how plainly he states this?"
        answer={<>Completely. The bluntness is the joke — Dickens is about to give us a ghost, but first he insists, almost belligerently, that Marley is dead. The over-insistence is the set-up.</>}
        rotate={0.2}
        actions
      />
      <div style={{
        padding: '10px 12px',
        background: 'var(--accent-softer)',
        border: '1px dashed var(--accent)',
        borderRadius: 8,
        display: 'flex', alignItems: 'center', gap: 8,
        fontSize: 12, color: 'var(--accent-ink)', cursor: 'pointer',
        fontFamily: 'var(--sans)', fontWeight: 500,
      }}>
        <IcArrowL size={11}/> Jump to anchor on this page
      </div>
    </div>
  </V3Frame>
);

// 7. Cross-page reference — card from an earlier page
const V3_CrossPage = () => (
  <V3Frame stateLabel="cross-page reference" footer={<span>Card anchored to p. 1 · still visible on p. 2–3 spread</span>}>
    <div><BookSpread/></div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingTop: 40 }}>
      <V3Card
        crossPage
        quote="There is no doubt whatever about that."
        page="1"
        question="Why belabor it?"
        answer={<>The narrator is protesting too much — a classic Dickens feint. The certainty about Marley's death is the table being set for the ghost.</>}
        rotate={-0.2}
        actions
      />
      <V3Card
        quote="Scrooge signed it."
        page="2"
        question="Why does Dickens emphasize this?"
        answer={<>It's a legal ritual. Dickens binds Scrooge to Marley's death through the paper.</>}
        rotate={0.2}
      />
      <V3Invitation variant="add"/>
    </div>
  </V3Frame>
);

// ─────────────────────────────────────────────────────────────
// OVERFLOW STRATEGIES — many cards on one spread
// ─────────────────────────────────────────────────────────────

// Generate a bunch of cards for overflow tests
const SAMPLE_CARDS = [
  { quote: 'Marley was dead', page: '1', q: 'Irony in stating it plainly?', a: 'Completely. Over-insistence is the set-up.' },
  { quote: 'no doubt whatever', page: '1', q: 'Why belabor it?', a: 'The narrator protests too much — a Dickens feint.' },
  { quote: 'Scrooge signed it.', page: '2', q: 'Legal significance?', a: "Scrooge is bound through paper. He's not just present, he's responsible." },
  { quote: 'door-nail', page: '2', q: 'Why specifically?', a: 'A door-nail was hammered flat, never re-used. Proverbial for terminal.' },
  { quote: 'wisdom of our ancestors', page: '2', q: 'Whose voice is this?', a: 'The narrator breaking in — Dickens playing the garrulous storyteller.' },
  { quote: 'sole mourner', page: '3', q: 'What does "sole" hammer?', a: "Dickens repeats it five times. Scrooge is Marley's everything." },
  { quote: "dreadfully cut up", page: '3', q: 'Tone shift here?', a: 'Deadpan. Dickens turns grief into a business transaction.' },
];

// Strategy A: Scroll within the cards column
const V3_OverflowScroll = () => (
  <V3Frame stateLabel="overflow · column scrolls" footer={<span>7 cards · column scrolls independently</span>}>
    <div><BookSpread/></div>
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 40,
      overflow: 'auto', maxHeight: 720, paddingRight: 6, position: 'relative',
    }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 2,
        padding: '8px 10px', background: 'color-mix(in oklab, var(--paper-0) 80%, transparent)',
        backdropFilter: 'blur(6px)',
        borderRadius: 8, marginBottom: 2,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        fontSize: 10.5, letterSpacing: 1.2, color: 'var(--ink-3)', fontWeight: 600, textTransform: 'uppercase',
      }}>
        <span>7 cards on this spread</span>
        <span style={{ fontFamily: 'var(--mono)', letterSpacing: 0 }}>↕ scroll</span>
      </div>
      {SAMPLE_CARDS.map((c, i) => (
        <V3Card
          key={i}
          quote={c.quote}
          page={c.page}
          question={c.q}
          answer={c.a}
          rotate={i % 2 ? 0.2 : -0.2}
        />
      ))}
      <V3Invitation variant="add"/>
    </div>
  </V3Frame>
);

// Strategy B: Collapse older cards into 1-line summaries; expand the most recent
const V3_OverflowCollapse = () => (
  <V3Frame stateLabel="overflow · older cards collapse" footer={<span>Older cards collapse to 1 line — tap to expand</span>}>
    <div><BookSpread/></div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 40 }}>
      {/* Collapsed older cards */}
      {SAMPLE_CARDS.slice(0, 5).map((c, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '8px 12px',
          background: 'var(--paper-00)', border: '1px solid var(--paper-2)',
          borderLeft: '3px solid var(--accent)',
          borderRadius: 8,
          fontSize: 12.5, cursor: 'pointer',
        }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-3)', minWidth: 28 }}>p.{c.page}</span>
          <span style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', color: 'var(--ink-1)', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {c.q}
          </span>
          <IcChevron size={10}/>
        </div>
      ))}
      {/* Divider */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        margin: '6px 0 2px',
        fontSize: 10, letterSpacing: 1, color: 'var(--ink-3)', fontWeight: 500, textTransform: 'uppercase',
      }}>
        <span style={{ height: 1, flex: 1, background: 'var(--paper-2)' }}/>
        Latest · expanded
        <span style={{ height: 1, flex: 1, background: 'var(--paper-2)' }}/>
      </div>
      {/* Recent expanded */}
      <V3Card
        quote={SAMPLE_CARDS[5].quote}
        page={SAMPLE_CARDS[5].page}
        question={SAMPLE_CARDS[5].q}
        answer={SAMPLE_CARDS[5].a}
        rotate={-0.2}
      />
      <V3Card
        quote={SAMPLE_CARDS[6].quote}
        page={SAMPLE_CARDS[6].page}
        question={SAMPLE_CARDS[6].q}
        answer={SAMPLE_CARDS[6].a}
        rotate={0.2}
      />
      <V3Invitation variant="add"/>
    </div>
  </V3Frame>
);

// Strategy C: Stack / pile — latest on top, old ones fan behind
const V3_OverflowStack = () => (
  <V3Frame stateLabel="overflow · pile of cards" footer={<span>Older cards fan behind — peel back to read</span>}>
    <div><BookSpread/></div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingTop: 40, position: 'relative' }}>
      {/* Pile — absolutely positioned sheets */}
      <div style={{ position: 'relative', height: 220 }}>
        {SAMPLE_CARDS.slice(0, 4).map((c, i) => (
          <div key={i} style={{
            position: 'absolute', left: i * 4, top: i * 4, right: -i * 4,
            padding: '10px 14px',
            background: 'var(--paper-00)', border: '1px solid var(--paper-2)',
            borderLeft: '3px solid var(--accent)',
            borderRadius: 8,
            transform: `rotate(${i % 2 ? 0.4 : -0.5}deg)`,
            boxShadow: '0 3px 8px -3px rgba(28,24,18,.1)',
            zIndex: i,
            opacity: 1 - i * 0.05,
          }}>
            <div style={{ fontSize: 9.5, letterSpacing: 1.3, color: 'var(--accent-ink)', fontWeight: 600, marginBottom: 4 }}>
              p. {c.page} · "{c.quote}"
            </div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 13, fontStyle: 'italic', color: 'var(--ink-1)' }}>
              {c.q}
            </div>
          </div>
        ))}
        {/* Top card — the current, fully readable one */}
        <div style={{
          position: 'absolute', left: 16, top: 16, right: -16,
          padding: '14px 16px',
          background: 'var(--paper-00)', border: '1px solid var(--paper-2)',
          borderLeft: '3px solid var(--accent)',
          borderRadius: 10,
          transform: 'rotate(-0.2deg)',
          boxShadow: '0 8px 20px -6px rgba(28,24,18,.15)',
          zIndex: 10,
        }}>
          <div style={{ fontSize: 9.5, letterSpacing: 1.3, color: 'var(--accent-ink)', fontWeight: 600, marginBottom: 6 }}>
            ASKED ABOUT "{SAMPLE_CARDS[6].quote}" · p. {SAMPLE_CARDS[6].page}
          </div>
          <div style={{ fontFamily: 'var(--serif)', fontSize: 13.5, color: 'var(--ink-1)', lineHeight: 1.5, marginBottom: 8, fontStyle: 'italic' }}>
            {SAMPLE_CARDS[6].q}
          </div>
          <div style={{ fontFamily: 'var(--serif)', fontSize: 14, color: 'var(--ink-0)', lineHeight: 1.62 }}>
            {SAMPLE_CARDS[6].a}
          </div>
        </div>
      </div>
      <div style={{
        padding: '8px 12px',
        background: 'var(--paper-0)', borderRadius: 8,
        fontSize: 11, color: 'var(--ink-3)', fontFamily: 'var(--sans)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{ letterSpacing: 0.8, fontWeight: 500, textTransform: 'uppercase', fontSize: 10 }}>
          6 cards beneath · newest on top
        </span>
        <span style={{ cursor: 'pointer', color: 'var(--accent-ink)', fontWeight: 500 }}>Browse all →</span>
      </div>
      <V3Invitation variant="add"/>
    </div>
  </V3Frame>
);

// Strategy D: Margin-dot mode — all older cards become small dots in the left margin; 2 latest expanded
const V3_OverflowDots = () => (
  <V3Frame stateLabel="overflow · margin dots" footer={<span>Older cards become margin dots — tap to reveal</span>}>
    <div style={{ position: 'relative' }}>
      <BookSpread/>
      {/* Margin dots on left page */}
      <div style={{
        position: 'absolute',
        left: -14, top: 60, bottom: 60,
        width: 10,
        display: 'flex', flexDirection: 'column',
        gap: 6,
      }}>
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} style={{
            width: 10, height: 10, borderRadius: 999,
            background: 'var(--accent)', opacity: 0.55 + i * 0.08,
            boxShadow: '0 0 0 3px color-mix(in oklab, var(--paper-0) 60%, transparent)',
            cursor: 'pointer',
            marginTop: i * 8,
          }}/>
        ))}
      </div>
      <div style={{
        position: 'absolute', left: -6, top: 30, fontSize: 9.5, letterSpacing: 1,
        color: 'var(--accent-ink)', fontWeight: 600, writingMode: 'vertical-rl', transform: 'rotate(180deg)',
      }}>5 EARLIER CARDS</div>
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingTop: 40 }}>
      <V3Card
        quote={SAMPLE_CARDS[5].quote}
        page={SAMPLE_CARDS[5].page}
        question={SAMPLE_CARDS[5].q}
        answer={SAMPLE_CARDS[5].a}
        rotate={-0.2}
      />
      <V3Card
        quote={SAMPLE_CARDS[6].quote}
        page={SAMPLE_CARDS[6].page}
        question={SAMPLE_CARDS[6].q}
        answer={SAMPLE_CARDS[6].a}
        rotate={0.2}
      />
      <V3Invitation variant="add"/>
    </div>
  </V3Frame>
);

Object.assign(window, {
  V3_Empty, V3_Single, V3_Streaming, V3_LongAnswer, V3_Thread,
  V3_Offscreen, V3_CrossPage,
  V3_OverflowScroll, V3_OverflowCollapse, V3_OverflowStack, V3_OverflowDots,
});
