# GraphRAG eval — baseline

- **Backend:** `http://localhost:8000`
- **Book:** `christmas_carol_e6ddcd76`
- **Mode:** `baseline` (BOOKRAG_USE_TRIPLETS unset)
- **Questions:** 12

## Aggregates

| Metric | Mean | Median |
|---|---|---|
| answer_similarity | 0.565 | 0.721 |
| source_chapter_precision | 0.750 | 1.000 |
| entity_recall | 0.708 | 1.000 |
| spoiler_safety | 1.000 | 1.000 |
| latency_ms | 1096 | 1186 |

**Spoiler leaks:** 0 / 12

## Per-question

| id | similarity | prec | recall | safe | ms |
|---|---|---|---|---|---|
| cc-001 | 0.860 | 1.00 | 1.00 | 1.0 | 1531 |
| cc-002 | 0.765 | 1.00 | 1.00 | 1.0 | 1328 |
| cc-003 | 0.083 | 1.00 | 0.00 | 1.0 | 1362 |
| cc-004 | 0.759 | 1.00 | 1.00 | 1.0 | 737 |
| cc-005 | 0.684 | 1.00 | 1.00 | 1.0 | 1379 |
| cc-006 | 0.822 | 1.00 | 0.50 | 1.0 | 1043 |
| cc-007 | 0.147 | 0.27 | 0.67 | 1.0 | 583 |
| cc-008 | 0.110 | 0.27 | 0.33 | 1.0 | 733 |
| cc-009 | 0.760 | 0.77 | 1.00 | 1.0 | 1875 |
| cc-010 | 0.646 | 1.00 | 1.00 | 1.0 | 1890 |
| cc-011 | 0.828 | 0.68 | 1.00 | 1.0 | 693 |
| cc-012 | 0.321 | 0.00 | 0.00 | 1.0 | 4 |

## Details

### cc-001 — Who is Marley and what is his relationship to Scrooge?

**Answer:** Marley is Scrooge's deceased business partner who appears as a ghost to warn Scrooge about the consequences of his miserly life. He informs Scrooge that he will be visited by three spirits.

**Top sources:**
- Marley's Ghost visits Scrooge to warn him of the consequences of his miserly lif
- Scrooge refuses to celebrate Christmas and is confronted by his nephew Fred who 
- Mr. Fezziwig — Scrooge's former employer, known for his generous and merry demea

### cc-002 — What kind of person is Scrooge at the start of the book?

**Answer:** At the start of the book, Scrooge is portrayed as a miserly and cold-hearted person who refuses to join his nephew Fred for Christmas dinner and dismisses holiday cheer. He also refuses to celebrate Christmas, illustrating his lack of warmth and generosity.

**Top sources:**
- Marley's Ghost visits Scrooge to warn him of the consequences of his miserly lif
- Scrooge recalls his former employer Mr. Fezziwig and reminisces about the joyful
- most other parts of the world — a general reference indicating regions outside t

### cc-003 — Who is Bob Cratchit?

**Answer:** I don't know yet.

**Top sources:**
- Marley — Scrooge's deceased business partner who appears as a ghost to warn Scro
- Scrooge refuses to celebrate Christmas and is confronted by his nephew Fred who 

### cc-004 — What does Fred invite Scrooge to?

**Answer:** Fred invites Scrooge to join him for Christmas dinner.

**Top sources:**
- Scrooge refuses to join his nephew Fred for Christmas dinner and dismisses his h
- Scrooge refuses to celebrate Christmas and is confronted by his nephew Fred who 
- Mr. Fezziwig — Scrooge's former employer, known for his generous and merry demea

### cc-005 — Why does Marley's ghost wear chains?

**Answer:** Marley's ghost wears chains as a representation of the burdens and consequences of his miserly life. The chains symbolize the greed and wrongdoings that he accumulated during his lifetime, and he appears to warn Scrooge about the fate that awaits him if he continues on the same path.

**Top sources:**
- Marley's Ghost visits Scrooge to warn him of the consequences of his miserly lif
- Marley — Scrooge's deceased business partner who appears as a ghost to warn Scro

### cc-006 — Who is Tiny Tim?

**Answer:** Tiny Tim is a member of the Cratchit family, observed by Scrooge during their Christmas dinner. He embodies a sense of love and hope within the family.

**Top sources:**
- Scrooge observes the Cratchit family's Christmas dinner, appreciating their love
- Marley — Scrooge's deceased business partner who appears as a ghost to warn Scro
- Scrooge refuses to celebrate Christmas and is confronted by his nephew Fred who 

### cc-007 — Who is the last spirit that visits Scrooge, and what does the spirit show him?

**Answer:** I don't know yet.

**Top sources:**
- Marley's Ghost visits Scrooge to warn him of the consequences of his miserly lif
- Scrooge's nephew Fred, along with friends, mockingly celebrate Scrooge's refusal
- Marley’s ghost appears to Scrooge, warning him of the consequences of his miserl

### cc-008 — What does Scrooge see on the bed that horrifies him?

**Answer:** I don't know yet.

**Top sources:**
- Marley's Ghost visits Scrooge to warn him of the consequences of his miserly lif
- Marley’s ghost appears to Scrooge, warning him of the consequences of his miserl
- Scrooge recalls his former employer Mr. Fezziwig and reminisces about the joyful

### cc-009 — How does Scrooge change by the end of the book?

**Answer:** By the end of the book, Scrooge transforms from a miserly figure into a generous and kind-hearted person. He realizes the importance of redemption through his interactions with the ghosts and acknowledges the spirit of Christmas embodied by his nephew Fred and the Cratchit family. This change is exemplified when he sends a large turkey to the Cratchit family and begins to embrace the joy and goodwill of the holiday season.

**Top sources:**
- Scrooge is shown his own neglected grave, realizing the fate that awaits him if 
- Scrooge's nephew Fred, along with friends, mockingly celebrate Scrooge's refusal
- Scrooge sends a large turkey to the Cratchit family as a gesture of goodwill.

### cc-010 — What is the central theme of A Christmas Carol?

**Answer:** The central theme of A Christmas Carol revolves around redemption, emphasizing Scrooge's transformation from a miserly figure to one capable of generosity. It highlights the potential for personal change through the spirit of Christmas, showcased by the joy and warmth of characters like Scrooge's nephew Fred and the Cratchit family. The contrast between Scrooge's initial misery and their holiday spirit underscores messages of charity, goodwill, and the true essence of Christmas.

**Top sources:**
- redemption — Scrooge's journey from a miserly figure to one capable of generosit
- Christmas spirit — The joy and warmth of Christmas as embodied by Fred and Tim C
- the spirit of Christmas — Embodied by Fred and the Cratchit family, this theme s

### cc-011 — What gift does Scrooge send to the Cratchits?

**Answer:** Scrooge sends a large turkey to the Cratchit family as a gesture of goodwill.

**Top sources:**
- Scrooge is shown his own neglected grave, realizing the fate that awaits him if 
- Scrooge sends a large turkey to the Cratchit family as a gesture of goodwill.
- Scrooge’s nephew — Scrooge's cheerful and optimistic nephew embodies the spirit 

### cc-012 — Does Tiny Tim die?

**Answer:** I don't have information about that yet based on your reading progress.

