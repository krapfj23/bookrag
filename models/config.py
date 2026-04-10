"""Pydantic settings model and YAML config loader for BookRAG.

Configuration is loaded in priority order:
  1. Environment variables (prefixed ``BOOKRAG_``)
  2. ``config.yaml`` in the project root
  3. Pydantic field defaults
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings


class BookRAGConfig(BaseSettings):
    """Central configuration for the BookRAG pipeline and API."""

    model_config = {"env_prefix": "BOOKRAG_"}

    # Pipeline
    batch_size: int = 3
    max_retries: int = 3
    booknlp_model: str = "small"
    chunk_size: int = 1500

    # Coreference resolution
    distance_threshold: int = 3
    annotate_ambiguous: bool = True

    # Cognee / LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    graph_db: str = "kuzu"
    vector_db: str = "lancedb"

    # Ontology
    auto_review: bool = False
    min_entity_frequency: int = 2

    # EPUB cleaning
    strip_html: bool = True
    remove_toc: bool = True
    remove_copyright: bool = True
    keep_epigraphs: bool = True
    keep_section_breaks: bool = True

    # Paths
    data_dir: Path = Path("data")
    books_dir: Path = Path("data/books")
    processed_dir: Path = Path("data/processed")


def load_config(config_path: str | Path = "config.yaml") -> BookRAGConfig:
    """Load configuration from a YAML file with env var overrides.

    Args:
        config_path: Path to the YAML config file. If it doesn't exist,
            defaults are used.

    Returns:
        A fully resolved ``BookRAGConfig`` instance.
    """
    config_path = Path(config_path)
    yaml_values: dict[str, Any] = {}

    if config_path.exists():
        try:
            raw = config_path.read_text(encoding="utf-8")
            parsed = yaml.safe_load(raw)
            if isinstance(parsed, dict):
                yaml_values = parsed
                logger.info("Loaded config from {}", config_path)
            else:
                logger.warning("Config file {} is not a YAML mapping — using defaults", config_path)
        except yaml.YAMLError as exc:
            logger.warning("Failed to parse {}: {} — using defaults", config_path, exc)
    else:
        logger.info("No config file at {} — using defaults", config_path)

    # Pydantic will merge yaml_values with env vars (env vars win)
    config = BookRAGConfig(**yaml_values)

    logger.info(
        "Config: batch_size={}, llm={}/{}, graph_db={}, vector_db={}",
        config.batch_size,
        config.llm_provider,
        config.llm_model,
        config.graph_db,
        config.vector_db,
    )

    return config


def ensure_directories(config: BookRAGConfig) -> None:
    """Create the pipeline data directories if they don't exist.

    Separated from load_config so that tests importing config don't trigger
    filesystem side effects.  Call this once at application startup.
    """
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.books_dir.mkdir(parents=True, exist_ok=True)
    config.processed_dir.mkdir(parents=True, exist_ok=True)
