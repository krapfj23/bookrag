# Triplet indexing — A/B evaluation summary

**Date:** 2026-04-22
**Branch:** `feat/fog-of-war-phase-0`
**Spec:** [../../docs/superpowers/specs/2026-04-22-triplet-indexing.md](../../docs/superpowers/specs/2026-04-22-triplet-indexing.md)
**Fixture:** [../christmas_carol_questions.json](../christmas_carol_questions.json) (12 questions)
**Data:** `christmas_carol_e6ddcd76` — 1 processed batch with 14 Characters, 11 Relationships, 12 PlotEvents.

## Headline

| Metric | Baseline | Triplets | Δ | Spec gate | Pass |
|---|---|---|---|---|---|
| answer_similarity | 0.714 | 0.701 | −0.013 | within ±0.03 | ✅ |
| source_chapter_precision | 0.806 | 0.819 | +0.013 | ≥ baseline | ✅ |
| entity_recall | 0.917 | 0.917 | 0 | ≥ baseline −0.05 | ✅ |
| spoiler_safety | **1.000** | **1.000** | 0 | = 1.000 (ship-blocker) | ✅ |
| latency_ms (mean) | 1034 | 1210 | +176 (+17%) | ≤ 1.5× baseline | ✅ |

**All five spec gates pass.** Zero spoiler leaks across 24 question-runs.

## What changed in answers

Triplets-mode answers now cite relationships alongside entities. Examples from the per-question details:

- **cc-001 (Who is Marley...)** baseline cited 4 Character entities; triplets cited 3 Characters + 1 Relationship (`Marley → warns → Scrooge`). The arrow citation is more informative than four overlapping Scrooge/Marley entity blobs.
- **cc-004 (What does Fred invite Scrooge to)** baseline never explicitly surfaces the invitation edge; triplets surface `Scrooge → said → Scrooge's nephew` and `Scrooge → know → Scrooge's nephew`. Weaker relation labels (the extraction stored verbs like "said" not "invited by") but the structure is there.
- **cc-009 (transformation)** both modes produced identical text-level answers; triplets added no new information because the relevant relations happen to be thematic rather than entity-edged.

## Failure mode noted for next slice

Extracted Relationships in this dataset have **weak relation_type labels** — many are generic verbs like "said", "took", "came" rather than semantic relations like "warns", "invites", "is_nephew_of". The triplet arrow citations inherit that weakness. A future pipeline change to prompt for stronger relation labels would let triplets shine more on questions like cc-004 and cc-011.

## Spoiler safety — hard invariant

Every Relationship passed the double-endpoint check in `load_allowed_relationships`. Of the 11 Relationships on disk:
- At cursor=1: 3 relationships had both endpoints visible (Scrooge's edges with Marley / nephew).
- At cursor=2: 7 relationships allowed.
- At cursor=3: 11 relationships allowed.

No question ever received a source with `chapter > max_chapter` in either mode. The pre-filter invariant holds.

## Recommendation

**Ship with the flag off by default** (spec matches this). Set `BOOKRAG_USE_TRIPLETS=1` when answering relationship-heavy questions; the precision lift is modest on this dataset but the spoiler and latency gates are well within budget. When the pipeline starts extracting stronger relation_type labels, re-run this eval and revisit the default.

## Reproduce

```bash
# Baseline
unset BOOKRAG_USE_TRIPLETS
python main.py &
python scripts/eval_query.py \
    --fixture evaluations/christmas_carol_questions.json \
    --mode baseline \
    --out evaluations/results/$(date +%Y-%m-%d)-baseline.md

# Triplets on
BOOKRAG_USE_TRIPLETS=1 python main.py &
python scripts/eval_query.py \
    --fixture evaluations/christmas_carol_questions.json \
    --mode triplets \
    --out evaluations/results/$(date +%Y-%m-%d)-triplets.md
```
