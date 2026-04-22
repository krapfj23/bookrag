# GraphRAG eval — baseline

- **Backend:** `http://localhost:8000`
- **Book:** `christmas_carol_e6ddcd76`
- **Mode:** `baseline` (BOOKRAG_USE_TRIPLETS unset)
- **Questions:** 12

## Aggregates

| Metric | Mean | Median |
|---|---|---|
| answer_similarity | 0.489 | 0.615 |
| source_chapter_precision | 0.715 | 1.000 |
| entity_recall | 0.597 | 0.750 |
| spoiler_safety | 1.000 | 1.000 |
| latency_ms | 956 | 805 |

**Spoiler leaks:** 0 / 12

## Per-question

| id | similarity | prec | recall | safe | ms |
|---|---|---|---|---|---|
| cc-001 | 0.760 | 1.00 | 0.75 | 1.0 | 1827 |
| cc-002 | 0.758 | 1.00 | 1.00 | 1.0 | 1365 |
| cc-003 | 0.083 | 1.00 | 0.00 | 1.0 | 498 |
| cc-004 | 0.785 | 1.00 | 1.00 | 1.0 | 850 |
| cc-005 | 0.701 | 1.00 | 1.00 | 1.0 | 1064 |
| cc-006 | 0.099 | 1.00 | 0.00 | 1.0 | 759 |
| cc-007 | 0.147 | 0.00 | 0.33 | 1.0 | 454 |
| cc-008 | 0.110 | 0.00 | 0.33 | 1.0 | 469 |
| cc-009 | 0.765 | 0.79 | 0.75 | 1.0 | 2180 |
| cc-010 | 0.528 | 1.00 | 1.00 | 1.0 | 1278 |
| cc-011 | 0.808 | 0.78 | 1.00 | 1.0 | 718 |
| cc-012 | 0.321 | 0.00 | 0.00 | 1.0 | 4 |

## Details

### cc-001 — Who is Marley and what is his relationship to Scrooge?

**Answer:** Marley is a ghost who visits Scrooge and warns him about the consequences of his greed. He has a past relationship with Scrooge, representing the potential fate that awaits Scrooge if he does not change his ways.

**Top sources:**
- Scrooge is visited by the ghost of Marley, who warns him about the consequences 
- Scrooge refuses his nephew's invitation to Christmas dinner and expresses disdai
- The conversation between Scrooge and his nephew escalates as Scrooge dismisses h

### cc-002 — What kind of person is Scrooge at the start of the book?

**Answer:** At the start of the book, Scrooge is depicted as a miserable and irritable person. He shows disdain for Christmas and expresses the belief that people should not be joyful when they are poor. He dismisses his nephew's enthusiasm for the holiday, refuses his invitation to Christmas dinner, and generally exhibits a greedy and uncaring attitude toward others.

**Top sources:**
- Scrooge is visited by the ghost of Marley, who warns him about the consequences 
- Scrooge expresses irritation at the joy of Christmas and feels that people shoul
- The conversation between Scrooge and his nephew escalates as Scrooge dismisses h

### cc-003 — Who is Bob Cratchit?

**Answer:** I don't know yet.

**Top sources:**
- Scrooge is visited by the ghost of Marley, who warns him about the consequences 

### cc-004 — What does Fred invite Scrooge to?

**Answer:** Fred invites Scrooge to Christmas dinner.

**Top sources:**
- Scrooge's nephew visits him to wish him a Merry Christmas and invite him to dinn
- Scrooge is visited by the ghost of Marley, who warns him about the consequences 
- Scrooge refuses his nephew's invitation to Christmas dinner and expresses disdai

### cc-005 — Why does Marley's ghost wear chains?

**Answer:** Marley's ghost wears chains to symbolize the consequences of his greed and selfishness in life. The chains serve as a visual representation of the burdens he accumulated through his actions, warning Scrooge about the need to change his ways.

**Top sources:**
- Scrooge is visited by the ghost of Marley, who warns him about the consequences 

### cc-006 — Who is Tiny Tim?

**Answer:** I don't know yet.

**Top sources:**
- Scrooge is visited by the ghost of Marley, who warns him about the consequences 

### cc-007 — Who is the last spirit that visits Scrooge, and what does the spirit show him?

**Answer:** I don't know yet.

**Top sources:**
- Scrooge is visited by the ghost of Marley, who warns him about the consequences 
- Scrooge expresses irritation at the joy of Christmas and feels that people shoul
- Scrooge's nephew visits him to wish him a Merry Christmas and invite him to dinn

### cc-008 — What does Scrooge see on the bed that horrifies him?

**Answer:** I don't know yet.

**Top sources:**
- Scrooge is visited by the ghost of Marley, who warns him about the consequences 
- Scrooge expresses irritation at the joy of Christmas and feels that people shoul
- Scrooge's nephew visits him to wish him a Merry Christmas and invite him to dinn

### cc-009 — How does Scrooge change by the end of the book?

**Answer:** By the end of the book, Scrooge undergoes a significant transformation. He moves from being a "covetous old sinner," greedy and indifferent to the suffering of others, to becoming someone filled with joy and determination to embrace the holiday spirit. This change highlights the theme of redemption, as he expresses a desire to alter his fate after being visited by the spirits. Scrooge's interactions with his nephew Fred and the Cratchit family reveal his newfound understanding of generosity, kindness, and social responsibility. He actively participates in the spirit of Christmas by sending a large turkey to Bob Cratchit as a surprise gift, demonstrating his commitment to caring for others.

**Top sources:**
- redemption — The theme of redemption is shown through Scrooge's interactions wit
- the consequences of greed — The story illustrates how greed can lead to loneline
- Scrooge cries out to the spirit after seeing a vision of a man who died in his b

### cc-010 — What is the central theme of A Christmas Carol?

**Answer:** The central theme of A Christmas Carol revolves around the spirit of Christmas, emphasizing the importance of generosity, kindness, and family during the holiday season. This theme is contrasted with Scrooge's initial disdain for Christmas and his transformation into a more joyful and caring individual through the experiences he undergoes.

**Top sources:**
- Christmas Spirit — The theme manifests through Scrooge's ongoing disdain for Chr
- Scrooge witnesses the Cratchit family having dinner and celebrating Christmas de
- redemption — The theme of redemption is shown through Scrooge's interactions wit

### cc-011 — What gift does Scrooge send to the Cratchits?

**Answer:** Scrooge sends a boy to buy a large turkey to send to Bob Cratchit as a surprise Christmas gift.

**Top sources:**
- Scrooge sends a boy to buy a large turkey to send to Bob Cratchit as a surprise 
- Scrooge — a covetous old sinner, greedy and indifferent to others' suffering
- London — the city where Scrooge lives and works; a backdrop for the social issue

### cc-012 — Does Tiny Tim die?

**Answer:** I don't have information about that yet based on your reading progress.

