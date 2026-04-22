"""Tests for pipeline/spoiler_filter.py — chapter filtering primitives."""

import pytest


class TestEffectiveLatestChapter:
    """effective_latest_chapter returns the greatest chapter value a node 'knows about'."""

    def test_uses_last_known_when_greater_than_first(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        node = {"first_chapter": 1, "last_known_chapter": 5}
        assert effective_latest_chapter(node) == 5

    def test_uses_first_when_last_known_missing(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        node = {"first_chapter": 3}
        assert effective_latest_chapter(node) == 3

    def test_uses_chapter_for_plot_events(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        node = {"chapter": 7}
        assert effective_latest_chapter(node) == 7

    def test_returns_none_when_no_chapter_info(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        assert effective_latest_chapter({}) is None

    def test_accepts_pydantic_like_object(self):
        from pipeline.spoiler_filter import effective_latest_chapter

        class Fake:
            first_chapter = 1
            last_known_chapter = 4

        assert effective_latest_chapter(Fake()) == 4

    def test_max_across_all_fields(self):
        from pipeline.spoiler_filter import effective_latest_chapter
        node = {"first_chapter": 1, "chapter": 9, "last_known_chapter": 3}
        assert effective_latest_chapter(node) == 9
