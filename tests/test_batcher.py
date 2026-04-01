"""Comprehensive tests for pipeline/batcher.py.

Covers:
- Batch dataclass (word_count, __len__, combined_text)
- Batcher ABC (cannot instantiate)
- FixedSizeBatcher: default 3, custom sizes, last-batch-smaller, single chapter,
  exact division, empty input, chapter_numbers auto-generation and explicit,
  mismatched lengths, batch_size < 1 validation, combined_text join,
  batch composition logging (per plan: "groups N chapters per batch")
- TokenBudgetBatcher: grouping until budget hit, single chapter exceeds budget,
  multiple chapters fit in one batch, flush remaining, max_tokens < 100 validation,
  _estimate_tokens, mismatched lengths
- get_batcher factory: dict config, object config, max_tokens triggers TokenBudget,
  no max_tokens triggers FixedSize, default batch_size=3

Aligned with:
- CLAUDE.md: "3 chapters default batch size, pluggable batcher interface"
- bookrag_pipeline_plan.md: "Default 3 chapters per batch; pluggable batcher interface"
- bookrag_pipeline_plan.md: "Token-budget batcher heuristic — start fixed-3, tune later"
"""
from __future__ import annotations

import pytest
from pipeline.batcher import Batch, Batcher, FixedSizeBatcher, TokenBudgetBatcher, get_batcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chapters(n: int, words_per: int = 100) -> list[str]:
    """Generate n chapters, each with `words_per` words."""
    return [f"word " * words_per for _ in range(n)]


# ---------------------------------------------------------------------------
# Batch dataclass
# ---------------------------------------------------------------------------

class TestBatch:
    def test_word_count(self):
        b = Batch(chapter_numbers=[1], texts=["hello world foo"], combined_text="hello world foo")
        assert b.word_count == 3

    def test_word_count_empty(self):
        b = Batch(chapter_numbers=[], texts=[], combined_text="")
        assert b.word_count == 0

    def test_len(self):
        b = Batch(chapter_numbers=[1, 2, 3], texts=["a", "b", "c"], combined_text="a\n\nb\n\nc")
        assert len(b) == 3

    def test_combined_text_not_in_repr(self):
        b = Batch(chapter_numbers=[1], texts=["x"], combined_text="HIDDEN_COMBINED_DATA")
        r = repr(b)
        # combined_text has repr=False, so it shouldn't appear in repr
        assert "HIDDEN_COMBINED_DATA" not in r

    def test_chapter_numbers_preserved(self):
        b = Batch(chapter_numbers=[5, 10, 15], texts=["a", "b", "c"], combined_text="a\n\nb\n\nc")
        assert b.chapter_numbers == [5, 10, 15]


# ---------------------------------------------------------------------------
# Batcher ABC
# ---------------------------------------------------------------------------

class TestBatcherABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Batcher()

    def test_subclass_must_implement_batch(self):
        class IncompleteBatcher(Batcher):
            pass

        with pytest.raises(TypeError):
            IncompleteBatcher()


# ---------------------------------------------------------------------------
# FixedSizeBatcher
# ---------------------------------------------------------------------------

class TestFixedSizeBatcher:
    def test_default_batch_size_is_3(self):
        """CLAUDE.md: '3 chapters default batch size'."""
        b = FixedSizeBatcher()
        assert b.batch_size == 3

    def test_batch_size_3_with_5_chapters(self):
        """Plan: 'last batch may be smaller'."""
        chapters = _make_chapters(5)
        batches = FixedSizeBatcher(batch_size=3).batch(chapters)
        assert len(batches) == 2
        assert batches[0].chapter_numbers == [1, 2, 3]
        assert batches[1].chapter_numbers == [4, 5]

    def test_exact_division(self):
        chapters = _make_chapters(6)
        batches = FixedSizeBatcher(batch_size=3).batch(chapters)
        assert len(batches) == 2
        assert all(len(b) == 3 for b in batches)

    def test_single_chapter(self):
        batches = FixedSizeBatcher(batch_size=3).batch(["Only chapter"])
        assert len(batches) == 1
        assert batches[0].chapter_numbers == [1]

    def test_batch_size_1(self):
        chapters = _make_chapters(3)
        batches = FixedSizeBatcher(batch_size=1).batch(chapters)
        assert len(batches) == 3
        for i, b in enumerate(batches):
            assert b.chapter_numbers == [i + 1]

    def test_large_batch_size(self):
        """Batch size larger than chapter count → single batch."""
        chapters = _make_chapters(3)
        batches = FixedSizeBatcher(batch_size=100).batch(chapters)
        assert len(batches) == 1
        assert batches[0].chapter_numbers == [1, 2, 3]

    def test_auto_chapter_numbers(self):
        """Default chapter_numbers should be 1..N."""
        chapters = _make_chapters(4)
        batches = FixedSizeBatcher(batch_size=2).batch(chapters)
        assert batches[0].chapter_numbers == [1, 2]
        assert batches[1].chapter_numbers == [3, 4]

    def test_explicit_chapter_numbers(self):
        chapters = _make_chapters(3)
        batches = FixedSizeBatcher(batch_size=2).batch(chapters, chapter_numbers=[10, 20, 30])
        assert batches[0].chapter_numbers == [10, 20]
        assert batches[1].chapter_numbers == [30]

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="chapter_texts length"):
            FixedSizeBatcher().batch(["a", "b"], chapter_numbers=[1, 2, 3])

    def test_batch_size_zero_raises(self):
        with pytest.raises(ValueError, match="batch_size must be >= 1"):
            FixedSizeBatcher(batch_size=0)

    def test_batch_size_negative_raises(self):
        with pytest.raises(ValueError):
            FixedSizeBatcher(batch_size=-1)

    def test_combined_text_is_joined(self):
        batches = FixedSizeBatcher(batch_size=2).batch(["Chapter one.", "Chapter two."])
        assert batches[0].combined_text == "Chapter one.\n\nChapter two."

    def test_texts_preserved(self):
        chapters = ["Ch1 text", "Ch2 text", "Ch3 text"]
        batches = FixedSizeBatcher(batch_size=2).batch(chapters)
        assert batches[0].texts == ["Ch1 text", "Ch2 text"]
        assert batches[1].texts == ["Ch3 text"]

    def test_empty_input(self):
        batches = FixedSizeBatcher().batch([])
        assert batches == []

    def test_christmas_carol_5_chapters_batch_3(self):
        """Plan: A Christmas Carol has 5 chapters, batch size 3 → 2 batches."""
        chapters = _make_chapters(5)
        batches = FixedSizeBatcher(batch_size=3).batch(chapters)
        assert len(batches) == 2
        assert len(batches[0]) == 3
        assert len(batches[1]) == 2

    def test_red_rising_45_chapters_batch_3(self):
        """Plan: Red Rising ~45 chapters, batch size 3 → 15 batches."""
        chapters = _make_chapters(45)
        batches = FixedSizeBatcher(batch_size=3).batch(chapters)
        assert len(batches) == 15
        assert all(len(b) == 3 for b in batches)


# ---------------------------------------------------------------------------
# TokenBudgetBatcher
# ---------------------------------------------------------------------------

class TestTokenBudgetBatcher:
    def test_default_max_tokens(self):
        b = TokenBudgetBatcher()
        assert b.max_tokens == 8000

    def test_estimate_tokens(self):
        b = TokenBudgetBatcher()
        assert b._estimate_tokens("a" * 400) == 100
        assert b._estimate_tokens("") == 1  # max(1, 0)

    def test_small_chapters_fit_single_batch(self):
        """Multiple short chapters should fit in one batch."""
        chapters = ["short " * 10] * 5  # ~50 chars each → ~12 tokens each
        batches = TokenBudgetBatcher(max_tokens=8000).batch(chapters)
        assert len(batches) == 1
        assert batches[0].chapter_numbers == [1, 2, 3, 4, 5]

    def test_large_chapter_gets_own_batch(self):
        """A chapter exceeding the budget goes into its own batch."""
        small = "word " * 10          # ~50 chars → ~12 tokens
        large = "word " * 10000       # ~50000 chars → ~12500 tokens
        chapters = [small, large, small]
        batches = TokenBudgetBatcher(max_tokens=200).batch(chapters)
        # small fits alone, large gets own batch, last small gets own batch
        assert len(batches) >= 2
        # The large chapter should be alone in a batch
        large_batch = [b for b in batches if len(b.combined_text) > 40000]
        assert len(large_batch) == 1

    def test_budget_causes_split(self):
        """Chapters that together exceed budget should split."""
        # Each chapter is ~1000 chars → ~250 tokens
        chapters = ["word " * 200] * 6
        batches = TokenBudgetBatcher(max_tokens=600).batch(chapters)
        assert len(batches) > 1
        # All chapter numbers should be covered
        all_nums = []
        for b in batches:
            all_nums.extend(b.chapter_numbers)
        assert sorted(all_nums) == [1, 2, 3, 4, 5, 6]

    def test_flush_remaining(self):
        """Last group of chapters should be flushed even if under budget."""
        chapters = ["short"] * 3
        batches = TokenBudgetBatcher(max_tokens=8000).batch(chapters)
        assert len(batches) == 1

    def test_max_tokens_too_small_raises(self):
        with pytest.raises(ValueError, match="max_tokens must be >= 100"):
            TokenBudgetBatcher(max_tokens=50)

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="chapter_texts length"):
            TokenBudgetBatcher().batch(["a"], chapter_numbers=[1, 2])

    def test_explicit_chapter_numbers(self):
        chapters = ["word " * 10] * 3
        batches = TokenBudgetBatcher(max_tokens=8000).batch(
            chapters, chapter_numbers=[10, 20, 30]
        )
        assert batches[0].chapter_numbers == [10, 20, 30]

    def test_empty_input(self):
        batches = TokenBudgetBatcher().batch([])
        assert batches == []

    def test_combined_text_join(self):
        chapters = ["Ch1.", "Ch2."]
        batches = TokenBudgetBatcher(max_tokens=8000).batch(chapters)
        assert batches[0].combined_text == "Ch1.\n\nCh2."


# ---------------------------------------------------------------------------
# get_batcher factory
# ---------------------------------------------------------------------------

class TestGetBatcher:
    def test_dict_config_fixed(self):
        """No max_tokens → FixedSizeBatcher."""
        batcher = get_batcher({"batch_size": 5})
        assert isinstance(batcher, FixedSizeBatcher)
        assert batcher.batch_size == 5

    def test_dict_config_token_budget(self):
        """max_tokens present → TokenBudgetBatcher."""
        batcher = get_batcher({"max_tokens": 4000})
        assert isinstance(batcher, TokenBudgetBatcher)
        assert batcher.max_tokens == 4000

    def test_object_config_fixed(self):
        class Cfg:
            batch_size = 7
        batcher = get_batcher(Cfg())
        assert isinstance(batcher, FixedSizeBatcher)
        assert batcher.batch_size == 7

    def test_object_config_token_budget(self):
        class Cfg:
            max_tokens = 6000
            batch_size = 3
        batcher = get_batcher(Cfg())
        assert isinstance(batcher, TokenBudgetBatcher)

    def test_default_batch_size(self):
        """Plan: 'Default 3 chapters per batch'."""
        batcher = get_batcher({})
        assert isinstance(batcher, FixedSizeBatcher)
        assert batcher.batch_size == 3

    def test_max_tokens_none_uses_fixed(self):
        batcher = get_batcher({"max_tokens": None, "batch_size": 4})
        assert isinstance(batcher, FixedSizeBatcher)
