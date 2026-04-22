# GraphRAG eval — triplets

- **Backend:** `http://localhost:8000`
- **Book:** `christmas_carol_e6ddcd76`
- **Mode:** `triplets` (BOOKRAG_USE_TRIPLETS =1)
- **Questions:** 12

## Aggregates

| Metric | Mean | Median |
|---|---|---|
| answer_similarity | 0.560 | 0.697 |
| source_chapter_precision | 0.795 | 1.000 |
| entity_recall | 0.729 | 0.875 |
| spoiler_safety | 1.000 | 1.000 |
| latency_ms | 1206 | 1227 |

**Spoiler leaks:** 0 / 12

## Per-question

| id | similarity | prec | recall | safe | ms |
|---|---|---|---|---|---|
| cc-001 | 0.842 | 1.00 | 1.00 | 1.0 | 1797 |
| cc-002 | 0.763 | 1.00 | 1.00 | 1.0 | 1318 |
| cc-003 | 0.856 | 1.00 | 0.33 | 1.0 | 1845 |
| cc-004 | 0.785 | 1.00 | 1.00 | 1.0 | 1121 |
| cc-005 | 0.690 | 1.00 | 1.00 | 1.0 | 1451 |
| cc-006 | 0.808 | 1.00 | 1.00 | 1.0 | 1152 |
| cc-007 | 0.147 | 0.54 | 0.67 | 1.0 | 662 |
| cc-008 | 0.110 | 0.54 | 0.33 | 1.0 | 1034 |
| cc-009 | 0.704 | 0.83 | 0.75 | 1.0 | 2045 |
| cc-010 | 0.617 | 1.00 | 1.00 | 1.0 | 1302 |
| cc-011 | 0.073 | 0.63 | 0.67 | 1.0 | 747 |
| cc-012 | 0.321 | 0.00 | 0.00 | 1.0 | 4 |

## Details

### cc-001 — Who is Marley and what is his relationship to Scrooge?

**Answer:** Marley is the ghost of Scrooge's former business partner. He appears to Scrooge to warn him about the consequences of his selfish life and informs him about the forthcoming visits from three spirits.

**Top sources:**
- Marley's Ghost appears to Scrooge, warning him of the consequences of his selfis
- Scrooge is visited by the ghost of his former business partner Marley, who warns
- Scrooge meets his nephew and refuses his invitation for Christmas dinner, displa

### cc-002 — What kind of person is Scrooge at the start of the book?

**Answer:** At the start of the book, Scrooge is depicted as a selfish and miserly person. He shows disdain for the holiday season, refusing his nephew's invitation for Christmas dinner and arguing about the purpose of Christmas. He is unkind and begrudges the cheer of others, including his employee Bob Cratchit, who struggles to support his family.

**Top sources:**
- Scrooge meets his nephew and refuses his invitation for Christmas dinner, displa
- Marley's Ghost appears to Scrooge, warning him of the consequences of his selfis
- Scrooge is visited by the ghost of his former business partner Marley, who warns

### cc-003 — Who is Bob Cratchit?

**Answer:** Bob Cratchit is an employee of Scrooge who is struggling to support his family.

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

**Answer:** Marley's Ghost wears chains to symbolize the weight of his past actions and the consequences of his selfish life. The chains represent the burdens he carries as a result of his greed and need for personal gain, serving as a warning to Scrooge about the fate that awaits him if he does not change his ways.

**Top sources:**
- Marley's Ghost appears to Scrooge, warning him of the consequences of his selfis
- Scrooge is visited by the ghost of his former business partner Marley, who warns

### cc-006 — Who is Tiny Tim?

**Answer:** Tiny Tim is a character in "A Christmas Carol" who is part of Bob Cratchit's family. He is known for his health struggles and is highlighted during the family's Christmas dinner as they celebrate love and unity despite their difficulties. Tiny Tim is also famous for his heartfelt toast during the meal.

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

**Answer:** By the end of the book, Scrooge undergoes a significant transformation. He wakes up on Christmas Day with a newfound realization that it is not too late to change his ways. He expresses a desire to honor Christmas and to live fully in the past, present, and future, indicating a pivotal change in his character. This journey toward redemption highlights his evolution from a miser to someone who learns the value of family and generosity.

**Top sources:**
- Scrooge reflects on his past and expresses his desire to change, kneeling before
- Scrooge wakes up on Christmas Day, realizing it is not too late to change his wa
- Scrooge promises to honor Christmas and live in the past, present, and future, m

### cc-010 — What is the central theme of A Christmas Carol?

**Answer:** The central theme of 'A Christmas Carol' revolves around redemption and transformation, as illustrated by Scrooge's journey from a miserly and unloving person to one who embraces the joy, love, and generosity of the Christmas spirit.

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

