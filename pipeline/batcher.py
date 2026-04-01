"""Batch chapters into groups for Cognee pipeline processing.

Provides pluggable batching strategies (fixed-size, token-budget) so the
downstream Cognee pipeline can process manageable chunks of a book at a time.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class Batch:
    """A group of consecutive chapters to be processed together."""

    chapter_numbers: list[int]
    texts: list[str]
    combined_text: str = field(repr=False)

    @property
    def word_count(self) -> int:
        return len(self.combined_text.split())

    def __len__(self) -> int:
        return len(self.chapter_numbers)


class Batcher(ABC):
    """Abstract base for chapter-batching strategies."""

    @abstractmethod
    def batch(
        self, chapter_texts: list[str], chapter_numbers: list[int] | None = None
    ) -> list[Batch]:
        """Split chapters into batches.

        Args:
            chapter_texts: Ordered list of chapter plain-text strings.
            chapter_numbers: Explicit chapter numbers. Defaults to 1..N.

        Returns:
            List of ``Batch`` objects ready for pipeline consumption.
        """
        ...


class FixedSizeBatcher(Batcher):
    """Groups a fixed number of chapters per batch.

    The last batch may contain fewer chapters than ``batch_size``.
    """

    def __init__(self, batch_size: int = 3) -> None:
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")
        self.batch_size = batch_size

    def batch(
        self, chapter_texts: list[str], chapter_numbers: list[int] | None = None
    ) -> list[Batch]:
        if chapter_numbers is None:
            chapter_numbers = list(range(1, len(chapter_texts) + 1))

        if len(chapter_texts) != len(chapter_numbers):
            raise ValueError(
                f"chapter_texts length ({len(chapter_texts)}) != "
                f"chapter_numbers length ({len(chapter_numbers)})"
            )

        batches: list[Batch] = []
        for i in range(0, len(chapter_texts), self.batch_size):
            nums = chapter_numbers[i : i + self.batch_size]
            texts = chapter_texts[i : i + self.batch_size]
            combined = "\n\n".join(texts)
            batches.append(Batch(chapter_numbers=nums, texts=texts, combined_text=combined))

        for idx, b in enumerate(batches):
            logger.info(
                "Batch {:>2}: chapters {} ({} words)",
                idx + 1,
                b.chapter_numbers,
                b.word_count,
            )

        logger.info(
            "Created {} batches from {} chapters (batch_size={})",
            len(batches),
            len(chapter_texts),
            self.batch_size,
        )
        return batches


class TokenBudgetBatcher(Batcher):
    """Groups chapters until a token budget is reached.

    Uses a simple whitespace tokenizer (1 token ~ 1 word * 1.3) as a rough
    approximation.  A proper sub-word tokenizer can be swapped in later.
    """

    CHARS_PER_TOKEN = 4  # rough average for English text

    def __init__(self, max_tokens: int = 8000) -> None:
        if max_tokens < 100:
            raise ValueError(f"max_tokens must be >= 100, got {max_tokens}")
        self.max_tokens = max_tokens

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate based on character count."""
        return max(1, len(text) // self.CHARS_PER_TOKEN)

    def batch(
        self, chapter_texts: list[str], chapter_numbers: list[int] | None = None
    ) -> list[Batch]:
        if chapter_numbers is None:
            chapter_numbers = list(range(1, len(chapter_texts) + 1))

        if len(chapter_texts) != len(chapter_numbers):
            raise ValueError(
                f"chapter_texts length ({len(chapter_texts)}) != "
                f"chapter_numbers length ({len(chapter_numbers)})"
            )

        batches: list[Batch] = []
        current_nums: list[int] = []
        current_texts: list[str] = []
        current_tokens = 0

        for num, text in zip(chapter_numbers, chapter_texts):
            est = self._estimate_tokens(text)

            # If a single chapter exceeds budget, give it its own batch
            if current_texts and (current_tokens + est) > self.max_tokens:
                combined = "\n\n".join(current_texts)
                batches.append(
                    Batch(
                        chapter_numbers=list(current_nums),
                        texts=list(current_texts),
                        combined_text=combined,
                    )
                )
                current_nums = []
                current_texts = []
                current_tokens = 0

            current_nums.append(num)
            current_texts.append(text)
            current_tokens += est

        # Flush remaining
        if current_texts:
            combined = "\n\n".join(current_texts)
            batches.append(
                Batch(
                    chapter_numbers=list(current_nums),
                    texts=list(current_texts),
                    combined_text=combined,
                )
            )

        for idx, b in enumerate(batches):
            logger.info(
                "Batch {:>2}: chapters {} (~{} tokens, {} words)",
                idx + 1,
                b.chapter_numbers,
                self._estimate_tokens(b.combined_text),
                b.word_count,
            )

        logger.info(
            "Created {} batches from {} chapters (max_tokens={})",
            len(batches),
            len(chapter_texts),
            self.max_tokens,
        )
        return batches


def get_batcher(config: Any) -> Batcher:
    """Factory: return the appropriate Batcher based on config.

    Args:
        config: A config object (or dict) with at least ``batch_size``.
            If it has ``max_tokens``, a ``TokenBudgetBatcher`` is returned
            instead of a ``FixedSizeBatcher``.

    Returns:
        A configured ``Batcher`` instance.
    """
    if isinstance(config, dict):
        max_tokens = config.get("max_tokens")
        batch_size = config.get("batch_size", 3)
    else:
        max_tokens = getattr(config, "max_tokens", None)
        batch_size = getattr(config, "batch_size", 3)

    if max_tokens is not None:
        logger.info("Using TokenBudgetBatcher (max_tokens={})", max_tokens)
        return TokenBudgetBatcher(max_tokens=max_tokens)

    logger.info("Using FixedSizeBatcher (batch_size={})", batch_size)
    return FixedSizeBatcher(batch_size=batch_size)
