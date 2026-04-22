# EPUB Enhancement & Preprocessing: State of the Art for Text-Analysis Pipelines

**Date:** 2026-04-22
**Scope:** Techniques relevant to BookRAG (EPUB → BookNLP → coref → Cognee KG).
**Assumption:** Input is trade-fiction EPUB2/EPUB3; output must be chapter-segmented plain text that preserves dialogue, paragraph breaks, scene breaks, and narrative order, while stripping HTML/TOC/front-matter/page-number noise.

---

## 1. EPUB Parsing Libraries

EPUB is a zipped bundle of XHTML + OPF metadata + optional NCX/nav navigation. Parsing quality varies mostly in (a) robustness to malformed archives, (b) fidelity of spine ordering, and (c) how much semantic markup survives the extraction.

- **ebooklib 0.20** (current, Python-only, `aerkalov/ebooklib`). Full EPUB2/EPUB3 read/write, OPF/spine/NCX/nav access, metadata via Dublin Core namespaces. Tolerant of minor malformation, but not strict on EPUB3 nav semantics. Pure Python, slow on large corpora. Still the de-facto Python choice. 0.20 is the last version supporting Python 2.7; active commits continue on the Python-3 line.
- **fast-ebook 0.2.0** (2026-04-10, `arc53/fast-ebook`). Rust core via PyO3 with a drop-in compatibility shim for ebooklib. Reports 6.7x faster markdown conversion on War and Peace, 3x faster chapter extract, 78x faster `get_item_with_id`. Parallel batch processing. Useful when re-ingesting a large library; overkill for one-off uploads.
- **pypub3**. Focused on *creating* EPUBs; thin for reading. Skip.
- **python-epub3** / **epubfile** / **ebookmeta**. Better for metadata/OPF surgery than for extracting narrative content. `epubfile` exposes the OPF as a BeautifulSoup tree (useful if you want to filter `<manifest>` items by `epub:type` before extraction).
- **Apache Tika (tika-python)**. Wraps Tika's Java extractor. Robust against malformed archives and produces reasonable plain text, but loses most structural markup and chapter boundaries. Useful as a last-resort fallback extractor.
- **PyMuPDF (`fitz`)**. Handles EPUB via MuPDF's reflow engine. Good for text-only dumps; bad for semantic HTML preservation.
- **Calibre `ebook-convert`** (v9.7, `kovidgoyal/calibre`). The gold standard CLI. Its "heuristic processing" stage specifically normalizes chapter headings, scene breaks, and italics, and can emit clean TXT/HTML/MD. Heavyweight dependency (must shell out), but for messy EPUBs it often rescues books other parsers mangle. See §2 for its chapter detection internals.
- **Pandoc 3.x**. `pandoc input.epub -t plain` or `-t gfm` converts via an intermediate AST that preserves headings, blockquotes, lists, `<hr/>`. Excellent structure preservation; weaker than Calibre on malformed input. This is what `unstructured.io` uses under the hood for its `partition_epub`.
- **unstructured.io `partition_epub`** (v0.18+). Pandoc-based conversion → HTML → `partition_html`, producing typed elements (`Title`, `NarrativeText`, `ListItem`, `Footer`). Good option if BookRAG ever wants typed segments downstream.
- **ebook_splitter** (`hirowa/ebook_splitter`). Purpose-built chapter extractor with a three-tier fallback: TOC → `<h1>/<h2>` headings → GPT-assisted chapter-title prediction from the first N pages. Emits CSV. Worth reading for the fallback design even if you don't adopt it.

Practical finding: no single library is best at everything. A hybrid pipeline (ebooklib for spine/metadata + Calibre/Pandoc for cleanup fallback + manual XPath for edge cases) outperforms any monoculture.

---

## 2. Chapter / Section Detection

The EPUB spine is the authoritative read order, but it does **not** map 1:1 to chapters: one spine item may be a whole book, or a single chapter may be split across 6 spine items (one per HTML file). TOC (NCX in EPUB2, `nav` in EPUB3) is usually correct when present — but publisher-generated EPUBs frequently have TOCs that only list "Part I / Part II" or omit prologue/epilogue, and hand-converted EPUBs may have no TOC at all.

**Recommended cascade (matches Calibre's approach):**

1. **EPUB3 `<nav epub:type="toc">`** — highest trust. Ignore `landmarks` and `page-list`; use the `toc` nav only.
2. **EPUB2 NCX `navMap`** — second highest. Beware nested `navPoint`s representing sub-sections.
3. **Heading regex on spine contents** — Calibre default: `<h1>` or `<h2>` matching `/chapter|book|section|prologue|epilogue|part/i` OR any tag with `class="chapter"`. Expressed as `//h:h1[re:test(., 'chapter|...', 'i')] | //h:h2[...] | //*[@class='chapter']`.
4. **Font-size / boldness heuristics** — if no headings, detect the largest font-size run in CSS and treat its occurrences as chapter starts.
5. **Pagebreak / `<hr>` + all-caps first line** — publishers often mark chapters with a section break followed by "CHAPTER ONE" or a number-word.
6. **LLM fallback** (ebook_splitter pattern) — send the first ~5KB of each spine item to a small model and ask "does this begin a new chapter? title?". Cheap, high-recall on the residual ~5% of files the rule-based cascade misses.

**Front-matter / body separation.** EPUB3's `epub:type` vocabulary is the cleanest signal (`cover`, `titlepage`, `copyright-page`, `toc`, `dedication`, `foreword`, `preface`, `bodymatter`, `chapter`, `appendix`, `glossary`, `index`, `colophon`). When it's set, trust it. When it's missing, apply these rules in order until you hit real body text:

- Skip spine items ≤ 500 words whose text density contains copyright symbols, ISBNs, publisher names, "all rights reserved", "First published".
- Skip items with ≥ 20% of content inside `<a>` elements (likely a TOC).
- Treat "Prologue" / "Epilogue" as body (include them). "Introduction" is ambiguous — some novels have in-world introductions (Red Rising does not; *Dune* does) — keep if word-count > 1500, drop if it mentions the author in third person.
- Treat "Appendix", "Glossary", "About the Author", "Also by" as out-of-body.

**Prologue/Epilogue.** Assign them synthetic chapter numbers (0 for prologue, N+1 for epilogue) so the spoiler filter's monotonic `effective_latest_chapter` logic still works. Store the original label in metadata.

---

## 3. Text Normalization

The right form is **NFC**, not NFKC, for literary text. NFKC is destructive: it collapses the `ﬁ` ligature to `fi` (good), but also collapses `½` → `1/2`, superscript-2 → regular 2, full-width Latin → ASCII, non-breaking space → space — some of which destroys author intent or changes token boundaries. Recommended layering:

1. **ftfy 6.x** (`rspeer/python-ftfy`, active 2025). `ftfy.fix_text()` fixes mojibake (UTF-8-interpreted-as-Latin-1 → recovered UTF-8), normalizes line breaks, and repairs HTML entities. Use `fix_and_explain()` during ingestion QA to log what it changed. Configure: keep `unescape_html=True`, keep `fix_latin_ligatures=True`, keep `uncurl_quotes=False` for fiction — smart quotes are semantic signals BookNLP uses for dialogue detection; **do not** ASCII-ify them.
2. **Selective ligature expansion.** Expand Latin display ligatures (`ﬁ`, `ﬂ`, `ﬃ`, `ﬄ`, `ﬅ`) — these are PDF/OCR artifacts, never author intent. Leave `æ`, `œ`, Unicode digraphs alone.
3. **Soft-hyphen `­` removal.** Always strip. Publishers insert these for reflow hinting; they break tokenization.
4. **Zero-width joiners/non-joiners `​-‍`, BOM `﻿`.** Strip (except inside code/foreign-script spans, irrelevant for English fiction).
5. **Em-dash / en-dash.** Preserve as-is. BookNLP uses em-dashes as dialogue turn markers in certain styles (Joyce, McCarthy). Do not collapse to hyphen.
6. **Quote style.** Normalize to a single consistent pair (prefer canonical curly `“ ”` and `‘ ’`). Mixed straight/curly in the same book confuses BookNLP's quote detector.
7. **Drop caps.** Detected as a leading capital letter in a `<span class="dropcap">` or `<span style="font-size:...">`. Merge back into the next word before tokenization (drop caps are often split: `<span>T</span>he king` → `The king`).
8. **Hyphenation.** End-of-line hyphens from reflowed print scans: use `dehyphen` (PyPI) which scores join candidates via a small char-LM perplexity model. Only run when OCR heuristics (§6) flag the book as scanned.
9. **Footnotes.** EPUB3 marks them with `epub:type="footnote"` / `doc-footnote` / `doc-endnote` and in-text references with `doc-noteref`. Strategy: (a) detach the note body; (b) inline a placeholder like `[fn:N]` at the reference site; (c) store note bodies in a sidecar file. This keeps narrative flow clean while letting you optionally re-inject citations in the KG.

---

## 4. Structural Preservation

BookNLP operates on plain text but is highly sensitive to paragraph segmentation (coref windows) and quotation marks (speaker attribution). The downstream Cognee LLM extraction benefits from extra signals like section breaks.

**Keep these:**
- **Paragraph boundaries** — map each `<p>` to a `\n\n` delimiter. Do not merge short paragraphs; BookNLP uses them as coref scope anchors.
- **Dialogue quotes** — preserve curly quote pairs; do not strip trailing tags like `he said`.
- **Scene breaks** — render `<hr/>`, three-asterism (`* * *`), dinkus (`***`), or empty `<div class="scenebreak">` as a single `\n\n***\n\n` marker. This gives downstream tools a reliable scene delimiter. BookNLP does not use it, but Cognee batching and relationship extraction benefit.
- **Epigraphs** — typically `<blockquote class="epigraph">` at chapter head. Preserve as a block with attribution, but prefix with a sentinel (`[epigraph] ... [/epigraph]`) so coref doesn't cross the boundary. Epigraphs contain quotes from fictional sources ("*Golden Sons are the Sons of Ares...*" in Red Rising) that should not be attributed to real characters.
- **Verse / poetry** — preserve line breaks (`\n` within a block). Strip only if BookNLP coref starts misfiring; measurable.
- **Chapter titles** — keep as the first line of each chapter file, separated from body by `\n\n`. Cognee often cites titles.

**Discard:**
- Page numbers (`<span class="pagenum">`, stand-alone digit paragraphs), running headers/footers, publisher marketing pages, navigation/anchor-only paragraphs, image alt-text that says "image", CSS-only content.
- In-text hyperlinks: strip the `<a>` wrapper, keep the text.
- Table-of-contents spine items (detected via density of `<a>` elements).

---

## 5. Metadata Extraction

- **OPF metadata** (Dublin Core): `dc:title`, `dc:creator` (with `opf:role="aut"`), `dc:identifier` (ISBN when `opf:scheme="ISBN"`), `dc:language`, `dc:publisher`, `dc:date`, `dc:description`. `ebooklib.get_metadata('DC', 'title')` is the canonical access.
- **Cover image.** EPUB3: `<item properties="cover-image">`. EPUB2: `<meta name="cover" content="..."/>` pointing to a manifest id. Fallback: first image in the spine's first item. For BookRAG's library UI, extract cover at ingest, store at `data/processed/{book_id}/cover.jpg`.
- **Language detection.** Trust `dc:language` first; verify with `lingua-py` or `fasttext-langid` on a random body sample (~5KB). Multi-language books (English novels with Latin epigraphs) are common; detect at paragraph granularity if you want to skip non-English regions during BookNLP (which is English-only in most deployments).
- **Publisher-inserted noise.** Common patterns:
  - "Also by [author]" / "Praise for [book]" — detect by high density of title-case short lines and em-dashes.
  - Newsletter signup / "Sign up to receive" CTA — keyword match.
  - Series cross-promotion pages — often a spine item that is >50% `<a>` text.
  - Legal/copyright — keyword match (`© | Copyright | ISBN | rights reserved | printed in`).
  A combined classifier (keyword set + word-count threshold + link density) drops these reliably; manual review of ~10 books builds the rule set.

---

## 6. OCR-Originated EPUBs

Public-domain classics on Gutenberg/Standard Ebooks are typically clean, but scan-derived EPUBs (Google Books exports, Archive.org "Text" EPUBs) are riddled with OCR artifacts.

**Detection signals (run before ingestion, flag the book):**
- Frequency of the bigrams `rn`, `cl`, `vv`, `nn` inside dictionary words (English bigram-frequency deltas > 2σ from reference corpus).
- Ratio of lines ending in `-` (hyphenation breaks not cleaned up).
- Presence of stray single characters on lines (`1` instead of `I`, `0` for `O`).
- Words with character-class flips inside (`he1lo`, `wor1d`).
- Very short paragraphs (< 4 words) exceeding 25% of total — indicates column-break artifacts.
- ftfy flags a high count of heuristic fixes per 10k chars.

**Remediation ladder:**
1. **dehyphen** for end-of-line hyphenation.
2. **symspellpy** or **Hunspell** against a large dictionary — correct only when edit-distance ≤ 1 and candidate is >1000x more frequent.
3. **Contextual correction via LLM** — the 2025 literature (Schwitter, Sage Journals) shows GPT-4-class models correct OCR'd historical text with ~90% accuracy at word level when given ~500-token context windows. For BookRAG, use an async batched call at ingestion time only when the detection signals fire. Prompt: "Correct OCR errors in the following passage. Do not change wording, style, punctuation, or paragraph breaks. Only fix clear character recognition errors." Preserve original alongside corrected version for audit.
4. **arXiv 2409.04117 "Confidence-Aware Document OCR Error Detection"** proposes a BERT classifier that flags suspect tokens before LLM correction — useful if you want a lightweight first-pass filter.

Do not run OCR correction on clean EPUBs — the false-positive rate is real (esp. invented proper nouns: "Darrow" → "Arrow", "Mustang" → "Mustache").

---

## 7. QA Signals for Bad Conversions

Compute at ingestion, persist to `data/processed/{book_id}/qa.json`, surface in `/books/{id}/status`:

| Signal | Healthy range (novel) | Interpretation when outside |
|--------|----------------------|----------------------------|
| Total word count | 40k–250k | <40k: missing chapters; >250k: merged back-matter |
| Chapter count | 8–60 | <8: TOC collapse; >60: spine-item-per-page split |
| Words per chapter (median / IQR) | 2k–8k / <2x | wide IQR: mis-segmentation |
| Paragraph count per chapter | 40–300 | <40: wall-of-text paragraphs merged; >300: OCR fragmentation |
| Mean paragraph length (words) | 30–80 | <15: OCR fragments; >150: merged paragraphs |
| % lines ending in `-` | <0.2% | >1%: unresolved hyphenation |
| % dialogue (paragraphs containing curly quotes) | 15–45% | <5%: quotes stripped/straight-only; >60%: play/screenplay, not a novel |
| ftfy fix count per 10k chars | <5 | >20: bad encoding source |
| Non-ASCII ratio | 0.5–3% | <0.1%: smart quotes stripped; >10%: foreign-language content or encoding garbage |
| Unique speakers (post-BookNLP) vs. chapters | ratio 0.3–3.0 | <0.1: coref collapsed; >5: coref fragmented |

Also log the first 200 chars of each chapter to eyeball for residual TOC/page-number bleed.

---

## 8. Recent Research & Tools (2023–2026)

- **unstructured v0.18** (2025). Solid EPUB partitioner via Pandoc; emits typed elements downstream tools can filter.
- **fast-ebook 0.2.0** (April 2026). Rust-backed ebooklib alternative; biggest win is on batch re-ingestion.
- **ftfy 6.x with `fix_and_explain`** (Apr 2025 blog by Alex Chan, rspeer/python-ftfy). Audit trail for encoding fixes.
- **dehyphen 0.3.4** (PyPI, maintained). Char-LM perplexity-based hyphen join scoring.
- **ebook_splitter** (2024–2025). GPT-fallback chapter extraction is a good pattern even if you roll your own.
- **EPUB TOC & Chapter Rebuilder** (Novel Translator, browser tool). Worth inspecting for its detection rules even though it's a UI, not a library.
- **Schwitter (2025), "Using LLMs for preprocessing and information extraction from unstructured text"** (*Methods, Data, Analyses*, Sage). Benchmarks GPT-4 / Llama-3.1 on historical OCR cleanup; confirms LLMs are now the state of the art for this step.
- **"Confidence-Aware Document OCR Error Detection"** (arXiv 2409.04117, 2024). ConfBERT — token-level error flagger that stacks with LLM correction.
- **Cleanlab + Unstructured** (2025 blog, Tianyi Huang). Pipeline pattern for trust-scoring parsed documents; relevant to BookRAG's validation stage.
- **BookCoref** (upcoming, per Bamman lab 2024–2025 signals). Successor to BookNLP's coref; already referenced as a swappable target in BookRAG's design. Watch for release.

---

## Recommendations for BookRAG

Mapped to concrete actions in the current codebase (`pipeline/epub_parser.py`, `pipeline/text_cleaner.py`).

1. **Keep ebooklib as primary parser, add Pandoc fallback.** When ebooklib's spine yields <3 chapters or <10k total words, shell out to `pandoc input.epub -t gfm` and reparse. Low cost, high recall on malformed files.
2. **Implement the §2 chapter-detection cascade explicitly in `epub_parser.py`.** Today the code is TOC-first; add (a) EPUB3 `epub:type` classification, (b) heading regex matching Calibre's pattern, (c) a final small-LLM fallback that fires only when <5 chapters detected. Persist the detection-method-per-chapter into `qa.json` for auditability.
3. **Switch text normalization to NFC + ftfy + targeted ligature expansion.** Drop any NFKC in the pipeline. Add ftfy at the top of `text_cleaner.py`. Explicitly strip soft hyphens (`­`), zero-widths, BOM; preserve smart quotes and em-dashes. Unit-test with a ligature-heavy sample.
4. **Footnote isolation.** Detect `epub:type` in (`footnote`, `endnote`, `doc-footnote`, `doc-endnote`), lift note bodies to `data/processed/{book_id}/notes.json`, replace in-text refs with `[fn:N]` tokens. BookNLP will treat the tokens as opaque strings and not try to attribute them.
5. **Scene-break sentinel.** Emit `\n\n***\n\n` for every `<hr/>` and every paragraph whose visible text is exactly `* * *` / `***` / `⁂` / `•••`. Useful later for Cognee batch boundary hints.
6. **Front-matter classifier.** Today the code strips by pattern; upgrade to score each spine item on (word-count, link density, keyword matches, `epub:type`) and drop items with a total-score threshold. Log dropped items to `qa.json` so mis-drops are diagnosable.
7. **Add `qa.json` with §7 signals.** Cheap to compute, huge uplift for debugging a bad ingestion 6 months from now. Surface on the existing `/books/{id}/status` endpoint.
8. **OCR detection + opt-in LLM repair.** Compute the §6 detection signals. If triggered, call dehyphen first, then (guarded by a config flag) run a batched LLM cleanup pass with strict "do-not-rewrite" instructions. Default OFF for known-clean sources.
9. **Metadata: extract cover and language confidently.** Current code likely does title/author; add cover image extraction (for the library UI) and `dc:language` + a lingua-py verification. Refuse/flag non-English books since BookNLP is English-configured.
10. **Defer fast-ebook.** Single-user, M4 Pro, book at a time: ebooklib is fast enough. Revisit if/when batch re-ingestion is on the table.
11. **Validation step should consume `qa.json`.** The existing `validate` stage in the orchestrator can promote QA red flags to warnings visible in `/books/{id}/validation`.
12. **Drop-cap merge.** Small win, add a regex pass that detects `<span class*="dropcap|initcap|firstletter">X</span>[a-z]+` patterns before HTML stripping and merges them.

These changes stay within the existing Phase-1 stages (`parse_epub` + text cleaner), don't touch Phase 2 / Cognee, and each is independently testable.

---

## Sources

- [aerkalov/ebooklib](https://github.com/aerkalov/ebooklib)
- [arc53/fast-ebook](https://github.com/arc53/fast-ebook)
- [hirowa/ebook_splitter](https://github.com/hirowa/ebook_splitter)
- [pypub3 on PyPI](https://pypi.org/project/pypub3/)
- [Extracting text from EPUB files in Python (bitsgalore)](https://bitsgalore.org/2023/03/09/extracting-text-from-epub-files-in-python.html)
- [KB LAB EPUB extraction tutorial](https://lab.kb.nl/tutorial/extracting-text-epub-files-python)
- [Calibre 9.7 e-book conversion manual](https://manual.calibre-ebook.com/conversion.html)
- [Calibre XPath tutorial](https://manual.calibre-ebook.com/xpath.html)
- [Calibre chapter detection tutorial (MobileRead)](https://www.mobileread.com/forums/showthread.php?t=122222)
- [Pandoc EPUB](https://pandoc.org/epub.html)
- [Unstructured partitioning docs (EPUB)](https://docs.unstructured.io/open-source/core-functionality/partitioning)
- [Unstructured-IO/unstructured](https://github.com/Unstructured-IO/unstructured)
- [ftfy documentation](https://ftfy.readthedocs.io/)
- [rspeer/python-ftfy](https://github.com/rspeer/python-ftfy)
- [Alex Chan: `ftfy.fix_and_explain()` (Apr 2025)](https://alexwlchan.net/notes/2025/ftfy-fix-and-explain/)
- [UAX #15 Unicode Normalization Forms](https://unicode.org/reports/tr15/)
- [Text Normalization for NLP (Brenndoerfer)](https://mbrenndoerfer.com/writing/text-normalization-unicode-nlp)
- [textacy preprocessing](https://textacy.readthedocs.io/en/0.11.0/api_reference/preprocessing.html)
- [dehyphen on PyPI](https://pypi.org/project/dehyphen/)
- [Pyphen](https://pyphen.org/)
- [Improved Dehyphenation of Line Breaks for PDF (Hernaes, Freiburg, 2019)](https://ad-publications.cs.uni-freiburg.de/theses/Bachelor_Mari_Hernaes_2019.pdf)
- [Confidence-Aware Document OCR Error Detection (arXiv 2409.04117)](https://arxiv.org/html/2409.04117v1)
- [OCR CER/WER evaluation](https://towardsdatascience.com/evaluating-ocr-output-quality-with-character-error-rate-cer-and-word-error-rate-wer-853175297510/)
- [Schwitter 2025, LLMs for preprocessing unstructured text (Sage)](https://journals.sagepub.com/doi/10.1177/20597991251313876)
- [Intel: Four Data Cleaning Techniques to Improve LLM Performance](https://medium.com/intel-tech/four-data-cleaning-techniques-to-improve-large-language-model-llm-performance-77bee9003625)
- [Latitude: Ultimate Guide to Preprocessing Pipelines for LLMs](https://latitude.so/blog/ultimate-guide-to-preprocessing-pipelines-for-llms)
- [thetexttool: Clean Text for LLMs Checklist 2025](https://thetexttool.com/blog/clean-text-for-llms-preprocessing-checklist-2025)
- [booknlp/booknlp](https://github.com/booknlp/booknlp)
- [Multilingual BookNLP whitepaper (NEH/UC Berkeley)](https://www.neh.gov/sites/default/files/inline-files/FOIA%2021-09%20Regents%20of%20the%20University%20of%20California,%20Berkeley.pdf)
- [EPUB 3 Structural Semantics Vocabulary (IDPF)](https://idpf.github.io/epub-vocabs/structure/)
- [DAISY Accessible Publishing: Notes (footnotes/endnotes)](https://kb.daisy.org/publishing/docs/html/notes.html)
- [Novel Translator: EPUB TOC & Chapter Rebuilder](https://noveltranslator.com/tools/epub-toc-rebuilder)
- [paulocheque/epub-meta](https://github.com/paulocheque/epub-meta)
- [python-epub3 tutorial](https://python-epub3.readthedocs.io/en/latest/tutorial.html)
- [epubfile on PyPI](https://pypi.org/project/epubfile/)
- [Trustworthy LLM Document Processing with Unstructured and Cleanlab](https://medium.com/@tianyihuangx23/trustworthy-llm-document-processing-with-unstructured-and-cleanlab-99fa8104ce13)
