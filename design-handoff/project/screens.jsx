// screens.jsx — three screens: Library, Reading+Chat, Upload/Pipeline.

// Sample data
const BOOKS = [
  { id: 1, title: 'A Christmas Carol', author: 'Charles Dickens', page: 48, total: 96, mood: 'sage', lastRead: '2 hours ago' },
  { id: 2, title: 'Red Rising', author: 'Pierce Brown', page: 142, total: 432, mood: 'charcoal', lastRead: 'Yesterday' },
  { id: 3, title: 'The Left Hand of Darkness', author: 'Ursula K. Le Guin', page: 210, total: 304, mood: 'slate', lastRead: '3 days ago' },
  { id: 4, title: 'Piranesi', author: 'Susanna Clarke', page: 88, total: 272, mood: 'paper', lastRead: '1 week ago' },
  { id: 5, title: 'The Remains of the Day', author: 'Kazuo Ishiguro', page: 254, total: 254, mood: 'amber', lastRead: 'Finished' },
  { id: 6, title: 'Gilead', author: 'Marilynne Robinson', page: 12, total: 247, mood: 'rose', lastRead: 'Just started' },
];

// ── Library screen ──────────────────────────────────────────────
const LibraryScreen = () => (
  <div className="br" style={{ minHeight: 720, background: 'var(--paper-0)' }}>
    <NavBar active="library"/>
    <div style={{ maxWidth: 1040, margin: '0 auto', padding: '48px 32px 80px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 40 }}>
        <div>
          <div style={{ fontFamily: 'var(--sans)', fontSize: 12, letterSpacing: 1.6, textTransform: 'uppercase', color: 'var(--ink-3)', marginBottom: 10 }}>
            Your shelf
          </div>
          <h1 style={{
            margin: 0, fontFamily: 'var(--serif)', fontWeight: 400, fontSize: 44,
            letterSpacing: -0.8, color: 'var(--ink-0)', lineHeight: 1.1,
          }}>
            Six books, <span style={{ fontStyle: 'italic', color: 'var(--ink-2)' }}>reading in parallel.</span>
          </h1>
        </div>
        <Row gap={10}>
          <div style={{ width: 240 }}>
            <TextInput size="sm" icon={<IcSearch size={13}/>} placeholder="Search your books"/>
          </div>
          <Button variant="secondary" size="md" icon={<IcPlus size={13}/>}>Add book</Button>
        </Row>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 40, rowGap: 56 }}>
        {BOOKS.map((b) => <BookCard key={b.id} {...b}/>)}
      </div>
    </div>
  </div>
);

// ── Reading + Chat screen ──────────────────────────────────────
const READING_TEXT = [
  "Marley was dead, to begin with. There is no doubt whatever about that. The register of his burial was signed by the clergyman, the clerk, the undertaker, and the chief mourner. Scrooge signed it.",
  "Oh! But he was a tight-fisted hand at the grindstone, Scrooge! a squeezing, wrenching, grasping, scraping, clutching, covetous, old sinner! Hard and sharp as flint, from which no steel had ever struck out generous fire; secret, and self-contained, and solitary as an oyster.",
  "The cold within him froze his old features, nipped his pointed nose, shrivelled his cheek, stiffened his gait; made his eyes red, his thin lips blue, and spoke out shrewdly in his grating voice.",
  "External heat and cold had little influence on Scrooge. No warmth could warm, no wintry weather chill him. No wind that blew was bitterer than he, no falling snow was more intent upon its purpose, no pelting rain less open to entreaty.",
];

const ReadingScreen = () => (
  <div className="br" style={{ minHeight: 900, background: 'var(--paper-0)' }}>
    <NavBar active="reading"/>
    <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr 440px', minHeight: 844 }}>

      {/* left — chapter rail */}
      <aside style={{ borderRight: 'var(--hairline)', padding: '32px 0', fontFamily: 'var(--sans)' }}>
        <div style={{ padding: '0 24px 20px' }}>
          <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 20, letterSpacing: -0.3, color: 'var(--ink-0)' }}>
            A Christmas Carol
          </div>
          <div style={{ fontSize: 12, color: 'var(--ink-2)', marginTop: 4 }}>Charles Dickens</div>
          <div style={{ marginTop: 14 }}><ProgressPill page={48} total={96} variant="soft" size="sm"/></div>
        </div>
        <div>
          <ChapterRow num={1} title="Marley's Ghost" pages="1–23" state="read"/>
          <ChapterRow num={2} title="The First of the Three Spirits" pages="24–47" state="read"/>
          <ChapterRow num={3} title="The Second of the Three Spirits" pages="48–72" state="current"/>
          <ChapterRow num={4} title="The Last of the Spirits" pages="73–88" state="locked"/>
          <ChapterRow num={5} title="The End of It" pages="89–96" state="locked"/>
        </div>
      </aside>

      {/* center — reading column */}
      <main style={{ padding: '56px 56px 0', position: 'relative', overflow: 'hidden' }}>
        <div style={{ maxWidth: 620, margin: '0 auto', position: 'relative' }}>
          <div style={{ fontFamily: 'var(--sans)', fontSize: 11, letterSpacing: 1.6, textTransform: 'uppercase', color: 'var(--ink-3)', marginBottom: 12 }}>
            Stave III · p. 54
          </div>
          <h2 style={{
            margin: '0 0 28px', fontFamily: 'var(--serif)', fontWeight: 400,
            fontSize: 30, letterSpacing: -0.5, color: 'var(--ink-0)', lineHeight: 1.15,
          }}>
            The Second of the Three Spirits
          </h2>

          <div style={{ fontFamily: 'var(--serif)', fontSize: 17, lineHeight: 1.7, color: 'var(--ink-0)' }}>
            <p style={{ margin: '0 0 22px', textWrap: 'pretty' }}>
              {READING_TEXT[0]}
            </p>
            <p style={{ margin: '0 0 22px', textWrap: 'pretty' }}>
              Oh! But he was a tight-fisted hand at the grindstone, <Highlight variant="entity">Scrooge</Highlight>! a <Highlight variant="mark">squeezing, wrenching, grasping, scraping, clutching, covetous, old sinner</Highlight>! Hard and sharp as flint, from which no steel had ever struck out generous fire; secret, and self-contained, and solitary as an oyster.
            </p>
            <p style={{ margin: '0 0 22px', textWrap: 'pretty' }}>
              {READING_TEXT[2]}
            </p>
            <p style={{ margin: '0 0 22px', textWrap: 'pretty' }}>
              {READING_TEXT[3]} What the <Highlight variant="selection">dickens</Highlight> could have brought him here?
            </p>
            <p style={{ margin: '0 0 22px', textWrap: 'pretty', opacity: 0.9 }}>
              Nobody ever stopped him in the street to say, with gladsome looks, "My dear Scrooge, how are you? When will you come to see me?" No beggars implored him to bestow a trifle, no children asked him what it was o'clock, no man or woman ever once in all his life inquired the way to such and such a place, of Scrooge.
            </p>
          </div>
          <ProgressiveBlur height={220} locked/>
        </div>
      </main>

      {/* right — chat column */}
      <aside style={{ borderLeft: 'var(--hairline)', display: 'flex', flexDirection: 'column', background: 'color-mix(in oklab, var(--paper-0) 92%, var(--paper-1))' }}>
        <div style={{ padding: '20px 24px', borderBottom: 'var(--hairline)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Row gap={8}>
            <IcChat size={14} style={{ color: 'var(--ink-2)' }}/>
            <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--ink-0)', letterSpacing: 0.2 }}>Margin notes</span>
          </Row>
          <LockState state="spoilerSafe" label="safe through p. 54"/>
        </div>

        <div style={{ flex: 1, padding: '24px', display: 'flex', flexDirection: 'column', gap: 24, overflow: 'hidden' }}>
          <UserBubble pageAt={48}>Who is Marley, really? The book keeps circling him.</UserBubble>

          <AssistantBubble
            sources={[
              { quote: "Marley was dead, to begin with.", ch: 'Stave I', page: 1 },
              { quote: "Scrooge never painted out Old Marley's name, however. There it stood…", ch: 'Stave I', page: 3 },
            ]}
          >
            Jacob Marley was <em>Scrooge's business partner of many years</em>, dead seven years to the day by the time the story opens. The narrator insists on the fact of his death up front — "<em>dead as a door-nail</em>" — because the story needs it to land: what appears later must first be impossible.
            {' '}For now, he is mostly a name on a sign Scrooge never bothered to paint over.
          </AssistantBubble>

          <UserBubble pageAt={54}>And the first spirit — what should I be watching for?</UserBubble>

          <AssistantBubble streaming>
            The Ghost of Christmas Past arrives as a figure of paradox: <em>"like a child: yet not so like a child as like an old man."</em> Watch how Dickens uses its light — it shines from the crown, and Scrooge will reach for an extinguisher
          </AssistantBubble>
        </div>

        <div style={{ padding: '16px 20px 20px' }}>
          <ChatInput value="" placeholder="Ask about what you've read…"/>
          <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {['Summarize this chapter', 'What do I know about Scrooge?', 'Define “counting house”'].map((q) => (
              <button key={q} style={{
                padding: '5px 10px', borderRadius: 'var(--r-pill)',
                background: 'var(--paper-00)', border: 'var(--hairline)',
                fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--ink-2)', letterSpacing: 0.2,
              }}>{q}</button>
            ))}
          </div>
        </div>
      </aside>
    </div>
  </div>
);

// ── Upload / Pipeline screen ───────────────────────────────────
const UploadScreen = () => (
  <div className="br" style={{ minHeight: 840, background: 'var(--paper-0)' }}>
    <NavBar active="upload"/>
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '64px 32px 80px' }}>
      <div style={{ fontFamily: 'var(--sans)', fontSize: 11, letterSpacing: 1.6, textTransform: 'uppercase', color: 'var(--ink-3)', marginBottom: 10 }}>
        Add a book
      </div>
      <h1 style={{ margin: '0 0 8px', fontFamily: 'var(--serif)', fontWeight: 400, fontSize: 38, letterSpacing: -0.8, color: 'var(--ink-0)' }}>
        Upload an EPUB.
      </h1>
      <div style={{ fontFamily: 'var(--serif)', fontSize: 17, lineHeight: 1.55, color: 'var(--ink-2)', maxWidth: 520, marginBottom: 36 }}>
        We'll parse the chapters, learn the characters, and build a spoiler-aware index — so you can ask anything, and we'll answer only from what you've already read.
      </div>

      <Dropzone filename="a-christmas-carol.epub" active={false} state="uploading"/>

      <div style={{ marginTop: 40, padding: '24px 24px 8px', background: 'var(--paper-00)', border: 'var(--hairline)', borderRadius: 'var(--r-lg)' }}>
        <Row style={{ justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 19, color: 'var(--ink-0)', letterSpacing: -0.2 }}>
              <span style={{ fontStyle: 'italic' }}>A Christmas Carol</span>
            </div>
            <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--ink-2)', marginTop: 2 }}>
              Charles Dickens · 5 staves · ~28,000 words
            </div>
          </div>
          <StatusBadge state="running" label="building — 3 of 7"/>
        </Row>

        <PipelineRow stage="Parse EPUB" desc="Split into chapter-segmented text" meta="0.4s" state="done"/>
        <PipelineRow stage="Run BookNLP" desc="Entities, coreference, quotes" meta="38s" state="done"/>
        <PipelineRow stage="Resolve coref" desc="Parenthetical insertion pass" meta="12s" state="done"/>
        <PipelineRow stage="Discover ontology" desc="BERTopic + TF-IDF → OWL" meta="Stave 3 of 5" state="running"/>
        <PipelineRow stage="Review ontology" desc="Optional refinement" meta="—" state="idle"/>
        <PipelineRow stage="Cognee batches" desc="Claude extracts structured entities" meta="—" state="idle"/>
        <PipelineRow stage="Validate" desc="Spoiler-safety + spot checks" meta="—" state="idle"/>
      </div>

      <div style={{ marginTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--ink-3)' }}>
          You can close this tab — we'll keep going in the background.
        </div>
        <Row gap={8}>
          <Button variant="ghost">Cancel</Button>
          <Button variant="secondary" icon={<IcClock size={13}/>}>Notify me when done</Button>
        </Row>
      </div>
    </div>
  </div>
);

Object.assign(window, { LibraryScreen, ReadingScreen, UploadScreen });
