# Pedagogy Guide: Learning a Complex Codebase

A reference for how to deeply understand unfamiliar software systems. These principles informed the BookRAG curriculum and apply broadly to any codebase study.

---

## Core Learning Principles

### 1. Follow the Data, Not the Code

The fastest path to understanding a system is tracing what happens to data as it moves through. Code is the *how*; data flow is the *what* and *why*.

**Practice:** For each module, answer:
- What does the input look like? (format, shape, source)
- What does the output look like? (format, shape, destination)
- What is *lost* or *added* in the transformation?

### 2. Understand the Problem Before the Solution

Before reading `coref_resolver.py`, understand *why* coreference resolution exists. Before reading `ontology_discovery.py`, understand what an ontology is and why you'd want one.

**Practice:** For each module, first articulate the *problem it solves* in plain language. If you can't, you're not ready to read the code.

### 3. Layered Depth (The Spiral Approach)

Don't try to understand everything on the first pass. Make multiple passes at increasing depth:

| Pass | Goal | Time |
|------|------|------|
| **Skim** | What are the files? What do they import? | 5 min |
| **Shape** | What are the main functions/classes? What are inputs/outputs? | 15 min |
| **Logic** | How does the core algorithm work? | 30 min |
| **Edge cases** | What breaks? What's guarded against? | 20 min |
| **Design** | Why was it done *this way* and not another? | 10 min |

### 4. Test-Driven Understanding

Tests are documentation written by someone who understood the code. They show:
- **What the code is supposed to do** (assertions)
- **What edge cases matter** (test names)
- **What the expected data looks like** (fixtures)
- **What the author was worried about** (regression tests)

**Practice:** Read the test file *before* or *alongside* the implementation. If a test name says `test_distance_triggers_at_threshold`, you now know there's a threshold-based distance rule — and you know exactly what value triggers it.

### 5. Trace Decisions, Not Just Implementations

The hardest part of understanding a codebase isn't *what* it does — it's *why* it does it that way. Look for:
- Comments that say "we chose X because Y"
- Architecture decision records (ADRs) or plan documents
- Git commit messages that explain motivation
- Locked decisions lists (like in CLAUDE.md)

**Practice:** For each major design choice, ask: "What were the alternatives? Why were they rejected?"

---

## Effective Study Techniques

### The Explain-It-Back Method

After studying a module, explain it in your own words *without looking at the code*. If you get stuck, that's where your understanding has a gap. This is more effective than re-reading.

### The "What Would Break?" Method

For each module, ask: "If I deleted this function / changed this threshold / removed this edge case check, what would break downstream?" This forces you to understand dependencies and contracts between modules.

### The Input-Output Sandwich

For any function you're studying:
1. Look at a concrete input example (from tests or fixtures)
2. Look at the expected output (from test assertions)
3. *Then* read the code that transforms one to the other

This gives you anchor points so the algorithm isn't abstract.

### Diagram as You Go

Draw the data flow yourself. Don't just look at someone else's diagram. The act of creating it forces understanding. Keep it rough — boxes and arrows on paper work better than polished diagrams.

### Question-Driven Reading

Before reading a module, write down 3 questions you want answered. Read *for* those answers. This prevents passive reading where your eyes scan code but your brain doesn't engage.

---

## Pitfalls to Avoid

### 1. "I'll Just Read All the Code"
Reading code linearly (top to bottom, file by file) is the slowest way to learn. It's like reading a dictionary to learn a language. Instead, follow execution paths and data flows.

### 2. Skipping the "Boring" Parts
Config loading, state serialization, and error handling often encode the most important business rules and constraints. The "boring" infrastructure code tells you what the system *promises*.

### 3. Confusing "I Can Read It" with "I Understand It"
You understand code when you can:
- Predict what it does on a new input
- Explain *why* a design choice was made
- Identify what would break if you changed something
- Write a test for it from memory

### 4. Ignoring the Test Suite
Tests are the most reliable documentation. They're executable, maintained, and show concrete examples. Skipping them is like ignoring the answer key while studying.

### 5. Not Building a Mental Model
Individual function understanding isn't enough. You need a mental model of how components interact. After each module, update your mental picture of the whole system.

---

## Applied to BookRAG

This codebase is particularly well-suited to structured learning because:

1. **Linear pipeline** — modules execute in a defined order, each feeding the next
2. **Disk artifacts** — every intermediate output is saved, so you can inspect real data at each stage
3. **Rich test suite** — 805 tests with realistic fixtures (Christmas Carol data)
4. **Documented decisions** — `bookrag_pipeline_plan.md` captures *why*, not just *what*
5. **Two clear phases** — Phase 1 (NLP) and Phase 2 (KG) are conceptually distinct, letting you learn one before the other

**Recommended study order:** Follow the data through the pipeline. Start where the book enters (EPUB), end where the knowledge graph is queried. This mirrors the curriculum.

---

## Self-Assessment Rubric

After completing each curriculum module, rate yourself:

| Level | Description |
|-------|-------------|
| **1 - Aware** | I know this module exists and roughly what it does |
| **2 - Familiar** | I can describe the inputs, outputs, and main algorithm |
| **3 - Competent** | I can explain design decisions and predict behavior on new inputs |
| **4 - Proficient** | I could modify this module, write new tests, or debug issues in it |
| **5 - Expert** | I could redesign this module, evaluate alternatives, and teach it to others |

The curriculum targets **Level 3** for all modules. Revisit modules where you're below that after completing the full curriculum.
