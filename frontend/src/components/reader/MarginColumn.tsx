import type { Card } from "../../lib/reader/cards";
import { AskCard } from "./AskCard";
import { NoteCard } from "./NoteCard";
import { S1EmptyCard } from "./S1EmptyCard";

export function MarginColumn({
  cards,
  visibleSids,
  focusedCardId,
  newlyCreatedNoteId,
  onBodyChange,
  onBodyCommit,
}: {
  cards: Card[];
  visibleSids: Set<string>;
  focusedCardId: string | null;
  newlyCreatedNoteId?: string | null;
  onBodyChange: (id: string, next: string) => void;
  onBodyCommit: (id: string) => void;
}) {
  const visible = cards.filter((c) => visibleSids.has(c.anchor));
  return (
    <aside
      aria-label="Margin cards"
      data-testid="margin-column"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 14,
        paddingTop: 40,
        width: 400,
      }}
    >
      {visible.length === 0 && <S1EmptyCard />}
      {visible.map((card) =>
        card.kind === "ask" ? (
          <AskCard key={card.id} card={card} flash={focusedCardId === card.id} />
        ) : (
          <NoteCard
            key={card.id}
            card={card}
            flash={focusedCardId === card.id}
            autoFocus={newlyCreatedNoteId === card.id}
            onBodyChange={onBodyChange}
            onBodyCommit={onBodyCommit}
          />
        ),
      )}
    </aside>
  );
}
