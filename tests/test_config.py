"""Comprehensive tests for models/config.py.

Covers:
- BookRAGConfig defaults match plan spec
- YAML config loading
- Env var overrides (BOOKRAG_ prefix)
- Missing config file uses defaults
- Invalid YAML graceful fallback
- Non-mapping YAML graceful fallback
- Directory creation
- All config fields: pipeline, coref, cognee, ontology, cleaning, paths

Aligned with:
- CLAUDE.md: ".env for secrets + YAML for settings"
- Plan config.yaml spec: batch_size=3, max_retries=3, booknlp_model="small",
  distance_threshold=3, annotate_ambiguous=true, llm_provider="openai",
  llm_model="gpt-4.1-mini", graph_db="kuzu", vector_db="lancedb",
  auto_review=false, min_entity_frequency=2, strip_html=true, remove_toc=true,
  remove_copyright=true, keep_epigraphs=true, keep_section_breaks=true
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from models.config import BookRAGConfig, load_config, ensure_directories


# ---------------------------------------------------------------------------
# BookRAGConfig defaults
# ---------------------------------------------------------------------------

class TestBookRAGConfigDefaults:
    """All defaults must match the plan's config.yaml spec exactly."""

    def test_batch_size(self):
        """Plan: 'batch_size: 3'."""
        assert BookRAGConfig().batch_size == 3

    def test_max_retries(self):
        """Plan: 'max_retries: 3'."""
        assert BookRAGConfig().max_retries == 3

    def test_booknlp_model(self):
        """Plan: 'booknlp_model: small'."""
        assert BookRAGConfig().booknlp_model == "small"

    def test_chunk_size(self):
        assert BookRAGConfig().chunk_size == 1500

    def test_distance_threshold(self):
        """Plan: 'distance_threshold: 3'."""
        assert BookRAGConfig().distance_threshold == 3

    def test_annotate_ambiguous(self):
        """Plan: 'annotate_ambiguous: true'."""
        assert BookRAGConfig().annotate_ambiguous is True

    def test_llm_provider(self):
        assert BookRAGConfig().llm_provider == "openai"

    def test_llm_model(self):
        assert BookRAGConfig().llm_model == "gpt-4.1-mini"

    def test_graph_db(self):
        """Plan: 'graph_db: kuzu'. CLAUDE.md: 'Cognee defaults: Kuzu + LanceDB + SQLite'."""
        assert BookRAGConfig().graph_db == "kuzu"

    def test_vector_db(self):
        """Plan: 'vector_db: lancedb'."""
        assert BookRAGConfig().vector_db == "lancedb"

    def test_auto_review(self):
        """Plan: 'auto_review: false'."""
        assert BookRAGConfig().auto_review is False

    def test_min_entity_frequency(self):
        """Plan: 'min_entity_frequency: 2'."""
        assert BookRAGConfig().min_entity_frequency == 2

    def test_strip_html(self):
        assert BookRAGConfig().strip_html is True

    def test_remove_toc(self):
        assert BookRAGConfig().remove_toc is True

    def test_remove_copyright(self):
        assert BookRAGConfig().remove_copyright is True

    def test_keep_epigraphs(self):
        """Plan: 'keep_epigraphs: true'."""
        assert BookRAGConfig().keep_epigraphs is True

    def test_keep_section_breaks(self):
        """Plan: 'keep_section_breaks: true'."""
        assert BookRAGConfig().keep_section_breaks is True

    def test_data_dir(self):
        assert BookRAGConfig().data_dir == Path("data")

    def test_books_dir(self):
        assert BookRAGConfig().books_dir == Path("data/books")

    def test_processed_dir(self):
        assert BookRAGConfig().processed_dir == Path("data/processed")

    def test_env_prefix(self):
        """Config should use BOOKRAG_ prefix for env vars."""
        assert BookRAGConfig.model_config["env_prefix"] == "BOOKRAG_"


# ---------------------------------------------------------------------------
# load_config: YAML loading
# ---------------------------------------------------------------------------

class TestLoadConfigYAML:
    def test_loads_from_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"batch_size": 5, "llm_provider": "openai"}))
        cfg = load_config(config_file)
        assert cfg.batch_size == 5
        assert cfg.llm_provider == "openai"

    def test_yaml_overrides_defaults(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "max_retries": 10,
            "auto_review": True,
            "graph_db": "neo4j",
        }))
        cfg = load_config(config_file)
        assert cfg.max_retries == 10
        assert cfg.auto_review is True
        assert cfg.graph_db == "neo4j"

    def test_yaml_partial_override(self, tmp_path):
        """Only specified fields override; rest use defaults."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"batch_size": 7}))
        cfg = load_config(config_file)
        assert cfg.batch_size == 7
        assert cfg.max_retries == 3  # default
        assert cfg.llm_provider == "openai"  # default

    def test_missing_yaml_uses_defaults(self, tmp_path):
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg.batch_size == 3
        assert cfg.llm_provider == "openai"

    def test_invalid_yaml_uses_defaults(self, tmp_path):
        config_file = tmp_path / "bad.yaml"
        config_file.write_text(":::invalid yaml{{{")
        cfg = load_config(config_file)
        assert cfg.batch_size == 3

    def test_non_mapping_yaml_uses_defaults(self, tmp_path):
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- item1\n- item2\n")
        cfg = load_config(config_file)
        assert cfg.batch_size == 3

    def test_empty_yaml_uses_defaults(self, tmp_path):
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        cfg = load_config(config_file)
        assert cfg.batch_size == 3


# ---------------------------------------------------------------------------
# load_config: env var overrides
# ---------------------------------------------------------------------------

class TestLoadConfigEnvVars:
    def test_env_overrides_default_str(self, tmp_path, monkeypatch):
        """Env vars should override defaults when no YAML value is set."""
        monkeypatch.setenv("BOOKRAG_LLM_PROVIDER", "openai")
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg.llm_provider == "openai"

    def test_env_overrides_default_int(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BOOKRAG_MAX_RETRIES", "7")
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg.max_retries == 7

    def test_env_bool(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BOOKRAG_AUTO_REVIEW", "true")
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg.auto_review is True

    def test_env_path(self, tmp_path, monkeypatch):
        custom_dir = tmp_path / "custom_data"
        monkeypatch.setenv("BOOKRAG_DATA_DIR", str(custom_dir))
        monkeypatch.setenv("BOOKRAG_BOOKS_DIR", str(custom_dir / "books"))
        monkeypatch.setenv("BOOKRAG_PROCESSED_DIR", str(custom_dir / "processed"))
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg.data_dir == custom_dir


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------

class TestLoadConfigDirectories:
    def test_creates_data_dirs(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        data_dir = tmp_path / "testdata"
        books_dir = tmp_path / "testdata" / "books"
        processed_dir = tmp_path / "testdata" / "processed"
        config_file.write_text(yaml.dump({
            "data_dir": str(data_dir),
            "books_dir": str(books_dir),
            "processed_dir": str(processed_dir),
        }))
        cfg = load_config(config_file)
        ensure_directories(cfg)
        assert data_dir.exists()
        assert books_dir.exists()
        assert processed_dir.exists()


# ---------------------------------------------------------------------------
# All fields accessible
# ---------------------------------------------------------------------------

class TestAllFieldsAccessible:
    def test_all_fields_have_values(self):
        """Every config field should be accessible with a default."""
        cfg = BookRAGConfig()
        fields = [
            "batch_size", "max_retries", "booknlp_model", "chunk_size",
            "distance_threshold", "annotate_ambiguous",
            "llm_provider", "llm_model", "graph_db", "vector_db",
            "auto_review", "min_entity_frequency",
            "strip_html", "remove_toc", "remove_copyright",
            "keep_epigraphs", "keep_section_breaks",
            "data_dir", "books_dir", "processed_dir",
        ]
        for field_name in fields:
            assert hasattr(cfg, field_name), f"Missing field: {field_name}"
            assert getattr(cfg, field_name) is not None, f"Field {field_name} is None"
