import { useNavigate } from "react-router-dom";
import { BookCover } from "./BookCover";
import { ProgressPill } from "./ProgressPill";

export type BookCardProps = {
  book_id: string;
  title: string;
  total_chapters: number;
  current_chapter: number;
};

export function BookCard({
  book_id,
  title,
  total_chapters,
  current_chapter,
}: BookCardProps) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      onClick={() => navigate(`/books/${book_id}/read`)}
      aria-label={`${title}, continue reading`}
      style={{
        display: "block",
        textAlign: "left",
        fontFamily: "var(--sans)",
        cursor: "pointer",
        width: 200,
        padding: 0,
        background: "transparent",
        border: 0,
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
    </button>
  );
}
