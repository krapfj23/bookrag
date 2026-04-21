import { BookCover } from "./BookCover";
import { ProgressPill } from "./ProgressPill";

export type BookCardProps = {
  book_id: string;
  title: string;
  total_chapters: number;
  current_chapter: number;
  onClick?: () => void;
};

export function BookCard({
  book_id,
  title,
  total_chapters,
  current_chapter,
  onClick,
}: BookCardProps) {
  return (
    <div
      onClick={onClick}
      style={{
        fontFamily: "var(--sans)",
        cursor: onClick ? "pointer" : "default",
        width: 200,
      }}
    >
      <BookCover book_id={book_id} title={title} />
      <div style={{ marginTop: 14 }}>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontSize: 16,
            fontWeight: 500,
            color: "var(--ink-0)",
            lineHeight: 1.25,
            letterSpacing: -0.2,
          }}
        >
          {title}
        </div>
        <div style={{ marginTop: 10 }}>
          <ProgressPill current={current_chapter} total={total_chapters} />
        </div>
      </div>
    </div>
  );
}
