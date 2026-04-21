export const MOODS = ["sage", "amber", "slate", "rose", "charcoal", "paper"] as const;
export type Mood = (typeof MOODS)[number];

/** Stable mood picker: sum char codes modulo MOODS.length. */
export function moodForBookId(bookId: string): Mood {
  let sum = 0;
  for (let i = 0; i < bookId.length; i++) sum += bookId.charCodeAt(i);
  return MOODS[sum % MOODS.length];
}
