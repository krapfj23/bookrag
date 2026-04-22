# GraphRAG eval — baseline

- **Backend:** `http://localhost:8000`
- **Book:** `christmas_carol_e6ddcd76`
- **Mode:** `baseline` (BOOKRAG_USE_TRIPLETS unset)
- **Questions:** 12

## Aggregates

| Metric | Mean | Median |
|---|---|---|
| answer_similarity | 0.561 | 0.710 |
| source_chapter_precision | 0.795 | 1.000 |
| entity_recall | 0.729 | 0.875 |
| spoiler_safety | 1.000 | 1.000 |
| latency_ms | 1031 | 913 |

**Spoiler leaks:** 0 / 12

## Per-question

| id | similarity | prec | recall | safe | ms |
|---|---|---|---|---|---|
| cc-001 | 0.821 | 1.00 | 1.00 | 1.0 | 987 |
| cc-002 | 0.757 | 1.00 | 1.00 | 1.0 | 1542 |
| cc-003 | 0.855 | 1.00 | 0.33 | 1.0 | 740 |
| cc-004 | 0.785 | 1.00 | 1.00 | 1.0 | 587 |
| cc-005 | 0.704 | 1.00 | 1.00 | 1.0 | 1484 |
| cc-006 | 0.838 | 1.00 | 1.00 | 1.0 | 942 |
| cc-007 | 0.147 | 0.54 | 0.67 | 1.0 | 706 |
| cc-008 | 0.110 | 0.54 | 0.33 | 1.0 | 884 |
| cc-009 | 0.716 | 0.83 | 0.75 | 1.0 | 2940 |
| cc-010 | 0.608 | 1.00 | 1.00 | 1.0 | 1087 |
| cc-011 | 0.073 | 0.63 | 0.67 | 1.0 | 476 |
| cc-012 | 0.321 | 0.00 | 0.00 | 1.0 | 3 |

## Details

### cc-001 — Who is Marley and what is his relationship to Scrooge?

**Answer:** Marley is Scrooge's former business partner who appears to warn Scrooge about the consequences of his selfish life and the forthcoming visits from three spirits.

**Top sources:**
- Marley's Ghost appears to Scrooge, warning him of the consequences of his selfis
- Scrooge is visited by the ghost of his former business partner Marley, who warns
- Scrooge meets his nephew and refuses his invitation for Christmas dinner, displa

### cc-002 — What kind of person is Scrooge at the start of the book?

**Answer:** At the start of the book, Scrooge is portrayed as a selfish and miserly person who displays disdain for the holiday season. He refuses an invitation to Christmas dinner from his cheerful nephew and argues against the purpose of Christmas. His negative attitude is further highlighted by his treatment of his employee, Bob Cratchit, who struggles to support his family.

**Top sources:**
- Scrooge meets his nephew and refuses his invitation for Christmas dinner, displa
- Marley's Ghost appears to Scrooge, warning him of the consequences of his selfis
- Scrooge is visited by the ghost of his former business partner Marley, who warns

### cc-003 — Who is Bob Cratchit?

**Answer:** Bob Cratchit is an employee of Scrooge, struggling to support his family.

**Top sources:**
- Bob Cratchit — an employee of Scrooge, struggling to support his family
- Camden Town — a location in London where Bob Cratchit lives
- Scrooge is visited by the ghost of his former business partner Marley, who warns

### cc-004 — What does Fred invite Scrooge to?

**Answer:** Fred invites Scrooge to Christmas dinner.

**Top sources:**
- Scrooge's nephew arrives to invite Scrooge to Christmas dinner, but Scrooge refu
- Scrooge meets his nephew and refuses his invitation for Christmas dinner, displa
- Marley's Ghost appears to Scrooge, warning him of the consequences of his selfis

### cc-005 — Why does Marley's ghost wear chains?

**Answer:** Marley's ghost wears chains as a symbol of the consequences of his selfish life. The chains represent the burdens and regrets he carries due to his past actions, serving as a warning to Scrooge about the fate that awaits him if he does not change his ways.

**Top sources:**
- Marley's Ghost appears to Scrooge, warning him of the consequences of his selfis
- Scrooge is visited by the ghost of his former business partner Marley, who warns

### cc-006 — Who is Tiny Tim?

**Answer:** Tiny Tim is a character in the story who is part of Bob Cratchit's family. He is notably discussed in the context of the family's struggles, particularly regarding his health, which is highlighted when Scrooge learns about the difficulties they face.

**Top sources:**
- Bob Cratchit and his family celebrate Christmas dinner, demonstrating love and u
- Scrooge learns about the struggles of Bob Cratchit's family, particularly focusi
- Scrooge is visited by the ghost of his former business partner Marley, who warns

### cc-007 — Who is the last spirit that visits Scrooge, and what does the spirit show him?

**Answer:** I don't know yet.

**Top sources:**
- Marley's Ghost appears to Scrooge, warning him of the consequences of his selfis
- Scrooge is visited by the ghost of his former business partner Marley, who warns
- Scrooge begrudges his nephew's Christmas cheer and argues with him about the pur

### cc-008 — What does Scrooge see on the bed that horrifies him?

**Answer:** I don't know yet.

**Top sources:**
- Marley's Ghost appears to Scrooge, warning him of the consequences of his selfis
- Scrooge is visited by the ghost of his former business partner Marley, who warns
- Scrooge begrudges his nephew's Christmas cheer and argues with him about the pur

### cc-009 — How does Scrooge change by the end of the book?

**Answer:** By the end of the book, Scrooge undergoes a significant transformation. He wakes up on Christmas Day, filled with joy and the realization that it is not too late to change his ways. Scrooge promises to honor Christmas and embrace the values of generosity and family, marking a pivotal change in his character from a miser to someone who learns to appreciate the spirit of the holiday and the importance of kindness.

**Top sources:**
- Scrooge reflects on his past and expresses his desire to change, kneeling before
- Scrooge wakes up on Christmas Day, realizing it is not too late to change his wa
- Scrooge promises to honor Christmas and live in the past, present, and future, m

### cc-010 — What is the central theme of A Christmas Carol?

**Answer:** The central theme of A Christmas Carol is redemption and transformation, as illustrated through Scrooge's journey from a miser to a more compassionate person. Other themes include the importance of family and love, the joy of Christmas, and the significance of generosity and kindness.

**Top sources:**
- Scrooge meets his nephew and refuses his invitation for Christmas dinner, displa
- Fezziwig hosts a Christmas party, demonstrating the joy and generosity of Christ
- Bob Cratchit and his family celebrate Christmas dinner, demonstrating love and u

### cc-011 — What gift does Scrooge send to the Cratchits?

**Answer:** I don't know yet.

**Top sources:**
- Scrooge — a tight-fisted hand at the grindstone; a squeezing, wrenching, graspin
- Bob Cratchit — Scrooge's underpaid clerk, a loving father who struggles to provi
- the city — implied as London, where Scrooge lives and works, reflecting a cold a

### cc-012 — Does Tiny Tim die?

**Answer:** I don't have information about that yet based on your reading progress.

