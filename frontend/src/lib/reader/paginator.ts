import type { AnchoredParagraph, AnchoredSentence } from "../api";

export type PaginatorBox = {
  pageWidth: number;
  pageHeight: number;
  paddingPx: number;
  fontPx: number;
  lineHeight: number;
};

export type PageParagraph = {
  paragraph_idx: number;
  sentences: AnchoredSentence[];
  isContinuation?: boolean;
};

export type Page = PageParagraph[];

export type Spread = {
  index: number;
  left: Page;
  right: Page;
  lastSid: string;
  firstSid: string;
};

// Measurement: create a hidden element sized to the inner page box, append
// candidate paragraphs, measure scrollHeight. If scrollHeight <= innerHeight,
// the paragraph fits; else the last-added paragraph overflows.
function makeMeasurer(box: PaginatorBox): {
  el: HTMLDivElement;
  inner: HTMLDivElement;
  innerHeight: number;
  cleanup: () => void;
} {
  const el = document.createElement("div");
  el.style.position = "absolute";
  el.style.left = "-99999px";
  el.style.top = "0";
  el.style.width = `${box.pageWidth}px`;
  el.style.height = `${box.pageHeight}px`;
  el.style.padding = `${box.paddingPx}px`;
  el.style.boxSizing = "border-box";
  el.style.fontFamily = "var(--serif, Lora, serif)";
  el.style.fontSize = `${box.fontPx}px`;
  el.style.lineHeight = String(box.lineHeight);
  el.style.textAlign = "justify";
  const inner = document.createElement("div");
  inner.style.width = "100%";
  inner.style.height = "auto";
  el.appendChild(inner);
  document.body.appendChild(el);
  return {
    el,
    inner,
    innerHeight: box.pageHeight - box.paddingPx * 2,
    cleanup: () => el.remove(),
  };
}

function paragraphNode(p: PageParagraph): HTMLParagraphElement {
  const node = document.createElement("p");
  node.style.margin = "0 0 0.9em";
  node.style.hyphens = "auto";
  for (let i = 0; i < p.sentences.length; i++) {
    const span = document.createElement("span");
    span.setAttribute("data-sid", p.sentences[i].sid);
    span.textContent = p.sentences[i].text + (i < p.sentences.length - 1 ? " " : "");
    node.appendChild(span);
  }
  return node;
}

function packPage(
  remaining: PageParagraph[],
  inner: HTMLDivElement,
  innerHeight: number,
): { fitted: PageParagraph[]; leftover: PageParagraph[] } {
  const fitted: PageParagraph[] = [];
  inner.innerHTML = "";
  while (remaining.length) {
    const p = remaining[0];
    const node = paragraphNode(p);
    inner.appendChild(node);
    if (inner.scrollHeight <= innerHeight) {
      fitted.push(p);
      remaining.shift();
      continue;
    }
    // Does not fit whole. Try splitting at sentence boundary.
    inner.removeChild(node);
    const splitFit: AnchoredSentence[] = [];
    const splitRest: AnchoredSentence[] = [...p.sentences];
    const partialNode = document.createElement("p");
    partialNode.style.margin = "0 0 0.9em";
    inner.appendChild(partialNode);
    while (splitRest.length) {
      const s = splitRest[0];
      const span = document.createElement("span");
      span.setAttribute("data-sid", s.sid);
      span.textContent = s.text + " ";
      partialNode.appendChild(span);
      if (inner.scrollHeight <= innerHeight) {
        splitFit.push(s);
        splitRest.shift();
      } else {
        partialNode.removeChild(span);
        break;
      }
    }
    if (splitFit.length > 0) {
      fitted.push({
        paragraph_idx: p.paragraph_idx,
        sentences: splitFit,
        isContinuation: p.isContinuation ?? false,
      });
    }
    if (splitRest.length > 0) {
      // Put back the rest as a continuation of the same paragraph.
      remaining[0] = {
        paragraph_idx: p.paragraph_idx,
        sentences: splitRest,
        isContinuation: true,
      };
    } else {
      remaining.shift();
    }
    break;
  }
  return { fitted, leftover: remaining };
}

export function paginate(
  paragraphs: AnchoredParagraph[],
  box: PaginatorBox,
): Spread[] {
  const { inner, innerHeight, cleanup } = makeMeasurer(box);
  try {
    const queue: PageParagraph[] = paragraphs.map((p) => ({
      paragraph_idx: p.paragraph_idx,
      sentences: [...p.sentences],
    }));
    const spreads: Spread[] = [];
    let idx = 0;
    // Safety cap: at most 1 spread per sentence (impossible to exceed).
    const totalSentences = paragraphs.reduce((n, p) => n + p.sentences.length, 0);
    const maxSpreads = Math.max(1, totalSentences);
    while (queue.length && spreads.length < maxSpreads) {
      const leftPack = packPage(queue, inner, innerHeight);
      const left = leftPack.fitted;
      let right: PageParagraph[] = [];
      if (leftPack.leftover.length) {
        const rightPack = packPage(leftPack.leftover, inner, innerHeight);
        right = rightPack.fitted;
      }
      const pageParas = [...left, ...right];
      if (pageParas.length === 0) break;
      const flatSids = pageParas.flatMap((p) => p.sentences.map((s) => s.sid));
      spreads.push({
        index: idx++,
        left,
        right,
        firstSid: flatSids[0],
        lastSid: flatSids[flatSids.length - 1],
      });
    }
    if (spreads.length === 0) {
      // Fallback: one spread with everything left on the left page.
      const pageParas = paragraphs.map((p) => ({
        paragraph_idx: p.paragraph_idx,
        sentences: [...p.sentences],
      }));
      const flatSids = pageParas.flatMap((p) => p.sentences.map((s) => s.sid));
      spreads.push({
        index: 0,
        left: pageParas,
        right: [],
        firstSid: flatSids[0] ?? "p1.s1",
        lastSid: flatSids[flatSids.length - 1] ?? "p1.s1",
      });
    }
    return spreads;
  } finally {
    cleanup();
  }
}
