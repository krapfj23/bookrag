"""Pipeline orchestrator — manages the full flow from EPUB to validated KG.

Runs stages sequentially, persists state to JSON, supports resume on crash,
and exposes progress at both stage and batch granularity.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from loguru import logger

from models.pipeline_state import PipelineState, StageStatus, save_state, load_state
from pipeline.batcher import get_batcher, Batch
from pipeline.booknlp_runner import (
    run_booknlp,
    parse_booknlp_output,
    create_stub_output,
    BookNLPOutput,
)
from pipeline.cognee_pipeline import run_bookrag_pipeline, configure_cognee
from pipeline.coref_resolver import (
    Token as CorefToken,
    EntityMention as CorefEntityMention,
    CharacterProfile as CorefCharacterProfile,
    CorefConfig,
    resolve_coreferences,
    save_coref_outputs,
)
from pipeline.epub_parser import parse_epub
from pipeline.ontology_discovery import discover_ontology


# Ordered list of pipeline stages
STAGES = [
    "parse_epub",
    "run_booknlp",
    "resolve_coref",
    "discover_ontology",
    "review_ontology",
    "run_cognee_batches",
    "validate",
]


class PipelineOrchestrator:
    """Manages the end-to-end BookRAG pipeline for a single book.

    Each stage updates a ``PipelineState`` that is persisted to disk after
    every transition, enabling crash recovery and progress queries.
    """

    def __init__(self, config: Any) -> None:
        self.config = config
        self._threads: dict[str, threading.Thread] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_in_background(self, book_id: str, epub_path: str | Path) -> None:
        """Launch the full pipeline in a background daemon thread.

        Args:
            book_id: Unique identifier for the book.
            epub_path: Path to the uploaded EPUB file.
        """
        if book_id in self._threads and self._threads[book_id].is_alive():
            logger.warning("Pipeline already running for book_id={}", book_id)
            return

        thread = threading.Thread(
            target=self._run_sync_wrapper,
            args=(book_id, epub_path),
            name=f"pipeline-{book_id}",
            daemon=True,
        )
        self._threads[book_id] = thread
        thread.start()
        logger.info("Background pipeline started for book_id={}", book_id)

    def get_state(self, book_id: str) -> PipelineState | None:
        """Load and return the current pipeline state from disk."""
        state_path = self._state_path(book_id)
        if not state_path.exists():
            return None
        return load_state(state_path)

    # ------------------------------------------------------------------
    # Internal: sync wrapper for threading
    # ------------------------------------------------------------------

    def _run_sync_wrapper(self, book_id: str, epub_path: str | Path) -> None:
        """Sync entry point that runs the async pipeline in a new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_pipeline(book_id, Path(epub_path)))
        except Exception as exc:
            logger.exception("Pipeline failed for book_id={}: {}", book_id, exc)
        finally:
            loop.close()

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    async def _run_pipeline(self, book_id: str, epub_path: Path) -> None:
        """Execute all pipeline stages sequentially with crash-resume support."""
        state = self._init_or_resume_state(book_id)
        log_ctx = logger.bind(book_id=book_id)

        log_ctx.info("Pipeline starting for book_id={}", book_id)
        state.status = "processing"
        self._persist(state)

        # Shared context across stages
        ctx: dict[str, Any] = {
            "epub_path": epub_path,
            "parsed_book": None,
            "booknlp_output": None,
            "coref_output": None,
            "ontology": None,
            "batches": None,
        }

        for stage_name in STAGES:
            stage_status = state.stages[stage_name]

            # Skip already-completed stages (resume support)
            if stage_status.status == "complete":
                log_ctx.info("Skipping completed stage: {}", stage_name)
                continue

            # Optional review stage — skip if auto_review is off
            if stage_name == "review_ontology" and not getattr(self.config, "auto_review", False):
                state.stages[stage_name] = StageStatus(status="complete", duration_seconds=0.0)
                self._persist(state)
                log_ctx.info("Skipping ontology review (auto_review=False)")
                continue

            log_ctx.info("Starting stage: {}", stage_name)
            stage_status.status = "running"
            self._persist(state)
            t0 = time.monotonic()

            try:
                await self._execute_stage(stage_name, state, ctx, log_ctx)
                elapsed = time.monotonic() - t0
                state.stages[stage_name] = StageStatus(
                    status="complete", duration_seconds=round(elapsed, 2)
                )
                self._persist(state)
                log_ctx.info("Stage {} complete ({:.1f}s)", stage_name, elapsed)

            except Exception as exc:
                elapsed = time.monotonic() - t0
                # Log full traceback for debugging, but only store the
                # exception summary in state to avoid leaking internal paths
                # and code structure via the API.
                log_ctx.error(
                    "Stage {} failed after {:.1f}s:\n{}",
                    stage_name, elapsed, traceback.format_exc(),
                )
                state.stages[stage_name] = StageStatus(
                    status="failed",
                    duration_seconds=round(elapsed, 2),
                    error=f"{type(exc).__name__}: {exc}",
                )
                state.status = "failed"
                self._persist(state)
                return

        state.status = "complete"
        state.ready_for_query = True
        self._persist(state)
        log_ctx.info("Pipeline complete for book_id={}", book_id)

    async def _execute_stage(
        self,
        stage_name: str,
        state: PipelineState,
        ctx: dict[str, Any],
        log: Any,
    ) -> None:
        """Dispatch to the appropriate stage handler."""
        handler = getattr(self, f"_stage_{stage_name}", None)
        if handler is None:
            raise NotImplementedError(f"No handler for stage: {stage_name}")
        await handler(state, ctx, log)

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    async def _stage_parse_epub(
        self, state: PipelineState, ctx: dict[str, Any], log: Any
    ) -> None:
        """Parse the EPUB into chapter-segmented text."""
        epub_path = ctx["epub_path"]
        output_dir = self._book_dir(state.book_id) / "raw"
        parsed = parse_epub(epub_path, output_dir=output_dir)
        ctx["parsed_book"] = parsed
        log.info("Parsed {} chapters from EPUB", parsed.chapter_count)

    async def _stage_run_booknlp(
        self, state: PipelineState, ctx: dict[str, Any], log: Any
    ) -> None:
        """Run BookNLP on the full text to extract entities and quotes.

        NOTE: Requires booknlp package. This stage produces annotations used
        by the graph extraction step. Falls back to stub output if booknlp
        is not installed.
        """
        parsed = ctx["parsed_book"]
        if parsed is None:
            # Reload from disk if resuming
            raw_dir = self._book_dir(state.book_id) / "raw"
            full_text_path = raw_dir / "full_text.txt"
            if not full_text_path.exists():
                raise FileNotFoundError(f"Cannot resume run_booknlp: {full_text_path} missing")
            full_text = full_text_path.read_text(encoding="utf-8")
        else:
            full_text = parsed.full_text

        booknlp_dir = self._book_dir(state.book_id) / "booknlp"
        booknlp_dir.mkdir(parents=True, exist_ok=True)
        model_size = getattr(self.config, "booknlp_model", "small")

        # Check if BookNLP outputs already exist (resume support)
        book_file = booknlp_dir / f"{state.book_id}.book"
        if book_file.exists():
            log.info("BookNLP outputs already exist — re-parsing from disk")
            booknlp_result = parse_booknlp_output(booknlp_dir, state.book_id)
        else:
            try:
                booknlp_result = await run_booknlp(
                    full_text, booknlp_dir, state.book_id, model_size
                )
            except ImportError:
                log.warning("booknlp not installed — using stub annotations")
                booknlp_result = create_stub_output(state.book_id)

        ctx["booknlp_output"] = booknlp_result.to_pipeline_dict()
        ctx["booknlp_result"] = booknlp_result  # full structured output for coref
        log.info(
            "BookNLP complete: {} characters, {} entities, {} quotes",
            booknlp_result.character_count,
            booknlp_result.entity_count,
            booknlp_result.quote_count,
        )

    async def _stage_resolve_coref(
        self, state: PipelineState, ctx: dict[str, Any], log: Any
    ) -> None:
        """Resolve coreferences via parenthetical insertion.

        Reads BookNLP structured output, applies distance + ambiguity rules,
        and produces resolved chapter text like:
            "he [Scrooge] muttered to his [Scrooge] clerk [Bob Cratchit]"

        Outputs:
            coref/clusters.json, coref/resolution_log.json,
            resolved/chapters/*.txt, resolved/full_text_resolved.txt
        """
        booknlp_result: BookNLPOutput | None = ctx.get("booknlp_result")
        parsed = ctx.get("parsed_book")

        distance_threshold = getattr(self.config, "distance_threshold", 3)
        annotate_ambiguous = getattr(self.config, "annotate_ambiguous", True)
        coref_config = CorefConfig(
            distance_threshold=distance_threshold,
            annotate_ambiguous=annotate_ambiguous,
        )

        # If no structured BookNLP result, check for outputs on disk (resume)
        if booknlp_result is None or booknlp_result.entity_count == 0:
            resolved_dir = self._book_dir(state.book_id) / "resolved"
            if resolved_dir.exists():
                log.info("Resolved text already on disk — loading")
                chapter_files = sorted(
                    (resolved_dir / "chapters").glob("chapter_*.txt")
                )
                resolved_chapters = [f.read_text(encoding="utf-8") for f in chapter_files]
                ctx["coref_output"] = ctx.get("booknlp_output", {})
                ctx["resolved_chapters"] = resolved_chapters
                log.info("Loaded {} resolved chapters from disk", len(resolved_chapters))
                return

            # No BookNLP data and no resolved text — passthrough raw chapters
            log.warning("No BookNLP annotations available — skipping coref resolution")
            ctx["coref_output"] = ctx.get("booknlp_output", {})
            if parsed:
                ctx["resolved_chapters"] = parsed.chapter_texts
            return

        # Convert booknlp_runner dataclasses → coref_resolver dataclasses
        coref_tokens = [
            CorefToken(
                token_id=t.token_id,
                sentence_id=0,  # will be filled below
                token_offset_begin=t.start_char,
                token_offset_end=t.end_char,
                word=t.text,
                pos=t.pos,
                coref_id=t.coref_id if t.coref_id is not None else -1,
            )
            for t in booknlp_result.tokens
        ]

        # Assign sentence IDs: BookNLP tokens don't always carry sentence_id
        # in our parsed format. We approximate by splitting on sentence-ending POS.
        _assign_sentence_ids(coref_tokens)

        coref_entities = [
            CorefEntityMention(
                coref_id=e.coref_id,
                start_token=e.start_token,
                end_token=e.end_token,
                prop=e.prop,
                cat=e.cat,
                text=e.text,
            )
            for e in booknlp_result.entities
        ]

        coref_characters = [
            CorefCharacterProfile(
                coref_id=c.coref_id,
                name=c.canonical_name,
                aliases=list(c.aliases.keys()),
            )
            for c in booknlp_result.characters
        ]

        # Chapter boundaries as token ranges
        chapter_texts = parsed.chapter_texts if parsed else []
        chapter_boundaries = _compute_chapter_token_boundaries(
            coref_tokens, chapter_texts
        )

        log.info(
            "Running coref resolution: {} tokens, {} entities, {} characters "
            "(distance_threshold={}, annotate_ambiguous={})",
            len(coref_tokens), len(coref_entities), len(coref_characters),
            distance_threshold, annotate_ambiguous,
        )

        coref_result = await asyncio.to_thread(
            resolve_coreferences,
            tokens=coref_tokens,
            entities=coref_entities,
            characters=coref_characters,
            chapter_texts=chapter_texts,
            chapter_boundaries=chapter_boundaries,
            config=coref_config,
        )

        # Save outputs to disk
        base_dir = getattr(self.config, "processed_dir", Path("data/processed"))
        save_coref_outputs(coref_result, state.book_id, base_dir=base_dir)

        # Pass resolved text downstream
        ctx["coref_output"] = ctx.get("booknlp_output", {})
        ctx["resolved_chapters"] = coref_result.resolved_chapters

        log.info(
            "Coref resolution complete: {} insertions across {} chapters",
            len(coref_result.resolution_log),
            len(coref_result.resolved_chapters),
        )

    async def _stage_discover_ontology(
        self, state: PipelineState, ctx: dict[str, Any], log: Any
    ) -> None:
        """Discover ontology from BookNLP output via BERTopic + TF-IDF.

        Uses ontology_discovery.discover_ontology() to extract entity types,
        themes, and relation types, then generates an OWL file. If the
        ontology already exists on disk (resume), it is loaded instead.

        Outputs:
            ontology/discovered_entities.json, ontology/book_ontology.owl
        """
        ontology_dir = self._book_dir(state.book_id) / "ontology"
        owl_path = ontology_dir / "book_ontology.owl"
        discovery_path = ontology_dir / "discovered_entities.json"

        # Resume: if discovery output already exists, load it
        if discovery_path.exists():
            discovery_data = json.loads(discovery_path.read_text(encoding="utf-8"))
            log.info("Loaded existing ontology discovery from {}", discovery_path)
            ctx["ontology"] = discovery_data
            return

        # Build the booknlp_output dict that discover_ontology expects:
        #   {"book_json": {...}, "entities_tsv": [...]}
        booknlp_result: BookNLPOutput | None = ctx.get("booknlp_result")
        if booknlp_result is not None:
            # Convert structured output to the dict format ontology_discovery expects
            book_json = {
                "characters": [
                    {
                        "id": c.coref_id,
                        "names": c.aliases,
                        "agent": c.agent_actions,
                        "patient": c.patient_actions,
                        "mod": c.modifiers,
                        "poss": c.possessions,
                        "g": c.gender,
                    }
                    for c in booknlp_result.characters
                ]
            }
            entities_tsv = [
                {
                    "COREF": str(e.coref_id),
                    "start_token": str(e.start_token),
                    "end_token": str(e.end_token),
                    "prop": e.prop,
                    "cat": e.cat,
                    "text": e.text,
                }
                for e in booknlp_result.entities
            ]
            booknlp_for_ontology = {
                "book_json": book_json,
                "entities_tsv": entities_tsv,
            }
        else:
            booknlp_for_ontology = {"book_json": {}, "entities_tsv": []}

        # Get the full text (prefer resolved, fall back to raw)
        resolved_chapters = ctx.get("resolved_chapters")
        parsed = ctx.get("parsed_book")
        if resolved_chapters:
            full_text = "\n\n".join(resolved_chapters)
        elif parsed:
            full_text = parsed.full_text
        else:
            raw_path = self._book_dir(state.book_id) / "raw" / "full_text.txt"
            if raw_path.exists():
                full_text = raw_path.read_text(encoding="utf-8")
            else:
                full_text = ""

        ontology_config = {
            "min_entity_frequency": getattr(self.config, "min_entity_frequency", 2),
        }

        log.info("Running ontology discovery for book_id={}", state.book_id)

        ontology_result = await asyncio.to_thread(
            discover_ontology,
            booknlp_output=booknlp_for_ontology,
            full_text=full_text,
            book_id=state.book_id,
            config=ontology_config,
        )

        # Store result for downstream stages
        ctx["ontology"] = {
            "discovered_entities": ontology_result.discovered_entities,
            "discovered_themes": ontology_result.discovered_themes,
            "discovered_relations": ontology_result.discovered_relations,
            "owl_path": str(ontology_result.owl_path),
        }

        log.info(
            "Ontology discovery complete: {} entity types, {} themes, {} relations",
            len(ontology_result.discovered_entities),
            len(ontology_result.discovered_themes),
            len(ontology_result.discovered_relations),
        )

    async def _stage_review_ontology(
        self, state: PipelineState, ctx: dict[str, Any], log: Any
    ) -> None:
        """Optional manual ontology review step.

        Only runs when config.auto_review is True. In that case, an LLM
        reviews and refines the discovered ontology.
        """
        log.info("Auto-review of ontology (placeholder — no changes applied)")

    async def _stage_run_cognee_batches(
        self, state: PipelineState, ctx: dict[str, Any], log: Any
    ) -> None:
        """Batch chapters and run the Cognee extraction pipeline.

        Prefers resolved (coref-annotated) chapters over raw chapters.
        """
        # Configure Cognee's LLM provider/model/key from our config
        configure_cognee(self.config)

        # Prefer resolved chapters (coref output), fall back to raw
        resolved_chapters = ctx.get("resolved_chapters")
        if resolved_chapters:
            chapter_texts = resolved_chapters
            log.info("Using {} coref-resolved chapters for batching", len(chapter_texts))
        else:
            parsed = ctx.get("parsed_book")
            if parsed is None:
                # Try resolved chapters on disk first, then raw
                resolved_dir = self._book_dir(state.book_id) / "resolved" / "chapters"
                raw_dir = self._book_dir(state.book_id) / "raw" / "chapters"
                if resolved_dir.exists():
                    chapter_files = sorted(resolved_dir.glob("chapter_*.txt"))
                    chapter_texts = [f.read_text(encoding="utf-8") for f in chapter_files]
                    log.info("Loaded {} resolved chapters from disk", len(chapter_texts))
                elif raw_dir.exists():
                    chapter_files = sorted(raw_dir.glob("chapter_*.txt"))
                    chapter_texts = [f.read_text(encoding="utf-8") for f in chapter_files]
                    log.info("Loaded {} raw chapters from disk (no resolved text)", len(chapter_texts))
                else:
                    raise FileNotFoundError(
                        f"Cannot resume: neither {resolved_dir} nor {raw_dir} exist"
                    )
            else:
                chapter_texts = parsed.chapter_texts

        batcher = get_batcher(self.config)
        batches = batcher.batch(chapter_texts)

        state.total_batches = len(batches)
        state.current_batch = 0
        self._persist(state)

        booknlp_output = ctx.get("coref_output") or ctx.get("booknlp_output", {})
        ontology = ctx.get("ontology", {})
        max_retries = getattr(self.config, "max_retries", 3)
        chunk_size = getattr(self.config, "chunk_size", 1500)

        for idx, batch in enumerate(batches):
            state.current_batch = idx + 1
            self._persist(state)
            log.info(
                "Processing batch {}/{} (chapters {})",
                idx + 1,
                len(batches),
                batch.chapter_numbers,
            )

            success = False
            for attempt in range(1, max_retries + 1):
                try:
                    await run_bookrag_pipeline(
                        batch=batch,
                        booknlp_output=booknlp_output,
                        ontology=ontology,
                        book_id=state.book_id,
                        chunk_size=chunk_size,
                        max_retries=max_retries,
                    )
                    success = True
                    break
                except Exception as exc:
                    log.warning(
                        "Batch {} attempt {}/{} failed: {}",
                        idx + 1,
                        attempt,
                        max_retries,
                        exc,
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)

            if not success:
                raise RuntimeError(
                    f"Batch {idx + 1} (chapters {batch.chapter_numbers}) "
                    f"failed after {max_retries} retries"
                )

        log.info("All {} batches processed successfully", len(batches))

    async def _stage_validate(
        self, state: PipelineState, ctx: dict[str, Any], log: Any
    ) -> None:
        """Run known-answer validation checks on the constructed knowledge graph.

        Uses validation/test_suite.py with fixture files from
        validation/fixtures/{book_id}.json. Books without a fixture
        file are skipped with a note.
        """
        from validation.test_suite import run_validation, save_validation_report

        processed_dir = Path(getattr(self.config, "processed_dir", "data/processed"))
        validation_dir = self._book_dir(state.book_id) / "validation"

        report = await run_validation(state.book_id, processed_dir)
        save_validation_report(report, validation_dir)

        if report.all_passed:
            log.info(
                "Validation passed: {}/{} checks OK for '{}'",
                report.passed, report.total, state.book_id,
            )
        else:
            log.warning(
                "Validation: {}/{} passed, {} failed for '{}'",
                report.passed, report.total, report.failed, state.book_id,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _state_path(self, book_id: str) -> Path:
        """Path to the persisted pipeline state JSON for a book."""
        return self._book_dir(book_id) / "pipeline_state.json"

    def _book_dir(self, book_id: str) -> Path:
        """Base processed directory for a book."""
        base = getattr(self.config, "processed_dir", Path("data/processed"))
        return Path(base) / book_id

    def _init_or_resume_state(self, book_id: str) -> PipelineState:
        """Load existing state or create a fresh one."""
        state_path = self._state_path(book_id)
        if state_path.exists():
            state = load_state(state_path)
            if state.status == "complete":
                logger.info("Book {} already complete — resetting for reprocessing", book_id)
                state = PipelineState.new(book_id, STAGES)
            else:
                logger.info("Resuming pipeline for book_id={} from saved state", book_id)
                return state
        else:
            state = PipelineState.new(book_id, STAGES)

        state_path.parent.mkdir(parents=True, exist_ok=True)
        save_state(state, state_path)
        return state

    def _persist(self, state: PipelineState) -> None:
        """Save pipeline state to disk."""
        state_path = self._state_path(state.book_id)
        save_state(state, state_path)



def _assign_sentence_ids(tokens: list[CorefToken]) -> None:
    """Assign sentence_id to tokens by detecting sentence boundaries.

    Uses a simple heuristic: a sentence ends at a period, exclamation mark,
    or question mark POS tag (`.`). This is approximate but sufficient for
    the distance rule in coref resolution.
    """
    sentence_id = 0
    sentence_ending_pos = {".", "!", "?"}
    for tok in tokens:
        tok.sentence_id = sentence_id
        if tok.pos in sentence_ending_pos or tok.word in (".", "!", "?"):
            sentence_id += 1


def _compute_chapter_token_boundaries(
    tokens: list[CorefToken],
    chapter_texts: list[str],
) -> list[tuple[int, int]]:
    """Compute (start_token_id, end_token_id) boundaries per chapter.

    Uses character offsets: each chapter's char range maps to a token range.
    Falls back to a single boundary spanning all tokens if chapter_texts is empty.
    """
    if not chapter_texts or not tokens:
        if tokens:
            return [(tokens[0].token_id, tokens[-1].token_id + 1)]
        return []

    # Build chapter char boundaries
    boundaries: list[tuple[int, int]] = []
    cursor = 0
    for ch_text in chapter_texts:
        start = cursor
        end = cursor + len(ch_text)
        boundaries.append((start, end))
        cursor = end + 2  # account for "\n\n" join separator

    # Map each chapter's char range to token ID range
    token_boundaries: list[tuple[int, int]] = []
    for char_start, char_end in boundaries:
        chapter_tokens = [
            t for t in tokens
            if t.token_offset_begin >= char_start and t.token_offset_begin < char_end
        ]
        if chapter_tokens:
            token_boundaries.append(
                (chapter_tokens[0].token_id, chapter_tokens[-1].token_id + 1)
            )
        else:
            # Empty chapter — use dummy range
            token_boundaries.append((0, 0))

    return token_boundaries
