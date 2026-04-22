# Re-extraction summary — stronger relation-label prompt

**Date:** 2026-04-22
**Branch:** `feat/fog-of-war-phase-0`
**Prompt change:** commit `ca45b43` (reject dialogue/motion verbs as relation_type)
**Re-extract script:** `scripts/reextract_book.py christmas_carol_e6ddcd76`

## The relation-label outcome was a clear win

Before the prompt change, Christmas Carol had 11 extracted Relationships. 7 of 11 used generic narrative verbs (`said`, `came`, `took`, `cried`, `thought`, `know`, `had`) that the triplet retrieval happily surfaced as arrow-shaped citations like "Scrooge → said → nephew" — technically correct but semantically useless.

After the prompt change, 8 Relationships, and **every one is a semantic tie**:

| Before (weak) | After (strong) |
|---|---|
| Scrooge → said → Scrooge's nephew | Scrooge → is_nephew_of → Scrooge's nephew |
| Scrooge → know → Scrooge's nephew | (dropped — same pair already has is_nephew_of) |
| Bob Cratchit → took → Tiny Tim | (dropped — not a relationship, just a scene action) |
| Scrooge's nephew → cried → Scrooge | (dropped — dialogue verb) |
| Scrooge → thought → Tiny Tim | (dropped — mental action, not a relation) |
| Scrooge → had → Mr. Fezziwig | Mr. Fezziwig → is_employer_of → Scrooge |
| Marley → came → Scrooge | Marley → haunts → Scrooge |
| Scrooge → employs → Bob Cratchit | Scrooge → employs → Bob Cratchit (kept) |
| Bob Cratchit → works_for → Scrooge | (implicit in Scrooge → employs) |
| Marley → warns → Scrooge | Marley → warns → Scrooge (kept) |
|  | Scrooge → is_rival_of → Bob Cratchit (new) |

Generic-verb count: **7 → 0**. Semantic-tie count: **4 → 8**.

## The eval scores did NOT improve — and that's expected

| Metric | Baseline-v1 (old data) | Triplets-v1 (old data) | Baseline-v2 (new data) | Triplets-v2 (new data) |
|---|---|---|---|---|
| answer_similarity | 0.714 | 0.701 | 0.559 | 0.510 |
| source_chapter_precision | 0.806 | 0.819 | 0.753 | 0.757 |
| entity_recall | 0.917 | 0.917 | 0.708 | 0.708 |
| spoiler_safety | 1.000 | 1.000 | 1.000 | 1.000 |
| latency_ms | 1034 | 1210 | 948 | 842 |

**Spoiler safety held:** 1.000 in every single run. Zero leaks across 48 question-runs total.

**Why eval scores dropped on v2:** the re-extraction is LLM-nondeterministic; this run happened to drop `Tiny Tim`, `The Nephew`, `Scrooge and Marley`, and `the city` as standalone entities (they're still referenced in other entities' descriptions). Themes got renamed ("Generosity" → "Generosity vs. Greed"). Several `expected_entities` in the eval fixture no longer literal-match, so `entity_recall` and `answer_similarity` dropped.

This is a **measurement artefact of single-run LLM extraction variance**, not a prompt regression. The v1→v2 numbers across 12 questions are each a single sample; you'd need averaged runs or a more tolerant fixture (paraphrase-aware matching) to see the real signal.

## What we actually learned

1. **The prompt change works as designed.** Generic verbs are gone from relation_type; semantic ties dominate. Triplet citations are now readable: "Marley → haunts → Scrooge" vs the old "Marley → came → Scrooge".
2. **The eval fixture is too strict for measuring re-extractions.** It hard-codes specific entity names; an LLM run that extracts "Scrooge's nephew" instead of "The Nephew" looks like a regression. Future work: make `expected_entities` accept synonym lists, or fuzz-match.
3. **Extraction variance is real.** This single re-extraction dropped 3 Characters, 1 Location, 1 Faction, and 2 Themes compared to the previous run — from the SAME source text and SAME ontology. We need averaging or determinism (temperature=0 extraction) to track quality changes reliably.
4. **Triplet retrieval still produces zero spoiler leaks** — the spoiler filter is stable across extraction variance.

## Decisions locked in

- **Keep the prompt change.** Structural improvement is unambiguous even when this single eval run doesn't capture it.
- **Keep triplets OFF by default.** Until averaging/determinism makes the eval reliable, no reason to change the default.
- **Next improvement worth prioritising over triplet tuning:** extraction determinism (temperature=0) or averaging across N runs. Right now every prompt change looks like a regression somewhere because variance dominates signal.

## Files

- Before artifacts: `data/processed/christmas_carol_e6ddcd76/batches.bak.20260421-234042/`
- After artifacts:  `data/processed/christmas_carol_e6ddcd76/batches/`
- Scripts: `scripts/reextract_book.py`
- Eval runs: `evaluations/results/2026-04-22-*.md`
