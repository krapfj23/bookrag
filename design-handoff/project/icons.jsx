// icons.jsx — SVG-only icon set, stroke-based, currentColor.
// All icons are 1.5 stroke · round caps · 16×16 default. Sized via font-size or width/height.

const Icon = ({ d, size = 16, stroke = 1.5, fill = 'none', viewBox = '0 0 16 16', style, children, ...rest }) => (
  <svg width={size} height={size} viewBox={viewBox} fill={fill} stroke="currentColor"
       strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
       style={{ flexShrink: 0, ...style }} {...rest}>
    {d ? <path d={d} /> : children}
  </svg>
);

const IcBook     = (p) => <Icon {...p}><path d="M3 2.5h6a2 2 0 0 1 2 2V14l-2-1H3V2.5zm10 0h-2v10.5l2-1h.5V2.5H13z"/></Icon>;
const IcSearch   = (p) => <Icon {...p} d="M7.5 12.5a5 5 0 1 0 0-10 5 5 0 0 0 0 10zm3.5-1.5l2.5 2.5" />;
const IcChat     = (p) => <Icon {...p}><path d="M3 4a1.5 1.5 0 0 1 1.5-1.5h7A1.5 1.5 0 0 1 13 4v5a1.5 1.5 0 0 1-1.5 1.5H7l-3 3v-3h-1A1.5 1.5 0 0 1 3 9V4z"/></Icon>;
const IcLibrary  = (p) => <Icon {...p}><path d="M3 2.5v11m3-11v11m4-11l2.5 10.6M6.3 2.7l3 10.5"/></Icon>;
const IcUpload   = (p) => <Icon {...p} d="M8 11V3m0 0L5 6m3-3l3 3M3 13h10" />;
const IcLock     = (p) => <Icon {...p}><path d="M4.5 7.5h7v6h-7v-6zM6 7.5V5a2 2 0 0 1 4 0v2.5"/><circle cx="8" cy="10.5" r="0.7" fill="currentColor" stroke="none"/></Icon>;
const IcUnlock   = (p) => <Icon {...p}><path d="M4.5 7.5h7v6h-7v-6zM6 7.5V5a2 2 0 0 1 3.8-.8"/></Icon>;
const IcCheck    = (p) => <Icon {...p} d="M3 8.5L6.5 12 13 5" />;
const IcArrowR   = (p) => <Icon {...p} d="M3.5 8h9m-3-3l3 3-3 3" />;
const IcArrowL   = (p) => <Icon {...p} d="M12.5 8h-9m3-3l-3 3 3 3" />;
const IcChevron  = (p) => <Icon {...p} d="M4 6l4 4 4-4" />;
const IcDot      = (p) => <Icon {...p}><circle cx="8" cy="8" r="3" fill="currentColor" stroke="none"/></Icon>;
const IcClose    = (p) => <Icon {...p} d="M4 4l8 8M12 4l-8 8" />;
const IcPlus     = (p) => <Icon {...p} d="M8 3v10M3 8h10" />;
const IcSpark    = (p) => <Icon {...p}><path d="M8 2v3M8 11v3M2 8h3M11 8h3M4 4l2 2M10 10l2 2M12 4l-2 2M4 12l2-2"/></Icon>;
const IcSun      = (p) => <Icon {...p}><circle cx="8" cy="8" r="3"/><path d="M8 1.5v1.5M8 13v1.5M1.5 8h1.5M13 8h1.5M3.3 3.3l1 1M11.7 11.7l1 1M12.7 3.3l-1 1M3.3 12.7l1-1"/></Icon>;
const IcMoon     = (p) => <Icon {...p}><path d="M13 9a5 5 0 0 1-6-6 5 5 0 1 0 6 6z"/></Icon>;
const IcSettings = (p) => <Icon {...p}><circle cx="8" cy="8" r="1.8"/><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.3 3.3l1.5 1.5M11.2 11.2l1.5 1.5M12.7 3.3l-1.5 1.5M4.8 11.2l-1.5 1.5"/></Icon>;
const IcUser     = (p) => <Icon {...p}><circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5c0-2.5 2.2-4 5-4s5 1.5 5 4"/></Icon>;
const IcBookmark = (p) => <Icon {...p}><path d="M4 2.5h8v11l-4-2.5-4 2.5v-11z"/></Icon>;
const IcHighlight= (p) => <Icon {...p}><path d="M3 13h10M4.5 10.5l3 3 6-6-3-3-6 6z"/></Icon>;
const IcCopy     = (p) => <Icon {...p}><path d="M5 5V3h8v8h-2M3 5h8v8H3V5z"/></Icon>;
const IcSend     = (p) => <Icon {...p} d="M13.5 2.5L2.5 7l5 1.5L9 13.5l4.5-11z" />;
const IcQuote    = (p) => <Icon {...p}><path d="M4 10c0-3 1-4.5 3-5M9 10c0-3 1-4.5 3-5M3 10v2.5h2.5V10H3zm5 0v2.5h2.5V10H8z"/></Icon>;
const IcRefresh  = (p) => <Icon {...p}><path d="M2.5 8a5.5 5.5 0 0 1 10-3M13.5 8a5.5 5.5 0 0 1-10 3M12 2v3.5h-3.5M4 14v-3.5h3.5"/></Icon>;
const IcStop     = (p) => <Icon {...p}><rect x="4" y="4" width="8" height="8" rx="1" fill="currentColor" stroke="none"/></Icon>;
const IcFile     = (p) => <Icon {...p}><path d="M4 2.5h5l3 3V13.5H4v-11zM9 2.5V6h3"/></Icon>;
const IcClock    = (p) => <Icon {...p}><circle cx="8" cy="8" r="5.5"/><path d="M8 5v3l2 1.5"/></Icon>;

Object.assign(window, {
  IcBook, IcSearch, IcChat, IcLibrary, IcUpload, IcLock, IcUnlock, IcCheck,
  IcArrowR, IcArrowL, IcChevron, IcDot, IcClose, IcPlus, IcSpark,
  IcSun, IcMoon, IcSettings, IcUser, IcBookmark, IcHighlight, IcCopy, IcSend,
  IcQuote, IcRefresh, IcStop, IcFile, IcClock,
});
