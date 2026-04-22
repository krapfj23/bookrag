// ─────────────────────────────────────────────────────────────
// Shared reader bits for EPUB Visualizer v2
// Chapter data (Dickens excerpts), tokenizer, selection toolbar.
// Everything here is global (assigned to window at bottom).
// ─────────────────────────────────────────────────────────────

const CHAPTERS_V2 = [
  { n: 1, title: "Marley's Ghost",                    pct: '0–25%',   pages: '1–23'  },
  { n: 2, title: "The First of the Three Spirits",    pct: '25–48%',  pages: '24–47' },
  { n: 3, title: "The Second of the Three Spirits",   pct: '48–72%',  pages: '48–72' },
  { n: 4, title: "The Last of the Spirits",           pct: '72–92%',  pages: '73–88' },
  { n: 5, title: "The End of It",                     pct: '92–100%', pages: '89–96' },
];

// A handful of rich paragraphs per chapter, enough to overflow a page.
const PROSE_V2 = {
  1: [
    "Marley was dead, to begin with. There is no doubt whatever about that. The register of his burial was signed by the clergyman, the clerk, the undertaker, and the chief mourner. Scrooge signed it. And Scrooge's name was good upon 'Change for anything he chose to put his hand to.",
    "Old Marley was as dead as a door-nail. Mind! I don't mean to say that I know, of my own knowledge, what there is particularly dead about a door-nail. I might have been inclined, myself, to regard a coffin-nail as the deadest piece of ironmongery in the trade.",
    "But the wisdom of our ancestors is in the simile; and my unhallowed hands shall not disturb it, or the Country's done for. You will therefore permit me to repeat, emphatically, that Marley was as dead as a door-nail.",
    "Scrooge knew he was dead? Of course he did. How could it be otherwise? Scrooge and he were partners for I don't know how many years. Scrooge was his sole executor, his sole administrator, his sole assign, his sole residuary legatee, his sole friend, and sole mourner.",
    "And even Scrooge was not so dreadfully cut up by the sad event, but that he was an excellent man of business on the very day of the funeral, and solemnised it with an undoubted bargain.",
  ],
  2: [
    "Oh! But he was a tight-fisted hand at the grindstone, Scrooge! a squeezing, wrenching, grasping, scraping, clutching, covetous, old sinner! Hard and sharp as flint, from which no steel had ever struck out generous fire; secret, and self-contained, and solitary as an oyster.",
    "The cold within him froze his old features, nipped his pointed nose, shrivelled his cheek, stiffened his gait; made his eyes red, his thin lips blue, and spoke out shrewdly in his grating voice. A frosty rime was on his head, and on his eyebrows, and his wiry chin.",
    "He carried his own low temperature always about with him; he iced his office in the dog-days; and didn't thaw it one degree at Christmas. External heat and cold had little influence on Scrooge. No warmth could warm, no wintry weather chill him.",
  ],
  3: [
    "Scrooge awoke in his own bedroom. There was no doubt about that. But it and his own adjoining sitting-room, into which he shuffled in his slippers, attracted by a great light there, had undergone a surprising transformation.",
    "The walls and ceiling were so hung with living green, that it looked a perfect grove; from every part of which, bright gleaming berries glistened. The crisp leaves of holly, mistletoe, and ivy reflected back the light, as if so many little mirrors had been scattered there.",
    "Heaped up on the floor, to form a kind of throne, were turkeys, geese, game, poultry, brawn, great joints of meat, sucking-pigs, long wreaths of sausages, mince-pies, plum-puddings, barrels of oysters, red-hot chestnuts, cherry-cheeked apples, juicy pears, immense twelfth-cakes, and seething bowls of punch.",
    "In easy state upon this couch, there sat a jolly Giant, glorious to see, who bore a glowing torch, in shape not unlike Plenty's horn, and held it up, high up, to shed its light on Scrooge, as he came peeping round the door.",
    "\"Come in!\" exclaimed the Ghost. \"Come in! and know me better, man!\" Scrooge entered timidly, and hung his head before this Spirit. He was not the dogged Scrooge he had been; and though the Spirit's eyes were clear and kind, he did not like to meet them.",
    "\"I am the Ghost of Christmas Present,\" said the Spirit. \"Look upon me!\" Scrooge reverently did so. It was clothed in one simple green robe, or mantle, bordered with white fur. This garment hung so loosely on the figure, that its capacious breast was bare, as if disdaining to be warded or concealed by any artifice.",
    "Its feet, observable beneath the ample folds of the garment, were also bare; and on its head it wore no other covering than a holly wreath, set here and there with shining icicles. Its dark brown curls were long and free; free as its genial face, its sparkling eye, its open hand, its cheery voice, its unconstrained demeanour, and its joyful air.",
    "Girded round its middle was an antique scabbard; but no sword was in it, and the ancient sheath was eaten up with rust.",
  ],
};

// A roman-numeral helper for stave numbers.
const ROMAN_V2 = ['','I','II','III','IV','V'];

// ─────────────────────────────────────────────────────────────
// Selection toolbar — floating, appears on highlight.
// Three actions: Ask, Highlight, Note. Uses design system tokens.
// ─────────────────────────────────────────────────────────────
const SelectionToolbar = ({ x = 480, y = 260, onAsk, onHighlight, onNote, visible = true }) => {
  if (!visible) return null;
  const btn = {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '7px 11px', borderRadius: 'var(--r-md)',
    fontFamily: 'var(--sans)', fontSize: 12.5, fontWeight: 500,
    color: 'var(--ink-0)', cursor: 'pointer',
    transition: 'background var(--dur) var(--ease)',
  };
  return (
    <div style={{
      position: 'absolute', left: x, top: y, transform: 'translate(-50%, -100%)',
      marginTop: -10,
      display: 'inline-flex', alignItems: 'center', gap: 2,
      padding: 4,
      background: 'var(--paper-00)',
      border: '1px solid var(--paper-2)',
      borderRadius: 'var(--r-lg)',
      boxShadow: '0 12px 32px -8px rgba(28,24,18,.22), 0 2px 6px rgba(28,24,18,.06)',
      zIndex: 20,
      animation: 'fadeUp 180ms var(--ease-out)',
    }}>
      <div style={{ ...btn, background: 'var(--accent)', color: 'var(--paper-00)', paddingLeft: 12, paddingRight: 12 }} onClick={onAsk}>
        <IcSpark size={12}/> Ask
      </div>
      <div style={{ ...btn }} onClick={onHighlight} onMouseOver={(e)=>e.currentTarget.style.background='var(--paper-1)'} onMouseOut={(e)=>e.currentTarget.style.background='transparent'}>
        <IcHighlight size={12}/> Highlight
      </div>
      <div style={{ ...btn }} onClick={onNote} onMouseOver={(e)=>e.currentTarget.style.background='var(--paper-1)'} onMouseOut={(e)=>e.currentTarget.style.background='transparent'}>
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 3h6.5L13 6.5V13H3V3z"/><path d="M9.5 3v3.5H13"/><path d="M5.5 9h5M5.5 11h3.5"/>
        </svg>
        Note
      </div>
      {/* little pointer */}
      <div style={{
        position: 'absolute', left: '50%', bottom: -5, transform: 'translateX(-50%) rotate(45deg)',
        width: 10, height: 10, background: 'var(--paper-00)',
        borderRight: '1px solid var(--paper-2)', borderBottom: '1px solid var(--paper-2)',
      }}/>
    </div>
  );
};

// Highlighted selection in prose — reusable.
const Selection = ({ children }) => (
  <span style={{
    background: 'var(--accent-soft)',
    color: 'var(--accent-ink)',
    borderRadius: 2,
    padding: '1px 0',
    boxShadow: '0 0 0 2px var(--accent-soft)',
  }}>{children}</span>
);

// Mini progress dots — used along bottom of variations.
const ProgressDots = ({ current = 3, total = 5 }) => (
  <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
    {Array.from({ length: total }).map((_, i) => {
      const active = i + 1 === current;
      const done = i + 1 < current;
      return (
        <div key={i} style={{
          width: active ? 22 : 6, height: 6, borderRadius: 999,
          background: active ? 'var(--accent)' : done ? 'var(--accent-soft)' : 'var(--paper-2)',
          transition: 'all var(--dur)',
        }}/>
      );
    })}
  </div>
);

// Tiny progress bar.
const MiniBar = ({ pct = 54, w = 220, h = 3 }) => (
  <div style={{ width: w, height: h, background: 'var(--paper-2)', borderRadius: 999, overflow: 'hidden' }}>
    <div style={{ width: `${pct}%`, height: '100%', background: 'var(--accent)' }}/>
  </div>
);

// Drop-cap paragraph
const DropCapP = ({ children, style }) => (
  <p style={style} className="dropcap-p">{children}</p>
);

Object.assign(window, {
  CHAPTERS_V2, PROSE_V2, ROMAN_V2,
  SelectionToolbar, Selection, ProgressDots, MiniBar, DropCapP,
});
