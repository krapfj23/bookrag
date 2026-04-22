"""Tests for paragraph-kind classification used by the reader renderer.

The loader tags each paragraph as body / scene_break / epigraph so the
frontend can render ornaments, italic blockquotes, and drop caps without
inspecting raw text.
"""
from __future__ import annotations

from api.loaders.sentence_anchors import (
    AnchoredParagraph,
    AnchoredSentence,
    classify_paragraphs,
)


def _para(idx: int, *texts: str) -> AnchoredParagraph:
    sents = [
        AnchoredSentence(sid=f"p{idx}.s{i}", text=t)
        for i, t in enumerate(texts, start=1)
    ]
    return AnchoredParagraph(paragraph_idx=idx, sentences=sents)


class TestSceneBreakClassification:
    def test_canonical_dinkus(self):
        paras = classify_paragraphs([_para(1, "***")])
        assert paras[0].kind == "scene_break"
        assert paras[0].sentences[0].text == "***"

    def test_spaced_asterisks_normalized(self):
        paras = classify_paragraphs([_para(1, "* * *")])
        assert paras[0].kind == "scene_break"
        assert paras[0].sentences[0].text == "***"

    def test_dashes_become_scene_break(self):
        paras = classify_paragraphs([_para(1, "---")])
        assert paras[0].kind == "scene_break"
        assert paras[0].sentences[0].text == "***"

    def test_three_dots_ornament(self):
        paras = classify_paragraphs([_para(1, "• • •")])
        assert paras[0].kind == "scene_break"

    def test_body_paragraph_stays_body(self):
        paras = classify_paragraphs([_para(1, "He sat by the window.")])
        assert paras[0].kind == "body"


class TestEpigraphClassification:
    def test_quoted_block_at_chapter_head(self):
        paras = classify_paragraphs([
            _para(1, "“Fate whispers to the warrior: you cannot withstand the storm.”"),
            _para(2, "Darrow walked into the arena."),
        ])
        assert paras[0].kind == "epigraph"
        assert paras[1].kind == "body"

    def test_quote_with_em_dash_attribution(self):
        text = "“The future belongs to those who prepare.”\n— Ares"
        paras = classify_paragraphs([_para(1, text)])
        assert paras[0].kind == "epigraph"

    def test_not_epigraph_when_too_late_in_chapter(self):
        paras = classify_paragraphs([
            _para(1, "Body."),
            _para(2, "Body."),
            _para(3, "Body."),
            _para(4, "“Quote that looks like an epigraph.”"),
        ])
        assert paras[3].kind == "body"

    def test_not_epigraph_when_too_long(self):
        long_quote = "“" + ("word " * 200) + "”"
        paras = classify_paragraphs([_para(1, long_quote)])
        assert paras[0].kind == "body"

    def test_dialogue_not_epigraph(self):
        # Quote without attribution and followed by narrative — not an epigraph
        # on its own, but it IS quote-wrapped, so our simple heuristic accepts
        # it. Document: rare false positive is acceptable; worst case reader
        # italicizes a short opening line of dialogue at chapter start.
        paras = classify_paragraphs([
            _para(1, "“Hello,” he said."),
        ])
        # Quote ends mid-paragraph (ends with period), so our heuristic
        # actually REJECTS this: stripped[-1] is '.', not a closing quote.
        assert paras[0].kind == "body"


class TestMixedChapter:
    def test_epigraph_then_scene_break_then_body(self):
        paras = classify_paragraphs([
            _para(1, "“Opening line.”\n— Author"),
            _para(2, "The chapter begins."),
            _para(3, "***"),
            _para(4, "After the break."),
        ])
        kinds = [p.kind for p in paras]
        assert kinds == ["epigraph", "body", "scene_break", "body"]


# ============================================================================
# text_cleaner Phase A typography preservation
# ============================================================================

from pipeline.text_cleaner import CleaningConfig, SCENE_BREAK_SENTINEL, clean_text


class TestTypographyPreservation:
    """Smart quotes, em-dashes, and NFC survive the default cleaner."""

    def test_smart_quotes_preserved(self):
        out = clean_text("“Hello,” she said.")
        assert "“" in out
        assert "”" in out

    def test_em_dash_preserved(self):
        out = clean_text("Silence—then a voice.")
        assert "—" in out

    def test_en_dash_preserved(self):
        out = clean_text("Pages 12–15")
        assert "–" in out

    def test_ellipsis_preserved(self):
        out = clean_text("Wait… what?")
        assert "…" in out

    def test_nfc_normalization_composes_decomposed(self):
        # 'é' as e + combining acute should normalize to single codepoint
        decomposed = "café"
        out = clean_text(decomposed)
        assert "café" in out
        assert "́" not in out

    def test_soft_hyphen_stripped(self):
        out = clean_text("beau­tiful day")
        assert "­" not in out
        assert "beautiful day" in out

    def test_zero_width_chars_stripped(self):
        out = clean_text("good​bye‍world﻿!")
        assert "​" not in out
        assert "‍" not in out
        assert "﻿" not in out
        assert "goodbyeworld!" in out

    def test_ascii_quotes_opt_in(self):
        out = clean_text(
            "“Bah!” — Scrooge",
            CleaningConfig(ascii_quotes=True),
        )
        assert "“" not in out
        assert "—" not in out
        assert '"Bah!"' in out
        assert "--" in out

    def test_scene_break_sentinel_is_triple_asterisk(self):
        assert SCENE_BREAK_SENTINEL == "***"
