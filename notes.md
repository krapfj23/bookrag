# BookRAG Known Limitations & Future Considerations

## EPUB Parser

**Single-spine EPUB support (known limitation)**
Parser assumes multi-spine EPUBs. Single-spine EPUBs (entire novel in one HTML file) produce one giant "chapter," breaking all downstream modules that expect chapter-level granularity. No fallback exists by design — regex-based heading detection was considered too fragile (silent failures from inline headings, ambiguous matches). Acceptable for current test books (A Christmas Carol, Red Rising). If single-spine EPUBs become a requirement, revisit with awareness that regex detection trades loud failures for silent ones.
